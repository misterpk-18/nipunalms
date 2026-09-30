"""Test setup.

- The test database (nipunalms_test) is rebuilt from db/*.sql once per test run.
- Each test runs inside a transaction that is rolled back afterwards; commits made by
  the request hooks become savepoint releases, so nothing leaks between tests.
"""
import itertools
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import scoped_session, sessionmaker

from app import create_app
from cli.database import rebuild_database
from config.database import db
from config.settings import TestingConfig
from models import CurriculumVersion, Role, User, UserRoleScope
from services.security import hash_password
from tests import helpers

PASSWORD = "Correct-horse-1"
SERVICE_KEY = TestingConfig.CRM_SERVICE_KEY


@pytest.fixture(scope="session", autouse=True)
def test_database():
    rebuild_database(TestingConfig.SQLALCHEMY_DATABASE_URI, TestingConfig.MIGRATIONS_DIR)


@pytest.fixture
def app():
    app = create_app("test")
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        original_session = db.session
        # A plain SQLAlchemy session: Flask-SQLAlchemy's Session.get_bind ignores `bind` and
        # would route straight to the engine, escaping the test transaction.
        db.session = scoped_session(sessionmaker(bind=connection, join_transaction_mode="create_savepoint"))

        yield app

        db.session.remove()
        db.session = original_session
        transaction.rollback()
        connection.close()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------- auth helpers

def _commit():
    """Release the test savepoint so setup data survives a failed (rolled-back) request."""
    db.session.commit()


@pytest.fixture
def run_sql(app):
    def _run(statement: str, **params):
        result = db.session.execute(text(statement), params)
        _commit()
        return result

    return _run


@pytest.fixture
def make_user(app):
    """make_user(roles=[("TRAINER", 1)], email=..., password=..., **user_columns) -> SimpleNamespace(user_id, email)."""
    counter = itertools.count(1)

    def _make(roles=(("SUPER_ADMIN", None),), email=None, password=PASSWORD, **columns):
        n = next(counter)
        user = User(
            full_name=columns.pop("full_name", f"Test User {n}"),
            email=email or f"user{n}@nipuna.test",
            password_hash=hash_password(password),
            **columns,
        )
        db.session.add(user)
        db.session.flush()
        for role_code, branch_id in roles:
            role_id = db.session.execute(select(Role.role_id).where(Role.role_code == role_code)).scalar_one()
            db.session.add(UserRoleScope(user_id=user.user_id, role_id=role_id, branch_id=branch_id))
        db.session.flush()
        created = SimpleNamespace(user_id=user.user_id, email=user.email)
        _commit()
        return created

    return _make


@pytest.fixture
def login(client):
    """login(login, password) -> Authorization header dict. `login` is a staff email, a Student ID or a student email."""

    def _login(login_value, password=PASSWORD):
        response = client.post("/api/v1/auth/login", json={"login": login_value, "password": password})
        assert response.status_code == 200, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['data']['token']}"}

    return _login


# ---------------------------------------------------------------- CRM events

@pytest.fixture
def crm_event(client):
    """crm_event(event_type, data, event_id=None, source_version=1, occurred_at=None, key=SERVICE_KEY) -> response."""
    counter = itertools.count(1)

    def _post(event_type, data, *, event_id=None, source_version=1, occurred_at=None, key=SERVICE_KEY):
        body = {
            "event_id": event_id or f"evt-{next(counter)}",
            "event_type": event_type,
            "source_version": source_version,
            "occurred_at": occurred_at or "2026-09-28T10:00:00+05:30",
            "data": data,
        }
        headers = {"X-Service-Key": key} if key is not None else {}
        return client.post("/api/v1/integrations/crm/events", json=body, headers=headers)

    return _post


@pytest.fixture
def catalog(app, crm_event):
    """Courses through CRM events, with Active curriculum versions for all but NIT-CRS-052 (Curriculum Mapping Pending).

    NIT-CRS-018: combo (tracks T1-T3 + included booster NIT-CRS-019); NIT-CRS-047 and NIT-CRS-019 standalone.
    """
    for data in helpers.catalog_courses():
        assert crm_event("CourseUpserted", data).status_code == 201

    from repositories import catalog as catalog_repo

    now = datetime.now(timezone.utc)
    versions = {}
    for label, course_code, track_code in helpers.CURRICULA:
        course = catalog_repo.get_course_by_code(course_code)
        component = catalog_repo.get_component_by_track_code(track_code) if track_code else None
        version = CurriculumVersion(course_id=course.course_id, component_id=component.component_id if component else None,
                                    version_label=label, status="Active", approved_at=now)
        db.session.add(version)
        versions[label] = version
    db.session.flush()
    _commit()
    return SimpleNamespace(versions={label: v.curriculum_version_id for label, v in versions.items()})


# ---------------------------------------------------------------- students

@pytest.fixture
def make_student(client, catalog, crm_event):
    """make_student(person_id="P-100", activate=True, **admission_data) -> SimpleNamespace(student_id, student_code, email,
    admission_id, enrolments, token). An activated student signs in with PASSWORD."""
    counter = itertools.count(1)

    def _make(person_id=None, *, activate=True, **kwargs):
        n = next(counter)
        person_id = person_id or f"P-{n}"
        kwargs.setdefault("admission_id", f"A-{n}")
        kwargs.setdefault("email", f"student{n}@example.test")
        response = crm_event("AdmissionQualified", helpers.admission_data(person_id=person_id, **kwargs))
        assert response.status_code == 201, response.get_json()
        data = response.get_json()["data"]
        result = data["result"]
        if activate:
            activated = client.post("/api/v1/auth/activate", json={"token": data["activation_token"], "password": PASSWORD})
            assert activated.status_code == 200, activated.get_json()
        return SimpleNamespace(student_id=result["student_id"], student_code=result["student_code"], email=kwargs["email"],
                               admission_id=result["admission_id"], enrolments=result["enrolments"],
                               token=data["activation_token"])

    return _make


# ---------------------------------------------------------------- batches

@pytest.fixture
def make_batch(app, catalog):
    """make_batch(branch_id=1, course_code="NIT-CRS-047", trainers=(user, ...), capacity=30, **batch_columns) -> Batch.
    The first trainer is Lead. Sessions can be added with make_session(batch, trainer_user, starts_at, ...)."""
    from models import Batch, BatchTrainer
    from repositories import catalog as catalog_repo

    def _make(branch_id=1, course_code="NIT-CRS-047", trainers=(), capacity=30, **columns):
        course = catalog_repo.get_course_by_code(course_code)
        batch = Batch(course_id=course.course_id, branch_id=branch_id, capacity=capacity, **columns)
        db.session.add(batch)
        db.session.flush()
        for index, trainer in enumerate(trainers):
            db.session.add(BatchTrainer(batch_id=batch.batch_id, trainer_user_id=trainer.user_id,
                                        role="Lead" if index == 0 else "Co-trainer"))
        db.session.flush()
        _commit()
        return batch

    return _make


@pytest.fixture
def make_session(app):
    from models import ClassSession

    def _make(batch, trainer, starts_at, hours=2, **columns):
        from datetime import timedelta

        session = ClassSession(batch_id=batch.batch_id, trainer_user_id=trainer.user_id, title=columns.pop("title", "Session"),
                               starts_at=starts_at, ends_at=starts_at + timedelta(hours=hours),
                               mode=columns.pop("mode", "Classroom"), **columns)
        db.session.add(session)
        db.session.flush()
        _commit()
        return session

    return _make


@pytest.fixture
def allocate(app):
    """allocate(student, batch, course_code=None) -> allocation. Puts the student's enrolment (that course) into the batch."""
    from repositories import students as students_repo
    from services import allocations

    def _allocate(student, batch):
        enrolment = next(e for e in students_repo.enrolments_of_student(student.student_id)
                         if e.course_id == batch.course_id)
        allocation = allocations.allocate(enrolment, batch)
        _commit()
        return allocation

    return _allocate

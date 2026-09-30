"""A small world for the student-services tests: two branches, staff of every role, students in batches.

Import the fixture into a test module:  from tests.services_fixtures import world  # noqa: F401
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from config.timezone import IST
from tests import helpers


@pytest.fixture
def world(make_user, make_student, make_batch, make_session, allocate, login):
    """Guntur: trainers t1 (batch B1, Java) and t2 (batch B2), AC, BM; students s1 (B1), s2 (B2). Vijayawada: AC, BM, student s3.
    Also an admin (Super Admin) and a founder. `h(person)` returns the Authorization headers of a person or student."""
    people = SimpleNamespace(
        t1=make_user(roles=[("TRAINER", 1)], full_name="Trainer One"),
        t2=make_user(roles=[("TRAINER", 1)], full_name="Trainer Two"),
        ac=make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="Coordinator Guntur"),
        bm=make_user(roles=[("BRANCH_MANAGER", 1)], full_name="Manager Guntur"),
        ac_vij=make_user(roles=[("ACADEMIC_COORDINATOR", 2)], full_name="Coordinator Vijayawada"),
        bm_vij=make_user(roles=[("BRANCH_MANAGER", 2)], full_name="Manager Vijayawada"),
        admin=make_user(roles=[("SUPER_ADMIN", None)], full_name="Super Admin"),
        founder=make_user(roles=[("FOUNDER_CEO", None)], full_name="Founder"),
    )
    batches = SimpleNamespace(
        b1=make_batch(1, trainers=[people.t1], state="Running"),
        b2=make_batch(1, trainers=[people.t2], state="Running"),
    )
    students = SimpleNamespace(
        s1=make_student(name="Student One", mobile="9876500417"),
        s2=make_student(name="Student Two"),
        s3=make_student(name="Student Three", service="NIT-VIJ", collecting="NIT-GNT", admission_id="A-VIJ"),
    )
    allocate(students.s1, batches.b1)
    allocate(students.s2, batches.b2)
    now = datetime.now(timezone.utc)
    sessions = SimpleNamespace(
        upcoming=make_session(batches.b1, people.t1, now + timedelta(days=2), title="Streams and lambdas"),
        delivered=make_session(batches.b1, people.t1, now - timedelta(days=3), title="OOP recap", state="Delivered", delivered_at=now - timedelta(days=3)),
    )
    headers: dict = {}

    def h(person):
        key = person.student_code if hasattr(person, "student_code") else person.email
        if key not in headers:
            headers[key] = login(key)
        return headers[key]

    return SimpleNamespace(people=people, batches=batches, students=students, sessions=sessions, h=h, IST=IST, helpers=helpers)

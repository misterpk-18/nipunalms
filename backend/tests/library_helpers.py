"""A small Guntur / Vijayawada world for the content, recording and access-extension tests, plus request helpers."""
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from config.database import db
from config.timezone import today_ist
from models import CurriculumModule, CurriculumTopic

API = "/api/v1"
PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n"


def build_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql) -> SimpleNamespace:
    """Guntur batch G1 (Java, trainer t1, Running) with a module of two topics and sessions; student s1 allocated and
    joined (2026-03-02), s2 not allocated, s3 at Vijayawada in batch V1 (trainer tv)."""
    people = SimpleNamespace(
        t1=make_user(roles=[("TRAINER", 1)], full_name="Trainer One"),
        t2=make_user(roles=[("TRAINER", 1)], full_name="Trainer Two"),
        tv=make_user(roles=[("TRAINER", 2)], full_name="Trainer Vij"),
        ac=make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur"),
        ac2=make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur Two"),
        ac_vij=make_user(roles=[("ACADEMIC_COORDINATOR", 2)], full_name="AC Vijayawada"),
        bm=make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM Guntur"),
        bm_vij=make_user(roles=[("BRANCH_MANAGER", 2)], full_name="BM Vijayawada"),
        admin=make_user(roles=[("SUPER_ADMIN", None)], full_name="Super Admin"),
        founder=make_user(roles=[("FOUNDER_CEO", None)], full_name="Founder"),
    )
    version_id = catalog.versions["CV 5.1"]
    module = CurriculumModule(curriculum_version_id=version_id, title="Core Java", sort_order=1)
    db.session.add(module)
    db.session.flush()
    topics = SimpleNamespace(
        oop=CurriculumTopic(module_id=module.module_id, title="OOP & Collections", sort_order=1),
        streams=CurriculumTopic(module_id=module.module_id, title="Streams & Lambdas", sort_order=2),
    )
    db.session.add_all([topics.oop, topics.streams])
    db.session.commit()

    g1 = make_batch(1, "NIT-CRS-047", trainers=[people.t1], state="Running", curriculum_version_id=version_id)
    v1 = make_batch(2, "NIT-CRS-047", trainers=[people.tv], state="Running", curriculum_version_id=version_id)
    students = SimpleNamespace(
        s1=make_student(),
        s2=make_student(),
        s3=make_student(service="NIT-VIJ", collecting="NIT-GNT", admission_id="A-VIJ"),
    )
    allocate(students.s1, g1)
    allocate(students.s3, v1)
    run_sql("UPDATE enrolments SET status = 'Active', joining_date = :d WHERE student_id = :s", d="2026-03-02", s=students.s1.student_id)

    now = datetime.now(timezone.utc)
    delivered = make_session(g1, people.t1, now - timedelta(days=3), title="OOP basics", topic_id=topics.oop.topic_id,
                             state="Delivered", delivered_at=now - timedelta(days=3, hours=-2))
    upcoming = make_session(g1, people.t1, now + timedelta(days=3), title="Streams intro", topic_id=topics.streams.topic_id)
    return SimpleNamespace(people=people, module=module, topics=topics, g1=g1, v1=v1, students=students, version_id=version_id,
                           delivered=delivered, upcoming=upcoming)


def auth(login, who) -> dict:
    """Authorization header for a made user (staff email) or student (Student ID)."""
    return login(getattr(who, "email", None) or who.student_code)


def upload_data(title="Regression notes", content_type="PDF", *, filename="notes.pdf", content=PDF, **fields) -> dict:
    """Multipart form fields for POST /content-items (or /versions when only `file` is used)."""
    data = {"title": title, "content_type": content_type, **{k: str(v) for k, v in fields.items()}}
    if filename is not None:
        data["file"] = (io.BytesIO(content), filename)
    return data


def create_item(client, headers, world, *, expect=201, **kwargs):
    """POST /content-items as multipart for the world's topic (OOP) and batch (G1) unless overridden."""
    fields = {"topic_id": world.topics.oop.topic_id, "batch_id": world.g1.batch_id, **kwargs.pop("fields", {})}
    response = client.post(f"{API}/content-items", data=upload_data(**fields, **kwargs), headers=headers, content_type="multipart/form-data")
    assert response.status_code == expect, response.get_json()
    return response.get_json()["data"] if expect == 201 else response.get_json()


def post(client, path, headers, expect=200, **kwargs):
    response = client.post(f"{API}{path}", headers=headers, **kwargs)
    assert response.status_code == expect, response.get_json()
    return response.get_json().get("data")


def get(client, path, headers, expect=200):
    response = client.get(f"{API}{path}", headers=headers)
    assert response.status_code == expect, response.get_json()
    return response.get_json().get("data")


def release_item(client, world, login, item_id, *, trainer=None, coordinator=None):
    """Submit as the trainer and approve + release as the coordinator."""
    trainer_headers = auth(login, trainer or world.people.t1)
    coordinator_headers = auth(login, coordinator or world.people.ac)
    post(client, f"/content-items/{item_id}/submit", trainer_headers)
    return post(client, f"/content-items/{item_id}/review", coordinator_headers, json={"decision": "approve", "release": True})


def days_ago(days: int) -> str:
    return (today_ist() - timedelta(days=days)).isoformat()


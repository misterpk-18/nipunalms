"""A small world for the assessment tests: two Guntur batches (G1, G2), a Vijayawada batch (V1), their trainers, coordinators and students.

    G1  Java Full Stack, trainer g1, students s1 and s2, with a module (2 topics) of curriculum version CV 5.1
    G2  Java Full Stack, trainer g2, student s3
    V1  Java Full Stack at Vijayawada, trainer v1, student s4
Every login uses the shared test password.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from config.database import db
from models import CurriculumModule, CurriculumTopic
from tests.conftest import _commit

API = "/api/v1"


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def hours(n: float) -> datetime:
    """A moment n hours from now (negative = past)."""
    return datetime.now(timezone.utc) + timedelta(hours=n)


@pytest.fixture
def world(make_user, make_student, make_batch, allocate, login, catalog):
    people = {
        "g1": make_user(roles=[("TRAINER", 1)], full_name="Trainer G1"),
        "g2": make_user(roles=[("TRAINER", 1)], full_name="Trainer G2"),
        "v1": make_user(roles=[("TRAINER", 2)], full_name="Trainer V1"),
        "ac": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur"),
        "ac2": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur Two"),
        "ac_vij": make_user(roles=[("ACADEMIC_COORDINATOR", 2)]),
        "bm": make_user(roles=[("BRANCH_MANAGER", 1)]),
        "admin": make_user(roles=[("SUPER_ADMIN", None)]),
    }
    version_id = catalog.versions["CV 5.1"]
    batches = {
        "G1": make_batch(1, trainers=[people["g1"]], state="Running", curriculum_version_id=version_id),
        "G2": make_batch(1, trainers=[people["g2"]], state="Running", curriculum_version_id=version_id),
        "V1": make_batch(2, trainers=[people["v1"]], state="Running", curriculum_version_id=version_id),
    }
    module = CurriculumModule(curriculum_version_id=version_id, title="Core Java", sort_order=1)
    db.session.add(module)
    db.session.flush()
    topics = [CurriculumTopic(module_id=module.module_id, title=t, sort_order=i) for i, t in enumerate(["OOP & Collections", "Streams"], 1)]
    db.session.add_all(topics)
    db.session.flush()

    students = {
        "s1": make_student(),
        "s2": make_student(),
        "s3": make_student(),
        "s4": make_student(service="NIT-VIJ", collecting="NIT-VIJ", original="NIT-VIJ"),
    }
    allocate(students["s1"], batches["G1"])
    allocate(students["s2"], batches["G1"])
    allocate(students["s3"], batches["G2"])
    allocate(students["s4"], batches["V1"])
    _commit()

    headers = {name: login(user.email) for name, user in people.items()}
    headers.update({name: login(s.student_code) for name, s in students.items()})
    return SimpleNamespace(people=people, batches=batches, students=students, h=headers, topics=topics, module=module)


def assignment_body(world, **overrides) -> dict:
    body = {
        "batch_id": world.batches["G1"].batch_id, "topic_id": world.topics[0].topic_id, "title": "Regression on housing dataset",
        "brief": "Build and evaluate a model.", "max_marks": 20, "due_at": iso(hours(48)),
    }
    return {**body, **overrides}


@pytest.fixture
def released_assignment(client, world):
    """An assignment of G1 released to its students, due in 48 hours."""
    response = client.post(f"{API}/assignments", json=assignment_body(world, release_now=True), headers=world.h["g1"])
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def question_body(world, **overrides) -> dict:
    body = {
        "course_id": world.batches["G1"].course_id, "question_type": "Single choice", "stem": "Which metric suits an imbalanced classifier?",
        "options": [{"key": "A", "text": "Accuracy"}, {"key": "B", "text": "F1-score"}, {"key": "C", "text": "R2"}],
        "answer_key": {"option": "B"}, "marks": 2, "difficulty": "Medium", "tags": ["metrics"],
    }
    return {**body, **overrides}


def make_question(client, world, *, approve=True, **overrides) -> dict:
    """A question authored by trainer g1 and (by default) approved by the Guntur coordinator."""
    response = client.post(f"{API}/questions", json=question_body(world, **overrides), headers=world.h["g1"])
    assert response.status_code == 201, response.get_json()
    question = response.get_json()["data"]
    if approve:
        approved = client.post(f"{API}/questions/{question['question_id']}/approve", headers=world.h["ac"])
        assert approved.status_code == 200, approved.get_json()
        question = approved.get_json()["data"]
    return question


def make_test(client, world, question_ids, *, kind="Practice quiz", release=True, **overrides) -> dict:
    """A test of G1 with the given approved questions, approved (formal kinds) and released; returns the test as the trainer sees it."""
    body = {"batch_id": world.batches["G1"].batch_id, "kind": kind, "title": f"{kind} test", **overrides}
    if kind in ("Module test", "Final test", "Coding exercise"):
        body.setdefault("closes_at", iso(hours(72)))
        body.setdefault("pass_marks", 2)
    response = client.post(f"{API}/tests", json=body, headers=world.h["g1"])
    assert response.status_code == 201, response.get_json()
    test = response.get_json()["data"]
    put = client.put(f"{API}/tests/{test['test_id']}/questions", json={"questions": [{"question_id": q} for q in question_ids]},
                     headers=world.h["g1"])
    assert put.status_code == 200, put.get_json()
    if kind in ("Module test", "Final test", "Coding exercise"):
        approved = client.post(f"{API}/tests/{test['test_id']}/approve", headers=world.h["ac"])
        assert approved.status_code == 200, approved.get_json()
    if release:
        released = client.post(f"{API}/tests/{test['test_id']}/release", json={}, headers=world.h["g1"])
        assert released.status_code == 200, released.get_json()
        return released.get_json()["data"]
    return client.get(f"{API}/tests/{test['test_id']}", headers=world.h["g1"]).get_json()["data"]

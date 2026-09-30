"""Results: moderation, publication, what students see, and the coordinator's review queue."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from models import AuditLog, Notification, Result
from tests.assessment_world import API, assignment_body, hours, iso, released_assignment, world  # noqa: F401 (fixtures)


@pytest.fixture
def provisional(client, world, released_assignment):
    """Both G1 students submitted; the trainer reviewed them with 18 and 12 marks (provisional results)."""
    marks = {"s1": 18, "s2": 12}
    ids = {}
    for who, mark in marks.items():
        sub = client.post(f"{API}/assignments/{released_assignment['assignment_id']}/submissions", json={"body_text": who}, headers=world.h[who]).get_json()["data"]
        client.post(f"{API}/submissions/{sub['submission_id']}/review", json={"outcome": "Reviewed", "feedback": "ok", "marks": mark}, headers=world.h["g1"])
    for r in db.session.execute(select(Result)).scalars():
        ids[r.student_id] = r.result_id
    return released_assignment, [ids[world.students["s1"].student_id], ids[world.students["s2"].student_id]]


def test_staff_see_provisional_results_and_students_see_only_pending_rows(client, world, provisional):
    assignment, (r1, _) = provisional
    rows = client.get(f"{API}/results?assignment_id={assignment['assignment_id']}", headers=world.h["g1"]).get_json()
    assert rows["meta"]["total"] == 2 and {r["status"] for r in rows["data"]} == {"Provisional"}
    assert {r["provisional_marks"] for r in rows["data"]} == {"18.00", "12.00"}
    assert client.get(f"{API}/results", headers=world.h["g2"]).get_json()["data"] == []
    assert client.get(f"{API}/results?batch_id={world.batches['G1'].batch_id}", headers=world.h["g2"]).status_code == 404
    assert client.get(f"{API}/results", headers=world.h["s1"]).status_code == 403

    mine = client.get(f"{API}/me/results", headers=world.h["s1"]).get_json()["data"]
    assert len(mine) == 1 and mine[0]["score"] is None and mine[0]["state"] == "Provisional — pending moderation"
    assert client.get(f"{API}/me/results", headers=world.h["g1"]).status_code == 403


def test_moderation_adjusts_marks_with_a_reason_and_is_audited(client, world, provisional):
    _, (r1, _) = provisional
    url = f"{API}/results/{r1}/moderate"
    assert client.post(url, json={"marks": 19, "reason": "Rubric correction"}, headers=world.h["g1"]).status_code == 403  # trainers do not moderate
    assert client.post(url, json={"marks": 19, "reason": "Rubric correction"}, headers=world.h["ac_vij"]).status_code == 404
    assert client.post(url, json={"marks": 19}, headers=world.h["ac"]).status_code == 400  # a reason is required
    assert client.post(url, json={"marks": 25, "reason": "Too generous"}, headers=world.h["ac"]).status_code == 400  # above the maximum
    assert client.post(url, json={"marks": 18, "reason": "No change at all"}, headers=world.h["ac"]).status_code == 400
    moderated = client.post(url, json={"marks": 19, "reason": "Rubric correction"}, headers=world.h["ac"])
    assert moderated.status_code == 200
    body = moderated.get_json()["data"]
    assert body["status"] == "Moderated" and body["provisional_marks"] == "18.00" and body["moderated_marks"] == "19.00"
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "moderate")).scalars().one()
    assert entry.old_values["marks"] == "18.00" and entry.new_values["marks"] == "19.00" and entry.reason == "Rubric correction"


def test_publishing_makes_the_counting_marks_final_and_tells_students(client, world, provisional):
    assignment, (r1, r2) = provisional
    client.post(f"{API}/results/{r1}/moderate", json={"marks": 19, "reason": "Rubric correction"}, headers=world.h["ac"])
    assert client.post(f"{API}/results/publish", json={"result_ids": [r1]}, headers=world.h["g1"]).status_code == 403
    assert client.post(f"{API}/results/publish", json={"result_ids": [r1]}, headers=world.h["ac_vij"]).status_code == 404
    assert client.post(f"{API}/results/publish", json={}, headers=world.h["ac"]).status_code == 400

    published = client.post(f"{API}/results/publish", json={"assignment_id": assignment["assignment_id"]}, headers=world.h["ac"]).get_json()["data"]
    assert published["published"] == 2
    finals = {r["student"]["student_code"]: r["final_marks"] for r in published["results"]}
    assert sorted(finals.values()) == ["12.00", "19.00"]
    assert client.post(f"{API}/results/publish", json={"assignment_id": assignment["assignment_id"]}, headers=world.h["ac"]).status_code == 422  # nothing left
    assert client.post(f"{API}/results/{r1}/moderate", json={"marks": 5, "reason": "Late change"}, headers=world.h["ac"]).status_code == 422
    assert db.session.execute(select(AuditLog).where(AuditLog.action == "publish")).scalars().all().__len__() == 2
    assert db.session.execute(select(Notification).where(Notification.category == "Results")).scalars().all().__len__() == 2

    mine = client.get(f"{API}/me/results", headers=world.h["s1"]).get_json()["data"][0]
    assert mine["score"] == "19.00 / 20.00" and mine["state"] == "Published"
    assert client.get(f"{API}/me/results", headers=world.h["s2"]).get_json()["data"][0]["score"] == "12.00 / 20.00"


def test_the_database_keeps_published_results_final(client, world, provisional, run_sql):
    _, (r1, _) = provisional
    client.post(f"{API}/results/publish", json={"result_ids": [r1]}, headers=world.h["ac"])
    with pytest.raises(DBAPIError, match="published result cannot be changed"):
        run_sql("UPDATE results SET final_marks = 1 WHERE result_id = :id", id=r1)
    db.session.rollback()


def test_review_queue_summarises_per_assessment_and_lists_tests_not_ready(client, world, provisional):
    assignment, (r1, _) = provisional
    client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Final test", "title": "Final test"}, headers=world.h["g1"])
    rows = client.get(f"{API}/assessment-reviews", headers=world.h["ac"]).get_json()["data"]
    by_kind = {r["kind"]: r for r in rows}
    assert by_kind["Assignment"]["state"] == "Awaiting moderation" and by_kind["Assignment"]["counts"]["provisional"] == 2
    assert by_kind["Assignment"]["can_moderate"] is True
    assert by_kind["Test"]["state"] == "Configuration Pending" and "Set the pass marks" in by_kind["Test"]["gaps"]

    client.post(f"{API}/results/publish", json={"result_ids": [r1]}, headers=world.h["ac"])
    after = [r for r in client.get(f"{API}/assessment-reviews", headers=world.h["ac"]).get_json()["data"] if r["kind"] == "Assignment"][0]
    assert after["counts"] == {"provisional": 1, "moderated": 0, "published": 1, "awaiting_grading": 0}

    assert [r for r in client.get(f"{API}/assessment-reviews", headers=world.h["ac_vij"]).get_json()["data"]] == []
    bm = client.get(f"{API}/assessment-reviews", headers=world.h["bm"]).get_json()["data"]
    assert bm and all(r["can_moderate"] is False for r in bm)
    assert client.get(f"{API}/assessment-reviews", headers=world.h["s1"]).status_code == 403

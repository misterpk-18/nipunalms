"""Tests: configuration and release, the server-authoritative timer, receipts, scoring and grading."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from models import AuditLog, Notification, Result, TestAttempt
from tests.assessment_world import API, hours, iso, make_question, make_test, world  # noqa: F401 (fixtures)

RECEIPT = re.compile(r"^RCPT-T-\d{5}$")


def start(client, world, test_id, who="s1"):
    return client.post(f"{API}/tests/{test_id}/attempts", headers=world.h[who])


def answer(client, world, attempt_id, answers, who="s1"):
    return client.put(f"{API}/attempts/{attempt_id}/answers", json={"answers": answers}, headers=world.h[who])


def expire(run_sql, attempt_id, minutes_ago=1):
    """Move the attempt's server deadline into the past (and its start before that)."""
    run_sql("UPDATE test_attempts SET started_at = now() - interval '3 hours', deadline_at = now() - make_interval(mins => :m) WHERE attempt_id = :id",
            m=minutes_ago, id=attempt_id)


@pytest.fixture
def quiz(client, world):
    """A released practice quiz (one choice question, one short answer) and the two questions."""
    q1 = make_question(client, world, marks=2)
    q2 = make_question(client, world, question_type="Short answer", options=[], answer_key={"variants": ["random forest"]}, stem="Name an ensemble", marks=1)
    test = make_test(client, world, [q1["question_id"], q2["question_id"]])
    return test, q1, q2


# ---------------------------------------------------------------- configuration and release

def test_kind_defaults_and_what_is_missing(client, world):
    body = {"batch_id": world.batches["G1"].batch_id, "kind": "Module test", "title": "Supervised Learning module test"}
    test = client.post(f"{API}/tests", json=body, headers=world.h["g1"]).get_json()["data"]
    assert test["test_code"].startswith("TST-") and test["duration_minutes"] == 30 and test["attempts_allowed"] == 1
    assert test["release_status"] == "Configuration Pending" and test["status"] == "Configuration Pending"
    assert test["is_formal"] is True and set(test["gaps"]) == {"Select the questions", "Set the pass marks", "Set the closing time", "Academic Coordinator approval"}

    practice = client.post(f"{API}/tests", json={**body, "kind": "Practice quiz", "title": "Warm-up"}, headers=world.h["g1"]).get_json()["data"]
    assert practice["duration_minutes"] is None and practice["attempts_allowed"] is None and practice["is_formal"] is False
    assert practice["gaps"] == ["Select the questions"]

    for kind, minutes in (("Final test", 60), ("Coding exercise", 90)):
        made = client.post(f"{API}/tests", json={**body, "kind": kind}, headers=world.h["g1"]).get_json()["data"]
        assert made["duration_minutes"] == minutes


def test_only_the_batch_staff_change_tests(client, world):
    body = {"batch_id": world.batches["G1"].batch_id, "kind": "Practice quiz", "title": "Quiz"}
    assert client.post(f"{API}/tests", json=body, headers=world.h["s1"]).status_code == 403
    assert client.post(f"{API}/tests", json=body, headers=world.h["bm"]).status_code == 403
    assert client.post(f"{API}/tests", json=body, headers=world.h["g2"]).status_code == 404
    assert client.post(f"{API}/tests", json=body, headers=world.h["ac_vij"]).status_code == 404
    test = client.post(f"{API}/tests", json=body, headers=world.h["g1"]).get_json()["data"]
    url = f"{API}/tests/{test['test_id']}"
    assert client.patch(url, json={"title": "x"}, headers=world.h["g2"]).status_code == 404
    assert client.patch(url, json={"title": "x"}, headers=world.h["bm"]).status_code == 403
    assert client.get(url, headers=world.h["g2"]).status_code == 404
    assert client.get(url, headers=world.h["s3"]).status_code == 404  # a student of another batch
    assert client.get(url, headers=world.h["s1"]).status_code == 200
    assert client.get(url, headers=world.h["bm"]).status_code == 200


def test_settings_are_validated(client, world):
    body = {"batch_id": world.batches["G1"].batch_id, "kind": "Module test", "title": "T"}
    assert client.post(f"{API}/tests", json={**body, "opens_at": iso(hours(5)), "closes_at": iso(hours(4))}, headers=world.h["g1"]).status_code == 400
    assert client.post(f"{API}/tests", json={**body, "opens_at": iso(hours(5)), "closes_at": iso(hours(5.2))}, headers=world.h["g1"]).status_code == 400  # window < 30 min
    assert client.post(f"{API}/tests", json={**body, "duration_minutes": 0}, headers=world.h["g1"]).status_code == 400
    assert client.post(f"{API}/tests", json={**body, "module_id": 999999}, headers=world.h["g1"]).status_code == 400
    assert client.post(f"{API}/tests", json={**body, "reviewer_user_id": world.people["g2"].user_id}, headers=world.h["g1"]).status_code == 400
    ok = client.post(f"{API}/tests", json={**body, "module_id": world.module.module_id}, headers=world.h["g1"])
    assert ok.status_code == 201 and ok.get_json()["data"]["module"]["title"] == "Core Java"


def test_question_selection_rules(client, world):
    approved = make_question(client, world)
    draft = make_question(client, world, approve=False)
    other_branch = client.post(f"{API}/questions", json={"course_id": world.batches["V1"].course_id, "question_type": "True / False", "stem": "x",
                                                        "answer_key": {"value": True}}, headers=world.h["v1"]).get_json()["data"]
    test = client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Practice quiz", "title": "Q"},
                       headers=world.h["g1"]).get_json()["data"]
    url = f"{API}/tests/{test['test_id']}/questions"
    assert client.put(url, json={"questions": [{"question_id": draft["question_id"]}]}, headers=world.h["g1"]).status_code == 400  # not approved
    assert client.put(url, json={"questions": [{"question_id": other_branch["question_id"]}]}, headers=world.h["g1"]).status_code == 400
    assert client.put(url, json={"questions": [{"question_id": approved["question_id"]}, {"question_id": approved["question_id"]}]},
                      headers=world.h["g1"]).status_code == 400  # twice
    assert client.put(url, json={"questions": [{"question_id": approved["question_id"]}]}, headers=world.h["g2"]).status_code == 404
    done = client.put(url, json={"questions": [{"question_id": approved["question_id"], "marks": 3}]}, headers=world.h["g1"])
    assert done.status_code == 200
    body = done.get_json()["data"]
    assert body["question_count"] == 1 and body["total_marks"] == "3.00" and body["release_status"] == "Not Released"
    assert body["questions"][0]["answer_key"] == {"option": "B"}  # the trainer sees the key

    # A later edit to the bank (a new version) does not change the frozen test
    new = client.post(f"{API}/questions/{approved['question_id']}/new-version", headers=world.h["g1"]).get_json()["data"]
    client.patch(f"{API}/questions/{new['question_id']}", json={"stem": "Completely different"}, headers=world.h["g1"])
    client.post(f"{API}/questions/{new['question_id']}/approve", headers=world.h["ac"])
    frozen = client.get(f"{API}/tests/{test['test_id']}", headers=world.h["g1"]).get_json()["data"]["questions"][0]
    assert frozen["stem"] == "Which metric suits an imbalanced classifier?" and frozen["question_version"] == 1


def test_a_formal_test_needs_approval_and_a_change_asks_again(client, world):
    q = make_question(client, world, marks=2)
    test = client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Module test", "title": "Module test",
                                             "closes_at": iso(hours(72)), "pass_marks": 1}, headers=world.h["g1"]).get_json()["data"]
    tid = test["test_id"]
    client.put(f"{API}/tests/{tid}/questions", json={"questions": [{"question_id": q["question_id"]}]}, headers=world.h["g1"])
    state = client.get(f"{API}/tests/{tid}", headers=world.h["g1"]).get_json()["data"]
    assert state["release_status"] == "Configuration Pending" and state["gaps"] == ["Academic Coordinator approval"]
    assert client.post(f"{API}/tests/{tid}/release", json={}, headers=world.h["g1"]).status_code == 422
    assert client.post(f"{API}/tests/{tid}/approve", headers=world.h["g1"]).status_code == 403  # trainers do not approve
    assert client.post(f"{API}/tests/{tid}/approve", headers=world.h["ac_vij"]).status_code == 404
    approved = client.post(f"{API}/tests/{tid}/approve", headers=world.h["ac"])
    assert approved.status_code == 200 and approved.get_json()["data"]["release_status"] == "Not Released"
    assert db.session.execute(select(AuditLog).where(AuditLog.entity_type == "test", AuditLog.action == "approve")).scalars().one()

    client.patch(f"{API}/tests/{tid}", json={"pass_marks": 2}, headers=world.h["g1"])  # settings changed after approval
    again = client.get(f"{API}/tests/{tid}", headers=world.h["g1"]).get_json()["data"]
    assert again["release_status"] == "Configuration Pending" and again["approved_at"] is None
    client.post(f"{API}/tests/{tid}/approve", headers=world.h["ac"])
    assert client.patch(f"{API}/tests/{tid}", json={"pass_marks": 99}, headers=world.h["g1"]).status_code == 400  # over the total marks


def test_release_scheduling_and_closing(client, world):
    q = make_question(client, world)
    test = make_test(client, world, [q["question_id"]], kind="Practice quiz", release=False)
    tid = test["test_id"]
    assert test["release_status"] == "Not Released"
    released = client.post(f"{API}/tests/{tid}/release", json={"opens_at": iso(hours(24))}, headers=world.h["g1"]).get_json()["data"]
    assert released["release_status"] == "Released" and released["status"] == "Scheduled"
    assert start(client, world, tid).status_code == 422  # not open yet
    assert client.post(f"{API}/tests/{tid}/release", json={}, headers=world.h["g1"]).status_code == 422  # already released
    assert client.patch(f"{API}/tests/{tid}", json={"title": "New"}, headers=world.h["g1"]).status_code == 422  # settings are locked
    assert client.put(f"{API}/tests/{tid}/questions", json={"questions": []}, headers=world.h["g1"]).status_code == 422
    assert db.session.execute(select(Notification).where(Notification.event_key == f"test-released:{tid}")).scalars().all().__len__() == 2

    seen = client.get(f"{API}/tests", headers=world.h["s1"]).get_json()["data"]
    assert seen[0]["status"] == "Scheduled" and seen[0]["my"]["can_start"] is False and "questions" not in seen[0]

    client.patch(f"{API}/tests/{tid}", json={"instructions": "Bring a pen"}, headers=world.h["g1"])  # instructions may change
    closed = client.post(f"{API}/tests/{tid}/close", headers=world.h["g1"]).get_json()["data"]
    assert closed["status"] == "Closed"
    assert client.post(f"{API}/tests/{tid}/close", headers=world.h["g1"]).status_code == 422
    assert start(client, world, tid).status_code == 422


def test_students_see_every_status_of_their_batch_but_never_the_keys(client, world, quiz):
    test, q1, _ = quiz
    client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Final test", "title": "Final test — Track 1"},
                headers=world.h["g1"])  # Configuration Pending
    listed = client.get(f"{API}/tests", headers=world.h["s1"]).get_json()["data"]
    assert sorted(t["status"] for t in listed) == ["Available", "Configuration Pending"]
    assert client.get(f"{API}/tests", headers=world.h["s3"]).get_json()["data"] == []  # G2 has none
    detail = client.get(f"{API}/tests/{test['test_id']}", headers=world.h["s1"]).get_json()["data"]
    assert "questions" not in detail and detail["question_count"] == 2 and detail["my"]["can_start"] is True

    attempt = start(client, world, test["test_id"]).get_json()["data"]
    assert all("answer_key" not in q and "explanation" not in q for q in attempt["questions"])


# ---------------------------------------------------------------- the attempt clock

def test_start_records_the_server_deadline_and_a_reconnect_resumes_the_same_attempt(client, world, quiz):
    test, q1, q2 = quiz
    body = {"batch_id": world.batches["G1"].batch_id, "kind": "Practice quiz", "title": "Timed", "duration_minutes": 20}
    timed = client.post(f"{API}/tests", json=body, headers=world.h["g1"]).get_json()["data"]
    client.put(f"{API}/tests/{timed['test_id']}/questions", json={"questions": [{"question_id": q1["question_id"]}]}, headers=world.h["g1"])
    client.post(f"{API}/tests/{timed['test_id']}/release", json={}, headers=world.h["g1"])

    first = start(client, world, timed["test_id"])
    assert first.status_code == 201
    payload = first.get_json()["data"]
    attempt = payload["attempt"]
    assert attempt["status"] == "In Progress" and 1150 <= attempt["remaining_seconds"] <= 1200 and attempt["attempt_no"] == 1
    assert [q["question_id"] for q in payload["questions"]] == [q1["question_id"]] and payload["answers"] == {}

    saved = answer(client, world, attempt["attempt_id"], {str(q1["question_id"]): "B"}).get_json()["data"]
    assert saved["accepted"] is True and saved["remaining_seconds"] > 0

    again = start(client, world, timed["test_id"])  # a reconnect: same paper, same clock, saved answers
    assert again.status_code == 200
    resumed = again.get_json()["data"]
    assert resumed["attempt"]["attempt_id"] == attempt["attempt_id"] and resumed["answers"] == {str(q1["question_id"]): "B"}
    assert datetime.fromisoformat(resumed["attempt"]["deadline_at"]) == datetime.fromisoformat(attempt["deadline_at"])
    assert db.session.execute(select(TestAttempt)).scalars().all().__len__() == 1


def test_the_deadline_never_passes_the_window_end(client, world):
    q = make_question(client, world)
    soon = iso(hours(5 / 60))  # the window closes in five minutes; the test lasts 30
    test = make_test(client, world, [q["question_id"]], kind="Practice quiz", duration_minutes=30, closes_at=soon)
    attempt = start(client, world, test["test_id"]).get_json()["data"]["attempt"]
    assert attempt["remaining_seconds"] <= 300


def test_answers_after_the_deadline_are_refused_and_the_saved_ones_are_submitted_once(client, world, quiz, run_sql):
    test, q1, q2 = quiz
    attempt = start(client, world, test["test_id"]).get_json()["data"]["attempt"]
    aid = attempt["attempt_id"]
    answer(client, world, aid, {str(q1["question_id"]): "B"})
    expire(run_sql, aid)

    late = answer(client, world, aid, {str(q2["question_id"]): "random forest"})  # too late: not accepted, attempt submitted as saved
    body = late.get_json()["data"]
    assert late.status_code == 200 and body["accepted"] is False and body["status"] == "Submitted" and RECEIPT.match(body["receipt_code"])

    read = client.get(f"{API}/attempts/{aid}", headers=world.h["s1"]).get_json()["data"]
    assert read["attempt"]["status"] == "Submitted" and read["attempt"]["submit_reason"] == "Timeout"
    assert read["answers"] == {str(q1["question_id"]): "B"}  # the late answer was not saved
    stored = db.session.get(TestAttempt, aid)
    db.session.refresh(stored)
    assert stored.submitted_at == stored.deadline_at  # the effective time is the deadline, not when it was processed
    assert float(stored.total_score) == 2.0  # q1 correct (2), q2 blank

    # The receipt is issued once
    assert client.post(f"{API}/attempts/{aid}/submit", json={}, headers=world.h["s1"]).get_json()["data"]["attempt"]["receipt_code"] == body["receipt_code"]


def test_a_read_after_expiry_submits_the_attempt(client, world, quiz, run_sql):
    test, q1, _ = quiz
    aid = start(client, world, test["test_id"]).get_json()["data"]["attempt"]["attempt_id"]
    expire(run_sql, aid)
    staff = client.get(f"{API}/attempts/{aid}", headers=world.h["g1"]).get_json()["data"]
    assert staff["attempt"]["status"] == "Submitted" and RECEIPT.match(staff["attempt"]["receipt_code"])


def test_the_database_itself_refuses_late_and_frozen_answers(client, world, quiz, run_sql):
    test, q1, _ = quiz
    aid = start(client, world, test["test_id"]).get_json()["data"]["attempt"]["attempt_id"]
    expire(run_sql, aid)
    with pytest.raises(DBAPIError, match="time for this attempt is over"):
        run_sql("INSERT INTO attempt_answers (attempt_id, question_id, answer) VALUES (:a, :q, '\"B\"')", a=aid, q=q1["question_id"])
    db.session.rollback()


def test_saving_needs_valid_answers_and_belongs_to_the_owner(client, world, quiz):
    test, q1, q2 = quiz
    aid = start(client, world, test["test_id"]).get_json()["data"]["attempt"]["attempt_id"]
    assert answer(client, world, aid, {str(q1["question_id"]): "Z"}).status_code == 400  # not an option
    assert answer(client, world, aid, {str(q1["question_id"]): ["B"]}).status_code == 400
    assert answer(client, world, aid, {"999999": "B"}).status_code == 400
    assert answer(client, world, aid, {"abc": "B"}).status_code == 400
    assert client.put(f"{API}/attempts/{aid}/answers", json={"answers": []}, headers=world.h["s1"]).status_code == 400
    assert answer(client, world, aid, {str(q1["question_id"]): "B"}, who="s2").status_code == 404  # another student
    assert answer(client, world, aid, {str(q1["question_id"]): "B"}, who="g1").status_code == 403  # staff do not answer
    assert client.get(f"{API}/attempts/{aid}", headers=world.h["s2"]).status_code == 404
    assert client.get(f"{API}/attempts/{aid}", headers=world.h["g2"]).status_code == 404
    assert start(client, world, test["test_id"], who="s3").status_code == 404  # not in this batch
    assert start(client, world, test["test_id"], who="g1").status_code == 403


# ---------------------------------------------------------------- scoring, receipts, results

def test_practice_quiz_is_scored_at_once_and_can_be_repeated(client, world, quiz):
    test, q1, q2 = quiz
    aid = start(client, world, test["test_id"]).get_json()["data"]["attempt"]["attempt_id"]
    resp = client.post(f"{API}/attempts/{aid}/submit", json={"answers": {str(q1["question_id"]): "B", str(q2["question_id"]): "Random Forest"}},
                       headers=world.h["s1"])
    assert resp.status_code == 200, resp.get_json()
    submitted = resp.get_json()["data"]
    attempt = submitted["attempt"]
    assert RECEIPT.match(attempt["receipt_code"]) and attempt["status"] == "Submitted" and attempt["submit_reason"] == "Student"
    assert attempt["score"] == "3.00" and attempt["total_marks"] == "3.00"  # practice: automated feedback at once
    assert db.session.execute(select(Result)).first() is None  # a non-credit practice makes no result
    again = start(client, world, test["test_id"])  # untimed / unlimited: repeat within the window
    assert again.status_code == 201 and again.get_json()["data"]["attempt"]["attempt_no"] == 2
    listing = client.get(f"{API}/tests", headers=world.h["s1"]).get_json()["data"][0]["my"]
    assert listing["my_status"] == "In progress"


def test_a_formal_test_allows_one_attempt_and_withholds_the_score_until_published(client, world):
    q1 = make_question(client, world, marks=2)
    q2 = make_question(client, world, marks=2, question_type="True / False", options=[], answer_key={"value": True}, stem="Logistic regression outputs probabilities")
    test = make_test(client, world, [q1["question_id"], q2["question_id"]], kind="Module test", pass_marks=3)
    tid = test["test_id"]
    aid = start(client, world, tid).get_json()["data"]["attempt"]["attempt_id"]
    done = client.post(f"{API}/attempts/{aid}/submit", json={"answers": {str(q1["question_id"]): "B", str(q2["question_id"]): True}},
                       headers=world.h["s1"]).get_json()["data"]["attempt"]
    assert done["score"] is None and done["grading_status"] == "Graded"  # graded, but a formal score stays hidden
    result = db.session.execute(select(Result).where(Result.test_id == tid)).scalars().one()
    assert result.status == "Provisional" and float(result.provisional_marks) == 4.0 and float(result.max_marks) == 4.0

    assert start(client, world, tid).status_code == 422  # one attempt only
    assert client.get(f"{API}/tests/{tid}", headers=world.h["s1"]).get_json()["data"]["my"]["attempts_remaining"] == 0

    mine = client.get(f"{API}/me/results", headers=world.h["s1"]).get_json()["data"]
    assert mine == [{**mine[0], "item": "Module test test", "score": None, "state": "Provisional — pending moderation", "pass_status": None}]

    assert client.post(f"{API}/results/publish", json={"test_id": tid}, headers=world.h["ac"]).status_code == 200
    mine = client.get(f"{API}/me/results", headers=world.h["s1"]).get_json()["data"][0]
    assert mine["score"] == "4.00 / 4.00" and mine["state"] == "Published" and mine["pass_status"] == "Passed"


def test_written_and_coding_answers_wait_for_the_trainer(client, world):
    q1 = make_question(client, world, marks=2)
    q2 = make_question(client, world, marks=6, question_type="Coding", options=[], answer_key={"rubric": "Returns the mean"}, stem="Write mean(xs)")
    q3 = make_question(client, world, marks=2, question_type="Descriptive", options=[], answer_key={"rubric": "bias and variance"}, stem="Explain the trade-off")
    test = make_test(client, world, [q1["question_id"], q2["question_id"], q3["question_id"]], kind="Coding exercise", pass_marks=5)
    tid = test["test_id"]
    aid = start(client, world, tid).get_json()["data"]["attempt"]["attempt_id"]
    submitted = client.post(f"{API}/attempts/{aid}/submit", json={"answers": {str(q1["question_id"]): "B", str(q2["question_id"]): "def mean(xs): return sum(xs)/len(xs)"}},
                            headers=world.h["s1"]).get_json()["data"]["attempt"]
    assert submitted["grading_status"] == "Awaiting Grading" and RECEIPT.match(submitted["receipt_code"])
    assert db.session.execute(select(Result)).first() is None  # nothing provisional until every answer is marked

    queue = client.get(f"{API}/attempts?grading_status=Awaiting Grading&reviewer_me=true", headers=world.h["g1"]).get_json()["data"]
    assert [a["attempt_id"] for a in queue] == [aid] and queue[0]["manual_pending"] == 1  # q3 was left blank -> 0 automatically
    assert client.get(f"{API}/attempts?grading_status=Awaiting Grading", headers=world.h["g2"]).get_json()["data"] == []
    assert client.get(f"{API}/attempts", headers=world.h["s1"]).status_code == 403

    grading = client.get(f"{API}/attempts/{aid}", headers=world.h["g1"]).get_json()["data"]
    assert grading["questions"][1]["answer"].startswith("def mean") and grading["questions"][1]["needs_grading"] is True
    assert grading["questions"][1]["answer_key"] == {"rubric": "Returns the mean"}  # the grader sees the rubric

    grade = lambda who, marks, **kw: client.post(f"{API}/attempts/{aid}/grade", headers=world.h[who],  # noqa: E731
                                                 json={"grades": [{"question_id": q2["question_id"], "marks": marks, "feedback": "Handles empty list?", **kw}]})
    assert grade("s1", 5).status_code == 403
    assert grade("g2", 5).status_code == 404
    assert grade("g1", 7).status_code == 400  # over the question's marks
    assert client.post(f"{API}/attempts/{aid}/grade", json={"grades": [{"question_id": q1["question_id"], "marks": 1}]}, headers=world.h["g1"]).status_code == 422  # auto-scored
    graded = grade("g1", 5)
    assert graded.status_code == 200 and graded.get_json()["data"]["attempt"]["grading_status"] == "Graded"
    assert graded.get_json()["data"]["attempt"]["total_score"] == "7.00"  # 2 + 5 + 0
    result = db.session.execute(select(Result).where(Result.test_id == tid)).scalars().one()
    assert result.status == "Provisional" and float(result.provisional_marks) == 7.0 and float(result.max_marks) == 10.0
    assert grade("g1", 4).status_code == 422  # already graded

    # The student never sees a formal score before publication
    assert client.get(f"{API}/attempts/{aid}", headers=world.h["s1"]).get_json()["data"]["attempt"]["score"] is None


# ---------------------------------------------------------------- mock interview

def test_mock_interview_slots_are_offered_booked_confirmed_and_completed(client, world):
    test = client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Mock interview", "title": "Mock interview — ML basics"},
                       headers=world.h["g1"]).get_json()["data"]
    tid = test["test_id"]
    assert test["gaps"] == ["Offer at least one interview slot"] and test["duration_minutes"] == 30

    base = hours(0).replace(second=0, microsecond=0)

    def slots(*offsets):
        return {"slots": [{"starts_at": iso(base + timedelta(hours=o)), "ends_at": iso(base + timedelta(hours=o + 0.5))} for o in offsets]}

    assert client.post(f"{API}/tests/{tid}/slots", json=slots(-2), headers=world.h["g1"]).status_code == 400  # in the past
    assert client.post(f"{API}/tests/{tid}/slots", json=slots(24), headers=world.h["s1"]).status_code == 403
    assert client.post(f"{API}/tests/{tid}/slots", json=slots(24), headers=world.h["g2"]).status_code == 404
    assert client.post(f"{API}/tests/{tid}/slots", json={**slots(24), "trainer_user_id": world.people["g2"].user_id}, headers=world.h["g1"]).status_code == 400
    offered = client.post(f"{API}/tests/{tid}/slots", json=slots(24, 26), headers=world.h["g1"])
    assert offered.status_code == 201 and len(offered.get_json()["data"]) == 2
    assert client.post(f"{API}/tests/{tid}/slots", json=slots(24), headers=world.h["g1"]).status_code == 409  # same time again
    first, second = (s["slot_id"] for s in offered.get_json()["data"])
    assert client.get(f"{API}/tests/{tid}", headers=world.h["g1"]).get_json()["data"]["release_status"] == "Not Released"

    assert client.post(f"{API}/interview-slots/{first}/book", headers=world.h["s1"]).status_code == 422  # not released yet
    client.post(f"{API}/tests/{tid}/release", json={}, headers=world.h["g1"])
    assert start(client, world, tid).status_code == 422  # interviews are booked, not attempted

    open_slots = client.get(f"{API}/tests/{tid}/slots", headers=world.h["s1"]).get_json()["data"]
    assert len(open_slots) == 2 and all(s["student"] is None for s in open_slots)
    booked = client.post(f"{API}/interview-slots/{first}/book", headers=world.h["s1"])
    assert booked.status_code == 200 and booked.get_json()["data"]["status"] == "Slot Confirmation Pending"
    assert client.post(f"{API}/interview-slots/{first}/book", headers=world.h["s2"]).status_code == 404  # another student's booking
    assert client.post(f"{API}/interview-slots/{second}/book", headers=world.h["s1"]).status_code == 409  # one booking per student
    assert client.post(f"{API}/interview-slots/{second}/book", headers=world.h["s3"]).status_code == 404  # another batch
    assert db.session.execute(select(Notification).where(Notification.recipient_user_id == world.people["g1"].user_id,
                                                         Notification.category == "Assessments", Notification.action_status == "Open")).scalars().first()

    assert client.get(f"{API}/tests/{tid}", headers=world.h["s1"]).get_json()["data"]["my"]["my_status"] == "Slot Confirmation Pending"
    assert client.post(f"{API}/interview-slots/{first}/confirm", headers=world.h["s1"]).status_code == 403
    assert client.post(f"{API}/interview-slots/{first}/confirm", headers=world.h["g2"]).status_code == 404
    assert client.post(f"{API}/interview-slots/{first}/complete", json={"rating": 4, "strengths": "a", "improvements": "b", "next_action": "c"},
                       headers=world.h["g1"]).status_code == 422  # not confirmed yet
    assert client.post(f"{API}/interview-slots/{first}/confirm", headers=world.h["g1"]).get_json()["data"]["status"] == "Confirmed"
    assert client.get(f"{API}/tests/{tid}", headers=world.h["s1"]).get_json()["data"]["my"]["my_status"] == "Confirmed"

    bad = client.post(f"{API}/interview-slots/{first}/complete", json={"rating": 9, "strengths": "a", "improvements": "b", "next_action": "c"}, headers=world.h["g1"])
    assert bad.status_code == 400
    done = client.post(f"{API}/interview-slots/{first}/complete", json={"rating": 4, "strengths": "Clear explanations", "improvements": "Bias-variance",
                                                                        "next_action": "Practise two more questions"}, headers=world.h["g1"])
    assert done.status_code == 200 and done.get_json()["data"]["status"] == "Completed" and done.get_json()["data"]["student"]["full_name"]
    mine = client.get(f"{API}/tests/{tid}/slots", headers=world.h["s1"]).get_json()["data"]
    assert [s["status"] for s in mine] == ["Completed", "Open"] and mine[0]["strengths"] == "Clear explanations"
    assert db.session.execute(select(Result)).first() is None  # practice only: no result


def test_students_can_free_their_booking_and_staff_cancel_slots(client, world):
    test = client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Mock interview", "title": "MI"}, headers=world.h["g1"]).get_json()["data"]
    tid = test["test_id"]
    slot = client.post(f"{API}/tests/{tid}/slots", json={"slots": [{"starts_at": iso(hours(30)), "ends_at": iso(hours(30.5))}]},
                       headers=world.h["g1"]).get_json()["data"][0]["slot_id"]
    client.post(f"{API}/tests/{tid}/release", json={}, headers=world.h["g1"])
    client.post(f"{API}/interview-slots/{slot}/book", headers=world.h["s1"])
    freed = client.post(f"{API}/interview-slots/{slot}/cancel", json={}, headers=world.h["s1"])
    assert freed.status_code == 200 and freed.get_json()["data"]["status"] == "Open"
    client.post(f"{API}/interview-slots/{slot}/book", headers=world.h["s2"])
    cancelled = client.post(f"{API}/interview-slots/{slot}/cancel", json={"reason": "Trainer unwell"}, headers=world.h["g1"])
    assert cancelled.status_code == 200 and cancelled.get_json()["data"]["status"] == "Cancelled"
    assert db.session.execute(select(Notification).where(Notification.event_key == f"slot-cancelled:{slot}")).scalars().one()
    assert client.post(f"{API}/interview-slots/{slot}/cancel", json={}, headers=world.h["g1"]).status_code == 422

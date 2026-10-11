"""UX phase U13: the trainer's To grade inbox, students at risk, the batch and student pages, the reviewer's comment on content and
recovery requests in My requests."""
from datetime import datetime, timedelta, timezone

import pytest

from services import review_clock
from tests.assessment_world import API, make_question, make_test, released_assignment, world  # noqa: F401 (fixtures)
from tests.test_assignments import move_deadline, review, submit
from tests.test_tests_attempts import start


def get(client, world, path, who="g1"):
    return client.get(f"{API}{path}", headers=world.h[who])


def inbox(client, world, who="g1", query=""):
    response = get(client, world, f"/trainer/to-grade{query}", who)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


@pytest.fixture
def work(client, world, released_assignment):
    """G1 has one submission (s1, assignment) and one test attempt (s2, a written answer) waiting for the trainer."""
    submission = submit(client, world, "s1", released_assignment["assignment_id"]).get_json()["data"]
    mcq = make_question(client, world, marks=2)
    written = make_question(client, world, marks=6, question_type="Descriptive", options=[], answer_key={"rubric": "bias"}, stem="Explain the trade-off")
    test = make_test(client, world, [mcq["question_id"], written["question_id"]], kind="Coding exercise", pass_marks=3)
    attempt = start(client, world, test["test_id"], "s2").get_json()["data"]["attempt"]
    client.post(f"{API}/attempts/{attempt['attempt_id']}/submit", json={"answers": {str(mcq["question_id"]): "B", str(written["question_id"]): "text"}},
                headers=world.h["s2"])
    return {"submission": submission, "attempt": attempt, "test": test, "assignment": released_assignment, "written": written}


# ---------------------------------------------------------------- To grade

def test_to_grade_merges_submissions_and_attempts_oldest_first(client, world, work):
    data = inbox(client, world)
    assert data["counts"] == {"total": 2, "submissions": 1, "attempts": 1, "overdue": 0}
    kinds = {item["kind"]: item for item in data["items"]}
    submission, attempt = kinds["submission"], kinds["attempt"]
    assert submission["id"] == work["submission"]["submission_id"] and submission["student"]["student_code"] == world.students["s1"].student_code
    assert submission["started"] is False and submission["max_marks"] == "20.00" and submission["batch"]["batch_code"] == world.batches["G1"].batch_code
    assert attempt["id"] == work["attempt"]["attempt_id"] and attempt["to_mark"] == 1 and attempt["max_marks"] == "8.00"
    # the submission came first, so it is first in the list
    assert [i["kind"] for i in data["items"]] == ["submission", "attempt"]
    assert data["batches"] == [world.batches["G1"].to_summary()]

    # the count is the one the navigation badge shows
    counts = client.get(f"{API}/me/nav-counts?workspace=trainer", headers=world.h["g1"]).get_json()["data"]
    assert counts["to_grade"] == data["counts"]["total"]


def test_overdue_work_comes_first_and_the_batch_filter_narrows_the_list(client, world, work, monkeypatch):
    real = review_clock.review_due

    def overdue_for_tests(kind, submitted_at, branch_id, *, tests=False):
        due = real(kind, submitted_at, branch_id, tests=tests)
        return {**due, "overdue": True} if due and tests else due

    monkeypatch.setattr(review_clock, "review_due", overdue_for_tests)
    data = inbox(client, world)
    assert [i["kind"] for i in data["items"]] == ["attempt", "submission"] and data["items"][0]["overdue"] and data["counts"]["overdue"] == 1

    g1, g2 = world.batches["G1"].batch_id, world.batches["G2"].batch_id
    assert inbox(client, world, query=f"?batch_id={g1}")["counts"]["total"] == 2
    assert inbox(client, world, "g2")["items"] == []                                  # another trainer's batches show nothing of G1's
    assert get(client, world, f"/trainer/to-grade?batch_id={g2}", "g1").status_code == 404   # a batch that is not theirs
    assert get(client, world, "/trainer/to-grade", "s1").status_code == 403
    assert get(client, world, "/trainer/to-grade", "ac").status_code == 403


def test_a_saved_review_leaves_the_inbox_and_marks_cannot_exceed_the_maximum(client, world, work):
    sid = work["submission"]["submission_id"]
    assert review(client, world, sid, outcome="Reviewed", feedback="Good", marks=21).status_code == 400
    assert review(client, world, sid, outcome="Reviewed", feedback="Good", marks=-1).status_code == 400
    assert review(client, world, sid, outcome="Reviewed", feedback="Good", marks=18).status_code == 201
    data = inbox(client, world)
    assert [i["kind"] for i in data["items"]] == ["attempt"]

    aid = work["attempt"]["attempt_id"]
    detail = client.get(f"{API}/attempts/{aid}", headers=world.h["g1"]).get_json()["data"]
    written = next(q for q in detail["questions"] if q["needs_grading"])
    assert client.post(f"{API}/attempts/{aid}/grade", json={"grades": [{"question_id": written["question_id"], "marks": 7}]},
                       headers=world.h["g1"]).status_code == 400
    assert client.post(f"{API}/attempts/{aid}/grade", json={"grades": [{"question_id": written["question_id"], "marks": 4}]},
                       headers=world.h["g1"]).status_code == 200
    assert inbox(client, world)["items"] == []


def test_starting_a_review_is_recorded_and_shown_in_the_inbox(client, world, work):
    sid = work["submission"]["submission_id"]
    assert inbox(client, world)["items"][0]["started"] is False
    assert client.post(f"{API}/submissions/{sid}/start-review", headers=world.h["g1"]).status_code == 200
    item = next(i for i in inbox(client, world)["items"] if i["kind"] == "submission")
    assert item["started"] is True


# ---------------------------------------------------------------- Students at risk

def test_students_at_risk_are_listed_per_batch_with_where_to_act(client, world, run_sql, released_assignment, work):
    move_deadline(run_sql, released_assignment["assignment_id"], -48)             # the required task is now past due
    s1, s2 = world.students["s1"], world.students["s2"]

    data = get(client, world, "/trainer/at-risk").get_json()["data"]
    assert data["totals"] == {"students": 2, "at_risk": 1}
    (batch,) = data["batches"]
    assert batch["batch"]["batch_code"] == world.batches["G1"].batch_code and batch["students"] == 2 and batch["at_risk"] == 1
    (row,) = batch["rows"]                                                         # s1 handed it in, s2 did not
    assert row["student"]["student_code"] == s2.student_code
    reason = next(r for r in row["reasons"] if r["kind"] == "work")
    assert "1 required task not handed in" in reason["detail"] and reason["to"] == f"/trainer/students/{s2.student_id}"

    other = get(client, world, "/trainer/at-risk", "g2").get_json()["data"]        # G2 has its own student and none at risk
    assert other["totals"] == {"students": 1, "at_risk": 0}
    assert get(client, world, "/trainer/at-risk", "s1").status_code == 403
    assert get(client, world, "/trainer/at-risk", "ac").status_code == 403
    assert s1.student_id != s2.student_id


def test_overdue_reviews_make_a_student_at_risk_and_link_to_the_grading_screen(client, world, work, monkeypatch):
    real = review_clock.review_due
    monkeypatch.setattr(review_clock, "review_due", lambda *a, **k: {**real(*a, **k), "overdue": True} if real(*a, **k) else None)
    (batch,) = get(client, world, "/trainer/at-risk").get_json()["data"]["batches"]
    by_student = {r["student"]["student_code"]: r for r in batch["rows"]}
    reason = next(r for r in by_student[world.students["s1"].student_code]["reasons"] if r["kind"] == "review_overdue")
    assert reason["to"] == f"/trainer/to-grade/submission/{work['submission']['submission_id']}" and reason["action"] == "Grade now"


# ---------------------------------------------------------------- Students, batch page, student page

def test_students_list_has_search_and_a_batch_filter(client, world):
    everyone = get(client, world, "/trainer/students").get_json()["data"]
    assert {r["student"]["student_code"] for r in everyone} == {world.students["s1"].student_code, world.students["s2"].student_code}
    assert {"attendance_pct", "reasons", "open_requests", "flag", "batch", "enrolment"} <= set(everyone[0])
    code = world.students["s1"].student_code
    assert [r["student"]["student_code"] for r in get(client, world, f"/trainer/students?q={code}").get_json()["data"]] == [code]
    assert get(client, world, "/trainer/students?q=zzzz").get_json()["data"] == []
    g1, g2 = world.batches["G1"].batch_id, world.batches["G2"].batch_id
    assert len(get(client, world, f"/trainer/students?batch_id={g1}").get_json()["data"]) == 2
    assert get(client, world, f"/trainer/students?batch_id={g2}").status_code == 404


def test_a_batch_page_shows_the_roster_classes_content_and_assignments(client, world, released_assignment, make_session):
    g1 = world.batches["G1"]
    make_session(g1, world.people["g1"], datetime.now(timezone.utc) + timedelta(days=2), title="Next class")
    page = get(client, world, f"/trainer/batches/{g1.batch_id}").get_json()["data"]
    assert page["batch"]["batch_code"] == g1.batch_code and page["batch"]["allocated_count"] == 2
    assert [s["title"] for s in page["sessions"]["coming"]] == ["Next class"]
    assert {r["student"]["student_code"] for r in page["roster"]} == {world.students["s1"].student_code, world.students["s2"].student_code}
    assert page["assignments"][0]["title"] == released_assignment["title"] and page["assignments"][0]["counts"]["submitted"] == 0
    assert set(page["progress"]) >= {"students", "attendance_pct", "delivery_pct", "at_risk"}

    listing = get(client, world, "/trainer/batches").get_json()["data"]
    assert [b["batch"]["batch_id"] for b in listing] == [g1.batch_id] and listing[0]["next_class"]["title"] == "Next class"
    assert listing[0]["students"] == 2

    assert get(client, world, f"/trainer/batches/{g1.batch_id}", "g2").status_code == 404
    assert get(client, world, f"/trainer/batches/{g1.batch_id}", "s1").status_code == 403


def test_a_student_page_shows_work_results_and_flags_only_inside_the_trainers_batches(client, world, work):
    s1 = world.students["s1"]
    sid = work["submission"]["submission_id"]
    assert review(client, world, sid, outcome="Reviewed", feedback="Good", marks=15).status_code == 201
    flagged = client.post(f"{API}/support-requests", headers=world.h["g1"], json={
        "student_id": s1.student_id, "category": "Academic", "details": "Struggling with streams"})
    assert flagged.status_code == 201, flagged.get_json()

    page = get(client, world, f"/trainer/students/{s1.student_id}").get_json()["data"]
    assert page["student"]["student_code"] == s1.student_code
    (seat,) = page["enrolments"]
    assert seat["batch"]["batch_code"] == world.batches["G1"].batch_code
    (task,) = seat["assignments"]
    assert task["state"] == "Reviewed" and task["marks"] == "15.00" and task["max_marks"] == "20.00" and task["to_grade"] is False
    assert [r["item"]["kind"] for r in seat["results"]] == ["Assignment"] and seat["results"][0]["marks"] == "15.00"
    assert [f["category"] for f in page["flags"]] == ["Academic"]
    assert "attendance" in seat and "reasons" in seat

    # a student of another trainer's batch, or a student account, is not reachable
    assert get(client, world, f"/trainer/students/{s1.student_id}", "g2").status_code == 404
    assert get(client, world, f"/trainer/students/{world.students['s3'].student_id}", "g1").status_code == 404
    assert get(client, world, f"/trainer/students/{s1.student_id}", "s1").status_code == 403


def test_a_student_page_marks_work_that_is_waiting_for_the_trainer(client, world, work):
    s1 = world.students["s1"]
    (seat,) = get(client, world, f"/trainer/students/{s1.student_id}").get_json()["data"]["enrolments"]
    (task,) = seat["assignments"]
    assert task["state"] == "Submitted" and task["to_grade"] is True and task["submission_id"] == work["submission"]["submission_id"]


# ---------------------------------------------------------------- Support: flag from a student row

def test_a_trainer_flags_a_student_and_the_list_shows_it(client, world):
    s1 = world.students["s1"]
    assert client.post(f"{API}/support-requests", headers=world.h["g1"], json={
        "student_id": s1.student_id, "category": "Academic", "details": "Missing three classes"}).status_code == 201
    rows = get(client, world, "/trainer/students").get_json()["data"]
    row = next(r for r in rows if r["student"]["student_code"] == s1.student_code)
    assert row["flag"] == "Open — Academic" and len(row["open_requests"]) == 1
    # a trainer cannot flag a student of someone else's batch
    assert client.post(f"{API}/support-requests", headers=world.h["g2"], json={
        "student_id": s1.student_id, "category": "Academic", "details": "Not mine"}).status_code == 404

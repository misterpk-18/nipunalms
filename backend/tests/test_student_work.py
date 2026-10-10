"""UX phase U9: the Tasks & Tests list (`GET /me/work`) and the schedule's Coming and Past views (`GET /me/schedule`)."""
from datetime import datetime, timedelta, timezone

from config.database import db
from models import AttendanceRecord
from tests.assessment_world import API, hours, iso, make_question, make_test, released_assignment, world  # noqa: F401 (fixtures)
from tests.conftest import _commit
from tests.test_assignments import move_deadline, review, submit
from tests.test_student_learning import enrolment_id
from tests.test_tests_attempts import start


def work(client, world, who="s1"):
    response = client.get(f"{API}/me/work", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def titles(rows) -> list[str]:
    return [r["title"] for r in rows]


def take(client, world, test_id, answers, who="s1"):
    attempt = start(client, world, test_id, who).get_json()["data"]["attempt"]["attempt_id"]
    done = client.post(f"{API}/attempts/{attempt}/submit", json={"answers": answers}, headers=world.h[who])
    assert done.status_code == 200, done.get_json()
    return attempt


# ---------------------------------------------------------------- assignments

def test_a_new_assignment_is_to_do_and_counted(client, world, released_assignment):
    data = work(client, world)

    assert data["counts"] == {"todo": 1, "waiting": 0, "done": 0, "overdue": 0}
    (item,) = data["todo"]
    assert (item["kind"], item["id"], item["state"], item["action"]) == ("assignment", released_assignment["assignment_id"], "Due", "Submit")
    assert item["is_required"] is True and item["topic"]["title"] == "OOP & Collections" and item["state_domain"] == "work"


def test_an_assignment_moves_to_waiting_and_then_to_done_when_the_result_is_published(client, world, released_assignment):
    aid = released_assignment["assignment_id"]
    sub = submit(client, world, "s1", aid, body_text="analysis").get_json()["data"]

    waiting = work(client, world)
    assert titles(waiting["waiting"]) == [released_assignment["title"]] and waiting["todo"] == []
    assert waiting["waiting"][0]["state"] == "Submitted" and waiting["counts"]["waiting"] == 1

    client.post(f"{API}/submissions/{sub['submission_id']}/start-review", headers=world.h["g1"])
    assert work(client, world)["waiting"][0]["state"] == "Under Review"

    assert review(client, world, sub["submission_id"], outcome="Reviewed", feedback="Good", marks=18).status_code == 201
    still = work(client, world)
    assert still["counts"]["waiting"] == 1 and still["done"] == []  # marked, but the Branch Manager has not published it

    client.post(f"{API}/results/publish", json={"assignment_id": aid}, headers=world.h["ac"])
    done = work(client, world)
    assert done["counts"] == {"todo": 0, "waiting": 0, "done": 1, "overdue": 0}
    assert (done["done"][0]["state"], done["done"][0]["marks"], done["done"][0]["max_marks"]) == ("Reviewed", "18.00", "20.00")


def test_overdue_work_comes_first_and_a_closed_window_is_missed(client, world, released_assignment, run_sql):
    aid = released_assignment["assignment_id"]
    second = client.post(f"{API}/assignments", json={"batch_id": world.batches["G1"].batch_id, "title": "Second task", "brief": "x",
                                                    "max_marks": 10, "due_at": iso(hours(30)), "release_now": True}, headers=world.h["g1"]).get_json()["data"]
    move_deadline(run_sql, aid, -5, 100)  # late, but still open
    data = work(client, world)
    assert titles(data["todo"]) == [released_assignment["title"], "Second task"]
    assert data["todo"][0]["overdue"] is True and data["todo"][0]["state"] == "Overdue"
    assert data["counts"] == {"todo": 2, "waiting": 0, "done": 0, "overdue": 1}

    move_deadline(run_sql, aid, -200, -20)  # the window closed with nothing handed in
    data = work(client, world)
    assert titles(data["todo"]) == ["Second task"]
    assert [(i["title"], i["state"]) for i in data["done"]] == [(released_assignment["title"], "Missed")]
    assert second["assignment_id"] != aid


def test_a_resubmission_request_is_to_do_again(client, world, released_assignment):
    aid = released_assignment["assignment_id"]
    sub = submit(client, world, "s1", aid, body_text="first try").get_json()["data"]
    again = review(client, world, sub["submission_id"], outcome="Resubmission Requested", feedback="Add the error analysis",
                   resubmission_due_at=iso(hours(72)))
    assert again.status_code == 201, again.get_json()

    (item,) = work(client, world)["todo"]
    assert (item["state"], item["action"]) == ("Resubmission Requested", "Resubmit")


def test_each_student_sees_only_their_own_batchs_work(client, world, released_assignment):
    assert work(client, world, "s3")["counts"] == {"todo": 0, "waiting": 0, "done": 0, "overdue": 0}
    assert work(client, world, "s2")["counts"]["todo"] == 1


# ---------------------------------------------------------------- tests

def test_a_released_quiz_is_to_do_until_it_is_taken(client, world):
    q = make_question(client, world, marks=2)
    test = make_test(client, world, [q["question_id"]])

    (item,) = work(client, world)["todo"]
    assert (item["kind"], item["id"], item["state"], item["state_domain"], item["action"]) == ("test", test["test_id"], "Available", "test", "Start test")

    attempt = start(client, world, test["test_id"]).get_json()["data"]["attempt"]
    (item,) = work(client, world)["todo"]
    assert (item["state"], item["action"], item["in_progress"]) == ("In progress", "Resume test", True)

    client.post(f"{API}/attempts/{attempt['attempt_id']}/submit", json={"answers": {str(q["question_id"]): "B"}}, headers=world.h["s1"])
    data = work(client, world)
    assert data["todo"] == [] and data["counts"]["done"] == 1
    assert (data["done"][0]["state"], data["done"][0]["marks"], data["done"][0]["max_marks"], data["done"][0]["action"]) == ("Graded", "2.00", "2.00", "Try again")


def test_a_formal_test_waits_until_the_result_is_published(client, world):
    q = make_question(client, world, marks=2)
    test = make_test(client, world, [q["question_id"]], kind="Module test", pass_marks=1)
    take(client, world, test["test_id"], {str(q["question_id"]): "B"})

    data = work(client, world)
    assert data["counts"] == {"todo": 0, "waiting": 1, "done": 0, "overdue": 0}
    assert data["waiting"][0]["state"] == "Under Review" and data["waiting"][0]["duration_minutes"] == 30

    client.post(f"{API}/results/publish", json={"test_id": test["test_id"]}, headers=world.h["ac"])
    done = work(client, world)
    assert done["counts"]["done"] == 1 and (done["done"][0]["marks"], done["done"][0]["max_marks"]) == ("2.00", "2.00")


def test_a_test_with_attempts_left_shows_them_and_one_that_closed_untaken_is_missed(client, world, run_sql):
    q = make_question(client, world, marks=2)
    test = make_test(client, world, [q["question_id"]], kind="Module test", pass_marks=1)
    (item,) = work(client, world)["todo"]
    assert item["attempts_remaining"] == 1 and item["duration_minutes"] == 30

    run_sql("UPDATE tests SET opens_at = now() - interval '2 days', closes_at = now() - interval '1 day' WHERE test_id = :t", t=test["test_id"])
    data = work(client, world)
    assert data["todo"] == [] and [(i["title"], i["state"]) for i in data["done"]] == [(test["title"], "Missed")]


def test_tests_that_are_not_released_are_not_tasks(client, world):
    q = make_question(client, world)
    make_test(client, world, [q["question_id"]], release=False)
    assert work(client, world)["counts"] == {"todo": 0, "waiting": 0, "done": 0, "overdue": 0}


def test_a_mock_interview_is_booked_confirmed_and_done(client, world):
    test = client.post(f"{API}/tests", json={"batch_id": world.batches["G1"].batch_id, "kind": "Mock interview", "title": "Mock interview"},
                       headers=world.h["g1"]).get_json()["data"]
    base = hours(24).replace(second=0, microsecond=0)
    slot = client.post(f"{API}/tests/{test['test_id']}/slots", json={"slots": [{"starts_at": iso(base), "ends_at": iso(base + timedelta(minutes=30))}]},
                       headers=world.h["g1"]).get_json()["data"][0]
    client.post(f"{API}/tests/{test['test_id']}/release", json={}, headers=world.h["g1"])

    (item,) = work(client, world)["todo"]
    assert (item["state"], item["action"]) == ("Available", "Book a slot")

    client.post(f"{API}/interview-slots/{slot['slot_id']}/book", headers=world.h["s1"])
    (item,) = work(client, world)["waiting"]
    assert (item["state"], item["state_domain"]) == ("Slot Confirmation Pending", "slot")

    client.post(f"{API}/interview-slots/{slot['slot_id']}/confirm", headers=world.h["g1"])
    (item,) = work(client, world)["todo"]
    assert item["state"] == "Confirmed" and item["due_at"] is not None

    done = client.post(f"{API}/interview-slots/{slot['slot_id']}/complete", headers=world.h["g1"],
                       json={"rating": 4, "strengths": "a", "improvements": "b", "next_action": "c"})
    assert done.status_code == 200, done.get_json()
    assert [(i["state"], i["state_domain"]) for i in work(client, world)["done"]] == [("Completed", "slot")]


def test_only_a_student_has_a_task_list_and_the_nav_badge_matches_it(client, world, released_assignment):
    assert client.get(f"{API}/me/work", headers=world.h["g1"]).status_code == 403
    assert client.get(f"{API}/me/work").status_code == 401

    q = make_question(client, world)
    make_test(client, world, [q["question_id"]])
    counts = client.get(f"{API}/me/nav-counts?workspace=student", headers=world.h["s1"]).get_json()["data"]
    assert counts["tasks"] == work(client, world)["counts"]["todo"] == 2


# ---------------------------------------------------------------- the schedule

def at(offset_hours: float, **columns):
    return {"starts_at": datetime.now(timezone.utc) + timedelta(hours=offset_hours), **columns}


def listed(client, world, query="", who="s1"):
    response = client.get(f"{API}/me/schedule{query}", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def test_coming_classes_include_a_cancelled_one_and_leave_out_finished_ones(client, world, make_session):
    batch, trainer = world.batches["G1"], world.people["g1"]
    make_session(batch, trainer, **at(-6), title="Finished earlier", state="Delivered", delivered_at=datetime.now(timezone.utc) - timedelta(hours=3))
    soon = make_session(batch, trainer, **at(3), title="Later today")
    cancelled = make_session(batch, trainer, **at(30), title="Cancelled class", state="Cancelled")

    rows = listed(client, world)

    assert [r["session_id"] for r in rows] == [soon.session_id, cancelled.session_id]
    assert rows[1]["state"] == "Cancelled" and rows[0]["enrolment"]["enrolment_id"] == enrolment_id(world.students["s1"])


def test_a_class_running_over_its_end_is_still_coming(client, world, make_session):
    session = make_session(world.batches["G1"], world.people["g1"], **at(-3), title="Running over", state="Live", hours=2)
    assert [r["session_id"] for r in listed(client, world)] == [session.session_id]
    assert listed(client, world, "?past=1") == []


def test_past_classes_come_newest_first_with_attendance_and_recording(client, world, make_session, run_sql):
    batch, trainer = world.batches["G1"], world.people["g1"]
    older = make_session(batch, trainer, **at(-72), title="Older class", state="Delivered", delivered_at=datetime.now(timezone.utc) - timedelta(hours=70))
    newer = make_session(batch, trainer, **at(-26), title="Newer class", state="Delivered", delivered_at=datetime.now(timezone.utc) - timedelta(hours=24))
    make_session(batch, trainer, **at(5), title="Still to come")
    db.session.add(AttendanceRecord(session_id=newer.session_id, enrolment_id=enrolment_id(world.students["s1"]), status="Present",
                                    marked_by=trainer.user_id))
    _commit()
    run_sql("INSERT INTO recordings (session_id, status, media_ref, released_at) VALUES (:s, 'Released', 'drive-file-1', now())", s=newer.session_id)

    rows = listed(client, world, "?past=1")

    assert [r["session_id"] for r in rows] == [newer.session_id, older.session_id]
    assert rows[0]["attendance"] == "Present" and rows[0]["recording"]["status"] == "Released" and rows[0]["recording"]["playable"] is True
    assert rows[1]["attendance"] is None and rows[1]["recording"] is None


def test_a_classmate_does_not_inherit_the_past_attendance_of_another_student(client, world, make_session):
    batch, trainer = world.batches["G1"], world.people["g1"]
    session = make_session(batch, trainer, **at(-26), title="Class", state="Delivered", delivered_at=datetime.now(timezone.utc) - timedelta(hours=24))
    db.session.add(AttendanceRecord(session_id=session.session_id, enrolment_id=enrolment_id(world.students["s1"]), status="Absent",
                                    marked_by=trainer.user_id))
    _commit()

    assert listed(client, world, "?past=1", "s1")[0]["attendance"] == "Absent"
    assert listed(client, world, "?past=1", "s2")[0]["attendance"] is None
    assert listed(client, world, "?past=1", "s3") == []
    assert client.get(f"{API}/me/schedule?past=maybe", headers=world.h["s1"]).status_code == 400

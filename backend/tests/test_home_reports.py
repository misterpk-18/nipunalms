"""P3: Student Home, Trainer Today, trainer and academic reports (aggregation endpoints, scope and empty states)."""
from datetime import datetime, timedelta, timezone

import pytest

from config.database import db
from config.timezone import IST
from models import ActivityEvent, CompletionReview, Enrolment
from services import student_home
from tests.assessment_world import API, assignment_body, hours, iso, released_assignment, world  # noqa: F401 (fixtures)
from tests.conftest import _commit


def home(client, world, who):
    response = client.get(f"{API}/me/home", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def today_view(client, world, who="g1"):
    response = client.get(f"{API}/trainer/today", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def add_session(make_session, batch, trainer, starts_at, **columns):
    return make_session(batch, trainer, starts_at, **columns)


# ---------------------------------------------------------------- Student Home

def test_student_home_is_student_only(client, world):
    assert client.get(f"{API}/me/home").status_code == 401
    for who in ("g1", "ac", "bm", "admin"):
        assert client.get(f"{API}/me/home", headers=world.h[who]).status_code == 403


def test_a_student_sees_only_their_own_home(client, world, make_session):
    g1 = world.people["g1"]
    g2 = world.people["g2"]
    make_session(world.batches["G1"], g1, datetime.now(IST) + timedelta(days=2), title="G1 class")
    make_session(world.batches["G2"], g2, datetime.now(IST) + timedelta(days=3), title="G2 class")
    one, three = home(client, world, "s1"), home(client, world, "s3")
    assert one["student"]["student_code"] == world.students["s1"].student_code
    assert three["student"]["student_code"] == world.students["s3"].student_code
    assert one["next_class"]["session_title"] == "G1 class"
    assert three["next_class"]["session_title"] == "G2 class"  # never the other batch's class
    assert one["next_class"]["batch"]["batch_id"] == world.batches["G1"].batch_id
    assert one["primary_enrolment"]["enrolment_id"] != three["primary_enrolment"]["enrolment_id"]


def test_home_cards_report_empty_states_honestly(client, world):
    data = home(client, world, "s1")
    assert data["next_class"]["state"] == "Empty" and data["next_class"]["message"]
    assert data["due_work"]["state"] == "Empty" and data["upcoming_work"]["state"] == "Empty"
    assert data["latest_recording"]["state"] == "Empty"
    assert data["continue_learning"]["state"] == "Empty"
    assert data["attendance_alert"]["state"] == "Empty"
    assert data["support"] == {"state": "Empty", "open_count": 0, "requests": [], "message": "No open request."}
    assert data["career"]["opted_in"] is False
    # delivery is None ("Not Yet Calculable") when nothing is planned, never 0
    assert data["course_progress"]["percent"] is None and data["course_progress"]["state"] == "Empty"
    assert data["certificate"]["status"] == "Not Yet Eligible"
    assert data["ask_nipuna"]["used"] == 0 and data["ask_nipuna"]["limit"] > 0


def test_engagement_is_stale_not_zero_until_there_is_recent_activity(client, world, run_sql):
    # signing in records activity; age it so the student looks quiet
    run_sql("UPDATE activity_events SET occurred_at = now() - interval '40 days' WHERE student_id = :sid", sid=world.students["s2"].student_id)
    quiet = home(client, world, "s2")["engagement"]
    assert quiet["state"] == "Stale" and quiet["level"] is None and "Stale" in quiet["message"]
    student = world.students["s2"]
    enrolment_id = next(e["enrolment_id"] for e in student.enrolments)
    db.session.add(ActivityEvent(student_id=student.student_id, enrolment_id=enrolment_id, kind="login",
                                 occurred_at=datetime.now(timezone.utc) - timedelta(hours=3)))
    _commit()
    live = home(client, world, "s2")["engagement"]
    assert live["state"] == "Fresh" and live["refreshed_at"]


def test_next_class_join_state_and_meet_stay_unverified(client, world, make_session):
    make_session(world.batches["G1"], world.people["g1"], datetime.now(IST) + timedelta(days=1), title="Online class", mode="Live Online",
                 meet_status="Pending Verification")
    nxt = home(client, world, "s1")["next_class"]
    assert nxt["mode"] == "Live Online" and nxt["meet_status_label"] == "Pending Verification"
    assert nxt["join"]["enabled"] is False and nxt["join"]["url"] is None and "Pending Verification" in nxt["join"]["reason"]
    assert "meet.google.com" not in str(nxt)


def test_continue_learning_follows_the_last_class_taught(client, world, make_session):
    base = datetime.now(IST)
    make_session(world.batches["G1"], world.people["g1"], base - timedelta(days=3), title="Earlier", state="Delivered",
                 delivered_at=base - timedelta(days=3), topic_id=world.topics[0].topic_id)
    make_session(world.batches["G1"], world.people["g1"], base - timedelta(days=1), title="Latest", state="Delivered",
                 delivered_at=base - timedelta(days=1), topic_id=world.topics[1].topic_id)
    card = home(client, world, "s1")["continue_learning"]
    assert card["state"] == "Ready" and card["basis"] == "Last class taught"
    assert card["module"]["title"] == "Core Java" and card["topic"]["title"] == "Streams"
    assert home(client, world, "s3")["continue_learning"]["state"] == "Empty"  # another batch's classes do not count


def test_due_work_and_support_come_from_the_existing_services(client, world, released_assignment):
    data = home(client, world, "s1")
    assert data["due_work"]["state"] == "Ready" and data["due_work"]["assignments"] == 1
    assert data["due_work"]["nearest"]["title"] == "Regression on housing dataset"
    assert home(client, world, "s3")["due_work"]["assignments"] == 0  # the assignment belongs to G1 only
    raised = client.post(f"{API}/support-requests", json={"category": "Academic", "subject": "Need help", "details": "Please help"},
                         headers=world.h["s1"])
    assert raised.status_code == 201, raised.get_json()
    support = home(client, world, "s1")["support"]
    assert support["open_count"] == 1 and support["requests"][0]["owner"]
    assert home(client, world, "s2")["support"]["open_count"] == 0


def test_one_failing_card_does_not_break_the_home_screen(client, world, monkeypatch):
    def boom():
        raise RuntimeError("recordings exploded")

    monkeypatch.setattr(student_home, "_latest_recording", boom)
    data = home(client, world, "s1")
    assert data["latest_recording"]["state"] == "Unavailable"
    assert data["next_class"]["state"] == "Empty" and data["ask_nipuna"]["state"] == "Ready"  # the rest still render


# ---------------------------------------------------------------- Trainer Today

def test_trainer_today_is_trainer_only(client, world):
    assert client.get(f"{API}/trainer/today").status_code == 401
    for who in ("s1", "ac", "bm", "admin"):
        assert client.get(f"{API}/trainer/today", headers=world.h[who]).status_code == 403


def test_trainer_today_empty_state_and_scope_note(client, world):
    data = today_view(client, world)
    assert data["today"] == {"state": "Empty", "date": data["today"]["date"], "sessions": [], "message": "No assigned session scheduled today."}
    assert "assigned batches and students" in data["scope_note"]
    assert data["tiles"]["sessions"]["count"] == 0
    assert data["tiles"]["reviews"] == {"state": "Ready", "count": 0, "oldest_submitted_at": None, "oldest_age_days": None}
    assert data["tiles"]["support_flags"]["count"] == 0 and data["tiles"]["support_flags"]["assigned_students"] == 2


def test_trainer_today_counts_only_assigned_work(client, world, make_session, released_assignment):
    now = datetime.now(IST)
    make_session(world.batches["G1"], world.people["g1"], now + timedelta(days=2), title="Mine")
    make_session(world.batches["G1"], world.people["g1"], now + timedelta(days=12), title="Too far away")
    make_session(world.batches["G2"], world.people["g2"], now + timedelta(days=2), title="Someone else's")
    submitted = client.post(f"{API}/assignments/{released_assignment['assignment_id']}/submissions", json={"body_text": "work"}, headers=world.h["s1"])
    assert submitted.status_code == 201, submitted.get_json()
    tiles = today_view(client, world, "g1")["tiles"]
    assert tiles["sessions"]["count"] == 1
    assert tiles["reviews"]["count"] == 1 and tiles["reviews"]["oldest_age_days"] == 0
    other = today_view(client, world, "g2")["tiles"]
    assert other["sessions"]["count"] == 1 and other["reviews"]["count"] == 0  # g2 neither reviews g1's work nor sees its classes


def test_trainer_today_lists_todays_sessions_with_the_flow_state(client, world, make_session):
    start = datetime.now(IST) + timedelta(minutes=10)
    if start.date() != datetime.now(IST).date():
        pytest.skip("too close to midnight IST")
    session = make_session(world.batches["G1"], world.people["g1"], start, title="Today's class", topic_id=world.topics[0].topic_id)
    make_session(world.batches["G2"], world.people["g2"], start, title="Another trainer's class")
    data = today_view(client, world)["today"]
    assert data["state"] == "Ready" and [s["session_id"] for s in data["sessions"]] == [session.session_id]
    item = data["sessions"][0]
    assert item["state"] == "Scheduled" and item["topic"]["title"] == "OOP & Collections"
    assert item["attendance"]["seats"] == 2 and item["attendance"]["marked"] == 0 and item["attendance"]["can_mark"] is True
    assert item["recording"]["mapping"] == "Pending Verification"
    # the stepper drives the existing endpoints: start -> deliver -> notes
    assert client.post(f"{API}/class-sessions/{session.session_id}/start", headers=world.h["g1"]).status_code == 200
    assert client.post(f"{API}/class-sessions/{session.session_id}/deliver", json={}, headers=world.h["g1"]).status_code == 200
    saved = client.put(f"{API}/class-sessions/{session.session_id}/notes", json={"notes": "Covered OOP; revisit interfaces."}, headers=world.h["g1"])
    assert saved.status_code == 200 and saved.get_json()["data"]["notes"].startswith("Covered OOP")
    item = today_view(client, world)["today"]["sessions"][0]
    assert item["state"] == "Delivered" and item["notes"].startswith("Covered OOP")


def test_session_notes_need_the_teaching_trainer_and_a_started_class(client, world, make_session):
    session = make_session(world.batches["G1"], world.people["g1"], datetime.now(IST) + timedelta(days=2), title="Later")
    url = f"{API}/class-sessions/{session.session_id}/notes"
    assert client.put(url, json={"notes": "x"}, headers=world.h["g1"]).status_code == 422  # still Scheduled
    assert client.put(url, json={"notes": "x"}, headers=world.h["s1"]).status_code == 403
    assert client.put(url, json={"notes": "x"}, headers=world.h["g2"]).status_code == 404  # another batch's trainer
    assert client.put(url, json={}, headers=world.h["g1"]).status_code == 400


# ---------------------------------------------------------------- Reports

def quiet_students(run_sql):
    """Signing in records activity; age it so every student looks quiet."""
    run_sql("UPDATE activity_events SET occurred_at = now() - interval '40 days'")


def test_trainer_reports_cover_only_assigned_batches(client, world, run_sql):
    quiet_students(run_sql)
    response = client.get(f"{API}/trainer/reports", headers=world.h["g1"])
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    rows = data["batches"]["rows"]
    assert [r["batch"]["batch_id"] for r in rows] == [world.batches["G1"].batch_id]
    assert rows[0]["students"] == 2
    assert rows[0]["delivery"]["percent"] is None  # no class planned: Not Yet Calculable, not 0
    assert data["review_turnaround"]["state"] == "Empty"
    assert data["engagement"]["state"] == "Stale"
    for who in ("s1", "ac", "admin"):
        assert client.get(f"{API}/trainer/reports", headers=world.h[who]).status_code == 403
    assert client.get(f"{API}/trainer/reports").status_code == 401


def test_trainer_reports_show_delivery_attendance_and_review_turnaround(client, world, make_session, released_assignment, run_sql):
    base = datetime.now(IST)
    make_session(world.batches["G1"], world.people["g1"], base - timedelta(days=2), state="Delivered", delivered_at=base - timedelta(days=2))
    make_session(world.batches["G1"], world.people["g1"], base + timedelta(days=2))
    row = client.get(f"{API}/trainer/reports", headers=world.h["g1"]).get_json()["data"]["batches"]["rows"][0]
    assert row["delivery"]["percent"] == 50.0
    submitted = client.post(f"{API}/assignments/{released_assignment['assignment_id']}/submissions", json={"body_text": "work"}, headers=world.h["s1"])
    sid = submitted.get_json()["data"]["submission_id"]
    reviewed = client.post(f"{API}/submissions/{sid}/review", json={"outcome": "Reviewed", "feedback": "Good", "marks": 15}, headers=world.h["g1"])
    assert reviewed.status_code in (200, 201), reviewed.get_json()
    # the test transaction shares one database clock, so place the review five hours after the submission
    run_sql("UPDATE submission_reviews SET reviewed_at = (SELECT submitted_at FROM assignment_submissions s WHERE s.submission_id = "
            "submission_reviews.submission_id) + interval '5 hours'")
    turnaround = client.get(f"{API}/trainer/reports", headers=world.h["g1"]).get_json()["data"]["review_turnaround"]
    assert turnaround["state"] == "Calculated" and turnaround["reviewed"] == 1 and turnaround["average_hours"] == 5.0
    assert client.get(f"{API}/trainer/reports", headers=world.h["g2"]).get_json()["data"]["review_turnaround"]["state"] == "Empty"


def test_review_turnaround_is_partial_data_when_timestamps_are_missing():
    from services.trainer_workspace import review_turnaround

    now = datetime.now(timezone.utc)
    result = review_turnaround([(now - timedelta(hours=10), now), (None, now), (now, now - timedelta(hours=1))])
    assert result["state"] == "Partial Data" and result["missing_timestamps"] == 2 and result["average_hours"] == 10.0
    assert review_turnaround([])["state"] == "Empty"


def test_academic_reports_are_limited_to_the_users_branch(client, world, make_session):
    base = datetime.now(IST)
    make_session(world.batches["G1"], world.people["g1"], base - timedelta(days=2), state="Delivered", delivered_at=base - timedelta(days=2))
    ac = client.get(f"{API}/academic/reports", headers=world.h["ac"])
    assert ac.status_code == 200, ac.get_json()
    blocks = ac.get_json()["data"]["branches"]
    assert [b["branch"]["branch_code"] for b in blocks] == ["NIT-GNT"]
    delivered = blocks[0]["curriculum_delivered"]
    assert delivered["percent"] == 100.0 and delivered["batches"] == 2  # G2 has no class planned: the figure is Partial Data, not diluted to 50
    assert delivered["state"] == "Partial Data" and world.batches["G2"].batch_code in delivered["message"]
    assert blocks[0]["certificate_lead_time"]["state"] == "Not Configured"
    assert blocks[0]["completion_reviews"]["state"] == "Empty"
    vij = client.get(f"{API}/academic/reports", headers=world.h["ac_vij"]).get_json()["data"]["branches"]
    assert [b["branch"]["branch_code"] for b in vij] == ["NIT-VIJ"]
    assert vij[0]["curriculum_delivered"]["percent"] is None  # V1 has no class planned: Not Yet Calculable, not 0
    assert client.get(f"{API}/academic/reports?branch_id=2", headers=world.h["ac"]).status_code == 404  # another branch is invisible
    allb = client.get(f"{API}/academic/reports", headers=world.h["admin"]).get_json()["data"]["branches"]
    assert len(allb) >= 2
    for who in ("g1", "s1"):
        assert client.get(f"{API}/academic/reports", headers=world.h[who]).status_code == 403


def test_academic_reports_flag_completed_enrolments_without_a_review_as_partial(client, world):
    enrolment_id = next(e["enrolment_id"] for e in world.students["s1"].enrolments)
    db.session.get(Enrolment, enrolment_id).status = "Completed"
    _commit()
    block = client.get(f"{API}/academic/reports", headers=world.h["ac"]).get_json()["data"]["branches"][0]
    completion = block["completion_reviews"]
    assert completion["state"] == "Partial Data" and completion["completed_without_review"] == 1
    enrolment = db.session.get(Enrolment, enrolment_id)
    enrolment.joining_date = datetime.now(IST).date() - timedelta(days=30)
    enrolment.status = "Active"  # a review can only be opened on an Active enrolment
    db.session.add(CompletionReview(enrolment_id=enrolment_id, status="Decided", opened_by=world.people["ac"].user_id, decision="Complete",
                                    decided_by=world.people["ac"].user_id, decided_at=datetime.now(timezone.utc), evidence={"note": "test"}))
    _commit()
    db.session.get(Enrolment, enrolment_id).status = "Completed"
    _commit()
    block = client.get(f"{API}/academic/reports", headers=world.h["ac"]).get_json()["data"]["branches"][0]
    assert block["completion_reviews"]["state"] == "Calculated" and block["completion_reviews"]["closed"] == 1

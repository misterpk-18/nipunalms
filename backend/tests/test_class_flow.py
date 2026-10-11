"""UX phase U12: Today's guided class flow (saved progress, the full class log, no Meet link), the trainer's to-do counts and
My requests."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from config.timezone import IST
from models import AttendanceRecord, ClassFlowProgress, ClassSession, ClassSessionTopic, MeetEvent, Notification
from tests import attendance_world

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    world = attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)
    world.make_session = make_session
    return world


def now():
    return datetime.now(timezone.utc)


def today_data(client, w, who="t1"):
    response = client.get(f"{API}/trainer/today", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def flow_of(client, w, session, who="t1"):
    response = client.get(f"{API}/class-sessions/{session.session_id}/flow", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def save_flow(client, w, session, body, who="t1"):
    return client.put(f"{API}/class-sessions/{session.session_id}/flow", json=body, headers=w.h[who])


def counts(client, w, who="t1"):
    response = client.get(f"{API}/me/nav-counts?workspace=trainer", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def running_class(w, **columns):
    """A class that began 30 minutes ago and ends in 90 (inside today's window for the trainer)."""
    return w.make_session(w.b1, w.t1, now() - timedelta(minutes=30), title="Running class", topic_id=w.topics[0], **columns)


# ---------------------------------------------------------------- the flow and its saved progress

def test_the_flow_starts_at_the_first_step_and_is_clamped_to_the_class_state(client, w):
    session = running_class(w)
    item = flow_of(client, w, session)
    assert item["flow"]["steps"] == ["open", "join", "attendance", "log"] and item["flow"]["step"] == "open"
    assert item["flow"]["can_start"] is True and item["log"] is None
    # not started: asking for a later step is held at the first one
    assert save_flow(client, w, session, {"step": "log"}).get_json()["data"]["flow"]["step"] == "open"
    assert client.post(f"{API}/class-sessions/{session.session_id}/start", headers=w.h["t1"]).status_code == 200
    assert flow_of(client, w, session)["flow"]["step"] == "join"          # a started class is at least at Join


def test_progress_and_the_draft_log_survive_a_refresh(client, w):
    session = running_class(w)
    client.post(f"{API}/class-sessions/{session.session_id}/start", headers=w.h["t1"])
    saved = save_flow(client, w, session, {"step": "attendance", "draft": {"notes": "Covered OOP", "break_minutes": 10, "topic_ids": [w.topics[0]]}})
    assert saved.status_code == 200, saved.get_json()
    assert db.session.get(ClassFlowProgress, session.session_id).step == "attendance"
    # the "refresh": the class comes back from the server with the same step and draft
    item = today_data(client, w)["today"]["sessions"][0]
    assert item["flow"]["step"] == "attendance"
    assert item["flow"]["draft"] == {"notes": "Covered OOP", "break_minutes": 10, "topic_ids": [w.topics[0]]}
    again = save_flow(client, w, session, {"draft": {"outcome": "Partially Held"}}).get_json()["data"]["flow"]
    assert again["step"] == "attendance" and again["draft"]["notes"] == "Covered OOP" and again["draft"]["outcome"] == "Partially Held"
    assert save_flow(client, w, session, {"step": "nonsense"}).status_code == 400
    assert save_flow(client, w, session, {"draft": {"break_minutes": 9999}}).status_code == 400


def test_topic_options_list_the_curriculum_by_module(client, w):
    options = flow_of(client, w, running_class(w))["flow"]["topic_options"]
    assert {o["title"] for o in options} >= {"OOP", "Collections", "REST APIs"} and {o["module"] for o in options} >= {"Core Java", "Spring Boot"}


def test_only_the_teaching_trainer_runs_the_flow(client, w):
    session = running_class(w)
    url = f"{API}/class-sessions/{session.session_id}/flow"
    assert client.get(url, headers=w.h["t2"]).status_code == 404              # another batch's trainer cannot even see it
    assert client.get(url, headers=w.h["s1"]).status_code == 403
    assert client.get(url, headers=w.h["ac"]).status_code == 403              # a Branch Manager runs classes from the schedule
    assert client.put(url, json={"step": "open"}, headers=w.h["t2"]).status_code == 404
    assert client.get(url).status_code == 401


def test_delivering_saves_the_whole_class_log(client, w):
    session = running_class(w)
    client.post(f"{API}/class-sessions/{session.session_id}/start", headers=w.h["t1"])
    save_flow(client, w, session, {"step": "log", "draft": {"notes": "draft"}})
    start = (now() - timedelta(minutes=20)).isoformat()
    body = {"outcome": "Partially Held", "actual_start": start, "actual_end": now().isoformat(), "break_minutes": 5,
            "topic_ids": [w.topics[0], w.topics[2]], "notes": "Covered OOP and REST", "attendance": [{"enrolment_id": w.e1, "status": "Present"}],
            "attendance_default_status": "Absent"}
    assert client.post(f"{API}/class-sessions/{session.session_id}/deliver", json=body, headers=w.h["t1"]).status_code == 400  # what was not delivered?
    body["unfulfilled_note"] = "Ran out of time for collections"
    response = client.post(f"{API}/class-sessions/{session.session_id}/deliver", json=body, headers=w.h["t1"])
    assert response.status_code == 200, response.get_json()
    done = response.get_json()["data"]
    assert done["state"] == "Delivered" and done["delivery_outcome"] == "Partially Held" and done["break_minutes"] == 5
    assert done["delivered_minutes"] == 15 and done["unfulfilled_note"].startswith("Ran out")
    assert db.session.get(ClassFlowProgress, session.session_id) is None     # the saved progress is gone
    covered = db.session.execute(select(ClassSessionTopic.topic_id).where(ClassSessionTopic.session_id == session.session_id)).scalars().all()
    assert sorted(covered) == sorted([w.topics[0], w.topics[2]])
    statuses = {r.enrolment_id: r.status for r in db.session.execute(select(AttendanceRecord).where(AttendanceRecord.session_id == session.session_id)).scalars()}
    assert statuses == {w.e1: "Present", w.e2: "Absent"}                      # the entry, and the default for everyone else
    item = flow_of(client, w, session)
    assert item["flow"]["step"] is None and item["flow"]["steps"] == []
    assert item["log"]["outcome"] == "Partially Held" and [t["title"] for t in item["log"]["topics"]] == ["OOP", "REST APIs"]
    assert item["attendance"]["marked"] == 2
    assert save_flow(client, w, session, {"step": "log"}).status_code == 422  # nothing left to run
    told = db.session.execute(select(Notification).where(Notification.title.like("Partially held%"))).scalars().all()
    assert told and all(n.link for n in told)


def test_a_topic_from_another_course_is_refused(client, w):
    session = running_class(w)
    assert client.post(f"{API}/class-sessions/{session.session_id}/deliver", json={"topic_ids": [999999]}, headers=w.h["t1"]).status_code == 400
    assert db.session.get(ClassSession, session.session_id).state == "Scheduled"


# ---------------------------------------------------------------- classes that ended without a log

def test_a_class_that_can_no_longer_be_started_has_just_the_log(client, w):
    session = w.make_session(w.b1, w.t1, now() - timedelta(hours=10), title="Yesterday's class")
    item = flow_of(client, w, session)
    assert item["flow"]["steps"] == ["log"] and item["flow"]["step"] == "log"
    assert client.post(f"{API}/class-sessions/{session.session_id}/start", headers=w.h["t1"]).status_code == 422
    done = client.post(f"{API}/class-sessions/{session.session_id}/deliver", json={"attendance_default_status": "Present"}, headers=w.h["t1"])
    assert done.status_code == 200, done.get_json()
    assert flow_of(client, w, session)["attendance"]["marked"] == 2


def test_missing_class_logs_are_counted_and_listed(client, w):
    missed = w.make_session(w.b1, w.t1, now() - timedelta(hours=30), title="Missed class")
    w.make_session(w.b1, w.t1, now() - timedelta(days=40), title="Too old to chase")
    w.make_session(w.b1, w.t1, now() + timedelta(days=1), title="Still to come")
    w.make_session(w.b2, w.t2, now() - timedelta(hours=30), title="Another trainer's")
    assert counts(client, w)["class_logs"] == 1 and counts(client, w, "t2")["class_logs"] == 1
    todo = today_data(client, w)["todo"]
    assert todo["class_logs"]["count"] == 1 and [s["session_id"] for s in todo["class_logs"]["sessions"]] == [missed.session_id]
    client.post(f"{API}/class-sessions/{missed.session_id}/deliver", json={}, headers=w.h["t1"])
    assert counts(client, w)["class_logs"] == 0


# ---------------------------------------------------------------- Today

def test_today_picks_the_next_class_and_shows_tomorrow_when_nothing_is_left(client, w):
    data = today_data(client, w)
    assert data["today"]["state"] == "Empty" and data["tomorrow"] == {"date": data["tomorrow"]["date"], "sessions": []}
    start = now() + timedelta(days=1)
    w.make_session(w.b1, w.t1, start, title="Tomorrow's class")
    assert [s["title"] for s in today_data(client, w)["tomorrow"]["sessions"]] == ["Tomorrow's class"]
    first, second = now() - timedelta(minutes=30), now() + timedelta(minutes=45)
    if first.astimezone(IST).date() != second.astimezone(IST).date() or first.astimezone(IST).date() != now().astimezone(IST).date():
        pytest.skip("too close to midnight IST")
    a = w.make_session(w.b1, w.t1, first, hours=0.25, title="Earlier")
    b = w.make_session(w.b1, w.t1, second, title="Later")
    data = today_data(client, w)
    assert data["today"]["next_up"] == b.session_id and data["tomorrow"] is None   # the earlier class has ended: the later one is next
    client.post(f"{API}/class-sessions/{a.session_id}/start", headers=w.h["t1"])
    assert today_data(client, w)["today"]["next_up"] == a.session_id               # a class that is on now comes first


def test_the_todo_counts_match_the_navigation_badges(client, w):
    done = w.delivered(w.recent_start, w.topics[0], "Marked halfway")
    client.put(f"{API}/attendance/sessions/{done.session_id}", json={"entries": [{"enrolment_id": w.e1, "status": "Present"}]}, headers=w.h["t1"])
    cid = client.post(f"{API}/attendance/corrections", json={"session_id": w.older.session_id, "enrolment_id": w.e1, "requested_status": "Present",
                                                             "reason": "Was there"}, headers=w.h["t1"]).get_json()["data"]["correction_id"]
    assert cid
    nav = counts(client, w)
    assert set(nav) == {"to_grade", "support", "attendance", "class_logs"}
    todo = today_data(client, w)["todo"]
    work = todo["attendance"]
    assert work["classes"] >= 1 and work["corrections"] == 1 and nav["attendance"] == work["total"]
    assert todo["assignments"] + todo["attempts"] == nav["to_grade"]


# ---------------------------------------------------------------- no Meet link

def test_asking_for_a_meet_link_tells_the_branch_once(client, w):
    session = running_class(w, mode="Live Online", meet_status="Pending Verification")
    url = f"{API}/class-sessions/{session.session_id}/meet/request-link"
    assert flow_of(client, w, session)["meet"]["link_requested_at"] is None
    asked = client.post(url, headers=w.h["t1"])
    assert asked.status_code == 200, asked.get_json()
    assert asked.get_json()["data"]["meet"]["link_requested_at"] is not None
    assert client.post(url, headers=w.h["t1"]).status_code == 200            # asking twice is harmless
    events = db.session.execute(select(MeetEvent).where(MeetEvent.session_id == session.session_id, MeetEvent.event_type == "Link requested")).scalars().all()
    assert len(events) == 1
    told = db.session.execute(select(Notification).where(Notification.title.like("Meet link needed%"))).scalars().all()
    assert {n.recipient_user_id for n in told} == {w.ac.user_id, w.ac2.user_id, w.bm.user_id}
    assert all(n.link and n.action_status == "Open" for n in told)
    # the trainer carries on: the flow still works
    assert client.post(f"{API}/class-sessions/{session.session_id}/start", headers=w.h["t1"]).status_code == 200
    assert flow_of(client, w, session)["flow"]["step"] == "join"


def test_the_meet_link_request_has_rules(client, w):
    classroom = running_class(w)
    assert client.post(f"{API}/class-sessions/{classroom.session_id}/meet/request-link", headers=w.h["t1"]).status_code == 422
    online = w.make_session(w.b1, w.t1, now() + timedelta(hours=3), mode="Live Online", meet_status="Pending Verification", title="Online class")
    assert client.post(f"{API}/class-sessions/{online.session_id}/meet/request-link", headers=w.h["t2"]).status_code == 404
    assert client.post(f"{API}/class-sessions/{online.session_id}/meet/request-link", headers=w.h["ac"]).status_code == 403
    client.put(f"{API}/class-sessions/{online.session_id}/meet", json={"meet_link": "https://meet.google.com/abc-defg-hij"}, headers=w.h["ac"])
    assert client.post(f"{API}/class-sessions/{online.session_id}/meet/request-link", headers=w.h["t1"]).status_code == 422  # it has one now


# ---------------------------------------------------------------- My requests

def ask_reschedule(client, w, session, who="t1"):
    start = now() + timedelta(days=4)
    return client.post(f"{API}/class-sessions/{session.session_id}/reschedule-requests", headers=w.h[who],
                       json={"proposed_starts_at": start.isoformat(), "proposed_ends_at": (start + timedelta(hours=2)).isoformat(), "reason": "Hospital visit"})


def mine(client, w, who="t1"):
    response = client.get(f"{API}/me/requests", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def test_my_requests_lists_reschedules_and_corrections_with_their_decisions(client, w):
    assert mine(client, w) == {"items": [], "counts": {"waiting": 0, "decided": 0}}
    rid = ask_reschedule(client, w, w.future).get_json()["data"]["request_id"]
    cid = client.post(f"{API}/attendance/corrections", headers=w.h["t1"], json={
        "session_id": w.older.session_id, "enrolment_id": w.e1, "requested_status": "Present", "reason": "Was in class"}).get_json()["data"]["correction_id"]
    data = mine(client, w)
    assert data["counts"] == {"waiting": 2, "decided": 0}
    assert {(i["kind"], i["status"], i["decides"]) for i in data["items"]} == {("reschedule", "Pending", "Branch Manager"), ("correction", "Pending", "Branch Manager")}
    assert mine(client, w, "t2")["items"] == []                              # nobody else's requests
    assert client.get(f"{API}/me/requests", headers=w.h["s1"]).status_code == 403
    assert client.get(f"{API}/me/requests").status_code == 401

    assert client.post(f"{API}/reschedule-requests/{rid}/reject", json={"note": "Exam week, please keep the date"}, headers=w.h["ac"]).status_code == 200
    assert client.post(f"{API}/attendance/corrections/{cid}/decision", json={"decision": "Approved", "decision_note": "Register checked"},
                       headers=w.h["bm"]).status_code == 200
    data = mine(client, w)
    assert data["counts"] == {"waiting": 0, "decided": 2}
    by_kind = {i["kind"]: i for i in data["items"]}
    assert by_kind["reschedule"]["status"] == "Rejected" and by_kind["reschedule"]["decision_note"].startswith("Exam week")
    assert by_kind["reschedule"]["decided_by"]["full_name"] == "Coordinator Guntur" and by_kind["reschedule"]["reason"] == "Hospital visit"
    assert by_kind["correction"]["status"] == "Approved" and by_kind["correction"]["decided_by"]["full_name"] == "Manager Guntur"
    assert by_kind["correction"]["summary"].startswith("Not marked to Present") and by_kind["correction"]["session"]["title"] == "Older class"


def test_my_requests_lists_recovery_requests_and_tells_the_trainer_the_decision(client, w):
    from tests.test_attendance import absent_entry, request_recovery

    attendance_id = absent_entry(client, w)
    recovery = request_recovery(client, w, "t1", attendance_id).get_json()["data"]
    (item,) = [i for i in mine(client, w)["items"] if i["kind"] == "recovery"]
    assert item["status"] == "Pending" and item["decides"] == "Branch Manager" and item["title"] == "Recovery for Anvitha K."
    assert item["summary"].startswith("Recording watched for the class") and item["reason"] == "Was unwell"
    assert mine(client, w)["counts"] == {"waiting": 1, "decided": 0}

    assert client.post(f"{API}/attendance/recoveries/{recovery['recovery_id']}/decision", json={"decision": "Approved", "decision_note": "Watch by Friday"},
                       headers=w.h["bm"]).status_code == 200
    (item,) = [i for i in mine(client, w)["items"] if i["kind"] == "recovery"]
    assert item["status"] == "Approved" and item["decided_by"]["full_name"] == "Manager Guntur" and item["decision_note"] == "Watch by Friday"
    told = db.session.execute(select(Notification).where(Notification.recipient_user_id == w.t1.user_id,
                                                         Notification.event_key == f"recovery-decided-requester:{recovery['recovery_id']}")).scalar_one()
    assert told.link == "/trainer/requests"


def test_each_decision_notifies_the_trainer_with_a_link_to_my_requests(client, w):
    rid = ask_reschedule(client, w, w.future).get_json()["data"]["request_id"]
    cid = client.post(f"{API}/attendance/corrections", headers=w.h["t1"], json={
        "session_id": w.older.session_id, "enrolment_id": w.e1, "requested_status": "Present", "reason": "Was in class"}).get_json()["data"]["correction_id"]
    assert client.post(f"{API}/reschedule-requests/{rid}/approve", json={"note": "Fine"}, headers=w.h["ac"]).status_code == 200
    assert client.post(f"{API}/attendance/corrections/{cid}/decision", json={"decision": "Rejected", "decision_note": "Not in the register"},
                       headers=w.h["bm"]).status_code == 200
    told = db.session.execute(select(Notification).where(Notification.recipient_user_id == w.t1.user_id,
                                                         Notification.event_key.in_([f"reschedule-decision-{rid}", f"correction-decided:{cid}"]))).scalars().all()
    assert {n.event_key: n.link for n in told} == {f"reschedule-decision-{rid}": "/trainer/requests", f"correction-decided:{cid}": "/trainer/requests"}
    assert all(n.body for n in told)


def test_a_branch_managers_own_request_names_the_founder_or_super_admin(client, w):
    client.post(f"{API}/attendance/corrections", headers=w.h["ac"], json={
        "session_id": w.older.session_id, "enrolment_id": w.e1, "requested_status": "Absent", "reason": "Wrong entry"})
    assert mine(client, w, "ac")["items"][0]["decides"] == "Founder or Super Admin"

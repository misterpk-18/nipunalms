"""UX phase U10: My Progress. "What to do next" (`GET /me/progress/next-steps`) and the request status on each attendance row."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from config.database import db
from config.timezone import today_ist
from models import AttendanceRecord, Certificate
from tests import attendance_world
from tests.assessment_world import API as ASSESSMENT_API
from tests.assessment_world import released_assignment, world  # noqa: F401 (fixtures)
from tests.test_assignments import move_deadline
from tests.test_certificates import complete

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login, run_sql):
    world_ = attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)
    for enrolment_id in (world_.e1, world_.e2, world_.e3):
        attendance_world.set_fee(run_sql, enrolment_id)
    return world_


def steps(client, headers):
    response = client.get(f"{API}/me/progress/next-steps", headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def kinds(client, headers) -> list[str]:
    return [step["kind"] for step in steps(client, headers)]


def mark(client, w, session, entries):
    response = client.put(f"{API}/attendance/sessions/{session.session_id}", json={"entries": entries}, headers=w.h["t1"])
    assert response.status_code == 200, response.get_json()


def absent_three_times(client, w, run_sql):
    """Three marked absences: enough for the attendance alert (it needs three marked classes)."""
    run_sql("UPDATE app_settings SET setting_value = '30' WHERE setting_key = 'attendance_lock_days'")
    third = w.delivered(w.recent_start - timedelta(days=3), w.topics[2], "Third class")
    for session in (w.recent, w.older, third):
        mark(client, w, session, [{"enrolment_id": w.e1, "status": "Absent"}])


def attendance_rows(client, w, who="s1"):
    (block,) = client.get(f"{API}/me/attendance", headers=w.h[who]).get_json()["data"]
    return {row["session"]["title"]: row for row in block["rows"]}


def attendance_id(w, session) -> int:
    return db.session.execute(select(AttendanceRecord.attendance_id).where(AttendanceRecord.session_id == session.session_id,
                                                                           AttendanceRecord.enrolment_id == w.e1)).scalar_one()


# ---------------------------------------------------------------- what to do next

def test_a_student_with_nothing_to_do_gets_an_empty_list(client, w):
    assert steps(client, w.h["s3"]) == []


def test_only_students_have_next_steps(client, w):
    assert client.get(f"{API}/me/progress/next-steps", headers=w.h["t1"]).status_code == 403
    assert client.get(f"{API}/me/progress/next-steps").status_code == 401


def test_an_absence_that_can_be_recovered_is_the_first_thing_to_do(client, w):
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Absent"}])
    first = steps(client, w.h["s1"])[0]
    assert first["kind"] == "recovery" and first["params"] == {"n": 1, "session": "Recent class"}
    assert first["course"]["course_code"] == "NIT-CRS-047"

    # asking for the recovery takes the step away: it is now waiting for the Branch Manager
    asked = client.post(f"{API}/attendance/recoveries", json={"attendance_id": attendance_id(w, w.recent), "method": "Recording watched",
                                                              "reason": "Was unwell"}, headers=w.h["s1"])
    assert asked.status_code == 201
    assert "recovery" not in kinds(client, w.h["s1"])


def test_attendance_below_the_alert_level_is_a_step_with_the_figures(client, w, run_sql):
    absent_three_times(client, w, run_sql)
    low = next(s for s in steps(client, w.h["s1"]) if s["kind"] == "attendance_low")
    assert low["params"] == {"percent": 0, "threshold": 75}


def test_a_certificate_waiting_for_the_fee_and_a_ready_one_are_steps(client, w, run_sql):
    attendance_world.set_fee(run_sql, w.e1, balance=5000)
    complete(client, w)
    fee = next(s for s in steps(client, w.h["s1"]) if s["kind"] == "certificate_fee")
    assert fee["params"] == {"balance": "5000.00"}

    attendance_world.set_fee(run_sql, w.e1)  # paid
    complete_to_issue(client, w)
    ready = next(s for s in steps(client, w.h["s1"]) if s["kind"] == "certificate_ready")
    assert ready["course"]["course_code"] == "NIT-CRS-047"
    assert "certificate_fee" not in kinds(client, w.h["s1"])


def complete_to_issue(client, w):
    """Approve and issue the certificate that `complete()` opened for S1; returns its id."""
    cid = db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == w.e1)).scalar_one()
    assert client.post(f"{API}/certificates/{cid}/approval", json={}, headers=w.h["bm"]).status_code == 200
    assert client.post(f"{API}/certificates/{cid}/issue", json={}, headers=w.h["bm"]).status_code == 200
    return cid


def test_access_that_ends_within_a_month_or_has_ended_is_one_step_per_course(client, w, run_sql):
    today = today_ist()
    run_sql("UPDATE enrolments SET joining_date = :d WHERE enrolment_id = :e", d=today - timedelta(days=345), e=w.e1)
    ending = next(s for s in steps(client, w.h["s1"]) if s["kind"] == "access_ending")
    assert ending["params"]["what"] == "both" and ending["params"]["can_request"] is True
    assert ending["params"]["until"] == (today - timedelta(days=345)).replace(year=(today - timedelta(days=345)).year + 1).isoformat()

    run_sql("UPDATE enrolments SET joining_date = :d WHERE enrolment_id = :e", d=today - timedelta(days=400), e=w.e1)
    ended = [s for s in steps(client, w.h["s1"]) if s["kind"].startswith("access_")]
    assert [s["kind"] for s in ended] == ["access_ended"] and ended[0]["params"]["what"] == "both"


def test_the_list_is_ordered_by_urgency_and_capped(client, w, run_sql):
    absent_three_times(client, w, run_sql)
    run_sql("UPDATE enrolments SET joining_date = :d WHERE enrolment_id = :e", d=today_ist() - timedelta(days=400), e=w.e1)
    order = kinds(client, w.h["s1"])
    assert order.index("recovery") < order.index("attendance_low") < order.index("access_ended")
    assert len(order) <= 6


def test_overdue_work_comes_first_and_open_work_is_counted(client, world, released_assignment, run_sql):  # noqa: F811
    move_deadline(run_sql, released_assignment["assignment_id"], 48)
    only = client.get(f"{ASSESSMENT_API}/me/progress/next-steps", headers=world.h["s1"]).get_json()["data"]
    assert [(s["kind"], s["params"]) for s in only if s["kind"].startswith("work_")] == [("work_todo", {"n": 1})]

    move_deadline(run_sql, released_assignment["assignment_id"], -5, 100)  # past its deadline, still open for late hand-in
    steps_now = client.get(f"{ASSESSMENT_API}/me/progress/next-steps", headers=world.h["s1"]).get_json()["data"]
    assert steps_now[0]["kind"] == "work_overdue" and steps_now[0]["params"] == {"n": 1}
    assert "work_todo" not in [s["kind"] for s in steps_now]


# ---------------------------------------------------------------- attendance rows carry the request status

def test_a_recovery_request_shows_its_status_and_who_decides(client, w):
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Absent"}])
    row = attendance_rows(client, w)["Recent class"]
    assert row["can_request_recovery"] is True and row["recovery"] is None

    rid = client.post(f"{API}/attendance/recoveries", json={"attendance_id": row["attendance_id"], "method": "Recording watched", "reason": "Was unwell"},
                      headers=w.h["s1"]).get_json()["data"]["recovery_id"]
    row = attendance_rows(client, w)["Recent class"]
    assert row["can_request_recovery"] is False
    assert (row["recovery"]["status"], row["recovery"]["decides"], row["recovery"]["decision_note"]) == ("Requested", "Branch Manager", None)

    client.post(f"{API}/attendance/recoveries/{rid}/decision", json={"decision": "Approved", "decision_note": "Watch it by Friday", "target_date": "2026-10-16"},
                headers=w.h["ac"])
    recovery = attendance_rows(client, w)["Recent class"]["recovery"]
    assert (recovery["status"], recovery["decision_note"], recovery["target_date"]) == ("Approved", "Watch it by Friday", "2026-10-16")
    assert recovery["decided_at"] is not None


def test_a_correction_request_shows_its_status_decision_and_who_decides(client, w):
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Absent"}])
    assert attendance_rows(client, w)["Recent class"]["correction"] is None

    created = client.post(f"{API}/attendance/corrections", json={"session_id": w.recent.session_id, "enrolment_id": w.e1, "requested_status": "Present",
                                                                 "reason": "I was there"}, headers=w.h["s1"])
    assert created.status_code == 201, created.get_json()
    row = attendance_rows(client, w)["Recent class"]
    assert row["correction_pending"] is True
    assert (row["correction"]["status"], row["correction"]["requested_status"], row["correction"]["decides"]) == ("Pending", "Present", "Branch Manager")

    cid = created.get_json()["data"]["correction_id"]
    rejected = client.post(f"{API}/attendance/corrections/{cid}/decision", json={"decision": "Rejected", "decision_note": "Register shows absent"},
                           headers=w.h["ac"])
    assert rejected.status_code == 200
    row = attendance_rows(client, w)["Recent class"]
    assert row["correction_pending"] is False
    assert (row["correction"]["status"], row["correction"]["decision_note"]) == ("Rejected", "Register shows absent")

    # a later request replaces the earlier one on the row
    again = client.post(f"{API}/attendance/corrections", json={"session_id": w.recent.session_id, "enrolment_id": w.e1, "requested_status": "Late",
                                                               "reason": "Joined late"}, headers=w.h["s1"])
    assert again.status_code == 201
    assert attendance_rows(client, w)["Recent class"]["correction"]["requested_status"] == "Late"


def test_another_student_sees_none_of_it(client, w):
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Absent"}])
    client.post(f"{API}/attendance/corrections", json={"session_id": w.recent.session_id, "enrolment_id": w.e1, "requested_status": "Present",
                                                       "reason": "I was there"}, headers=w.h["s1"])
    assert attendance_rows(client, w, "s2")["Recent class"]["correction"] is None


def test_topics_still_to_finish_and_a_quiet_spell_come_last(client, w):
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Present"}])
    found = steps(client, w.h["s1"])
    assert [s["kind"] for s in found] == ["topics_left", "inactive"]
    assert found[0]["params"] == {"n": 2} and found[1]["params"] == {"days": 14}  # one of the three required topics is covered

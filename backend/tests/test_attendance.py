"""Attendance marking, joining date, locking, corrections and recovery (Module 21)."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from config.database import db
from models import AttendanceRecord, AuditLog, Enrolment, Notification
from tests import attendance_world

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    return attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)


def register(client, w, who, session):
    return client.get(f"{API}/attendance/sessions/{session.session_id}", headers=w.h[who])


def mark(client, w, who, session, body):
    return client.put(f"{API}/attendance/sessions/{session.session_id}", json=body, headers=w.h[who])


def status_of(client, w, session, enrolment_id, who="t1"):
    rows = register(client, w, who, session).get_json()["data"]["rows"]
    row = next(r for r in rows if r["enrolment"]["enrolment_id"] == enrolment_id)
    return row["attendance"]["status"] if row["attendance"] else None


def enrolment(enrolment_id) -> Enrolment:
    db.session.expire_all()
    return db.session.get(Enrolment, enrolment_id)


# ---------------------------------------------------------------- the register and marking

def test_register_lists_allocated_seats_not_yet_marked(client, w):
    data = register(client, w, "t1", w.recent).get_json()["data"]
    assert [r["student"]["full_name"] for r in data["rows"]] == ["Anvitha K.", "Learner Two"]
    assert {r["label"] for r in data["rows"]} == {"Not yet marked"}
    assert data["summary"] == {"seats": 2, "marked": 0, "not_yet_marked": 2, "present": 0, "absent": 0, "late": 0, "excused": 0}
    assert data["can_mark"] is True and data["locked"] is False


def test_mark_all_present_then_exceptions(client, w):
    response = mark(client, w, "t1", w.recent, {"default_status": "Present", "entries": [{"enrolment_id": w.e2, "status": "Absent"}]})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["summary"]["present"] == 1 and data["summary"]["absent"] == 1
    assert status_of(client, w, w.recent, w.e1) == "Present"
    assert status_of(client, w, w.recent, w.e2) == "Absent"
    labels = {r["student"]["full_name"]: r["label"] for r in data["rows"]}
    assert labels == {"Anvitha K.": "Present (trainer-confirmed)", "Learner Two": "Absent"}


def test_default_status_never_overwrites_an_existing_entry(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    mark(client, w, "t1", w.recent, {"default_status": "Present"})
    assert status_of(client, w, w.recent, w.e1) == "Absent"
    assert status_of(client, w, w.recent, w.e2) == "Present"


def test_first_present_sets_joining_date_and_activates_the_enrolment(client, w):
    assert enrolment(w.e1).status == "Allocated — awaiting first regular class" and enrolment(w.e1).joining_date is None
    mark(client, w, "t1", w.older, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}, {"enrolment_id": w.e2, "status": "Excused", "remarks": "Medical"}]})
    assert enrolment(w.e1).joining_date is None  # an absence or an excused entry is not attendance

    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Late"}]})
    e1 = enrolment(w.e1)
    assert e1.status == "Active"
    assert e1.joining_date == w.recent_start.date()
    assert enrolment(w.e2).status == "Allocated — awaiting first regular class"

    actions = db.session.execute(select(AuditLog.action).where(AuditLog.entity_id == e1.enrolment_code)).scalars().all()
    assert "ENROLMENT_JOINED" in actions


def test_joining_date_keeps_the_earliest_present_and_is_not_moved_later(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    later = w.delivered(w.recent_start - timedelta(hours=1), title="Same day")
    mark(client, w, "t1", later, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    assert enrolment(w.e1).joining_date == w.recent_start.date()


def test_marking_is_audited_and_absent_students_are_told(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}, {"enrolment_id": w.e2, "status": "Present"}]})
    audit = db.session.execute(select(AuditLog).where(AuditLog.action == "ATTENDANCE_MARKED")).scalar_one()
    assert audit.entity_id == w.recent.session_code and audit.actor_user_id == w.t1.user_id
    told = db.session.execute(select(Notification).where(Notification.category == "Attendance")).scalars().all()
    assert len(told) == 1 and told[0].title.startswith("Marked absent") and told[0].link == "/attendance"


def test_remarking_before_the_lock_replaces_the_entry(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    assert status_of(client, w, w.recent, w.e1) == "Present"
    assert db.session.execute(select(AttendanceRecord)).scalars().all().__len__() == 1


def test_excused_needs_a_reason(client, w):
    response = mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Excused"}]})
    assert response.status_code == 422
    assert "Excused" in response.get_json()["error"]["message"] or response.get_json()["error"]["details"]


def test_only_live_or_delivered_sessions_can_be_marked(client, w):
    response = mark(client, w, "t1", w.future, {"default_status": "Present"})
    assert response.status_code == 422 and "Live or Delivered" in response.get_json()["error"]["message"]


def test_entries_must_be_seats_of_the_batch(client, w):
    response = mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e3, "status": "Present"}]})
    assert response.status_code == 422
    assert mark(client, w, "t1", w.recent, {"entries": []}).status_code == 400
    duplicate = mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}, {"enrolment_id": w.e1, "status": "Absent"}]})
    assert duplicate.status_code == 400


def test_validation_of_status_values(client, w):
    assert mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Maybe"}]}).status_code == 400
    assert mark(client, w, "t1", w.recent, {"default_status": "Sometimes"}).status_code == 400


# ---------------------------------------------------------------- who may do what

def test_permissions_on_the_register(client, w):
    body = {"default_status": "Present"}
    assert mark(client, w, "t2", w.recent, body).status_code == 404          # trainer of another batch: outside scope
    assert mark(client, w, "ac_v", w.recent, body).status_code == 404        # another branch
    assert mark(client, w, "bm", w.recent, body).status_code == 403          # branch manager is read-only
    assert mark(client, w, "s1", w.recent, body).status_code == 403          # students never mark
    assert register(client, w, "s1", w.recent).status_code == 403
    assert register(client, w, "t2", w.recent).status_code == 404
    assert register(client, w, "bm", w.recent).status_code == 200
    assert mark(client, w, "ac", w.recent, body).status_code == 200          # coordinator oversight
    assert client.get(f"{API}/attendance/sessions/{w.recent.session_id}").status_code == 401


def test_register_sessions_list_follows_scope_and_filters(client, w):
    def codes(who, query=""):
        response = client.get(f"{API}/attendance/sessions{query}", headers=w.h[who])
        assert response.status_code == 200
        return {s["session_code"]: s for s in response.get_json()["data"]}

    assert set(codes("t1")) == {w.recent.session_code, w.older.session_code}   # the future session is not Live or Delivered
    assert codes("t2") == {}
    assert codes("ac_v") == {}
    assert set(codes("bm")) == set(codes("t1"))
    assert codes("t1")[w.recent.session_code]["attendance_state"] == "Not yet marked"

    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    sessions = codes("t1")
    assert sessions[w.recent.session_code]["attendance_state"] == "Partially marked"
    assert sessions[w.older.session_code]["locked"] is True
    assert set(codes("t1", "?attendance=pending")) == {w.recent.session_code}
    assert set(codes("t1", "?attendance=locked")) == {w.older.session_code}
    mark(client, w, "t1", w.recent, {"default_status": "Present"})
    assert codes("t1")[w.recent.session_code]["attendance_state"] == "Marked"
    assert codes("t1", "?attendance=pending") == {}


# ---------------------------------------------------------------- lock and corrections

def test_locked_sessions_cannot_be_marked_directly(client, w):
    response = mark(client, w, "t1", w.older, {"default_status": "Present"})
    assert response.status_code == 422 and "locked" in response.get_json()["error"]["message"]


def test_lock_period_is_a_setting(client, w, run_sql):
    run_sql("UPDATE app_settings SET setting_value = '30' WHERE setting_key = 'attendance_lock_days'")
    assert mark(client, w, "t1", w.older, {"default_status": "Present"}).status_code == 200


def correction(client, w, who, session, enrolment_id, status="Present", reason="Was in class"):
    return client.post(f"{API}/attendance/corrections", json={"session_id": session.session_id, "enrolment_id": enrolment_id,
                                                              "requested_status": status, "reason": reason}, headers=w.h[who])


def decide(client, w, who, correction_id, decision="Approved", note=None):
    return client.post(f"{API}/attendance/corrections/{correction_id}/decision", json={"decision": decision, "decision_note": note}, headers=w.h[who])


def test_correction_after_the_lock_needs_independent_approval(client, w):
    created = correction(client, w, "t1", w.older, w.e1)
    assert created.status_code == 201, created.get_json()
    cid = created.get_json()["data"]["correction_id"]
    assert created.get_json()["data"]["previous_status"] is None
    assert correction(client, w, "t1", w.older, w.e1).status_code == 409           # one pending request per entry

    assert decide(client, w, "t1", cid).status_code == 403                        # a trainer cannot decide
    assert decide(client, w, "s1", cid).status_code == 403
    assert decide(client, w, "ac_v", cid).status_code == 404
    assert decide(client, w, "t1", cid).status_code == 403

    approved = decide(client, w, "ac", cid)
    assert approved.status_code == 200 and approved.get_json()["data"]["status"] == "Approved"
    assert status_of(client, w, w.older, w.e1) == "Present"
    record = db.session.execute(select(AttendanceRecord).where(AttendanceRecord.enrolment_id == w.e1)).scalar_one()
    assert record.corrected_by is not None and record.marked_by == record.corrected_by
    assert enrolment(w.e1).joining_date == w.older_start.date()
    assert decide(client, w, "ac", cid).status_code == 422                        # already decided
    actions = db.session.execute(select(AuditLog.action)).scalars().all()
    assert {"ATTENDANCE_CORRECTION_REQUESTED", "ATTENDANCE_CORRECTION_DECIDED"} <= set(actions)


def test_a_coordinator_cannot_approve_their_own_correction_but_the_manager_can(client, w):
    cid = correction(client, w, "ac", w.older, w.e1, "Absent", "Wrong entry").get_json()["data"]["correction_id"]
    own = decide(client, w, "ac", cid)
    assert own.status_code == 422 and "independent" in own.get_json()["error"]["message"]
    assert decide(client, w, "ac2", cid).status_code == 200


def test_the_person_who_marked_an_entry_cannot_approve_its_correction(client, w):
    mark(client, w, "ac", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    cid = correction(client, w, "s1", w.recent, w.e1, "Present", "I attended").get_json()["data"]["correction_id"]
    assert decide(client, w, "ac", cid).status_code == 422
    assert decide(client, w, "bm", cid).status_code == 200
    assert status_of(client, w, w.recent, w.e1) == "Present"


def test_rejecting_a_correction_needs_a_reason_and_changes_nothing(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    cid = correction(client, w, "s1", w.recent, w.e1).get_json()["data"]["correction_id"]
    assert decide(client, w, "ac", cid, "Rejected").status_code == 400
    assert decide(client, w, "ac", cid, "Rejected", "Register shows absent").status_code == 200
    assert status_of(client, w, w.recent, w.e1) == "Absent"
    told = db.session.execute(select(Notification).where(Notification.title.like("Attendance correction rejected%"))).scalars().all()
    assert len(told) == 1


def test_students_can_only_dispute_their_own_entries(client, w):
    assert correction(client, w, "s1", w.recent, w.e2).status_code == 404
    assert correction(client, w, "s1", w.recent, w.e1).status_code == 201
    listed = client.get(f"{API}/attendance/corrections", headers=w.h["s1"]).get_json()["data"]
    assert [c["student"]["full_name"] for c in listed] == ["Anvitha K."]
    assert client.get(f"{API}/attendance/corrections", headers=w.h["s2"]).get_json()["data"] == []
    assert len(client.get(f"{API}/attendance/corrections?status=Pending", headers=w.h["ac"]).get_json()["data"]) == 1
    assert client.get(f"{API}/attendance/corrections", headers=w.h["ac_v"]).get_json()["data"] == []


def test_a_correction_must_change_something_on_a_held_session(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    assert correction(client, w, "s1", w.recent, w.e1, "Present").status_code == 422
    assert correction(client, w, "s1", w.future, w.e1).status_code == 422


# ---------------------------------------------------------------- recovery

def absent_entry(client, w, session=None, who="t1"):
    session = session or w.recent
    mark(client, w, who, session, {"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    return db.session.execute(select(AttendanceRecord).where(AttendanceRecord.session_id == session.session_id,
                                                              AttendanceRecord.enrolment_id == w.e1)).scalar_one().attendance_id


def request_recovery(client, w, who, attendance_id, method="Recording watched"):
    return client.post(f"{API}/attendance/recoveries", json={"attendance_id": attendance_id, "method": method, "reason": "Was unwell"},
                       headers=w.h[who])


def test_recovery_lifecycle_with_codes_and_label(client, w):
    attendance_id = absent_entry(client, w)
    requested = request_recovery(client, w, "s1", attendance_id)
    assert requested.status_code == 201, requested.get_json()
    recovery = requested.get_json()["data"]
    assert recovery["recovery_code"].startswith("REC-") and recovery["status"] == "Requested"

    rid = recovery["recovery_id"]
    assert request_recovery(client, w, "t1", attendance_id).status_code == 409        # one live recovery per absence
    label = next(r["label"] for r in register(client, w, "t1", w.recent).get_json()["data"]["rows"] if r["enrolment"]["enrolment_id"] == w.e1)
    assert label == f"Absent — recovery requested ({recovery['recovery_code']})"

    decision = client.post(f"{API}/attendance/recoveries/{rid}/decision", json={"decision": "Approved", "target_date": "2026-10-10"}, headers=w.h["ac"])
    assert decision.status_code == 200 and decision.get_json()["data"]["status"] == "Approved"
    mine = client.get(f"{API}/me/attendance", headers=w.h["s1"]).get_json()["data"][0]["rows"]
    assert mine[0]["label"] == f"Absent — recovery approved ({recovery['recovery_code']})"

    assert client.post(f"{API}/attendance/recoveries/{rid}/completion", json={"evidence_note": ""}, headers=w.h["t1"]).status_code == 400
    completed = client.post(f"{API}/attendance/recoveries/{rid}/completion", json={"evidence_note": "Reviewed the lab task"}, headers=w.h["t1"])
    assert completed.status_code == 200 and completed.get_json()["data"]["status"] == "Completed"
    assert client.post(f"{API}/attendance/recoveries/{rid}/completion", json={"evidence_note": "again"}, headers=w.h["t1"]).status_code == 422
    # The original absence is never rewritten
    assert status_of(client, w, w.recent, w.e1) == "Absent"
    actions = set(db.session.execute(select(AuditLog.action)).scalars())
    assert {"RECOVERY_REQUESTED", "RECOVERY_DECIDED", "RECOVERY_COMPLETED"} <= actions


def test_recovery_only_for_absences_and_only_by_people_in_scope(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    present_id = db.session.execute(select(AttendanceRecord.attendance_id)).scalar_one()
    assert request_recovery(client, w, "s1", present_id).status_code == 422

    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e2, "status": "Absent"}]})
    absent_id = db.session.execute(select(AttendanceRecord.attendance_id).where(AttendanceRecord.enrolment_id == w.e2)).scalar_one()
    assert request_recovery(client, w, "s1", absent_id).status_code == 404          # another student's absence
    assert request_recovery(client, w, "t2", absent_id).status_code == 404          # trainer of another batch
    assert request_recovery(client, w, "bm", absent_id).status_code == 403
    assert request_recovery(client, w, "t1", absent_id).status_code == 201


def test_only_the_coordinator_decides_and_rejection_can_be_raised_again(client, w):
    attendance_id = absent_entry(client, w)
    rid = request_recovery(client, w, "s1", attendance_id).get_json()["data"]["recovery_id"]
    url = f"{API}/attendance/recoveries/{rid}/decision"
    assert client.post(url, json={"decision": "Approved"}, headers=w.h["t1"]).status_code == 403
    assert client.post(url, json={"decision": "Approved"}, headers=w.h["s1"]).status_code == 403
    assert client.post(url, json={"decision": "Approved"}, headers=w.h["ac_v"]).status_code == 404
    assert client.post(url, json={"decision": "Rejected"}, headers=w.h["ac"]).status_code == 400
    assert client.post(url, json={"decision": "Rejected", "decision_note": "Not eligible"}, headers=w.h["ac"]).status_code == 200
    assert client.post(url, json={"decision": "Approved"}, headers=w.h["ac"]).status_code == 422
    assert request_recovery(client, w, "s1", attendance_id, "Extra session").status_code == 201


def test_recoveries_list_is_scoped(client, w):
    attendance_id = absent_entry(client, w)
    request_recovery(client, w, "s1", attendance_id)
    assert len(client.get(f"{API}/attendance/recoveries", headers=w.h["s1"]).get_json()["data"]) == 1
    assert client.get(f"{API}/attendance/recoveries", headers=w.h["s2"]).get_json()["data"] == []
    assert len(client.get(f"{API}/attendance/recoveries?status=Requested", headers=w.h["ac"]).get_json()["data"]) == 1
    assert client.get(f"{API}/attendance/recoveries", headers=w.h["ac_v"]).get_json()["data"] == []
    assert client.get(f"{API}/attendance/recoveries", headers=w.h["t2"]).get_json()["data"] == []
    assert len(client.get(f"{API}/attendance/recoveries", headers=w.h["t1"]).get_json()["data"]) == 1


# ---------------------------------------------------------------- the student's view

def test_student_attendance_screen_data(client, w):
    mark(client, w, "t1", w.recent, {"entries": [{"enrolment_id": w.e1, "status": "Present"}]})
    blocks = client.get(f"{API}/me/attendance", headers=w.h["s1"]).get_json()["data"]
    assert len(blocks) == 1 and blocks[0]["enrolment"]["enrolment_id"] == w.e1
    assert blocks[0]["joining_date"] == w.recent_start.date().isoformat()
    assert blocks[0]["rows"][0]["label"] == "Present (trainer-confirmed)"
    assert blocks[0]["summary"]["percent"] == 100.0
    assert client.get(f"{API}/me/attendance", headers=w.h["t1"]).status_code == 403


def test_enrolment_attendance_scope(client, w):
    url = f"{API}/attendance/enrolments/{w.e1}"
    assert client.get(url, headers=w.h["s1"]).status_code == 200
    assert client.get(url, headers=w.h["s2"]).status_code == 404
    assert client.get(url, headers=w.h["t1"]).status_code == 200
    assert client.get(url, headers=w.h["t2"]).status_code == 404
    assert client.get(url, headers=w.h["ac_v"]).status_code == 404

"""Gap fix phase 6: batches and delivery operations (Modules 15 and 16). Lifecycle and the 7-point confirmation, capacity
requests, material changes and agreement, transfers and track batches, merge / split and completion, class logs and purposes,
delayed starts, cover, Meet hosts / incidents / participation, shared classes, slot preferences and the Meet operations view."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from config.database import db
from config.timezone import IST, today_ist
from models import Notification, WhatsappMessage
from services.jobs import JOBS
from tests.test_delivery import call, data, future, iso, world  # noqa: F401

LINK = "https://meet.google.com/abc-defg-hij"


def titles_for(user_id):
    return list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == user_id)).scalars())


def ready_fields(**extra):
    """Everything points 3, 4 and 6 of the readiness record need for a classroom batch."""
    return {"planned_start": future(10).date().isoformat(), "planned_end": future(100).date().isoformat(), "schedule_days": ["Tue", "Thu"],
            "start_time": "15:00", "end_time": "17:00", "location": "Lab 2", "classroom_capacity": 30, "recording_provision": "Not Included",
            **extra}


def confirmed_batch(client, login, people, make_batch, **columns):
    """A confirmed (Starting) Java batch at Guntur led by g1, through proposal and the Branch Manager's confirmation."""
    batch = make_batch(1, trainers=[people["g1"]], **columns)
    data(call(client, login, people["ac"], "patch", f"/batches/{batch.batch_id}", json=ready_fields()), 200)
    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/proposal", json={}), 200)
    data(call(client, login, people["bm"], "post", f"/batches/{batch.batch_id}/confirmation", json={"decision": "Confirmed"}), 200)
    return batch


def seat(client, login, people, batch, student):
    eid = student.enrolments[0]["enrolment_id"]
    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/allocations", json={"enrolment_id": eid, "acknowledge_warnings": True}), 201)
    return eid


# ---------------------------------------------------------------- lifecycle (G015, G062)

def test_proposal_and_confirmation_by_a_branch_manager(world, client, login, make_batch, make_user):
    people, _, _ = world
    batch = make_batch(1, trainers=[people["g1"]])
    bid = batch.batch_id
    blocked = call(client, login, people["ac"], "post", f"/batches/{bid}/proposal", json={})
    assert blocked.status_code == 422 and any("3." in b for b in blocked.get_json()["error"]["details"]["blocking"])

    detail = data(call(client, login, people["ac"], "patch", f"/batches/{bid}", json=ready_fields(
        display_name="Java · Lab 2 · Tue/Thu 3 PM", batch_type="Corporate", schedule_pattern="Weekend")), 200)
    assert (detail["display_name"], detail["batch_type"], detail["schedule_pattern"]) == ("Java · Lab 2 · Tue/Thu 3 PM", "Corporate", "Weekend")
    assert detail["creating_branch"]["branch_id"] == 1 and detail["state_label"] == "Draft"
    readiness = data(call(client, login, people["ac"], "get", f"/batches/{bid}/readiness"), 200)
    assert [c["status"] for c in readiness["checklist"]] == ["pass"] * 6 + ["pending"] and len(readiness["checklist"]) == 7

    # the Branch Manager decides alone: the one who proposes may also return or confirm the batch
    data(call(client, login, people["bm"], "post", f"/batches/{bid}/proposal", json={"note": "Reviewed"}), 200)
    # returned to Draft with a reason, proposed again, confirmed by a Branch Manager
    assert call(client, login, people["admin"], "post", f"/batches/{bid}/confirmation", json={"decision": "Returned"}).status_code == 400  # a Super Admin may decide, but returning needs a reason
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/confirmation", json={"decision": "Returned"}).status_code == 400
    assert data(call(client, login, people["ac"], "post", f"/batches/{bid}/confirmation", json={"decision": "Returned", "note": "Recheck lab"}), 200)["state"] == "Forming"
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/proposal", json={}), 200)
    # editing a proposed batch sends it back to Draft
    assert data(call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"location": "Lab 3"}), 200)["state"] == "Forming"
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/proposal", json={}), 200)
    confirmed = data(call(client, login, people["bm"], "post", f"/batches/{bid}/confirmation", json={"decision": "Confirmed"}), 200)
    assert confirmed["state"] == "Starting" and confirmed["state_label"] == "Confirmed"
    stored = db.session.execute(text("SELECT confirmation_checklist FROM batches WHERE batch_id = :b"), {"b": bid}).scalar_one()
    assert len(stored) == 7 and stored[-1]["status"] == "pass"

    # a room another batch already books at those times is an advisory warning: the Branch Manager records why
    other = make_batch(1, trainers=[people["g2"]])
    data(call(client, login, people["ac"], "patch", f"/batches/{other.batch_id}", json=ready_fields(location="Lab 3")), 200)
    data(call(client, login, people["ac"], "post", f"/batches/{other.batch_id}/proposal", json={}), 200)
    r = call(client, login, people["bm"], "post", f"/batches/{other.batch_id}/confirmation", json={"decision": "Confirmed"})
    assert r.status_code == 422 and r.get_json()["error"]["details"]["warnings"]
    data(call(client, login, people["bm"], "post", f"/batches/{other.batch_id}/confirmation",
              json={"decision": "Confirmed", "override_reason": "Lab 3 has two benches; split timings agreed"}), 200)
    # the same trainer at the same times is impossible, not a warning
    clash = make_batch(1, trainers=[people["g1"]])
    data(call(client, login, people["ac"], "patch", f"/batches/{clash.batch_id}", json=ready_fields(location="Lab 9")), 200)
    r = call(client, login, people["ac"], "post", f"/batches/{clash.batch_id}/proposal", json={})
    assert r.status_code == 422 and "trainer already teaches" in r.get_json()["error"]["message"]


def test_hold_resume_complete_and_archive(world, client, login, make_batch, make_session, allocate, run_sql):
    people, _, student = world
    batch = confirmed_batch(client, login, people, make_batch)
    bid = batch.batch_id
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Running"}), 200)
    assert call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "On Hold"}).status_code == 400
    held = data(call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "On Hold", "reason": "Trainer ill"}), 200)
    assert held["state"] == "On Hold" and held["held_from_state"] == "Running"
    eid = student.enrolments[0]["enrolment_id"]
    r = call(client, login, people["ac"], "post", f"/batches/{bid}/allocations", json={"enrolment_id": eid, "acknowledge_warnings": True})
    assert r.status_code == 422  # no new seats while on hold
    assert data(call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "Resume"}), 200)["state"] == "Running"
    assert call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "Archived"}).status_code == 422

    # completion needs a handover for a student still owed teaching, and a replacement (or waiver) for a cancelled class
    allocate(student, batch)
    gone = make_session(batch, people["g1"], datetime.now(timezone.utc) - timedelta(days=3), state="Cancelled")
    r = call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Completed"})
    blocking = r.get_json()["error"]["details"]["blocking"]
    assert r.status_code == 422 and any("replacement" in b for b in blocking) and any("handover" in b for b in blocking)
    data(call(client, login, people["ac"], "post", f"/class-sessions/{gone.session_id}/replacement-waiver", json={"reason": "Covered in the next class"}), 200)
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/handovers", json={
        "enrolment_id": eid, "owner_user_id": people["ac"].user_id, "plan": "Individual catch-up classes", "destination": "Next Java batch"}), 201)
    assert data(call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Completed"}), 200)["state"] == "Completed"
    # archive only when nobody still studies there
    r = call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "Archived"})
    assert r.status_code == 422 and "still study" in r.get_json()["error"]["message"]
    run_sql("UPDATE enrolments SET status = 'Completed' WHERE enrolment_id = :e", e=eid)
    archived = data(call(client, login, people["bm"], "post", f"/batches/{bid}/state", json={"state": "Archived"}), 200)
    assert archived["state"] == "Archived"
    assert db.session.execute(text("SELECT payload->>'status' FROM batch_crm_state WHERE batch_id = :b"), {"b": bid}).scalar_one() == "Archived"


# ---------------------------------------------------------------- capacity (G103)

def test_capacity_sides_and_reviewed_increases(world, client, login, make_batch):
    people, _, _ = world
    batch = confirmed_batch(client, login, people, make_batch, capacity=20)
    bid = batch.batch_id
    r = call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"classroom_capacity": 10})
    assert r.status_code == 400 and "verified" in r.get_json()["error"]["message"]
    assert call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"capacity": 25}).status_code == 422
    data(call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"capacity": 18}), 200)  # a decrease is direct

    body = {"to_capacity": 28, "classroom_capacity": 28, "resource_validation": "Two more benches installed", "academic_review": "Trainer can handle 28"}
    req = data(call(client, login, people["ac"], "post", f"/batches/{bid}/capacity-requests", json=body), 201)
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/capacity-requests", json=body).status_code == 409
    done = data(call(client, login, people["bm"], "post", f"/batch-capacity-requests/{req['request_id']}/decision", json={"decision": "Approved"}), 200)
    assert done["status"] == "Approved"
    after = data(call(client, login, people["ac"], "get", f"/batches/{bid}"), 200)
    assert (after["capacity"], after["classroom_capacity"]) == (28, 28)


# ---------------------------------------------------------------- material changes (G018)

def test_material_change_needs_each_students_agreement(world, client, login, make_batch, make_student):
    people, _, student = world
    other = make_student()
    batch = confirmed_batch(client, login, people, make_batch)
    bid = batch.batch_id
    first, second = seat(client, login, people, batch, student), seat(client, login, people, batch, other)

    r = call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"start_time": "16:00", "end_time": "18:00"})
    assert r.status_code == 422 and "material change" in r.get_json()["error"]["message"]
    change = data(call(client, login, people["ac"], "post", f"/batches/{bid}/material-changes", json={
        "kind": "Teaching days / times", "proposed_plan": "Tue, Thu 16:00–18:00", "reason": "Lab is booked at 15:00",
        "changes": {"start_time": "16:00", "end_time": "18:00"}, "alternative": "Move to the morning batch"}), 201)
    assert change["status"] == "Pending Approval" and change["response_counts"]["Pending"] == 2
    assert call(client, login, people["ac"], "post", f"/material-changes/{change['change_id']}/decision", json={"decision": "Approved"}).status_code == 422
    assert call(client, login, people["bm"], "post", f"/material-changes/{change['change_id']}/decision", json={"decision": "Approved"}).status_code == 422  # a Branch Manager's own request
    data(call(client, login, people["admin"], "post", f"/material-changes/{change['change_id']}/decision", json={"decision": "Approved"}), 200)
    assert any("agreement is needed" in t for t in titles_for(_user_of(student)))
    queued = db.session.execute(select(WhatsappMessage).where(WhatsappMessage.template_name == "nipuna_lms_batch_change_agreement_u_v1")).scalars().all()
    assert len(queued) == 2 and queued[0].status == "Skipped"  # one per student; WhatsApp ships switched off

    mine = data(call(client, login, student.student_code, "get", "/me/material-changes"), 200)
    assert [m["change_id"] for m in mine] == [change["change_id"]] and mine[0]["my_response"]["response"] == "Pending"
    data(call(client, login, student.student_code, "post", f"/me/material-changes/{change['change_id']}/response", json={"response": "Agreed"}), 200)
    data(call(client, login, other.student_code, "post", f"/me/material-changes/{change['change_id']}/response", json={"response": "Declined"}), 200)
    r = call(client, login, people["ac"], "post", f"/material-changes/{change['change_id']}/apply")
    assert r.status_code == 422 and r.get_json()["error"]["details"]["declined_without_alternative"] == [second]
    assert call(client, login, people["ac"], "post", f"/material-changes/{change['change_id']}/responses",
                json={"enrolment_id": second, "response": "Declined", "note": "Phoned the student"}).status_code == 400
    data(call(client, login, people["ac"], "post", f"/material-changes/{change['change_id']}/responses", json={
        "enrolment_id": second, "response": "Declined", "note": "Phoned the student", "alternative_arranged": "Moves to the morning batch"}), 200)
    applied = data(call(client, login, people["ac"], "post", f"/material-changes/{change['change_id']}/apply"), 200)
    assert applied["status"] == "Applied"
    assert data(call(client, login, people["ac"], "get", f"/batches/{bid}"), 200)["start_time"] == "16:00"
    assert first in [r["enrolment_id"] for r in applied["responses"] if r["response"] == "Agreed"]


def _user_of(student):
    return db.session.execute(text("SELECT user_id FROM users WHERE student_id = :s"), {"s": student.student_id}).scalar_one()


# ---------------------------------------------------------------- transfers and track batches (G016, G017)

def test_track_batches_and_component_placement_at_another_branch(world, client, login, make_batch, make_student, make_user):
    people, _, _ = world
    from repositories import catalog as catalog_repo

    student = make_student(course="NIT-CRS-018", enrolments=[{"course_code": "NIT-CRS-018", "kind": "Combo"}], admission_id="A-TRK")
    eid = student.enrolments[0]["enrolment_id"]
    course = catalog_repo.get_course_by_code("NIT-CRS-018")
    t2 = next(c for c in course.components if c.track_code == "NIT-CRS-018/T2")
    track_id = db.session.execute(text("SELECT enrolment_track_id FROM enrolment_tracks WHERE enrolment_id = :e AND component_id = :c"),
                                  {"e": eid, "c": t2.component_id}).scalar_one()

    created = data(call(client, login, people["ac"], "post", "/batches", json={"course_id": course.course_id, "branch_id": 1, "capacity": 10,
                                                                              "component_id": t2.component_id}), 201)
    assert created["component"]["track_code"] == "NIT-CRS-018/T2"
    tb = created["batch_id"]
    call(client, login, people["ac"], "post", f"/batches/{tb}/trainers", json={"trainer_user_id": people["g1"].user_id, "role": "Lead"})
    whole = call(client, login, people["ac"], "post", f"/batches/{tb}/allocations", json={"enrolment_id": eid})
    assert whole.status_code == 422 and "teaches one track" in whole.get_json()["error"]["message"]
    seat_ = data(call(client, login, people["ac"], "post", f"/batches/{tb}/allocations",
                      json={"enrolment_id": eid, "enrolment_track_id": track_id, "acknowledge_warnings": True}), 201)
    assert seat_["enrolment_track_id"] == track_id

    # the same track placed in a Vijayawada track batch: the destination confirms, then the Guntur Branch Manager approves
    vij = make_batch(2, course_code="NIT-CRS-018", trainers=[people["v1"]], component_id=t2.component_id)
    whole_move = call(client, login, people["ac"], "post", f"/enrolments/{eid}/transfer-requests", json={"to_batch_id": vij.batch_id, "reason": "Timing"})
    assert whole_move.status_code == 422 or whole_move.status_code == 404
    req = data(call(client, login, people["ac"], "post", f"/enrolments/{eid}/transfer-requests", json={
        "to_batch_id": vij.batch_id, "enrolment_track_id": track_id, "reason": "Evening slot only in Vijayawada", "acknowledge_warnings": True}), 201)
    assert req["interbranch"] and req["from_batch"]["batch_id"] == tb
    r = call(client, login, people["bm"], "post", f"/batch-transfer-requests/{req['request_id']}/decision", json={"decision": "Approved"})
    assert r.status_code == 422 and "destination" in r.get_json()["error"]["message"]
    assert call(client, login, people["ac"], "post", f"/batch-transfer-requests/{req['request_id']}/destination", json={"decision": "Confirmed"}).status_code == 403
    data(call(client, login, people["ac_vij"], "post", f"/batch-transfer-requests/{req['request_id']}/destination", json={"decision": "Confirmed"}), 200)
    data(call(client, login, people["bm"], "post", f"/batch-transfer-requests/{req['request_id']}/decision", json={"decision": "Approved"}), 200)
    seats = db.session.execute(text("SELECT batch_id, status FROM batch_allocations WHERE enrolment_id = :e ORDER BY allocation_id"), {"e": eid}).all()
    assert [(b, s) for b, s in seats] == [(tb, "Transferred"), (vij.batch_id, "Active")]
    # the admission stays at Guntur
    assert db.session.execute(text("SELECT service_branch_id FROM enrolments WHERE enrolment_id = :e"), {"e": eid}).scalar_one() == 1


def test_a_transfer_is_decided_by_a_branch_manager_alone_and_rejection_needs_a_reason(world, client, login, make_batch):
    people, _, student = world
    a = make_batch(1, trainers=[people["g1"]], state="Running")
    b = make_batch(1, trainers=[people["g2"]], state="Running")
    eid = seat(client, login, people, a, student)
    req = data(call(client, login, people["bm"], "post", f"/enrolments/{eid}/transfer-requests", json={"to_batch_id": b.batch_id, "reason": "x"}), 201)
    assert call(client, login, people["admin"], "post", f"/batch-transfer-requests/{req['request_id']}/decision", json={"decision": "Rejected"}).status_code == 400
    assert data(call(client, login, people["admin"], "post", f"/batch-transfer-requests/{req['request_id']}/decision",
                     json={"decision": "Rejected", "note": "Batch B is full next month"}), 200)["status"] == "Rejected"


# ---------------------------------------------------------------- merge / split (G069)

def test_split_and_merge_of_a_branch_managers_request_go_to_an_admin_and_need_a_matching_plan(world, client, login, make_batch, make_student):
    people, _, student = world
    other = make_student()
    source = make_batch(1, trainers=[people["g1"]], state="Running", schedule_days=[2, 4],
                        start_time=datetime.strptime("15:00", "%H:%M").time(), end_time=datetime.strptime("17:00", "%H:%M").time())
    same = make_batch(1, trainers=[people["g2"]], state="Running", schedule_days=[2, 4],
                      start_time=datetime.strptime("15:00", "%H:%M").time(), end_time=datetime.strptime("17:00", "%H:%M").time())
    morning = make_batch(1, trainers=[people["g2"]], state="Running", schedule_days=[1, 3],
                         start_time=datetime.strptime("09:00", "%H:%M").time(), end_time=datetime.strptime("11:00", "%H:%M").time())
    first, second = seat(client, login, people, source, student), seat(client, login, people, source, other)
    body = {"kind": "Split", "from_batch_id": source.batch_id, "to_batch_id": same.batch_id, "enrolment_ids": [second],
            "effective_from": today_ist().isoformat(), "reason": "Too many in one lab", "academic_review": "Same version and progress"}
    split = data(call(client, login, people["ac"], "post", "/batch-successions", json=body), 201)
    assert call(client, login, people["ac"], "post", f"/batch-successions/{split['succession_id']}/decision", json={"decision": "Approved"}).status_code == 422
    assert call(client, login, people["bm"], "post", f"/batch-successions/{split['succession_id']}/decision", json={"decision": "Approved"}).status_code == 422  # a Branch Manager's own request
    done = data(call(client, login, people["admin"], "post", f"/batch-successions/{split['succession_id']}/decision", json={"decision": "Approved"}), 200)
    assert done["moved_count"] == 1
    assert db.session.execute(text("SELECT batch_id FROM batch_allocations WHERE enrolment_id = :e AND status = 'Active'"), {"e": second}).scalar_one() == same.batch_id

    merge = data(call(client, login, people["ac"], "post", "/batch-successions", json={**body, "kind": "Merge", "to_batch_id": morning.batch_id, "enrolment_ids": []}), 201)
    r = call(client, login, people["admin"], "post", f"/batch-successions/{merge['succession_id']}/decision", json={"decision": "Approved"})
    assert r.status_code == 422 and "material change" in r.get_json()["error"]["message"]
    history = data(call(client, login, people["ac"], "get", f"/batches/{source.batch_id}"), 200)
    assert {s["kind"] for s in history["successions"]} == {"Split", "Merge"}
    assert first  # the remaining student stays until their agreement to the morning timetable is recorded


# ---------------------------------------------------------------- class states, logs and purposes (G065, G066, G068)

def test_class_log_partially_held_and_original_slot(world, client, login):
    people, batch, _ = world
    soon = datetime.now(IST) + timedelta(minutes=20)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Streams",
                                                                                "starts_at": iso(soon), "ends_at": iso(soon + timedelta(minutes=90))}), 201)[0]["session_id"]
    assert data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/start"), 200)["state_label"] == "In Progress"
    r = call(client, login, people["g1"], "post", f"/class-sessions/{sid}/deliver", json={"outcome": "Partially Held"})
    assert r.status_code == 400
    start = datetime.now(IST) - timedelta(minutes=50)
    done = data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/deliver", json={
        "outcome": "Partially Held", "actual_start": iso(start), "actual_end": iso(start + timedelta(minutes=45)), "break_minutes": 5,
        "unfulfilled_note": "Collectors not covered"}), 200)
    assert done["state_label"] == "Partially Held" and done["delivered_minutes"] == 40 and done["planned_minutes"] == 90
    # a replacement for the unfulfilled part, proposed by the coordinator and approved by the Branch Manager
    later = future(4)
    body = {"batch_id": batch.batch_id, "title": "Streams (rest)", "purpose": "Replacement", "replaces_session_id": sid,
            "starts_at": iso(later), "ends_at": iso(later + timedelta(hours=1))}
    assert call(client, login, people["ac"], "post", "/class-sessions", json=body).status_code == 400  # owner and deadline
    rep = data(call(client, login, people["ac"], "post", "/class-sessions", json={**body, "owner_user_id": people["ac"].user_id,
                                                                                "due_on": future(5).date().isoformat()}), 201)[0]
    assert rep["approval_status"] == "Pending" and rep["replaces_session_id"] == sid
    assert call(client, login, people["g1"], "post", f"/class-sessions/{rep['session_id']}/start").status_code == 422
    assert data(call(client, login, people["bm"], "post", f"/class-sessions/{rep['session_id']}/approval", json={"decision": "Approved"}), 200)["approval_status"] == "Approved"

    # a reschedule keeps the original slot; inside 24 hours it needs the emergency reason and next action
    near = datetime.now(IST) + timedelta(hours=5)
    nid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Near",
                                                                                "starts_at": iso(near), "ends_at": iso(near + timedelta(hours=1))}), 201)[0]["session_id"]
    move = {"starts_at": iso(near + timedelta(days=1)), "ends_at": iso(near + timedelta(days=1, hours=1)), "reason": "Power cut"}
    assert call(client, login, people["ac"], "post", f"/class-sessions/{nid}/reschedule", json=move).status_code == 400
    moved = data(call(client, login, people["ac"], "post", f"/class-sessions/{nid}/reschedule",
                      json={**move, "emergency_reason": "Grid failure since morning", "next_action": "Class moves to tomorrow"}), 200)
    assert moved["original_starts_at"] != moved["starts_at"] and moved["state_label"] == "Rescheduled"
    change = data(call(client, login, people["ac"], "get", f"/class-sessions/{nid}"), 200)["changes"][0]
    assert change["short_notice"] and change["next_action"] == "Class moves to tomorrow"


def test_room_and_student_clashes_need_the_branch_managers_reason(world, client, login, make_batch, allocate, make_session):
    people, batch, student = world
    allocate(student, batch)
    other = make_batch(1, trainers=[people["g2"]], state="Running")
    when = future(5)
    data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "A", "room": "Lab 1",
                                                                         "starts_at": iso(when), "ends_at": iso(when + timedelta(hours=1))}), 201)
    body = {"batch_id": other.batch_id, "title": "B", "room": "Lab 1", "starts_at": iso(when), "ends_at": iso(when + timedelta(hours=1))}
    r = call(client, login, people["ac"], "post", "/class-sessions", json=body)
    assert r.status_code == 422 and "Lab 1" in r.get_json()["error"]["message"]
    made = data(call(client, login, people["bm"], "post", "/class-sessions", json={**body, "override_reason": "Lab 1 seats both groups"}), 201)[0]
    assert made["room_override_reason"] == "Lab 1 seats both groups"



def test_student_timetable_clash_across_a_combos_track_batch(world, client, login, make_batch, make_student, make_session):
    """A combo student seated in the combo batch and, for the booster, in a separate booster batch."""
    people, _, _ = world
    from models import BatchAllocation
    from repositories import catalog as catalog_repo

    student = make_student(course="NIT-CRS-018", enrolments=[{"course_code": "NIT-CRS-018", "kind": "Combo"}], admission_id="A-CLASH")
    eid = student.enrolments[0]["enrolment_id"]
    combo = make_batch(1, course_code="NIT-CRS-018", trainers=[people["g1"]], state="Running")
    booster = make_batch(1, course_code="NIT-CRS-019", trainers=[people["g2"]], state="Running")
    booster_track = db.session.execute(text("SELECT t.enrolment_track_id FROM enrolment_tracks t JOIN course_components c USING (component_id) "
                                            "WHERE t.enrolment_id = :e AND c.track_code = 'NIT-CRS-019'"), {"e": eid}).scalar_one()
    db.session.add_all([BatchAllocation(enrolment_id=eid, batch_id=combo.batch_id),
                        BatchAllocation(enrolment_id=eid, enrolment_track_id=booster_track, batch_id=booster.batch_id)])
    db.session.commit()
    when = future(6)
    make_session(booster, people["g2"], when, title="Booster lab")
    body = {"batch_id": combo.batch_id, "title": "Combo class", "starts_at": iso(when), "ends_at": iso(when + timedelta(hours=1))}
    r = call(client, login, people["ac"], "post", "/class-sessions", json=body)
    assert r.status_code == 422 and "Students of this class also attend" in r.get_json()["error"]["message"]
    data(call(client, login, people["bm"], "post", "/class-sessions", json={**body, "override_reason": "Booster moved online for that week"}), 201)
    assert catalog_repo.get_course_by_code("NIT-CRS-019") is not None


# ---------------------------------------------------------------- delayed starts and missing logs (G019, G065)

def test_delay_job_tells_students_then_records_a_disruption(world, client, login, allocate, make_session):
    people, batch, student = world
    allocate(student, batch)
    late = make_session(batch, people["g1"], datetime.now(timezone.utc) - timedelta(minutes=7), title="Late class", mode="Live Online",
                        meet_status="Pending Verification")
    assert JOBS["session-delay-check"]() == {"students_told": 1, "disruptions": 0}
    assert any("running late" in t for t in titles_for(_user_of(student)))
    db.session.execute(text("UPDATE class_sessions SET starts_at = starts_at - interval '10 minutes', ends_at = ends_at - interval '10 minutes' "
                            "WHERE session_id = :s"), {"s": late.session_id})
    db.session.commit()
    assert JOBS["session-delay-check"]() == {"students_told": 0, "disruptions": 1}
    assert JOBS["session-delay-check"]() == {"students_told": 0, "disruptions": 0}  # once per class
    queue = data(call(client, login, people["ac"], "get", "/exceptions?source=DISRUPTION"), 200)
    assert [q["reference"] for q in queue] == [late.session_code]

    disruption = data(call(client, login, people["ac"], "get", "/session-disruptions?status=Open"), 200)[0]
    assert call(client, login, people["ac"], "post", f"/session-disruptions/{disruption['disruption_id']}/resolve", json={"recovery_plan": "x"}).status_code == 400
    resolved = data(call(client, login, people["ac"], "post", f"/session-disruptions/{disruption['disruption_id']}/resolve", json={
        "recovery_plan": "Replacement on Saturday", "undelivered_minutes": 120, "cause": "Provider"}), 200)
    assert resolved["status"] == "Resolved" and resolved["undelivered_minutes"] == 120
    assert any("Recovery plan" in t for t in titles_for(_user_of(student)))
    assert data(call(client, login, people["ac"], "get", "/exceptions?source=DISRUPTION"), 200) == []


def test_class_log_check_flags_unlogged_classes_once(world, client, login, make_session):
    people, batch, _ = world
    yesterday = datetime.now(timezone.utc) - timedelta(days=1, hours=2)
    s = make_session(batch, people["g1"], yesterday, title="Unlogged")
    make_session(batch, people["g1"], yesterday - timedelta(hours=3), title="Logged", state="Delivered", delivered_at=yesterday)
    assert JOBS["class-log-check"]() == {"flagged": 1}
    assert JOBS["class-log-check"]() == {"flagged": 0}
    assert [q["reference"] for q in data(call(client, login, people["ac"], "get", "/exceptions?source=CLASS_LOG"), 200)] == [s.session_code]
    assert any("Class log missing" in t for t in titles_for(people["ac"].user_id))


# ---------------------------------------------------------------- cover (G101)

def test_substitute_cover_is_approved_verified_then_applied(world, client, login, make_user, allocate):
    people, batch, student = world
    allocate(student, batch)
    outsider = make_user(roles=[("TRAINER", 1)], full_name="Trainer Cover")  # not assigned to the batch
    start = future(3)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Cover me",
                                                                                "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}), 201)[0]["session_id"]
    req = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/cover-requests", json={
        "cover_role": "Substitute", "cover_user_id": outsider.user_id, "reason": "Lead on leave", "scope": "Teach the planned topic only",
        "handover": "Slides shared; attendance on the register"}), 201)
    assert call(client, login, outsider.email, "get", f"/class-sessions/{sid}").status_code == 404
    data(call(client, login, people["ac"], "post", f"/session-cover-requests/{req['request_id']}/verification", json={"note": "Taught Java before"}), 200)
    assert call(client, login, people["ac"], "post", f"/session-cover-requests/{req['request_id']}/decision", json={"decision": "Approved"}).status_code == 422
    assert call(client, login, people["bm"], "post", f"/session-cover-requests/{req['request_id']}/decision", json={"decision": "Approved"}).status_code == 422  # a Branch Manager's own request
    applied = data(call(client, login, people["admin"], "post", f"/session-cover-requests/{req['request_id']}/decision", json={"decision": "Approved"}), 200)
    assert applied["status"] == "Applied"
    session = data(call(client, login, outsider.email, "get", f"/class-sessions/{sid}"), 200)
    assert session["trainer"]["full_name"] == "Trainer Cover" and session["changes"][-1]["change_type"] == "Trainer changed"
    assert any("Trainer change" in t for t in titles_for(_user_of(student)))


# ---------------------------------------------------------------- Meet (G070, G071, G104)

def test_online_class_confirmation_hosts_incidents_and_participation(world, client, login, make_batch, allocate):
    people, batch, student = world
    allocate(student, batch)
    start = future(3)
    body = {"batch_id": batch.batch_id, "title": "Online", "mode": "Live Online", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json=body), 201)[0]["session_id"]
    r = call(client, login, people["ac"], "post", f"/class-sessions/{sid}/confirm")
    assert r.status_code == 422 and "Meet link" in r.get_json()["error"]["message"] and "backup" in r.get_json()["error"]["message"]
    linked = data(call(client, login, people["ac"], "put", f"/class-sessions/{sid}/meet", json={"meet_link": LINK, "meet_space_id": "spaces/abc",
                                                                                             "calendar_event_id": "evt-1"}), 200)
    assert linked["meet_space_id"] == "spaces/abc" and linked["hosting_branch_id"] == 1
    # one link never serves another batch
    other = make_batch(1, trainers=[people["g2"]], state="Running")
    oid = data(call(client, login, people["ac"], "post", "/class-sessions", json={**body, "batch_id": other.batch_id, "starts_at": iso(start + timedelta(days=1)),
                                                                                "ends_at": iso(start + timedelta(days=1, hours=1))}), 201)[0]["session_id"]
    assert call(client, login, people["ac"], "put", f"/class-sessions/{oid}/meet", json={"meet_link": LINK}).status_code == 422

    data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/people", json={"role": "Backup", "user_id": people["g2"].user_id}), 201)
    assert data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/confirm"), 200)["state_label"] == "Confirmed"
    guest = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/people", json={
        "role": "Guest", "guest_name": "Industry mentor", "purpose": "Talk on careers", "student_agreement": "Asked in class"}), 201)
    assert guest["status"] == "Pending"
    assert call(client, login, people["ac"], "post", f"/session-people/{guest['session_person_id']}/decision", json={"decision": "Approved"}).status_code == 422
    data(call(client, login, people["admin"], "post", f"/session-people/{guest['session_person_id']}/decision", json={"decision": "Approved"}), 200)

    incident = data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/meet-incidents", json={
        "kind": "Compromised link", "description": "Link posted publicly", "actions_taken": "Ended the meeting", "replace_link": True}), 201)
    assert incident["link_replaced"] and incident["old_meet_link"] == LINK and incident["participants_notified_at"]
    after = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert after["meet_status"] == "Pending Verification" and after["state_label"] == "Planned"
    assert any("New class link" in t for t in titles_for(_user_of(student)))

    rows = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/participation", json={"entries": [
        {"participant_email": student.email, "joined_at": iso(start), "left_at": iso(start + timedelta(minutes=50))},
        {"participant_name": "Unknown device", "joined_at": iso(start)}]}), 201)
    assert [r["match_status"] for r in rows] == ["Matched", "Unmatched"] and rows[0]["matched_enrolment_id"]
    assert db.session.execute(text("SELECT count(*) FROM attendance_records WHERE session_id = :s"), {"s": sid}).scalar_one() == 0
    unmatched = data(call(client, login, people["ac"], "get", "/meet-participation/unmatched"), 200)
    assert [u["participant_name"] for u in unmatched] == ["Unknown device"]
    data(call(client, login, people["ac"], "post", f"/meet-participation/{unmatched[0]['participation_id']}/review",
              json={"match_status": "Dismissed", "note": "Projector account"}), 200)
    ops = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}/operations"), 200)
    assert len(ops["incidents"]) == 1 and {p["role"] for p in ops["people"]} == {"Backup", "Guest"}


# ---------------------------------------------------------------- shared classes (G067)

def test_shared_class_counts_once_and_reaches_both_batches(world, client, login, make_batch, make_student, allocate, run_sql):
    people, batch, student = world
    other_student = make_student()
    allocate(student, batch)
    joined = make_batch(1, trainers=[people["g2"]], state="Running")
    allocate(other_student, joined)
    soon = datetime.now(IST) + timedelta(minutes=30)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Shared intro",
                                                                                "starts_at": iso(soon), "ends_at": iso(soon + timedelta(hours=1))}), 201)[0]["session_id"]
    assert call(client, login, other_student.student_code, "get", f"/class-sessions/{sid}").status_code == 404
    assert call(client, login, people["g1"], "post", f"/class-sessions/{sid}/rosters", json={"batch_id": joined.batch_id, "coverage_note": "x"}).status_code == 403
    data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/rosters", json={
        "batch_id": joined.batch_id, "coverage_note": "Same introduction topic in both curricula"}), 201)
    assert call(client, login, other_student.student_code, "get", f"/class-sessions/{sid}").status_code == 200
    data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/start"), 200)
    data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/deliver", json={}), 200)
    register = data(call(client, login, people["g1"], "get", f"/attendance/sessions/{sid}"), 200)
    assert len(register["rows"]) == 2
    data(call(client, login, people["g1"], "put", f"/attendance/sessions/{sid}", json={"default_status": "Present"}), 200)
    counted = run_sql("SELECT enrolment_id, delivered_since_joining, present_count FROM enrolment_attendance WHERE enrolment_id IN (:a, :b)",
                      a=student.enrolments[0]["enrolment_id"], b=other_student.enrolments[0]["enrolment_id"]).all()
    assert sorted((d, p) for _, d, p in counted) == [(1, 1), (1, 1)]
    assert db.session.execute(text("SELECT count(*) FROM class_sessions WHERE title = 'Shared intro'")).scalar_one() == 1


# ---------------------------------------------------------------- slot preferences (G102)

def test_slot_preference_reserves_nothing_until_a_seat(world, client, login, make_batch):
    people, _, student = world
    good = make_batch(1, trainers=[people["g2"]], state="Running")
    eid = student.enrolments[0]["enrolment_id"]
    options = data(call(client, login, student.student_code, "get", f"/me/slot-options?enrolment_id={eid}"), 200)
    assert good.batch_id in [o["batch_id"] for o in options]
    pref = data(call(client, login, student.student_code, "post", "/me/slot-preferences", json={
        "enrolment_id": eid, "batch_id": good.batch_id, "preferred_days": ["Sat", "Sun"], "preferred_start": "10:00", "preferred_end": "12:00"}), 201)
    assert pref["status"] == "Requested" and pref["reserves_seat"] is False
    assert call(client, login, student.student_code, "post", "/me/slot-preferences", json={"enrolment_id": eid, "preferred_days": ["Mon"]}).status_code == 409
    assert call(client, login, people["ac"], "patch", f"/slot-preferences/{pref['preference_id']}", json={"status": "Confirmed"}).status_code == 422
    assert data(call(client, login, people["ac"], "patch", f"/slot-preferences/{pref['preference_id']}", json={"status": "Waitlisted"}), 200)["status"] == "Waitlisted"
    seat(client, login, people, good, student)
    assert data(call(client, login, student.student_code, "get", "/me/slot-preferences"), 200)[0]["status"] == "Confirmed"


# ---------------------------------------------------------------- the Meet operations view (G072)

def test_meet_operations_view(world, client, login, make_session, run_sql):
    people, batch, _ = world
    today = datetime.now(IST).replace(hour=23, minute=0, second=0, microsecond=0)
    make_session(batch, people["g1"], today, title="Tonight", mode="Live Online", meet_status="Pending Verification")
    run_sql("INSERT INTO job_runs (job_name, last_started_at, last_finished_at, last_ok_at) VALUES ('session-delay-check', now(), now(), now())")
    view = data(call(client, login, people["ac"], "get", "/meet-operations"), 200)
    tonight = next(s for s in view["sessions"] if s["title"] == "Tonight")
    assert tonight["link_ready"] is False and tonight["host_ready"] is False and view["summary"]["online_not_ready"] >= 1
    runs = {r["job_name"]: r for r in view["last_runs"]}
    assert runs["session-delay-check"]["last_ok_at"] and runs["class-log-check"]["last_ok_at"] is None
    assert call(client, login, people["g1"], "get", "/meet-operations").status_code == 200  # a trainer sees their own batches
    student = db.session.execute(text("SELECT student_code FROM students LIMIT 1")).scalar_one()
    assert call(client, login, student, "get", "/meet-operations").status_code == 403


def test_no_missing_recording_alert_when_the_batch_promises_none(world, make_batch, make_session):
    people, batch, _ = world
    unpromised = make_batch(1, trainers=[people["g2"]], state="Running", recording_provision="Not Included")
    ended = datetime.now(timezone.utc) - timedelta(days=2)
    promised_class = make_session(batch, people["g1"], ended, title="Promised", state="Delivered", delivered_at=ended)
    make_session(unpromised, people["g2"], ended, title="Unpromised", state="Delivered", delivered_at=ended)
    JOBS["recording-check"]()
    flagged = db.session.execute(text("SELECT session_id FROM recording_exceptions")).scalars().all()
    assert flagged == [promised_class.session_id]

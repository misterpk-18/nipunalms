"""S1 Delivery: curriculum, batches, allocation, class sessions, Meet association, student course views."""
from datetime import datetime, timedelta

import pytest

from config.timezone import IST

API = "/api/v1"


def future(days=2, hour=10):
    """A class time `days` from now, on the hour, IST."""
    day = (datetime.now(IST) + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return day


def iso(dt):
    return dt.isoformat()


@pytest.fixture
def world(make_user, make_batch, make_student, catalog):
    people = {
        "g1": make_user(roles=[("TRAINER", 1)], full_name="Trainer G1"),
        "g2": make_user(roles=[("TRAINER", 1)], full_name="Trainer G2"),
        "v1": make_user(roles=[("TRAINER", 2)], full_name="Trainer V1"),
        "ac": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur"),
        "ac2": make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur 2"),
        "ac_vij": make_user(roles=[("ACADEMIC_COORDINATOR", 2)]),
        "bm": make_user(roles=[("BRANCH_MANAGER", 1)]),
        "admin": make_user(roles=[("SUPER_ADMIN", None)]),
        "founder": make_user(roles=[("FOUNDER_CEO", None)]),
    }
    batch = make_batch(1, trainers=[people["g1"]], state="Running", curriculum_version_id=None)
    student = make_student()
    return people, batch, student


def call(client, login, who, method, path, **kwargs):
    headers = login(who.email if hasattr(who, "email") else who)
    return getattr(client, method)(f"{API}{path}", headers=headers, **kwargs)


def data(response, status=None):
    if status is not None:
        assert response.status_code == status, response.get_json()
    return response.get_json().get("data")


# ---------------------------------------------------------------- curriculum

def test_curriculum_review_path_and_independent_approval(world, client, login):
    people, _, _ = world
    course_id = client.get(f"{API}/reference/courses", headers=login(people["ac"].email)).get_json()["data"]
    course_id = next(c["course_id"] for c in course_id if c["course_code"] == "NIT-CRS-052")

    version = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id, "version_label": "CV 3.0"}), 201)
    vid = version["curriculum_version_id"]
    assert version["status"] == "Draft"
    # An empty draft cannot be submitted
    assert call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit").status_code == 422

    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/modules", json={"title": "Basics"}), 201)
    t1 = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "Syntax"}), 201)
    t2 = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "Loops", "is_required": False}), 201)
    # Move Loops to first place: positions renumber 1..n
    data(call(client, login, people["ac"], "patch", f"/curriculum-topics/{t2['topic_id']}", json={"position": 1}), 200)
    detail = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)
    assert [t["title"] for t in detail["modules"][0]["topics"]] == ["Loops", "Syntax"]
    assert t1["sort_order"] == 1

    data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit"), 200)
    # Published content is frozen; the submitter cannot approve
    assert call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "x"}).status_code == 422
    assert call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/approve").status_code == 422
    assert call(client, login, people["bm"], "post", f"/curriculum-versions/{vid}/approve").status_code == 403
    data(call(client, login, people["ac2"], "post", f"/curriculum-versions/{vid}/approve"), 200)
    assert call(client, login, people["ac2"], "post", f"/curriculum-versions/{vid}/approve").status_code == 422


def test_activation_maps_waiting_enrolments_and_batches(world, client, login, make_student, make_batch, run_sql):
    people, _, _ = world
    waiting = make_student(course="NIT-CRS-052", admission_id="A-052")
    assert waiting.enrolments[0]["status"] == "Curriculum Mapping Pending"
    from repositories import catalog as catalog_repo

    course = catalog_repo.get_course_by_code("NIT-CRS-052")
    blocked = make_batch(1, course_code="NIT-CRS-052", trainers=[people["g2"]], readiness="Blocked",
                         readiness_reason="Curriculum Mapping Pending: NIT-CRS-052 has no Active curriculum version", recovery_owner="AC")

    vid = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course.course_id, "version_label": "CV 1.0"}), 201)["curriculum_version_id"]
    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/modules", json={"title": "M"}), 201)
    call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "T"})
    call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit")
    call(client, login, people["ac2"], "post", f"/curriculum-versions/{vid}/approve")
    result = data(call(client, login, people["ac2"], "post", f"/curriculum-versions/{vid}/activate"), 200)

    assert result["status"] == "Active"
    assert result["released"] == {"enrolments_released": 1, "batches_mapped": 1}
    student = data(call(client, login, waiting.student_code, "get", "/me/enrolments"), 200)
    assert student[0]["status"] == "Allocation Pending"
    assert student[0]["curriculum_version"]["version_label"] == "CV 1.0"
    detail = data(call(client, login, people["ac"], "get", f"/batches/{blocked.batch_id}"), 200)
    assert detail["readiness"] != "Blocked"
    assert any(e["event_type"] == "Curriculum mapped" for e in detail["history"])


def test_activation_retires_previous_active_version(world, client, login):
    people, _, _ = world
    overview = data(call(client, login, people["ac"], "get", "/curriculum/overview"), 200)
    java = next(r for r in overview if r["course"]["course_code"] == "NIT-CRS-047")
    old = java["active_version"]["curriculum_version_id"]
    new = data(call(client, login, people["ac"], "post", "/curriculum-versions",
                    json={"course_id": java["course"]["course_id"], "version_label": "CV 6.0", "copy_from_version_id": old}), 201)
    # copying an empty version gives an empty draft; add content and go through review
    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{new['curriculum_version_id']}/modules", json={"title": "M"}), 201)
    call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "T"})
    for who, action in (("ac", "submit"), ("ac2", "approve"), ("ac2", "activate")):
        assert call(client, login, people[who], "post", f"/curriculum-versions/{new['curriculum_version_id']}/{action}").status_code == 200
    versions = data(call(client, login, people["ac"], "get", f"/curriculum-versions?course_id={java['course']['course_id']}"), 200)
    assert {v["version_label"]: v["status"] for v in versions}["CV 5.1"] == "Retired"
    assert {v["version_label"]: v["status"] for v in versions}["CV 6.0"] == "Active"


def test_curriculum_writes_are_role_limited(world, client, login):
    people, _, student = world
    assert call(client, login, people["g1"], "post", "/curriculum-versions", json={"course_id": 1, "version_label": "x"}).status_code == 403
    assert call(client, login, student.student_code, "get", "/curriculum/overview").status_code == 403


# ---------------------------------------------------------------- batches

def test_batch_create_update_state_and_readiness(world, client, login):
    people, _, _ = world
    from repositories import catalog as catalog_repo

    course = catalog_repo.get_course_by_code("NIT-CRS-047")
    created = data(call(client, login, people["ac"], "post", "/batches", json={"course_id": course.course_id, "branch_id": 1, "capacity": 3, "mode": "Live Online"}), 201)
    assert created["state"] == "Forming" and created["curriculum_version"]["version_label"] == "CV 5.1"
    assert created["readiness"] == "Blocked"  # no lead trainer yet
    bid = created["batch_id"]

    # other branch's coordinator cannot create at Guntur, nor touch the batch
    assert call(client, login, people["ac_vij"], "post", "/batches", json={"course_id": course.course_id, "branch_id": 1, "capacity": 3}).status_code == 403
    assert call(client, login, people["ac_vij"], "patch", f"/batches/{bid}", json={"capacity": 5}).status_code == 404
    assert call(client, login, people["g1"], "patch", f"/batches/{bid}", json={"capacity": 5}).status_code == 403

    # cannot start without a lead trainer; trainer must be a Guntur trainer
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Starting"}).status_code == 422
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/trainers", json={"trainer_user_id": people["v1"].user_id, "role": "Lead"}).status_code == 422
    lead = data(call(client, login, people["ac"], "post", f"/batches/{bid}/trainers", json={"trainer_user_id": people["g1"].user_id, "role": "Lead"}), 201)
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/trainers", json={"trainer_user_id": people["g2"].user_id, "role": "Lead"}).status_code == 422
    co = data(call(client, login, people["ac"], "post", f"/batches/{bid}/trainers", json={"trainer_user_id": people["g2"].user_id}), 201)
    # promoting the co-trainer demotes the lead
    data(call(client, login, people["ac"], "patch", f"/batches/{bid}/trainers/{co['batch_trainer_id']}", json={"role": "Lead"}), 200)
    detail = data(call(client, login, people["ac"], "get", f"/batches/{bid}"), 200)
    assert {t["full_name"]: t["role"] for t in detail["trainers"]} == {"Trainer G1": "Co-trainer", "Trainer G2": "Lead"}
    data(call(client, login, people["ac"], "delete", f"/batches/{bid}/trainers/{lead['batch_trainer_id']}"), 200)

    readiness = data(call(client, login, people["ac"], "get", f"/batches/{bid}/readiness"), 200)
    assert readiness["suggested"]["readiness"] == "Pending Verification"  # Live Online, Meet not verified
    assert call(client, login, people["ac"], "patch", f"/batches/{bid}/readiness", json={"readiness": "Blocked", "readiness_reason": "x"}).status_code == 400
    data(call(client, login, people["ac"], "patch", f"/batches/{bid}/readiness", json={"readiness": "Ready"}), 200)

    data(call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Starting"}), 200)
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Running"}), 200)
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Starting"}).status_code == 422
    assert call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Cancelled"}).status_code == 400  # reason required
    data(call(client, login, people["ac"], "post", f"/batches/{bid}/state", json={"state": "Completed"}), 200)
    assert call(client, login, people["ac"], "patch", f"/batches/{bid}", json={"capacity": 9}).status_code == 422


def test_batch_cannot_be_cancelled_with_students_or_completed_with_open_sessions(world, client, login, allocate, make_session):
    people, batch, student = world
    allocate(student, batch)
    r = call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/state", json={"state": "Cancelled", "reason": "no demand"})
    assert r.status_code == 422 and "allocated" in r.get_json()["error"]["message"]
    make_session(batch, people["g1"], future(3))
    r = call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/state", json={"state": "Completed"})
    assert r.status_code == 422 and "open class session" in r.get_json()["error"]["message"]


def test_batches_list_filters(world, client, login):
    people, batch, _ = world
    rows = data(call(client, login, people["ac"], "get", "/batches?mode=Classroom&q=Java"), 200)
    assert [b["batch_id"] for b in rows] == [batch.batch_id]
    assert data(call(client, login, people["ac"], "get", "/batches?mode=Hybrid"), 200) == []


# ---------------------------------------------------------------- allocation

def test_allocation_review_allocate_transfer_deallocate(world, client, login, make_batch, make_student):
    people, batch, student = world
    eid = student.enrolments[0]["enrolment_id"]
    queue = data(call(client, login, people["ac"], "get", "/allocation-queue"), 200)
    assert [q["enrolment_id"] for q in queue] == [eid]

    # The batch has no curriculum version: the review blocks
    review = data(call(client, login, people["ac"], "get", f"/batches/{batch.batch_id}/allocation-review?enrolment_id={eid}"), 200)
    assert review["result"] == "Blocked" and any("no curriculum version" in b for b in review["blocking"])
    r = call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/allocations", json={"enrolment_id": eid})
    assert r.status_code == 422 and r.get_json()["error"]["details"]["blocking"]

    good = make_batch(1, trainers=[people["g2"]], capacity=1, state="Running", curriculum_version_id=_java_version())
    review = data(call(client, login, people["ac"], "get", f"/batches/{good.batch_id}/allocation-review?enrolment_id={eid}"), 200)
    assert review["result"] == "Ready to allocate"
    allocation = data(call(client, login, people["ac"], "post", f"/batches/{good.batch_id}/allocations", json={"enrolment_id": eid, "reason": "first seat"}), 201)
    assert allocation["status"] == "Active"
    assert data(call(client, login, student.student_code, "get", "/me/enrolments"), 200)[0]["status"] == "Allocated — awaiting first regular class"
    assert data(call(client, login, people["ac"], "get", f"/batches/{good.batch_id}"), 200)["state"] == "Full"  # derived from capacity
    assert data(call(client, login, people["ac"], "get", "/allocation-queue"), 200) == []
    assert call(client, login, people["ac"], "post", f"/batches/{good.batch_id}/allocations", json={"enrolment_id": eid}).status_code == 422

    other = make_batch(1, trainers=[people["g2"]], capacity=5, state="Running", curriculum_version_id=_java_version())
    t = data(call(client, login, people["ac"], "post", f"/enrolments/{eid}/transfer", json={"batch_id": other.batch_id, "reason": "timing"}), 200)
    assert t["batch"]["batch_id"] == other.batch_id
    assert data(call(client, login, people["ac"], "get", f"/batches/{good.batch_id}"), 200)["state"] == "Running"
    history = data(call(client, login, people["ac"], "get", f"/batches/{good.batch_id}/allocations?status=Transferred"), 200)
    assert history and "Moved to" in history[0]["reason"]

    assert call(client, login, people["ac"], "post", f"/enrolments/{eid}/deallocate", json={}).status_code == 400
    data(call(client, login, people["ac"], "post", f"/enrolments/{eid}/deallocate", json={"reason": "left"}), 200)
    assert data(call(client, login, student.student_code, "get", "/me/enrolments"), 200)[0]["status"] == "Allocation Pending"
    assert call(client, login, people["ac"], "post", f"/enrolments/{eid}/deallocate", json={"reason": "again"}).status_code == 409


def _java_version():
    from repositories import catalog as catalog_repo

    return catalog_repo.active_curriculum_version_id(catalog_repo.get_course_by_code("NIT-CRS-047").course_id)


def test_allocation_scope_and_version_warning(world, client, login, make_batch, make_student):
    people, batch, student = world
    eid = student.enrolments[0]["enrolment_id"]
    good = make_batch(1, trainers=[people["g2"]], curriculum_version_id=_java_version())
    vij = make_batch(2, trainers=[people["v1"]], curriculum_version_id=_java_version())
    assert call(client, login, people["ac_vij"], "post", f"/batches/{good.batch_id}/allocations", json={"enrolment_id": eid}).status_code == 404
    r = call(client, login, people["ac"], "post", f"/batches/{vij.batch_id}/allocations", json={"enrolment_id": eid})
    assert r.status_code == 404
    assert call(client, login, people["g1"], "get", f"/batches/{good.batch_id}/allocations").status_code == 404  # not their batch
    assert call(client, login, student.student_code, "post", f"/batches/{good.batch_id}/allocations", json={"enrolment_id": eid}).status_code == 403

    # a different mode is a warning that must be acknowledged
    hybrid_less = make_batch(1, trainers=[people["g2"]], mode="Live Online", curriculum_version_id=_java_version())
    r = call(client, login, people["ac"], "post", f"/batches/{hybrid_less.batch_id}/allocations", json={"enrolment_id": eid})
    assert r.status_code == 422 and r.get_json()["error"]["details"]["warnings"]
    data(call(client, login, people["ac"], "post", f"/batches/{hybrid_less.batch_id}/allocations", json={"enrolment_id": eid, "acknowledge_warnings": True}), 201)


def test_roster_is_staff_only(world, client, login, allocate):
    people, batch, student = world
    allocate(student, batch)
    assert call(client, login, student.student_code, "get", f"/batches/{batch.batch_id}/allocations").status_code == 403
    rows = data(call(client, login, people["g1"], "get", f"/batches/{batch.batch_id}/allocations"), 200)
    assert rows[0]["student"]["student_code"] == student.student_code
    detail = data(call(client, login, student.student_code, "get", f"/batches/{batch.batch_id}"), 200)
    assert "history" in detail and detail["history"] == [] and detail["trainer_history"] == []


# ---------------------------------------------------------------- sessions

def test_create_weekly_series_and_conflicts(world, client, login):
    people, batch, _ = world
    start = future(3)
    body = {"batch_id": batch.batch_id, "title": "Live class", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=2)),
            "room": "Lab 1", "recurrence": {"count": 3}}
    sessions = data(call(client, login, people["ac"], "post", "/class-sessions", json=body), 201)
    assert len(sessions) == 3
    days = [datetime.fromisoformat(s["starts_at"]).astimezone(IST).date() for s in sessions]
    assert days[1] - days[0] == timedelta(days=7) and days[2] - days[1] == timedelta(days=7)
    assert all(s["state"] == "Scheduled" and s["meet_status"] == "Not Required" for s in sessions)

    # the trainer cannot be in two places
    r = call(client, login, people["ac"], "post", "/class-sessions", json={**body, "recurrence": None, "title": "Clash", "room": "Lab 2"})
    assert r.status_code == 422 and "already teaches" in r.get_json()["error"]["message"]
    # a room clash is advisory
    other = {**body, "recurrence": None, "title": "Room clash", "trainer_user_id": people["g1"].user_id}
    r = call(client, login, people["ac"], "post", "/class-sessions", json={**other, "starts_at": iso(start + timedelta(minutes=30))})
    assert r.status_code == 422
    # past classes and unassigned trainers are rejected
    past = future(-2)
    assert call(client, login, people["ac"], "post", "/class-sessions", json={**body, "recurrence": None, "starts_at": iso(past), "ends_at": iso(past + timedelta(hours=1))}).status_code == 400
    assert call(client, login, people["ac"], "post", "/class-sessions", json={**body, "recurrence": None, "trainer_user_id": people["g2"].user_id, "room": "Z"}).status_code == 400
    # a trainer cannot schedule
    assert call(client, login, people["g1"], "post", "/class-sessions", json=body).status_code == 403


def test_online_session_meet_lifecycle(world, client, login):
    people, batch, student = world
    start = future(4)
    body = {"batch_id": batch.batch_id, "title": "Online", "mode": "Live Online", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}
    session = data(call(client, login, people["ac"], "post", "/class-sessions", json=body), 201)[0]
    sid = session["session_id"]
    assert session["meet_status"] == "Pending Verification" and session["organizer_email"] == "trainer@nipunatechnologies.com"

    assert call(client, login, people["ac"], "put", f"/class-sessions/{sid}/meet", json={"meet_link": "https://evil.example/x"}).status_code == 400
    linked = data(call(client, login, people["ac"], "put", f"/class-sessions/{sid}/meet", json={"meet_link": "https://meet.google.com/abc-defg-hij"}), 200)
    assert linked["meet_status"] == "Linked" and linked["meet_status_label"] == "Associated"
    failed = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/meet/fail", json={"detail": "No licence"}), 200)
    assert failed["meet_status_label"] == "Failed" and failed["meet_link"] is None
    assert data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/meet/reset"), 200)["meet_status"] == "Pending Verification"
    detail = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert [e["event_type"] for e in detail["meet_events"]] == ["Requested", "Link associated", "Association failed", "Association retried"]

    # classroom sessions have no Meet
    classroom = data(call(client, login, people["ac"], "post", "/class-sessions", json={**body, "mode": "Classroom", "title": "In room",
                                                                                     "starts_at": iso(start + timedelta(days=1)), "ends_at": iso(start + timedelta(days=1, hours=1))}), 201)[0]
    assert call(client, login, people["ac"], "put", f"/class-sessions/{classroom['session_id']}/meet", json={"meet_link": "https://meet.google.com/a-b-c"}).status_code == 422


def test_reschedule_cancel_history_and_notices(world, client, login, allocate):
    people, batch, student = world
    allocate(student, batch)
    start = future(3)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Regression", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=2))}), 201)[0]["session_id"]

    assert call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule", json={"starts_at": iso(start + timedelta(days=1)), "ends_at": iso(start + timedelta(days=1, hours=2))}).status_code == 400  # reason
    moved = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule",
                      json={"starts_at": iso(start + timedelta(days=1)), "ends_at": iso(start + timedelta(days=1, hours=2)), "reason": "Holiday"}), 200)
    assert moved["state"] == "Rescheduled"
    detail = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert detail["changes"][0]["change_type"] == "Rescheduled" and detail["changes"][0]["short_notice"] is False

    assert any(t.startswith("Class rescheduled") for t in notification_titles(student))

    cancelled = data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/cancel", json={"reason": "Trainer unwell"}), 200)
    assert cancelled["state"] == "Cancelled"
    assert call(client, login, people["ac"], "post", f"/class-sessions/{sid}/cancel", json={"reason": "again"}).status_code == 422
    assert call(client, login, people["ac"], "post", f"/class-sessions/{sid}/start").status_code == 422
    assert call(client, login, people["ac2"], "post", f"/class-sessions/{sid}/cancel", json={"reason": "x"}).status_code == 422
    assert call(client, login, people["ac_vij"], "post", f"/class-sessions/{sid}/cancel", json={"reason": "x"}).status_code == 404


def notification_titles(student):
    from sqlalchemy import select

    from config.database import db
    from models import Notification
    from repositories import users as users_repo

    user = users_repo.get_by_student_id(student.student_id)
    return list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == user.user_id)).scalars())


def test_start_and_deliver_rules(world, client, login):
    people, batch, student = world
    later = future(3)
    far = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Later", "starts_at": iso(later), "ends_at": iso(later + timedelta(hours=1))}), 201)[0]
    assert call(client, login, people["g1"], "post", f"/class-sessions/{far['session_id']}/start").status_code == 422  # too early
    assert call(client, login, people["g1"], "post", f"/class-sessions/{far['session_id']}/deliver").status_code == 422  # not begun

    soon = datetime.now(IST) + timedelta(minutes=20)
    near = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Soon", "starts_at": iso(soon), "ends_at": iso(soon + timedelta(minutes=45))}), 201)[0]
    sid = near["session_id"]
    assert call(client, login, people["g2"], "post", f"/class-sessions/{sid}/start").status_code == 404  # not on this batch
    assert data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/start"), 200)["state"] == "Live"
    done = data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/deliver", json={"notes": "Covered OOP"}), 200)
    assert done["state"] == "Delivered" and done["delivered_at"] and done["notes"] == "Covered OOP"
    assert call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule", json={"starts_at": iso(later), "ends_at": iso(later + timedelta(hours=1)), "reason": "x"}).status_code == 422

    from services import class_sessions as service

    assert [s.session_id for s in service.delivered_sessions(batch.batch_id)] == [sid]


def test_reschedule_requests(world, client, login):
    people, batch, _ = world
    start = future(3)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Lab", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=2))}), 201)[0]["session_id"]
    proposal = {"proposed_starts_at": iso(start + timedelta(days=2)), "proposed_ends_at": iso(start + timedelta(days=2, hours=2)), "reason": "Exam that day"}
    assert call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule-requests", json=proposal).status_code == 403  # trainers ask
    req = data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/reschedule-requests", json=proposal), 201)
    assert call(client, login, people["g1"], "post", f"/class-sessions/{sid}/reschedule-requests", json=proposal).status_code == 409
    assert [r["request_id"] for r in data(call(client, login, people["g1"], "get", "/reschedule-requests?status=Open"), 200)] == [req["request_id"]]
    assert call(client, login, people["g1"], "post", f"/reschedule-requests/{req['request_id']}/approve", json={}).status_code == 403
    approved = data(call(client, login, people["ac"], "post", f"/reschedule-requests/{req['request_id']}/approve", json={}), 200)
    assert approved["status"] == "Approved"
    session = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert session["state"] == "Rescheduled" and session["open_request"] is None

    again = data(call(client, login, people["g1"], "post", f"/class-sessions/{sid}/reschedule-requests", json=proposal), 201)
    assert call(client, login, people["ac"], "post", f"/reschedule-requests/{again['request_id']}/reject", json={}).status_code == 400
    assert data(call(client, login, people["ac"], "post", f"/reschedule-requests/{again['request_id']}/reject", json={"note": "Not possible"}), 200)["status"] == "Rejected"


def test_trainer_substitute_needs_reason_and_assignment(world, client, login):
    people, batch, _ = world
    start = future(3)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Cover", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}), 201)[0]["session_id"]
    call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/trainers", json={"trainer_user_id": people["g2"].user_id})
    assert call(client, login, people["ac"], "patch", f"/class-sessions/{sid}", json={"trainer_user_id": people["g2"].user_id}).status_code == 400
    updated = data(call(client, login, people["ac"], "patch", f"/class-sessions/{sid}", json={"trainer_user_id": people["g2"].user_id, "reason": "Leave"}), 200)
    assert updated["trainer"]["full_name"] == "Trainer G2"
    detail = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert detail["changes"][0]["change_type"] == "Trainer changed"
    # a trainer with upcoming sessions cannot be ended; one without can
    trainers = {t["full_name"]: t for t in data(call(client, login, people["ac"], "get", f"/batches/{batch.batch_id}"), 200)["trainers"]}
    assert call(client, login, people["ac"], "delete", f"/batches/{batch.batch_id}/trainers/{trainers['Trainer G2']['batch_trainer_id']}").status_code == 422
    assert call(client, login, people["ac"], "delete", f"/batches/{batch.batch_id}/trainers/{trainers['Trainer G1']['batch_trainer_id']}").status_code == 200


# ---------------------------------------------------------------- student views

def test_student_views_are_own_only_and_hide_the_meet_link(world, client, login, allocate, make_student, make_batch):
    people, batch, student = world
    other_student = make_student()
    good = make_batch(1, trainers=[people["g2"]], curriculum_version_id=_java_version(), state="Running")
    allocate(student, good)
    soon = datetime.now(IST) + timedelta(minutes=10)
    sess = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": good.batch_id, "title": "Live", "mode": "Live Online", "starts_at": iso(soon), "ends_at": iso(soon + timedelta(hours=1))}), 201)[0]
    sid = sess["session_id"]
    join = data(call(client, login, student.student_code, "get", f"/class-sessions/{sid}"), 200)
    assert join["join"]["enabled"] is False and join["meet_link"] is None and "changes" not in join

    call(client, login, people["ac"], "put", f"/class-sessions/{sid}/meet", json={"meet_link": "https://meet.google.com/abc-defg-hij"})
    joined = data(call(client, login, student.student_code, "get", f"/class-sessions/{sid}"), 200)
    assert joined["join"]["enabled"] is True and joined["join"]["url"] == "https://meet.google.com/abc-defg-hij" and joined["meet_link"] is None
    listed = data(call(client, login, student.student_code, "get", "/class-sessions"), 200)
    assert all(s["meet_link"] is None for s in listed)
    staff_view = data(call(client, login, people["ac"], "get", f"/class-sessions/{sid}"), 200)
    assert staff_view["meet_link"] == "https://meet.google.com/abc-defg-hij"

    # other student sees nothing of it; course pages are own-only
    assert call(client, login, other_student.student_code, "get", f"/class-sessions/{sid}").status_code == 404
    mine = data(call(client, login, student.student_code, "get", "/me/enrolments"), 200)
    assert len(mine) == 1 and mine[0]["batch"]["batch_id"] == good.batch_id and mine[0]["delivery"]["upcoming"] == 1
    theirs = other_student.enrolments[0]["enrolment_id"]
    assert call(client, login, student.student_code, "get", f"/me/enrolments/{theirs}").status_code == 404
    assert call(client, login, people["ac"], "get", "/me/enrolments").status_code == 403

    schedule = data(call(client, login, student.student_code, "get", "/me/schedule"), 200)
    assert [s["session_id"] for s in schedule] == [sid] and schedule[0]["enrolment"]["enrolment_id"] == mine[0]["enrolment_id"]
    other_schedule = data(call(client, login, other_student.student_code, "get", "/me/schedule"), 200)
    assert other_schedule == []

    from services import class_sessions as service

    assert [s.session_id for s in service.sessions_for_enrolment(mine[0]["enrolment_id"])] == [sid]


def test_combo_course_tracks_modules_and_topics(world, client, login, make_student, make_batch, allocate, run_sql):
    people, _, _ = world
    student = make_student(course="NIT-CRS-018", enrolments=[{"course_code": "NIT-CRS-018", "kind": "Combo"}, {"course_code": "NIT-CRS-052", "kind": "Complimentary", "parent_course_code": "NIT-CRS-018", "benefit_gate": {"met": True}}], admission_id="A-COMBO")
    from repositories import catalog as catalog_repo
    from models import CurriculumModule, CurriculumTopic
    from config.database import db

    course = catalog_repo.get_course_by_code("NIT-CRS-018")
    t2 = next(c for c in course.components if c.track_code == "NIT-CRS-018/T2")
    version_id = catalog_repo.active_curriculum_version_id(course.course_id, t2.component_id)
    module = CurriculumModule(curriculum_version_id=version_id, title="Supervised Learning", sort_order=1)
    db.session.add(module)
    db.session.flush()
    topic = CurriculumTopic(module_id=module.module_id, title="Regression", sort_order=1)
    db.session.add(topic)
    db.session.commit()

    batch = make_batch(1, course_code="NIT-CRS-018", trainers=[people["g1"]], state="Running", curriculum_version_id=catalog_repo.active_curriculum_version_id(course.course_id))
    allocate(student, batch)
    start = future(2)
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json={"batch_id": batch.batch_id, "title": "Regression I", "topic_id": topic.topic_id, "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=2))}), 201)[0]["session_id"]

    cards = data(call(client, login, student.student_code, "get", "/me/enrolments"), 200)
    combo = next(c for c in cards if c["kind"] == "Combo")
    comp = next(c for c in cards if c["kind"] == "Complimentary")
    assert comp["linked_admission_code"] == combo["admission"]["admission_code"]
    assert "Curriculum Mapping Pending" in comp["explanation"]
    overview = data(call(client, login, student.student_code, "get", f"/me/enrolments/{combo['enrolment_id']}"), 200)
    assert len(overview["tracks"]) == 4
    ml = next(t for t in overview["tracks"] if t["track_code"] == "NIT-CRS-018/T2")
    assert ml["delivery"]["upcoming"] == 1 and overview["finance"] is None
    track = data(call(client, login, student.student_code, "get", f"/me/enrolments/{combo['enrolment_id']}/tracks/{ml['enrolment_track_id']}"), 200)
    assert track["modules"][0]["title"] == "Supervised Learning" and track["modules"][0]["status"] == "Scheduled"
    mod = data(call(client, login, student.student_code, "get", f"/modules/{module.module_id}"), 200)
    assert mod["context"]["track"]["track_code"] == "NIT-CRS-018/T2" and mod["topics"][0]["session_count"] == 1
    top = data(call(client, login, student.student_code, "get", f"/topics/{topic.topic_id}"), 200)
    assert [s["session_id"] for s in top["sessions"]] == [sid]
    detail = data(call(client, login, student.student_code, "get", f"/class-sessions/{sid}"), 200)
    assert detail["topic_path"]["module"]["title"] == "Supervised Learning"

    # another learner cannot open this student's curriculum pages
    stranger = make_student(course="NIT-CRS-047", admission_id="A-OTHER")
    assert call(client, login, stranger.student_code, "get", f"/modules/{module.module_id}").status_code == 404
    assert call(client, login, stranger.student_code, "get", f"/topics/{topic.topic_id}").status_code == 404
    assert call(client, login, people["g1"], "get", f"/topics/{topic.topic_id}").status_code == 200


def test_enrolment_people_list_scope(world, client, login, allocate):
    people, batch, student = world
    allocate(student, batch)
    rows = data(call(client, login, people["ac"], "get", f"/enrolments?batch_id={batch.batch_id}"), 200)
    assert [r["student"]["student_code"] for r in rows] == [student.student_code]
    assert data(call(client, login, people["ac_vij"], "get", "/enrolments"), 200) == []
    assert [r["enrolment_id"] for r in data(call(client, login, people["g1"], "get", "/enrolments"), 200)] == [student.enrolments[0]["enrolment_id"]]
    assert data(call(client, login, people["g2"], "get", "/enrolments"), 200) == []
    assert call(client, login, student.student_code, "get", "/enrolments").status_code == 403
    assert call(client, login, people["g1"], "get", "/allocation-queue").status_code == 403

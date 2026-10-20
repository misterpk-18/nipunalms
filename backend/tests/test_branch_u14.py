"""UX phase U14: the Branch Manager's My work, Waiting for a batch, the batch's step bar and one-step confirmation, and Create classes
(preview and create from the batch timetable, skipping holidays and closures)."""
from datetime import datetime, timedelta

from config.database import db
from config.timezone import IST, today_ist
from models import ClassSession, CourseModule, CourseTopic
from tests.helpers import course_id
from tests.test_batches_delivery import confirmed_batch, ready_fields, seat
from tests.test_delivery import call, data, future, iso, world  # noqa: F401


def get(client, login, who, path, status=200):
    return data(call(client, login, who, "get", path), status)


def rows_of(client, login, who, query=""):
    return {r["key"]: r for r in get(client, login, who, f"/branch/my-work{query}")["rows"]}


# ---------------------------------------------------------------- My work

def test_my_work_lists_what_waits_in_the_decided_order(world, client, login, make_session, run_sql, make_user):
    people, batch, student = world
    mine = get(client, login, people["ac"], "/branch/my-work")
    assert [r["key"] for r in mine["rows"]] == ["waiting"]
    waiting = mine["rows"][0]
    assert waiting["count"] == 1 and waiting["to"] == "/branch/waiting" and waiting["action"] == "Allocate" and "waiting for a batch" in waiting["what"]

    # a reschedule request and a proposed extra class are decisions on the schedule
    upcoming = make_session(batch, people["g1"], future(3, 10))
    data(call(client, login, people["g1"], "post", f"/class-sessions/{upcoming.session_id}/reschedule-requests", json={
        "proposed_starts_at": iso(future(4, 10)), "proposed_ends_at": iso(future(4, 12)), "reason": "Trainer unwell"}), 201)
    data(call(client, login, people["ac"], "post", "/class-sessions", json={
        "batch_id": batch.batch_id, "title": "Extra doubt clearing", "starts_at": iso(future(5, 10)), "ends_at": iso(future(5, 12)),
        "purpose": "Extra", "purpose_reference": "Approved addition", "owner_user_id": people["ac"].user_id, "due_on": future(5).date().isoformat()}), 201)
    # a request near its reply deadline, and an online class today with no link
    sent = client.post("/api/v1/support-requests", json={"category": "LMS", "subject": "Cannot open the recording", "details": "It never loads"},
                       headers=login(student.student_code))
    assert sent.status_code == 201, sent.get_json()
    run_sql("UPDATE support_requests SET sla_due_at = now() - interval '1 hour'")
    now = datetime.now(IST).replace(microsecond=0)
    soon = now + timedelta(hours=2)
    if soon.date() != now.date():  # late evening: keep the class on today's date
        soon = now.replace(hour=23, minute=59, second=0)
    make_session(batch, people["g1"], soon, hours=1, mode="Live Online", meet_status="Pending Verification", title="Online today")

    keys = [r["key"] for r in get(client, login, people["ac"], "/branch/my-work")["rows"]]
    assert keys == ["waiting", "decisions", "support", "class_day"]
    rows = rows_of(client, login, people["ac"])
    assert rows["decisions"]["count"] == 2 and "1 reschedule request and 1 extra class to decide" == rows["decisions"]["what"]
    assert rows["decisions"]["to"] == "/branch/schedule" and rows["decisions"]["oldest_at"]
    assert rows["class_day"]["count"] == 1 and "Online today" in rows["class_day"]["where"]
    assert get(client, login, people["ac"], "/branch/my-work")["total"] == 1 + 2 + 1 + 1


def test_my_work_follows_the_branch_and_the_role(world, client, login):
    people, _, _ = world
    assert rows_of(client, login, people["ac_vij"]) == {}                                  # nothing waits at Vijayawada
    assert call(client, login, people["ac"], "get", "/branch/my-work?branch_id=2").status_code == 404
    assert call(client, login, people["admin"], "get", "/branch/my-work?branch_id=1").status_code == 200  # Super Admin and Founder read it for any branch
    assert call(client, login, people["founder"], "get", "/branch/my-work").status_code == 200
    assert call(client, login, people["g1"], "get", "/branch/my-work").status_code == 403
    assert call(client, login, "NIT-STU-2026-000001", "get", "/branch/my-work").status_code in (401, 403)
    # the navigation badges come from the same rows
    counts = get(client, login, people["ac"], "/me/nav-counts?workspace=branch")
    assert counts["my_work"] == get(client, login, people["ac"], "/branch/my-work")["total"] == 1 and counts["waiting"] == 1
    assert counts["schedule"] == 0 and counts["class_day"] == 0


# ---------------------------------------------------------------- Waiting for a batch

def test_waiting_lists_each_student_with_the_batches_that_could_take_them(world, client, login, make_batch, make_student):
    people, batch, student = world
    page = call(client, login, people["ac"], "get", "/branch/waiting")
    assert page.status_code == 200
    body = page.get_json()
    assert body["meta"]["total"] == 1
    row = body["data"][0]
    assert row["student"]["student_code"] == student.student_code and row["branch"]["branch_code"] == "NIT-GNT" and row["waiting_days"] >= 0
    assert [m["batch"]["batch_id"] for m in row["matches"]] == [batch.batch_id]
    match = row["matches"][0]
    assert match["result"] == "Ready to allocate" and match["warnings"] == [] and match["track"] is None
    assert match["batch"]["seats_left"] == 30 and match["batch"]["capacity"] == 30 and match["batch"]["trainers"] == ["Trainer G1"]

    # a full batch and a batch of another course are not offered
    make_batch(1, trainers=[people["g2"]], capacity=5, state="Running", course_code="NIT-CRS-019")
    full = make_batch(1, trainers=[people["g2"]], capacity=1, state="Running")
    seat(client, login, people, full, make_student(admission_id="A-OTHER"))
    row = get(client, login, people["ac"], "/branch/waiting")[0]
    assert [m["batch"]["batch_id"] for m in row["matches"]] == [batch.batch_id] and row["blocked"] == []

    # another branch's manager sees none of it; a trainer is refused
    assert get(client, login, people["ac_vij"], "/branch/waiting") == []
    assert call(client, login, people["g1"], "get", "/branch/waiting").status_code == 403


def test_a_student_the_review_blocks_is_told_why_instead_of_offered_a_batch(world, client, login, run_sql):
    people, batch, student = world
    eid = student.enrolments[0]["enrolment_id"]
    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/allocations", json={"enrolment_id": eid}), 201)
    run_sql("UPDATE enrolments SET status = 'Allocation Pending' WHERE enrolment_id = :e", e=eid)       # a seat and still on the list
    row = get(client, login, people["ac"], "/branch/waiting")[0]
    assert row["matches"] == [] and row["blocked"][0]["batch"]["batch_id"] == batch.batch_id
    assert "use transfer" in row["blocked"][0]["reasons"][0]


def test_one_click_allocate_takes_the_student_off_the_list_and_batch_view_matches(world, client, login, make_batch):
    people, batch, student = world
    listed = get(client, login, people["ac"], f"/batches/{batch.batch_id}/waiting")
    assert listed["seats_left"] == 30 and [r["student"]["student_code"] for r in listed["students"]] == [student.student_code]
    eid = listed["students"][0]["enrolment"]["enrolment_id"]
    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/allocations", json={"enrolment_id": eid}), 201)
    assert get(client, login, people["ac"], "/branch/waiting") == []
    assert get(client, login, people["ac"], f"/batches/{batch.batch_id}/waiting")["students"] == []
    assert call(client, login, people["ac_vij"], "get", f"/batches/{batch.batch_id}/waiting").status_code == 404
    assert call(client, login, people["g1"], "get", f"/batches/{batch.batch_id}/waiting").status_code == 403


def test_a_combo_student_is_offered_the_whole_programme_and_each_track(world, client, login, make_batch, make_student, crm_event):
    people, _, _ = world
    from tests import helpers

    combo = make_student(admission_id="A-COMBO", course="NIT-CRS-018", enrolments=helpers.combo_admission_data()["enrolments"])
    parent = make_batch(1, trainers=[people["g2"]], course_code="NIT-CRS-018", state="Running")
    track_batch = make_batch(1, trainers=[people["g2"]], course_code="NIT-CRS-018", state="Running")
    from config.database import db as _db
    from repositories import catalog as catalog_repo

    track_batch.component_id = catalog_repo.get_component_by_track_code("NIT-CRS-018/T1").component_id
    _db.session.flush()
    _db.session.commit()
    rows = get(client, login, people["ac"], "/branch/waiting?q=" + combo.student_code)
    matches = rows[0]["matches"]
    assert {(m["batch"]["batch_id"], m["track"]["track_code"] if m["track"] else None) for m in matches} == {
        (parent.batch_id, None), (track_batch.batch_id, "NIT-CRS-018/T1")}


# ---------------------------------------------------------------- the batch's steps

def topics_for(batch, titles):
    module = CourseModule(course_id=course_id(), title="Core Java", sort_order=1)
    db.session.add(module)
    db.session.flush()
    for order, title in enumerate(titles, 1):
        db.session.add(CourseTopic(module_id=module.module_id, title=title, sort_order=order))
    db.session.flush()
    db.session.commit()


def progress(client, login, who, batch_id):
    return get(client, login, who, f"/batches/{batch_id}/progress")


def test_the_steps_walk_a_batch_from_created_to_classes(world, client, login, make_batch):
    people, _, student = world
    bare = make_batch(1)            # no trainer yet
    p = progress(client, login, people["ac"], bare.batch_id)
    assert [(s["key"], s["done"]) for s in p["steps"]] == [("created", True), ("trainer", False), ("ready", False), ("confirmed", False), ("students", False), ("classes", False)]
    assert p["current"] == "trainer" and p["next"] == {"key": "assign_trainer", "label": "Assign a lead trainer"}

    batch = make_batch(1, trainers=[people["g1"]])
    p = progress(client, login, people["ac"], batch.batch_id)
    assert p["current"] == "ready" and p["next"]["key"] == "finish_setup"
    assert {x["key"] for x in p["problems"]} >= {"timetable", "resources", "recording"} and all(x["fix"] == "details" for x in p["problems"])

    data(call(client, login, people["ac"], "patch", f"/batches/{batch.batch_id}", json=ready_fields()), 200)
    p = progress(client, login, people["ac"], batch.batch_id)
    assert p["current"] == "confirmed" and p["next"]["label"] == "Confirm batch" and p["problems"] == [] and p["can_confirm"] is True

    # the Branch Manager confirms in one step (proposal included); a trainer may not
    assert call(client, login, people["g1"], "post", f"/batches/{batch.batch_id}/confirm", json={}).status_code == 403
    from sqlalchemy import text

    # created before the trainer: the stored readiness still says Blocked until the batch is confirmed
    db.session.execute(text("UPDATE batches SET readiness = 'Blocked', readiness_reason = 'No lead trainer assigned', recovery_owner = 'x' WHERE batch_id = :b"), {"b": batch.batch_id})
    db.session.commit()
    confirmed = data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/confirm", json={}), 200)
    assert confirmed["readiness"] == "Ready"
    assert confirmed["state"] == "Starting" and confirmed["confirmed_by"]["full_name"] == "AC Guntur"
    kinds = [e["event_type"] for e in get(client, login, people["ac"], f"/batches/{batch.batch_id}")["history"]]
    assert "Proposed" in kinds and "Confirmed" in kinds
    p = progress(client, login, people["ac"], batch.batch_id)
    assert p["current"] == "students" and p["next"]["key"] == "add_students" and p["counts"]["students"] == 0

    seat(client, login, people, batch, student)
    p = progress(client, login, people["ac"], batch.batch_id)
    assert p["current"] == "classes" and p["next"]["key"] == "create_classes" and p["counts"] == {"students": 1, "capacity": 30, "classes": 0, "upcoming": 0}

    data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/generate-sessions", json={}), 201)
    p = progress(client, login, people["ac"], batch.batch_id)
    assert p["current"] is None and p["next"] is None and all(s["done"] for s in p["steps"]) and p["counts"]["classes"] > 0


def test_confirming_with_warnings_needs_a_reason_and_a_batch_that_is_not_ready_is_refused(world, client, login, make_batch):
    people, _, _ = world
    first = confirmed_batch(client, login, people, make_batch)
    other = make_batch(1, trainers=[people["g2"]])
    data(call(client, login, people["ac"], "patch", f"/batches/{other.batch_id}", json=ready_fields(location="Lab 2")), 200)
    p = progress(client, login, people["ac"], other.batch_id)
    assert p["warnings"] and "Lab 2" in p["warnings"][0]["detail"] and p["problems"] == []
    asked = call(client, login, people["ac"], "post", f"/batches/{other.batch_id}/confirm", json={})
    assert asked.status_code == 422 and asked.get_json()["error"]["details"]["warnings"]
    assert data(call(client, login, people["ac"], "get", f"/batches/{other.batch_id}"), 200)["state"] == "Forming"   # the refusal leaves nothing half done
    data(call(client, login, people["ac"], "post", f"/batches/{other.batch_id}/confirm", json={"override_reason": "Two benches, split timings"}), 200)

    unready = make_batch(1, trainers=[people["g1"]])
    refused = call(client, login, people["ac"], "post", f"/batches/{unready.batch_id}/confirm", json={})
    assert refused.status_code == 422 and refused.get_json()["error"]["details"]["blocking"]


# ---------------------------------------------------------------- Create classes

def generate(client, login, who, batch, status=201, **body):
    return data(call(client, login, who, "post", f"/batches/{batch.batch_id}/generate-sessions", json=body), status)


def teaching_days(start, end, weekdays):
    return [start + timedelta(days=n) for n in range((end - start).days + 1) if (start + timedelta(days=n)).isoweekday() in weekdays]


def test_the_preview_plans_a_class_per_teaching_day_and_skips_holidays_and_closures(world, client, login, make_batch, run_sql):
    people, _, _ = world
    batch = confirmed_batch(client, login, people, make_batch)             # Tue and Thu 15:00-17:00, in 10 to 100 days
    topics_for(batch, ["Syntax", "Loops", "Streams"])
    start, end = future(10).date(), future(100).date()
    days = teaching_days(start, end, {2, 4})
    holiday, closure = days[1], days[2]
    run_sql("INSERT INTO calendar_closures (kind, branch_id, starts_on, ends_on, title, status, requested_by, decided_by, decided_at) "
            "SELECT 'Company Holiday', NULL, :d, :d, 'Dussehra', 'Approved', user_id, user_id, now() FROM users LIMIT 1", d=holiday)
    run_sql("INSERT INTO calendar_closures (kind, branch_id, starts_on, ends_on, title, status, requested_by, decided_by, decided_at) "
            "SELECT 'Branch Closure', 1, :d, :d, 'Flooding', 'Approved', user_id, user_id, now() FROM users LIMIT 1", d=closure)
    run_sql("INSERT INTO calendar_closures (kind, branch_id, starts_on, ends_on, title, status, requested_by, decided_by, decided_at) "
            "SELECT 'Branch Closure', 2, :d, :d, 'Other branch', 'Approved', user_id, user_id, now() FROM users LIMIT 1", d=days[3])

    plan = generate(client, login, people["ac"], batch, 200, preview=True)
    planned = [c["starts_at"][:10] for c in plan["classes"]]
    assert planned == [d.isoformat() for d in days if d not in (holiday, closure)]
    assert {s["date"]: s["reason"] for s in plan["skipped"]} == {holiday.isoformat(): "Holiday: Dussehra", closure.isoformat(): "Closed: Flooding"}
    assert plan["trainer"]["full_name"] == "Trainer G1" and plan["room"] == "Lab 2" and plan["truncated"] is False and plan["created"] == []
    assert [c["title"] for c in plan["classes"][:3]] == ["Syntax", "Loops", "Streams"] and plan["classes"][3]["title"].startswith("Java Full Stack Developer: class")
    assert plan["classes"][0]["starts_at"].endswith("15:00:00+05:30") and plan["classes"][0]["ends_at"].endswith("17:00:00+05:30")
    assert db.session.query(ClassSession).filter_by(batch_id=batch.batch_id).count() == 0      # a preview changes nothing

    done = generate(client, login, people["ac"], batch)
    assert len(done["created"]) == len(plan["classes"]) and done["created"][0]["topic"]["title"] == "Syntax" and done["created"][0]["room"] == "Lab 2"
    assert all(c["trainer"]["full_name"] == "Trainer G1" and c["state"] == "Scheduled" for c in done["created"])

    # run again: nothing doubles up, the days already planned are named
    again = generate(client, login, people["ac"], batch, 200, preview=True)
    assert again["classes"] == [] and {s["reason"] for s in again["skipped"]} >= {"The batch already has a class this day"}
    assert call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/generate-sessions", json={}).status_code == 422


def test_dates_can_be_narrowed_and_long_runs_are_cut_at_sixty_classes(world, client, login, make_batch):
    people, _, _ = world
    batch = confirmed_batch(client, login, people, make_batch)
    first = future(10).date()
    narrow = generate(client, login, people["ac"], batch, 200, preview=True, from_date=first.isoformat(), until=(first + timedelta(days=13)).isoformat())
    assert len(narrow["classes"]) == 4 and narrow["until"] == (first + timedelta(days=13)).isoformat()
    assert call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/generate-sessions",
                json={"preview": True, "from_date": first.isoformat(), "until": (first - timedelta(days=1)).isoformat()}).status_code == 400

    db.session.query(type(batch)).filter_by(batch_id=batch.batch_id).update({"planned_end": today_ist() + timedelta(days=700)})
    db.session.commit()
    long = generate(client, login, people["ac"], batch, 200, preview=True)
    assert len(long["classes"]) == 60 and long["truncated"] is True
    created = generate(client, login, people["ac"], batch)
    assert len(created["created"]) == 60


def test_classes_need_a_timetable_a_trainer_and_an_open_batch(world, client, login, make_batch):
    people, _, _ = world
    no_timetable = make_batch(1, trainers=[people["g1"]], planned_end=today_ist() + timedelta(days=30))
    refused = call(client, login, people["ac"], "post", f"/batches/{no_timetable.batch_id}/generate-sessions", json={"preview": True})
    assert refused.status_code == 422 and "teaching days" in refused.get_json()["error"]["message"]

    no_lead = make_batch(1, schedule_days=[2], start_time="10:00", end_time="11:00", planned_end=today_ist() + timedelta(days=30))
    refused = call(client, login, people["ac"], "post", f"/batches/{no_lead.batch_id}/generate-sessions", json={"preview": True})
    assert refused.status_code == 422 and "lead trainer" in refused.get_json()["error"]["message"]

    done = make_batch(1, trainers=[people["g1"]], schedule_days=[2], start_time="10:00", end_time="11:00", planned_end=today_ist() + timedelta(days=30), state="Completed")
    assert call(client, login, people["ac"], "post", f"/batches/{done.batch_id}/generate-sessions", json={"preview": True}).status_code == 422

    assert call(client, login, people["g1"], "post", f"/batches/{done.batch_id}/generate-sessions", json={}).status_code == 403
    assert call(client, login, people["ac_vij"], "post", f"/batches/{done.batch_id}/generate-sessions", json={}).status_code == 404


def test_a_trainer_clash_blocks_and_a_booked_room_needs_the_managers_reason(world, client, login, make_batch):
    people, _, _ = world
    first = confirmed_batch(client, login, people, make_batch)
    generate(client, login, people["ac"], first)
    # the same trainer, the same times: it cannot be overridden
    same_trainer = make_batch(1, trainers=[people["g1"]], **{})
    data(call(client, login, people["ac"], "patch", f"/batches/{same_trainer.batch_id}", json=ready_fields(location="Lab 9")), 200)
    plan = generate(client, login, people["ac"], same_trainer, 200, preview=True)
    assert plan["blocking"] and "already teaches" in plan["blocking"][0] and plan["classes"][0]["blocked"]
    refused = call(client, login, people["ac"], "post", f"/batches/{same_trainer.batch_id}/generate-sessions", json={"override_reason": "no"})
    assert refused.status_code == 422 and refused.get_json()["error"]["details"]["blocking"]

    # another trainer in the same room at the same times: a warning the Branch Manager overrides with a reason
    same_room = make_batch(1, trainers=[people["g2"]])
    data(call(client, login, people["ac"], "patch", f"/batches/{same_room.batch_id}", json=ready_fields(location="Lab 2")), 200)
    plan = generate(client, login, people["ac"], same_room, 200, preview=True)
    assert plan["blocking"] == [] and plan["warnings"] and "Lab 2" in plan["warnings"][0]
    asked = call(client, login, people["ac"], "post", f"/batches/{same_room.batch_id}/generate-sessions", json={})
    assert asked.status_code == 422 and asked.get_json()["error"]["details"]["warnings"]
    assert db.session.query(ClassSession).filter_by(batch_id=same_room.batch_id).count() == 0           # all or nothing
    done = generate(client, login, people["ac"], same_room, override_reason="Lab 2 has two benches; classes alternate")
    assert len(done["created"]) == len(plan["classes"])
    assert db.session.query(ClassSession).filter_by(batch_id=same_room.batch_id).first().room_override_reason


def test_creating_classes_tells_the_students_and_the_trainer_once(world, client, login, make_batch, make_student, allocate):
    from sqlalchemy import select

    from models import Notification

    people, _, student = world
    batch = confirmed_batch(client, login, people, make_batch)
    seat(client, login, people, batch, student)
    done = generate(client, login, people["ac"], batch)
    titles = list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == people["g1"].user_id)).scalars())
    assert sum(1 for t in titles if t.startswith(f"{len(done['created'])} new classes")) == 1


# ---------------------------------------------------------------- how students pay

def test_a_branch_manager_reads_how_students_pay_but_only_the_super_admin_and_founder_set_it(world, client, login, make_user):
    people, _, _ = world
    path = "/branches/1/payment-instructions"
    assert get(client, login, people["ac"], path)["payment_instructions"] is None
    # the Branch Manager is read-only
    assert call(client, login, people["ac"], "put", path, json={"payment_instructions": "Pay at the front desk"}).status_code == 403
    assert get(client, login, people["ac"], path)["payment_instructions"] is None
    for role in ("SUPER_ADMIN", "FOUNDER_CEO"):
        who = make_user(roles=[(role, None)])
        data(call(client, login, who, "put", path, json={"payment_instructions": f"Pay at the front desk ({role})"}), 200)
        assert get(client, login, people["ac"], path)["payment_instructions"] == f"Pay at the front desk ({role})"
    assert call(client, login, people["ac"], "get", "/branches/2/payment-instructions").status_code == 404
    assert call(client, login, people["g1"], "get", path).status_code == 403


def test_waiting_marks_the_batch_the_crm_counsellor_preferred(world, client, login, make_batch, run_sql):
    people, batch, student = world
    other = make_batch(1, trainers=[people["g2"]], state="Running")
    row = get(client, login, people["ac"], "/branch/waiting")[0]
    assert row["preferred_batch_code"] is None and [m["preferred"] for m in row["matches"]] == [False, False]

    run_sql(f"UPDATE admissions SET preferred_batch_code = '{other.batch_code}'")
    row = get(client, login, people["ac"], "/branch/waiting")[0]
    assert row["preferred_batch_code"] == other.batch_code
    assert {m["batch"]["batch_code"]: m["preferred"] for m in row["matches"]} == {batch.batch_code: False, other.batch_code: True}

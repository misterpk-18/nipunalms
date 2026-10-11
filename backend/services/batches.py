"""Batches: scoped reads, create / update, lifecycle, delivery readiness and trainer assignments.

Lifecycle (Module 15 §5, stored names kept for the CRM): Forming (Draft) -> Proposed -> Starting (Confirmed) -> Running
(In Progress) -> Completed; On Hold from Proposed / Starting / Running / Full and back to where it was; Cancelled while
nobody holds a seat; Archived after Completed or Cancelled once no live activity is left. The Branch Manager proposes
a batch once the first six points of the readiness record pass and confirms it (warnings need a recorded reason). 'Full' is not chosen by anyone: a Running batch flips to Full when its last seat is taken and back when a seat
frees up (`sync_full`). The database enforces the same transitions; the checks here give readable messages first.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from config.database import db
from config.timezone import today_ist
from models import (
    Batch, BatchCapacityRequest, BatchHandover, BatchSuccession, BatchTrainer, BatchTransferRequest, CalendarClosure, ClassSession,
    MaterialChange, RecordingException, SessionDisruption,
)
from models.batches import BATCH_STATE_LABELS, WEEKDAYS
from repositories import batches as batches_repo
from repositories import branches as branches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories import settings as settings_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, delivery_access, delivery_notices, meet, scope
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

CLOSED_STATES = ("Completed", "Cancelled", "Archived")
PUBLISHED_STATUSES = ("Approved", "Active")
NO_CURRICULUM = "No approved curriculum yet. Classes can be scheduled without topics, and the batch picks up the curriculum when one is activated"
# The Branch Manager confirms, holds and archives; Super Admin covers every branch (Module 15 §5, §19)
CONFIRM_ROLES = ("BRANCH_MANAGER", "SUPER_ADMIN")
# Enrolments that still owe teaching when a batch completes: each needs a named owner, plan and destination (§19)
OWING_STATUSES = ("Paused", "Allocation Pending", "Allocated — awaiting first regular class")
MATERIAL_FIELDS = ("planned_start", "mode", "schedule_days", "start_time", "end_time")


@dataclass
class BatchDetail:
    batch: Batch
    allocated_count: int
    session_counts: dict[str, int]
    trainer_history: list[BatchTrainer]
    events: list
    successions: list
    handovers: list


# ---------------------------------------------------------------- reads

def list_batches(filters: dict, page: int, per_page: int) -> tuple[list[tuple[Batch, int]], dict]:
    """Batches the user may see, each with its allocated-student count."""
    stmt = batches_repo.list_stmt(filters, scope.visible_branch_ids(), scope.visible_batch_ids())
    batches, meta = paginate(stmt, page, per_page)
    counts = batches_repo.allocated_counts([b.batch_id for b in batches])
    return [(b, counts.get(b.batch_id, 0)) for b in batches], meta


def get_batch(batch_id: int) -> tuple[Batch, int]:
    batch = batches_repo.get_batch(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    return batch, batches_repo.allocated_counts([batch_id]).get(batch_id, 0)


def get_batch_detail(batch_id: int) -> BatchDetail:
    """Detail with delivery counts; trainer history and the change log are for staff only, never the learners of the batch."""
    batch, allocated = get_batch(batch_id)
    staff = not delivery_access.is_student_only()
    return BatchDetail(
        batch=batch,
        allocated_count=allocated,
        session_counts=sessions_repo.state_counts_by_batch([batch_id]).get(batch_id, {"delivered": 0, "upcoming": 0, "cancelled": 0}),
        trainer_history=batches_repo.trainer_history(batch_id) if staff else [],
        events=batches_repo.events(batch_id) if staff else [],
        successions=_successions_of(batch_id) if staff else [],
        handovers=list(db.session.execute(select(BatchHandover).where(BatchHandover.batch_id == batch_id)).scalars()) if staff else [],
    )


def _successions_of(batch_id: int) -> list[BatchSuccession]:
    """Merge / split links in and out of the batch, newest first (Module 15 §17)."""
    stmt = (select(BatchSuccession).where((BatchSuccession.from_batch_id == batch_id) | (BatchSuccession.to_batch_id == batch_id))
            .order_by(BatchSuccession.requested_at.desc()))
    return list(db.session.execute(stmt).scalars())


def load_managed_batch(batch_id: int) -> Batch:
    """The batch, row-locked, for a change: 404 outside the user's scope, 403 when they may only look."""
    batch = batches_repo.get_batch_for_update(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    delivery_access.assert_can_manage_branch(batch.branch_id)
    return batch


TIMETABLE_FIELDS = ("schedule_days", "start_time", "end_time", "location")
# Descriptive fields any manager may edit while the batch is open
PLAIN_FIELDS = ("display_name", "batch_type", "schedule_pattern", "recording_provision", "recording_terms", "meet_series_link",
                "meet_space_id", "calendar_series_id")
CAPACITY_SIDES = ("classroom_capacity", "lab_capacity", "online_capacity")


def _snapshot(batch: Batch) -> dict:
    return {"capacity": batch.capacity, "mode": batch.mode, "planned_start": batch.planned_start, "planned_end": batch.planned_end,
            "curriculum_version_id": batch.curriculum_version_id, "state": batch.state, "readiness": batch.readiness,
            "schedule_days": batch.schedule_days, "start_time": batch.start_time, "end_time": batch.end_time,
            "location": batch.location, **{f: getattr(batch, f) for f in PLAIN_FIELDS + CAPACITY_SIDES}}


def check_capacity_sides(mode: str, capacity: int, sides: dict) -> None:
    """Seats never exceed the verified resources of the mode (Module 15 §7): a classroom by its room and lab positions, an
    online batch by its verified online capacity, a hybrid batch by both sides together. A side not yet given isn't checked."""
    classroom, lab, online = (sides.get(f) for f in CAPACITY_SIDES)
    if mode == "Classroom":
        limits = [(c, f) for c, f in ((classroom, "classroom_capacity"), (lab, "lab_capacity")) if c is not None]
    elif mode == "Live Online":
        limits = [(online, "online_capacity")] if online is not None else []
    else:
        limits = [(classroom + online, "online_capacity")] if classroom is not None and online is not None else []
    for limit, field in limits:
        if capacity > limit:
            raise ValidationError("Capacity is more than the verified resources",
                                  {"capacity": [f"{capacity} seats but only {limit} verified ({field.replace('_', ' ')})"]})


def _apply_timetable(batch: Batch, data: dict) -> None:
    """Days, times and room. Start and end come together, the end after the start; a Live Online batch has no room."""
    for field in TIMETABLE_FIELDS:
        if field in data:
            setattr(batch, field, data[field])
    if (batch.start_time is None) != (batch.end_time is None):
        raise ValidationError("Invalid request data", {"end_time" if batch.end_time is None else "start_time":
                                                       ["Give both the start and the end time, or neither"]})
    if batch.start_time is not None and batch.end_time <= batch.start_time:
        raise ValidationError("Invalid request data", {"end_time": ["Must be after the start time"]})
    if batch.mode == "Live Online":
        batch.location = None


# ---------------------------------------------------------------- readiness

def readiness_checks(batch: Batch, allocated: int) -> list[dict]:
    """What has to be true before a batch can start, each check pass / fail / pending with what to do about it."""
    checks = []
    version = batch.curriculum_version
    if version is None:
        checks.append({"key": "curriculum", "label": "Curriculum version", "status": "warn", "detail": NO_CURRICULUM})
    elif version.status not in PUBLISHED_STATUSES:
        checks.append({"key": "curriculum", "label": "Curriculum version", "status": "fail",
                       "detail": f"{version.version_label} is {version.status} and not yet approved"})
    else:
        checks.append({"key": "curriculum", "label": "Curriculum version", "status": "pass", "detail": f"{version.version_label} ({version.status})"})

    lead = batches_repo.lead_trainer(batch.batch_id)
    checks.append({"key": "trainer", "label": "Lead trainer", "status": "pass" if lead else "fail",
                   "detail": lead.trainer.full_name if lead else "No lead trainer assigned"})
    checks.append({"key": "capacity", "label": "Capacity", "status": "pass", "detail": f"{allocated} of {batch.capacity} seats taken"})

    counts = sessions_repo.state_counts_by_batch([batch.batch_id]).get(batch.batch_id, {"upcoming": 0})
    checks.append({"key": "schedule", "label": "Class schedule", "status": "pass" if counts["upcoming"] else "pending",
                   "detail": f"{counts['upcoming']} upcoming class session(s)" if counts["upcoming"] else "No class sessions scheduled yet"})

    if batch.mode == "Classroom":
        checks.append({"key": "meet", "label": "Meet organizer", "status": "pass", "detail": "Classroom batch — no Meet needed"})
    else:
        verified = meet.is_verified()
        checks.append({"key": "meet", "label": "Meet organizer", "status": "pass" if verified else "pending",
                       "detail": f"{batch.branch.mailbox} — " + ("Verified" if verified else "Pending Verification") + f" ({meet.integration_note()})"})
    return checks


def suggested_readiness(batch: Batch, checks: list[dict]) -> dict:
    """The readiness the checks add up to: Blocked while a required check fails, Pending Verification while Meet is unverified."""
    failing = [c["detail"] for c in checks if c["status"] == "fail"]
    if failing:
        return {"readiness": "Blocked", "readiness_reason": "; ".join(failing),
                "recovery_owner": f"Branch Manager {batch.branch.branch_name}"}
    if any(c["key"] == "meet" and c["status"] == "pending" for c in checks):
        return {"readiness": "Pending Verification", "readiness_reason": "Meet organizer Pending Verification", "recovery_owner": "Super Admin"}
    return {"readiness": "Ready", "readiness_reason": None, "recovery_owner": None}


def readiness_report(batch_id: int) -> dict:
    batch, allocated = get_batch(batch_id)
    if delivery_access.is_student_only():
        raise NotFound("Batch not found")
    checks = readiness_checks(batch, allocated)
    return {"batch_id": batch.batch_id, "readiness": batch.readiness, "readiness_reason": batch.readiness_reason,
            "recovery_owner": batch.recovery_owner, "checks": checks, "suggested": suggested_readiness(batch, checks),
            "checklist": confirmation_checklist(batch)}


# ---------------------------------------------------------------- the 7-point readiness record (Module 15 §5)

def _item(key: str, label: str, status: str, detail: str) -> dict:
    """status: pass; warn (advisory: the Branch Manager may confirm with a recorded reason); pending (missing); fail."""
    return {"key": key, "label": label, "status": status, "detail": detail}


def _course_item(batch: Batch) -> dict:
    version = batch.curriculum_version
    label = "1. Course and curriculum version"
    if version is None:
        return _item("course_version", label, "warn", NO_CURRICULUM)
    if version.status not in PUBLISHED_STATUSES:
        return _item("course_version", label, "fail", f"{version.version_label} is {version.status}")
    if batch.component_id is None and batch.course.is_combo:
        pinned = {p.component_id for p in catalog_repo.version_components(version.curriculum_version_id)}
        missing = [c.track_code for c in catalog_repo.components_of(batch.course_id) if c.component_id not in pinned]
        if missing:
            return _item("course_version", label, "fail", f"{version.version_label} does not pin {', '.join(missing)}")
    what = f"{batch.component.track_code} of {batch.course.course_code}" if batch.component else batch.course.course_code
    return _item("course_version", label, "pass", f"{what} · {version.version_label} ({version.status})")


def _people_item(batch: Batch) -> dict:
    label = "2. Branch Manager, trainer and cover"
    missing = []
    if not users_repo.user_ids_with_role("BRANCH_MANAGER", batch.branch_id):
        missing.append("no Branch Manager at the branch")
    live = [t for t in batch.trainers if t.to_date is None]
    lead = next((t for t in live if t.role == "Lead"), None)
    if lead is None:
        missing.append("no lead trainer")
    if missing:
        return _item("people", label, "fail", "; ".join(missing))
    if batch.mode == "Hybrid" and len(live) < 2:
        return _item("people", label, "pending", f"{lead.trainer.full_name} leads; a hybrid batch needs a second trainer for remote learners")
    return _item("people", label, "pass", f"Lead {lead.trainer.full_name}" + (f" + {len(live) - 1} more" if len(live) > 1 else ""))


def _timetable_item(batch: Batch) -> dict:
    label = "3. Start, timetable, planned hours and end"
    missing = [name for name, value in (("start date", batch.planned_start), ("end date", batch.planned_end),
                                        ("teaching days", batch.schedule_days), ("class times", batch.start_time)) if not value]
    if missing:
        return _item("timetable", label, "pending", "Missing " + ", ".join(missing))
    from services import curriculum  # curriculum imports batches

    totals = curriculum.totals(batch.curriculum_version) if batch.curriculum_version else None
    hours = (f"{round(totals['instructional_minutes'] / 60, 1)} instructional hours" if totals and totals["hours_verified"]
             else "planned hours Pending")
    days = ", ".join(WEEKDAYS[d - 1] for d in sorted(batch.schedule_days))
    return _item("timetable", label, "pass", f"{batch.planned_start} to {batch.planned_end}, {days} "
                 f"{batch.start_time:%H:%M}–{batch.end_time:%H:%M}; {hours}")


def _resources_item(batch: Batch) -> dict:
    label = "4. Room / online arrangements and verified capacity"
    missing = []
    if batch.mode in ("Classroom", "Hybrid"):
        if not batch.location:
            missing.append("classroom")
        if batch.classroom_capacity is None:
            missing.append("verified classroom seats")
    if batch.mode in ("Live Online", "Hybrid") and batch.online_capacity is None:
        missing.append("verified online capacity")
    if missing:
        return _item("resources", label, "pending", "Missing " + ", ".join(missing))
    try:
        check_capacity_sides(batch.mode, batch.capacity, {f: getattr(batch, f) for f in CAPACITY_SIDES})
    except ValidationError as exc:
        return _item("resources", label, "fail", exc.details["capacity"][0])
    sides = ", ".join(f"{f.split('_')[0]} {getattr(batch, f)}" for f in CAPACITY_SIDES if getattr(batch, f) is not None)
    online = f"; organizer {batch.branch.mailbox} ({meet.integration_note()})" if batch.mode != "Classroom" else ""
    return _item("resources", label, "pass", f"{batch.capacity} seats ({sides}){online}")


def _conflicts_item(batch: Batch) -> dict:
    """Holidays, trainer and room availability and the students' other classes (Module 15 §10)."""
    label = "5. Holidays, trainer, room and student timetable checks"
    if not batch.schedule_days or batch.start_time is None:
        return _item("conflicts", label, "pending", "Set the timetable first")
    trainer_ids = [t.trainer_user_id for t in batch.trainers if t.to_date is None]
    clashes = batches_repo.timetable_overlaps(batch, batches_repo.batch_ids_taught_by(trainer_ids)) if trainer_ids else []
    if clashes:
        return _item("conflicts", label, "fail", "A trainer already teaches " + ", ".join(b.batch_code for b in clashes) + " at these times")
    notes, status = [], "pass"
    if batch.location:
        rooms = batches_repo.timetable_overlaps(batch, batches_repo.batch_ids_in_room(batch.branch_id, batch.location))
        if rooms:
            status = "warn"
            notes.append(f"{batch.location} is also booked by " + ", ".join(b.batch_code for b in rooms))
    students = [e.student_id for _, e in batches_repo.active_allocation_rows(batch.batch_id)]
    if students:
        theirs = batches_repo.timetable_overlaps(batch, batches_repo.batch_ids_of_students(students, batch.batch_id))
        if theirs:
            status = "warn"
            notes.append("allocated students also attend " + ", ".join(b.batch_code for b in theirs) + " at these times")
    if batch.planned_start and batch.planned_end:
        closures = db.session.execute(select(func.count()).select_from(CalendarClosure).where(
            CalendarClosure.in_force(), CalendarClosure.starts_on <= batch.planned_end, CalendarClosure.ends_on >= batch.planned_start,
            (CalendarClosure.branch_id.is_(None)) | (CalendarClosure.branch_id == batch.branch_id))).scalar_one()
        notes.append(f"{closures} approved closure(s) in the planned dates" if closures else "no approved closures in the planned dates")
    return _item("conflicts", label, status, "; ".join(notes) or "No conflicts found")


def _recording_item(batch: Batch) -> dict:
    label = "6. Recording provision"
    if batch.recording_provision is None:
        return _item("recording", label, "pending", "State Included, Not Included or Limited")
    terms = f": {batch.recording_terms}" if batch.recording_terms else ""
    return _item("recording", label, "pass", batch.recording_provision + terms)


def _approval_item(batch: Batch) -> dict:
    label = "7. Branch Manager confirmation"
    if batch.confirmed_at is not None:
        who = batch.confirmer.full_name if batch.confirmer else "earlier rules"
        return _item("approval", label, "pass", f"Confirmed by {who}")
    if batch.proposed_at is not None:
        return _item("approval", label, "pending", f"Proposed by {batch.proposer.full_name}; awaiting the Branch Manager")
    return _item("approval", label, "pending", "Not yet proposed")


def confirmation_checklist(batch: Batch) -> list[dict]:
    return [_course_item(batch), _people_item(batch), _timetable_item(batch), _resources_item(batch), _conflicts_item(batch),
            _recording_item(batch), _approval_item(batch)]


def _checklist_blockers(checklist: list[dict]) -> tuple[list[str], list[str]]:
    """Items 1-6 that still block (fail / pending) and the advisory warnings."""
    review = [c for c in checklist if c["key"] != "approval"]
    return ([f"{c['label']}: {c['detail']}" for c in review if c["status"] in ("fail", "pending")],
            [f"{c['label']}: {c['detail']}" for c in review if c["status"] == "warn"])


def apply_readiness(batch: Batch, readiness: str, reason: str | None, owner: str | None, *, note: str | None = None) -> None:
    """Store a readiness value and log the change (no checks: callers decide whether the value is allowed)."""
    if (batch.readiness, batch.readiness_reason, batch.recovery_owner) == (readiness, reason, owner):
        return
    old = batch.readiness
    batch.readiness, batch.readiness_reason, batch.recovery_owner = readiness, reason, owner
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "Readiness changed", from_value=old, to_value=readiness, reason=note or reason,
                           actor_user_id=actor_id())


def set_readiness(batch_id: int, readiness: str, reason: str | None, recovery_owner: str | None) -> Batch:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    if readiness == "Ready":
        checks = readiness_checks(batch, batches_repo.allocated_counts([batch_id]).get(batch_id, 0))
        failing = [c["detail"] for c in checks if c["status"] == "fail"]
        if failing:
            raise BusinessRule("The batch cannot be marked Ready yet: " + "; ".join(failing))
        reason = owner = None
    else:
        if not reason:
            raise ValidationError("A reason is required", {"readiness_reason": ["Required when the batch is not Ready"]})
        owner = recovery_owner
        if readiness == "Blocked" and not owner:
            raise ValidationError("A recovery owner is required", {"recovery_owner": ["Required when the batch is Blocked"]})
    old = _snapshot(batch)
    apply_readiness(batch, readiness, reason, owner)
    audit.record("BATCH_READINESS", "batch", batch.batch_id, old={"readiness": old["readiness"]}, new={"readiness": readiness, "reason": reason},
                 branch_id=batch.branch_id)
    return batch


# ---------------------------------------------------------------- create / update

def _validate_version(course_id: int, version_id: int, component_id: int | None = None) -> None:
    version = catalog_repo.get_curriculum_version(version_id)
    if version is None or version.course_id != course_id or version.component_id != component_id:
        what = "this track" if component_id else "this course"
        raise ValidationError("Invalid curriculum version", {"curriculum_version_id": [f"Not a curriculum version of {what}"]})
    if version.status not in PUBLISHED_STATUSES:
        raise ValidationError("Invalid curriculum version", {"curriculum_version_id": [f"{version.version_label} is {version.status}; use an approved version"]})


def _validate_component(course, component_id: int | None) -> None:
    """A track batch teaches one main track (or the booster) of a combo course (Module 15 §4)."""
    if component_id is None:
        return
    component = catalog_repo.get_component(component_id)
    if component is None or component.parent_course_id != course.course_id:
        raise ValidationError("Invalid track", {"component_id": [f"Not a track of {course.course_code}"]})


def create_batch(data: dict) -> Batch:
    """A new batch in Forming (Draft). The Active curriculum version of the course (or track) is used unless one is chosen;
    readiness is worked out from the checks."""
    course = catalog_repo.get_course(data["course_id"])
    if course is None or course.status != "Active":
        raise ValidationError("Unknown course", {"course_id": ["Not an active course"]})
    branch = branches_repo.get_by_id(data["branch_id"])
    if branch is None or not branch.is_active:
        raise ValidationError("Unknown branch", {"branch_id": ["Not an active branch"]})
    delivery_access.assert_can_manage_branch(branch.branch_id)
    component_id = data.get("component_id")
    _validate_component(course, component_id)

    version_id = (data["curriculum_version_id"] if "curriculum_version_id" in data
                  else catalog_repo.active_curriculum_version_id(course.course_id, component_id))
    if version_id is not None:
        _validate_version(course.course_id, version_id, component_id)
    mode = data.get("mode", "Classroom")
    check_capacity_sides(mode, data["capacity"], data)

    batch = Batch(course_id=course.course_id, branch_id=branch.branch_id, curriculum_version_id=version_id, capacity=data["capacity"],
                  mode=mode, planned_start=data.get("planned_start"), planned_end=data.get("planned_end"),
                  crm_batch_id=data.get("crm_batch_id"), component_id=component_id,
                  **{f: data[f] for f in PLAIN_FIELDS + CAPACITY_SIDES if f in data})
    _apply_timetable(batch, data)
    db.session.add(batch)
    db.session.flush()
    db.session.refresh(batch)
    checks = readiness_checks(batch, 0)
    suggestion = suggested_readiness(batch, checks)
    batch.readiness, batch.readiness_reason, batch.recovery_owner = (suggestion["readiness"], suggestion["readiness_reason"], suggestion["recovery_owner"])
    batches_repo.add_event(batch.batch_id, "Created", to_value=batch.state, actor_user_id=actor_id())
    audit.record("BATCH_CREATED", "batch", batch.batch_id, new={**_snapshot(batch), "batch_code": batch.batch_code}, branch_id=batch.branch_id)
    db.session.flush()
    return batch


def _material_edits(batch: Batch, data: dict) -> list[str]:
    """Changes to an agreed plan that need each student's agreement first (Module 15 §14): the start, mode, teaching days
    and times, or an end-date extension past material_end_extension_days, once students hold seats in a confirmed batch."""
    if batch.state in ("Forming", "Proposed") or not batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id):
        return []
    changed = [f for f in MATERIAL_FIELDS if f in data and data[f] != getattr(batch, f)]
    if "planned_end" in data and data["planned_end"] and batch.planned_end and \
            (data["planned_end"] - batch.planned_end).days > settings_repo.get_int("material_end_extension_days", 7):
        changed.append("planned_end")
    return changed


def _withdraw_proposal(batch: Batch, why: str) -> None:
    """A proposed batch that is edited goes back to Draft: the Branch Manager reviews and proposes it again."""
    if batch.state != "Proposed":
        return
    batch.state, batch.proposed_by, batch.proposed_at = "Forming", None, None
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "State changed", from_value="Proposed", to_value="Forming", reason=why, actor_user_id=actor_id())


def update_batch(batch_id: int, data: dict) -> Batch:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state} and can no longer be edited")
    material = _material_edits(batch, data)
    if material:
        raise BusinessRule(f"Changing {', '.join(sorted(set(material)))} is a material change for the students of {batch.batch_code}: "
                           "record it as a material change and get each student's agreement first", {"material": material})
    if "capacity" in data and data["capacity"] > batch.capacity and batch.state != "Forming":
        raise BusinessRule("A capacity increase on a proposed or confirmed batch needs resource validation, academic review and the "
                           "Branch Manager's approval: request it as a capacity change")
    old = _snapshot(batch)

    if "component_id" in data and data["component_id"] != batch.component_id:
        if batch.state != "Forming" or batches_repo.allocated_counts([batch_id]).get(batch_id):
            raise BusinessRule("The track of a batch can only change while it is a Draft with no students")
        _validate_component(batch.course, data["component_id"])
        batch.component_id = data["component_id"]
        if "curriculum_version_id" not in data:
            data["curriculum_version_id"] = catalog_repo.active_curriculum_version_id(batch.course_id, data["component_id"])
    if "curriculum_version_id" in data and data["curriculum_version_id"] != batch.curriculum_version_id:
        if batch.state not in ("Forming", "Proposed", "Starting"):
            raise BusinessRule("The curriculum version can only change before the batch is Running; use an academic mapping for running batches")
        if data["curriculum_version_id"] is not None:
            _validate_version(batch.course_id, data["curriculum_version_id"], batch.component_id)
        batch.curriculum_version_id = data["curriculum_version_id"]
        batches_repo.add_event(batch.batch_id, "Curriculum changed", from_value=str(old["curriculum_version_id"]),
                               to_value=str(data["curriculum_version_id"]), actor_user_id=actor_id())
    for field in ("capacity", "mode", "planned_start", "planned_end", *PLAIN_FIELDS, *CAPACITY_SIDES):
        if field in data:
            setattr(batch, field, data[field])
    _apply_timetable(batch, data)
    check_capacity_sides(batch.mode, batch.capacity, {f: getattr(batch, f) for f in CAPACITY_SIDES})
    db.session.flush()
    if "capacity" in data and data["capacity"] != old["capacity"]:
        batches_repo.add_event(batch.batch_id, "Capacity changed", from_value=str(old["capacity"]), to_value=str(data["capacity"]),
                               actor_user_id=actor_id())
    new = _snapshot(batch)
    if any(new[k] != old[k] for k in new if k not in ("display_name", "state", "readiness")):
        _withdraw_proposal(batch, "Edited after it was proposed")
    sync_full(batch)
    audit.record("BATCH_UPDATED", "batch", batch.batch_id, old=old, new=_snapshot(batch), branch_id=batch.branch_id)
    return batch


# ---------------------------------------------------------------- lifecycle

def sync_full(batch: Batch) -> None:
    """A Running batch is Full exactly when every seat is taken."""
    if batch.state not in ("Running", "Full"):
        return
    taken = batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0)
    target = "Full" if taken >= batch.capacity else "Running"
    if target != batch.state:
        old = batch.state
        batch.state = target
        db.session.flush()
        batches_repo.add_event(batch.batch_id, "State changed", from_value=old, to_value=target,
                               reason="All seats taken" if target == "Full" else "A seat is free again", actor_user_id=actor_id())


def _set_state(batch: Batch, state: str, reason: str | None, event: str = "State changed") -> None:
    old = batch.state
    batch.state = state
    db.session.flush()  # the database validates the move and raises a readable message
    batches_repo.add_event(batch.batch_id, event, from_value=old, to_value=state, reason=reason, actor_user_id=actor_id())
    audit.record("BATCH_STATE", "batch", batch.batch_id, old={"state": old}, new={"state": state}, reason=reason, branch_id=batch.branch_id)


def _require_confirmer(batch: Batch) -> None:
    if not current_user().has_role(*CONFIRM_ROLES, branch_id=batch.branch_id):
        raise Forbidden("Only the Branch Manager of this branch or a Super Admin can do this")


def propose(batch_id: int, note: str | None) -> Batch:
    """The review is done: points 1-6 of the readiness record pass, so the batch is proposed for confirmation."""
    batch = load_managed_batch(batch_id)
    if batch.state != "Forming":
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}; only a Draft batch can be proposed")
    blockers, _ = _checklist_blockers(confirmation_checklist(batch))
    if blockers:
        raise BusinessRule("The readiness record is not complete: " + "; ".join(blockers), {"blocking": blockers})
    batch.proposed_by, batch.proposed_at, batch.proposal_note = actor_id(), datetime.now(timezone.utc), note
    _set_state(batch, "Proposed", note, "Proposed")
    db.session.expire(batch, ["proposer"])
    delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", batch.branch_id), category="Batch", action_required=True,
                                  title=f"Confirm batch {batch.batch_code}", body=f"{batch.course.title}. Proposed by {current_user().full_name}.",
                                  event_key=f"batch-proposed-{batch.batch_id}-{int(batch.proposed_at.timestamp())}",
                                  link="/branch/batches", branch_id=batch.branch_id)
    return batch


def decide_confirmation(batch_id: int, decision: str, note: str | None, override_reason: str | None) -> Batch:
    """The Branch Manager (or Super Admin) confirms the delivery commitment (Proposed -> Confirmed) or
    returns it to Draft. Advisory warnings need a recorded reason; failing or missing points cannot be overridden."""
    batch = load_managed_batch(batch_id)
    _require_confirmer(batch)
    if batch.state != "Proposed":
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}, not Proposed")
    if decision == "Returned":
        if not note:
            raise ValidationError("A reason is required", {"note": ["Say what has to change"]})
        batch.proposed_by = batch.proposed_at = None
        _set_state(batch, "Forming", note, "Returned")
        return batch

    checklist = confirmation_checklist(batch)
    blockers, warnings = _checklist_blockers(checklist)
    if blockers:
        raise BusinessRule("The batch cannot be confirmed: " + "; ".join(blockers), {"blocking": blockers})
    if warnings and not override_reason:
        raise BusinessRule("Record why the warnings are acceptable: " + "; ".join(warnings), {"warnings": warnings})
    batch.confirmed_by, batch.confirmed_at = actor_id(), datetime.now(timezone.utc)
    batch.confirmation_checklist = [*checklist[:-1], _item("approval", checklist[-1]["label"], "pass", f"Confirmed by {current_user().full_name}"
                                                        + (f"; warnings accepted: {override_reason}" if warnings else ""))]
    _set_state(batch, "Starting", "; ".join(x for x in (note, override_reason and f"Override: {override_reason}") if x), "Confirmed")
    db.session.expire(batch, ["confirmer"])
    return batch


def confirm_batch(batch_id: int, note: str | None, override_reason: str | None) -> Batch:
    """Propose and confirm in one step: the Branch Manager decides alone, so a Draft batch whose readiness record passes is
    proposed (no notice: they are the one who would be asked) and confirmed together. A Proposed batch is just confirmed.
    Advisory warnings need `override_reason`, which is audited with the confirmation."""
    batch = load_managed_batch(batch_id)
    _require_confirmer(batch)
    if batch.state == "Forming":
        blockers, _ = _checklist_blockers(confirmation_checklist(batch))
        if blockers:
            raise BusinessRule("The batch cannot be confirmed yet: " + "; ".join(blockers), {"blocking": blockers})
        batch.proposed_by, batch.proposed_at, batch.proposal_note = actor_id(), datetime.now(timezone.utc), note
        _set_state(batch, "Proposed", note, "Proposed")
        db.session.expire(batch, ["proposer"])
    # the stored readiness was worked out when the batch was created (no trainer yet, say): bring it up to date before the batch may start
    suggestion = suggested_readiness(batch, readiness_checks(batch, batches_repo.allocated_counts([batch_id]).get(batch_id, 0)))
    if suggestion["readiness"] != "Blocked":
        apply_readiness(batch, suggestion["readiness"], suggestion["readiness_reason"], suggestion["recovery_owner"], note="Updated when the batch was confirmed")
    return decide_confirmation(batch_id, "Confirmed", note, override_reason)


def completion_blockers(batch: Batch) -> list[str]:
    """What still stands between the batch and Completed (Module 15 §19): replacements owed, open disruptions, pending
    requests, and students still owed teaching without a named owner, plan and destination."""
    blockers = []
    open_sessions = sessions_repo.state_counts_by_batch([batch.batch_id]).get(batch.batch_id, {}).get("upcoming", 0)
    if open_sessions:
        blockers.append(f"{open_sessions} open class session(s); deliver or cancel them before completing the batch")
    owed = sessions_repo.replacements_owed(batch.batch_id)
    if owed:
        blockers.append(f"{len(owed)} cancelled class(es) still owe a replacement or a recorded waiver ({', '.join(owed[:5])})")
    disruptions = db.session.execute(select(func.count()).select_from(SessionDisruption).join(
        ClassSession, ClassSession.session_id == SessionDisruption.session_id).where(
        ClassSession.batch_id == batch.batch_id, SessionDisruption.status == "Open")).scalar_one()
    if disruptions:
        blockers.append(f"{disruptions} class disruption(s) without a recovery plan")
    blockers += _pending_requests(batch.batch_id)
    handed = set(db.session.execute(select(BatchHandover.enrolment_id).where(BatchHandover.batch_id == batch.batch_id)).scalars())
    owing = [e.enrolment_code for _, e in batches_repo.active_allocation_rows(batch.batch_id)
             if e.status in OWING_STATUSES and e.enrolment_id not in handed]
    if owing:
        blockers.append(f"{len(owing)} student(s) still owed teaching need a handover (owner, plan, destination): {', '.join(owing[:5])}")
    return blockers


def _pending_requests(batch_id: int) -> list[str]:
    pending = []
    for model, label, cond in (
        (BatchTransferRequest, "transfer request(s)",
         (BatchTransferRequest.status == "Pending") & ((BatchTransferRequest.from_batch_id == batch_id) | (BatchTransferRequest.to_batch_id == batch_id))),
        (MaterialChange, "material change(s)", (MaterialChange.batch_id == batch_id) & MaterialChange.status.in_(("Pending Approval", "Awaiting Agreement"))),
        (BatchSuccession, "merge / split request(s)",
         (BatchSuccession.status == "Pending") & ((BatchSuccession.from_batch_id == batch_id) | (BatchSuccession.to_batch_id == batch_id))),
        (BatchCapacityRequest, "capacity request(s)", (BatchCapacityRequest.batch_id == batch_id) & (BatchCapacityRequest.status == "Pending")),
    ):
        count = db.session.execute(select(func.count()).select_from(model).where(cond)).scalar_one()
        if count:
            pending.append(f"{count} pending {label}")
    return pending


def archive_blockers(batch: Batch) -> list[str]:
    """Archive only once the batch manages no live activity: every student finished, withdrew or moved on, no request is
    pending and no recording promise is still open (Module 15 §19)."""
    blockers = _pending_requests(batch.batch_id)
    live = [e.enrolment_code for _, e in batches_repo.active_allocation_rows(batch.batch_id) if e.status not in ("Completed", "Withdrawn")]
    if live:
        blockers.append(f"{len(live)} student(s) still study in this batch ({', '.join(live[:5])}); move them to a successor first")
    open_recordings = db.session.execute(select(func.count()).select_from(RecordingException).join(
        ClassSession, ClassSession.session_id == RecordingException.session_id).where(
        ClassSession.batch_id == batch.batch_id, RecordingException.status != "Resolved")).scalar_one()
    if open_recordings:
        blockers.append(f"{open_recordings} recording issue(s) still open")
    return blockers


def transition(batch_id: int, state: str, reason: str | None) -> Batch:
    """Running, On Hold, Resume (back to the state before the hold), Completed, Cancelled, Archived."""
    batch = load_managed_batch(batch_id)
    if state in ("On Hold", "Archived", "Resume"):
        _require_confirmer(batch)
    if state in ("On Hold", "Cancelled") and not reason:
        raise ValidationError("A reason is required", {"reason": [f"Required to put a batch {'on hold' if state == 'On Hold' else 'Cancelled'}"]})
    if state in ("Starting", "Proposed"):
        raise BusinessRule("Propose the batch and have the Branch Manager confirm it")
    if state == "Running":
        if batches_repo.lead_trainer(batch.batch_id) is None:
            raise BusinessRule(f"Batch {batch.batch_code} needs a lead trainer before it can start")
    if state == "Completed":
        blockers = completion_blockers(batch)
        if blockers:
            raise BusinessRule(f"Batch {batch.batch_code} cannot be completed: " + "; ".join(blockers), {"blocking": blockers})
    if state == "Archived":
        blockers = archive_blockers(batch)
        if blockers:
            raise BusinessRule(f"Batch {batch.batch_code} cannot be archived: " + "; ".join(blockers), {"blocking": blockers})

    if state == "On Hold":
        if batch.state not in ("Proposed", "Starting", "Running", "Full"):
            raise BusinessRule(f"Batch {batch.batch_code} is {batch.state} and cannot be put on hold")
        batch.held_from_state = batch.state
    tell_students = state in ("On Hold", "Resume", "Cancelled")
    if state == "Resume":
        if batch.state != "On Hold":
            raise BusinessRule(f"Batch {batch.batch_code} is not On Hold")
        state = batch.held_from_state
    _set_state(batch, state, reason)
    if batch.state != "On Hold":
        batch.held_from_state = None
    if tell_students:
        delivery_notices.notify_batch_students(batch.batch_id, category="Batch", title=f"Batch {batch.batch_code}: {BATCH_STATE_LABELS[batch.state]}",
                                               body=f"{batch.course.title}. {reason or ''}".strip(), link="/my-courses",
                                               event_key=f"batch-state-{batch.batch_id}-{batch.state}-{int(datetime.now().timestamp())}",
                                               branch_id=batch.branch_id)
    sync_full(batch)
    return batch


def record_handover(batch_id: int, data: dict) -> BatchHandover:
    """A named owner, plan and destination for a student the batch still owes teaching (paused, deferred, not started)."""
    batch = load_managed_batch(batch_id)
    seat = next(((a, e) for a, e in batches_repo.active_allocation_rows(batch.batch_id) if e.enrolment_id == data["enrolment_id"]), None)
    if seat is None:
        raise ValidationError("Not in this batch", {"enrolment_id": ["The student holds no seat in this batch"]})
    if data.get("destination_batch_id"):
        destination = batches_repo.get_batch(data["destination_batch_id"])
        if destination is None or destination.batch_id == batch.batch_id:
            raise ValidationError("Invalid destination", {"destination_batch_id": ["Another batch"]})
    if data["owner_user_id"] not in _branch_managers(batch.branch_id):
        raise ValidationError("Invalid owner", {"owner_user_id": ["The owner must be a Branch Manager of this branch"]})
    handover = db.session.execute(select(BatchHandover).where(BatchHandover.batch_id == batch_id,
                                                              BatchHandover.enrolment_id == data["enrolment_id"])).scalar_one_or_none()
    if handover is None:
        handover = BatchHandover(batch_id=batch_id, enrolment_id=data["enrolment_id"], recorded_by=actor_id())
        db.session.add(handover)
    handover.owner_user_id, handover.plan, handover.destination = data["owner_user_id"], data["plan"], data["destination"]
    handover.destination_batch_id, handover.recorded_by = data.get("destination_batch_id"), actor_id()
    db.session.flush()
    batches_repo.add_event(batch_id, "Handover recorded", to_value=seat[1].enrolment_code, reason=data["plan"], actor_user_id=actor_id())
    audit.record("BATCH_HANDOVER", "batch", batch_id, new={"enrolment_id": data["enrolment_id"], "owner_user_id": data["owner_user_id"],
                                                           "destination": data["destination"]}, branch_id=batch.branch_id)
    return handover


def _branch_managers(branch_id: int) -> set[int]:
    """Users who manage delivery at the branch: its Branch Managers, and Super Admins."""
    return {u for role in delivery_access.MANAGE_ROLES for u in users_repo.user_ids_with_role(role, branch_id)}


# ---------------------------------------------------------------- trainers

def assign_trainer(batch_id: int, trainer_user_id: int, role: str, from_date) -> BatchTrainer:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    live = {t.trainer_user_id: t for t in batch.trainers if t.to_date is None}
    if trainer_user_id in live:
        raise Conflict(f"{live[trainer_user_id].trainer.full_name} is already assigned to this batch")
    lead = batches_repo.lead_trainer(batch.batch_id)
    if role == "Lead" and lead is not None:
        raise BusinessRule(f"{lead.trainer.full_name} is already the lead trainer; make them Co-trainer or end their assignment first")

    assignment = BatchTrainer(batch_id=batch.batch_id, trainer_user_id=trainer_user_id, role=role, from_date=from_date or today_ist())
    db.session.add(assignment)
    db.session.flush()  # the database checks the person holds the Trainer role at this branch
    db.session.refresh(batch)
    batches_repo.add_event(batch.batch_id, "Trainer assigned", to_value=f"{assignment.trainer.full_name} ({role})", actor_user_id=actor_id())
    audit.record("BATCH_TRAINER_ASSIGNED", "batch", batch.batch_id, new={"trainer_user_id": trainer_user_id, "role": role}, branch_id=batch.branch_id)
    delivery_notices.notify_users([trainer_user_id], title=f"You are assigned to batch {batch.batch_code}", category="Batch",
                                  body=f"{batch.course.title} · {role}", event_key=f"batch-trainer-{assignment.batch_trainer_id}",
                                  link="/trainer/batches", branch_id=batch.branch_id)
    return assignment


def _load_assignment(batch: Batch, batch_trainer_id: int) -> BatchTrainer:
    assignment = batches_repo.get_batch_trainer(batch_trainer_id)
    if assignment is None or assignment.batch_id != batch.batch_id or assignment.to_date is not None:
        raise NotFound("Trainer assignment not found")
    return assignment


def change_trainer_role(batch_id: int, batch_trainer_id: int, role: str) -> BatchTrainer:
    """Lead <-> Co-trainer. Making someone Lead demotes the current lead so there is always at most one."""
    batch = load_managed_batch(batch_id)
    assignment = _load_assignment(batch, batch_trainer_id)
    if assignment.role == role:
        return assignment
    if role == "Lead":
        current = batches_repo.lead_trainer(batch.batch_id)
        if current is not None:
            current.role = "Co-trainer"
            db.session.flush()  # free the one-lead slot first
            batches_repo.add_event(batch.batch_id, "Trainer role changed", from_value=f"{current.trainer.full_name} (Lead)",
                                   to_value=f"{current.trainer.full_name} (Co-trainer)", actor_user_id=actor_id())
    old_role = assignment.role
    assignment.role = role
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "Trainer role changed", from_value=f"{assignment.trainer.full_name} ({old_role})",
                           to_value=f"{assignment.trainer.full_name} ({role})", actor_user_id=actor_id())
    audit.record("BATCH_TRAINER_ROLE", "batch", batch.batch_id, old={"role": old_role}, new={"role": role, "trainer_user_id": assignment.trainer_user_id},
                 branch_id=batch.branch_id)
    return assignment


def end_trainer(batch_id: int, batch_trainer_id: int) -> BatchTrainer:
    """End an assignment today. Their upcoming sessions must be handed to another assigned trainer first."""
    batch = load_managed_batch(batch_id)
    assignment = _load_assignment(batch, batch_trainer_id)
    upcoming = sessions_repo.trainer_open_sessions(batch.batch_id, assignment.trainer_user_id)
    if upcoming:
        raise BusinessRule(f"{assignment.trainer.full_name} still teaches {len(upcoming)} upcoming session(s) of this batch; "
                           "assign another trainer to them first")
    assignment.to_date = max(today_ist(), assignment.from_date)
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "Trainer ended", from_value=f"{assignment.trainer.full_name} ({assignment.role})", actor_user_id=actor_id())
    audit.record("BATCH_TRAINER_ENDED", "batch", batch.batch_id, old={"trainer_user_id": assignment.trainer_user_id, "role": assignment.role},
                 branch_id=batch.branch_id)
    return assignment

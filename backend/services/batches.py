"""Batches: scoped reads, create / update, lifecycle, delivery readiness and trainer assignments.

Lifecycle: Forming -> Starting -> Running -> Completed, or Cancelled while nobody holds a seat. 'Full' is not chosen by
anyone: a Running batch flips to Full when its last seat is taken and back to Running when a seat frees up (`sync_full`).
The database enforces the same transitions; the checks here give readable messages first.
"""
from dataclasses import dataclass

from config.database import db
from config.timezone import today_ist
from models import Batch, BatchTrainer
from repositories import batches as batches_repo
from repositories import branches as branches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories.common import paginate
from services import audit, delivery_access, delivery_notices, meet, scope
from services.context import actor_id
from services.errors import BusinessRule, Conflict, NotFound, ValidationError

CLOSED_STATES = ("Completed", "Cancelled")
PUBLISHED_STATUSES = ("Approved", "Active")


@dataclass
class BatchDetail:
    batch: Batch
    allocated_count: int
    session_counts: dict[str, int]
    trainer_history: list[BatchTrainer]
    events: list


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
    )


def load_managed_batch(batch_id: int) -> Batch:
    """The batch, row-locked, for a change: 404 outside the user's scope, 403 when they may only look."""
    batch = batches_repo.get_batch_for_update(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    delivery_access.assert_can_manage_branch(batch.branch_id)
    return batch


TIMETABLE_FIELDS = ("schedule_days", "start_time", "end_time", "location")


def _snapshot(batch: Batch) -> dict:
    return {"capacity": batch.capacity, "mode": batch.mode, "planned_start": batch.planned_start, "planned_end": batch.planned_end,
            "curriculum_version_id": batch.curriculum_version_id, "state": batch.state, "readiness": batch.readiness,
            "schedule_days": batch.schedule_days, "start_time": batch.start_time, "end_time": batch.end_time,
            "location": batch.location}


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
        checks.append({"key": "curriculum", "label": "Curriculum version", "status": "fail",
                       "detail": f"Curriculum Mapping Pending: {batch.course.course_code} has no Active curriculum version"})
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
                "recovery_owner": f"Academic Coordinator {batch.branch.branch_name}"}
    if any(c["key"] == "meet" and c["status"] == "pending" for c in checks):
        return {"readiness": "Pending Verification", "readiness_reason": "Meet organizer Pending Verification", "recovery_owner": "Super Admin"}
    return {"readiness": "Ready", "readiness_reason": None, "recovery_owner": None}


def readiness_report(batch_id: int) -> dict:
    batch, allocated = get_batch(batch_id)
    if delivery_access.is_student_only():
        raise NotFound("Batch not found")
    checks = readiness_checks(batch, allocated)
    return {"batch_id": batch.batch_id, "readiness": batch.readiness, "readiness_reason": batch.readiness_reason,
            "recovery_owner": batch.recovery_owner, "checks": checks, "suggested": suggested_readiness(batch, checks)}


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

def _validate_version(course_id: int, version_id: int) -> None:
    version = catalog_repo.get_curriculum_version(version_id)
    if version is None or version.course_id != course_id or version.component_id is not None:
        raise ValidationError("Invalid curriculum version", {"curriculum_version_id": ["Not a curriculum version of this course"]})
    if version.status not in PUBLISHED_STATUSES:
        raise ValidationError("Invalid curriculum version", {"curriculum_version_id": [f"{version.version_label} is {version.status}; use an approved version"]})


def create_batch(data: dict) -> Batch:
    """A new batch in Forming. The Active curriculum version is used unless one is chosen; readiness is worked out from the checks."""
    course = catalog_repo.get_course(data["course_id"])
    if course is None or course.status != "Active":
        raise ValidationError("Unknown course", {"course_id": ["Not an active course"]})
    branch = branches_repo.get_by_id(data["branch_id"])
    if branch is None or not branch.is_active:
        raise ValidationError("Unknown branch", {"branch_id": ["Not an active branch"]})
    delivery_access.assert_can_manage_branch(branch.branch_id)

    version_id = data["curriculum_version_id"] if "curriculum_version_id" in data else catalog_repo.active_curriculum_version_id(course.course_id)
    if version_id is not None:
        _validate_version(course.course_id, version_id)

    batch = Batch(course_id=course.course_id, branch_id=branch.branch_id, curriculum_version_id=version_id, capacity=data["capacity"],
                  mode=data.get("mode", "Classroom"), planned_start=data.get("planned_start"), planned_end=data.get("planned_end"),
                  crm_batch_id=data.get("crm_batch_id"))
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


def update_batch(batch_id: int, data: dict) -> Batch:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state} and can no longer be edited")
    old = _snapshot(batch)

    if "curriculum_version_id" in data and data["curriculum_version_id"] != batch.curriculum_version_id:
        if batch.state not in ("Forming", "Starting"):
            raise BusinessRule("The curriculum version can only change before the batch is Running; use an academic mapping for running batches")
        if data["curriculum_version_id"] is not None:
            _validate_version(batch.course_id, data["curriculum_version_id"])
        batch.curriculum_version_id = data["curriculum_version_id"]
        batches_repo.add_event(batch.batch_id, "Curriculum changed", from_value=str(old["curriculum_version_id"]),
                               to_value=str(data["curriculum_version_id"]), actor_user_id=actor_id())
    for field in ("capacity", "mode", "planned_start", "planned_end"):
        if field in data:
            setattr(batch, field, data[field])
    _apply_timetable(batch, data)
    db.session.flush()
    if "capacity" in data and data["capacity"] != old["capacity"]:
        batches_repo.add_event(batch.batch_id, "Capacity changed", from_value=str(old["capacity"]), to_value=str(data["capacity"]),
                               actor_user_id=actor_id())
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


def transition(batch_id: int, state: str, reason: str | None) -> Batch:
    batch = load_managed_batch(batch_id)
    if state in ("Starting", "Running"):
        if batch.curriculum_version_id is None:
            raise BusinessRule(f"Batch {batch.batch_code} has no curriculum version yet (Curriculum Mapping Pending)")
        if batches_repo.lead_trainer(batch.batch_id) is None:
            raise BusinessRule(f"Batch {batch.batch_code} needs a lead trainer before it can start")
    if state == "Cancelled" and not reason:
        raise ValidationError("A reason is required", {"reason": ["Required to cancel a batch"]})

    old = batch.state
    batch.state = state
    db.session.flush()  # the database validates the move and raises a readable message
    batches_repo.add_event(batch.batch_id, "State changed", from_value=old, to_value=state, reason=reason, actor_user_id=actor_id())
    audit.record("BATCH_STATE", "batch", batch.batch_id, old={"state": old}, new={"state": state}, reason=reason, branch_id=batch.branch_id)
    sync_full(batch)
    return batch


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

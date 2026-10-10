"""Changes to a running commitment (Module 15 §7, §14, §17).

Capacity increase: the Branch Manager records the resource validation and academic review; the Branch Manager (or Super
Admin), never the requester, approves the new capacity.

Material change: a change to the start, delivery mode, teaching days / times, instructional hours or a significant end-date
extension. The old and proposed plan, reason and affected students are recorded and approved independently; then each
student agrees (in the LMS, or recorded by staff with evidence) or declines and is given an agreed alternative. Only then is
the change applied. A notice being delivered or read is not agreement.

Merge / split: students move to a successor batch of the same branch, course and curriculum version, with an effective
date, reason and the Branch Manager's review, after the Branch Manager's independent approval. A move to a batch with a
different mode or timetable needs an applied 'Batch move' material change first. Past classes, attendance and payments stay
on the original batch.
"""
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from config.database import db
from models import BatchCapacityRequest, BatchSuccession, MaterialChange, MaterialChangeResponse, Student
from models.batches import WEEKDAYS
from repositories import batches as batches_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import allocations, approvals, audit, delivery_access, delivery_notices, scope, whatsapp_messages
from services.batches import CAPACITY_SIDES, CLOSED_STATES, CONFIRM_ROLES, check_capacity_sides, load_managed_batch, sync_full
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

# What each kind of material change may set on the batch when it is applied
KIND_FIELDS = {
    "Start date": ("planned_start",),
    "Delivery mode": ("mode",),
    "Teaching days / times": ("schedule_days", "start_time", "end_time"),
    "End date extension": ("planned_end",),
    "Instructional hours": (),
    "Batch move": ("target_batch_id",),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_confirmer(branch_id: int) -> None:
    if not current_user().has_role(*CONFIRM_ROLES, branch_id=branch_id):
        raise Forbidden("Only the Branch Manager of this branch or a Super Admin decides this")


def _visible(batch) -> None:
    scope.assert_can_view_batch(batch)
    if delivery_access.is_student_only():
        raise NotFound("Not found")


def _decision_fields(record, status: str, note: str | None) -> None:
    record.status, record.decided_by, record.decided_at, record.decision_note = status, actor_id(), _now(), note


# ---------------------------------------------------------------- capacity increases

def request_capacity(batch_id: int, data: dict) -> BatchCapacityRequest:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    if data["to_capacity"] <= batch.capacity:
        raise ValidationError("Not an increase", {"to_capacity": [f"The batch already has {batch.capacity} seats; lower it directly"]})
    sides = {f: data.get(f, getattr(batch, f)) for f in CAPACITY_SIDES}
    check_capacity_sides(batch.mode, data["to_capacity"], sides)
    if db.session.execute(select(BatchCapacityRequest).where(BatchCapacityRequest.batch_id == batch_id,
                                                             BatchCapacityRequest.status == "Pending")).first():
        raise Conflict("A capacity request for this batch is already waiting for a decision")
    request = BatchCapacityRequest(batch_id=batch_id, from_capacity=batch.capacity, to_capacity=data["to_capacity"],
                                   resource_validation=data["resource_validation"], academic_review=data["academic_review"],
                                   requested_by=actor_id(), **{f: data.get(f) for f in CAPACITY_SIDES})
    db.session.add(request)
    db.session.flush()
    delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", batch.branch_id), category="Batch", action_required=True,
                                  title=f"Approve capacity {batch.capacity} → {data['to_capacity']}: {batch.batch_code}",
                                  body=data["resource_validation"], event_key=f"capacity-request-{request.request_id}",
                                  link="/branch/batches", branch_id=batch.branch_id)
    return request


def decide_capacity(request_id: int, decision: str, note: str | None) -> BatchCapacityRequest:
    request = db.session.get(BatchCapacityRequest, request_id)
    if request is None:
        raise NotFound("Capacity request not found")
    batch = load_managed_batch(request.batch_id)
    _require_confirmer(batch.branch_id)
    if request.status != "Pending":
        raise BusinessRule(f"The request is already {request.status}")
    if decision == "Rejected" and not note:
        raise ValidationError("A reason is required", {"note": ["Say why the increase is not approved"]})
    _decision_fields(request, decision, note)
    if decision == "Approved":
        if batch.state in CLOSED_STATES:
            raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
        old = batch.capacity
        batch.capacity = request.to_capacity
        for field in CAPACITY_SIDES:
            if getattr(request, field) is not None:
                setattr(batch, field, getattr(request, field))
        check_capacity_sides(batch.mode, batch.capacity, {f: getattr(batch, f) for f in CAPACITY_SIDES})
        db.session.flush()
        batches_repo.add_event(batch.batch_id, "Capacity changed", from_value=str(old), to_value=str(batch.capacity),
                               reason=f"Approved request {request.request_id}: {request.resource_validation}", actor_user_id=actor_id())
        sync_full(batch)
    db.session.flush()
    audit.record("BATCH_CAPACITY_DECIDED", "batch_capacity_request", request.request_id, branch_id=batch.branch_id, reason=note,
                 new={"status": decision, "to_capacity": request.to_capacity})
    return request


def list_capacity_requests(filters: dict, page: int, per_page: int):
    from models import Batch

    stmt = (select(BatchCapacityRequest).join(Batch, Batch.batch_id == BatchCapacityRequest.batch_id)
            .order_by(BatchCapacityRequest.requested_at.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}))
    for key in ("status", "batch_id"):
        if filters.get(key):
            stmt = stmt.where(getattr(BatchCapacityRequest, key) == filters[key])
    return paginate(stmt, page, per_page)


# ---------------------------------------------------------------- material changes

def _plan(batch) -> str:
    days = ", ".join(WEEKDAYS[d - 1] for d in sorted(batch.schedule_days or [])) or "days not set"
    times = f"{batch.start_time:%H:%M}–{batch.end_time:%H:%M}" if batch.start_time else "times not set"
    return f"{batch.mode}; {batch.planned_start or 'start not set'} to {batch.planned_end or 'end not set'}; {days} {times}"


def _clean_changes(kind: str, changes: dict, batch) -> dict:
    allowed = KIND_FIELDS[kind]
    unknown = set(changes) - set(allowed)
    if unknown:
        raise ValidationError("Invalid change", {"changes": [f"A {kind} change sets only {', '.join(allowed) or 'nothing on the batch'}"]})
    if kind != "Instructional hours" and not changes:
        raise ValidationError("Invalid change", {"changes": [f"Give the new {', '.join(allowed)}"]})
    if kind == "Batch move":
        target = batches_repo.get_batch(changes["target_batch_id"])
        if target is None or target.branch_id != batch.branch_id or target.batch_id == batch.batch_id:
            raise ValidationError("Invalid change", {"changes": ["The successor must be another batch of the same branch"]})
    out = {}
    for key, value in changes.items():
        if key in ("start_time", "end_time") and value is not None:
            time.fromisoformat(value)  # validated as HH:MM
        out[key] = value
    return out


def propose_change(batch_id: int, data: dict) -> MaterialChange:
    batch = load_managed_batch(batch_id)
    if batch.state in CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    learners = batches_repo.active_allocation_rows(batch.batch_id)
    if not learners:
        raise BusinessRule("No student holds a seat in this batch: edit the batch directly")
    change = MaterialChange(batch_id=batch_id, kind=data["kind"], current_plan=_plan(batch), proposed_plan=data["proposed_plan"],
                            reason=data["reason"], changes=_clean_changes(data["kind"], data.get("changes") or {}, batch),
                            alternative=data.get("alternative"), requested_by=actor_id())
    db.session.add(change)
    db.session.flush()
    for enrolment_id in dict.fromkeys(e.enrolment_id for _, e in learners):
        db.session.add(MaterialChangeResponse(change_id=change.change_id, enrolment_id=enrolment_id))
    db.session.flush()
    audit.record("MATERIAL_CHANGE_PROPOSED", "material_change", change.change_id, branch_id=batch.branch_id, reason=data["reason"],
                 new={"kind": change.kind, "changes": change.changes, "affected": len(change.responses)})
    delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", batch.branch_id), category="Batch", action_required=True,
                                  title=f"Approve a material change: {batch.batch_code} ({change.kind})", body=data["proposed_plan"],
                                  event_key=f"material-change-{change.change_id}", link="/branch/batches", branch_id=batch.branch_id)
    return change


def _load_change(change_id: int) -> MaterialChange:
    change = db.session.get(MaterialChange, change_id)
    if change is None:
        raise NotFound("Material change not found")
    _visible(change.batch)
    return change


def get_change(change_id: int) -> MaterialChange:
    return _load_change(change_id)


def list_changes(filters: dict, page: int, per_page: int):
    from models import Batch

    stmt = select(MaterialChange).join(Batch, Batch.batch_id == MaterialChange.batch_id).order_by(MaterialChange.requested_at.desc())
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}) | Batch.batch_id.in_(scope.trainer_batch_ids() or {0}))
    for key in ("status", "batch_id"):
        if filters.get(key):
            stmt = stmt.where(getattr(MaterialChange, key) == filters[key])
    return paginate(stmt, page, per_page)


def decide_change(change_id: int, decision: str, note: str | None) -> MaterialChange:
    """The Branch Manager approves the change independently; the students are then asked to agree."""
    change = _load_change(change_id)
    _require_confirmer(change.batch.branch_id)
    if change.status != "Pending Approval":
        raise BusinessRule(f"The change is {change.status}")
    approvals.require_independent(change.requested_by, message="The person who proposed the change cannot approve it",
                                  requester=change.requested_by)
    if decision == "Rejected" and not note:
        raise ValidationError("A reason is required", {"note": ["Say why the change is not approved"]})
    _decision_fields(change, "Awaiting Agreement" if decision == "Approved" else "Rejected", note)
    if change.status == "Awaiting Agreement":
        change.reply_by = _now() + timedelta(days=settings_repo.get_int("batch_change_reply_days", 7))
    db.session.flush()
    audit.record("MATERIAL_CHANGE_DECIDED", "material_change", change.change_id, branch_id=change.batch.branch_id, reason=note,
                 new={"status": change.status})
    if change.status == "Awaiting Agreement":
        for response in change.responses:
            enrolment = students_repo.get_enrolment(response.enrolment_id)
            delivery_notices.notify_student(enrolment.student_id, category="Batch",
                                            title=f"Your agreement is needed: {change.batch.batch_code} {change.kind.lower()}",
                                            body=f"Now: {change.current_plan}. Proposed: {change.proposed_plan}. Why: {change.reason}",
                                            event_key=f"material-change-{change.change_id}-ask", link="/my-courses",
                                            branch_id=enrolment.service_branch_id)
            whatsapp_messages.batch_change_agreement(change, db.session.get(Student, enrolment.student_id))
    return change


def _record(change: MaterialChange, response: MaterialChangeResponse, answer: str, note: str | None, alternative: str | None, via: str) -> None:
    if change.status != "Awaiting Agreement":
        raise BusinessRule(f"The change is {change.status}; it is not waiting for agreement")
    response.response, response.note, response.recorded_via = answer, note, via
    response.recorded_by, response.responded_at = actor_id(), _now()
    if alternative is not None:
        response.alternative_arranged = alternative
    db.session.flush()
    audit.record("MATERIAL_CHANGE_RESPONSE", "material_change", change.change_id, branch_id=change.batch.branch_id, reason=note,
                 new={"enrolment_id": response.enrolment_id, "response": answer, "via": via})


def respond_as_student(change_id: int, answer: str, note: str | None) -> MaterialChange:
    """The student's own affirmative agreement (or refusal) in the LMS."""
    change = db.session.get(MaterialChange, change_id)
    mine = scope.student_enrolment_ids()
    response = next((r for r in change.responses if r.enrolment_id in mine), None) if change else None
    if response is None:
        raise NotFound("Material change not found")
    _record(change, response, answer, note, None, "Student")
    return change


def record_response(change_id: int, data: dict) -> MaterialChange:
    """Staff record a student's answer given outside the LMS (with the evidence), or the alternative agreed with a student
    who declined."""
    change = _load_change(change_id)
    delivery_access.assert_can_manage_branch(change.batch.branch_id)
    response = next((r for r in change.responses if r.enrolment_id == data["enrolment_id"]), None)
    if response is None:
        raise ValidationError("Not affected", {"enrolment_id": ["This student is not affected by the change"]})
    if data["response"] == "Declined" and not (data.get("alternative_arranged") or response.alternative_arranged):
        raise ValidationError("An alternative is required", {"alternative_arranged": ["Record what was agreed instead"]})
    _record(change, response, data["response"], data["note"], data.get("alternative_arranged"), "Staff")
    return change


def apply_change(change_id: int) -> MaterialChange:
    """Apply once every affected student agreed, or declined with an agreed alternative recorded."""
    change = _load_change(change_id)
    batch = load_managed_batch(change.batch_id)
    if change.status != "Awaiting Agreement":
        raise BusinessRule(f"The change is {change.status}")
    waiting = [r.enrolment_id for r in change.responses if r.response == "Pending"]
    unresolved = [r.enrolment_id for r in change.responses if r.response == "Declined" and not r.alternative_arranged]
    if waiting or unresolved:
        codes = [students_repo.get_enrolment(e).enrolment_code for e in waiting + unresolved]
        raise BusinessRule("Not every affected student has agreed or been given an agreed alternative: " + ", ".join(codes),
                           {"waiting": waiting, "declined_without_alternative": unresolved})
    fields = {k: v for k, v in change.changes.items() if k != "target_batch_id"}
    for key, value in fields.items():
        if key in ("start_time", "end_time") and value is not None:
            value = time.fromisoformat(value)
        elif key in ("planned_start", "planned_end") and value is not None:
            value = datetime.fromisoformat(value).date() if isinstance(value, str) else value
        setattr(batch, key, value)
    if batch.mode == "Live Online":
        batch.location = None
    change.status, change.applied_by, change.applied_at = "Applied", actor_id(), _now()
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "Material change applied", from_value=change.current_plan[:200],
                           to_value=change.proposed_plan[:200], reason=change.reason, actor_user_id=actor_id())
    audit.record("MATERIAL_CHANGE_APPLIED", "material_change", change.change_id, branch_id=batch.branch_id, new={"changes": change.changes})
    for response in change.responses:
        enrolment = students_repo.get_enrolment(response.enrolment_id)
        delivery_notices.notify_student(enrolment.student_id, category="Batch", title=f"Change applied: {batch.batch_code} {change.kind.lower()}",
                                        body=change.proposed_plan if response.response == "Agreed" else f"Your agreed alternative: {response.alternative_arranged}",
                                        event_key=f"material-change-{change.change_id}-applied", link="/my-courses",
                                        branch_id=enrolment.service_branch_id)
    return change


def withdraw_change(change_id: int, note: str) -> MaterialChange:
    change = _load_change(change_id)
    delivery_access.assert_can_manage_branch(change.batch.branch_id)
    if change.status not in ("Pending Approval", "Awaiting Agreement"):
        raise BusinessRule(f"The change is {change.status}")
    change.status, change.decision_note = "Withdrawn", note
    db.session.flush()
    audit.record("MATERIAL_CHANGE_WITHDRAWN", "material_change", change.change_id, branch_id=change.batch.branch_id, reason=note)
    return change


def my_changes() -> list[tuple[MaterialChange, MaterialChangeResponse]]:
    """Changes the student is asked to agree to (and recent ones they answered)."""
    mine = scope.student_enrolment_ids()
    if not mine:
        return []
    stmt = (select(MaterialChange, MaterialChangeResponse).join(MaterialChangeResponse, MaterialChangeResponse.change_id == MaterialChange.change_id)
            .where(MaterialChangeResponse.enrolment_id.in_(mine), MaterialChange.status.in_(("Awaiting Agreement", "Applied")))
            .order_by(MaterialChange.requested_at.desc()))
    return [(c, r) for c, r in db.session.execute(stmt).all()]


# ---------------------------------------------------------------- merge / split

def request_succession(data: dict) -> BatchSuccession:
    source = load_managed_batch(data["from_batch_id"])
    target = load_managed_batch(data["to_batch_id"])
    if source.batch_id == target.batch_id:
        raise ValidationError("Invalid successor", {"to_batch_id": ["Choose another batch"]})
    if source.branch_id != target.branch_id:
        raise BusinessRule("A merge or split stays within one branch; moving branch follows the interbranch transfer rule")
    if (source.course_id, source.component_id) != (target.course_id, target.component_id):
        raise BusinessRule("The successor batch teaches a different course or track")
    if source.curriculum_version_id != target.curriculum_version_id:
        raise BusinessRule("The batches run different curriculum versions: the students need an approved academic mapping first")
    if target.state in CLOSED_STATES or target.state == "On Hold":
        raise BusinessRule(f"Batch {target.batch_code} is {target.state} and cannot take students")
    seated = {e.enrolment_id for _, e in batches_repo.active_allocation_rows(source.batch_id)}
    if data["kind"] == "Split":
        chosen = set(data.get("enrolment_ids") or [])
        if not chosen or not chosen <= seated:
            raise ValidationError("Invalid students", {"enrolment_ids": ["Choose students who hold a seat in the batch"]})
    elif not seated:
        raise BusinessRule(f"Nobody holds a seat in {source.batch_code}")
    succession = BatchSuccession(kind=data["kind"], from_batch_id=source.batch_id, to_batch_id=target.batch_id,
                                 enrolment_ids=sorted(data.get("enrolment_ids") or []) if data["kind"] == "Split" else [],
                                 effective_from=data["effective_from"], reason=data["reason"], academic_review=data["academic_review"],
                                 requested_by=actor_id())
    db.session.add(succession)
    db.session.flush()
    delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", source.branch_id), category="Batch", action_required=True,
                                  title=f"Approve {data['kind'].lower()}: {source.batch_code} → {target.batch_code}", body=data["reason"],
                                  event_key=f"succession-{succession.succession_id}", link="/branch/batches", branch_id=source.branch_id)
    return succession


def _same_plan(a, b) -> bool:
    return (a.mode, sorted(a.schedule_days or []), a.start_time, a.end_time) == (b.mode, sorted(b.schedule_days or []), b.start_time, b.end_time)


def decide_succession(succession_id: int, decision: str, note: str | None) -> BatchSuccession:
    succession = db.session.get(BatchSuccession, succession_id)
    if succession is None:
        raise NotFound("Merge / split request not found")
    source = load_managed_batch(succession.from_batch_id)
    target = load_managed_batch(succession.to_batch_id)
    _require_confirmer(source.branch_id)
    if succession.status != "Pending":
        raise BusinessRule(f"The request is already {succession.status}")
    approvals.require_independent(succession.requested_by, message="The requester cannot approve their own merge or split",
                                  requester=succession.requested_by)
    if decision == "Rejected":
        if not note:
            raise ValidationError("A reason is required", {"note": ["Say why"]})
        _decision_fields(succession, "Rejected", note)
        db.session.flush()
        return succession

    if not _same_plan(source, target) and not db.session.execute(select(MaterialChange).where(
            MaterialChange.batch_id == source.batch_id, MaterialChange.kind == "Batch move", MaterialChange.status == "Applied",
            MaterialChange.changes["target_batch_id"].as_integer() == target.batch_id)).first():
        raise BusinessRule(f"{target.batch_code} has a different mode or timetable: record a 'Batch move' material change on "
                           f"{source.batch_code} and apply it once every student agreed")
    rows = [(a, e) for a, e in batches_repo.active_allocation_rows(source.batch_id)
            if succession.kind == "Merge" or e.enrolment_id in succession.enrolment_ids]
    newcomers = {e.enrolment_id for _, e in rows} - {e.enrolment_id for _, e in batches_repo.active_allocation_rows(target.batch_id)}
    free = target.capacity - batches_repo.allocated_counts([target.batch_id]).get(target.batch_id, 0)
    if len(newcomers) > free:
        raise BusinessRule(f"{target.batch_code} has {free} free seat(s) for {len(newcomers)} student(s); raise its capacity first")
    _decision_fields(succession, "Approved", note)
    reason = f"{succession.kind} {source.batch_code} → {target.batch_code}: {succession.reason}"
    for allocation, enrolment in rows:
        allocations.allocate(enrolment, target, created_by=actor_id(), reason=reason, effective_from=succession.effective_from,
                             enrolment_track_id=allocation.enrolment_track_id)
    succession.moved_count = len(rows)
    db.session.flush()
    for batch, other, verb in ((source, target, "Successor"), (target, source, "Predecessor")):
        batches_repo.add_event(batch.batch_id, f"{succession.kind} approved", from_value=source.batch_code, to_value=target.batch_code,
                               reason=f"{verb}: {other.batch_code}. {succession.reason}", actor_user_id=actor_id())
        sync_full(batch)
    audit.record("BATCH_SUCCESSION", "batch_succession", succession.succession_id, branch_id=source.branch_id, reason=succession.reason,
                 new={"kind": succession.kind, "from": source.batch_id, "to": target.batch_id, "moved": len(rows)})
    for _, enrolment in rows:
        delivery_notices.notify_student(enrolment.student_id, category="Batch", title=f"Your batch is now {target.batch_code}",
                                        body=f"{succession.kind} from {source.batch_code}, effective {succession.effective_from}.",
                                        event_key=f"succession-{succession.succession_id}", link="/my-courses",
                                        branch_id=enrolment.service_branch_id)
    return succession


def list_successions(filters: dict, page: int, per_page: int):
    from models import Batch

    stmt = (select(BatchSuccession).join(Batch, Batch.batch_id == BatchSuccession.from_batch_id)
            .order_by(BatchSuccession.requested_at.desc()))
    branch_ids = scope.visible_branch_ids()
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids or {0}))
    if filters.get("status"):
        stmt = stmt.where(BatchSuccession.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.where((BatchSuccession.from_batch_id == filters["batch_id"]) | (BatchSuccession.to_batch_id == filters["batch_id"]))
    return paginate(stmt, page, per_page)

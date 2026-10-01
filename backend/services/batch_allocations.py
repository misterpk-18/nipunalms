"""Putting students into batches: the review checks shown before allocating, allocate, transfer, deallocate, the roster.

A seat is only given after the batch allocation review: service branch, course, curriculum mapping / version, capacity,
delivery mode and the enrolment's own state. A failed check blocks; a warning (different curriculum version or mode)
needs the coordinator to acknowledge it. Ended and transferred allocations stay as history; nothing the student did
in a previous batch is touched.
"""
from datetime import datetime, timedelta

from config.database import db
from config.timezone import IST
from models import Batch, BatchAllocation, Enrolment
from repositories import batches as batches_repo
from repositories import enrolments as enrolments_repo
from repositories import students as students_repo
from repositories.common import paginate
from services import allocations, audit, delivery_access, delivery_notices, scope
from services import batches as batches_service
from services.batches import CLOSED_STATES, load_managed_batch, sync_full
from services.context import actor_id
from services.errors import BusinessRule, Conflict, NotFound
from services.notifications import notify

# Statuses from which an enrolment can be given a first seat / can no longer be moved
ALLOCATION_READY = "Allocation Pending"
AWAITING_SEAT = ("Curriculum Mapping Pending", "Allocation Pending")
ESCALATE_BEFORE_START = timedelta(hours=24)
SEATED_STATUSES = ("Allocated — awaiting first regular class", "Active")


def _check(key: str, label: str, status: str, detail: str) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail}


def review(batch: Batch, enrolment: Enrolment, *, transfer: bool = False) -> dict:
    """The batch allocation review for one enrolment and one batch. Status per check: pass, warn or fail."""
    taken = batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0)
    current = batches_repo.active_allocation(enrolment.enrolment_id)
    already_here = current is not None and current.batch_id == batch.batch_id
    checks = [
        _check("branch", "Service branch", "pass" if batch.branch_id == enrolment.service_branch_id else "fail",
               f"Enrolment is serviced at {enrolment.service_branch.branch_name}; batch is at {batch.branch.branch_name}"
               if batch.branch_id != enrolment.service_branch_id else f"{batch.branch.branch_name}"),
        _check("course", "Course / track", "pass" if batch.course_id == enrolment.course_id else "fail",
               f"{enrolment.course.course_code}" + (f" — combo with {len(enrolment.tracks)} tracks" if enrolment.tracks else "")
               if batch.course_id == enrolment.course_id else f"Batch is for {batch.course.course_code}, enrolment is for {enrolment.course.course_code}"),
    ]

    unmapped_tracks = [t.component.track_code for t in enrolment.tracks if t.curriculum_version_id is None]
    if enrolment.curriculum_version_id is None or unmapped_tracks:
        missing = "the course" if enrolment.curriculum_version_id is None else ", ".join(unmapped_tracks)
        checks.append(_check("curriculum", "Curriculum mapping / version", "fail", f"Curriculum Mapping Pending ({missing})"))
    elif batch.curriculum_version_id is None:
        checks.append(_check("curriculum", "Curriculum mapping / version", "fail", "The batch has no curriculum version yet"))
    elif batch.curriculum_version_id != enrolment.curriculum_version_id:
        checks.append(_check("curriculum", "Curriculum mapping / version", "warn",
                             f"Enrolment is on {enrolment.curriculum_version.version_label}; the batch runs {batch.curriculum_version.version_label}. "
                             "Record the academic mapping before allocating"))
    else:
        checks.append(_check("curriculum", "Curriculum mapping / version", "pass", batch.curriculum_version.version_label))

    if already_here:
        checks.append(_check("capacity", "Capacity", "pass", f"{taken} of {batch.capacity} seats taken (already holds a seat)"))
    elif taken >= batch.capacity:
        checks.append(_check("capacity", "Capacity", "fail", f"{taken} of {batch.capacity} seats taken — the batch is full"))
    else:
        checks.append(_check("capacity", "Capacity", "pass", f"{taken} of {batch.capacity} seats taken"))

    if batch.mode == enrolment.mode or batch.mode == "Hybrid":
        checks.append(_check("mode", "Delivery mode", "pass", f"{enrolment.mode} enrolment, {batch.mode} batch"))
    else:
        checks.append(_check("mode", "Delivery mode", "warn",
                             f"Enrolment is {enrolment.mode}; batch is {batch.mode}. A change of delivery mode needs the student's agreement"))

    if batch.state in CLOSED_STATES:
        checks.append(_check("batch_state", "Batch state", "fail", f"Batch is {batch.state}"))
    else:
        checks.append(_check("batch_state", "Batch state", "pass", batch.state))

    if transfer:
        if current is None:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", "Not allocated to a batch yet; allocate instead of transfer"))
        elif already_here:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", "Already allocated to this batch"))
        elif enrolment.status in SEATED_STATUSES:
            checks.append(_check("enrolment_state", "Enrolment state", "pass", f"{enrolment.status}; moves from {current.batch.batch_code}"))
        else:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", enrolment.status))
    elif enrolment.status == ALLOCATION_READY and current is None:
        checks.append(_check("enrolment_state", "Enrolment state", "pass", "Admission verified (CRM); waiting for a batch"))
    elif current is not None:
        checks.append(_check("enrolment_state", "Enrolment state", "fail", f"Already allocated to {current.batch.batch_code}; use transfer"))
    else:
        checks.append(_check("enrolment_state", "Enrolment state", "fail", enrolment.status))

    blocking = [c["detail"] for c in checks if c["status"] == "fail"]
    warnings = [c["detail"] for c in checks if c["status"] == "warn"]
    return {
        "enrolment": enrolment.to_summary(),
        "batch": batch.to_summary(),
        "checks": checks,
        "result": "Blocked" if blocking else "Review needed" if warnings else "Ready to allocate",
        "blocking": blocking,
        "warnings": warnings,
        "recovery_owner": f"Academic Coordinator — {enrolment.service_branch.branch_name}" if blocking else None,
    }


def review_for_enrolment(batch_id: int, enrolment_id: int, transfer: bool = False) -> dict:
    batch, _ = batches_service.get_batch(batch_id)
    delivery_access.assert_can_manage_branch(batch.branch_id)
    enrolment = _viewable_enrolment(enrolment_id)
    return review(batch, enrolment, transfer=transfer)


def _viewable_enrolment(enrolment_id: int) -> Enrolment:
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    return enrolment


def _enforce(report: dict, acknowledge_warnings: bool) -> None:
    if report["blocking"]:
        raise BusinessRule("The batch allocation review failed: " + "; ".join(report["blocking"]), {"blocking": report["blocking"]})
    if report["warnings"] and not acknowledge_warnings:
        raise BusinessRule("Acknowledge the review warnings to continue: " + "; ".join(report["warnings"]), {"warnings": report["warnings"]})


def _notify_seat(enrolment: Enrolment, batch: Batch, title: str, body: str, key: str) -> None:
    delivery_notices.notify_student(enrolment.student_id, title=title, body=body, event_key=key, link="/my-courses",
                                    branch_id=enrolment.service_branch_id)


# ---------------------------------------------------------------- seat changes

def allocate(batch_id: int, enrolment_id: int, reason: str | None, acknowledge_warnings: bool) -> BatchAllocation:
    """Give an enrolment in Allocation Pending its seat, after the review. Moves it to 'Allocated — awaiting first regular class'."""
    batch = load_managed_batch(batch_id)
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    report = review(batch, enrolment)
    _enforce(report, acknowledge_warnings)

    allocation = allocations.allocate(enrolment, batch, created_by=actor_id(), reason=reason)
    sync_full(batch)
    audit.record("BATCH_ALLOCATED", "batch_allocation", allocation.allocation_id, branch_id=batch.branch_id, reason=reason,
                 new={"enrolment_id": enrolment.enrolment_id, "batch_id": batch.batch_id, "acknowledged_warnings": report["warnings"]})
    _notify_seat(enrolment, batch, f"You are allocated to batch {batch.batch_code}",
                 f"{enrolment.course.title}. Your Joining Date is set when you attend your first confirmed regular class.",
                 f"allocation-{allocation.allocation_id}")
    return allocation


def transfer(enrolment_id: int, to_batch_id: int, reason: str, acknowledge_warnings: bool) -> BatchAllocation:
    """Move an allocated enrolment to another batch of the same course and branch. The previous allocation is kept as history."""
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    current = batches_repo.active_allocation(enrolment.enrolment_id)
    if current is None:
        raise Conflict("The enrolment is not allocated to a batch; allocate it instead")
    delivery_access.assert_can_manage_branch(current.batch.branch_id)
    old_batch = batches_repo.get_batch_for_update(current.batch_id)
    new_batch = load_managed_batch(to_batch_id)
    _enforce(review(new_batch, enrolment, transfer=True), acknowledge_warnings)

    allocation = allocations.allocate(enrolment, new_batch, created_by=actor_id(), reason=reason)
    current.reason = f"Moved to {new_batch.batch_code}: {reason}"
    db.session.flush()
    sync_full(old_batch)
    sync_full(new_batch)
    audit.record("BATCH_TRANSFERRED", "batch_allocation", allocation.allocation_id, branch_id=new_batch.branch_id, reason=reason,
                 old={"batch_id": old_batch.batch_id}, new={"batch_id": new_batch.batch_id, "enrolment_id": enrolment.enrolment_id})
    _notify_seat(enrolment, new_batch, f"You have moved to batch {new_batch.batch_code}", f"{enrolment.course.title}. Reason: {reason}",
                 f"allocation-{allocation.allocation_id}")
    return allocation


def deallocate(enrolment_id: int, reason: str) -> BatchAllocation:
    """Take an enrolment out of its batch (with a reason). An enrolment awaiting its first class returns to Allocation Pending."""
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    current = batches_repo.active_allocation(enrolment.enrolment_id)
    if current is None:
        raise Conflict("The enrolment is not allocated to a batch")
    delivery_access.assert_can_manage_branch(current.batch.branch_id)
    if enrolment.status in ("Completed", "Withdrawn"):
        raise BusinessRule(f"A {enrolment.status} enrolment keeps its batch history")
    batch = batches_repo.get_batch_for_update(current.batch_id)

    allocations.end(enrolment, "Ended", reason=reason)
    sync_full(batch)
    audit.record("BATCH_DEALLOCATED", "batch_allocation", current.allocation_id, branch_id=batch.branch_id, reason=reason,
                 old={"batch_id": batch.batch_id, "enrolment_id": enrolment.enrolment_id})
    _notify_seat(enrolment, batch, f"You are no longer allocated to batch {batch.batch_code}", f"{enrolment.course.title}. Reason: {reason}",
                 f"deallocation-{current.allocation_id}")
    return current


# ---------------------------------------------------------------- lists

def roster(batch_id: int, status: str | None, page: int, per_page: int):
    """The students of a batch (staff only), with their enrolment; history rows (Ended / Transferred) with status=."""
    batch, _ = batches_service.get_batch(batch_id)
    if delivery_access.is_student_only():
        raise NotFound("Batch not found")
    rows, meta = paginate(batches_repo.roster_stmt(batch.batch_id, status), page, per_page)
    enrolments = {e.enrolment_id: e for e in (students_repo.get_enrolment(r.enrolment_id) for r in rows)}
    students = enrolments_repo.students_by_id({e.student_id for e in enrolments.values()})
    return [(row, enrolments[row.enrolment_id], students[enrolments[row.enrolment_id].student_id]) for row in rows], meta


# ---------------------------------------------------------------- escalation (job)

def escalate_unallocated() -> int:
    """Job: an enrolment still without a seat 24 hours before its admission's planned start (IST) is raised to the
    service branch's Branch Managers, once per enrolment. This was the CRM's `batch-allocation` job; allocation is the
    LMS's now. Returns how many enrolments were newly escalated."""
    escalated = 0
    for enrolment in enrolments_repo.unallocated_starting_by((datetime.now(IST) + ESCALATE_BEFORE_START).date(), AWAITING_SEAT):
        admission = enrolment.admission
        student = students_repo.get_student(enrolment.student_id)
        sent = notify(category="Enrolment", event_key=f"allocation-escalate:{enrolment.enrolment_id}",
                      title=f"Allocate a batch now: {student.full_name} ({admission.admission_code}) starts "
                            f"{admission.planned_start_date.isoformat()}",
                      body=f"{enrolment.enrolment_code} · {enrolment.course.course_code} · {enrolment.status}",
                      link=f"/academic/students/{student.student_id}", role_code="BRANCH_MANAGER",
                      branch_id=enrolment.service_branch_id, action_required=True)
        escalated += 1 if sent else 0
    return escalated

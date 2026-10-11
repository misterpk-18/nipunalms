"""Putting students into batches: the review checks shown before allocating, allocate, deallocate, the roster. Moving a
seat between batches is a transfer request (services/batch_transfers.py).

A seat is only given after the batch allocation review: service branch, course or track, capacity, delivery mode, the
student's other classes and the enrolment's own state. The curriculum never blocks a seat: the student follows the
curriculum version of the batch they join (a batch with none yet picks one up when it is activated). A failed check blocks; a warning
(different mode, a timetable clash) needs the Branch Manager to acknowledge it. Ended and transferred allocations stay as
history; nothing the student did in a previous batch is touched.
"""
from datetime import date, datetime, timedelta

from config.database import db
from config.timezone import IST
from models import Batch, BatchAllocation, Enrolment
from models.batches import BATCH_STATE_LABELS
from repositories import batches as batches_repo
from repositories import enrolments as enrolments_repo
from repositories import students as students_repo
from repositories.common import paginate
from services import allocations, audit, delivery_access, delivery_notices, scope, slot_preferences, working_days
from services import batches as batches_service
from services.batches import CLOSED_STATES, load_managed_batch, sync_full
from services.context import actor_id
from services.errors import BusinessRule, Conflict, NotFound
from services.notifications import notify

# Statuses from which an enrolment can be given a first seat / can no longer be moved
ALLOCATION_READY = "Allocation Pending"
AWAITING_SEAT = ("Allocation Pending",)
ESCALATE_BEFORE_START = timedelta(hours=24)
SEATED_STATUSES = ("Allocated — awaiting first regular class", "Active")


def _check(key: str, label: str, status: str, detail: str) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail}


def _track(enrolment: Enrolment, enrolment_track_id: int | None):
    return next((t for t in enrolment.tracks if t.enrolment_track_id == enrolment_track_id), None) if enrolment_track_id else None


def review(batch: Batch, enrolment: Enrolment, *, transfer: bool = False, enrolment_track_id: int | None = None,
           interbranch: bool = False) -> dict:
    """The batch allocation review for one enrolment (or one combo track of it) and one batch. Status per check: pass, warn
    or fail. `interbranch`: a component placed at another branch, which its own approvals cover (Module 15 §4, §13)."""
    taken = batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0)
    track = _track(enrolment, enrolment_track_id)
    current = allocations.current_seat(enrolment, enrolment_track_id)
    seats = batches_repo.active_allocations_of(enrolment.enrolment_id)
    already_here = current is not None and current.batch_id == batch.batch_id
    same_branch = batch.branch_id == enrolment.service_branch_id
    if same_branch:
        branch_check = _check("branch", "Service branch", "pass", batch.branch.branch_name)
    elif interbranch and track is not None:
        branch_check = _check("branch", "Service branch", "pass",
                              f"{track.component.track_code} placed at {batch.branch.branch_name}; the admission stays at "
                              f"{enrolment.service_branch.branch_name} (needs the destination's confirmation and the Branch Manager's approval)")
    else:
        branch_check = _check("branch", "Service branch", "fail",
                              f"Enrolment is serviced at {enrolment.service_branch.branch_name}; batch is at {batch.branch.branch_name}"
                              + ("" if track else ". Only a single track can be placed at another branch"))
    problem = allocations.teaches(batch, enrolment, enrolment_track_id)
    what = (f"{enrolment.course.course_code} track {track.component.track_code}" if track else
            f"{enrolment.course.course_code}" + (f" — combo with {len(enrolment.tracks)} tracks" if enrolment.tracks else ""))
    checks = [branch_check, _check("course", "Course / track", "fail" if problem else "pass", problem or what)]

    if already_here or any(a.batch_id == batch.batch_id for a in seats):
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

    leaving = {current.batch_id} if current is not None else set()
    clashes = [b for b in batches_repo.timetable_overlaps(batch, batches_repo.batch_ids_of_students([enrolment.student_id], batch.batch_id))
               if b.batch_id not in leaving]
    if clashes:
        checks.append(_check("timetable", "Student timetable", "warn",
                             "The student already has classes at these times in " + ", ".join(b.batch_code for b in clashes)))
    else:
        checks.append(_check("timetable", "Student timetable", "pass",
                             "No clash with the student's other classes" if batch.schedule_days else "The batch has no timetable to compare yet"))

    if batch.state in allocations.NO_NEW_SEATS:
        checks.append(_check("batch_state", "Batch state", "fail", f"Batch is {batch.state}"))
    else:
        checks.append(_check("batch_state", "Batch state", "pass", BATCH_STATE_LABELS[batch.state]))

    if transfer:
        if current is None:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", "Not allocated to a batch yet; allocate instead of transfer"))
        elif already_here:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", "Already allocated to this batch"))
        elif enrolment.status in SEATED_STATUSES:
            checks.append(_check("enrolment_state", "Enrolment state", "pass", f"{enrolment.status}; moves from {current.batch.batch_code}"))
        else:
            checks.append(_check("enrolment_state", "Enrolment state", "fail", enrolment.status))
    elif current is not None:
        checks.append(_check("enrolment_state", "Enrolment state", "fail", f"Already allocated to {current.batch.batch_code}; use transfer"))
    elif track is not None and enrolment.status in (ALLOCATION_READY, *SEATED_STATUSES):
        checks.append(_check("enrolment_state", "Enrolment state", "pass", f"{enrolment.status}; track not yet seated"))
    elif enrolment.status == ALLOCATION_READY:
        checks.append(_check("enrolment_state", "Enrolment state", "pass", "Admission verified (CRM); waiting for a batch"))
    else:
        checks.append(_check("enrolment_state", "Enrolment state", "fail", enrolment.status))

    blocking = [c["detail"] for c in checks if c["status"] == "fail"]
    warnings = [c["detail"] for c in checks if c["status"] == "warn"]
    return {
        "enrolment": enrolment.to_summary(),
        "enrolment_track_id": enrolment_track_id,
        "batch": batch.to_summary(),
        "checks": checks,
        "result": "Blocked" if blocking else "Review needed" if warnings else "Ready to allocate",
        "blocking": blocking,
        "warnings": warnings,
        "recovery_owner": f"Branch Manager — {enrolment.service_branch.branch_name}" if blocking else None,
    }


def review_for_enrolment(batch_id: int, enrolment_id: int, transfer: bool = False, enrolment_track_id: int | None = None) -> dict:
    enrolment = _viewable_enrolment(enrolment_id)
    batch = batches_repo.get_batch(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    interbranch = enrolment_track_id is not None and batch.branch_id != enrolment.service_branch_id
    if interbranch:
        # a component placed elsewhere: the requester manages the student's service branch
        delivery_access.assert_can_manage_branch(enrolment.service_branch_id)
    else:
        scope.assert_can_view_batch(batch)
        delivery_access.assert_can_manage_branch(batch.branch_id)
    return review(batch, enrolment, transfer=transfer, enrolment_track_id=enrolment_track_id, interbranch=interbranch)


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

def allocate(batch_id: int, enrolment_id: int, reason: str | None, acknowledge_warnings: bool,
             enrolment_track_id: int | None = None) -> BatchAllocation:
    """Give an enrolment its first seat (or a combo track its seat in a track batch), after the review. The enrolment moves to
    'Allocated — awaiting first regular class'. Moving a seat that already exists is a transfer request."""
    batch = load_managed_batch(batch_id)
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    report = review(batch, enrolment, enrolment_track_id=enrolment_track_id)
    _enforce(report, acknowledge_warnings)

    allocation = allocations.allocate(enrolment, batch, created_by=actor_id(), reason=reason, enrolment_track_id=enrolment_track_id)
    sync_full(batch)
    slot_preferences.seat_taken(enrolment.enrolment_id, batch.batch_id)
    audit.record("BATCH_ALLOCATED", "batch_allocation", allocation.allocation_id, branch_id=batch.branch_id, reason=reason,
                 new={"enrolment_id": enrolment.enrolment_id, "enrolment_track_id": enrolment_track_id, "batch_id": batch.batch_id,
                      "acknowledged_warnings": report["warnings"]})
    _notify_seat(enrolment, batch, f"You are allocated to batch {batch.batch_code}",
                 f"{enrolment.course.title}. Your Joining Date is set when you attend your first confirmed regular class.",
                 f"allocation-{allocation.allocation_id}")
    return allocation


def deallocate(enrolment_id: int, reason: str, enrolment_track_id: int | None = None) -> BatchAllocation:
    """Take an enrolment (or one track) out of its batch (with a reason). An enrolment left without a seat while awaiting its
    first class returns to Allocation Pending."""
    enrolment = enrolments_repo.get_enrolment_for_update(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    current = allocations.current_seat(enrolment, enrolment_track_id)
    if current is None:
        raise Conflict("The enrolment is not allocated to a batch" if enrolment_track_id is None else "The track holds no seat")
    delivery_access.assert_can_manage_branch(enrolment.service_branch_id)
    if enrolment.status in ("Completed", "Withdrawn"):
        raise BusinessRule(f"A {enrolment.status} enrolment keeps its batch history")
    batch = batches_repo.get_batch_for_update(current.batch_id)

    allocations.end(enrolment, "Ended", reason=reason, enrolment_track_id=enrolment_track_id)
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

def allocation_due_on(enrolment: Enrolment) -> date | None:
    """Module 15 §6: a confirmed seat is allocated within one working day after Admission; an accepted future delivery plan at
    least 48 hours before the agreed first class; an Admission inside that window before the first class. The one-working-
    day target never runs past the day before the first class."""
    admission = enrolment.admission
    admitted = admission.admission_date or admission.created_at.astimezone(IST).date()
    first_class = admission.planned_start_date
    if admission.seat_type == "Future Plan" and first_class is not None:
        two_days_before = first_class - timedelta(days=2)
        return two_days_before if admitted <= two_days_before else first_class  # inside the window: before the first class
    due = working_days.add_working_days(admitted, 1, enrolment.service_branch_id)
    if first_class is not None and due >= first_class:
        due = max(first_class - timedelta(days=1), admitted)
    return due


# At 24 hours before the committed start an unresolved allocation goes to the Founder / CEO or Super Admin; the Branch
# Manager, who owns missed commitments, is told too (Module 15 §6)
ESCALATE_TO = ("FOUNDER_CEO", "SUPER_ADMIN", "BRANCH_MANAGER")


def escalate_unallocated() -> int:
    """Job: an enrolment still without a seat 24 hours before its admission's planned start (IST) — or first noticed inside
    that window — is raised to the Founder / CEO, Super Admin and the service branch's Branch Managers, once per enrolment.
    Returns how many enrolments were newly escalated."""
    escalated = 0
    for enrolment in enrolments_repo.unallocated_starting_by((datetime.now(IST) + ESCALATE_BEFORE_START).date(), AWAITING_SEAT):
        admission = enrolment.admission
        student = students_repo.get_student(enrolment.student_id)
        sent = 0
        for role_code in ESCALATE_TO:
            sent += notify(category="Enrolment", event_key=f"allocation-escalate:{enrolment.enrolment_id}",
                           title=f"Allocate a batch now: {student.full_name} ({admission.admission_code}) starts "
                                 f"{admission.planned_start_date.isoformat()}",
                           body=f"{enrolment.enrolment_code} · {enrolment.course.course_code} · {enrolment.status}. "
                                f"Record who is responsible, the blockage, the recovery and what the student is told.",
                           link="/branch/waiting" if role_code == "BRANCH_MANAGER" else "/admin/exceptions", role_code=role_code,
                           branch_id=enrolment.service_branch_id, action_required=True)
        escalated += 1 if sent else 0
    return escalated

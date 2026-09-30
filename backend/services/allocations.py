"""Seats: put an enrolment into a batch, take it out again. History is kept (allocations are ended, never deleted)."""
from datetime import date

from config.database import db
from config.timezone import today_ist
from models import Batch, BatchAllocation, Enrolment
from repositories import batches as batches_repo
from services.errors import BusinessRule

# A seat can be reserved while the curriculum is still being mapped; the status only moves on once it is
ALLOCATABLE_STATUSES = ("Curriculum Mapping Pending", "Allocation Pending", "Allocated — awaiting first regular class", "Active")


def allocate(enrolment: Enrolment, batch: Batch, *, created_by: int | None = None, reason: str | None = None,
             effective_from: date | None = None) -> BatchAllocation:
    """Give the enrolment its seat in the batch. A current allocation to another batch is ended as Transferred.

    The database enforces the same rules (course, branch, capacity) as a backstop; checking here gives readable errors.
    """
    if enrolment.status not in ALLOCATABLE_STATUSES:
        raise BusinessRule(f"Enrolment {enrolment.enrolment_code} is '{enrolment.status}' and cannot be allocated to a batch")
    if batch.course_id != enrolment.course_id:
        raise BusinessRule(f"Batch {batch.batch_code} is for a different course than enrolment {enrolment.enrolment_code}")
    if batch.branch_id != enrolment.service_branch_id:
        raise BusinessRule(f"Batch {batch.batch_code} is at a different branch than the enrolment's service branch")
    if batch.state in ("Completed", "Cancelled"):
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state} and cannot take new students")

    current = batches_repo.active_allocation(enrolment.enrolment_id)
    if current is not None and current.batch_id == batch.batch_id:
        return current
    if batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0) >= batch.capacity:
        raise BusinessRule(f"Batch {batch.batch_code} is full ({batch.capacity} of {batch.capacity} seats taken)")
    if current is not None:
        end(enrolment, "Transferred", reason=f"Moved to {batch.batch_code}")

    allocation = BatchAllocation(enrolment_id=enrolment.enrolment_id, batch_id=batch.batch_id, created_by=created_by,
                                 reason=reason, effective_from=effective_from or today_ist())
    db.session.add(allocation)
    if enrolment.status == "Allocation Pending":
        enrolment.status = "Allocated — awaiting first regular class"
    db.session.flush()
    return allocation


def end(enrolment: Enrolment, status: str = "Ended", *, reason: str | None = None) -> None:
    """End the enrolment's current allocation (if any). An enrolment still awaiting its first class goes back to Allocation Pending."""
    current = batches_repo.active_allocation(enrolment.enrolment_id)
    if current is None:
        return
    current.status = status
    current.effective_to = max(today_ist(), current.effective_from)
    current.reason = reason or current.reason
    if enrolment.status == "Allocated — awaiting first regular class":
        enrolment.status = "Allocation Pending"
    db.session.flush()

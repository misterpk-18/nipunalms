"""Seats: put an enrolment (or one combo track of it) into a batch, take it out again. History is kept (allocations are
ended, never deleted).

A combo enrolment can hold one seat for the whole enrolment and, separately, a seat per track in a track batch (Module 15
§4): moving one component never moves the parent Admission or its other tracks.
"""
from datetime import date

from config.database import db
from config.timezone import today_ist
from models import Batch, BatchAllocation, Enrolment
from repositories import batches as batches_repo
from services.errors import BusinessRule

ALLOCATABLE_STATUSES = ("Allocation Pending", "Allocated — awaiting first regular class", "Active")
NO_NEW_SEATS = ("Completed", "Cancelled", "Archived", "On Hold")


def current_seat(enrolment: Enrolment, enrolment_track_id: int | None = None) -> BatchAllocation | None:
    """The active seat for the whole enrolment (track None) or for one track."""
    if enrolment_track_id is not None:
        return batches_repo.active_track_allocation(enrolment.enrolment_id, enrolment_track_id)
    return next((a for a in batches_repo.active_allocations_of(enrolment.enrolment_id) if a.enrolment_track_id is None), None)


def teaches(batch: Batch, enrolment: Enrolment, enrolment_track_id: int | None) -> str | None:
    """Why the batch cannot take this seat's learning, or None: a whole-enrolment seat needs a batch of the enrolment's
    course (not a track batch); a track seat needs that track's batch, a combined batch of the course, or a batch of the
    track's own standalone course."""
    if enrolment_track_id is None:
        if batch.component_id is not None:
            return f"Batch {batch.batch_code} teaches one track; allocate the track, not the whole enrolment"
        if batch.course_id != enrolment.course_id:
            return f"Batch {batch.batch_code} is for a different course than enrolment {enrolment.enrolment_code}"
        return None
    track = next((t for t in enrolment.tracks if t.enrolment_track_id == enrolment_track_id), None)
    if track is None:
        return "The track does not belong to this enrolment"
    component = track.component
    if (batch.course_id == enrolment.course_id and batch.component_id in (None, component.component_id)) or \
            (batch.component_id is None and batch.course_id == component.component_course_id):
        return None
    return f"Batch {batch.batch_code} does not teach track {component.track_code}"


def allocate(enrolment: Enrolment, batch: Batch, *, created_by: int | None = None, reason: str | None = None,
             effective_from: date | None = None, enrolment_track_id: int | None = None, interbranch: bool = False) -> BatchAllocation:
    """Give the enrolment (or one track) its seat in the batch. A current seat of the same scope in another batch is ended as
    Transferred. `interbranch`: an approved component placement at another branch (the database checks the approval).

    The database enforces the same rules (course / track, branch, capacity) as a backstop; checking here gives readable errors.
    """
    if enrolment.status not in ALLOCATABLE_STATUSES:
        raise BusinessRule(f"Enrolment {enrolment.enrolment_code} is '{enrolment.status}' and cannot be allocated to a batch")
    problem = teaches(batch, enrolment, enrolment_track_id)
    if problem:
        raise BusinessRule(problem)
    if batch.branch_id != enrolment.service_branch_id and not interbranch:
        raise BusinessRule(f"Batch {batch.batch_code} is at a different branch than the enrolment's service branch")
    if batch.state in NO_NEW_SEATS:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state} and cannot take new students")

    current = current_seat(enrolment, enrolment_track_id)
    if current is not None and current.batch_id == batch.batch_id:
        return current
    seated_here = any(a.batch_id == batch.batch_id for a in batches_repo.active_allocations_of(enrolment.enrolment_id))
    if not seated_here and batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0) >= batch.capacity:
        raise BusinessRule(f"Batch {batch.batch_code} is full ({batch.capacity} of {batch.capacity} seats taken)")
    if current is not None:
        _close(current, "Transferred", f"Moved to {batch.batch_code}")

    allocation = BatchAllocation(enrolment_id=enrolment.enrolment_id, enrolment_track_id=enrolment_track_id, batch_id=batch.batch_id,
                                 created_by=created_by, reason=reason, effective_from=effective_from or today_ist())
    db.session.add(allocation)
    if enrolment.status == "Allocation Pending":
        enrolment.status = "Allocated — awaiting first regular class"
    db.session.flush()
    return allocation


def _close(allocation: BatchAllocation, status: str, reason: str | None) -> None:
    allocation.status = status
    allocation.effective_to = max(today_ist(), allocation.effective_from)
    allocation.reason = reason or allocation.reason


def end(enrolment: Enrolment, status: str = "Ended", *, reason: str | None = None, enrolment_track_id: int | None = None) -> None:
    """End one seat (the whole-enrolment seat by default). An enrolment left with no seat while still awaiting its first class
    goes back to Allocation Pending."""
    current = current_seat(enrolment, enrolment_track_id)
    if current is None:
        return
    _close(current, status, reason)
    _after_seat_change(enrolment)


def end_all(enrolment: Enrolment, status: str = "Ended", *, reason: str | None = None) -> None:
    """End every seat the enrolment holds (a service-branch transfer or cancellation moves the whole admission)."""
    for allocation in batches_repo.active_allocations_of(enrolment.enrolment_id):
        _close(allocation, status, reason)
    _after_seat_change(enrolment)


def _after_seat_change(enrolment: Enrolment) -> None:
    db.session.flush()
    if enrolment.status == "Allocated — awaiting first regular class" and not batches_repo.active_allocations_of(enrolment.enrolment_id):
        enrolment.status = "Allocation Pending"
    db.session.flush()

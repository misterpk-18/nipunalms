"""Waiting for a batch (UX phase U14): the students with an admission and no seat yet, each with the batches that could take them
now (same course and branch, a seat left) and what the allocation review says about each, so the Branch Manager can allocate in
one click. The allocation itself is `POST /batches/{id}/allocations`; nothing is bypassed.

A combo enrolment can be seated whole, or track by track: each track still without a seat is offered the batches that teach it.
A match the review blocks is left out; one with a warning (another delivery mode, a timetable clash) is offered but must be
acknowledged.
"""
from config.database import db
from config.timezone import IST, today_ist
from models import Batch, Enrolment
from repositories import batches as batches_repo
from repositories import enrolments as enrolments_repo
from services import allocations, batch_allocations, delivery_access, scope
from services import batches as batches_service
from services import enrolments as enrolments_service

# The most students the screen for one batch lists at once
BATCH_LIST_LIMIT = 100


def _timetable(batch: Batch) -> dict:
    d = batch.to_dict()
    return {"schedule_days": d["schedule_days"], "start_time": d["start_time"], "end_time": d["end_time"], "location": batch.location}


def _batch_block(batch: Batch, taken: int) -> dict:
    return {**batch.to_summary(), "state": batch.state, "state_label": batch.to_dict()["state_label"], "mode": batch.mode, "capacity": batch.capacity,
            "allocated": taken, "seats_left": max(batch.capacity - taken, 0), "planned_start": batch.planned_start, **_timetable(batch),
            "trainers": [t.trainer.full_name for t in batch.trainers if t.to_date is None]}


def _targets(enrolment: Enrolment) -> list:
    """What still needs a seat: the whole enrolment and, for a combo, each track that has none (a waiting enrolment holds no seat)."""
    return [None] + [t for t in enrolment.tracks if allocations.current_seat(enrolment, t.enrolment_track_id) is None]


def _candidates(enrolment: Enrolment, target) -> list[Batch]:
    """Open batches at the service branch that teach the target; for a track also those of the track's own course."""
    course_ids = {enrolment.course_id} | ({target.component.component_course_id} if target is not None else set())
    found: dict[int, Batch] = {}
    for course_id in course_ids:
        for batch in batches_repo.open_batches_for(course_id, enrolment.service_branch_id):
            found[batch.batch_id] = batch
    track_id = target.enrolment_track_id if target is not None else None
    return [b for b in found.values() if allocations.teaches(b, enrolment, track_id) is None
            # the batch of the whole programme is offered once, for the whole enrolment
            and not (target is not None and b.component_id is None and b.course_id == enrolment.course_id)]


def matches_for(enrolment: Enrolment, only_batch: Batch | None = None) -> tuple[list[dict], list[dict]]:
    """The batches that could take this enrolment now, with the review result of each, and the ones the review blocks with why.
    Full batches are left out."""
    matches, blocked = [], []
    for target in _targets(enrolment):
        track_id = target.enrolment_track_id if target is not None else None
        batches = _candidates(enrolment, target)
        if only_batch is not None:
            batches = [b for b in batches if b.batch_id == only_batch.batch_id]
        taken = batches_repo.allocated_counts([b.batch_id for b in batches])
        for batch in batches:
            if taken.get(batch.batch_id, 0) >= batch.capacity:
                continue
            report = batch_allocations.review(batch, enrolment, enrolment_track_id=track_id)
            if report["blocking"]:
                blocked.append({"batch": batch.to_summary(), "reasons": report["blocking"]})
                continue
            matches.append({"batch": _batch_block(batch, taken.get(batch.batch_id, 0)), "result": report["result"], "warnings": report["warnings"],
                            "preferred": batch.batch_code == enrolment.admission.preferred_batch_code,
                            "track": {"enrolment_track_id": track_id, "track_code": target.component.track_code,
                                      "track_name": target.component.track_name} if target is not None else None})
    return matches, blocked


def _row(enrolment: Enrolment, student, matches: list[dict], blocked: list[dict]) -> dict:
    today = today_ist()
    due = batch_allocations.allocation_due_on(enrolment)
    return {
        "enrolment": enrolment.to_summary(), "student": student.to_summary(), "course": enrolment.course.to_summary(),
        "branch": enrolment.service_branch.to_summary(), "mode": enrolment.mode,
        "waiting_days": (today - enrolment.updated_at.astimezone(IST).date()).days,
        "preferred_batch_code": enrolment.admission.preferred_batch_code,
        "allocation_due_on": due, "overdue": due is not None and due < today, "matches": matches, "blocked": blocked,
    }


def waiting(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """The students waiting for a batch in the user's branches, longest wait first, each with matching batches."""
    rows, meta = enrolments_service.allocation_queue(filters, page, per_page)
    return [_row(r.enrolment, r.student, *matches_for(r.enrolment)) for r in rows], meta


def waiting_for_batch(batch_id: int) -> dict:
    """Who on the waiting list could join this batch (for "Add students from waiting list" on the batch page)."""
    batch, taken = batches_service.get_batch(batch_id)
    delivery_access.assert_can_manage_branch(batch.branch_id)
    stmt = enrolments_repo.list_stmt({"status": "Allocation Pending", "branch_id": batch.branch_id}, scope.visible_branch_ids(), set())
    stmt = stmt.order_by(None).order_by(Enrolment.updated_at, Enrolment.enrolment_id)
    enrolments = list(db.session.execute(stmt).scalars().unique())
    students = enrolments_repo.students_by_id({e.student_id for e in enrolments})
    rows = []
    for enrolment in enrolments:
        matches, blocked = matches_for(enrolment, only_batch=batch)
        if matches:
            rows.append(_row(enrolment, students[enrolment.student_id], matches, blocked))
        if len(rows) >= BATCH_LIST_LIMIT:
            break
    return {"batch": _batch_block(batch, taken), "seats_left": max(batch.capacity - taken, 0), "students": rows}

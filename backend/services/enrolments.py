"""Staff views of enrolments: the people list of a branch or batch, and the allocation queue."""
from dataclasses import dataclass

from config.timezone import IST, today_ist
from models import Batch, Enrolment, Student
from repositories import batches as batches_repo
from repositories import enrolments as enrolments_repo
from repositories.common import paginate
from services import scope


@dataclass
class EnrolmentRow:
    enrolment: Enrolment
    student: Student
    batch: dict | None
    waiting_days: int | None = None
    open_batches: list[Batch] | None = None


def _rows(enrolments: list[Enrolment]) -> list[EnrolmentRow]:
    students = enrolments_repo.students_by_id({e.student_id for e in enrolments})
    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    return [EnrolmentRow(e, students[e.student_id], allocations[e.enrolment_id].batch.to_summary() if e.enrolment_id in allocations else None)
            for e in enrolments]


def list_enrolments(filters: dict, page: int, per_page: int) -> tuple[list[EnrolmentRow], dict]:
    """Enrolments in the user's branches; a trainer sees the students of their own batches."""
    tied = batches_repo.enrolment_ids_in_batches(scope.trainer_batch_ids())
    enrolments, meta = paginate(enrolments_repo.list_stmt(filters, scope.visible_branch_ids(), tied), page, per_page)
    return _rows(enrolments), meta


def allocation_queue(filters: dict, page: int, per_page: int) -> tuple[list[EnrolmentRow], dict]:
    """Enrolments waiting for a batch (Allocation Pending), longest wait first, with the batches that could take them."""
    stmt = enrolments_repo.list_stmt({**filters, "status": "Allocation Pending"}, scope.visible_branch_ids(), set())
    stmt = stmt.order_by(None).order_by(Enrolment.updated_at, Enrolment.enrolment_id)
    enrolments, meta = paginate(stmt, page, per_page)
    rows = _rows(enrolments)
    candidates: dict[tuple[int, int], list[Batch]] = {}
    today = today_ist()
    for row in rows:
        key = (row.enrolment.course_id, row.enrolment.service_branch_id)
        if key not in candidates:
            candidates[key] = batches_repo.open_batches_for(*key)
        row.open_batches = candidates[key]
        row.waiting_days = (today - row.enrolment.updated_at.astimezone(IST).date()).days
    return rows, meta


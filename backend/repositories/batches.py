"""Batches, trainer assignments, allocations and class sessions."""
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import (
    Batch, BatchAllocation, BatchEvent, BatchTrainer, Course, Enrolment, Student, User,
)


def get_batch(batch_id: int) -> Batch | None:
    return db.session.get(Batch, batch_id)


def get_batch_for_update(batch_id: int) -> Batch | None:
    """The batch, row-locked so concurrent seat changes and state changes are serialised."""
    return db.session.execute(
        select(Batch).where(Batch.batch_id == batch_id).with_for_update(of=Batch).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def get_batch_by_crm_id(crm_batch_id: str) -> Batch | None:
    return db.session.execute(select(Batch).where(Batch.crm_batch_id == crm_batch_id)).scalar_one_or_none()


def _scope_condition(column, other_column, branch_ids: set[int] | None, ids: set[int]):
    """Rows in the user's branches, or with an id the user is tied to (assigned batch / own batch)."""
    return column.in_(branch_ids) | other_column.in_(ids)


def list_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    """Batches, restricted to branch_ids (None = all) or to the given batch ids, then narrowed by the filters."""
    stmt = select(Batch).options(selectinload(Batch.trainers)).order_by(Batch.branch_id, Batch.batch_code)
    if branch_ids is not None:
        stmt = stmt.where(_scope_condition(Batch.branch_id, Batch.batch_id, branch_ids, batch_ids))
    if filters.get("branch_id"):
        stmt = stmt.where(Batch.branch_id == filters["branch_id"])
    if filters.get("course_id"):
        stmt = stmt.where(Batch.course_id == filters["course_id"])
    if filters.get("state"):
        stmt = stmt.where(Batch.state == filters["state"])
    if filters.get("mode"):
        stmt = stmt.where(Batch.mode == filters["mode"])
    if filters.get("readiness"):
        stmt = stmt.where(Batch.readiness == filters["readiness"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(Batch.course_id.in_(
            select(Course.course_id).where(or_(Course.title.ilike(pattern), Course.course_code.ilike(pattern)))
        ) | Batch.batch_code.ilike(pattern))
    return stmt


def allocated_counts(batch_ids: list[int]) -> dict[int, int]:
    """Students holding a seat (an active allocation) per batch."""
    if not batch_ids:
        return {}
    rows = db.session.execute(
        select(BatchAllocation.batch_id, func.count(func.distinct(BatchAllocation.enrolment_id)))
        .where(BatchAllocation.batch_id.in_(batch_ids), BatchAllocation.status == "Active")
        .group_by(BatchAllocation.batch_id)
    )
    return dict(rows.all())


def batch_ids_for_trainer(user_id: int, today: date) -> set[int]:
    """Batches the trainer is currently assigned to."""
    stmt = select(BatchTrainer.batch_id).where(
        BatchTrainer.trainer_user_id == user_id,
        BatchTrainer.from_date <= today,
        BatchTrainer.to_date.is_(None) | (BatchTrainer.to_date >= today),
    )
    return set(db.session.execute(stmt).scalars())


def batch_ids_for_enrolments(enrolment_ids: set[int]) -> set[int]:
    """Batches holding an active allocation of any of these enrolments."""
    if not enrolment_ids:
        return set()
    stmt = select(BatchAllocation.batch_id).where(
        BatchAllocation.enrolment_id.in_(enrolment_ids), BatchAllocation.status == "Active"
    )
    return set(db.session.execute(stmt).scalars())


def enrolment_ids_in_batches(batch_ids: set[int]) -> set[int]:
    """Enrolments holding an active allocation in any of these batches."""
    if not batch_ids:
        return set()
    stmt = select(BatchAllocation.enrolment_id).where(
        BatchAllocation.batch_id.in_(batch_ids), BatchAllocation.status == "Active"
    )
    return set(db.session.execute(stmt).scalars())


def active_allocation(enrolment_id: int) -> BatchAllocation | None:
    return db.session.execute(
        select(BatchAllocation).where(BatchAllocation.enrolment_id == enrolment_id, BatchAllocation.status == "Active")
    ).scalars().first()


def active_allocations(enrolment_ids: list[int]) -> dict[int, BatchAllocation]:
    if not enrolment_ids:
        return {}
    stmt = select(BatchAllocation).where(
        BatchAllocation.enrolment_id.in_(enrolment_ids), BatchAllocation.status == "Active"
    )
    return {a.enrolment_id: a for a in db.session.execute(stmt).scalars()}


# ---------------------------------------------------------------- management: trainers, roster, history

def get_batch_trainer(batch_trainer_id: int) -> BatchTrainer | None:
    return db.session.get(BatchTrainer, batch_trainer_id)


def trainer_history(batch_id: int) -> list[BatchTrainer]:
    """Every trainer assignment of the batch, current ones first."""
    stmt = select(BatchTrainer).where(BatchTrainer.batch_id == batch_id).order_by(
        BatchTrainer.to_date.is_not(None), BatchTrainer.from_date, BatchTrainer.batch_trainer_id)
    return list(db.session.execute(stmt).scalars())


def lead_trainer(batch_id: int) -> BatchTrainer | None:
    return db.session.execute(
        select(BatchTrainer).where(BatchTrainer.batch_id == batch_id, BatchTrainer.role == "Lead", BatchTrainer.to_date.is_(None))
    ).scalar_one_or_none()


def add_event(batch_id: int, event_type: str, *, from_value: str | None = None, to_value: str | None = None,
              reason: str | None = None, actor_user_id: int | None = None) -> None:
    db.session.add(BatchEvent(batch_id=batch_id, event_type=event_type, from_value=from_value, to_value=to_value,
                              reason=reason, actor_user_id=actor_user_id))


def events(batch_id: int, limit: int = 50) -> list[BatchEvent]:
    stmt = (select(BatchEvent).where(BatchEvent.batch_id == batch_id)
            .order_by(BatchEvent.created_at.desc(), BatchEvent.event_id.desc()).limit(limit))
    return list(db.session.execute(stmt).scalars())


def roster_stmt(batch_id: int, status: str | None) -> Select:
    """Allocations of a batch with their enrolment and student."""
    stmt = (
        select(BatchAllocation)
        .join(Enrolment, Enrolment.enrolment_id == BatchAllocation.enrolment_id)
        .join(Student, Student.student_id == Enrolment.student_id)
        .where(BatchAllocation.batch_id == batch_id)
        .order_by(BatchAllocation.status, Student.full_name, BatchAllocation.allocation_id)
    )
    if status:
        stmt = stmt.where(BatchAllocation.status == status)
    return stmt


def student_user_ids_for_batch(batch_id: int) -> list[int]:
    """Login accounts of the students holding a seat in the batch (for notices)."""
    stmt = (
        select(func.distinct(User.user_id))
        .join(Enrolment, Enrolment.student_id == User.student_id)
        .join(BatchAllocation, BatchAllocation.enrolment_id == Enrolment.enrolment_id)
        .where(BatchAllocation.batch_id == batch_id, BatchAllocation.status == "Active")
    )
    return list(db.session.execute(stmt).scalars())


def allocations_of_enrolment(enrolment_id: int) -> list[BatchAllocation]:
    """Every allocation of the enrolment, oldest first (the transfer history)."""
    stmt = select(BatchAllocation).where(BatchAllocation.enrolment_id == enrolment_id).order_by(BatchAllocation.allocation_id)
    return list(db.session.execute(stmt).scalars())


def open_batches_for(course_id: int, branch_id: int) -> list[Batch]:
    """Batches of this course at this branch that can still take students."""
    stmt = select(Batch).where(
        Batch.course_id == course_id, Batch.branch_id == branch_id, Batch.state.in_(("Forming", "Starting", "Running", "Full"))
    ).order_by(Batch.batch_code)
    return list(db.session.execute(stmt).scalars())

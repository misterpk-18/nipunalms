"""Batches, trainer assignments, allocations and class sessions."""
from datetime import date, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from config.database import db
from config.timezone import IST
from models import Batch, BatchAllocation, BatchTrainer, ClassSession


def get_batch(batch_id: int) -> Batch | None:
    return db.session.get(Batch, batch_id)


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


def sessions_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    """Class sessions of the visible batches, filtered by batch and by IST dates (from and to both inclusive)."""
    stmt = select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id).order_by(
        ClassSession.starts_at, ClassSession.session_id
    )
    if branch_ids is not None:
        stmt = stmt.where(_scope_condition(Batch.branch_id, Batch.batch_id, branch_ids, batch_ids))
    if filters.get("batch_id"):
        stmt = stmt.where(ClassSession.batch_id == filters["batch_id"])
    if filters.get("from"):
        stmt = stmt.where(ClassSession.starts_at >= _start_of_day(filters["from"]))
    if filters.get("to"):
        stmt = stmt.where(ClassSession.starts_at < _start_of_day(filters["to"] + timedelta(days=1)))
    return stmt


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=IST)

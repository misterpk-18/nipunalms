"""Results (provisional, moderated, published) and the per-assessment summaries the moderation screen reads."""
from sqlalchemy import Select, func, select

from config.database import db
from models import Assignment, Result, Test


def get_result(result_id: int) -> Result | None:
    return db.session.get(Result, result_id)


def for_assignment(assignment_id: int, enrolment_id: int) -> Result | None:
    return db.session.execute(
        select(Result).where(Result.assignment_id == assignment_id, Result.enrolment_id == enrolment_id)
    ).scalar_one_or_none()


def for_test(test_id: int, enrolment_id: int) -> Result | None:
    return db.session.execute(
        select(Result).where(Result.test_id == test_id, Result.enrolment_id == enrolment_id)
    ).scalar_one_or_none()


def for_enrolments(enrolment_ids: set[int]) -> list[Result]:
    """Every result row of these enrolments, whatever its status (callers decide what a student may see)."""
    if not enrolment_ids:
        return []
    stmt = select(Result).where(Result.enrolment_id.in_(enrolment_ids)).order_by(Result.updated_at.desc(), Result.result_id)
    return list(db.session.execute(stmt).scalars())


def list_stmt(filters: dict, batch_clause=None) -> Select:
    """Staff view of results, narrowed by batch, item and status."""
    stmt = select(Result).order_by(Result.batch_id, Result.assignment_id, Result.test_id, Result.student_id)
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Result.batch_id))
    if filters.get("batch_id"):
        stmt = stmt.where(Result.batch_id == filters["batch_id"])
    if filters.get("assignment_id"):
        stmt = stmt.where(Result.assignment_id == filters["assignment_id"])
    if filters.get("test_id"):
        stmt = stmt.where(Result.test_id == filters["test_id"])
    if filters.get("status"):
        stmt = stmt.where(Result.status == filters["status"])
    return stmt


def status_counts(batch_clause=None, batch_id: int | None = None) -> list[tuple]:
    """(assignment_id, test_id, batch_id, status, count) rows: the raw material of the moderation queue."""
    stmt = select(Result.assignment_id, Result.test_id, Result.batch_id, Result.status, func.count()).group_by(
        Result.assignment_id, Result.test_id, Result.batch_id, Result.status
    )
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Result.batch_id))
    if batch_id:
        stmt = stmt.where(Result.batch_id == batch_id)
    return list(db.session.execute(stmt).all())


def assignments_by_ids(ids: set[int]) -> dict[int, Assignment]:
    if not ids:
        return {}
    return {a.assignment_id: a for a in db.session.execute(select(Assignment).where(Assignment.assignment_id.in_(ids))).scalars().unique()}


def tests_by_ids(ids: set[int]) -> dict[int, Test]:
    if not ids:
        return {}
    return {t.test_id: t for t in db.session.execute(select(Test).where(Test.test_id.in_(ids))).scalars().unique()}

"""Completion reviews: queries only."""
from sqlalchemy import Select, or_, select

from config.database import db
from models import CompletionReview, Enrolment, Student


def get_review(review_id: int) -> CompletionReview | None:
    return db.session.get(CompletionReview, review_id)


def open_review(enrolment_id: int) -> CompletionReview | None:
    return db.session.execute(
        select(CompletionReview).where(CompletionReview.enrolment_id == enrolment_id, CompletionReview.status == "Open")
    ).unique().scalar_one_or_none()


def latest_reviews(enrolment_ids: list[int]) -> dict[int, CompletionReview]:
    """The newest review (open or decided) per enrolment."""
    if not enrolment_ids:
        return {}
    stmt = (
        select(CompletionReview)
        .where(CompletionReview.enrolment_id.in_(enrolment_ids))
        .order_by(CompletionReview.review_id)
    )
    return {r.enrolment_id: r for r in db.session.execute(stmt).unique().scalars()}  # later rows overwrite earlier ones


def candidates_stmt(filters: dict, scope_condition) -> Select:
    """Enrolments in scope that are being taught or completed (the completion review's rows)."""
    stmt = (
        select(Enrolment)
        .join(Student, Student.student_id == Enrolment.student_id)
        .where(scope_condition, Enrolment.status.in_(("Active", "Completed")))
        .order_by(Student.full_name, Enrolment.enrolment_id)
    )
    if filters.get("branch_id"):
        stmt = stmt.where(Enrolment.service_branch_id == filters["branch_id"])
    if filters.get("course_id"):
        stmt = stmt.where(Enrolment.course_id == filters["course_id"])
    if filters.get("status"):
        stmt = stmt.where(Enrolment.status == filters["status"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.full_name.ilike(pattern), Student.student_code.ilike(pattern)))
    return stmt

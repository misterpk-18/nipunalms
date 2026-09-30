"""Student accounts, for the Super Admin's Student Accounts screen."""
from sqlalchemy import Select, func, or_, select

from config.database import db
from models import ActiveSession, Course, Enrolment, Student, User


def search_stmt(filters: dict) -> Select:
    """Students with their login (if any), by name."""
    stmt = (
        select(Student, User)
        .outerjoin(User, User.student_id == Student.student_id)
        .order_by(Student.full_name, Student.student_id)
    )
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.student_code.ilike(pattern), Student.full_name.ilike(pattern), Student.email.ilike(pattern)))
    if filters.get("activation_status"):
        stmt = stmt.where(Student.activation_status == filters["activation_status"])
    if filters.get("branch_id"):
        stmt = stmt.where(Student.service_branch_id == filters["branch_id"])
    return stmt


def get_with_user(student_id: int) -> tuple[Student, User | None] | None:
    row = db.session.execute(
        select(Student, User).outerjoin(User, User.student_id == Student.student_id).where(Student.student_id == student_id)
    ).first()
    return (row[0], row[1]) if row else None


def enrolment_status_counts(student_ids: list[int]) -> dict[int, dict[str, int]]:
    """student_id -> {enrolment status: count}."""
    if not student_ids:
        return {}
    rows = db.session.execute(
        select(Enrolment.student_id, Enrolment.status, func.count())
        .where(Enrolment.student_id.in_(student_ids))
        .group_by(Enrolment.student_id, Enrolment.status)
    ).all()
    counts: dict[int, dict[str, int]] = {}
    for student_id, status, count in rows:
        counts.setdefault(student_id, {})[status] = count
    return counts


def enrolment_rows(student_id: int) -> list[tuple[Enrolment, Course]]:
    stmt = (
        select(Enrolment, Course)
        .join(Course, Course.course_id == Enrolment.course_id)
        .where(Enrolment.student_id == student_id)
        .order_by(Enrolment.enrolment_id)
    )
    return [(e, c) for e, c in db.session.execute(stmt).all()]


def active_session_counts(user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = db.session.execute(
        select(ActiveSession.user_id, func.count()).where(ActiveSession.user_id.in_(user_ids)).group_by(ActiveSession.user_id)
    ).all()
    return {user_id: count for user_id, count in rows}

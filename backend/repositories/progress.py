"""The four progress measures: reads over the `enrolment_progress` view (db/040), plus branch and batch summaries."""
from sqlalchemy import Select, case, func, or_, select, true

from config.database import db
from models import Batch, BatchAllocation, Certificate, Enrolment, EnrolmentProgress, Student


def enrolment_scope_condition(branch_ids: set[int] | None, batch_ids: set[int], own_enrolment_ids: set[int]):
    """Enrolments a user may see: their branches (None = all), the students of their batches, or their own."""
    if branch_ids is None:
        return true()
    condition = Enrolment.service_branch_id.in_(branch_ids)
    if batch_ids:
        condition = or_(condition, Enrolment.enrolment_id.in_(
            select(BatchAllocation.enrolment_id).where(BatchAllocation.batch_id.in_(batch_ids), BatchAllocation.status == "Active")))
    if own_enrolment_ids:
        condition = or_(condition, Enrolment.enrolment_id.in_(own_enrolment_ids))
    return condition


def get_progress(enrolment_id: int) -> EnrolmentProgress | None:
    return db.session.get(EnrolmentProgress, enrolment_id)


def progress_by_enrolment(enrolment_ids: list[int]) -> dict[int, EnrolmentProgress]:
    if not enrolment_ids:
        return {}
    stmt = select(EnrolmentProgress).where(EnrolmentProgress.enrolment_id.in_(enrolment_ids))
    return {p.enrolment_id: p for p in db.session.execute(stmt).scalars()}


def progress_stmt(filters: dict, scope_condition) -> Select:
    """Progress rows (EnrolmentProgress, Enrolment) of the visible enrolments that are being taught or were completed."""
    stmt = (
        select(EnrolmentProgress, Enrolment)
        .join(Enrolment, Enrolment.enrolment_id == EnrolmentProgress.enrolment_id)
        .join(Student, Student.student_id == Enrolment.student_id)
        .where(scope_condition, Enrolment.status.in_(("Allocated — awaiting first regular class", "Active", "Paused", "Completed")))
        .order_by(Student.full_name, Enrolment.enrolment_id)
    )
    if filters.get("branch_id"):
        stmt = stmt.where(Enrolment.service_branch_id == filters["branch_id"])
    if filters.get("course_id"):
        stmt = stmt.where(Enrolment.course_id == filters["course_id"])
    if filters.get("status"):
        stmt = stmt.where(Enrolment.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.where(Enrolment.enrolment_id.in_(
            select(BatchAllocation.enrolment_id).where(BatchAllocation.batch_id == filters["batch_id"], BatchAllocation.status == "Active")))
    if filters.get("alert"):
        stmt = stmt.where(EnrolmentProgress.attendance_alert.is_(True))
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.full_name.ilike(pattern), Student.student_code.ilike(pattern)))
    return stmt


def batch_summaries(scope_condition, branch_id: int | None) -> list[dict]:
    """Per batch: seats in use and the average of each measure over its students (measures are averaged separately)."""
    stmt = (
        select(
            Batch,
            func.count(func.distinct(Enrolment.enrolment_id)).label("students"),
            func.avg(EnrolmentProgress.delivery_pct).label("avg_delivery"),
            func.avg(EnrolmentProgress.attendance_pct).label("avg_attendance"),
            func.avg(EnrolmentProgress.required_pct).label("avg_required"),
            func.count(case((EnrolmentProgress.attendance_alert.is_(True), 1))).label("alerts"),
            func.count(case((EnrolmentProgress.attendance_state == "Partial Data", 1))).label("partial"),
        )
        .join(BatchAllocation, BatchAllocation.batch_id == Batch.batch_id)
        .join(Enrolment, Enrolment.enrolment_id == BatchAllocation.enrolment_id)
        .join(EnrolmentProgress, EnrolmentProgress.enrolment_id == Enrolment.enrolment_id)
        .where(BatchAllocation.status == "Active", scope_condition)
        .group_by(Batch.batch_id)
        .order_by(Batch.branch_id, Batch.batch_code)
    )
    if branch_id:
        stmt = stmt.where(Batch.branch_id == branch_id)
    return [
        {"batch": batch, "students": students, "avg_delivery": _avg(delivery), "avg_attendance": _avg(attendance),
         "avg_required": _avg(required), "alerts": alerts, "partial_data": partial}
        for batch, students, delivery, attendance, required, alerts, partial in db.session.execute(stmt).unique().all()
    ]


def _avg(value) -> float | None:
    return None if value is None else round(float(value), 1)


def enrolment_status_counts(scope_condition, branch_id: int | None) -> dict[str, int]:
    """Enrolments per status among those in scope (for completion summaries)."""
    stmt = select(Enrolment.status, func.count()).where(scope_condition).group_by(Enrolment.status)
    if branch_id:
        stmt = stmt.where(Enrolment.service_branch_id == branch_id)
    return {str(status): count for status, count in db.session.execute(stmt).all()}


def certificate_status_counts(branch_ids: set[int] | None, branch_id: int | None) -> dict[str, int]:
    stmt = select(Certificate.status, func.count()).group_by(Certificate.status)
    if branch_ids is not None:
        stmt = stmt.where(Certificate.branch_id.in_(branch_ids))
    if branch_id:
        stmt = stmt.where(Certificate.branch_id == branch_id)
    return {str(status): count for status, count in db.session.execute(stmt).all()}


def students_by_id(student_ids: set[int]) -> dict[int, Student]:
    if not student_ids:
        return {}
    return {s.student_id: s for s in db.session.execute(select(Student).where(Student.student_id.in_(student_ids))).unique().scalars()}

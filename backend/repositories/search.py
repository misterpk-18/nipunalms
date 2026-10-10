"""Record search behind the Ctrl/Cmd+K palette. Callers pass what the user may see; nothing here decides scope."""
from sqlalchemy import exists, or_, select

from config.database import db
from models import Batch, Certificate, Course, Enrolment, Student


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def students(text: str, branch_ids: set[int] | None, enrolment_ids: set[int], limit: int) -> list[Student]:
    """Students matching by name or Student ID. branch_ids: None = every branch, else the branches seen in full;
    enrolment_ids: enrolments seen through a batch the user teaches."""
    pattern = _like(text)
    stmt = select(Student).where(or_(Student.full_name.ilike(pattern, escape="\\"), Student.student_code.ilike(pattern, escape="\\")))
    if branch_ids is not None:
        visible = []
        if branch_ids:
            visible += [Student.service_branch_id.in_(branch_ids),
                        exists().where(Enrolment.student_id == Student.student_id, Enrolment.service_branch_id.in_(branch_ids))]
        if enrolment_ids:
            visible.append(exists().where(Enrolment.student_id == Student.student_id, Enrolment.enrolment_id.in_(enrolment_ids)))
        if not visible:
            return []
        stmt = stmt.where(or_(*visible))
    return list(db.session.execute(stmt.order_by(Student.full_name).limit(limit)).scalars().unique())


def batches(text: str, branch_ids: set[int] | None, batch_ids: set[int], limit: int) -> list[Batch]:
    pattern = _like(text)
    stmt = select(Batch).join(Course, Course.course_id == Batch.course_id).where(
        or_(Batch.batch_code.ilike(pattern, escape="\\"), Batch.display_name.ilike(pattern, escape="\\"), Course.title.ilike(pattern, escape="\\")))
    if branch_ids is not None:
        visible = []
        if branch_ids:
            visible.append(Batch.branch_id.in_(branch_ids))
        if batch_ids:
            visible.append(Batch.batch_id.in_(batch_ids))
        if not visible:
            return []
        stmt = stmt.where(or_(*visible))
    return list(db.session.execute(stmt.order_by(Batch.batch_code.desc()).limit(limit)).scalars().unique())


def certificates(text: str, branch_ids: set[int] | None, limit: int) -> list[Certificate]:
    """Register entries by holder name or certificate number (a superseded version is never offered)."""
    if branch_ids is not None and not branch_ids:
        return []
    pattern = _like(text)
    stmt = select(Certificate).where(Certificate.status != "Superseded",
                                     or_(Certificate.holder_name.ilike(pattern, escape="\\"), Certificate.certificate_number.ilike(pattern, escape="\\")))
    if branch_ids is not None:
        stmt = stmt.where(Certificate.branch_id.in_(branch_ids))
    return list(db.session.execute(stmt.order_by(Certificate.certificate_id.desc()).limit(limit)).scalars().unique())

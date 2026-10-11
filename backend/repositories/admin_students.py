"""Student accounts, for the Super Admin's Student Accounts screen."""
from datetime import datetime

from sqlalchemy import Select, and_, exists, func, or_, select

from config.database import db
from models import ActiveSession, Admission, Course, Enrolment, Student, StudentActivation, User, WhatsappMessage


def needs_attention_clause():
    """The SQL of `services/student_next_step.next_step(...).attention` (a test keeps them in step)."""
    carried_link = exists().where(
        StudentActivation.student_id == Student.student_id, StudentActivation.used_at.is_(None), StudentActivation.revoked_at.is_(None),
        StudentActivation.expires_at > func.now(),
        exists().where(WhatsappMessage.dedupe_key == func.concat("activation-link:", StudentActivation.activation_id),
                       WhatsappMessage.status.in_(("Queued", "Sent"))).correlate(StudentActivation))
    held_back = exists().where(Enrolment.student_id == Student.student_id, Enrolment.status == "Provisioning Pending")
    return and_(Student.activation_status != "Suspended", or_(
        and_(Student.activation_status.in_(("Account Created", "Activation Pending")), ~carried_link),
        and_(Student.activation_status == "Activated", or_(User.user_id.is_(None), User.is_active.is_(False))),
        held_back,
    ))


def search_stmt(filters: dict) -> Select:
    """Students with their login (if any), by name."""
    stmt = (
        select(Student, User)
        .outerjoin(User, User.student_id == Student.student_id)
        .order_by(Student.full_name, Student.student_id)
    )
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.student_code.ilike(pattern), Student.full_name.ilike(pattern), Student.email.ilike(pattern),
                              Student.mobile.ilike(pattern),
                              Student.student_id.in_(select(Admission.student_id).where(Admission.admission_code.ilike(pattern)))))
    if filters.get("activation_status"):
        stmt = stmt.where(Student.activation_status == filters["activation_status"])
    if filters.get("branch_id"):
        stmt = stmt.where(Student.service_branch_id == filters["branch_id"])
    if filters.get("needs_attention"):
        stmt = stmt.where(needs_attention_clause())
    if filters.get("activation_channel"):
        # whose outstanding link came from this channel: 'CRM provisioning' = never delivered, a Branch Manager must reissue
        stmt = stmt.where(select(StudentActivation.activation_id).where(
            StudentActivation.student_id == Student.student_id, StudentActivation.used_at.is_(None),
            StudentActivation.revoked_at.is_(None), StudentActivation.channel == filters["activation_channel"]).exists())
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


def outstanding_activations(student_ids: list[int]) -> dict[int, StudentActivation]:
    """student_id -> the unused, unrevoked activation token (it may be expired)."""
    if not student_ids:
        return {}
    stmt = select(StudentActivation).where(StudentActivation.student_id.in_(student_ids), StudentActivation.used_at.is_(None),
                                           StudentActivation.revoked_at.is_(None))
    return {a.student_id: a for a in db.session.execute(stmt).scalars().unique()}


def activation_messages(activation_ids: list[int]) -> dict[int, WhatsappMessage]:
    """activation_id -> the WhatsApp message that carried (or failed to carry) its link."""
    if not activation_ids:
        return {}
    keys = {f"activation-link:{i}": i for i in activation_ids}
    rows = db.session.execute(select(WhatsappMessage).where(WhatsappMessage.dedupe_key.in_(list(keys)))).scalars()
    return {keys[m.dedupe_key]: m for m in rows}


def needs_attention_count() -> int:
    stmt = (select(func.count()).select_from(Student).outerjoin(User, User.student_id == Student.student_id).where(needs_attention_clause()))
    return db.session.execute(stmt).scalar_one()

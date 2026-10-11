"""Support requests, their messages, and the trainer's assigned-student list."""
from datetime import date, datetime

from sqlalchemy import Select, case, exists, func, or_, select

from config.database import db
from models import Batch, BatchAllocation, Enrolment, Student, SupportAttachment, SupportMessage, SupportRequest, User
from models.support import SUPPORT_OPEN_STATUSES


# The staff views of the request list (UX phase U15): what the status means for the person who answers
VIEWS = {
    "needs_action": ("Open", "In Progress"),
    "waiting": ("Waiting on Student",),
    "done": ("Resolved", "Closed"),
    "all": ("Open", "In Progress", "Waiting on Student", "Resolved", "Closed"),
}


def count_stmt(stmt: Select) -> int:
    return db.session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()


def reply_marks(request_ids: list[int]) -> dict[int, str]:
    """request id -> 'new_reply' (the student wrote last, after staff had answered) or 'new_request' (only the student has written)."""
    if not request_ids:
        return {}
    stmt = (select(SupportMessage.support_request_id, SupportMessage.support_message_id, User.student_id)
            .join(User, User.user_id == SupportMessage.author_user_id, isouter=True)
            .where(SupportMessage.support_request_id.in_(request_ids), SupportMessage.is_internal.is_(False), SupportMessage.kind == "Message")
            .order_by(SupportMessage.support_request_id, SupportMessage.support_message_id))
    last: dict[int, bool] = {}
    staff_spoke: set[int] = set()
    for request_id, _, student_id in db.session.execute(stmt).all():
        last[request_id] = student_id is not None
        if student_id is None:
            staff_spoke.add(request_id)
    return {rid: ("new_reply" if rid in staff_spoke else "new_request") for rid, from_student in last.items() if from_student}


def needing_attention(branch_ids: set[int] | None, due_by: datetime) -> int:
    """Open requests that are near or past their reply deadline, or where the student wrote last (the navigation badge)."""
    open_ = select(SupportRequest.support_request_id, SupportRequest.sla_due_at).where(SupportRequest.status.in_(("Open", "In Progress")))
    if branch_ids is not None:
        open_ = open_.where(SupportRequest.branch_id.in_(branch_ids))
    rows = db.session.execute(open_).all()
    marks = reply_marks([r[0] for r in rows])
    return sum(1 for rid, due in rows if due <= due_by or marks.get(rid) == "new_reply")


def get_request(support_request_id: int) -> SupportRequest | None:
    return db.session.get(SupportRequest, support_request_id)


def list_stmt(filters: dict, *, student_id: int | None, branch_ids: set[int] | None, user_id: int, all_branches: bool,
              trainer: bool) -> Select:
    """Requests the user may see, narrowed by the filters.

    student_id: a student sees only their own. Staff see: everything (all_branches), requests at their branches
    (branch_ids), and - as trainer or as anyone - requests they own or raised.
    """
    stmt = select(SupportRequest).order_by(SupportRequest.created_at.desc(), SupportRequest.support_request_id.desc())
    if student_id is not None:
        # What waits on the student comes first, then the newest
        waiting = case((SupportRequest.status == "Waiting on Student", 0), else_=1)
        stmt = stmt.order_by(None).order_by(waiting, SupportRequest.created_at.desc(), SupportRequest.support_request_id.desc())
        stmt = stmt.where(SupportRequest.student_id == student_id)
    elif not all_branches:
        visible = [SupportRequest.owner_user_id == user_id]
        if trainer:
            visible.append(SupportRequest.raised_by_user_id == user_id)
        if branch_ids:
            visible.append(SupportRequest.branch_id.in_(branch_ids))
        stmt = stmt.where(or_(*visible))

    view = filters.get("view")
    if view and student_id is None:
        stmt = stmt.where(SupportRequest.status.in_(VIEWS[view]))
        if view == "needs_action":  # the nearest reply deadline first (overdue ones lead)
            stmt = stmt.order_by(None).order_by(SupportRequest.sla_due_at, SupportRequest.support_request_id)
        elif view != "all":
            stmt = stmt.order_by(None).order_by(SupportRequest.updated_at.desc(), SupportRequest.support_request_id.desc())
    if filters.get("status"):
        stmt = stmt.where(SupportRequest.status == filters["status"])
    if filters.get("open"):
        stmt = stmt.where(SupportRequest.status.in_(SUPPORT_OPEN_STATUSES))
    if filters.get("category"):
        stmt = stmt.where(SupportRequest.category == filters["category"])
    if filters.get("branch_id"):
        stmt = stmt.where(SupportRequest.branch_id == filters["branch_id"])
    if filters.get("student_id"):
        stmt = stmt.where(SupportRequest.student_id == filters["student_id"])
    if filters.get("escalated") is not None:
        escalated = SupportRequest.escalation_level == "Branch Manager"
        stmt = stmt.where(escalated if filters["escalated"] else ~escalated)
    if filters.get("mine"):
        stmt = stmt.where(or_(SupportRequest.owner_user_id == user_id, SupportRequest.raised_by_user_id == user_id))
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.join(Student, Student.student_id == SupportRequest.student_id).where(
            or_(SupportRequest.request_code.ilike(pattern), SupportRequest.subject.ilike(pattern),
                Student.full_name.ilike(pattern), Student.student_code.ilike(pattern))
        )
    return stmt


def overdue_requests(now: datetime) -> list[SupportRequest]:
    """Open requests past their SLA that have not yet reached the Branch Manager."""
    stmt = select(SupportRequest).where(
        SupportRequest.status.in_(SUPPORT_OPEN_STATUSES),
        SupportRequest.sla_due_at < now,
        or_(SupportRequest.escalation_level.is_(None), SupportRequest.escalation_level != "Branch Manager"),
    )
    return list(db.session.execute(stmt).scalars())


def add_message(request: SupportRequest, author_user_id: int | None, body: str, *, kind: str = "Message",
                is_internal: bool = False) -> SupportMessage:
    message = SupportMessage(support_request_id=request.support_request_id, author_user_id=author_user_id, kind=kind,
                             body=body, is_internal=is_internal)
    db.session.add(message)
    db.session.flush()
    db.session.expire(request, ["messages"])
    return message


def add_attachment(message: SupportMessage, uploaded_by_user_id: int, stored: dict) -> SupportAttachment:
    attachment = SupportAttachment(support_request_id=message.support_request_id, support_message_id=message.support_message_id,
                                   uploaded_by_user_id=uploaded_by_user_id, **stored)
    db.session.add(attachment)
    db.session.flush()
    db.session.expire(message, ["attachments"])
    return attachment


def get_attachment(attachment_id: int) -> SupportAttachment | None:
    return db.session.get(SupportAttachment, attachment_id)


def assigned_students(batch_ids: set[int]) -> list[tuple[Student, Batch, Enrolment]]:
    """Students holding an active seat in any of these batches, with the batch and the enrolment."""
    if not batch_ids:
        return []
    stmt = (
        select(Student, Batch, Enrolment)
        .join(Enrolment, Enrolment.student_id == Student.student_id)
        .join(BatchAllocation, BatchAllocation.enrolment_id == Enrolment.enrolment_id)
        .join(Batch, Batch.batch_id == BatchAllocation.batch_id)
        .where(BatchAllocation.status == "Active", BatchAllocation.batch_id.in_(batch_ids))
        .order_by(Batch.batch_code, Student.full_name, Student.student_id)
    )
    return [tuple(row) for row in db.session.execute(stmt).all()]


def open_requests_by_student(student_ids: list[int]) -> dict[int, list[SupportRequest]]:
    """Open requests per student (newest first), for the trainer's support flags."""
    if not student_ids:
        return {}
    stmt = (
        select(SupportRequest)
        .where(SupportRequest.student_id.in_(student_ids), SupportRequest.status.in_(SUPPORT_OPEN_STATUSES))
        .order_by(SupportRequest.created_at.desc())
    )
    grouped: dict[int, list[SupportRequest]] = {}
    for request in db.session.execute(stmt).scalars():
        grouped.setdefault(request.student_id, []).append(request)
    return grouped


def trainers_of_batch(batch: Batch, today: date) -> list[int]:
    """Users currently assigned to the batch, Lead first."""
    live = [t for t in batch.trainers if t.from_date <= today and (t.to_date is None or t.to_date >= today)]
    return [t.trainer_user_id for t in sorted(live, key=lambda t: (t.role != "Lead", t.batch_trainer_id))]

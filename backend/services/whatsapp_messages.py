"""The WhatsApp messages the LMS sends (templates 1-9), built from the records that changed.

Each function is called from the service that made the change, in the same transaction, and only queues a message
(services/whatsapp.py). A student with no WhatsApp number, or who switched the kind of message off, gets a Skipped row.
"""
from datetime import datetime, timedelta, timezone

from config.database import db
from config.timezone import IST
from models import Batch, Certificate, ClassSession, Result, SessionChange, StaffInvite, Student, StudentActivation, User, WhatsappMessage
from models.delivery_ops import MaterialChange
from repositories import class_sessions as sessions_repo
from repositories import whatsapp as whatsapp_repo
from services import whatsapp
from services import whatsapp_templates as templates

# A change that somehow has no reply-by date asks the student to answer within this many days
BATCH_CHANGE_REPLY_DAYS = 7
REMINDER_LEAD = timedelta(hours=2)
JOIN_OPENS = timedelta(minutes=15)
REPLACEMENT_NEXT_STEP = "your Branch Manager will share a replacement class or confirm that none is needed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def when(moment: datetime) -> str:
    """'Mon 12 Oct, 10:00 AM IST'."""
    local = moment.astimezone(IST)
    return f"{local:%a} {local.day} {local:%b}, {local.hour % 12 or 12}:{local:%M} {local:%p} IST"


def stamp(moment: datetime) -> str:
    """'13 Oct 2026, 6:00 PM IST'."""
    local = moment.astimezone(IST)
    return f"{local.day} {local:%b %Y}, {local.hour % 12 or 12}:{local:%M} {local:%p} IST"


def _day(moment: datetime) -> str:
    local = moment.astimezone(IST)
    return f"{local.day} {local:%b %Y}"


def _mode(session: ClassSession, batch: Batch) -> str:
    if session.mode == "Classroom":
        return ", ".join(part for part in ("Classroom", session.room, batch.branch.branch_name) if part)
    return session.mode


def _class_students(session: ClassSession):
    """(student, batch) for every student of every batch the class serves."""
    for batch_id in sessions_repo.session_batch_ids(session.session_id):
        batch = db.session.get(Batch, batch_id)
        for student in whatsapp_repo.batch_roster(batch_id):
            yield student, batch


# ---------------------------------------------------------------- 4: class reminder (job)

def class_reminders() -> dict:
    """Job `class-reminders`: remind each student of every confirmed class that starts within about two hours. A class confirmed
    inside the window is reminded at once while it is still more than 15 minutes away. The dedupe key holds the start time, so a
    moved class is reminded again for its new time and a class is never reminded twice for the same time."""
    now = _now()
    queued = 0
    for session in whatsapp_repo.sessions_starting_between(now + JOIN_OPENS, now + REMINDER_LEAD):
        for student, batch in _class_students(session):
            message = whatsapp.enqueue(
                templates.CLASS_REMINDER,
                {"student": student.full_name, "branch": batch.branch.branch_name, "class": session.title, "course": batch.course.title,
                 "start": when(session.starts_at), "mode": _mode(session, batch)},
                dedupe_key=f"class-reminder:{session.session_id}:{student.student_id}:{session.starts_at.isoformat()}",
                student=student, expires_at=session.starts_at)
            queued += message is not None
    return {"reminders": queued}


# ---------------------------------------------------------------- 5 and 6: class cancelled / rescheduled

def class_cancelled(session: ClassSession, change: SessionChange) -> None:
    if session.approval_status == "Pending":
        return  # its students were never told about the class
    next_step = change.next_action or REPLACEMENT_NEXT_STEP
    for student, batch in _class_students(session):
        whatsapp.enqueue(
            templates.CLASS_CANCELLED,
            {"student": student.full_name, "branch": batch.branch.branch_name, "class": session.title, "course": batch.course.title,
             "planned_start": when(change.old_starts_at), "reason": change.reason, "next_step": next_step},
            dedupe_key=f"class-cancelled:{session.session_id}:{student.student_id}", student=student)


def class_rescheduled(session: ClassSession, change: SessionChange) -> None:
    if session.approval_status == "Pending" or change.new_starts_at is None or change.new_starts_at == change.old_starts_at:
        return  # only a change of time is worth a message; the app shows the other details
    for student, batch in _class_students(session):
        whatsapp.enqueue(
            templates.CLASS_RESCHEDULED,
            {"student": student.full_name, "branch": batch.branch.branch_name, "class": session.title, "course": batch.course.title,
             "old_start": when(change.old_starts_at), "new_start": when(change.new_starts_at), "mode": _mode(session, batch)},
            dedupe_key=f"class-rescheduled:{session.session_id}:{student.student_id}:{change.new_starts_at.isoformat()}", student=student)


# ---------------------------------------------------------------- 7: result published

def result_published(result: Result, title: str) -> None:
    student = db.session.get(Student, result.student_id)
    batch = result.batch
    whatsapp.enqueue(
        templates.RESULT_PUBLISHED,
        {"student": student.full_name, "branch": batch.branch.branch_name, "assessment": title, "course": batch.course.title},
        dedupe_key=f"result-published:{result.result_id}:{int(result.published_at.timestamp())}", student=student)


# ---------------------------------------------------------------- 8: certificate issued

def certificate_issued(certificate: Certificate) -> None:
    student = certificate.student
    whatsapp.enqueue(
        templates.CERTIFICATE_ISSUED,
        {"student": student.full_name, "branch": certificate.branch.branch_name, "certificate_type": certificate.certificate_type,
         "course": certificate.course.title, "number": certificate.certificate_number},
        dedupe_key=f"certificate-issued:{certificate.certificate_id}:{certificate.version}", student=student)


# ---------------------------------------------------------------- 9: batch change needs agreement

def batch_change_agreement(change: MaterialChange, student: Student) -> None:
    batch = change.batch
    whatsapp.enqueue(
        templates.BATCH_CHANGE_AGREEMENT,
        {"student": student.full_name, "branch": batch.branch.branch_name, "course": batch.course.title, "now": change.current_plan,
         "proposed": change.proposed_plan, "reason": change.reason, "reply_by": _day(change.reply_by or _now() + timedelta(days=BATCH_CHANGE_REPLY_DAYS))},
        dedupe_key=f"batch-change:{change.change_id}:{student.student_id}", student=student)


# ---------------------------------------------------------------- 1-3: sign-in messages (UX phase U7)

RESET_CODE_MINUTES = 10


def password_reset_code(user: User, code: str, code_id: int) -> WhatsappMessage | None:
    now = _now()
    return whatsapp.enqueue(
        templates.PASSWORD_RESET_CODE, {"code": code}, dedupe_key=f"pwd-reset:{user.user_id}:{code_id}",
        student=db.session.get(Student, user.student_id) if user.student_id else None, user=user, occurred_at=now,
        expires_at=now + timedelta(minutes=RESET_CODE_MINUTES))


def student_activation_link(student: Student, token: str, activation: StudentActivation) -> WhatsappMessage | None:
    return whatsapp.enqueue(
        templates.STUDENT_ACTIVATION_LINK,
        {"student": student.full_name, "branch": student.service_branch.branch_name, "student_code": student.student_code,
         "expires": stamp(activation.expires_at), "token": token},
        dedupe_key=f"activation-link:{activation.activation_id}", student=student, expires_at=activation.expires_at)


def staff_invite(user: User, token: str, invite: StaffInvite, role_name: str, branch_name: str) -> WhatsappMessage | None:
    return whatsapp.enqueue(
        templates.STAFF_ACCOUNT_INVITE,
        {"name": user.full_name, "role": role_name, "branch": branch_name, "expires": stamp(invite.expires_at), "token": token},
        dedupe_key=f"staff-invite:{invite.invite_id}", user=user, expires_at=invite.expires_at)

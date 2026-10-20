"""The emails the LMS sends, built from the records that changed. Each function is called from the service that made the change,
in the same transaction, and only queues a message (services/emails.py). They sit beside the WhatsApp messages of the same events."""
from datetime import datetime, timedelta, timezone

from config.database import db
from models import Batch, Certificate, ClassSession, EmailOutbox, Result, SessionChange, StaffInvite, Student, StudentActivation, User
from models.delivery_ops import MaterialChange
from repositories import class_sessions as sessions_repo
from repositories import whatsapp as whatsapp_repo
from services import emails
from services import email_templates as templates
from services.whatsapp_messages import (
    BATCH_CHANGE_REPLY_DAYS, JOIN_OPENS, REMINDER_LEAD, REPLACEMENT_NEXT_STEP, _class_students, _day, stamp, when,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def student_activation_link(student: Student, token: str, activation: StudentActivation) -> EmailOutbox | None:
    return emails.enqueue(
        templates.STUDENT_ACTIVATION_LINK,
        {"student": student.full_name, "branch": student.service_branch.branch_name, "student_code": student.student_code,
         "link": emails.lms_link("/activate", token=token), "expires": stamp(activation.expires_at)},
        dedupe_key=f"activation-link:{activation.activation_id}", student=student, branch_id=student.service_branch_id,
        expires_at=activation.expires_at)


def staff_invite(user: User, token: str, invite: StaffInvite, role_name: str, branch_name: str, branch_id: int | None = None) -> EmailOutbox | None:
    return emails.enqueue(
        templates.STAFF_ACCOUNT_INVITE,
        {"name": user.full_name, "role": role_name, "branch": branch_name, "link": emails.lms_link("/activate", token=token),
         "expires": stamp(invite.expires_at)},
        dedupe_key=f"staff-invite:{invite.invite_id}", user=user, branch_id=branch_id, expires_at=invite.expires_at)


def _mode(session: ClassSession, batch: Batch) -> str:
    if session.mode == "Classroom":
        return ", ".join(part for part in ("Classroom", session.room, batch.branch.branch_name) if part)
    return session.mode


def class_reminders() -> dict:
    """Job `class-reminders`, email side: remind each student of every confirmed class that starts within about two hours. The
    dedupe key holds the start time, so a moved class is reminded again for its new time and never twice for the same time."""
    now = _now()
    queued = 0
    for session in whatsapp_repo.sessions_starting_between(now + JOIN_OPENS, now + REMINDER_LEAD):
        for batch_id in sessions_repo.session_batch_ids(session.session_id):
            batch = db.session.get(Batch, batch_id)
            for student in whatsapp_repo.batch_roster(batch_id):
                message = emails.enqueue(
                    templates.CLASS_REMINDER,
                    {"student": student.full_name, "branch": batch.branch.branch_name, "class_title": session.title,
                     "course": batch.course.title, "start": when(session.starts_at), "mode": _mode(session, batch)},
                    dedupe_key=f"class-reminder:{session.session_id}:{student.student_id}:{session.starts_at.isoformat()}",
                    student=student, branch_id=batch.branch_id, expires_at=session.starts_at)
                queued += message is not None
    return {"emails": queued}


# ---------------------------------------------------------------- class cancelled / rescheduled

def class_cancelled(session: ClassSession, change: SessionChange) -> None:
    if session.approval_status == "Pending":
        return  # its students were never told about the class
    next_step = change.next_action or REPLACEMENT_NEXT_STEP
    for student, batch in _class_students(session):
        emails.enqueue(
            templates.CLASS_CANCELLED,
            {"student": student.full_name, "branch": batch.branch.branch_name, "class_title": session.title, "course": batch.course.title,
             "planned_start": when(change.old_starts_at), "reason": change.reason, "next_step": next_step},
            dedupe_key=f"class-cancelled:{session.session_id}:{student.student_id}", student=student, branch_id=batch.branch_id)


def class_rescheduled(session: ClassSession, change: SessionChange) -> None:
    if session.approval_status == "Pending" or change.new_starts_at is None or change.new_starts_at == change.old_starts_at:
        return  # only a change of time is worth a message; the app shows the other details
    for student, batch in _class_students(session):
        emails.enqueue(
            templates.CLASS_RESCHEDULED,
            {"student": student.full_name, "branch": batch.branch.branch_name, "class_title": session.title, "course": batch.course.title,
             "old_start": when(change.old_starts_at), "new_start": when(change.new_starts_at), "mode": _mode(session, batch)},
            dedupe_key=f"class-rescheduled:{session.session_id}:{student.student_id}:{change.new_starts_at.isoformat()}", student=student,
            branch_id=batch.branch_id)


# ---------------------------------------------------------------- result published, certificate issued, batch change

def result_published(result: Result, title: str) -> None:
    student = db.session.get(Student, result.student_id)
    batch = result.batch
    emails.enqueue(
        templates.RESULT_PUBLISHED,
        {"student": student.full_name, "branch": batch.branch.branch_name, "assessment": title, "course": batch.course.title},
        dedupe_key=f"result-published:{result.result_id}:{int(result.published_at.timestamp())}", student=student, branch_id=batch.branch_id)


def certificate_issued(certificate: Certificate) -> None:
    student = certificate.student
    link = emails.lms_link(f"/verify/{certificate.certificate_number}")
    emails.enqueue(
        templates.CERTIFICATE_ISSUED,
        {"student": student.full_name, "branch": certificate.branch.branch_name, "certificate_type": certificate.certificate_type,
         "course": certificate.course.title, "number": certificate.certificate_number,
         "verify_line": f"\n\nAnyone can check that it is genuine here:\n{link}" if link else ""},
        dedupe_key=f"certificate-issued:{certificate.certificate_id}:{certificate.version}", student=student, branch_id=certificate.branch_id)


def batch_change_agreement(change: MaterialChange, student: Student) -> None:
    batch = change.batch
    emails.enqueue(
        templates.BATCH_CHANGE_AGREEMENT,
        {"student": student.full_name, "branch": batch.branch.branch_name, "course": batch.course.title, "now": change.current_plan,
         "proposed": change.proposed_plan, "reason": change.reason, "reply_by": _day(change.reply_by or _now() + timedelta(days=BATCH_CHANGE_REPLY_DAYS))},
        dedupe_key=f"batch-change:{change.change_id}:{student.student_id}", student=student, branch_id=batch.branch_id)

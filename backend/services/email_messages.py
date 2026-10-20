"""The emails the LMS sends, built from the records that changed. Each function is called from the service that made the change,
in the same transaction, and only queues a message (services/emails.py). They sit beside the WhatsApp messages of the same events."""
from datetime import datetime, timedelta, timezone

from config.database import db
from models import Batch, ClassSession, EmailOutbox, StaffInvite, Student, StudentActivation, User
from repositories import class_sessions as sessions_repo
from repositories import whatsapp as whatsapp_repo
from services import emails
from services import email_templates as templates
from services.whatsapp_messages import JOIN_OPENS, REMINDER_LEAD, stamp, when


def _now() -> datetime:
    return datetime.now(timezone.utc)


def student_activation_link(student: Student, token: str, activation: StudentActivation) -> EmailOutbox | None:
    return emails.enqueue(
        templates.STUDENT_ACTIVATION_LINK,
        {"student": student.full_name, "branch": student.service_branch.branch_name, "student_code": student.student_code,
         "link": emails.activation_link("/activate", token=token), "expires": stamp(activation.expires_at)},
        dedupe_key=f"activation-link:{activation.activation_id}", student=student, branch_id=student.service_branch_id,
        expires_at=activation.expires_at)


def staff_invite(user: User, token: str, invite: StaffInvite, role_name: str, branch_name: str, branch_id: int | None = None) -> EmailOutbox | None:
    return emails.enqueue(
        templates.STAFF_ACCOUNT_INVITE,
        {"name": user.full_name, "role": role_name, "branch": branch_name, "link": emails.activation_link("/activate", token=token),
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

"""Email through Gmail (docs/GOOGLE_WORKSPACE.md §5.3).

Same shape as WhatsApp (services/whatsapp.py): a message is written to `email_outbox` in the same transaction as the change it
reports (`enqueue`), and the `email-send` job sends it after the commit (`send_pending`). The switch is the `EMAIL` entry of the
integrations register plus a configured service-account key. A message that cannot or should not go out is kept as Skipped with
the reason, so nothing is silently lost and nothing floods out when the switch is turned on.

  - one message per dedupe key, however often an event is processed;
  - a message past its expiry (a link that has lapsed, a class that has begun) is skipped, not sent;
  - no database transaction is held open during the Gmail call;
  - a timeout or 5xx is retried after 5 min, doubling to 6 h, five tries in all; any other refusal fails at once.
"""
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from flask import current_app

from config.database import db
from models import EmailOutbox, Student, User
from repositories import email as email_repo
from repositories import google as google_repo
from repositories import notifications as notifications_repo
from repositories import users as users_repo
from services import integrations
from services.email_templates import TEMPLATES, Template
from services.google import client, gmail
from services.google.client import GoogleError
from services import whatsapp as _whatsapp  # noqa: F401  (loaded first: whatsapp and notification_centre import each other)
from services.notification_centre import DEFAULT_EXTERNAL_ON

logger = logging.getLogger(__name__)

EMAIL_INTEGRATION = "EMAIL"
CHANNEL = "Email"
MAX_ATTEMPTS = 5
BACKOFF = timedelta(minutes=5)
BACKOFF_CAP = timedelta(hours=6)
IN_FLIGHT_LIMIT = timedelta(minutes=15)
DEFAULT_LIFETIME = timedelta(hours=48)
BATCH_SIZE = 50


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_enabled() -> bool:
    return client.is_configured() and integrations.is_verified(EMAIL_INTEGRATION)


def status() -> dict:
    """For Setup & health: whether email goes out, and how many messages are in each state."""
    return {"state": "On" if is_enabled() else "Switched off", "counts": email_repo.counts()}


def lms_link(path: str, **query: str) -> str | None:
    """A link into the LMS (`/activate?token=…`), or None when the LMS address is not set."""
    base = current_app.config.get("PUBLIC_BASE_URL")
    if not base:
        return None
    return f"{base.rstrip('/')}{path}" + (f"?{urlencode(query)}" if query else "")


# ---------------------------------------------------------------- queueing

def _switched_off_by_person(user: User | None, template: Template) -> bool:
    if template.essential:
        return False
    if user is None:
        return template.group not in DEFAULT_EXTERNAL_ON
    stored = notifications_repo.preferences(user.user_id)
    return not stored.get((template.group, CHANNEL), template.group in DEFAULT_EXTERNAL_ON)


def enqueue(template: Template, values: dict, *, dedupe_key: str, student: Student | None = None, user: User | None = None,
            branch_id: int | None = None, occurred_at: datetime | None = None, expires_at: datetime | None = None) -> EmailOutbox | None:
    """Record one message in the caller's transaction. Returns None for a repeat of the same event."""
    now = _now()
    occurred_at = occurred_at or now
    expires_at = expires_at or occurred_at + DEFAULT_LIFETIME
    if student is not None:
        user = user or users_repo.get_by_student_id(student.student_id)
        address = student.email or (user.email if user else None)
    else:
        address = user.email if user else None
    address = address.strip() if address else None

    note, subject, body = None, "", ""
    if not is_enabled():
        note = "Email is switched off"
    else:
        try:
            subject, body = template.render(values)
        except ValueError as error:
            note = str(error)
    if note is None and not address:
        note = "No email address on file"
    elif note is None and _switched_off_by_person(user, template):
        note = "The person switched email off for this kind of message"
    elif note is None and expires_at <= now:
        note = "Too old to send"
    if note is not None and template.essential:
        subject, body = "", ""  # nothing will be sent, so keep no link

    return email_repo.insert_once({
        "template": template.name, "recipient_user_id": user.user_id if user else None, "branch_id": branch_id, "to_email": address,
        "subject": subject, "body": body, "has_secret": template.essential, "dedupe_key": dedupe_key, "occurred_at": occurred_at,
        "expires_at": expires_at, "status": "Skipped" if note else "Queued", "status_note": note})


def outcome(message: EmailOutbox | None) -> dict:
    """What a screen tells the person who triggered an email: on its way, or why nothing will go out."""
    if message is None:
        return {"state": "Skipped", "note": "This email was already queued"}
    return {"state": message.status, "note": message.status_note}


# ---------------------------------------------------------------- sending

def _finish(message: EmailOutbox, status_value: str, note: str | None = None, provider_id: str | None = None) -> None:
    message.status, message.status_note, message.attempt_started_at = status_value, note, None
    if message.has_secret:
        message.body = ""  # a sign-in link is kept only until the message is done
    if provider_id:
        message.provider_message_id = provider_id
    if status_value == "Sent":
        message.sent_at = _now()


def _sender(message: EmailOutbox) -> str | None:
    return google_repo.gmail_sender(message.branch_id) or current_app.config.get("GOOGLE_DELEGATED_ADMIN")


def send_pending(*, sender=gmail.send, limit: int = BATCH_SIZE) -> dict:
    """The `email-send` job: send queued messages through Gmail. Commits after each message, so no transaction stays open during a call."""
    if not is_enabled():
        return {"state": "Switched off", "sent": 0}
    now = _now()
    for message in email_repo.due(now, now - IN_FLIGHT_LIMIT, limit):
        if message.expires_at <= now:
            _finish(message, "Skipped", "Too old to send")
    db.session.commit()

    sent = failed = retried = 0
    for message in email_repo.due(_now(), _now() - IN_FLIGHT_LIMIT, limit):
        message.attempts += 1
        message.attempt_started_at = _now()
        db.session.commit()  # claimed
        from_address = _sender(message)
        try:
            if not from_address:
                raise GoogleError("No mailbox to send from")
            provider_id = sender(from_address, message.to_email, message.subject, message.body)
        except GoogleError as error:
            if error.retryable and message.attempts < MAX_ATTEMPTS:
                message.attempt_started_at = None
                message.next_attempt_at = _now() + min(BACKOFF * 2 ** (message.attempts - 1), BACKOFF_CAP)
                message.status_note = str(error)[:500]
                retried += 1
            else:
                _finish(message, "Failed", str(error)[:500])
                failed += 1
        else:
            _finish(message, "Sent", provider_id=provider_id)
            sent += 1
        db.session.commit()
    return {"state": "On", "sent": sent, "retry": retried, "failed": failed}

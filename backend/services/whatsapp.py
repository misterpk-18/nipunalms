"""WhatsApp through the CRM (UX phase U6).

The LMS never talks to Pinbot. A message is written to `whatsapp_outbox` in the same transaction as the change it reports
(`enqueue`), and the `whatsapp-send` job posts it to the CRM's `POST {CRM_BASE_URL}/lms/whatsapp` after the commit
(`send_pending`). The CRM applies its own switch, test-number list, consent and backoff, and sends on the one company number.

Rules (from the CRM's note, nipuna crm-docs/CRM_WHATSAPP_CONNECTION.md §3):
  - one message per dedupe key, however often an event is processed;
  - a message about something older than `whatsapp_max_age_hours` (or a class that has begun) is skipped, not sent;
  - a database transaction is never held open during the HTTP call;
  - nothing is resent after a timeout: delivery is unknown, so the row is Failed with "check before resending";
  - the code ships switched off: `app_settings.whatsapp_enabled` is false, and only templates named in
    `whatsapp_approved_templates` are sent.
"""
import json
import logging
import socket
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import current_app

from config.database import db
from models import Student, User, WhatsappMessage
from repositories import notifications as notifications_repo
from repositories import settings as settings_repo
from repositories import users as users_repo
from repositories import whatsapp as whatsapp_repo
from services.notification_centre import DEFAULT_EXTERNAL_ON
from services.validation import normalise_phone
from services.whatsapp_templates import TEMPLATES, Template, build

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 60  # doubling to 30 minutes, like the CRM's own sender
BACKOFF_CAP_SECONDS = 30 * 60
IN_FLIGHT_LIMIT = timedelta(minutes=15)
BATCH_SIZE = 50
PATH = "/lms/whatsapp"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- the switch

def is_enabled() -> bool:
    return bool(settings_repo.get("whatsapp_enabled", False))


def approved_templates() -> set[str]:
    return set(settings_repo.get("whatsapp_approved_templates", []) or [])


def endpoint_configured() -> bool:
    return bool(current_app.config.get("CRM_BASE_URL") and current_app.config.get("CRM_SERVICE_KEY"))


def is_live() -> bool:
    """WhatsApp is a real channel for people: the switch is on, the CRM endpoint is set and a template is approved."""
    return is_enabled() and endpoint_configured() and bool(approved_templates() & set(TEMPLATES))


def status() -> dict:
    """For Setup & health: why messages are or are not going out, and how many are in each state."""
    if not is_enabled():
        state = "Switched off"
    elif not endpoint_configured():
        state = "CRM endpoint not available"
    elif not approved_templates() & set(TEMPLATES):
        state = "No template approved yet"
    else:
        state = "On"
    return {"state": state, "counts": whatsapp_repo.counts(), "approved_templates": sorted(approved_templates() & set(TEMPLATES))}


# ---------------------------------------------------------------- queueing

def _person(student: Student | None, user: User | None) -> tuple[User | None, str | None, str | None]:
    """The login account (for preferences), the LMS id and the WhatsApp number in digits."""
    if student is not None:
        user = user or users_repo.get_by_student_id(student.student_id)
        raw = student.mobile
        lms_id = student.lms_user_id
    else:
        raw = user.phone if user else None
        lms_id = None
    phone = normalise_phone(raw) if raw else None
    return user, lms_id, phone.lstrip("+") if phone else None


def _switched_off_by_person(user: User | None, template: Template) -> bool:
    if user is None:
        return template.group not in DEFAULT_EXTERNAL_ON
    stored = notifications_repo.preferences(user.user_id)
    return not stored.get((template.group, "WhatsApp"), template.group in DEFAULT_EXTERNAL_ON)


def enqueue(template: Template, values: dict, *, dedupe_key: str, student: Student | None = None, user: User | None = None,
            occurred_at: datetime | None = None, expires_at: datetime | None = None) -> WhatsappMessage | None:
    """Record one message in the caller's transaction. Returns None for a repeat of the same event. A message that cannot or
    should not go out is kept as Skipped with the reason, so nothing is silently lost and nothing floods out when the switch is turned on."""
    now = _now()
    occurred_at = occurred_at or now
    expires_at = expires_at or occurred_at + timedelta(hours=settings_repo.get_int("whatsapp_max_age_hours", 48))
    person, lms_user_id, number = _person(student, user)

    note = None
    params: list[str] = []
    button: list[str] = []
    try:
        params, button = build(template, values)
    except ValueError as error:
        note = str(error)
    if note is None and not is_enabled():
        note = "WhatsApp is switched off"
    elif note is None and template.name not in approved_templates():
        note = "This template is not approved yet"
    elif note is None and number is None:
        note = "No WhatsApp number on file"
    elif note is None and _switched_off_by_person(person, template):
        note = "The person switched WhatsApp off for this kind of message"
    elif note is None and expires_at <= now:
        note = "Too old to send"

    return whatsapp_repo.insert_once({
        "template_name": template.name, "language": template.language, "recipient_user_id": person.user_id if person else None,
        "lms_user_id": lms_user_id, "to_number": number, "params": params, "button_params": button, "dedupe_key": dedupe_key,
        "occurred_at": occurred_at, "expires_at": expires_at, "status": "Skipped" if note else "Queued", "status_note": note})


# ---------------------------------------------------------------- sending

class NoAnswer(Exception):
    """The request may have reached the CRM, so delivery is unknown."""


def post(url: str, payload: dict, key: str, timeout: float) -> tuple[int, dict | None]:
    """POST JSON; returns (status, parsed body or None). Raises NoAnswer on a timeout and ConnectionError when the request
    certainly never reached the CRM."""
    request = urllib.request.Request(url, data=json.dumps(payload, default=str).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json", "X-Service-Key": key})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - the URL is the configured CRM base
            return response.status, _json(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _json(error.read())
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise NoAnswer(str(error.reason)) from error
        raise ConnectionError(str(error.reason)) from error
    except (TimeoutError, socket.timeout) as error:
        raise NoAnswer(str(error)) from error


def _json(raw: bytes) -> dict | None:
    try:
        body = json.loads(raw or b"null")
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _payload(message: WhatsappMessage) -> dict:
    payload = {"template": message.template_name, "language": message.language, "params": message.params,
               "button_params": message.button_params, "dedupe_key": message.dedupe_key, "occurred_at": message.occurred_at.isoformat()}
    if message.to_number:
        payload["to"] = message.to_number
    if message.lms_user_id:
        payload["lms_user_id"] = message.lms_user_id
    return payload


def _finish(message: WhatsappMessage, status: str, note: str | None = None, provider_id: str | None = None) -> None:
    message.status, message.status_note, message.attempt_started_at = status, note, None
    if provider_id:
        message.provider_message_id = provider_id
    if status == "Sent":
        message.sent_at = _now()


def _retry_later(message: WhatsappMessage, note: str) -> None:
    message.attempt_started_at = None
    if message.attempts >= MAX_ATTEMPTS:
        _finish(message, "Failed", f"{note} (gave up after {MAX_ATTEMPTS} tries)")
        return
    delay = min(BACKOFF_SECONDS * 2 ** (message.attempts - 1), BACKOFF_CAP_SECONDS)
    message.next_attempt_at, message.status_note = _now() + timedelta(seconds=delay), note


def _record_answer(message: WhatsappMessage, status_code: int, body: dict | None) -> bool:
    """Apply the CRM's answer. Returns False when the whole run should stop (the key was refused)."""
    data = (body or {}).get("data") or {}
    if status_code in (401, 403):
        message.attempt_started_at, message.attempts = None, max(message.attempts - 1, 0)
        message.status_note = "The CRM refused the service key"
        return False
    if status_code == 409:  # the CRM already has this dedupe key
        _finish(message, "Sent", "The CRM already had this message", data.get("provider_message_id"))
    elif status_code == 429 or status_code >= 500:
        _retry_later(message, f"The CRM was busy or failed ({status_code})")
    elif 200 <= status_code < 300:
        state = data.get("status")
        if state == "Skipped":
            _finish(message, "Skipped", f"The CRM skipped it: {data.get('reason') or 'no reason given'}")
        elif state in ("Sent", "Queued") or data.get("provider_message_id"):
            _finish(message, "Sent", None, data.get("provider_message_id"))
        else:  # accepted but no confirmation: it may have been sent
            _finish(message, "Failed", "The CRM gave no confirmation; check before resending")
    else:
        error = (body or {}).get("error") or {}
        _finish(message, "Failed", f"The CRM refused it ({status_code}): {error.get('message') or 'no detail'}")
    return True


def send_pending(*, poster=post, limit: int = BATCH_SIZE) -> dict:
    """The `whatsapp-send` job: post queued messages to the CRM. Commits after each message, so no transaction stays open
    during a call and a crash never loses an answer."""
    current = status()
    if current["state"] != "On":
        return {"state": current["state"], "sent": 0}
    now = _now()
    for message in whatsapp_repo.stuck_in_flight(now - IN_FLIGHT_LIMIT):
        _finish(message, "Failed", "No answer recorded; check before resending")
    for message in whatsapp_repo.due(now, limit):
        if message.expires_at <= now:
            _finish(message, "Skipped", "Too old to send")
    db.session.commit()

    url = current_app.config["CRM_BASE_URL"].rstrip("/") + PATH
    key, timeout = current_app.config["CRM_SERVICE_KEY"], current_app.config["CRM_REQUEST_TIMEOUT"]
    sent = failed = 0
    for message in whatsapp_repo.due(_now(), limit):
        message.attempts += 1
        message.attempt_started_at = _now()
        db.session.commit()  # claimed: if we die from here on, the row is never auto-resent
        try:
            status_code, body = poster(url, _payload(message), key, timeout)
            keep_going = _record_answer(message, status_code, body)
        except NoAnswer:
            _finish(message, "Failed", "No answer from the CRM; check before resending")
            keep_going = True
        except ConnectionError as error:
            _retry_later(message, f"Could not reach the CRM ({error})")
            keep_going = True
        db.session.commit()
        sent += message.status == "Sent"
        failed += message.status == "Failed"
        if not keep_going:
            return {"state": "The CRM refused the service key", "sent": sent, "failed": failed}
    return {"state": "On", "sent": sent, "failed": failed}

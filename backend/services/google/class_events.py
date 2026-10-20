"""A class's Google Calendar event and its Meet link (docs/GOOGLE_WORKSPACE.md §5.1).

A Live Online or Hybrid class gets one event in its branch's calendar mailbox, with a Meet conference. When Google returns the
link, the class moves to Meet "Linked" in the same log (`meet_events`) a hand-entered link uses. A moved class patches the same
event; a cancelled class, or one that became a classroom class, deletes it. Nothing here runs inside a user's request: the
request calls `enqueue_*`, and the `google-sync` job calls `handle_*` after the commit.

The switch is the integrations register: with `GOOGLE_MEET` not Verified, or no service-account key, `enqueue_*` does nothing and
Meet links stay a manual entry, exactly as before.
"""
import logging
from urllib.parse import quote

from flask import current_app

from config.database import db
from models import ClassSession
from repositories import google as google_repo
from services import audit, delivery_notices, integrations, meet
from services.google import client
from services.google.client import GoogleError

logger = logging.getLogger(__name__)

MEET_INTEGRATION = "GOOGLE_MEET"
KIND_UPSERT = "CALENDAR_UPSERT"
KIND_CANCEL = "CALENDAR_CANCEL"
ENTITY = "class_session"
EVENTS = "https://www.googleapis.com/calendar/v3/calendars/{mailbox}/events"
EVENT_PARAMS = {"conferenceDataVersion": 1, "sendUpdates": "none"}


def is_enabled() -> bool:
    return client.is_configured() and integrations.is_verified(MEET_INTEGRATION)


def _wants_event(session: ClassSession) -> bool:
    return session.mode != "Classroom" and session.state not in ("Cancelled", "Delivered") and session.approval_status != "Pending"


# ---------------------------------------------------------------- called from a request: queue the work

def enqueue_upsert(session: ClassSession) -> None:
    """A class needs its event created or brought up to date (new, approved, moved, became online, or Meet retried)."""
    if is_enabled() and _wants_event(session):
        google_repo.enqueue(KIND_UPSERT, ENTITY, session.session_id)


def enqueue_cancel(session: ClassSession) -> None:
    """A class that has an event no longer needs it (cancelled, or became a classroom class)."""
    if is_enabled() and session.calendar_event_id:
        google_repo.enqueue(KIND_CANCEL, ENTITY, session.session_id)


# ---------------------------------------------------------------- called from the google-sync job

def _event_id(session: ClassSession) -> str:
    """Google accepts our own event id (base32hex: 0-9, a-v), so a retry after a lost reply finds the same event."""
    return f"lms{session.session_id:010d}"


def _body(session: ClassSession) -> dict:
    batch = session.batch
    lines = [f"Batch {batch.batch_code}", f"Trainer: {session.trainer.full_name}"]
    base = current_app.config.get("PUBLIC_BASE_URL")
    if base:
        lines.append(f"{base.rstrip('/')}/sessions/{session.session_id}")
    body = {
        "summary": f"{batch.batch_code} · {session.title}",
        "description": "\n".join(lines),
        "start": {"dateTime": session.starts_at.isoformat()},
        "end": {"dateTime": session.ends_at.isoformat()},
        "status": "confirmed",
        "guestsCanModify": False,
        "guestsCanInviteOthers": False,
        "reminders": {"useDefault": True},
    }
    if session.room and session.mode == "Hybrid":
        body["location"] = session.room
    if session.trainer.email:
        body["attendees"] = [{"email": session.trainer.email}]
    return body


def _conference(session: ClassSession) -> dict:
    return {"createRequest": {"requestId": _event_id(session), "conferenceSolutionKey": {"type": "hangoutsMeet"}}}


def _call(method: str, mailbox: str, event_id: str | None, *, body: dict | None = None, params: dict | None = None) -> dict:
    url = EVENTS.format(mailbox=quote(mailbox, safe="@")) + (f"/{event_id}" if event_id else "")
    return client.request(method, url, subject=mailbox, scopes=[client.CALENDAR_SCOPE], body=body, params=params)


def handle_upsert(session_id: int) -> str:
    session = db.session.get(ClassSession, session_id)
    if session is None:
        return "class no longer exists"
    if session.state == "Cancelled" or session.mode == "Classroom":
        return _delete_event(session)
    if session.state == "Delivered":
        return "class already delivered"
    if session.approval_status == "Pending":
        return "waiting for approval"
    if session.meet_status == "Linked" and not session.calendar_event_id:
        return "a link was entered by hand; kept"
    mailbox = google_repo.branch_mailbox(session.batch.branch_id)
    if not mailbox:
        raise GoogleError(f"Branch {session.batch.branch_id} has no calendar mailbox")
    body = _body(session)
    if not session.meet_link:
        body["conferenceData"] = _conference(session)

    event = _write_event(session, mailbox, body)
    session.calendar_event_id = event["id"]  # kept even if the link is not ready yet, so the retry patches this event
    link = event.get("hangoutLink")
    if not link:
        db.session.flush()
        raise GoogleError("Google has not returned the Meet link yet", retryable=True)
    if session.meet_link != link or session.meet_status != "Linked":
        _apply_link(session, link, event["id"])
    return f"event {event['id']} {'updated' if session.meet_link == link else 'created'}"


def _write_event(session: ClassSession, mailbox: str, body: dict) -> dict:
    """Patch the class's event when it has one; else insert it under our own id, and patch it if that id already exists."""
    if session.calendar_event_id:
        try:
            return _call("PATCH", mailbox, session.calendar_event_id, body=body, params=EVENT_PARAMS)
        except GoogleError as exc:
            if exc.status not in (404, 410):
                raise
            session.calendar_event_id = None  # someone deleted it in Calendar: make it again below
    try:
        return _call("POST", mailbox, None, body={**body, "id": _event_id(session)}, params=EVENT_PARAMS)
    except GoogleError as exc:
        if exc.status != 409:
            raise
        return _call("PATCH", mailbox, _event_id(session), body=body, params=EVENT_PARAMS)


def _apply_link(session: ClassSession, link: str, event_id: str) -> None:
    session.meet_link, session.meet_status, session.calendar_event_id = link, "Linked", event_id
    db.session.flush()
    meet.record(session, "Link associated", "Created from Google Calendar; " + meet.integration_note())
    audit.record("MEET_LINK_SET", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"meet_link": link, "calendar_event_id": event_id, "source": "google"}, actor_user_id=None)


def handle_cancel(session_id: int) -> str:
    session = db.session.get(ClassSession, session_id)
    if session is None:
        return "class no longer exists"
    if session.state != "Cancelled" and session.mode != "Classroom":
        return "class is on again; event kept"
    return _delete_event(session)


def _delete_event(session: ClassSession) -> str:
    if not session.calendar_event_id:
        return "no event to remove"
    mailbox = google_repo.branch_mailbox(session.batch.branch_id)
    try:
        _call("DELETE", mailbox, session.calendar_event_id)
    except GoogleError as exc:
        if exc.status not in (404, 410):
            raise
    event_id, session.calendar_event_id = session.calendar_event_id, None
    db.session.flush()
    meet.record(session, "Link removed", f"Google Calendar event {event_id} deleted")
    return f"event {event_id} removed"


def on_dead(job_kind: str, session_id: int, error: str) -> None:
    """The retries are used up: show the class's Meet as Failed (a Branch Manager task), as a failed hand association does."""
    session = db.session.get(ClassSession, session_id)
    if session is None or job_kind != KIND_UPSERT or not _wants_event(session):
        return
    if session.meet_status != "Linked":
        session.meet_link, session.meet_status = None, "Unavailable"
    db.session.flush()
    event = meet.record(session, "Association failed", f"Google Calendar: {error}")
    db.session.flush()
    delivery_notices.notify_branch_managers(
        session.batch.branch_id, title=f"Meet association failed: {session.title}", category="Session", action_required=True,
        body=f"Google Calendar could not be updated. {error}", event_key=f"meet-failed-{event.event_id}", link="/branch/schedule")

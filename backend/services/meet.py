"""Google Meet association state for class sessions. The LMS never calls Google: it records what is known.

A Live Online / Hybrid session starts as 'Pending Verification' (organizer and link not confirmed). A link entered by an
authorised person moves it to 'Linked' (shown as Associated); a failed attempt is 'Unavailable' (shown as Failed) and can be
retried. Classroom sessions need no Meet ('Not Required'). Every step is written to `meet_events`.
"""
from datetime import datetime, timedelta

from models import ClassSession, MeetEvent
from models.batches import MEET_STATUS_LABELS
from repositories import meet as meet_repo
from services.context import actor_id

JOIN_OPENS_BEFORE = timedelta(minutes=15)


def status_label(meet_status: str) -> str:
    return MEET_STATUS_LABELS[meet_status]


def initial_status(mode: str) -> str:
    return "Not Required" if mode == "Classroom" else "Pending Verification"


def organizer_email(session: ClassSession) -> str:
    """The branch mailbox that organizes the meeting (Module 16 §2): the student service branch's, whoever teaches."""
    return session.batch.branch.mailbox


def integration_note() -> str:
    """One line on the Google Meet register entry, shown next to the organizer."""
    integration = meet_repo.meet_integration()
    if integration is None:
        return "Google Meet is not in the integrations register"
    return f"Google Meet integration: {integration.configuration_status}, {integration.verification_status}"


def is_verified() -> bool:
    integration = meet_repo.meet_integration()
    return integration is not None and integration.verification_status == "Verified"


def join_state(session: ClassSession, now: datetime) -> dict:
    """Whether the Join button is enabled: Meet Associated and the class Live or about to start."""
    if session.mode == "Classroom":
        where = f" in {session.room}" if session.room else ""
        return {"enabled": False, "reason": f"Classroom session — attend in person{where}."}
    if session.state in ("Delivered", "Cancelled"):
        return {"enabled": False, "reason": f"The class is {session.state.lower()}."}
    if session.meet_status != "Linked":
        return {"enabled": False, "reason": f"Meet is {status_label(session.meet_status)} — the organizer link is not available yet."}
    if session.state == "Live" or session.starts_at - JOIN_OPENS_BEFORE <= now <= session.ends_at:
        return {"enabled": True, "reason": None}
    if now < session.starts_at:
        return {"enabled": False, "reason": "Joining opens 15 minutes before the class starts."}
    return {"enabled": False, "reason": "The class time has passed."}


def record(session: ClassSession, event_type: str, detail: str | None = None) -> MeetEvent:
    return meet_repo.add_event(session.session_id, event_type, session.meet_status, organizer_email=organizer_email(session),
                        meet_link=session.meet_link, detail=detail, actor_user_id=actor_id())

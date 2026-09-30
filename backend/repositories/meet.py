"""The Google Meet entry of the integrations register (read-only here) and the Meet association log."""
from sqlalchemy import select

from config.database import db
from models import Integration, MeetEvent

GOOGLE_MEET = "GOOGLE_MEET"


def meet_integration() -> Integration | None:
    return db.session.execute(select(Integration).where(Integration.integration_code == GOOGLE_MEET)).scalar_one_or_none()


def add_event(session_id: int, event_type: str, meet_status: str, *, organizer_email: str | None, meet_link: str | None,
              detail: str | None, actor_user_id: int | None) -> MeetEvent:
    event = MeetEvent(session_id=session_id, event_type=event_type, meet_status=meet_status, organizer_email=organizer_email,
                      meet_link=meet_link, detail=detail, actor_user_id=actor_user_id)
    db.session.add(event)
    return event

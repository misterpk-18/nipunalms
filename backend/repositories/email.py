"""Reads and writes of the email outbox."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from config.database import db
from models import EmailOutbox


def insert_once(values: dict) -> EmailOutbox | None:
    """Add the message unless one with this dedupe key exists; returns it, or None for a repeat."""
    outbox_id = db.session.execute(
        insert(EmailOutbox).values(**values).on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(EmailOutbox.outbox_id)
    ).scalar()
    return db.session.get(EmailOutbox, outbox_id) if outbox_id is not None else None


def due(now: datetime, in_flight_before: datetime, limit: int) -> list[EmailOutbox]:
    """Queued messages not waiting out a backoff, oldest first. A send that began before `in_flight_before` and never ended is due again."""
    stmt = (select(EmailOutbox).where(
        EmailOutbox.status == "Queued",
        (EmailOutbox.attempt_started_at.is_(None)) | (EmailOutbox.attempt_started_at < in_flight_before),
        (EmailOutbox.next_attempt_at.is_(None)) | (EmailOutbox.next_attempt_at <= now))
        .order_by(EmailOutbox.outbox_id).limit(limit))
    return list(db.session.execute(stmt).scalars())


def counts() -> dict[str, int]:
    return dict(db.session.execute(select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status)).all())

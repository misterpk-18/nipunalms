"""Reads and writes of the WhatsApp outbox, and the lookups the message builders need."""
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert

from config.database import db
from models import Batch, BatchAllocation, ClassSession, Enrolment, Student, WhatsappMessage


def insert_once(values: dict) -> WhatsappMessage | None:
    """Add the message unless one with this dedupe key exists; returns it, or None for a repeat."""
    outbox_id = db.session.execute(
        insert(WhatsappMessage).values(**values).on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(WhatsappMessage.outbox_id)
    ).scalar()
    return db.session.get(WhatsappMessage, outbox_id) if outbox_id is not None else None


def by_dedupe_key(dedupe_key: str) -> WhatsappMessage | None:
    return db.session.execute(select(WhatsappMessage).where(WhatsappMessage.dedupe_key == dedupe_key)).scalar_one_or_none()


def due(now: datetime, limit: int) -> list[WhatsappMessage]:
    """Queued messages not in flight and not waiting out a backoff, oldest first."""
    stmt = (select(WhatsappMessage).where(WhatsappMessage.status == "Queued", WhatsappMessage.attempt_started_at.is_(None),
                                          (WhatsappMessage.next_attempt_at.is_(None)) | (WhatsappMessage.next_attempt_at <= now))
            .order_by(WhatsappMessage.outbox_id).limit(limit))
    return list(db.session.execute(stmt).scalars())


def stuck_in_flight(before: datetime) -> list[WhatsappMessage]:
    """Posts that started before `before` and never recorded an answer: delivery is unknown."""
    return list(db.session.execute(select(WhatsappMessage).where(WhatsappMessage.status == "Queued",
                                                                 WhatsappMessage.attempt_started_at < before)).scalars())


def counts() -> dict[str, int]:
    return dict(db.session.execute(select(WhatsappMessage.status, func.count()).group_by(WhatsappMessage.status)).all())


def list_messages(status: str | None, limit: int) -> list[WhatsappMessage]:
    stmt: Select = select(WhatsappMessage).order_by(WhatsappMessage.outbox_id.desc()).limit(limit)
    if status:
        stmt = stmt.where(WhatsappMessage.status == status)
    return list(db.session.execute(stmt).scalars())


def batch_roster(batch_id: int) -> list[Student]:
    """Students holding an active seat in the batch."""
    stmt = (select(Student).join(Enrolment, Enrolment.student_id == Student.student_id)
            .join(BatchAllocation, BatchAllocation.enrolment_id == Enrolment.enrolment_id)
            .where(BatchAllocation.batch_id == batch_id, BatchAllocation.status == "Active").distinct())
    return list(db.session.execute(stmt).scalars().unique())


def sessions_starting_between(start: datetime, end: datetime) -> list[ClassSession]:
    """Confirmed, approved classes that begin in the window."""
    stmt = (select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.state.in_(("Scheduled", "Rescheduled")), ClassSession.confirmed_at.is_not(None),
                   ClassSession.approval_status != "Pending", ClassSession.starts_at > start, ClassSession.starts_at <= end)
            .order_by(ClassSession.starts_at))
    return list(db.session.execute(stmt).scalars().unique())

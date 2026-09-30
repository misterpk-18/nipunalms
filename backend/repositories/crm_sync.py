"""CRM sync monitor: inbox / outbox listings and counts (the intake queries live in repositories/crm.py)."""
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import CrmEvent, CrmOutbox


def events_stmt(filters: dict) -> Select:
    stmt = select(CrmEvent).order_by(CrmEvent.crm_event_id.desc())
    if filters.get("status"):
        stmt = stmt.where(CrmEvent.status == filters["status"])
    if filters.get("event_type"):
        stmt = stmt.where(CrmEvent.event_type == filters["event_type"])
    if filters.get("q"):
        stmt = stmt.where(CrmEvent.event_id.ilike(f"%{filters['q']}%"))
    if filters.get("received_from"):
        stmt = stmt.where(CrmEvent.received_at >= filters["received_from"])
    if filters.get("received_before"):
        stmt = stmt.where(CrmEvent.received_at < filters["received_before"])
    return stmt


def outbox_stmt(filters: dict) -> Select:
    stmt = select(CrmOutbox).order_by(CrmOutbox.outbox_id.desc())
    if filters.get("status"):
        stmt = stmt.where(CrmOutbox.status == filters["status"])
    if filters.get("event_type"):
        stmt = stmt.where(CrmOutbox.event_type == filters["event_type"])
    return stmt


def get_outbox(outbox_id: int) -> CrmOutbox | None:
    return db.session.get(CrmOutbox, outbox_id)


def event_counts() -> dict[str, int]:
    rows = db.session.execute(select(CrmEvent.status, func.count()).group_by(CrmEvent.status)).all()
    return {status: count for status, count in rows}


def outbox_counts() -> dict[str, int]:
    rows = db.session.execute(select(CrmOutbox.status, func.count()).group_by(CrmOutbox.status)).all()
    return {status: count for status, count in rows}


def event_types() -> list[str]:
    return list(db.session.execute(select(CrmEvent.event_type).distinct().order_by(CrmEvent.event_type)).scalars())


def outbox_event_types() -> list[str]:
    return list(db.session.execute(select(CrmOutbox.event_type).distinct().order_by(CrmOutbox.event_type)).scalars())


def last_received_at() -> datetime | None:
    return db.session.execute(select(func.max(CrmEvent.received_at))).scalar()


def oldest_pending_outbox_at() -> datetime | None:
    return db.session.execute(select(func.min(CrmOutbox.created_at)).where(CrmOutbox.status == "Pending")).scalar()


def last_delivered_at() -> datetime | None:
    return db.session.execute(select(func.max(CrmOutbox.delivered_at))).scalar()

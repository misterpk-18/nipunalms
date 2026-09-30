"""Ask Nipuna: the query log, daily usage and the class-session facts the assistant may use."""
from datetime import datetime

from sqlalchemy import Select, case, func, select

from config.database import db
from models import AiQuery, ClassSession


def get_query(ai_query_id: int) -> AiQuery | None:
    return db.session.get(AiQuery, ai_query_id)


def list_stmt(user_id: int) -> Select:
    return select(AiQuery).where(AiQuery.user_id == user_id).order_by(AiQuery.created_at.desc(), AiQuery.ai_query_id.desc())


def answered_since(user_id: int, since: datetime) -> int:
    """Successful answers since the given time. Refused and failed requests do not use up the allowance."""
    return db.session.execute(
        select(func.count()).select_from(AiQuery).where(AiQuery.user_id == user_id, AiQuery.status == "Answered", AiQuery.created_at >= since)
    ).scalar_one()


def upcoming_sessions(batch_ids: set[int], start: datetime, end: datetime, limit: int) -> list[ClassSession]:
    """Sessions still to happen (not cancelled) in the window, soonest first."""
    if not batch_ids:
        return []
    stmt = (
        select(ClassSession)
        .where(ClassSession.batch_id.in_(batch_ids), ClassSession.starts_at >= start, ClassSession.starts_at < end,
               ClassSession.state.in_(("Scheduled", "Live")))
        .order_by(ClassSession.starts_at, ClassSession.session_id)
        .limit(limit)
    )
    return list(db.session.execute(stmt).scalars())


def session_counts(batch_ids: set[int]) -> dict[int, tuple[int, int]]:
    """Per batch: (delivered sessions, all sessions that were not cancelled)."""
    if not batch_ids:
        return {}
    rows = db.session.execute(
        select(
            ClassSession.batch_id,
            func.count(case((ClassSession.state == "Delivered", 1))),
            func.count(),
        )
        .where(ClassSession.batch_id.in_(batch_ids), ClassSession.state != "Cancelled")
        .group_by(ClassSession.batch_id)
    )
    return {batch_id: (delivered, total) for batch_id, delivered, total in rows}

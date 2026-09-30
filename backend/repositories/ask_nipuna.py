"""Ask Nipuna: the query log and daily usage (class-session facts come from repositories.class_sessions)."""
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import AiQuery


def get_query(ai_query_id: int) -> AiQuery | None:
    return db.session.get(AiQuery, ai_query_id)


def list_stmt(user_id: int) -> Select:
    return select(AiQuery).where(AiQuery.user_id == user_id).order_by(AiQuery.created_at.desc(), AiQuery.ai_query_id.desc())


def answered_since(user_id: int, since: datetime) -> int:
    """Successful answers since the given time. Refused and failed requests do not use up the allowance."""
    return db.session.execute(
        select(func.count()).select_from(AiQuery).where(AiQuery.user_id == user_id, AiQuery.status == "Answered", AiQuery.created_at >= since)
    ).scalar_one()

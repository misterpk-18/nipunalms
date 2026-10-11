"""Codes that confirm a student's new email address."""
from datetime import datetime

from sqlalchemy import func, select

from config.database import db
from models import EmailChangeCode


def count_since(user_id: int, since: datetime) -> int:
    return db.session.execute(
        select(func.count()).select_from(EmailChangeCode).where(EmailChangeCode.user_id == user_id, EmailChangeCode.created_at >= since)
    ).scalar_one()


def latest_open(user_id: int, now: datetime) -> EmailChangeCode | None:
    """The newest code that is unused and not expired: asking again replaces the earlier code."""
    return db.session.execute(
        select(EmailChangeCode)
        .where(EmailChangeCode.user_id == user_id, EmailChangeCode.used_at.is_(None), EmailChangeCode.expires_at > now)
        .order_by(EmailChangeCode.code_id.desc()).limit(1)
    ).scalar_one_or_none()

"""Password reset codes."""
from datetime import datetime

from sqlalchemy import func, select

from config.database import db
from models import PasswordResetCode


def count_since(user_id: int, since: datetime) -> int:
    return db.session.execute(
        select(func.count()).select_from(PasswordResetCode).where(PasswordResetCode.user_id == user_id, PasswordResetCode.created_at >= since)
    ).scalar_one()


def latest_open(user_id: int, now: datetime) -> PasswordResetCode | None:
    """The newest code that is unused and not expired: asking again replaces the earlier code."""
    return db.session.execute(
        select(PasswordResetCode)
        .where(PasswordResetCode.user_id == user_id, PasswordResetCode.used_at.is_(None), PasswordResetCode.expires_at > now)
        .order_by(PasswordResetCode.code_id.desc()).limit(1)
    ).scalar_one_or_none()

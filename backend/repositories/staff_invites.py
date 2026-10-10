"""Staff invite tokens."""
from datetime import datetime

from sqlalchemy import select

from config.database import db
from models import StaffInvite


def find(token_hash: str) -> StaffInvite | None:
    return db.session.execute(select(StaffInvite).where(StaffInvite.token_hash == token_hash)).scalar_one_or_none()


def outstanding(user_id: int) -> StaffInvite | None:
    """The unused, unrevoked invite of a person (it may be expired)."""
    return db.session.execute(
        select(StaffInvite).where(StaffInvite.user_id == user_id, StaffInvite.used_at.is_(None), StaffInvite.revoked_at.is_(None))
    ).scalar_one_or_none()


def revoke_outstanding(user_id: int, now: datetime) -> None:
    invite = outstanding(user_id)
    if invite is not None:
        invite.revoked_at = now
        db.session.flush()  # free the one-outstanding slot before a new invite is inserted

"""Accounts created by the role-separation split, for the hand-out page."""
from sqlalchemy import Select, select

from config.database import db
from models import SplitAccountHandout


def list_stmt(pending_only: bool) -> Select:
    stmt = select(SplitAccountHandout).order_by(SplitAccountHandout.handed_out_at.is_(None).desc(), SplitAccountHandout.created_at,
                                                SplitAccountHandout.handout_id)
    if pending_only:
        stmt = stmt.where(SplitAccountHandout.handed_out_at.is_(None))
    return stmt


def get(handout_id: int) -> SplitAccountHandout | None:
    return db.session.get(SplitAccountHandout, handout_id)

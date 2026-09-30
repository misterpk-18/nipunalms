"""Branches."""
from sqlalchemy import select

from config.database import db
from models import Branch


def get_by_id(branch_id: int) -> Branch | None:
    return db.session.get(Branch, branch_id)


def get_by_code(branch_code: str) -> Branch | None:
    return db.session.execute(select(Branch).where(Branch.branch_code == branch_code)).scalar_one_or_none()


def list_active(branch_ids: set[int] | None = None) -> list[Branch]:
    """Active branches, restricted to branch_ids unless it is None (all)."""
    stmt = select(Branch).where(Branch.is_active).order_by(Branch.branch_id)
    if branch_ids is not None:
        stmt = stmt.where(Branch.branch_id.in_(branch_ids))
    return list(db.session.execute(stmt).scalars())

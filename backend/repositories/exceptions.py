"""The exception queue view and the recovery steps."""
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import ExceptionItem, ExceptionRecoveryStep


def list_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    """Open exceptions at the given branches (None = all, company-wide rows included), oldest first."""
    stmt = select(ExceptionItem).order_by(ExceptionItem.opened_at, ExceptionItem.source, ExceptionItem.source_id)
    if branch_ids is not None:
        stmt = stmt.where(ExceptionItem.branch_id.in_(branch_ids))
    for column in ("source", "state", "queue", "branch_id"):
        if filters.get(column) is not None:
            stmt = stmt.where(getattr(ExceptionItem, column) == filters[column])
    if filters.get("sources"):
        stmt = stmt.where(ExceptionItem.source.in_(filters["sources"]))
    if filters.get("opened_before") is not None:
        stmt = stmt.where(ExceptionItem.opened_at <= filters["opened_before"])
    if filters.get("opened_after") is not None:
        stmt = stmt.where(ExceptionItem.opened_at > filters["opened_after"])
    if filters.get("owner_user_id") is not None:
        stmt = stmt.where(ExceptionItem.owner_user_id == filters["owner_user_id"])
    if filters.get("awaiting_owner") is not None:
        stmt = stmt.where(ExceptionItem.owner_user_id.is_(None) if filters["awaiting_owner"] else ExceptionItem.owner_user_id.is_not(None))
    return stmt


def get_item(source: str, source_id: int) -> ExceptionItem | None:
    return db.session.get(ExceptionItem, (source, source_id))


def steps_of(source: str, source_id: int) -> list[ExceptionRecoveryStep]:
    stmt = (select(ExceptionRecoveryStep).where(ExceptionRecoveryStep.source == source, ExceptionRecoveryStep.source_id == source_id)
            .order_by(ExceptionRecoveryStep.step_id.desc()))
    return list(db.session.execute(stmt).scalars())


def add_step(source: str, source_id: int, branch_id: int | None, reason: str, logged_by: int) -> ExceptionRecoveryStep:
    step = ExceptionRecoveryStep(source=source, source_id=source_id, branch_id=branch_id, reason=reason, logged_by=logged_by)
    db.session.add(step)
    db.session.flush()
    db.session.refresh(step)
    return step


def counts(branch_ids: set[int] | None) -> dict:
    """Open exceptions at the branches (None = all): total, awaiting a named owner, and per source."""
    stmt = select(ExceptionItem.source, func.count(), func.count().filter(ExceptionItem.owner_user_id.is_(None)))
    if branch_ids is not None:
        stmt = stmt.where(ExceptionItem.branch_id.in_(branch_ids))
    by_source = {source: {"count": n, "awaiting_owner": unowned} for source, n, unowned in db.session.execute(stmt.group_by(ExceptionItem.source)).all()}
    return {"total": sum(v["count"] for v in by_source.values()), "awaiting_owner": sum(v["awaiting_owner"] for v in by_source.values()),
            "by_source": by_source}


def counts_by_source(filters: dict, branch_ids: set[int] | None) -> dict[str, int]:
    """Open items per source with the same scope and filters as the list (the source filter itself left out)."""
    stmt = list_stmt({k: v for k, v in filters.items() if k != "sources"}, branch_ids).order_by(None).subquery()
    return dict(db.session.execute(select(stmt.c.source, func.count()).group_by(stmt.c.source)).all())

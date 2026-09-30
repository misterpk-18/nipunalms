"""Audit log reads (writes go through services/audit.py)."""
from sqlalchemy import Select, select

from config.database import db
from models import AuditLog, User


def list_stmt(filters: dict) -> Select:
    """Newest first, each row with the actor's name and email."""
    stmt = (
        select(AuditLog, User.full_name, User.email)
        .outerjoin(User, User.user_id == AuditLog.actor_user_id)
        .order_by(AuditLog.audit_id.desc())
    )
    for column in ("actor_user_id", "entity_type", "entity_id", "action", "branch_id"):
        if filters.get(column) is not None:
            stmt = stmt.where(getattr(AuditLog, column) == filters[column])
    if filters.get("occurred_from"):
        stmt = stmt.where(AuditLog.occurred_at >= filters["occurred_from"])
    if filters.get("occurred_before"):
        stmt = stmt.where(AuditLog.occurred_at < filters["occurred_before"])
    return stmt


def recent_for_entity(entity_type: str, entity_id: str, limit: int) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.audit_id.desc())
        .limit(limit)
    )
    return list(db.session.execute(stmt).scalars())


def latest_for_entity(entity_type: str, entity_id: str, action: str) -> AuditLog | None:
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id, AuditLog.action == action)
        .order_by(AuditLog.audit_id.desc())
        .limit(1)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def facets() -> dict:
    """The values the filters offer: distinct actions and entity types."""
    return {
        "actions": list(db.session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action)).scalars()),
        "entity_types": list(
            db.session.execute(select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)).scalars()
        ),
    }

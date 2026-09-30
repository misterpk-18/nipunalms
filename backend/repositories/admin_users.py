"""Staff accounts and their role scopes, for the Super Admin's Users & Access screen."""
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import Role, User, UserRoleScope


def _active_scope_condition():
    """A scope that is not revoked and not past its expiry."""
    return UserRoleScope.revoked_at.is_(None) & (UserRoleScope.expires_at.is_(None) | (UserRoleScope.expires_at > func.now()))


def list_stmt(filters: dict) -> Select:
    """Staff logins (no student accounts), by name."""
    stmt = select(User).options(selectinload(User.scopes)).where(User.student_id.is_(None)).order_by(User.full_name, User.user_id)
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    if filters.get("is_active") is not None:
        stmt = stmt.where(User.is_active.is_(filters["is_active"]))
    scope_conditions = []
    if filters.get("role_code"):
        scope_conditions.append(Role.role_code == filters["role_code"])
    if filters.get("branch_id"):
        scope_conditions.append(UserRoleScope.branch_id == filters["branch_id"])
    if scope_conditions:
        stmt = stmt.where(
            exists().where(
                UserRoleScope.user_id == User.user_id, UserRoleScope.role_id == Role.role_id,
                _active_scope_condition(), and_(*scope_conditions),
            )
        )
    return stmt


def get_staff_user(user_id: int) -> User | None:
    stmt = select(User).options(selectinload(User.scopes)).where(User.user_id == user_id, User.student_id.is_(None))
    return db.session.execute(stmt).scalar_one_or_none()


def get_scope(scope_id: int) -> UserRoleScope | None:
    return db.session.get(UserRoleScope, scope_id)


def active_holder_ids(role_code: str) -> set[int]:
    """Active users holding the role at any branch (used to keep at least one Super Admin)."""
    stmt = (
        select(func.distinct(User.user_id))
        .join(UserRoleScope, UserRoleScope.user_id == User.user_id)
        .join(Role, Role.role_id == UserRoleScope.role_id)
        .where(User.is_active, Role.role_code == role_code, _active_scope_condition())
    )
    return set(db.session.execute(stmt).scalars())

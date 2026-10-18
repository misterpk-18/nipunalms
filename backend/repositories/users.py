"""Users and their role scopes."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import Role, User, UserRoleScope


def active_scope_condition():
    return (
        UserRoleScope.revoked_at.is_(None)
        & (UserRoleScope.expires_at.is_(None) | (UserRoleScope.expires_at > func.now()))
    )


def get_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def get_by_email(email: str) -> User | None:
    return db.session.execute(select(User).where(func.lower(User.email) == email.lower())).scalar_one_or_none()


def get_by_student_id(student_id: int) -> User | None:
    return db.session.execute(select(User).where(User.student_id == student_id)).scalar_one_or_none()


def email_taken(email: str, exclude_user_id: int | None = None) -> bool:
    stmt = select(User.user_id).where(func.lower(User.email) == email.lower())
    if exclude_user_id:
        stmt = stmt.where(User.user_id != exclude_user_id)
    return db.session.execute(stmt).first() is not None


def active_scopes(user_id: int) -> list[UserRoleScope]:
    stmt = (
        select(UserRoleScope)
        .join(Role)
        .where(UserRoleScope.user_id == user_id, active_scope_condition(), Role.is_active)
        .order_by(UserRoleScope.scope_id)
    )
    return list(db.session.execute(stmt).scalars())


def find_unrevoked_scope(user_id: int, role_id: int, branch_id: int | None) -> UserRoleScope | None:
    """The scope holding the (user, role, branch) slot — active or expired, but not revoked."""
    stmt = select(UserRoleScope).where(
        UserRoleScope.user_id == user_id,
        UserRoleScope.role_id == role_id,
        UserRoleScope.branch_id.is_(None) if branch_id is None else UserRoleScope.branch_id == branch_id,
        UserRoleScope.revoked_at.is_(None),
    )
    return db.session.execute(stmt).scalar_one_or_none()


def get_role_by_code(role_code: str) -> Role | None:
    return db.session.execute(select(Role).where(Role.role_code == role_code)).scalar_one_or_none()


def list_roles() -> list[Role]:
    return list(db.session.execute(select(Role).where(Role.is_active).order_by(Role.role_id)).scalars())


def holds_role(user_id: int, role_code: str) -> bool:
    """Whether the user currently holds the role at any branch (or company-wide)."""
    stmt = (
        select(UserRoleScope.scope_id)
        .join(Role, Role.role_id == UserRoleScope.role_id)
        .where(UserRoleScope.user_id == user_id, Role.role_code == role_code, Role.is_active, active_scope_condition())
        .limit(1)
    )
    return db.session.execute(stmt).first() is not None


def user_ids_with_role(role_code: str, branch_id: int | None) -> list[int]:
    """Active users holding the role at this branch, or company-wide. branch_id=None: any branch."""
    stmt = (
        select(func.distinct(User.user_id))
        .join(UserRoleScope, UserRoleScope.user_id == User.user_id)
        .join(Role, Role.role_id == UserRoleScope.role_id)
        .where(User.is_active, Role.role_code == role_code, active_scope_condition())
    )
    if branch_id is not None:
        stmt = stmt.where(UserRoleScope.branch_id.is_(None) | (UserRoleScope.branch_id == branch_id))
    return list(db.session.execute(stmt).scalars())


def staff_scopes(role_codes: list[str] | None, branch_ids: set[int] | None) -> list[UserRoleScope]:
    """Active scopes of active users, at the given branches (None = all) plus company-wide scopes."""
    stmt = (
        select(UserRoleScope)
        .join(User, User.user_id == UserRoleScope.user_id)
        .join(Role, Role.role_id == UserRoleScope.role_id)
        .options(selectinload(UserRoleScope.user))
        .where(active_scope_condition(), User.is_active.is_(True), Role.role_code != "STUDENT")
        .order_by(User.full_name, User.user_id, UserRoleScope.scope_id)
    )
    if role_codes:
        stmt = stmt.where(Role.role_code.in_(role_codes))
    if branch_ids is not None:
        stmt = stmt.where(or_(UserRoleScope.branch_id.in_(branch_ids), UserRoleScope.branch_id.is_(None)))
    return list(db.session.execute(stmt).scalars())


def active_role_codes(user_ids: list[int]) -> dict[int, str]:
    """`{user_id: role_code}` of each user's active role (one per account)."""
    if not user_ids:
        return {}
    stmt = (
        select(UserRoleScope.user_id, Role.role_code)
        .join(Role, Role.role_id == UserRoleScope.role_id)
        .where(UserRoleScope.user_id.in_(user_ids), active_scope_condition())
    )
    return {user_id: code for user_id, code in db.session.execute(stmt).all()}

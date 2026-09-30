"""Super Admin: staff accounts and their role scopes (create, grant / revoke scopes, deactivate, reset password).

Students are never created here; their logins come from the CRM (Admission Qualified) and are handled in
services/admin_students.py. Every change is audited with the acting Super Admin.
"""
import secrets
from datetime import datetime, timedelta, timezone

from config.database import db
from models import Role, User, UserRoleScope
from repositories import admin_users as admin_users_repo
from repositories import branches as branches_repo
from repositories import sessions as sessions_repo
from repositories import settings as settings_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit
from services.context import current_user
from services.errors import BusinessRule, Conflict, NotFound, ValidationError
from services.security import hash_password

TEMPORARY_ACCESS_MAX_DAYS = 7  # routine temporary access (security control TEMP_ACCESS)


def list_users(filters: dict, page: int, per_page: int):
    return paginate(admin_users_repo.list_stmt(filters), page, per_page)


def get_user(user_id: int) -> User:
    user = admin_users_repo.get_staff_user(user_id)
    if user is None:
        raise NotFound("Staff user not found")
    return user


def _temporary_password() -> str:
    """Random, long enough for the password policy; shown once to the Super Admin."""
    return secrets.token_urlsafe(max(12, settings_repo.get_int("password_min_length", 10)))


def _resolve_scope(role_code: str, branch_id: int | None) -> tuple[Role, int | None]:
    role = users_repo.get_role_by_code(role_code)
    if role is None or not role.is_active or role_code == "STUDENT":
        raise ValidationError("Choose a staff role", {"role_code": ["Not a staff role"]})
    if role.is_company_wide and branch_id is not None:
        raise ValidationError(f"{role.role_name} covers all branches", {"branch_id": ["Leave the branch empty for this role"]})
    if not role.is_company_wide:
        if branch_id is None:
            raise ValidationError(f"{role.role_name} needs a branch", {"branch_id": ["Required for this role"]})
        branch = branches_repo.get_by_id(branch_id)
        if branch is None or not branch.is_active:
            raise ValidationError("Branch not found", {"branch_id": ["Not an active branch"]})
    return role, branch_id


def _check_expiry(expires_at: datetime | None) -> None:
    if expires_at is None:
        return
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise ValidationError("Expiry must be in the future", {"expires_at": ["Must be in the future"]})
    if expires_at > now + timedelta(days=TEMPORARY_ACCESS_MAX_DAYS):
        raise BusinessRule(f"Temporary access is limited to {TEMPORARY_ACCESS_MAX_DAYS} calendar days",
                           {"expires_at": [f"At most {TEMPORARY_ACCESS_MAX_DAYS} days from now"]})


def _add_scope(user: User, role: Role, branch_id: int | None, expires_at: datetime | None) -> UserRoleScope:
    if users_repo.find_unrevoked_scope(user.user_id, role.role_id, branch_id) is not None:
        raise Conflict("The user already holds this role here", {"role_code": ["Already granted"]})
    scope = UserRoleScope(user_id=user.user_id, role_id=role.role_id, branch_id=branch_id,
                          granted_by=current_user().user_id, expires_at=expires_at)
    db.session.add(scope)
    db.session.flush()
    db.session.refresh(user)
    return scope


def create_user(data: dict) -> tuple[User, str]:
    """A staff login with a generated temporary password (must be changed at first sign-in). Returns (user, password)."""
    email = data["email"]
    if users_repo.email_taken(email):
        raise Conflict("A user with this email already exists", {"email": ["Already in use"]})
    resolved = [(_resolve_scope(s["role_code"], s.get("branch_id")), s.get("expires_at")) for s in data["scopes"]]
    for _, expires_at in resolved:
        _check_expiry(expires_at)

    password = _temporary_password()
    user = User(full_name=data["full_name"], email=email, phone=data.get("phone"), password_hash=hash_password(password),
                must_change_password=True)
    db.session.add(user)
    db.session.flush()
    for (role, branch_id), expires_at in resolved:
        _add_scope(user, role, branch_id, expires_at)
    audit.record("USER_CREATED", "user", user.user_id,
                 new={"full_name": user.full_name, "email": user.email,
                      "scopes": [{"role_code": r.role_code, "branch_id": b} for (r, b), _ in resolved]})
    return user, password


def update_user(user_id: int, changes: dict) -> User:
    user = get_user(user_id)
    if "email" in changes and users_repo.email_taken(changes["email"], exclude_user_id=user.user_id):
        raise Conflict("A user with this email already exists", {"email": ["Already in use"]})
    changed = {field: value for field, value in changes.items() if getattr(user, field) != value}
    if changed:
        old = {field: getattr(user, field) for field in changed}
        for field, value in changed.items():
            setattr(user, field, value)
        audit.record("USER_UPDATED", "user", user.user_id, old=old, new=changed)
    return user


def grant_scope(user_id: int, role_code: str, branch_id: int | None, expires_at: datetime | None) -> User:
    user = get_user(user_id)
    role, branch_id = _resolve_scope(role_code, branch_id)
    _check_expiry(expires_at)
    _add_scope(user, role, branch_id, expires_at)
    audit.record("SCOPE_GRANTED", "user", user.user_id, branch_id=branch_id,
                 new={"role_code": role_code, "branch_id": branch_id, "expires_at": expires_at})
    return user


def revoke_scope(user_id: int, scope_id: int, reason: str) -> User:
    user = get_user(user_id)
    scope = admin_users_repo.get_scope(scope_id)
    if scope is None or scope.user_id != user.user_id or scope.revoked_at is not None:
        raise NotFound("Role scope not found")
    if user.user_id == current_user().user_id:
        raise BusinessRule("You can't revoke your own access")
    if scope.role.role_code == "SUPER_ADMIN":
        _assert_another_super_admin(user.user_id)

    scope.revoked_at, scope.revoked_by = datetime.now(timezone.utc), current_user().user_id
    db.session.flush()
    db.session.refresh(user)
    audit.record("SCOPE_REVOKED", "user", user.user_id, branch_id=scope.branch_id, reason=reason,
                 old={"role_code": scope.role.role_code, "branch_id": scope.branch_id})
    return user


def deactivate(user_id: int, reason: str) -> User:
    """The user can no longer sign in; their sessions end."""
    user = get_user(user_id)
    if user.user_id == current_user().user_id:
        raise BusinessRule("You can't deactivate your own account")
    if not user.is_active:
        raise BusinessRule("This account is already deactivated")
    if user.user_id in admin_users_repo.active_holder_ids("SUPER_ADMIN"):
        _assert_another_super_admin(user.user_id)

    user.is_active = False
    signed_out = sessions_repo.revoke_all_for_user(user.user_id, "account deactivated")
    audit.record("USER_DEACTIVATED", "user", user.user_id, reason=reason, new={"sessions_ended": signed_out})
    return user


def reactivate(user_id: int, reason: str | None) -> User:
    user = get_user(user_id)
    if user.is_active:
        raise BusinessRule("This account is already active")
    user.is_active = True
    user.failed_login_attempts, user.locked_until = 0, None
    audit.record("USER_REACTIVATED", "user", user.user_id, reason=reason)
    return user


def reset_password(user_id: int) -> tuple[User, str]:
    """A new temporary password (must be changed at next sign-in); every session ends and any lockout is cleared."""
    user = get_user(user_id)
    password = _temporary_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_login_attempts, user.locked_until = 0, None
    signed_out = sessions_repo.revoke_all_for_user(user.user_id, "password reset by administrator")
    audit.record("PASSWORD_RESET", "user", user.user_id, new={"sessions_ended": signed_out})
    return user, password


def _assert_another_super_admin(user_id: int) -> None:
    """The system must always keep an active Super Admin."""
    if not (admin_users_repo.active_holder_ids("SUPER_ADMIN") - {user_id}):
        raise BusinessRule("This is the last active Super Admin; grant the role to someone else first")

"""Staff accounts."""
from config.database import db
from models import User, UserRoleScope
from repositories import users as users_repo
from services import audit
from services.auth import check_password_policy
from services.errors import Conflict, NotFound
from services.security import hash_password


def create_staff_user(full_name: str, email: str, password: str, scopes: list[tuple[str, int | None]], *,
                      must_change_password: bool = False) -> User:
    """Create a staff login with (role_code, branch_id) scopes. branch_id is None for company-wide roles."""
    if users_repo.email_taken(email):
        raise Conflict("A user with this email already exists", {"email": ["Already in use"]})
    check_password_policy(password, field="password")

    user = User(full_name=full_name, email=email.lower(), password_hash=hash_password(password),
                must_change_password=must_change_password)
    db.session.add(user)
    db.session.flush()
    for role_code, branch_id in scopes:
        role = users_repo.get_role_by_code(role_code)
        if role is None:
            raise NotFound(f"Role {role_code} not found")
        db.session.add(UserRoleScope(user_id=user.user_id, role_id=role.role_id, branch_id=branch_id))
    db.session.flush()
    audit.record("USER_CREATED", "user", user.user_id, actor_user_id=None,
                 new={"full_name": full_name, "email": user.email, "scopes": [list(s) for s in scopes]})
    return user


def create_initial_admin(email: str, full_name: str, role_code: str, password: str) -> User:
    """`flask create-admin`: the first Founder / CEO or Super Admin of a fresh database."""
    return create_staff_user(full_name, email, password, [(role_code, None)])

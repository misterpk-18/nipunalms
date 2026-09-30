"""Login (staff email, Student ID or student email), sessions, fresh authentication and password changes."""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.database import db
from models import ActivityEvent, Branch, Student, User, UserRoleScope, UserSession
from repositories import branches as branches_repo
from repositories import sessions as sessions_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import set_db_user
from services import audit
from services.context import CurrentUser, Scope, client_ip, client_user_agent, current_user, set_current_user
from services.errors import Forbidden, NotFound, TooManyAttempts, Unauthenticated, ValidationError
from services.security import hash_password, hash_token, new_session_token, verify_password
from services.validation import is_student_code

logger = logging.getLogger(__name__)

SESSION_EXPIRED = "Your session has expired. Please log in again."

# Workspaces, in the order the profile lists them, each with the roles that open it
WORKSPACE_ROLES = (
    ("founder", ("FOUNDER_CEO",)),
    ("admin", ("SUPER_ADMIN", "FOUNDER_CEO")),
    ("academic", ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")),
    ("branch", ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")),
    ("trainer", ("TRAINER",)),
    ("student", ("STUDENT",)),
)
# Where each workspace lands; the first workspace the user has (founder > admin > branch > academic > trainer > student) wins
HOME_ROUTES = (
    ("founder", "/founder"),
    ("admin", "/admin"),
    ("branch", "/branch"),
    ("academic", "/academic"),
    ("trainer", "/trainer"),
    ("student", "/dashboard"),
)


@dataclass
class LoginResult:
    token: str
    session: UserSession
    current: CurrentUser


@dataclass
class Profile:
    user: User
    scopes: list[UserRoleScope]
    branches: list[Branch]
    student: Student | None
    workspaces: list[str]
    home_route: str


# ---------------------------------------------------------------- per-request authentication

def authenticate(token: str) -> CurrentUser:
    """Resolve a bearer token to the current user (called by @login_required on every request)."""
    session = sessions_repo.find_active(hash_token(token))
    if session is None:
        raise Unauthenticated(SESSION_EXPIRED)

    user = users_repo.get_by_id(session.user_id)
    if user is None or not user.is_active:
        raise Unauthenticated(SESSION_EXPIRED)

    current = _to_current_user(user, session.session_id, session.has_fresh_auth, users_repo.active_scopes(user.user_id))
    set_current_user(current)
    set_db_user(user.user_id)
    sessions_repo.touch(session.session_id)
    return current


def _to_current_user(user: User, session_id: str, has_fresh_auth: bool, scopes: list[UserRoleScope]) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        student_id=user.student_id,
        session_id=session_id,
        must_change_password=user.must_change_password,
        has_fresh_auth=has_fresh_auth,
        scopes=tuple(
            Scope(s.scope_id, s.role.role_code, s.role.role_name, s.branch_id, s.role.is_company_wide) for s in scopes
        ),
    )


# ---------------------------------------------------------------- login / logout

def _find_login_user(login: str) -> User | None:
    """A Student ID (NIT-STU-…, any case) finds that student's login; anything else is an email."""
    if is_student_code(login):
        student = students_repo.get_student_by_code(login)
        return users_repo.get_by_student_id(student.student_id) if student else None
    return users_repo.get_by_email(login)


def login(login: str, password: str) -> LoginResult:
    user = _find_login_user(login.strip())
    now = datetime.now(timezone.utc)

    if user is not None and user.locked_until is not None and user.locked_until > now:
        raise TooManyAttempts("Too many failed attempts. Try again later.")

    if not verify_password(user.password_hash if user else None, password) or not user.is_active:
        if user is not None and user.is_active:
            _register_failed_attempt(user, now)
        logger.warning("Failed login for %s from %s", login, client_ip())
        raise Unauthenticated("Invalid login or password")

    scopes = users_repo.active_scopes(user.user_id)
    if not scopes:
        raise Forbidden("Your account has no active access. Contact your coordinator or a Super Admin.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    token = new_session_token()
    session = sessions_repo.create(
        UserSession(
            session_id=hash_token(token),
            user_id=user.user_id,
            ip_address=client_ip(),
            user_agent=client_user_agent(),
            reauthenticated_at=now,  # entering the password counts as fresh auth
        )
    )
    if user.student_id is not None:
        db.session.add(ActivityEvent(student_id=user.student_id, kind="login"))
    audit.record("LOGIN", "user", user.user_id, actor_user_id=user.user_id)
    return LoginResult(token=token, session=session, current=_to_current_user(user, session.session_id, True, scopes))


def _register_failed_attempt(user: User, now: datetime) -> None:
    max_attempts = settings_repo.get_int("login_max_attempts", 5)
    lock_minutes = settings_repo.get_int("login_lock_minutes", 15)

    user.failed_login_attempts += 1
    if user.failed_login_attempts >= max_attempts:
        user.locked_until = now + timedelta(minutes=lock_minutes)
        user.failed_login_attempts = 0
        logger.warning("Locked user %s for %s minutes after %s failed logins", user.user_id, lock_minutes, max_attempts)
    # Commit now: the 401 response would otherwise roll this back
    db.session.commit()


def logout() -> None:
    user = current_user()
    sessions_repo.revoke(user.session_id, "logout")
    audit.record("LOGOUT", "user", user.user_id)


# ---------------------------------------------------------------- current user

def profile(current: CurrentUser | None = None) -> Profile:
    """Everything the frontend needs after login (for /auth/me and the login response)."""
    current = current or current_user()
    user = users_repo.get_by_id(current.user_id)
    workspaces = workspaces_for(current.role_codes)
    return Profile(
        user=user,
        scopes=users_repo.active_scopes(current.user_id),
        branches=branches_repo.list_active(current.branch_ids()),
        student=students_repo.get_student(user.student_id) if user.student_id else None,
        workspaces=workspaces,
        home_route=home_route_for(workspaces),
    )


def workspaces_for(role_codes: set[str]) -> list[str]:
    """Student → student; Trainer → trainer; AC → academic; BM → branch; Super Admin → admin, academic, branch;
    Founder / CEO → founder, admin, branch."""
    return [name for name, roles in WORKSPACE_ROLES if role_codes & set(roles)]


def home_route_for(workspaces: list[str]) -> str:
    for name, route in HOME_ROUTES:
        if name in workspaces:
            return route
    raise Forbidden("Your account has no workspace")


# ---------------------------------------------------------------- fresh auth / passwords

def reauthenticate(password: str) -> None:
    current = current_user()
    user = users_repo.get_by_id(current.user_id)
    if not verify_password(user.password_hash, password):
        raise ValidationError("Password is incorrect", {"password": ["Incorrect password"]})
    sessions_repo.mark_reauthenticated(current.session_id)


def check_password_policy(password: str, field: str = "new_password") -> None:
    min_length = settings_repo.get_int("password_min_length", 10)
    if len(password) < min_length:
        raise ValidationError("Password is too short", {field: [f"Must be at least {min_length} characters"]})


def change_password(current_password: str, new_password: str) -> None:
    current = current_user()
    user = users_repo.get_by_id(current.user_id)
    if not verify_password(user.password_hash, current_password):
        raise ValidationError("Current password is incorrect", {"current_password": ["Incorrect password"]})
    if new_password == current_password:
        raise ValidationError("Choose a new password", {"new_password": ["Must differ from the current password"]})
    check_password_policy(new_password)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(timezone.utc)
    signed_out = sessions_repo.revoke_all_for_user(user.user_id, "password changed", except_session_id=current.session_id)
    sessions_repo.mark_reauthenticated(current.session_id)
    audit.record("PASSWORD_CHANGED", "user", user.user_id, new={"other_sessions_signed_out": signed_out})


# ---------------------------------------------------------------- own sessions

def list_sessions():
    return sessions_repo.list_active_for_user(current_user().user_id)


def revoke_session(session_id: str) -> None:
    current = current_user()
    session = sessions_repo.find_active(session_id)
    if session is None or session.user_id != current.user_id:
        raise NotFound("Session not found")
    sessions_repo.revoke(session_id, "signed out by user")
    audit.record("SESSION_REVOKED", "user", current.user_id, new={"session": session_id[:12]})

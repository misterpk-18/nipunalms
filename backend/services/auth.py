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
from services.errors import BusinessRule, Forbidden, NotFound, TooManyAttempts, Unauthenticated, ValidationError
from services.security import hash_password, hash_token, new_session_token, verify_password
from services.validation import is_student_code

logger = logging.getLogger(__name__)

SESSION_EXPIRED = "Your session has expired. Please log in again."

# One account holds one role (db/119) and that role has exactly one workspace and one home route.
# Highest first: used only to pick deterministically if data ever holds two live roles (decision 23); db/119 prevents it.
ROLE_PRECEDENCE = ("FOUNDER_CEO", "SUPER_ADMIN", "BRANCH_MANAGER", "TRAINER", "STUDENT")
WORKSPACE_OF_ROLE = {
    "FOUNDER_CEO": "founder",
    "SUPER_ADMIN": "admin",
    "BRANCH_MANAGER": "branch",
    "TRAINER": "trainer",
    "STUDENT": "student",
}
HOME_OF_WORKSPACE = {
    "founder": "/founder",
    "admin": "/admin",
    "branch": "/branch",
    "trainer": "/trainer",
    "student": "/dashboard",
}
# Endpoints a Branch Manager with several branches may call before picking one
BRANCH_PICK_ALLOWED = {"auth.me", "auth.logout", "auth.select_branch", "auth.change_branch"}


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
    role_code: str | None
    role_name: str | None
    workspace: str | None
    workspaces: list[str]  # always one element (kept so the frontend that reads a list keeps working)
    home_route: str
    branch: Branch | None  # a Branch Manager's branch for this session
    needs_branch: bool
    pick_branches: list[Branch]  # what a Branch Manager with several branches chooses from (empty once chosen)


# ---------------------------------------------------------------- per-request authentication

def authenticate(token: str) -> CurrentUser:
    """Resolve a bearer token to the current user (called by @login_required on every request)."""
    session = sessions_repo.find_active(hash_token(token))
    if session is None:
        raise Unauthenticated(SESSION_EXPIRED)

    user = users_repo.get_by_id(session.user_id)
    if user is None or not user.is_active:
        raise Unauthenticated(SESSION_EXPIRED)

    current = _session_user(user, session.session_id, session.has_fresh_auth, session.role_code, session.branch_id,
                            users_repo.active_scopes(user.user_id))
    if current is None:
        raise Unauthenticated(SESSION_EXPIRED)  # the role or branch the session started with is no longer on the account
    set_current_user(current)
    set_db_user(user.user_id)
    sessions_repo.touch(session.session_id)
    return current


def primary_role(scopes: list[UserRoleScope]) -> str | None:
    codes = {s.role.role_code for s in scopes}
    return next((code for code in ROLE_PRECEDENCE if code in codes), None)


def _session_user(user: User, session_id: str, has_fresh_auth: bool, role_code: str | None, branch_id: int | None,
                  scopes: list[UserRoleScope]) -> CurrentUser | None:
    """The signed-in person for a session: only the scope the session's role (and, for a Branch Manager, branch) maps to.
    None when the account no longer holds it."""
    if role_code is None:
        return None
    mine = [s for s in scopes if s.role.role_code == role_code]
    needs_branch = False
    if role_code == "BRANCH_MANAGER":
        if branch_id is not None:
            mine = [s for s in mine if s.branch_id == branch_id]
        elif len(mine) > 1:
            needs_branch, mine = True, []  # picks a branch before anything else
        else:
            branch_id = mine[0].branch_id if mine else None
    if not mine and not needs_branch:
        return None
    return CurrentUser(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        student_id=user.student_id,
        session_id=session_id,
        must_change_password=user.must_change_password,
        has_fresh_auth=has_fresh_auth,
        scopes=tuple(Scope(s.scope_id, s.role.role_code, s.role.role_name, s.branch_id, s.role.is_company_wide) for s in mine),
        role_code=role_code,
        active_branch_id=branch_id if role_code == "BRANCH_MANAGER" else None,
        needs_branch=needs_branch,
    )


# ---------------------------------------------------------------- login / logout

def find_login_user(login: str) -> User | None:
    """A Student ID (NIT-STU-…, any case) finds that student's login; anything else is an email."""
    if is_student_code(login):
        student = students_repo.get_student_by_code(login)
        return users_repo.get_by_student_id(student.student_id) if student else None
    return users_repo.get_by_email(login)


def login(login: str, password: str, branch_id: int | None = None) -> LoginResult:
    user = find_login_user(login.strip())
    now = datetime.now(timezone.utc)

    if user is not None and user.locked_until is not None and user.locked_until > now:
        raise TooManyAttempts("Too many failed attempts. Try again later.")

    if not verify_password(user.password_hash if user else None, password) or not user.is_active:
        if user is not None and user.is_active:
            _register_failed_attempt(user, now)
        logger.warning("Failed login for %s from %s", login, client_ip())
        raise Unauthenticated("Invalid login or password")

    return open_session(user, now, branch_id=branch_id)


def open_session(user: User, now: datetime, *, record_activity: bool = True, branch_id: int | None = None) -> LoginResult:
    """Sign `user` in: clear failed attempts, start a session (entering a password or a one-time link counts as fresh auth).
    The session takes the account's one role. A Branch Manager's branch is `branch_id` (403 when it is not on the account), the
    only branch they hold, or, with several, left empty until they pick one (POST /auth/branch).
    Activating an account is not learning activity (the CRM's "last activity" value reads these events), so it passes False."""
    scopes = users_repo.active_scopes(user.user_id)
    role_code = primary_role(scopes)
    if role_code is None:
        raise Forbidden("Your account has no active access. Contact your branch or a Super Admin.")
    session_branch = None
    if role_code == "BRANCH_MANAGER":
        held = sorted({s.branch_id for s in scopes if s.role.role_code == role_code})
        if branch_id is not None and branch_id not in held:
            raise Forbidden("That branch is not on your account")
        session_branch = branch_id if branch_id is not None else (held[0] if len(held) == 1 else None)

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
            reauthenticated_at=now,
            role_code=role_code,
            branch_id=session_branch,
        )
    )
    if user.student_id is not None and record_activity:
        db.session.add(ActivityEvent(student_id=user.student_id, kind="login"))
    audit.record("LOGIN", "user", user.user_id, actor_user_id=user.user_id)
    current = _session_user(user, session.session_id, True, role_code, session_branch, scopes)
    return LoginResult(token=token, session=session, current=current)


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
    workspace = WORKSPACE_OF_ROLE.get(current.role_code)
    held = users_repo.active_scopes(current.user_id)
    mine = [s for s in held if s.scope_id in {c.scope_id for c in current.scopes}]
    pick = []
    if current.needs_branch:
        pick = branches_repo.list_active({s.branch_id for s in held if s.role.role_code == "BRANCH_MANAGER"})
    return Profile(
        user=user,
        scopes=mine,
        branches=pick if current.needs_branch else branches_repo.list_active(current.branch_ids()),
        student=students_repo.get_student(user.student_id) if user.student_id else None,
        role_code=current.role_code,
        role_name=next((s.role.role_name for s in held if s.role.role_code == current.role_code), None),
        workspace=workspace,
        workspaces=[workspace] if workspace else [],
        home_route=home_route_for(workspace),
        branch=branches_repo.get_by_id(current.active_branch_id) if current.active_branch_id else None,
        needs_branch=current.needs_branch,
        pick_branches=pick,
    )


def workspace_of(role_code: str | None) -> str:
    """The one workspace of a role."""
    workspace = WORKSPACE_OF_ROLE.get(role_code)
    if workspace is None:
        raise Forbidden("Your account has no workspace")
    return workspace


def home_route_for(workspace: str | None) -> str:
    if workspace not in HOME_OF_WORKSPACE:
        raise Forbidden("Your account has no workspace")
    return HOME_OF_WORKSPACE[workspace]


# ---------------------------------------------------------------- branch pick (Branch Manager)

def select_branch(branch_id: int) -> CurrentUser:
    """Branch Manager with several branches: fix the session's branch. 403 when it is not one of theirs."""
    current = current_user()
    if current.role_code != "BRANCH_MANAGER":
        raise Forbidden("Only a Branch Manager picks a branch")
    if not current.needs_branch:
        raise BusinessRule("A branch is already chosen for this session. Use Change branch to pick another")
    held = {s.branch_id for s in users_repo.active_scopes(current.user_id) if s.role.role_code == "BRANCH_MANAGER"}
    if branch_id not in held:
        raise Forbidden("That branch is not on your account")
    sessions_repo.set_branch(current.session_id, branch_id)
    audit.record("BRANCH_SELECTED", "user", current.user_id, new={"branch_id": branch_id}, branch_id=branch_id)
    user = users_repo.get_by_id(current.user_id)
    chosen = _session_user(user, current.session_id, current.has_fresh_auth, current.role_code, branch_id,
                           users_repo.active_scopes(current.user_id))
    set_current_user(chosen)
    return chosen


def change_branch() -> None:
    """Ends the session; the person signs in again and picks a branch (the frontend returns to the branch picker)."""
    current = current_user()
    if current.role_code != "BRANCH_MANAGER":
        raise Forbidden("Only a Branch Manager changes branch")
    sessions_repo.revoke(current.session_id, "change branch")
    audit.record("BRANCH_CHANGE", "user", current.user_id, new={"from_branch_id": current.active_branch_id})


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

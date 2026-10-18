from repositories import settings as settings_repo
from controllers.common import Validator, json_body, no_content, ok
from services import activation as activation_service
from services import auth as auth_service
from services import password_reset
from services.context import current_user


def _profile(profile: auth_service.Profile) -> dict:
    return {
        "user": profile.user.to_dict(),
        "role": {"role_code": profile.role_code, "role_name": profile.role_name},
        "workspace": profile.workspace,
        "branch": profile.branch.to_summary() if profile.branch else None,
        "needs_branch": profile.needs_branch,
        "branches": [b.to_summary() for b in profile.pick_branches],
        "scopes": [s.to_dict() for s in profile.scopes],
        "allowed_branches": [b.to_summary() for b in profile.branches],
        "can_change_branch": profile.can_change_branch,
        "workspaces": profile.workspaces,
        "home_route": profile.home_route,
        "student": profile.student.to_profile() if profile.student else None,
    }


def login():
    v = Validator(json_body())
    v.string("login", required=True, max_length=255)
    v.string("password", required=True, max_length=200, strip=False)
    v.integer("branch_id", nullable=True)
    data = v.validate()

    result = auth_service.login(data["login"], data["password"], data.get("branch_id"))
    return ok({"token": result.token, "expires_at": result.session.expires_at,
               **_profile(auth_service.profile(result.current))})


def select_branch():
    v = Validator(json_body())
    v.integer("branch_id", required=True)
    current = auth_service.select_branch(v.validate()["branch_id"])
    return ok(_profile(auth_service.profile(current)))


def change_branch():
    auth_service.change_branch()
    return no_content()


def logout():
    auth_service.logout()
    return no_content()


def me():
    return ok(_profile(auth_service.profile()))


def reauthenticate():
    v = Validator(json_body())
    v.string("password", required=True, max_length=200, strip=False)
    auth_service.reauthenticate(v.validate()["password"])
    return no_content()


def change_password():
    v = Validator(json_body())
    v.string("current_password", required=True, max_length=200, strip=False)
    v.string("new_password", required=True, max_length=200, strip=False)
    data = v.validate()

    auth_service.change_password(data["current_password"], data["new_password"])
    return no_content()


def list_sessions():
    session_id = current_user().session_id
    return ok([s.to_dict(current_session_id=session_id) for s in auth_service.list_sessions()])


def revoke_session(session_id: str):
    auth_service.revoke_session(session_id)
    return no_content()


def get_activation(token: str):
    info = activation_service.describe(token)
    return ok({
        "kind": info.kind,
        "status": info.status,
        "student_code": info.student_code,
        "email": info.email,
        "full_name": info.full_name,
        "expires_at": info.expires_at,
        "password_min_length": settings_repo.get_int("password_min_length", 10),
    })


def activate():
    """Sets the password and signs the person in: the answer is a login response plus what the success step shows."""
    v = Validator(json_body())
    v.string("token", required=True, max_length=200)
    v.string("password", required=True, max_length=200, strip=False)
    data = v.validate()

    done = activation_service.activate(data["token"], data["password"])
    return ok({"activated": True, "student_code": done.student.student_code if done.student else None,
               "token": done.login.token, "expires_at": done.login.session.expires_at,
               **_profile(auth_service.profile(done.login.current))})


def request_reset_code():
    v = Validator(json_body())
    v.string("login", required=True, max_length=255)
    password_reset.request_code(v.validate()["login"])
    return ok({"message": "If the account exists, we've sent a code."})


def reset_password():
    v = Validator(json_body())
    v.string("login", required=True, max_length=255)
    v.string("code", required=True, max_length=20)
    v.string("new_password", required=True, max_length=200, strip=False)
    data = v.validate()
    password_reset.reset(data["login"], data["code"], data["new_password"])
    return no_content()

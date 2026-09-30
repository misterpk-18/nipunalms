from controllers.common import Validator, json_body, no_content, ok
from services import activation as activation_service
from services import auth as auth_service
from services.context import current_user


def _profile(profile: auth_service.Profile) -> dict:
    return {
        "user": profile.user.to_dict(),
        "scopes": [s.to_dict() for s in profile.scopes],
        "allowed_branches": [b.to_summary() for b in profile.branches],
        "workspaces": profile.workspaces,
        "home_route": profile.home_route,
        "student": profile.student.to_profile() if profile.student else None,
    }


def login():
    v = Validator(json_body())
    v.string("login", required=True, max_length=255)
    v.string("password", required=True, max_length=200, strip=False)
    data = v.validate()

    result = auth_service.login(data["login"], data["password"])
    return ok({"token": result.token, "expires_at": result.session.expires_at,
               **_profile(auth_service.profile(result.current))})


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
    record, status = activation_service.describe(token)
    return ok({
        "status": status,
        "student_code": activation_service.mask_student_code(record.student.student_code),
        "full_name": record.student.full_name,
        "expires_at": record.expires_at,
    })


def activate():
    v = Validator(json_body())
    v.string("token", required=True, max_length=200)
    v.string("password", required=True, max_length=200, strip=False)
    data = v.validate()

    student = activation_service.activate(data["token"], data["password"])
    return ok({"activated": True, "student_code": student.student_code})

from controllers.common import Validator, json_body, ok
from services import profile as profile_service
from services.context import current_user

MOBILE_NOTE = "Shared family mobile — not identity proof"


def _device(session) -> dict:
    return {
        "session_id": session.session_id,
        "label": profile_service.describe_device(session.user_agent),
        "created_at": session.created_at,
        "last_seen_at": session.last_seen_at,
        "current": session.session_id == current_user().session_id,
    }


def _view(view: profile_service.ProfileView) -> dict:
    user = view.user
    data = {
        "user": user.to_dict(),
        "scopes": [s.to_dict() for s in view.scopes],
        "allowed_branches": [b.to_summary() for b in view.branches],
        "password_changed_at": user.password_changed_at,
        "last_login_at": user.last_login_at,
        "devices": [_device(d) for d in view.devices],
        "student": None,
    }
    student = view.student
    if student is not None:
        data["student"] = {
            **student.to_profile(),
            "email": student.email,
            "mobile_masked": profile_service.mask_mobile(student.mobile),
            "mobile_note": MOBILE_NOTE,
            "original_branch": student.original_branch.to_summary(),
            "service_branch": student.service_branch.to_summary(),
            "mfa_status": student.mfa_status,
            "recovery": {
                "email_on_file": student.email is not None,
                "method": "Your branch Academic Coordinator can issue a new activation link; only you set the password.",
            },
        }
    return data


def get_profile():
    return ok(_view(profile_service.get_profile()))


def update_profile():
    v = Validator(json_body())
    v.choice("preferred_language", ("en", "te"), required=True)
    profile_service.set_language(v.validate()["preferred_language"])
    return get_profile()


def sign_out_other_devices():
    return ok({"signed_out": profile_service.sign_out_other_devices()})

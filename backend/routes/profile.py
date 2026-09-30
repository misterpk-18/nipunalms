from flask import Blueprint

from controllers import profile as profile_controller
from routes.decorators import login_required, require_roles

profile_bp = Blueprint("profile", __name__, url_prefix="/me")


@profile_bp.get("/profile")
@login_required
def get_profile():
    return profile_controller.get_profile()


@profile_bp.patch("/profile")
@login_required
@require_roles("STUDENT")
def update_profile():
    return profile_controller.update_profile()


@profile_bp.post("/devices/sign-out-others")
@login_required
def sign_out_other_devices():
    return profile_controller.sign_out_other_devices()

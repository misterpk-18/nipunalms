from flask import Blueprint

from controllers import security_controls as controls_controller
from routes.decorators import fresh_auth, login_required, require_roles

security_controls_bp = Blueprint("security_controls", __name__, url_prefix="/security-controls")


@security_controls_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_controls():
    return controls_controller.list_controls()


@security_controls_bp.get("/<int:control_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_control(control_id: int):
    return controls_controller.get_control(control_id)


@security_controls_bp.patch("/<int:control_id>")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def update_control(control_id: int):
    return controls_controller.update_control(control_id)

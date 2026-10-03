from flask import Blueprint

from controllers import ai_controls as ai_controls_controller
from routes.decorators import fresh_auth, login_required, require_roles

ai_controls_bp = Blueprint("ai_controls", __name__, url_prefix="/ai-controls")


@ai_controls_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_controls():
    return ai_controls_controller.list_controls()


@ai_controls_bp.post("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
@fresh_auth
def disable():
    return ai_controls_controller.disable()


@ai_controls_bp.post("/<int:control_id>/restore")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
@fresh_auth
def restore(control_id: int):
    return ai_controls_controller.restore(control_id)

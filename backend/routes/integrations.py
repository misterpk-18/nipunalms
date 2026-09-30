from flask import Blueprint

from controllers import integrations as integrations_controller
from routes.decorators import fresh_auth, login_required, require_roles

integrations_bp = Blueprint("integrations", __name__, url_prefix="/integrations")


@integrations_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_integrations():
    return integrations_controller.list_integrations()


@integrations_bp.get("/status")
@login_required
def list_statuses():
    """Every signed-in user: which integrations are Verified, Pending Verification or Integration Unavailable."""
    return integrations_controller.list_statuses()


@integrations_bp.get("/<int:integration_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_integration(integration_id: int):
    return integrations_controller.get_integration(integration_id)


@integrations_bp.patch("/<int:integration_id>")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def update_integration(integration_id: int):
    return integrations_controller.update_integration(integration_id)

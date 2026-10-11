"""The Super Admin's overview (UX phase U17)."""
from flask import Blueprint

from controllers import admin_overview as overview_controller
from routes.decorators import login_required, require_roles

admin_overview_bp = Blueprint("admin_overview", __name__, url_prefix="/admin")


@admin_overview_bp.get("/needs-action")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def needs_action():
    """What waits for the Super Admin, one row each with its button, and the Setup checklist."""
    return overview_controller.needs_action()


@admin_overview_bp.get("/setup")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def setup():
    """Integrations and security requirements as one checklist with plain states."""
    return overview_controller.setup()


@admin_overview_bp.get("/staff-options")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def staff_options():
    """Active staff, unpaged, for pickers."""
    return overview_controller.staff_options()

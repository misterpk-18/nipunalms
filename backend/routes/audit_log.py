from flask import Blueprint

from controllers import audit_log as audit_controller
from routes.decorators import login_required, require_roles

audit_log_bp = Blueprint("audit_log", __name__, url_prefix="/audit-log")


@audit_log_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_entries():
    return audit_controller.list_entries()


@audit_log_bp.get("/facets")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def facets():
    return audit_controller.facets()

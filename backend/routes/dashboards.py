"""Dashboard summaries: one read per staff workspace."""
from flask import Blueprint

from controllers import dashboards as dashboards_controller
from routes.decorators import login_required, require_roles

dashboards_bp = Blueprint("dashboards", __name__)


@dashboards_bp.get("/academic/summary")
@login_required
@require_roles("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def academic_summary():
    return dashboards_controller.academic_summary()


@dashboards_bp.get("/branch/summary")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def branch_summary():
    return dashboards_controller.branch_summary()


@dashboards_bp.get("/admin/summary")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def admin_summary():
    return dashboards_controller.admin_summary()


@dashboards_bp.get("/founder/summary")
@login_required
@require_roles("FOUNDER_CEO", "SUPER_ADMIN")
def founder_summary():
    return dashboards_controller.founder_summary()

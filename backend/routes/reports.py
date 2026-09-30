"""Workspace reports: the trainer's own batches and the academic branch report."""
from flask import Blueprint

from controllers import reports as reports_controller
from routes.decorators import login_required, require_roles

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/trainer/reports")
@login_required
@require_roles("TRAINER")
def trainer_reports():
    return reports_controller.trainer_reports()


@reports_bp.get("/academic/reports")
@login_required
@require_roles("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def academic_reports():
    return reports_controller.academic_reports_view()

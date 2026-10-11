"""The Issues inbox: one list across the exception sources (UX phase U15)."""
from flask import Blueprint

from controllers import issues as issues_controller
from routes.decorators import login_required, require_roles

issues_bp = Blueprint("issues", __name__, url_prefix="/issues")


@issues_bp.get("")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def list_issues():
    return issues_controller.list_issues()

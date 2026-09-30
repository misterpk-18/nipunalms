from flask import Blueprint

from controllers import finance as finance_controller
from routes.decorators import login_required, require_roles

finance_bp = Blueprint("finance", __name__)


@finance_bp.get("/me/finance")
@login_required
@require_roles("STUDENT")
def my_finance():
    return finance_controller.my_finance()


@finance_bp.get("/finance-summaries")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def list_summaries():
    return finance_controller.list_summaries()


@finance_bp.get("/finance-summaries/<int:admission_id>")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def get_summary(admission_id: int):
    return finance_controller.get_summary(admission_id)

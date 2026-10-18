from flask import Blueprint

from controllers import finance as finance_controller
from routes.decorators import login_required, require_roles

finance_bp = Blueprint("finance", __name__)


@finance_bp.get("/me/finance")
@login_required
@require_roles("STUDENT")
def my_finance():
    return finance_controller.my_finance()


@finance_bp.get("/me/finance/receipts/<int:admission_id>/<path:receipt_number>/pdf")
@login_required
@require_roles("STUDENT")
def my_receipt_pdf(admission_id: int, receipt_number: str):
    return finance_controller.my_receipt_pdf(admission_id, receipt_number)


@finance_bp.get("/branches/<int:branch_id>/payment-instructions")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def get_payment_instructions(branch_id: int):
    return finance_controller.get_payment_instructions(branch_id)


@finance_bp.put("/branches/<int:branch_id>/payment-instructions")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def set_payment_instructions(branch_id: int):
    return finance_controller.set_payment_instructions(branch_id)


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

"""The Branch Manager's workspace reads: My work, Waiting for a batch."""
from flask import Blueprint

from controllers import branch as branch_controller
from routes.decorators import login_required, require_roles
from services.context import ACADEMIC_ROLES

branch_bp = Blueprint("branch", __name__)


@branch_bp.get("/branch/my-work")
@login_required
@require_roles(*ACADEMIC_ROLES)
def my_work():
    return branch_controller.my_work()


@branch_bp.get("/branch/waiting")
@login_required
@require_roles(*ACADEMIC_ROLES)
def waiting():
    return branch_controller.waiting()


@branch_bp.get("/batches/<int:batch_id>/waiting")
@login_required
@require_roles(*ACADEMIC_ROLES)
def waiting_for_batch(batch_id: int):
    return branch_controller.waiting_for_batch(batch_id)


@branch_bp.get("/branch/attendance-summary")
@login_required
@require_roles(*ACADEMIC_ROLES)
def attendance_summary():
    return branch_controller.attendance_summary()


@branch_bp.get("/branch/completion")
@login_required
@require_roles(*ACADEMIC_ROLES)
def completion_pipeline():
    return branch_controller.completion_pipeline()

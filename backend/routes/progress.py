"""Progress endpoints: the four measures per enrolment, the staff table and the branch summary."""
from flask import Blueprint

from controllers import progress as progress_controller
from routes.decorators import login_required, require_roles

progress_bp = Blueprint("progress", __name__)

STAFF = ("TRAINER", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


@progress_bp.get("/me/progress")
@login_required
@require_roles("STUDENT")
def my_progress():
    return progress_controller.my_progress()


@progress_bp.get("/me/progress/next-steps")
@login_required
@require_roles("STUDENT")
def my_next_steps():
    return progress_controller.my_next_steps()


@progress_bp.get("/progress/enrolments/<int:enrolment_id>")
@login_required
@require_roles("STUDENT", *STAFF)
def get_enrolment_progress(enrolment_id: int):
    return progress_controller.get_enrolment_progress(enrolment_id)


@progress_bp.get("/progress/students")
@login_required
@require_roles(*STAFF)
def list_progress():
    return progress_controller.list_progress()


@progress_bp.get("/progress/summary")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def branch_summary():
    return progress_controller.branch_summary()

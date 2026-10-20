from flask import Blueprint

from controllers import google_admin as google_controller
from routes.decorators import fresh_auth, login_required, require_roles

google_bp = Blueprint("google", __name__, url_prefix="/google")


@google_bp.get("/overview")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def overview():
    return google_controller.overview()


@google_bp.get("/jobs")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_jobs():
    return google_controller.list_jobs()


@google_bp.post("/jobs/<int:job_id>/retry")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def retry_job(job_id: int):
    return google_controller.retry_job(job_id)


@google_bp.get("/emails")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_emails():
    return google_controller.list_emails()


@google_bp.get("/branches")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_branches():
    return google_controller.list_branches()


@google_bp.patch("/branches/<int:branch_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
@fresh_auth
def update_branch(branch_id: int):
    return google_controller.update_branch(branch_id)

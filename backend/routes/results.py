"""Results: provisional -> moderated -> published (Modules 19 and 20)."""
from flask import Blueprint

from controllers import results as controller
from routes.decorators import login_required, require_roles
from services.context import MODERATOR_ROLES, STAFF_ROLES, STUDENT_ROLES

results_bp = Blueprint("results", __name__)


@results_bp.get("/me/results")
@login_required
@require_roles(*STUDENT_ROLES)
def my_results():
    return controller.my_results()


@results_bp.get("/results")
@login_required
@require_roles(*STAFF_ROLES)
def list_results():
    return controller.list_results()


@results_bp.get("/assessment-reviews")
@login_required
@require_roles(*STAFF_ROLES)
def review_queue():
    return controller.review_queue()


@results_bp.post("/results/<int:result_id>/moderate")
@login_required
@require_roles(*MODERATOR_ROLES)
def moderate_result(result_id: int):
    return controller.moderate_result(result_id)


@results_bp.post("/results/publish")
@login_required
@require_roles(*MODERATOR_ROLES)
def publish_results():
    return controller.publish_results()

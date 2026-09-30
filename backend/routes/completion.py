"""Completion review endpoints."""
from flask import Blueprint

from controllers import completion as completion_controller
from routes.decorators import fresh_auth, login_required, require_roles

completion_bp = Blueprint("completion", __name__, url_prefix="/completion-reviews")

STAFF = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


@completion_bp.get("")
@login_required
@require_roles(*STAFF)
def list_candidates():
    return completion_controller.list_candidates()


@completion_bp.post("")
@login_required
@require_roles("TRAINER", "ACADEMIC_COORDINATOR", "SUPER_ADMIN")
def open_review():
    return completion_controller.open_review()


@completion_bp.get("/<int:review_id>")
@login_required
@require_roles(*STAFF)
def get_review(review_id: int):
    return completion_controller.get_review(review_id)


@completion_bp.post("/<int:review_id>/recommendation")
@login_required
@require_roles("TRAINER", "ACADEMIC_COORDINATOR", "SUPER_ADMIN")
def recommend(review_id: int):
    return completion_controller.recommend(review_id)


@completion_bp.post("/<int:review_id>/decision")
@login_required
@require_roles("ACADEMIC_COORDINATOR", "SUPER_ADMIN")
@fresh_auth
def decide(review_id: int):
    return completion_controller.decide(review_id)

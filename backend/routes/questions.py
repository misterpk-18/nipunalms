"""Question bank (Module 20). Answer keys are served to staff who author or approve questions only."""
from flask import Blueprint

from controllers import questions as controller
from routes.decorators import login_required, require_roles
from services.context import ASSESSMENT_AUTHOR_ROLES

questions_bp = Blueprint("questions", __name__, url_prefix="/questions")


@questions_bp.get("")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def list_questions():
    return controller.list_questions()


@questions_bp.post("")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def create_question():
    return controller.create_question()


@questions_bp.get("/<int:question_id>")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def get_question(question_id: int):
    return controller.get_question(question_id)


@questions_bp.patch("/<int:question_id>")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def update_question(question_id: int):
    return controller.update_question(question_id)


@questions_bp.post("/<int:question_id>/approve")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def approve_question(question_id: int):
    return controller.approve_question(question_id)


@questions_bp.post("/<int:question_id>/retire")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def retire_question(question_id: int):
    return controller.retire_question(question_id)


@questions_bp.post("/<int:question_id>/new-version")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def new_version(question_id: int):
    return controller.new_version(question_id)

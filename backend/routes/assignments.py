"""Assignments, submissions and reviews (Module 19)."""
from flask import Blueprint

from controllers import assignments as controller
from routes.decorators import login_required, require_roles
from services.context import ASSESSMENT_AUTHOR_ROLES, STUDENT_ROLES

assignments_bp = Blueprint("assignments", __name__)


@assignments_bp.get("/assignments")
@login_required
def list_assignments():
    return controller.list_assignments()


@assignments_bp.get("/assessments/curriculum")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def curriculum_options():
    return controller.curriculum_options()


@assignments_bp.get("/assignments/<int:assignment_id>")
@login_required
def get_assignment(assignment_id: int):
    return controller.get_assignment(assignment_id)


@assignments_bp.post("/assignments")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def create_assignment():
    return controller.create_assignment()


@assignments_bp.patch("/assignments/<int:assignment_id>")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def update_assignment(assignment_id: int):
    return controller.update_assignment(assignment_id)


@assignments_bp.post("/assignments/<int:assignment_id>/release")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def release_assignment(assignment_id: int):
    return controller.release_assignment(assignment_id)


@assignments_bp.post("/assignments/<int:assignment_id>/withdraw")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def withdraw_assignment(assignment_id: int):
    return controller.withdraw_assignment(assignment_id)


@assignments_bp.post("/assignments/<int:assignment_id>/submissions")
@login_required
@require_roles(*STUDENT_ROLES)
def submit_assignment(assignment_id: int):
    return controller.submit_assignment(assignment_id)


@assignments_bp.get("/submissions")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES, "BRANCH_MANAGER", "FOUNDER_CEO")
def list_submissions():
    return controller.list_submissions()


@assignments_bp.get("/submissions/<int:submission_id>")
@login_required
def get_submission(submission_id: int):
    return controller.get_submission(submission_id)


@assignments_bp.get("/submissions/<int:submission_id>/file")
@login_required
def download_submission(submission_id: int):
    return controller.download_submission(submission_id)


@assignments_bp.post("/submissions/<int:submission_id>/start-review")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def start_review(submission_id: int):
    return controller.start_review(submission_id)


@assignments_bp.post("/submissions/<int:submission_id>/review")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def review_submission(submission_id: int):
    return controller.review_submission(submission_id)

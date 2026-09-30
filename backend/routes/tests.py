"""Tests, attempts and mock interview slots (Module 20)."""
from flask import Blueprint

from controllers import tests as controller
from routes.decorators import login_required, require_roles
from services.context import ASSESSMENT_AUTHOR_ROLES, STAFF_ROLES, STUDENT_ROLES

tests_bp = Blueprint("tests", __name__)

# ---------------------------------------------------------------- tests


@tests_bp.get("/tests")
@login_required
def list_tests():
    return controller.list_tests()


@tests_bp.get("/tests/<int:test_id>")
@login_required
def get_test(test_id: int):
    return controller.get_test(test_id)


@tests_bp.post("/tests")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def create_test():
    return controller.create_test()


@tests_bp.patch("/tests/<int:test_id>")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def update_test(test_id: int):
    return controller.update_test(test_id)


@tests_bp.put("/tests/<int:test_id>/questions")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def set_questions(test_id: int):
    return controller.set_questions(test_id)


@tests_bp.post("/tests/<int:test_id>/approve")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def approve_test(test_id: int):
    return controller.approve_test(test_id)


@tests_bp.post("/tests/<int:test_id>/release")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def release_test(test_id: int):
    return controller.release_test(test_id)


@tests_bp.post("/tests/<int:test_id>/close")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def close_test(test_id: int):
    return controller.close_test(test_id)


# ---------------------------------------------------------------- attempts

@tests_bp.post("/tests/<int:test_id>/attempts")
@login_required
@require_roles(*STUDENT_ROLES)
def start_attempt(test_id: int):
    return controller.start_attempt(test_id)


@tests_bp.get("/attempts")
@login_required
@require_roles(*STAFF_ROLES)
def list_attempts():
    return controller.list_attempts()


@tests_bp.get("/attempts/<int:attempt_id>")
@login_required
def get_attempt(attempt_id: int):
    return controller.get_attempt(attempt_id)


@tests_bp.put("/attempts/<int:attempt_id>/answers")
@login_required
@require_roles(*STUDENT_ROLES)
def save_answers(attempt_id: int):
    return controller.save_answers(attempt_id)


@tests_bp.post("/attempts/<int:attempt_id>/submit")
@login_required
@require_roles(*STUDENT_ROLES)
def submit_attempt(attempt_id: int):
    return controller.submit_attempt(attempt_id)


@tests_bp.post("/attempts/<int:attempt_id>/grade")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def grade_attempt(attempt_id: int):
    return controller.grade_attempt(attempt_id)


# ---------------------------------------------------------------- mock interview slots

@tests_bp.get("/tests/<int:test_id>/slots")
@login_required
def list_slots(test_id: int):
    return controller.list_slots(test_id)


@tests_bp.post("/tests/<int:test_id>/slots")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def offer_slots(test_id: int):
    return controller.offer_slots(test_id)


@tests_bp.post("/interview-slots/<int:slot_id>/book")
@login_required
@require_roles(*STUDENT_ROLES)
def book_slot(slot_id: int):
    return controller.book_slot(slot_id)


@tests_bp.post("/interview-slots/<int:slot_id>/confirm")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def confirm_slot(slot_id: int):
    return controller.confirm_slot(slot_id)


@tests_bp.post("/interview-slots/<int:slot_id>/cancel")
@login_required
def cancel_slot(slot_id: int):
    return controller.cancel_slot(slot_id)


@tests_bp.post("/interview-slots/<int:slot_id>/complete")
@login_required
@require_roles(*ASSESSMENT_AUTHOR_ROLES)
def complete_slot(slot_id: int):
    return controller.complete_slot(slot_id)

"""Tests, attempts and mock interview slots."""
from decimal import Decimal

from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.assessments import AI_USE_RULES, GRADING_STATUSES, TEST_KINDS, TEST_RELEASE_STATUSES
from services import attempts as attempts_service
from services import interviews as interviews_service
from services import tests as tests_service
from services.errors import ValidationError


def _fields(v: Validator, *, creating: bool) -> None:
    v.integer("module_id", nullable=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    v.string("title", required=creating, max_length=200)
    v.string("instructions", nullable=True, max_length=5000)
    v.boolean("is_required")
    v.choice("ai_use_rule", AI_USE_RULES)
    v.integer("duration_minutes", nullable=True, min_value=1, max_value=600)
    v.datetime("opens_at", nullable=True)
    v.datetime("closes_at", nullable=True)
    v.integer("attempts_allowed", nullable=True, min_value=1, max_value=10)
    v.decimal("pass_marks", nullable=True, min_value=0)
    v.integer("reviewer_user_id", min_value=1)


def list_tests():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.choice("kind", TEST_KINDS)
    v.choice("release_status", TEST_RELEASE_STATUSES)
    v.integer("reviewer_id", min_value=1)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = tests_service.list_tests(filters, page, per_page)
    return paginated(rows, meta)


def get_test(test_id: int):
    return ok(tests_service.get_test(test_id))


def create_test():
    v = Validator(json_body())
    v.integer("batch_id", required=True, min_value=1)
    v.choice("kind", TEST_KINDS, required=True)
    _fields(v, creating=True)
    test = tests_service.create_test(v.validate())
    return created(tests_service.get_test(test.test_id))


def update_test(test_id: int):
    v = Validator(json_body())
    _fields(v, creating=False)
    test = tests_service.update_test(test_id, require_changes(v.validate()))
    return ok(tests_service.get_test(test.test_id))


def _question_item(v: Validator) -> None:
    v.integer("question_id", required=True, min_value=1)
    v.decimal("marks", min_value=Decimal("0.5"), max_value=100)


def set_questions(test_id: int):
    v = Validator(json_body())
    v.list_of("questions", _question_item, required=True)
    test = tests_service.set_questions(test_id, v.validate()["questions"])
    return ok(tests_service.get_test(test.test_id))


def approve_test(test_id: int):
    return ok(tests_service.get_test(tests_service.approve_test(test_id).test_id))


def release_test(test_id: int):
    v = Validator(json_body())
    v.datetime("opens_at", nullable=True)
    return ok(tests_service.get_test(tests_service.release_test(test_id, v.validate()).test_id))


def close_test(test_id: int):
    return ok(tests_service.get_test(tests_service.close_test(test_id).test_id))


# ---------------------------------------------------------------- attempts

def start_attempt(test_id: int):
    attempt, started = attempts_service.start_attempt(test_id)
    payload = attempts_service.student_payload(attempt)
    return created(payload) if started else ok(payload)


def list_attempts():
    v = Validator(request.args.to_dict())
    v.integer("test_id", min_value=1)
    v.integer("batch_id", min_value=1)
    v.choice("grading_status", GRADING_STATUSES)
    v.boolean("reviewer_me")
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = attempts_service.list_attempts(filters, page, per_page)
    return paginated(rows, meta)


def get_attempt(attempt_id: int):
    return ok(attempts_service.get_attempt(attempt_id))


def _answers(*, required: bool) -> dict | None:
    """{"<question id>": answer}: the answer's shape depends on the question type, so the service checks each one."""
    answers = json_body().get("answers")
    if answers is None and not required:
        return None
    if not isinstance(answers, dict):
        raise ValidationError("Invalid request data", {"answers": ["Must be an object of question id to answer"]})
    return answers


def save_answers(attempt_id: int):
    return ok(attempts_service.save_answers(attempt_id, _answers(required=True)))


def submit_attempt(attempt_id: int):
    return ok(attempts_service.submit_attempt(attempt_id, _answers(required=False)))


def _grade(v: Validator) -> None:
    v.integer("question_id", required=True, min_value=1)
    v.decimal("marks", required=True, min_value=0)
    v.string("feedback", nullable=True, max_length=2000)


def grade_attempt(attempt_id: int):
    v = Validator(json_body())
    v.list_of("grades", _grade, required=True, min_items=1)
    return ok(attempts_service.grade_attempt(attempt_id, v.validate()["grades"]))


# ---------------------------------------------------------------- interview slots

def list_slots(test_id: int):
    return ok(interviews_service.list_slots(test_id))


def _slot_time(v: Validator) -> None:
    v.datetime("starts_at", required=True)
    v.datetime("ends_at", required=True)


def offer_slots(test_id: int):
    v = Validator(json_body())
    v.list_of("slots", _slot_time, required=True, min_items=1)
    v.integer("trainer_user_id", min_value=1)
    data = v.validate()
    slots = interviews_service.offer_slots(test_id, data["slots"], data.get("trainer_user_id"))
    return created([s.to_dict() for s in slots])


def book_slot(slot_id: int):
    return ok(interviews_service.book_slot(slot_id).to_dict(viewer_is_student=True))


def confirm_slot(slot_id: int):
    return ok(interviews_service.confirm_slot(slot_id).to_dict())


def cancel_slot(slot_id: int):
    v = Validator(json_body())
    v.string("reason", max_length=300)
    slot = interviews_service.cancel_slot(slot_id, v.validate().get("reason"))
    return ok(slot.to_dict(viewer_is_student=slot.student_id is None))


def complete_slot(slot_id: int):
    v = Validator(json_body())
    v.integer("rating", required=True, min_value=1, max_value=5)
    v.string("strengths", required=True, max_length=2000)
    v.string("improvements", required=True, max_length=2000)
    v.string("next_action", required=True, max_length=1000)
    return ok(interviews_service.complete_slot(slot_id, v.validate()).to_dict())

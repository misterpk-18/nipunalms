"""Question bank."""
from decimal import Decimal

from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.assessments import QUESTION_DIFFICULTIES, QUESTION_STATUSES, QUESTION_TYPES
from services import questions as questions_service


def _option(v: Validator) -> None:
    v.string("key", required=True, max_length=10)
    v.string("text", required=True, max_length=500)


def _fields(v: Validator, *, creating: bool) -> None:
    v.integer("topic_id", nullable=True, min_value=1)
    v.choice("question_type", QUESTION_TYPES, required=creating)
    v.string("stem", required=creating, max_length=5000)
    v.list_of("options", _option)
    v.string("explanation", nullable=True, max_length=3000)
    v.decimal("marks", min_value=Decimal("0.5"), max_value=100)
    v.choice("difficulty", QUESTION_DIFFICULTIES)
    v.string_list("tags")


def list_questions():
    v = Validator(request.args.to_dict())
    v.integer("course_id", min_value=1)
    v.integer("branch_id", min_value=1)
    v.integer("topic_id", min_value=1)
    v.choice("question_type", QUESTION_TYPES)
    v.choice("status", QUESTION_STATUSES)
    v.choice("difficulty", QUESTION_DIFFICULTIES)
    v.string("q", max_length=100)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = questions_service.list_questions(filters, page, per_page)
    return paginated([q.to_dict() for q in rows], meta)


def get_question(question_id: int):
    return ok(questions_service.get_question(question_id).to_dict())


def create_question():
    body = json_body()
    v = Validator(body)
    v.integer("course_id", required=True, min_value=1)
    v.integer("branch_id", min_value=1)
    _fields(v, creating=True)
    data = v.validate()
    data["answer_key"] = body.get("answer_key")  # the shape depends on the type; the service checks it
    return created(questions_service.create_question(data).to_dict())


def update_question(question_id: int):
    body = json_body()
    v = Validator(body)
    _fields(v, creating=False)
    data = v.validate()
    if "answer_key" in body:
        data["answer_key"] = body["answer_key"]
    return ok(questions_service.update_question(question_id, require_changes(data)).to_dict())


def approve_question(question_id: int):
    return ok(questions_service.approve_question(question_id).to_dict())


def retire_question(question_id: int):
    return ok(questions_service.retire_question(question_id).to_dict())


def new_version(question_id: int):
    return created(questions_service.new_version(question_id).to_dict())

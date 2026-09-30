from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.attendance_enums import COMPLETION_DECISIONS
from services import completion as completion_service


def list_candidates():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.choice("status", ("Active", "Completed"))
    v.string("q", max_length=100)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = completion_service.list_candidates(filters, page, per_page)
    return paginated(rows, meta)


def get_review(review_id: int):
    return ok(completion_service.get_review(review_id))


def open_review():
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    review, is_new = completion_service.open_review(v.validate()["enrolment_id"])
    return created(review.to_dict()) if is_new else ok(review.to_dict())


def recommend(review_id: int):
    v = Validator(json_body())
    v.choice("recommendation", COMPLETION_DECISIONS, required=True)
    v.string("comment", nullable=True, max_length=1000)
    data = v.validate()
    return ok(completion_service.recommend(review_id, data["recommendation"], data.get("comment")).to_dict())


def decide(review_id: int):
    v = Validator(json_body())
    v.choice("decision", COMPLETION_DECISIONS, required=True)
    v.string("reason", nullable=True, max_length=1000)
    data = v.validate()
    return ok(completion_service.decide(review_id, data["decision"], data.get("reason")).to_dict())

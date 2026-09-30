"""Results: the student's published results, and the moderation and publication work of the Academic Coordinator."""
from flask import request

from controllers.common import Validator, get_page_params, json_body, ok, paginated
from models.assessments import RESULT_STATUSES
from services import results as results_service


def my_results():
    return ok(results_service.my_results())


def list_results():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.integer("assignment_id", min_value=1)
    v.integer("test_id", min_value=1)
    v.choice("status", RESULT_STATUSES)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = results_service.list_results(filters, page, per_page)
    return paginated([r.to_dict() for r in rows], meta)


def review_queue():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    return ok(results_service.review_queue(v.validate()))


def moderate_result(result_id: int):
    v = Validator(json_body())
    v.decimal("marks", required=True, min_value=0)
    v.string("reason", required=True, min_length=5, max_length=1000)
    data = v.validate()
    return ok(results_service.moderate(result_id, data["marks"], data["reason"]).to_dict())


def publish_results():
    v = Validator(json_body())
    v.id_list("result_ids", min_items=1)
    v.integer("assignment_id", min_value=1)
    v.integer("test_id", min_value=1)
    published = results_service.publish(v.validate())
    return ok({"published": len(published), "results": [r.to_dict() for r in published]})

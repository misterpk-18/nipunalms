from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.support import SUPPORT_CATEGORIES, SUPPORT_PRIORITIES, SUPPORT_STATUSES
from services import support as support_service


def _filters() -> dict:
    v = Validator(request.args.to_dict())
    v.choice("status", SUPPORT_STATUSES)
    v.choice("category", SUPPORT_CATEGORIES)
    v.boolean("escalated")
    v.boolean("open")
    v.boolean("mine")
    v.integer("branch_id", min_value=1)
    v.integer("student_id", min_value=1)
    v.string("q", max_length=100)
    return v.validate()


def list_requests():
    page, per_page = get_page_params()
    items, meta = support_service.list_requests(_filters(), page, per_page)
    return paginated(support_service.to_summaries(items), meta)


def get_request(support_request_id: int):
    return ok(support_service.to_detail(support_service.get_request(support_request_id)))


def raise_request():
    v = Validator(json_body())
    v.choice("category", SUPPORT_CATEGORIES, required=True)
    v.string("details", required=True, min_length=3, max_length=4000)
    v.string("subject", max_length=200)
    v.choice("priority", SUPPORT_PRIORITIES)
    v.integer("enrolment_id", nullable=True, min_value=1)
    v.integer("student_id", min_value=1)
    return created(support_service.to_detail(support_service.raise_request(v.validate())))


def add_message(support_request_id: int):
    v = Validator(json_body())
    v.string("body", required=True, max_length=4000)
    v.boolean("internal", default=False)
    data = v.validate()
    return created(support_service.to_detail(support_service.add_message(support_request_id, data["body"], internal=data["internal"])))


def change_status(support_request_id: int):
    v = Validator(json_body())
    v.choice("status", support_service.STAFF_STATUS_TARGETS, required=True)
    v.string("note", max_length=2000)
    data = v.validate()
    return ok(support_service.to_detail(support_service.change_status(support_request_id, data["status"], data.get("note"))))


def close(support_request_id: int):
    return ok(support_service.to_detail(support_service.close(support_request_id)))


def reopen(support_request_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, min_length=3, max_length=2000)
    return ok(support_service.to_detail(support_service.reopen(support_request_id, v.validate()["reason"])))


def escalate(support_request_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, min_length=3, max_length=2000)
    return ok(support_service.to_detail(support_service.escalate(support_request_id, v.validate()["reason"])))


def assign(support_request_id: int):
    v = Validator(json_body())
    v.integer("owner_user_id", required=True, min_value=1)
    return ok(support_service.to_detail(support_service.assign(support_request_id, v.validate()["owner_user_id"])))


def assigned_students():
    return ok(support_service.assigned_students())

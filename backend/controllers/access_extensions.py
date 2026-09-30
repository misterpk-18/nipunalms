from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.content import EXTENSION_SCOPES, EXTENSION_STATUSES
from services import access_extensions as extensions_service


def create_request():
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.choice("scope", EXTENSION_SCOPES, required=True)
    v.string("reason", required=True, max_length=1000)
    data = v.validate()
    return created(extensions_service.create_request(data["enrolment_id"], data["scope"], data["reason"]).to_dict())


def list_requests():
    v = Validator(request.args.to_dict())
    for field in ("enrolment_id", "branch_id", "student_id"):
        v.integer(field, min_value=1)
    v.choice("status", EXTENSION_STATUSES)
    v.choice("scope", EXTENSION_SCOPES)
    v.boolean("needs_exception")
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = extensions_service.list_requests(filters, page, per_page)
    return paginated([r.to_dict() for r in rows], meta)


def get_request(request_id: int):
    return ok(extensions_service.get_request(request_id).to_dict())


def decide(request_id: int):
    v = Validator(json_body())
    v.choice("decision", ("approve", "reject"), required=True)
    v.string("note", nullable=True, max_length=1000)
    v.date("new_expiry", nullable=True)
    data = v.validate()
    return ok(extensions_service.decide(request_id, data["decision"], data.get("note"), data.get("new_expiry")).to_dict())

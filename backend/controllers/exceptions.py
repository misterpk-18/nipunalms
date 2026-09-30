from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.exceptions import EXCEPTION_SOURCES
from services import exceptions as exceptions_service


def list_exceptions():
    v = Validator(request.args.to_dict())
    v.choice("source", EXCEPTION_SOURCES)
    v.string("state", max_length=40)
    v.string("queue", max_length=40)
    v.integer("branch_id", min_value=1)
    v.boolean("awaiting_owner")
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = exceptions_service.list_exceptions(filters, page, per_page)
    return paginated(rows, meta)


def list_steps(source: str, source_id: int):
    return ok([step.to_dict() for step in exceptions_service.list_steps(source, source_id)])


def log_step(source: str, source_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, min_length=3, max_length=1000)
    step, item = exceptions_service.log_step(source, source_id, v.validate()["reason"])
    return created({"step": step.to_dict(), "exception": item})

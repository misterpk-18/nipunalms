from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.calendar import CLOSURE_KINDS
from models.certificates import APPROVAL_STATUSES
from services import calendar as calendar_service


def list_closures():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.choice("status", APPROVAL_STATUSES)
    v.date("from")
    v.date("to")
    page, per_page = get_page_params()
    items, meta = calendar_service.list_closures(v.validate(), page, per_page)
    return paginated([c.to_dict() for c in items], meta)


def get_closure(closure_id: int):
    closure, sessions = calendar_service.get_closure(closure_id)
    return ok({**closure.to_dict(), "affected_sessions": [{**s.to_summary(), "batch": s.batch.to_summary()} for s in sessions]})


def create_closure():
    v = Validator(json_body())
    v.choice("kind", CLOSURE_KINDS, required=True)
    v.integer("branch_id", nullable=True, min_value=1)
    v.date("starts_on", required=True)
    v.date("ends_on", required=True)
    v.string("title", required=True, max_length=200)
    v.string("reason", nullable=True, max_length=1000)
    return created(calendar_service.create_closure(v.validate()).to_dict())


def decide_closure(closure_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    data = v.validate()
    return ok(calendar_service.decide_closure(closure_id, data["decision"], data.get("note")).to_dict())

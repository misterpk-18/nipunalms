from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from services import ai_controls as ai_controls_service


def list_controls():
    v = Validator(request.args.to_dict())
    v.boolean("active", default=False)
    page, per_page = get_page_params()
    items, meta = ai_controls_service.list_controls(v.validate()["active"], page, per_page)
    return paginated([c.to_dict() for c in items], meta)


def disable():
    v = Validator(json_body())
    v.choice("audience", ("All", "Student", "Staff"), required=True)
    v.integer("branch_id", nullable=True, min_value=1)
    v.string("reason", required=True, max_length=1000)
    v.string("remediation", nullable=True, max_length=2000)
    data = v.validate()
    return created(ai_controls_service.disable(data["audience"], data.get("branch_id"), data["reason"], data.get("remediation")).to_dict())


def restore(control_id: int):
    v = Validator(json_body())
    v.string("restoration_note", required=True, max_length=2000)
    return ok(ai_controls_service.restore(control_id, v.validate()["restoration_note"]).to_dict())

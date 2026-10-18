from flask import request

from controllers.common import Validator, json_body, ok
from services import ai_budget
from services import founder_inbox as inbox_service


def get_inbox():
    v = Validator(request.args.to_dict())
    v.choice("group", inbox_service.GROUPS)
    return ok(inbox_service.inbox(v.validate().get("group")))


def approve_ai_budget():
    v = Validator(json_body())
    v.integer("amount_inr", required=True, min_value=1)
    return ok(ai_budget.approve(v.validate()["amount_inr"]))

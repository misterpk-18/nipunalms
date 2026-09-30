from flask import request

from controllers.common import Validator, ok
from services import dashboards as dashboards_service


def _branch_id() -> int | None:
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return v.validate().get("branch_id")


def academic_summary():
    return ok(dashboards_service.academic_summary(_branch_id()))


def branch_summary():
    return ok(dashboards_service.branch_summary(_branch_id()))


def admin_summary():
    return ok(dashboards_service.admin_summary())


def founder_summary():
    return ok(dashboards_service.founder_summary())

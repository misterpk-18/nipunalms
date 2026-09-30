from flask import request

from controllers.common import Validator, ok
from services import academic_reports, trainer_workspace


def trainer_reports():
    return ok(trainer_workspace.reports())


def academic_reports_view():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return ok(academic_reports.reports(v.validate().get("branch_id")))

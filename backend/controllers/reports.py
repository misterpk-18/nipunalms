from flask import Response, request

from controllers.common import Validator, ok
from services import academic_reports, branch_reports, trainer_workspace


def trainer_reports():
    return ok(trainer_workspace.reports())


def academic_reports_view():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return ok(academic_reports.reports(v.validate().get("branch_id")))


def _report_args():
    v = Validator(request.args.to_dict())
    v.string("period", max_length=20)
    v.date("from")
    v.date("to")
    v.integer("branch_id", min_value=1)
    return v.validate()


def branch_report():
    a = _report_args()
    return ok(branch_reports.report(a.get("period"), a.get("from"), a.get("to"), a.get("branch_id")))


def branch_report_export():
    a = _report_args()
    v = Validator(request.args.to_dict())
    v.string("section", max_length=20)
    v.string("format", max_length=10)
    extra = v.validate()
    name, content, mime = branch_reports.export(extra.get("section", "figures"), extra.get("format", "csv"), a.get("period"), a.get("from"),
                                                a.get("to"), a.get("branch_id"))
    return Response(content, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})

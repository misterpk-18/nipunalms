from flask import Response, request

from controllers.common import Validator, get_page_params, ok, paginated
from services import audit_log as audit_service


def _filters() -> dict:
    v = Validator(request.args.to_dict())
    v.integer("actor_user_id", min_value=1)
    v.string("entity_type", max_length=50)
    v.string("entity_id", max_length=50)
    v.string("action", max_length=50)
    v.string("preset", max_length=20)
    v.integer("branch_id", min_value=1)
    v.date("from")
    v.date("to")
    return v.validate()


def list_entries():
    page, per_page = get_page_params()
    rows, meta = audit_service.list_entries(_filters(), page, per_page)
    return paginated(rows, meta)


def export():
    name, content = audit_service.export_csv(_filters())
    return Response(content, mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


def facets():
    return ok(audit_service.facets())

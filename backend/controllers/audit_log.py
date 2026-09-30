from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from services import audit_log as audit_service


def list_entries():
    v = Validator(request.args.to_dict())
    v.integer("actor_user_id", min_value=1)
    v.string("entity_type", max_length=50)
    v.string("entity_id", max_length=50)
    v.string("action", max_length=50)
    v.integer("branch_id", min_value=1)
    v.date("from")
    v.date("to")
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = audit_service.list_entries(filters, page, per_page)
    return paginated(
        [{**entry.to_dict(), "actor": {"user_id": entry.actor_user_id, "full_name": name, "email": email} if entry.actor_user_id else None}
         for entry, name, email in rows],
        meta,
    )


def facets():
    return ok(audit_service.facets())

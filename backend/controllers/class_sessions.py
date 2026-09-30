from flask import request

from controllers.common import Validator, get_page_params, paginated
from services import class_sessions as class_sessions_service


def list_class_sessions():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.date("from")
    v.date("to")
    filters = v.validate()

    page, per_page = get_page_params()
    sessions, meta = class_sessions_service.list_sessions(filters, page, per_page)
    return paginated([s.to_dict() for s in sessions], meta)

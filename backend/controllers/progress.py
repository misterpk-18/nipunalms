from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from models.enums import ENROLMENT_STATUSES
from services import progress as progress_service


def my_progress():
    return ok(progress_service.my_progress())


def get_enrolment_progress(enrolment_id: int):
    return ok(progress_service.get_enrolment_progress(enrolment_id))


def list_progress():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.integer("batch_id", min_value=1)
    v.choice("status", ENROLMENT_STATUSES)
    v.boolean("alert")
    v.string("q", max_length=100)
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = progress_service.list_progress(filters, page, per_page)
    return paginated(rows, meta)


def branch_summary():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return ok(progress_service.branch_summary(v.validate().get("branch_id")))

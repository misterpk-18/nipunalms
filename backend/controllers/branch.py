"""The Branch Manager's workspace reads (UX phase U14): My work and Waiting for a batch."""
from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from services import branch_work, completion_pipeline as completion_pipeline_service, waiting as waiting_service


def my_work():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return ok(branch_work.my_work(v.validate().get("branch_id")))


def waiting():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.string("q", max_length=100)
    page, per_page = get_page_params()
    rows, meta = waiting_service.waiting(v.validate(), page, per_page)
    return paginated(rows, meta)


def waiting_for_batch(batch_id: int):
    return ok(waiting_service.waiting_for_batch(batch_id))


def attendance_summary():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    return ok(branch_work.attendance_summary(v.validate().get("branch_id")))


def completion_pipeline():
    v = Validator(request.args.to_dict())
    v.string("stage", max_length=20)
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.string("q", max_length=100)
    page, per_page = get_page_params()
    rows, meta = completion_pipeline_service.pipeline(v.validate(), page, per_page)
    return paginated(rows, meta)

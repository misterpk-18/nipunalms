from flask import request

from controllers.common import Validator, get_page_params, paginated
from models.enums import ENROLMENT_KINDS, ENROLMENT_STATUSES
from services import enrolments as enrolments_service


def _row(row) -> dict:
    data = {**row.enrolment.to_dict(batch=row.batch), "student": row.student.to_summary()}
    if row.waiting_days is not None:
        data["waiting_days"] = row.waiting_days
        data["open_batches"] = [b.to_summary() | {"capacity": b.capacity, "state": b.state} for b in row.open_batches or []]
    return data


def _filters():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.integer("batch_id", min_value=1)
    v.choice("kind", ENROLMENT_KINDS)
    v.choice("status", ENROLMENT_STATUSES)
    v.string("q", max_length=100)
    return v.validate()


def list_enrolments():
    page, per_page = get_page_params()
    rows, meta = enrolments_service.list_enrolments(_filters(), page, per_page)
    return paginated([_row(r) for r in rows], meta)


def allocation_queue():
    page, per_page = get_page_params()
    filters = _filters()
    filters.pop("status", None)
    rows, meta = enrolments_service.allocation_queue(filters, page, per_page)
    return paginated([_row(r) for r in rows], meta)

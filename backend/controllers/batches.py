from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from models.enums import BATCH_STATES
from services import batches as batches_service


def list_batches():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.choice("state", BATCH_STATES)
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = batches_service.list_batches(filters, page, per_page)
    return paginated([b.to_dict(allocated_count=count) for b, count in rows], meta)


def get_batch(batch_id: int):
    batch, count = batches_service.get_batch(batch_id)
    return ok(batch.to_dict(allocated_count=count))

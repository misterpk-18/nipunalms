from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.enums import ALLOCATION_STATUSES
from services import batch_allocations as allocations_service


def roster(batch_id: int):
    v = Validator(request.args.to_dict())
    v.choice("status", ALLOCATION_STATUSES)
    page, per_page = get_page_params()
    rows, meta = allocations_service.roster(batch_id, v.validate().get("status"), page, per_page)
    return paginated([{
        **allocation.to_dict(),
        "student": student.to_summary(),
        "enrolment": {**enrolment.to_summary(), "joining_date": enrolment.joining_date, "mode": enrolment.mode},
    } for allocation, enrolment, student in rows], meta)


def review(batch_id: int):
    v = Validator(request.args.to_dict())
    v.integer("enrolment_id", required=True, min_value=1)
    v.integer("enrolment_track_id", min_value=1)
    v.boolean("transfer", default=False)
    data = v.validate()
    return ok(allocations_service.review_for_enrolment(batch_id, data["enrolment_id"], data["transfer"], data.get("enrolment_track_id")))


def allocate(batch_id: int):
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.integer("enrolment_track_id", nullable=True, min_value=1)
    v.string("reason", nullable=True, max_length=500)
    v.boolean("acknowledge_warnings", default=False)
    data = v.validate()
    allocation = allocations_service.allocate(batch_id, data["enrolment_id"], data.get("reason"), data["acknowledge_warnings"],
                                              data.get("enrolment_track_id"))
    return created(allocation.to_dict())


def deallocate(enrolment_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    v.integer("enrolment_track_id", nullable=True, min_value=1)
    data = v.validate()
    return ok(allocations_service.deallocate(enrolment_id, data["reason"], data.get("enrolment_track_id")).to_dict())

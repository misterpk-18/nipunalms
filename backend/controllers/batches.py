from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.enums import BATCH_READINESS, BATCH_STATES, BATCH_TRAINER_ROLES, DELIVERY_MODES
from services import batches as batches_service


def list_batches():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.choice("state", BATCH_STATES)
    v.choice("mode", DELIVERY_MODES)
    v.choice("readiness", BATCH_READINESS)
    v.string("q", max_length=100)
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = batches_service.list_batches(filters, page, per_page)
    return paginated([b.to_dict(allocated_count=count) for b, count in rows], meta)


def get_batch(batch_id: int):
    detail = batches_service.get_batch_detail(batch_id)
    return ok({
        **detail.batch.to_dict(allocated_count=detail.allocated_count),
        "session_counts": detail.session_counts,
        "trainer_history": [t.to_dict() for t in detail.trainer_history],
        "history": [e.to_dict() for e in detail.events],
    })


def create_batch():
    v = Validator(json_body())
    v.integer("course_id", required=True, min_value=1)
    v.integer("branch_id", required=True, min_value=1)
    v.integer("curriculum_version_id", nullable=True, min_value=1)
    v.integer("capacity", required=True, min_value=1, max_value=500)
    v.choice("mode", DELIVERY_MODES)
    v.date("planned_start", nullable=True)
    v.date("planned_end", nullable=True)
    v.string("crm_batch_id", nullable=True, max_length=100)
    batch = batches_service.create_batch(v.validate())
    return created(batch.to_dict())


def update_batch(batch_id: int):
    v = Validator(json_body())
    v.integer("curriculum_version_id", nullable=True, min_value=1)
    v.integer("capacity", min_value=1, max_value=500)
    v.choice("mode", DELIVERY_MODES)
    v.date("planned_start", nullable=True)
    v.date("planned_end", nullable=True)
    batch = batches_service.update_batch(batch_id, require_changes(v.validate()))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def transition(batch_id: int):
    v = Validator(json_body())
    v.choice("state", ("Starting", "Running", "Completed", "Cancelled"), required=True)
    v.string("reason", nullable=True, max_length=500)
    data = v.validate()
    batch = batches_service.transition(batch_id, data["state"], data.get("reason"))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def get_readiness(batch_id: int):
    return ok(batches_service.readiness_report(batch_id))


def set_readiness(batch_id: int):
    v = Validator(json_body())
    v.choice("readiness", BATCH_READINESS, required=True)
    v.string("readiness_reason", nullable=True, max_length=500)
    v.string("recovery_owner", nullable=True, max_length=100)
    data = v.validate()
    batches_service.set_readiness(batch_id, data["readiness"], data.get("readiness_reason"), data.get("recovery_owner"))
    return ok(batches_service.readiness_report(batch_id))


def assign_trainer(batch_id: int):
    v = Validator(json_body())
    v.integer("trainer_user_id", required=True, min_value=1)
    v.choice("role", BATCH_TRAINER_ROLES, default="Co-trainer")
    v.date("from_date", nullable=True)
    data = v.validate()
    assignment = batches_service.assign_trainer(batch_id, data["trainer_user_id"], data["role"], data.get("from_date"))
    return created(assignment.to_dict())


def change_trainer_role(batch_id: int, batch_trainer_id: int):
    v = Validator(json_body())
    v.choice("role", BATCH_TRAINER_ROLES, required=True)
    assignment = batches_service.change_trainer_role(batch_id, batch_trainer_id, v.validate()["role"])
    return ok(assignment.to_dict())


def end_trainer(batch_id: int, batch_trainer_id: int):
    return ok(batches_service.end_trainer(batch_id, batch_trainer_id).to_dict())

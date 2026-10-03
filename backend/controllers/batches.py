from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.enums import BATCH_READINESS, BATCH_STATES, BATCH_TRAINER_ROLES, DELIVERY_MODES

BATCH_TYPES = ("Group", "Individual", "Corporate")
SCHEDULE_PATTERNS = ("Regular", "Weekend", "Fast-track")
RECORDING_PROVISIONS = ("Included", "Not Included", "Limited")
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
        "successions": [s.to_dict() for s in detail.successions],
        "handovers": [h.to_dict() for h in detail.handovers],
    })


def _timetable(v: Validator) -> None:
    """When the batch meets, for the CRM's sales staff: days, IST start / end times, room. Each may be null (not set)."""
    v.weekdays("schedule_days", nullable=True)
    v.time("start_time", nullable=True)
    v.time("end_time", nullable=True)
    v.string("location", nullable=True, max_length=255)


def _module15(v: Validator) -> None:
    """Type, pattern and display name; verified capacity per side; the recording commitment; the batch-series Meet link."""
    v.string("display_name", nullable=True, max_length=200)
    v.choice("batch_type", BATCH_TYPES)
    v.choice("schedule_pattern", SCHEDULE_PATTERNS)
    for side in ("classroom_capacity", "lab_capacity", "online_capacity"):
        v.integer(side, nullable=True, min_value=0, max_value=500)
    v.choice("recording_provision", RECORDING_PROVISIONS, nullable=True)
    v.string("recording_terms", nullable=True, max_length=2000)
    v.string("meet_series_link", nullable=True, max_length=500)
    v.string("meet_space_id", nullable=True, max_length=200)
    v.string("calendar_series_id", nullable=True, max_length=200)


def create_batch():
    v = Validator(json_body())
    v.integer("course_id", required=True, min_value=1)
    v.integer("branch_id", required=True, min_value=1)
    v.integer("component_id", nullable=True, min_value=1)
    v.integer("curriculum_version_id", nullable=True, min_value=1)
    v.integer("capacity", required=True, min_value=1, max_value=500)
    v.choice("mode", DELIVERY_MODES)
    v.date("planned_start", nullable=True)
    v.date("planned_end", nullable=True)
    _timetable(v)
    _module15(v)
    v.string("crm_batch_id", nullable=True, max_length=100)
    batch = batches_service.create_batch(v.validate())
    return created(batch.to_dict())


def update_batch(batch_id: int):
    v = Validator(json_body())
    v.integer("component_id", nullable=True, min_value=1)
    v.integer("curriculum_version_id", nullable=True, min_value=1)
    v.integer("capacity", min_value=1, max_value=500)
    v.choice("mode", DELIVERY_MODES)
    v.date("planned_start", nullable=True)
    v.date("planned_end", nullable=True)
    _timetable(v)
    _module15(v)
    batch = batches_service.update_batch(batch_id, require_changes(v.validate()))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def transition(batch_id: int):
    v = Validator(json_body())
    v.choice("state", ("Running", "On Hold", "Resume", "Completed", "Cancelled", "Archived"), required=True)
    v.string("reason", nullable=True, max_length=500)
    data = v.validate()
    batch = batches_service.transition(batch_id, data["state"], data.get("reason"))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def propose(batch_id: int):
    v = Validator(json_body())
    v.string("note", nullable=True, max_length=1000)
    batch = batches_service.propose(batch_id, v.validate().get("note"))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def decide_confirmation(batch_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Confirmed", "Returned"), required=True)
    v.string("note", nullable=True, max_length=1000)
    v.string("override_reason", nullable=True, max_length=1000)
    data = v.validate()
    batch = batches_service.decide_confirmation(batch_id, data["decision"], data.get("note"), data.get("override_reason"))
    return ok(batch.to_dict(allocated_count=batches_service.get_batch(batch_id)[1]))


def record_handover(batch_id: int):
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.integer("owner_user_id", required=True, min_value=1)
    v.string("plan", required=True, max_length=2000)
    v.string("destination", required=True, max_length=500)
    v.integer("destination_batch_id", nullable=True, min_value=1)
    return created(batches_service.record_handover(batch_id, v.validate()).to_dict())


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

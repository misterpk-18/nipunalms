"""Module 15 requests: capacity increases, transfers, material changes and student agreement, merge / split, slot preferences."""
from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from models.certificates import APPROVAL_STATUSES
from models.enums import DELIVERY_MODES
from services import batch_changes, batch_transfers, slot_preferences
from services.batch_changes import KIND_FIELDS


def _decision(*choices: str) -> dict:
    v = Validator(json_body())
    v.choice("decision", choices or ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    return v.validate()


def _filters(statuses: tuple[str, ...]) -> dict:
    v = Validator(request.args.to_dict())
    v.choice("status", statuses)
    v.integer("batch_id", min_value=1)
    v.integer("branch_id", min_value=1)
    return v.validate()


# ---------------------------------------------------------------- capacity

def request_capacity(batch_id: int):
    v = Validator(json_body())
    v.integer("to_capacity", required=True, min_value=1, max_value=500)
    for side in ("classroom_capacity", "lab_capacity", "online_capacity"):
        v.integer(side, nullable=True, min_value=0, max_value=500)
    v.string("resource_validation", required=True, max_length=2000)
    v.string("academic_review", required=True, max_length=2000)
    return created(batch_changes.request_capacity(batch_id, v.validate()).to_dict())


def list_capacity_requests():
    page, per_page = get_page_params()
    items, meta = batch_changes.list_capacity_requests(_filters(APPROVAL_STATUSES), page, per_page)
    return paginated([r.to_dict() for r in items], meta)


def decide_capacity(request_id: int):
    data = _decision()
    return ok(batch_changes.decide_capacity(request_id, data["decision"], data.get("note")).to_dict())


# ---------------------------------------------------------------- transfers

def request_transfer(enrolment_id: int):
    v = Validator(json_body())
    v.integer("to_batch_id", required=True, min_value=1)
    v.integer("enrolment_track_id", nullable=True, min_value=1)
    v.string("reason", required=True, max_length=1000)
    v.boolean("acknowledge_warnings", default=False)
    req = batch_transfers.request_transfer(enrolment_id, v.validate())
    return created(req.to_dict())


def list_transfer_requests():
    page, per_page = get_page_params()
    rows, meta = batch_transfers.list_requests(_filters(APPROVAL_STATUSES), page, per_page)
    return paginated([r.to_dict(enrolment) for r, enrolment in rows], meta)


def confirm_destination(request_id: int):
    data = _decision("Confirmed", "Rejected")
    return ok(batch_transfers.confirm_destination(request_id, data["decision"], data.get("note")).to_dict())


def decide_transfer(request_id: int):
    data = _decision()
    return ok(batch_transfers.decide(request_id, data["decision"], data.get("note")).to_dict())


# ---------------------------------------------------------------- material changes

def propose_change(batch_id: int):
    v = Validator(json_body())
    v.choice("kind", tuple(KIND_FIELDS), required=True)
    v.string("proposed_plan", required=True, max_length=2000)
    v.string("reason", required=True, max_length=2000)
    v.string("alternative", nullable=True, max_length=2000)

    def changes(c: Validator) -> None:
        c.date("planned_start", nullable=True)
        c.date("planned_end", nullable=True)
        c.choice("mode", DELIVERY_MODES)
        c.weekdays("schedule_days", nullable=True)
        c.time("start_time", nullable=True)
        c.time("end_time", nullable=True)
        c.integer("target_batch_id", min_value=1)

    v.nested("changes", changes, nullable=True)
    data = v.validate()
    # stored as JSON: dates and times as ISO text, weekdays as ISO numbers
    data["changes"] = {k: (x.isoformat() if hasattr(x, "isoformat") else x) for k, x in (data.get("changes") or {}).items()}
    return created(batch_changes.propose_change(batch_id, data).to_dict())


def list_changes():
    page, per_page = get_page_params()
    items, meta = batch_changes.list_changes(_filters(("Pending Approval", "Awaiting Agreement", "Applied", "Rejected", "Withdrawn")), page, per_page)
    return paginated([c.to_dict(include_responses=False) for c in items], meta)


def get_change(change_id: int):
    return ok(batch_changes.get_change(change_id).to_dict())


def decide_change(change_id: int):
    data = _decision()
    return ok(batch_changes.decide_change(change_id, data["decision"], data.get("note")).to_dict())


def record_response(change_id: int):
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.choice("response", ("Agreed", "Declined"), required=True)
    v.string("note", required=True, max_length=2000)
    v.string("alternative_arranged", nullable=True, max_length=2000)
    return ok(batch_changes.record_response(change_id, v.validate()).to_dict())


def apply_change(change_id: int):
    return ok(batch_changes.apply_change(change_id).to_dict())


def withdraw_change(change_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=1000)
    return ok(batch_changes.withdraw_change(change_id, v.validate()["note"]).to_dict())


def my_changes():
    return ok([{**change.to_dict(include_responses=False), "my_response": response.to_dict()} for change, response in batch_changes.my_changes()])


def respond_as_student(change_id: int):
    v = Validator(json_body())
    v.choice("response", ("Agreed", "Declined"), required=True)
    v.string("note", nullable=True, max_length=2000)
    data = v.validate()
    change = batch_changes.respond_as_student(change_id, data["response"], data.get("note"))
    return ok({**change.to_dict(include_responses=False)})


# ---------------------------------------------------------------- merge / split

def request_succession():
    v = Validator(json_body())
    v.choice("kind", ("Merge", "Split"), required=True)
    v.integer("from_batch_id", required=True, min_value=1)
    v.integer("to_batch_id", required=True, min_value=1)
    v.int_list("enrolment_ids", min_value=1)
    v.date("effective_from", required=True)
    v.string("reason", required=True, max_length=2000)
    v.string("academic_review", required=True, max_length=2000)
    return created(batch_changes.request_succession(v.validate()).to_dict())


def list_successions():
    page, per_page = get_page_params()
    items, meta = batch_changes.list_successions(_filters(APPROVAL_STATUSES), page, per_page)
    return paginated([s.to_dict() for s in items], meta)


def decide_succession(succession_id: int):
    data = _decision()
    return ok(batch_changes.decide_succession(succession_id, data["decision"], data.get("note")).to_dict())


# ---------------------------------------------------------------- slot preferences

def slot_options():
    v = Validator(request.args.to_dict())
    v.integer("enrolment_id", required=True, min_value=1)
    return ok(slot_preferences.options(v.validate()["enrolment_id"]))


def create_preference():
    v = Validator(json_body())
    v.integer("enrolment_id", required=True, min_value=1)
    v.integer("batch_id", nullable=True, min_value=1)
    v.weekdays("preferred_days", nullable=True)
    v.time("preferred_start", nullable=True)
    v.time("preferred_end", nullable=True)
    v.choice("preferred_mode", DELIVERY_MODES, nullable=True)
    v.string("note", nullable=True, max_length=1000)
    return created(slot_preferences.create(v.validate()).to_dict())


def my_preferences():
    return ok([p.to_dict() for p in slot_preferences.mine()])


def withdraw_preference(preference_id: int):
    return ok(slot_preferences.withdraw(preference_id).to_dict())


def list_preferences():
    page, per_page = get_page_params()
    rows, meta = slot_preferences.list_for_staff(_filters(("Requested", "Waitlisted", "Confirmed", "Not Possible", "Withdrawn")), page, per_page)
    return paginated([p.to_dict(enrolment) for p, enrolment in rows], meta)


def set_preference_status(preference_id: int):
    v = Validator(json_body())
    v.choice("status", slot_preferences.STAFF_STATUSES, required=True)
    v.string("status_note", nullable=True, max_length=1000)
    v.integer("batch_id", nullable=True, min_value=1)
    data = v.validate()
    return ok(slot_preferences.set_status(preference_id, data["status"], data.get("status_note"), data.get("batch_id")).to_dict())

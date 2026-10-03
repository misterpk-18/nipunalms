"""Live-class operations: hosts and guests, link incidents, Meet participation, disruptions, cover, shared classes, Meet view."""
from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from services import session_ops


def _decision() -> dict:
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    return v.validate()


def operations_detail(session_id: int):
    return ok(session_ops.operations_detail(session_id))


def operations_view():
    v = Validator(request.args.to_dict())
    v.date("date")
    v.integer("branch_id", min_value=1)
    v.integer("batch_id", min_value=1)
    v.integer("trainer_user_id", min_value=1)
    return ok(session_ops.operations_view(v.validate()))


# ---------------------------------------------------------------- people

def add_person(session_id: int):
    v = Validator(json_body())
    v.choice("role", ("Host", "Backup", "Guest"), required=True)
    v.integer("user_id", nullable=True, min_value=1)
    v.string("guest_name", nullable=True, max_length=150)
    v.email("guest_email", nullable=True)
    v.string("purpose", nullable=True, max_length=1000)
    v.string("student_agreement", nullable=True, max_length=1000)
    return created(session_ops.add_person(session_id, v.validate()).to_dict())


def decide_guest(person_id: int):
    data = _decision()
    return ok(session_ops.decide_guest(person_id, data["decision"], data.get("note")).to_dict())


def remove_person(person_id: int):
    return ok(session_ops.remove_person(person_id).to_dict())


# ---------------------------------------------------------------- incidents and participation

def report_incident(session_id: int):
    v = Validator(json_body())
    v.choice("kind", ("Compromised link", "Unexpected joiner", "Host access failure", "Other"), required=True)
    v.string("description", required=True, max_length=2000)
    v.string("actions_taken", required=True, max_length=2000)
    v.boolean("replace_link", default=False)
    return created(session_ops.report_incident(session_id, v.validate()).to_dict())


def record_participation(session_id: int):
    v = Validator(json_body())
    v.choice("source", ("Meet API", "Manual"), default="Manual")

    def row(r: Validator) -> None:
        r.string("participant_name", nullable=True, max_length=200)
        r.string("participant_email", nullable=True, max_length=255)
        r.datetime("joined_at", required=True)
        r.datetime("left_at", nullable=True)

    v.list_of("entries", row, required=True, min_items=1)
    data = v.validate()
    return created([p.to_dict() for p in session_ops.record_participation(session_id, data["entries"], data["source"])])


def review_participation(participation_id: int):
    v = Validator(json_body())
    v.choice("match_status", ("Matched", "Dismissed"), required=True)
    v.integer("user_id", nullable=True, min_value=1)
    v.string("note", nullable=True, max_length=1000)
    return ok(session_ops.review_participation(participation_id, v.validate()).to_dict())


def list_unmatched():
    v = Validator(request.args.to_dict())
    v.integer("branch_id", min_value=1)
    page, per_page = get_page_params()
    items, meta = session_ops.list_unmatched(v.validate(), page, per_page)
    return paginated([p.to_dict() for p in items], meta)


# ---------------------------------------------------------------- disruptions

def record_disruption(session_id: int):
    v = Validator(json_body())
    v.choice("kind", ("Delayed start", "Failed start", "Connection failure", "Compromised link", "Other"), required=True)
    v.choice("cause", ("Institute", "Provider", "Trainer", "Unknown"), default="Unknown")
    v.integer("delay_minutes", nullable=True, min_value=0, max_value=1440)
    v.string("detail", nullable=True, max_length=2000)
    return created(session_ops.record_disruption(session_id, v.validate()).to_dict())


def resolve_disruption(disruption_id: int):
    v = Validator(json_body())
    v.string("recovery_plan", required=True, max_length=2000)
    v.integer("undelivered_minutes", required=True, min_value=0, max_value=1440)
    v.choice("cause", ("Institute", "Provider", "Trainer", "Unknown"))
    v.integer("replacement_session_id", nullable=True, min_value=1)
    v.integer("owner_user_id", nullable=True, min_value=1)
    return ok(session_ops.resolve_disruption(disruption_id, v.validate()).to_dict())


def list_disruptions():
    v = Validator(request.args.to_dict())
    v.choice("status", ("Open", "Resolved"))
    v.integer("branch_id", min_value=1)
    v.integer("batch_id", min_value=1)
    page, per_page = get_page_params()
    items, meta = session_ops.list_disruptions(v.validate(), page, per_page)
    return paginated([d.to_dict() for d in items], meta)


# ---------------------------------------------------------------- cover

def request_cover(session_id: int):
    v = Validator(json_body())
    v.choice("cover_role", ("Substitute", "Assistant"), required=True)
    v.integer("cover_user_id", required=True, min_value=1)
    v.string("reason", required=True, max_length=1000)
    v.string("scope", required=True, max_length=1000)
    v.string("handover", required=True, max_length=2000)
    return created(session_ops.request_cover(session_id, v.validate()).to_dict())


def list_cover():
    v = Validator(request.args.to_dict())
    v.choice("status", ("Pending", "Approved", "Applied", "Rejected"))
    page, per_page = get_page_params()
    items, meta = session_ops.list_cover(v.validate(), page, per_page)
    return paginated([c.to_dict() for c in items], meta)


def decide_cover(request_id: int):
    data = _decision()
    return ok(session_ops.decide_cover(request_id, data["decision"], data.get("note")).to_dict())


def verify_cover(request_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=1000)
    return ok(session_ops.verify_cover(request_id, v.validate()["note"]).to_dict())


# ---------------------------------------------------------------- shared classes

def add_roster(session_id: int):
    v = Validator(json_body())
    v.integer("batch_id", required=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    v.string("coverage_note", required=True, max_length=2000)
    return created(session_ops.add_roster(session_id, v.validate()).to_dict())


def remove_roster(session_id: int, batch_id: int):
    session_ops.remove_roster(session_id, batch_id)
    return ok({"session_id": session_id, "batch_id": batch_id, "removed": True})

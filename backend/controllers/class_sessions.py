from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.enums import DELIVERY_MODES, MEET_STATUSES, RESCHEDULE_REQUEST_STATUSES, SESSION_STATES
from models.attendance_enums import ATTENDANCE_STATUSES
from services import class_flow as class_flow_service
from services import approvals
from services import class_sessions as class_sessions_service
from services import delivery_access
from services.errors import ValidationError


def _session(session, join: dict | None = None) -> dict:
    """A learner never receives the raw Meet link: only `join`, which carries it while joining is open."""
    return session.to_dict(include_link=not delivery_access.is_student_only(), join=join)


def list_class_sessions():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.integer("branch_id", min_value=1)
    v.integer("course_id", min_value=1)
    v.integer("trainer_user_id", min_value=1)
    v.choice("state", SESSION_STATES)
    v.choice("meet_status", MEET_STATUSES)
    v.choice("purpose", class_sessions_service.PURPOSES)
    v.choice("approval_status", ("Not Required", "Pending", "Approved", "Rejected"))
    v.boolean("upcoming", default=False)
    v.boolean("mine", default=False)
    v.choice("window", ("coming", "past"))
    v.date("from")
    v.date("to")
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = class_sessions_service.list_sessions(filters, page, per_page)
    return paginated([{**_session(r.session, r.join), "open_request_id": r.open_request_id, "changes_count": r.changes_count} for r in rows], meta)


def get_class_session(session_id: int):
    detail = class_sessions_service.get_session(session_id)
    session = detail.session
    topic = session.topic
    return ok({
        **_session(session, detail.join),
        "allocated_count": detail.allocated_count,
        "topic_path": {"topic_id": topic.topic_id, "title": topic.title,
                       "module": {"module_id": topic.module.module_id, "title": topic.module.title}} if topic else None,
        **({} if delivery_access.is_student_only() else {
            "changes": [c.to_dict() for c in detail.changes],
            "meet_events": [e.to_dict() for e in detail.meet_events],
            "open_request": detail.open_request.to_dict() if detail.open_request else None,
            "organizer_note": detail.organizer_note,
        }),
    })


def create_class_sessions():
    v = Validator(json_body())
    v.integer("batch_id", required=True, min_value=1)
    v.integer("topic_id", nullable=True, min_value=1)
    v.string("title", required=True, max_length=200)
    v.datetime("starts_at", required=True)
    v.datetime("ends_at", required=True)
    v.choice("mode", DELIVERY_MODES)
    v.integer("trainer_user_id", min_value=1)
    v.string("room", nullable=True, max_length=100)
    v.string("notes", nullable=True, max_length=2000)
    v.string("override_reason", nullable=True, max_length=500)
    v.choice("purpose", class_sessions_service.PURPOSES, default="Regular")
    v.integer("replaces_session_id", nullable=True, min_value=1)
    v.string("purpose_reference", nullable=True, max_length=2000)
    v.integer("owner_user_id", nullable=True, min_value=1)
    v.date("due_on", nullable=True)
    _meet_ids(v)

    def recurrence_rules(r: Validator) -> None:
        r.int_list("weekdays")
        r.integer("count", min_value=2, max_value=class_sessions_service.MAX_SESSIONS_PER_REQUEST)
        r.date("until")

    v.nested("recurrence", recurrence_rules, nullable=True)
    data = v.validate()
    recurrence = data.get("recurrence")
    if recurrence is not None:
        if not recurrence.get("count") and not recurrence.get("until"):
            raise ValidationError("Invalid request data", {"recurrence": ["Give a count or an until date"]})
        if any(not 0 <= day <= 6 for day in recurrence.get("weekdays", [])):
            raise ValidationError("Invalid request data", {"recurrence": ["Weekdays are 0 (Monday) to 6 (Sunday)"]})
    sessions = class_sessions_service.create_sessions(data)
    return created([_session(s) for s in sessions])


def update_class_session(session_id: int):
    v = Validator(json_body())
    v.string("title", max_length=200)
    v.integer("topic_id", nullable=True, min_value=1)
    v.string("room", nullable=True, max_length=100)
    v.string("notes", nullable=True, max_length=2000)
    v.choice("mode", DELIVERY_MODES)
    v.integer("trainer_user_id", min_value=1)
    v.string("reason", nullable=True, max_length=500)
    v.string("override_reason", nullable=True, max_length=500)
    _meet_ids(v)
    data = v.validate()
    require_changes({k: x for k, x in data.items() if k not in ("override_reason",)})
    return ok(_session(class_sessions_service.update_session(session_id, data)))


def _meet_ids(v: Validator) -> None:
    for key in class_sessions_service.MEET_IDS:
        v.string(key, nullable=True, max_length=200)


def _emergency(v: Validator) -> None:
    """Needed when the change comes less than 24 hours before the class (Module 15 §14)."""
    v.string("emergency_reason", nullable=True, max_length=1000)
    v.string("next_action", nullable=True, max_length=1000)


def reschedule(session_id: int):
    v = Validator(json_body())
    v.datetime("starts_at", required=True)
    v.datetime("ends_at", required=True)
    v.string("reason", required=True, max_length=500)
    v.string("override_reason", nullable=True, max_length=500)
    _emergency(v)
    data = v.validate()
    session = class_sessions_service.reschedule(session_id, data["starts_at"], data["ends_at"], data["reason"], data.get("override_reason"),
                                                emergency=data)
    return ok(_session(session))


def cancel(session_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    _emergency(v)
    data = v.validate()
    return ok(_session(class_sessions_service.cancel(session_id, data["reason"], emergency=data)))


def start(session_id: int):
    return ok(_session(class_sessions_service.start(session_id)))


def deliver(session_id: int):
    v = Validator(json_body())
    v.string("notes", nullable=True, max_length=2000)
    v.choice("outcome", ("Held", "Partially Held"), default="Held")
    v.datetime("actual_start", nullable=True)
    v.datetime("actual_end", nullable=True)
    v.integer("break_minutes", nullable=True, min_value=0, max_value=600)
    v.string("unfulfilled_note", nullable=True, max_length=2000)
    v.int_list("topic_ids", min_value=1)
    v.choice("attendance_default_status", ATTENDANCE_STATUSES, nullable=True)

    def entry_rules(entry: Validator) -> None:
        entry.integer("enrolment_id", required=True, min_value=1)
        entry.choice("status", ATTENDANCE_STATUSES, required=True)
        entry.string("remarks", nullable=True, max_length=500)

    v.list_of("attendance", entry_rules)
    return ok(_session(class_sessions_service.deliver(session_id, v.validate())))


def get_flow(session_id: int):
    return ok(class_flow_service.get(session_id))


def save_flow(session_id: int):
    v = Validator(json_body())
    v.choice("step", class_flow_service.STEPS, nullable=True)

    def draft_rules(draft: Validator) -> None:
        draft.choice("outcome", class_flow_service.OUTCOMES, nullable=True)
        draft.string("actual_start", nullable=True, max_length=40)
        draft.string("actual_end", nullable=True, max_length=40)
        draft.integer("break_minutes", nullable=True, min_value=0, max_value=600)
        draft.string("unfulfilled_note", nullable=True, max_length=2000)
        draft.string("notes", nullable=True, max_length=2000)
        draft.int_list("topic_ids", min_value=1)

    v.nested("draft", draft_rules, nullable=True)
    data = v.validate()
    return ok(class_flow_service.save_progress(session_id, data.get("step"), data.get("draft")))


def request_meet_link(session_id: int):
    return ok(class_flow_service.ask_for_meet_link(session_id))


def confirm(session_id: int):
    return ok(_session(class_sessions_service.confirm(session_id)))


def decide_purpose(session_id: int):
    v = Validator(json_body())
    v.choice("decision", ("Approved", "Rejected"), required=True)
    v.string("note", nullable=True, max_length=1000)
    data = v.validate()
    return ok(_session(class_sessions_service.decide_purpose(session_id, data["decision"], data.get("note"))))


def waive_replacement(session_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=1000)
    return ok(_session(class_sessions_service.waive_replacement(session_id, v.validate()["reason"])))


def save_notes(session_id: int):
    v = Validator(json_body())
    v.string("notes", required=True, max_length=2000)
    return ok(_session(class_sessions_service.save_notes(session_id, v.validate()["notes"])))


# ---------------------------------------------------------------- Meet

def associate_meet(session_id: int):
    v = Validator(json_body())
    v.string("meet_link", required=True, max_length=500)
    _meet_ids(v)
    data = v.validate()
    return ok(_session(class_sessions_service.associate_meet(session_id, data["meet_link"], data)))


def mark_meet_failed(session_id: int):
    v = Validator(json_body())
    v.string("detail", required=True, max_length=500)
    return ok(_session(class_sessions_service.mark_meet_failed(session_id, v.validate()["detail"])))


def reset_meet(session_id: int):
    return ok(_session(class_sessions_service.reset_meet(session_id)))


# ---------------------------------------------------------------- reschedule requests

def list_requests():
    v = Validator(request.args.to_dict())
    v.choice("status", RESCHEDULE_REQUEST_STATUSES)
    v.integer("batch_id", min_value=1)
    v.integer("branch_id", min_value=1)
    page, per_page = get_page_params()
    rows, meta = class_sessions_service.list_requests(v.validate(), page, per_page)
    return paginated([r.to_dict() | {"can_decide": r.status == "Open" and approvals.can_decide_branch_request(r.requested_by)} for r in rows], meta)


def request_reschedule(session_id: int):
    v = Validator(json_body())
    v.datetime("proposed_starts_at", required=True)
    v.datetime("proposed_ends_at", required=True)
    v.string("reason", required=True, max_length=500)
    data = v.validate()
    req = class_sessions_service.request_reschedule(session_id, data["proposed_starts_at"], data["proposed_ends_at"], data["reason"])
    return created(req.to_dict())


def approve_request(request_id: int):
    v = Validator(json_body())
    v.string("note", nullable=True, max_length=500)
    v.string("override_reason", nullable=True, max_length=500)
    _emergency(v)
    data = v.validate()
    return ok(class_sessions_service.approve_request(request_id, data.get("note"), data.get("override_reason"), emergency=data).to_dict())


def reject_request(request_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=500)
    return ok(class_sessions_service.reject_request(request_id, v.validate()["note"]).to_dict())

from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.enums import DELIVERY_MODES, MEET_STATUSES, RESCHEDULE_REQUEST_STATUSES, SESSION_STATES
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
    v.boolean("upcoming", default=False)
    v.boolean("mine", default=False)
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
    v.boolean("acknowledge_room_conflict", default=False)

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
    v.boolean("acknowledge_room_conflict", default=False)
    data = v.validate()
    require_changes({k: x for k, x in data.items() if k not in ("acknowledge_room_conflict",)})
    return ok(_session(class_sessions_service.update_session(session_id, data)))


def reschedule(session_id: int):
    v = Validator(json_body())
    v.datetime("starts_at", required=True)
    v.datetime("ends_at", required=True)
    v.string("reason", required=True, max_length=500)
    v.boolean("acknowledge_room_conflict", default=False)
    data = v.validate()
    session = class_sessions_service.reschedule(session_id, data["starts_at"], data["ends_at"], data["reason"], data["acknowledge_room_conflict"])
    return ok(_session(session))


def cancel(session_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    return ok(_session(class_sessions_service.cancel(session_id, v.validate()["reason"])))


def start(session_id: int):
    return ok(_session(class_sessions_service.start(session_id)))


def deliver(session_id: int):
    v = Validator(json_body())
    v.string("notes", nullable=True, max_length=2000)
    return ok(_session(class_sessions_service.deliver(session_id, v.validate().get("notes"))))


# ---------------------------------------------------------------- Meet

def associate_meet(session_id: int):
    v = Validator(json_body())
    v.string("meet_link", required=True, max_length=500)
    return ok(_session(class_sessions_service.associate_meet(session_id, v.validate()["meet_link"])))


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
    return paginated([r.to_dict() for r in rows], meta)


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
    v.boolean("acknowledge_room_conflict", default=False)
    data = v.validate()
    return ok(class_sessions_service.approve_request(request_id, data.get("note"), data["acknowledge_room_conflict"]).to_dict())


def reject_request(request_id: int):
    v = Validator(json_body())
    v.string("note", required=True, max_length=500)
    return ok(class_sessions_service.reject_request(request_id, v.validate()["note"]).to_dict())

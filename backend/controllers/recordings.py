from flask import request

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.content import (
    RECORDING_EXCEPTION_STATUSES, RECORDING_ISSUE_TYPES, RECORDING_SOURCES, RECORDING_STATUSES,
)
from services import recordings as recordings_service


def list_recordings():
    v = Validator(request.args.to_dict())
    for field in ("session_id", "batch_id", "branch_id", "course_id"):
        v.integer(field, min_value=1)
    v.choice("status", RECORDING_STATUSES)
    filters = v.validate()

    page, per_page = get_page_params()
    recordings, meta = recordings_service.list_recordings(filters, page, per_page)
    return paginated([r.to_dict() for r in recordings], meta)


def get_recording(recording_id: int):
    recording, exceptions = recordings_service.get_recording_detail(recording_id)
    return ok({**recording.to_dict(), "exceptions": exceptions})


def register_recording():
    v = Validator(json_body())
    v.integer("session_id", required=True, min_value=1)
    v.choice("status", ("Processing", "Unavailable"), default="Processing")
    v.choice("source", RECORDING_SOURCES, default="Google Drive")
    v.string("media_ref", nullable=True, max_length=500)
    v.integer("duration_minutes", nullable=True, min_value=1)
    v.boolean("download_allowed", default=False)
    return created(recordings_service.register(v.validate()).to_dict())


def update_recording(recording_id: int):
    v = Validator(json_body())
    v.choice("source", RECORDING_SOURCES)
    v.string("media_ref", nullable=True, max_length=500)
    v.integer("duration_minutes", nullable=True, min_value=1)
    v.boolean("download_allowed")
    return ok(recordings_service.update(recording_id, require_changes(v.validate())).to_dict())


def release_recording(recording_id: int):
    return ok(recordings_service.release(recording_id).to_dict())


def _required_text(field: str) -> str:
    v = Validator(json_body())
    v.string(field, required=True, max_length=1000)
    return v.validate()[field]


def hold_recording(recording_id: int):
    return ok(recordings_service.hold(recording_id, _required_text("reason")).to_dict())


def partial_recording(recording_id: int):
    return ok(recordings_service.mark_partial(recording_id, _required_text("note")).to_dict())


def unavailable_recording(recording_id: int):
    return ok(recordings_service.mark_unavailable(recording_id, _required_text("reason")).to_dict())


def watch_recording(recording_id: int):
    return ok(recordings_service.watch(recording_id))


# ---------------------------------------------------------------- exceptions

def list_exceptions():
    v = Validator(request.args.to_dict())
    for field in ("branch_id", "batch_id", "session_id"):
        v.integer(field, min_value=1)
    v.choice("status", RECORDING_EXCEPTION_STATUSES)
    v.choice("issue_type", RECORDING_ISSUE_TYPES)
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = recordings_service.list_exceptions(filters, page, per_page)
    return paginated(rows, meta)


def get_exception(exception_id: int):
    return ok(recordings_service.get_exception_detail(exception_id))


def raise_exception():
    v = Validator(json_body())
    v.integer("session_id", required=True, min_value=1)
    v.choice("issue_type", RECORDING_ISSUE_TYPES, required=True)
    v.string("issue", required=True, max_length=1000)
    exception = recordings_service.raise_manual(v.validate())
    return created(recordings_service.exception_dict(exception))


def start_exception(exception_id: int):
    return ok(recordings_service.exception_dict(recordings_service.start_exception(exception_id)))


def resolve_exception(exception_id: int):
    exception = recordings_service.resolve_exception(exception_id, _required_text("resolution_note"))
    return ok(recordings_service.exception_dict(exception))

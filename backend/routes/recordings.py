from flask import Blueprint

from controllers import recordings as recordings_controller
from routes.decorators import login_required, require_roles

recordings_bp = Blueprint("recordings", __name__, url_prefix="/recordings")
recording_exceptions_bp = Blueprint("recording_exceptions", __name__, url_prefix="/recording-exceptions")

STAFF = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
MANAGERS = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")
EXCEPTION_HANDLERS = ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN")


@recordings_bp.get("")
@login_required
@require_roles(*STAFF)
def list_recordings():
    return recordings_controller.list_recordings()


@recordings_bp.post("")
@login_required
@require_roles(*MANAGERS)
def register_recording():
    return recordings_controller.register_recording()


@recordings_bp.get("/<int:recording_id>")
@login_required
@require_roles(*STAFF)
def get_recording(recording_id: int):
    return recordings_controller.get_recording(recording_id)


@recordings_bp.patch("/<int:recording_id>")
@login_required
@require_roles(*MANAGERS)
def update_recording(recording_id: int):
    return recordings_controller.update_recording(recording_id)


@recordings_bp.post("/<int:recording_id>/release")
@login_required
@require_roles(*MANAGERS)
def release_recording(recording_id: int):
    return recordings_controller.release_recording(recording_id)


@recordings_bp.post("/<int:recording_id>/hold")
@login_required
@require_roles(*MANAGERS)
def hold_recording(recording_id: int):
    return recordings_controller.hold_recording(recording_id)


@recordings_bp.post("/<int:recording_id>/partial")
@login_required
@require_roles(*MANAGERS)
def partial_recording(recording_id: int):
    return recordings_controller.partial_recording(recording_id)


@recordings_bp.post("/<int:recording_id>/unavailable")
@login_required
@require_roles(*MANAGERS)
def unavailable_recording(recording_id: int):
    return recordings_controller.unavailable_recording(recording_id)


@recordings_bp.post("/<int:recording_id>/watch")
@login_required
@require_roles("STUDENT")
def watch_recording(recording_id: int):
    return recordings_controller.watch_recording(recording_id)


@recording_exceptions_bp.get("")
@login_required
@require_roles(*STAFF)
def list_exceptions():
    return recordings_controller.list_exceptions()


@recording_exceptions_bp.post("")
@login_required
@require_roles("TRAINER", *MANAGERS)
def raise_exception():
    return recordings_controller.raise_exception()


@recording_exceptions_bp.get("/<int:exception_id>")
@login_required
@require_roles(*STAFF)
def get_exception(exception_id: int):
    return recordings_controller.get_exception(exception_id)


@recording_exceptions_bp.post("/<int:exception_id>/start")
@login_required
@require_roles(*EXCEPTION_HANDLERS)
def start_exception(exception_id: int):
    return recordings_controller.start_exception(exception_id)


@recording_exceptions_bp.post("/<int:exception_id>/resolve")
@login_required
@require_roles(*EXCEPTION_HANDLERS)
def resolve_exception(exception_id: int):
    return recordings_controller.resolve_exception(exception_id)

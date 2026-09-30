from flask import Blueprint

from controllers import support as support_controller
from routes.decorators import login_required, require_roles
from services.context import ACADEMIC_ROLES, STAFF_ROLES

support_bp = Blueprint("support", __name__, url_prefix="/support-requests")
trainer_students_bp = Blueprint("trainer_students", __name__, url_prefix="/trainer")


@support_bp.get("")
@login_required
def list_requests():
    return support_controller.list_requests()


@support_bp.post("")
@login_required
def raise_request():
    return support_controller.raise_request()


@support_bp.get("/<int:support_request_id>")
@login_required
def get_request(support_request_id: int):
    return support_controller.get_request(support_request_id)


@support_bp.post("/<int:support_request_id>/messages")
@login_required
def add_message(support_request_id: int):
    return support_controller.add_message(support_request_id)


@support_bp.post("/<int:support_request_id>/status")
@login_required
@require_roles(*STAFF_ROLES)
def change_status(support_request_id: int):
    return support_controller.change_status(support_request_id)


@support_bp.post("/<int:support_request_id>/close")
@login_required
@require_roles("STUDENT")
def close(support_request_id: int):
    return support_controller.close(support_request_id)


@support_bp.post("/<int:support_request_id>/reopen")
@login_required
def reopen(support_request_id: int):
    return support_controller.reopen(support_request_id)


@support_bp.post("/<int:support_request_id>/escalate")
@login_required
@require_roles(*STAFF_ROLES)
def escalate(support_request_id: int):
    return support_controller.escalate(support_request_id)


@support_bp.post("/<int:support_request_id>/assign")
@login_required
@require_roles(*ACADEMIC_ROLES)
def assign(support_request_id: int):
    return support_controller.assign(support_request_id)


@trainer_students_bp.get("/students")
@login_required
@require_roles("TRAINER")
def assigned_students():
    return support_controller.assigned_students()

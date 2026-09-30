from flask import Blueprint

from controllers import class_sessions as class_sessions_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES
from services.delivery_access import MANAGE_ROLES

class_sessions_bp = Blueprint("class_sessions", __name__)

TEACHING_ROLES = ("TRAINER", *MANAGE_ROLES)


@class_sessions_bp.get("/class-sessions")
@login_required
def list_class_sessions():
    return class_sessions_controller.list_class_sessions()


@class_sessions_bp.post("/class-sessions")
@login_required
@require_roles(*MANAGE_ROLES)
def create_class_sessions():
    return class_sessions_controller.create_class_sessions()


@class_sessions_bp.get("/class-sessions/<int:session_id>")
@login_required
def get_class_session(session_id: int):
    return class_sessions_controller.get_class_session(session_id)


@class_sessions_bp.patch("/class-sessions/<int:session_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def update_class_session(session_id: int):
    return class_sessions_controller.update_class_session(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/reschedule")
@login_required
@require_roles(*MANAGE_ROLES)
def reschedule(session_id: int):
    return class_sessions_controller.reschedule(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/cancel")
@login_required
@require_roles(*MANAGE_ROLES)
def cancel(session_id: int):
    return class_sessions_controller.cancel(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/start")
@login_required
@require_roles(*TEACHING_ROLES)
def start(session_id: int):
    return class_sessions_controller.start(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/deliver")
@login_required
@require_roles(*TEACHING_ROLES)
def deliver(session_id: int):
    return class_sessions_controller.deliver(session_id)


@class_sessions_bp.put("/class-sessions/<int:session_id>/notes")
@login_required
@require_roles(*TEACHING_ROLES)
def save_notes(session_id: int):
    return class_sessions_controller.save_notes(session_id)


@class_sessions_bp.put("/class-sessions/<int:session_id>/meet")
@login_required
@require_roles(*MANAGE_ROLES)
def associate_meet(session_id: int):
    return class_sessions_controller.associate_meet(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/meet/fail")
@login_required
@require_roles(*MANAGE_ROLES)
def mark_meet_failed(session_id: int):
    return class_sessions_controller.mark_meet_failed(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/meet/reset")
@login_required
@require_roles(*MANAGE_ROLES)
def reset_meet(session_id: int):
    return class_sessions_controller.reset_meet(session_id)


@class_sessions_bp.post("/class-sessions/<int:session_id>/reschedule-requests")
@login_required
@require_roles("TRAINER")
def request_reschedule(session_id: int):
    return class_sessions_controller.request_reschedule(session_id)


@class_sessions_bp.get("/reschedule-requests")
@login_required
@require_roles(*STAFF_ROLES)
def list_requests():
    return class_sessions_controller.list_requests()


@class_sessions_bp.post("/reschedule-requests/<int:request_id>/approve")
@login_required
@require_roles(*MANAGE_ROLES)
def approve_request(request_id: int):
    return class_sessions_controller.approve_request(request_id)


@class_sessions_bp.post("/reschedule-requests/<int:request_id>/reject")
@login_required
@require_roles(*MANAGE_ROLES)
def reject_request(request_id: int):
    return class_sessions_controller.reject_request(request_id)

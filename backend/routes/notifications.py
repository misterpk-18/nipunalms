from flask import Blueprint

from controllers import notifications as notifications_controller
from routes.decorators import login_required

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.get("")
@login_required
def list_notifications():
    return notifications_controller.list_notifications()


@notifications_bp.get("/overview")
@login_required
def overview():
    return notifications_controller.overview()


@notifications_bp.post("/read-all")
@login_required
def mark_all_read():
    return notifications_controller.mark_all_read()


@notifications_bp.get("/preferences")
@login_required
def get_preferences():
    return notifications_controller.get_preferences()


@notifications_bp.put("/preferences")
@login_required
def set_preferences():
    return notifications_controller.set_preferences()


@notifications_bp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    return notifications_controller.mark_read(notification_id)


@notifications_bp.post("/<int:notification_id>/acknowledge")
@login_required
def acknowledge(notification_id: int):
    return notifications_controller.acknowledge(notification_id)


@notifications_bp.post("/<int:notification_id>/action-done")
@login_required
def mark_action_done(notification_id: int):
    return notifications_controller.mark_action_done(notification_id)

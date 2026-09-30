from flask import Blueprint

from controllers import crm_sync as sync_controller
from routes.decorators import fresh_auth, login_required, require_roles

crm_sync_bp = Blueprint("crm_sync", __name__, url_prefix="/admin/crm-sync")


@crm_sync_bp.get("/summary")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def summary():
    return sync_controller.summary()


@crm_sync_bp.get("/events")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_events():
    return sync_controller.list_events()


@crm_sync_bp.get("/events/<int:crm_event_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_event(crm_event_id: int):
    return sync_controller.get_event(crm_event_id)


@crm_sync_bp.post("/events/<int:crm_event_id>/retry")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def retry_event(crm_event_id: int):
    return sync_controller.retry_event(crm_event_id)


@crm_sync_bp.get("/outbox")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def list_outbox():
    return sync_controller.list_outbox()


@crm_sync_bp.get("/outbox/<int:outbox_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_outbox(outbox_id: int):
    return sync_controller.get_outbox(outbox_id)

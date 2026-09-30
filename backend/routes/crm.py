from flask import Blueprint

from controllers import crm as crm_controller
from routes.decorators import login_required, require_roles, service_key_required

crm_bp = Blueprint("crm", __name__, url_prefix="/integrations/crm")


@crm_bp.post("/events")
@service_key_required
def receive_event():
    return crm_controller.receive_event()


@crm_bp.get("/events")
@login_required
@require_roles("SUPER_ADMIN")
def list_events():
    return crm_controller.list_events()


@crm_bp.post("/events/<int:crm_event_id>/retry")
@login_required
@require_roles("SUPER_ADMIN")
def retry_event(crm_event_id: int):
    return crm_controller.retry_event(crm_event_id)


@crm_bp.get("/status")
@service_key_required
def get_status():
    return crm_controller.get_status()

from flask import request

from controllers import crm as crm_controller
from controllers.common import Validator, get_page_params, ok, paginated
from models.enums import CRM_EVENT_STATUSES, OUTBOX_STATUSES
from services import crm_causes
from services import crm_sync as sync_service


def _event(event, include_payload: bool = False) -> dict:
    """The event as stored plus its plain-words label, summary and (for a failed one) cause."""
    return {**event.to_dict(include_payload=include_payload), **crm_causes.describe(event)}


def summary():
    return ok(sync_service.summary())


def list_events():
    v = Validator(request.args.to_dict())
    v.choice("status", CRM_EVENT_STATUSES)
    v.string("event_type", max_length=50)
    v.string("q", max_length=100)
    v.boolean("attention")
    v.date("from")
    v.date("to")
    filters = v.validate()

    page, per_page = get_page_params()
    events, meta = sync_service.list_events(filters, page, per_page)
    return paginated([_event(e) for e in events], meta)


def get_event(crm_event_id: int):
    return ok(_event(sync_service.get_event(crm_event_id), True))


def retry_event(crm_event_id: int):
    event = sync_service.get_event(crm_event_id)
    data = crm_controller.parse_data(event.event_type, event.payload)
    return ok(_event(sync_service.retry_event(event, data), True))


def list_outbox():
    v = Validator(request.args.to_dict())
    v.choice("status", OUTBOX_STATUSES)
    v.string("event_type", max_length=50)
    filters = v.validate()

    page, per_page = get_page_params()
    rows, meta = sync_service.list_outbox(filters, page, per_page)
    return paginated([r.to_dict() for r in rows], meta)


def get_outbox(outbox_id: int):
    return ok(sync_service.get_outbox(outbox_id).to_dict())

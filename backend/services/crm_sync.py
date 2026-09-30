"""CRM sync monitor: the inbox of events received from the CRM and the outbox of values queued for it.

Intake and retry rules live in services/crm.py; this module reads them for the Super Admin screen, adds the counts,
and audits a retry.
"""
from datetime import timedelta

from models import CrmEvent, CrmOutbox
from repositories import crm_sync as sync_repo
from repositories.common import paginate
from services import audit
from services import crm as crm_service
from services.audit_log import ist_day_start
from services.errors import NotFound


def summary() -> dict:
    events = sync_repo.event_counts()
    outbox = sync_repo.outbox_counts()
    return {
        "events": events,
        "outbox": outbox,
        "failed_events": events.get("Failed", 0),
        "pending_outbox": outbox.get("Pending", 0),
        "last_event_received_at": sync_repo.last_received_at(),
        "last_outbox_delivered_at": sync_repo.last_delivered_at(),
        "oldest_pending_outbox_at": sync_repo.oldest_pending_outbox_at(),
        "event_types": sync_repo.event_types(),
        "outbox_event_types": sync_repo.outbox_event_types(),
    }


def list_events(filters: dict, page: int, per_page: int):
    """Filters `from` / `to` are IST dates on the received time, both inclusive."""
    filters = dict(filters)
    if filters.get("from"):
        filters["received_from"] = ist_day_start(filters["from"])
    if filters.get("to"):
        filters["received_before"] = ist_day_start(filters["to"] + timedelta(days=1))
    return paginate(sync_repo.events_stmt(filters), page, per_page)


def get_event(crm_event_id: int) -> CrmEvent:
    return crm_service.get_event(crm_event_id)


def retry_event(event: CrmEvent, data: dict) -> CrmEvent:
    """Re-apply a failed event (audited when it succeeds; a failure stays on the event with its error)."""
    previous_error = event.error
    retried = crm_service.retry(event, data)
    audit.record("CRM_EVENT_RETRIED", "crm_event", event.crm_event_id,
                 old={"status": "Failed", "error": previous_error}, new={"status": retried.status, "retries": retried.retries})
    return retried


def list_outbox(filters: dict, page: int, per_page: int) -> tuple[list[CrmOutbox], dict]:
    return paginate(sync_repo.outbox_stmt(filters), page, per_page)


def get_outbox(outbox_id: int) -> CrmOutbox:
    row = sync_repo.get_outbox(outbox_id)
    if row is None:
        raise NotFound("Outbox entry not found")
    return row

"""CRM inbox (events received), outbox (values queued for the CRM) and the pull-status queries."""
from datetime import datetime

from sqlalchemy import Select, or_, select

from config.database import db
from models import AdmissionLmsState, Batch, CrmEvent, CrmOutbox, Student


def get_event_by_event_id(event_id: str) -> CrmEvent | None:
    return db.session.execute(select(CrmEvent).where(CrmEvent.event_id == event_id)).scalar_one_or_none()


def get_event(crm_event_id: int) -> CrmEvent | None:
    return db.session.get(CrmEvent, crm_event_id)


def events_stmt(filters: dict) -> Select:
    stmt = select(CrmEvent).order_by(CrmEvent.crm_event_id.desc())
    if filters.get("status"):
        stmt = stmt.where(CrmEvent.status == filters["status"])
    if filters.get("event_type"):
        stmt = stmt.where(CrmEvent.event_type == filters["event_type"])
    return stmt


def list_outbox(status: str | None, limit: int) -> list[CrmOutbox]:
    stmt = select(CrmOutbox).order_by(CrmOutbox.outbox_id.desc()).limit(limit)
    if status:
        stmt = stmt.where(CrmOutbox.status == status)
    return list(db.session.execute(stmt).scalars())


def students_provisioned_since(since: datetime) -> list[Student]:
    stmt = select(Student).where(Student.provisioned_at > since).order_by(Student.provisioned_at, Student.student_id)
    return list(db.session.execute(stmt).scalars())


def admission_states_changed_since(since: datetime) -> list[AdmissionLmsState]:
    """Admissions whose LMS status changed, or that saw new learning activity, after `since`."""
    stmt = (
        select(AdmissionLmsState)
        .where(or_(AdmissionLmsState.status_changed_at > since, AdmissionLmsState.last_activity_at > since))
        .order_by(AdmissionLmsState.admission_id)
    )
    return list(db.session.execute(stmt).scalars())


def batches_linked_since(since: datetime) -> list[Batch]:
    stmt = select(Batch).where(Batch.crm_linked_at > since).order_by(Batch.crm_linked_at, Batch.batch_id)
    return list(db.session.execute(stmt).scalars())

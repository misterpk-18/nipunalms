"""CRM inbox (events received), outbox (values queued for the CRM) and the pull-status queries.

The pull leaves out rows marked seed_data (the dev seed's made-up CRM IDs, db 090): the CRM knows none of them."""
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import Admission, AdmissionLmsState, Batch, BatchCrmState, Certificate, CrmEvent, CrmOutbox, Enrolment, Student


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
    stmt = select(Student).where(Student.provisioned_at > since, Student.seed_data.is_(False)).order_by(Student.provisioned_at, Student.student_id)
    return list(db.session.execute(stmt).scalars())


def pull_as_of() -> datetime:
    """The next `since`: just below the oldest transaction still open, so nothing it commits is skipped (db 095)."""
    return db.session.execute(select(func.crm_pull_as_of())).scalar_one()


def admission_states_changed_since(since: datetime) -> list[AdmissionLmsState]:
    """Admissions whose LMS status or last learning activity changed after `since`."""
    stmt = (
        select(AdmissionLmsState)
        .join(Admission, Admission.admission_id == AdmissionLmsState.admission_id)
        .where(AdmissionLmsState.changed_at > since, Admission.seed_data.is_(False))
        .order_by(AdmissionLmsState.changed_at, AdmissionLmsState.admission_id)
    )
    return list(db.session.execute(stmt).scalars())


def academics_changed_since(since: datetime) -> list[AdmissionLmsState]:
    """Admissions whose academic state (as the CRM stores it) changed after `since`."""
    stmt = (
        select(AdmissionLmsState)
        .join(Admission, Admission.admission_id == AdmissionLmsState.admission_id)
        .where(AdmissionLmsState.academic_changed_at > since, Admission.seed_data.is_(False))
        .order_by(AdmissionLmsState.academic_changed_at, AdmissionLmsState.admission_id)
    )
    return list(db.session.execute(stmt).scalars())


def batch_states_changed_since(since: datetime) -> list[BatchCrmState]:
    """Batches whose CRM-facing state (incl. a new CRM link) changed after `since`."""
    stmt = (
        select(BatchCrmState)
        .join(Batch, Batch.batch_id == BatchCrmState.batch_id)
        .where(BatchCrmState.changed_at > since, Batch.seed_data.is_(False))
        .order_by(BatchCrmState.changed_at, BatchCrmState.batch_id)
    )
    return list(db.session.execute(stmt).scalars())


def certificate_states_changed_since(since: datetime) -> list[dict]:
    """Numbered certificate versions (Issued / Superseded / Revoked) changed after `since`, as the CRM mirrors them."""
    stmt = (
        select(func.certificate_crm_state(Certificate.certificate_id))
        .join(Enrolment, Enrolment.enrolment_id == Certificate.enrolment_id)
        .join(Admission, Admission.admission_id == Enrolment.admission_id)
        .where(Certificate.certificate_number.is_not(None), Certificate.updated_at > since, Admission.seed_data.is_(False))
        .order_by(Certificate.updated_at, Certificate.certificate_id)
    )
    return list(db.session.execute(stmt).scalars())


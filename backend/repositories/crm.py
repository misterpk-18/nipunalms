"""CRM inbox (events received), outbox (values queued for the CRM) and the pull-status queries.

The pull leaves out rows marked seed_data (the dev seed's made-up CRM IDs, db 090): the CRM knows none of them. The
curriculum catalogue is not student data and is pulled whole. Every pull query takes an optional PullScope: the
records of one CRM admission or person (?crm_admission_id= / ?crm_person_id=)."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import (
    Admission, AdmissionLmsState, Batch, BatchAllocation, BatchCrmState, Certificate, Course, CrmEvent, CrmOutbox,
    CurriculumVersionCrmState, Enrolment, Student,
)


@dataclass(frozen=True)
class PullScope:
    """What one admission's (or person's) refresh covers: its person, admissions, the batches its allocations name and
    its courses' curriculum versions."""

    student_ids: frozenset[int]
    admission_ids: frozenset[int]
    batch_ids: frozenset[int]
    course_codes: frozenset[str]


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


def pull_scope(crm_admission_id: str | None, crm_person_id: str | None) -> PullScope:
    """The scope of a filtered pull. Seed rows stay out, so a seed admission's scope is empty."""
    stmt = select(Admission.admission_id, Admission.student_id, Course.course_code).join(
        Course, Course.course_id == Admission.course_id).join(Student, Student.student_id == Admission.student_id).where(
        Admission.seed_data.is_(False))
    if crm_admission_id is not None:
        stmt = stmt.where(Admission.crm_admission_id == crm_admission_id)
    if crm_person_id is not None:
        stmt = stmt.where(Student.crm_person_id == crm_person_id)
    rows = db.session.execute(stmt).all()
    admission_ids = frozenset(r.admission_id for r in rows)
    batch_ids = frozenset(db.session.execute(
        select(BatchAllocation.batch_id).join(Enrolment, Enrolment.enrolment_id == BatchAllocation.enrolment_id)
        .where(Enrolment.admission_id.in_(admission_ids))).scalars()) if admission_ids else frozenset()
    return PullScope(student_ids=frozenset(r.student_id for r in rows), admission_ids=admission_ids, batch_ids=batch_ids,
                     course_codes=frozenset(r.course_code for r in rows))


def pull_as_of() -> datetime:
    """The next `since`: just below the oldest transaction still open, so nothing it commits is skipped (db 095)."""
    return db.session.execute(select(func.crm_pull_as_of())).scalar_one()


def students_provisioned_since(since: datetime, scope: PullScope | None = None) -> list[Student]:
    stmt = select(Student).where(Student.provisioned_at > since, Student.seed_data.is_(False))
    if scope is not None:
        stmt = stmt.where(Student.student_id.in_(scope.student_ids))
    return list(db.session.execute(stmt.order_by(Student.provisioned_at, Student.student_id)).scalars())


def _admission_states(since_column, since: datetime, scope: PullScope | None) -> list[AdmissionLmsState]:
    stmt = (
        select(AdmissionLmsState)
        .join(Admission, Admission.admission_id == AdmissionLmsState.admission_id)
        .where(since_column > since, Admission.seed_data.is_(False))
        .order_by(since_column, AdmissionLmsState.admission_id)
    )
    if scope is not None:
        stmt = stmt.where(AdmissionLmsState.admission_id.in_(scope.admission_ids))
    return list(db.session.execute(stmt).scalars())


def admission_states_changed_since(since: datetime, scope: PullScope | None = None) -> list[AdmissionLmsState]:
    """Admissions whose LMS status or last learning activity changed after `since`."""
    return _admission_states(AdmissionLmsState.changed_at, since, scope)


def academics_changed_since(since: datetime, scope: PullScope | None = None) -> list[AdmissionLmsState]:
    """Admissions whose academic state (as the CRM stores it) changed after `since`."""
    return _admission_states(AdmissionLmsState.academic_changed_at, since, scope)


def batch_states_changed_since(since: datetime, scope: PullScope | None = None) -> list[BatchCrmState]:
    """Batches whose CRM-facing state (incl. a new CRM link) changed after `since`."""
    stmt = (
        select(BatchCrmState)
        .join(Batch, Batch.batch_id == BatchCrmState.batch_id)
        .where(BatchCrmState.changed_at > since, Batch.seed_data.is_(False))
        .order_by(BatchCrmState.changed_at, BatchCrmState.batch_id)
    )
    if scope is not None:
        stmt = stmt.where(BatchCrmState.batch_id.in_(scope.batch_ids))
    return list(db.session.execute(stmt).scalars())


def certificate_states_changed_since(since: datetime, scope: PullScope | None = None) -> list[dict]:
    """Numbered certificate versions (Issued / Superseded / Revoked) changed after `since`, as the CRM mirrors them."""
    stmt = (
        select(func.certificate_crm_state(Certificate.certificate_id))
        .join(Enrolment, Enrolment.enrolment_id == Certificate.enrolment_id)
        .join(Admission, Admission.admission_id == Enrolment.admission_id)
        .where(Certificate.certificate_number.is_not(None), Certificate.updated_at > since, Admission.seed_data.is_(False))
        .order_by(Certificate.updated_at, Certificate.certificate_id)
    )
    if scope is not None:
        stmt = stmt.where(Admission.admission_id.in_(scope.admission_ids))
    return list(db.session.execute(stmt).scalars())


def curriculum_versions_changed_since(since: datetime, scope: PullScope | None = None) -> list[dict]:
    """Every curriculum version changed after `since` (seed curricula included; a deleted Draft as a Retired tombstone)."""
    stmt = (
        select(CurriculumVersionCrmState.payload)
        .where(CurriculumVersionCrmState.changed_at > since)
        .order_by(CurriculumVersionCrmState.changed_at, CurriculumVersionCrmState.curriculum_version_id)
    )
    if scope is not None:
        stmt = stmt.where(CurriculumVersionCrmState.payload["course_code"].astext.in_(scope.course_codes))
    return list(db.session.execute(stmt).scalars())

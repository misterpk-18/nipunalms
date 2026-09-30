"""Counts for the dashboards. Each function reads another slice's own tables and applies only the branch filter:
which statuses count as "awaiting" is the status the owning slice already stores, never a rule of the dashboard.
"""
from datetime import datetime

from sqlalchemy import Select, func, select

from config.database import db
from models import (
    AccessExtensionRequest, Batch, Certificate, CompletionReview, ContentItem, Enrolment, FinanceSummary, Integration,
    RecordingException, Result, SessionChangeRequest, SupportRequest,
)
from models.batches import ClassSession

OPEN_BATCH_STATES = ("Forming", "Starting", "Running", "Full")
SUPPORT_OPEN = ("Open", "In Progress", "Waiting on Student")


def _branch(stmt: Select, column, branch_ids: set[int] | None) -> Select:
    return stmt if branch_ids is None else stmt.where(column.in_(branch_ids))


def _count(stmt: Select) -> int:
    return db.session.execute(stmt).scalar_one()


def enrolment_counts(branch_ids: set[int] | None) -> dict[str, int]:
    """Enrolments per status."""
    stmt = _branch(select(Enrolment.status, func.count()).group_by(Enrolment.status), Enrolment.service_branch_id, branch_ids)
    return {status: n for status, n in db.session.execute(stmt).all()}


def active_enrolments_by_branch() -> dict[int, int]:
    stmt = select(Enrolment.service_branch_id, func.count()).where(Enrolment.status == "Active").group_by(Enrolment.service_branch_id)
    return dict(db.session.execute(stmt).all())


def results_awaiting_publication(branch_ids: set[int] | None) -> int:
    stmt = select(func.count()).select_from(Result).join(Batch, Batch.batch_id == Result.batch_id).where(Result.status.in_(("Provisional", "Moderated")))
    return _count(_branch(stmt, Batch.branch_id, branch_ids))


def unresolved_recording_exceptions(branch_ids: set[int] | None) -> int:
    stmt = select(func.count()).select_from(RecordingException).where(RecordingException.status != "Resolved")
    return _count(_branch(stmt, RecordingException.branch_id, branch_ids))


def open_batches(branch_ids: set[int] | None) -> list[Batch]:
    """Batches that have not finished (Forming, Starting, Running, Full)."""
    stmt = select(Batch).where(Batch.state.in_(OPEN_BATCH_STATES)).order_by(Batch.batch_id)
    return list(db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).scalars().unique())


def content_awaiting_review(branch_ids: set[int] | None) -> int:
    stmt = select(func.count()).select_from(ContentItem).where(ContentItem.status.in_(("Submitted", "Under Review")))
    return _count(_branch(stmt, ContentItem.branch_id, branch_ids))


def open_completion_reviews(branch_ids: set[int] | None) -> int:
    stmt = (select(func.count()).select_from(CompletionReview).join(Enrolment, Enrolment.enrolment_id == CompletionReview.enrolment_id)
            .where(CompletionReview.status == "Open"))
    return _count(_branch(stmt, Enrolment.service_branch_id, branch_ids))


def certificates_in_status(statuses: tuple[str, ...], branch_ids: set[int] | None) -> dict[int, int]:
    """Certificate register entries in these statuses, per branch."""
    stmt = select(Certificate.branch_id, func.count()).where(Certificate.status.in_(statuses)).group_by(Certificate.branch_id)
    return dict(db.session.execute(_branch(stmt, Certificate.branch_id, branch_ids)).all())


def open_reschedule_requests(branch_ids: set[int] | None) -> int:
    stmt = (select(func.count()).select_from(SessionChangeRequest).join(ClassSession, ClassSession.session_id == SessionChangeRequest.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(SessionChangeRequest.status == "Open"))
    return _count(_branch(stmt, Batch.branch_id, branch_ids))


def escalated_support_requests(branch_ids: set[int] | None) -> int:
    stmt = select(func.count()).select_from(SupportRequest).where(SupportRequest.status.in_(SUPPORT_OPEN), SupportRequest.escalation_level.is_not(None))
    return _count(_branch(stmt, SupportRequest.branch_id, branch_ids))


def pending_extension_requests(branch_ids: set[int] | None) -> int:
    stmt = select(func.count()).select_from(AccessExtensionRequest).where(AccessExtensionRequest.status == "Pending")
    return _count(_branch(stmt, AccessExtensionRequest.branch_id, branch_ids))


def integration_counts() -> dict:
    """Integrations register: total, verified, and the ones that failed verification or are misconfigured."""
    rows = db.session.execute(select(Integration)).scalars().all()
    failing = [i for i in rows if i.verification_status == "Failed" or i.configuration_status == "Misconfigured"]
    return {"total": len(rows), "verified": sum(1 for i in rows if i.verification_status == "Verified"),
            "failing": [i.integration_code for i in failing]}


def latest_finance_refresh() -> datetime | None:
    """When the CRM last sent a finance summary (the freshness of everything the LMS shows about money)."""
    return db.session.execute(select(func.max(FinanceSummary.as_of))).scalar()


def pending_exception_requests() -> list[dict]:
    """Recording-access requests made after the second anniversary that wait for a Founder / Super Admin decision."""
    stmt = (select(AccessExtensionRequest).where(AccessExtensionRequest.status == "Pending", AccessExtensionRequest.needs_exception)
            .order_by(AccessExtensionRequest.requested_at))
    return [{"request_id": r.request_id, "request_code": r.request_code, "student_name": r.student.full_name, "scope": r.scope,
             "branch_id": r.branch_id, "requested_at": r.requested_at} for r in db.session.execute(stmt).scalars().unique()]

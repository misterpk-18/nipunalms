"""Counts behind the Branch Manager's Reports (UX phase U15). Queries only; callers pass the branches and the period [start, end)."""
from datetime import date, datetime

from sqlalchemy import func, select

from config.database import db
from models import (
    AttendanceRecord, AttendanceRecovery, Batch, Certificate, ClassSession, CompletionReview, ContentVersion, ContentItem, Enrolment, Result,
    SupportRequest,
)


def _branch(stmt, column, branch_ids: set[int] | None):
    return stmt if branch_ids is None else stmt.where(column.in_(branch_ids))


def classes_by_state(branch_ids, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (select(ClassSession.state, func.count()).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.starts_at >= start, ClassSession.starts_at < end).group_by(ClassSession.state))
    return {str(state): n for state, n in db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).all()}


def attendance_marks(branch_ids, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (select(AttendanceRecord.status, func.count()).join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(ClassSession.starts_at >= start, ClassSession.starts_at < end)
            .group_by(AttendanceRecord.status))
    return {str(status): n for status, n in db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).all()}


def recoveries_by_status(branch_ids, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (select(AttendanceRecovery.status, func.count()).join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
            .join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(AttendanceRecovery.requested_at >= start, AttendanceRecovery.requested_at < end).group_by(AttendanceRecovery.status))
    return {str(status): n for status, n in db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).all()}


def decisions_by_outcome(branch_ids, start: datetime, end: datetime) -> dict[str, int]:
    stmt = (select(CompletionReview.decision, func.count()).join(Enrolment, Enrolment.enrolment_id == CompletionReview.enrolment_id)
            .where(CompletionReview.status == "Decided", CompletionReview.decided_at >= start, CompletionReview.decided_at < end)
            .group_by(CompletionReview.decision))
    return {str(d): n for d, n in db.session.execute(_branch(stmt, Enrolment.service_branch_id, branch_ids)).all()}


def certificates_issued(branch_ids, start_day: date, end_day: date) -> int:
    stmt = select(func.count()).select_from(Certificate).where(Certificate.status.in_(("Issued", "Superseded", "Revoked")), Certificate.version == 1,
                                                               Certificate.issue_date >= start_day, Certificate.issue_date < end_day)
    return db.session.execute(_branch(stmt, Certificate.branch_id, branch_ids)).scalar_one()


def issued_list(branch_ids, start_day: date, end_day: date) -> list[Certificate]:
    stmt = (select(Certificate).where(Certificate.status == "Issued", Certificate.issue_date >= start_day, Certificate.issue_date < end_day)
            .order_by(Certificate.issue_date, Certificate.certificate_id))
    return list(db.session.execute(_branch(stmt, Certificate.branch_id, branch_ids)).scalars().unique())


def results_published(branch_ids, start: datetime, end: datetime) -> int:
    stmt = (select(func.count()).select_from(Result).join(Batch, Batch.batch_id == Result.batch_id)
            .where(Result.published_at >= start, Result.published_at < end))
    return db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).scalar_one()


def support_figures(branch_ids, start: datetime, end: datetime, now: datetime) -> dict[str, int]:
    def count(*where):
        return db.session.execute(_branch(select(func.count()).select_from(SupportRequest).where(*where), SupportRequest.branch_id, branch_ids)).scalar_one()
    return {
        "opened": count(SupportRequest.created_at >= start, SupportRequest.created_at < end),
        "resolved": count(SupportRequest.resolved_at >= start, SupportRequest.resolved_at < end),
        "overdue_now": count(SupportRequest.status.in_(("Open", "In Progress")), SupportRequest.sla_due_at < now),
    }


def content_released(branch_ids, start: datetime, end: datetime) -> int:
    stmt = (select(func.count()).select_from(ContentVersion).join(ContentItem, ContentItem.content_item_id == ContentVersion.content_item_id)
            .where(ContentVersion.released_at >= start, ContentVersion.released_at < end))
    return db.session.execute(_branch(stmt, ContentItem.branch_id, branch_ids)).scalar_one()

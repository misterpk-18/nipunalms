"""Aggregate reads for the trainer Today screen and the trainer / academic reports. Queries only; scope is applied by callers."""
from datetime import date, datetime

from sqlalchemy import func, select

from config.database import db
from models import (
    Assignment, AssignmentSubmission, AttendanceRecord, AttendanceRecovery, Batch, Certificate, ClassSession, CompletionReview,
    Enrolment, SubmissionReview,
)

OPEN_SESSION_STATES = ("Scheduled", "Rescheduled", "Live")


def sessions_of_trainer(trainer_user_id: int, starts_from: datetime, starts_before: datetime, *, states: tuple[str, ...] | None = None) -> list[ClassSession]:
    """Sessions this user teaches that start in [starts_from, starts_before), in time order (optionally only some states)."""
    stmt = (
        select(ClassSession)
        .where(ClassSession.trainer_user_id == trainer_user_id, ClassSession.starts_at >= starts_from, ClassSession.starts_at < starts_before)
        .order_by(ClassSession.starts_at, ClassSession.session_id)
    )
    if states:
        stmt = stmt.where(ClassSession.state.in_(states))
    return list(db.session.execute(stmt).scalars().unique())


def review_timings(*, reviewer_user_id: int | None = None, batch_ids: set[int] | None = None) -> list[tuple[datetime | None, datetime | None]]:
    """(submitted_at, reviewed_at) for every reviewed submission of the assignments this reviewer owns / of these batches."""
    stmt = (
        select(AssignmentSubmission.submitted_at, SubmissionReview.reviewed_at)
        .join(SubmissionReview, SubmissionReview.submission_id == AssignmentSubmission.submission_id)
        .join(Assignment, Assignment.assignment_id == AssignmentSubmission.assignment_id)
    )
    if reviewer_user_id is not None:
        stmt = stmt.where(Assignment.reviewer_user_id == reviewer_user_id)
    if batch_ids is not None:
        stmt = stmt.where(Assignment.batch_id.in_(batch_ids))
    return [(submitted, reviewed) for submitted, reviewed in db.session.execute(stmt).all()]


def recovery_counts(branch_ids: set[int] | None) -> dict[int, dict[str, int]]:
    """branch id -> recovery status -> count, by the branch of the batch the missed class belongs to."""
    stmt = (
        select(Batch.branch_id, AttendanceRecovery.status, func.count())
        .join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
        .join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id)
        .join(Batch, Batch.batch_id == ClassSession.batch_id)
        .group_by(Batch.branch_id, AttendanceRecovery.status)
    )
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids))
    counts: dict[int, dict[str, int]] = {}
    for branch_id, status, n in db.session.execute(stmt).all():
        counts.setdefault(branch_id, {})[str(status)] = n
    return counts


def completion_review_counts(branch_ids: set[int] | None) -> dict[int, dict[str, int]]:
    """branch id -> {Open, Decided, completed_without_review}: reviews by the enrolment's service branch, plus Completed
    enrolments that have no review record at all (the gap that makes the figure Partial Data)."""
    stmt = (
        select(Enrolment.service_branch_id, CompletionReview.status, func.count())
        .join(Enrolment, Enrolment.enrolment_id == CompletionReview.enrolment_id)
        .group_by(Enrolment.service_branch_id, CompletionReview.status)
    )
    if branch_ids is not None:
        stmt = stmt.where(Enrolment.service_branch_id.in_(branch_ids))
    counts: dict[int, dict[str, int]] = {}
    for branch_id, status, n in db.session.execute(stmt).all():
        counts.setdefault(branch_id, {})[str(status)] = n

    missing = (
        select(Enrolment.service_branch_id, func.count())
        .where(Enrolment.status == "Completed", ~select(CompletionReview.review_id).where(CompletionReview.enrolment_id == Enrolment.enrolment_id).exists())
        .group_by(Enrolment.service_branch_id)
    )
    if branch_ids is not None:
        missing = missing.where(Enrolment.service_branch_id.in_(branch_ids))
    for branch_id, n in db.session.execute(missing).all():
        counts.setdefault(branch_id, {})["completed_without_review"] = n
    return counts


def certificate_lead_times(branch_ids: set[int] | None) -> list[tuple[int, datetime, date]]:
    """(branch id, completion decision time, issue date) for issued certificates that trace back to a decided completion review."""
    stmt = (
        select(Certificate.branch_id, CompletionReview.decided_at, Certificate.issue_date)
        .join(CompletionReview, CompletionReview.review_id == Certificate.completion_review_id)
        .where(Certificate.status == "Issued", Certificate.issue_date.is_not(None), CompletionReview.decided_at.is_not(None))
    )
    if branch_ids is not None:
        stmt = stmt.where(Certificate.branch_id.in_(branch_ids))
    return [(branch_id, decided, issued) for branch_id, decided, issued in db.session.execute(stmt).all()]

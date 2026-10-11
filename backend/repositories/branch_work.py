"""Reads behind the Branch Manager's "My work" list, Class day and the Schedule "Needs decision" strip (UX phase U14). Each
function reads another slice's own tables and applies only the branch filter; what counts as waiting is what the owning
slice already stores."""
from datetime import datetime

from sqlalchemy import Select, exists, func, select

from config.database import db
from models import (
    AttendanceCorrection, AttendanceRecord, AttendanceRecovery, Batch, ClassSession, ContentItem, Enrolment, Result, SessionChangeRequest,
    SessionDisruption, SupportRequest,
)

OPEN_SESSION_STATES = ("Scheduled", "Rescheduled", "Live")


def _branch(stmt: Select, column, branch_ids: set[int] | None) -> Select:
    return stmt if branch_ids is None else stmt.where(column.in_(branch_ids))


def _row(stmt: Select):
    return db.session.execute(stmt).one()


def waiting_enrolments(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    """Enrolments waiting for a batch and when the longest-waiting one started to wait."""
    stmt = select(func.count(), func.min(Enrolment.updated_at)).where(Enrolment.status == "Allocation Pending")
    count, oldest = _row(_branch(stmt, Enrolment.service_branch_id, branch_ids))
    return count, oldest


def open_reschedule_requests(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    stmt = (select(func.count(), func.min(SessionChangeRequest.created_at)).select_from(SessionChangeRequest)
            .join(ClassSession, ClassSession.session_id == SessionChangeRequest.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(SessionChangeRequest.status == "Open"))
    count, oldest = _row(_branch(stmt, Batch.branch_id, branch_ids))
    return count, oldest


def classes_awaiting_approval(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    """Replacement, remedial and extra classes proposed and not yet approved."""
    stmt = (select(func.count(), func.min(ClassSession.created_at)).select_from(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.approval_status == "Pending", ClassSession.state.in_(("Scheduled", "Rescheduled"))))
    count, oldest = _row(_branch(stmt, Batch.branch_id, branch_ids))
    return count, oldest


def results_to_publish(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    stmt = (select(func.count(), func.min(Result.created_at)).select_from(Result).join(Batch, Batch.batch_id == Result.batch_id)
            .where(Result.status.in_(("Provisional", "Moderated"))))
    count, oldest = _row(_branch(stmt, Batch.branch_id, branch_ids))
    return count, oldest


def content_to_review(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    stmt = select(func.count(), func.min(ContentItem.updated_at)).where(ContentItem.status.in_(("Submitted", "Under Review")))
    count, oldest = _row(_branch(stmt, ContentItem.branch_id, branch_ids))
    return count, oldest


def recovery_requests(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    stmt = (select(func.count(), func.min(AttendanceRecovery.requested_at)).select_from(AttendanceRecovery)
            .join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
            .join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(AttendanceRecovery.status == "Requested"))
    count, oldest = _row(_branch(stmt, Batch.branch_id, branch_ids))
    return count, oldest


def correction_requests(branch_ids: set[int] | None) -> tuple[int, datetime | None]:
    stmt = (select(func.count(), func.min(AttendanceCorrection.requested_at)).select_from(AttendanceCorrection)
            .join(ClassSession, ClassSession.session_id == AttendanceCorrection.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(AttendanceCorrection.status == "Pending"))
    count, oldest = _row(_branch(stmt, Batch.branch_id, branch_ids))
    return count, oldest


def support_due(branch_ids: set[int] | None, due_by: datetime) -> tuple[int, datetime | None]:
    """Open requests whose reply deadline has passed or falls before `due_by`, and the earliest deadline."""
    stmt = select(func.count(), func.min(SupportRequest.sla_due_at)).where(SupportRequest.status.in_(("Open", "In Progress")),
                                                                         SupportRequest.sla_due_at <= due_by)
    count, oldest = _row(_branch(stmt, SupportRequest.branch_id, branch_ids))
    return count, oldest


def classes_at_risk(branch_ids: set[int] | None, day_start: datetime, day_end: datetime) -> list[ClassSession]:
    """Classes of the day that are still to run (or running) and have a problem now: an online class with no working link, a
    delay noticed, or a disruption still open."""
    disrupted = exists().where(SessionDisruption.session_id == ClassSession.session_id, SessionDisruption.status == "Open")
    stmt = (select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(ClassSession.starts_at >= day_start, ClassSession.starts_at < day_end, ClassSession.state.in_(OPEN_SESSION_STATES),
                   ((ClassSession.mode != "Classroom") & (ClassSession.meet_status != "Linked")) | ClassSession.delay_notice_at.is_not(None) | disrupted)
            .order_by(ClassSession.starts_at, ClassSession.session_id))
    return list(db.session.execute(_branch(stmt, Batch.branch_id, branch_ids)).scalars().unique())

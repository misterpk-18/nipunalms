"""Counts behind the navigation badges and the "Getting started" steps. Cheap reads of other slices' own tables: a badge says
how many items wait for the person, so each count uses the status the owning slice already stores."""
from datetime import datetime

from sqlalchemy import Select, exists, func, select

from config.database import db
from models import (
    AssignmentSubmission, AttendanceCorrection, AttendanceRecord, AttendanceRecovery, AuditLog, Batch, BatchAllocation, ClassSession,
    CurriculumVersion, Enrolment, Integration, SubmissionReview, SupportRequest, User,
)

SUPPORT_OPEN = ("Open", "In Progress", "Waiting on Student")


def _count(stmt: Select) -> int:
    return db.session.execute(stmt).scalar_one()


def _branch(stmt: Select, column, branch_ids: set[int] | None) -> Select:
    return stmt if branch_ids is None else stmt.where(column.in_(branch_ids))


# ---------------------------------------------------------------- badges

def support_waiting_on_student(student_id: int) -> int:
    return _count(select(func.count()).select_from(SupportRequest).where(SupportRequest.student_id == student_id,
                                                                         SupportRequest.status == "Waiting on Student"))


def support_open_for_owner(user_id: int) -> int:
    return _count(select(func.count()).select_from(SupportRequest).where(SupportRequest.owner_user_id == user_id,
                                                                         SupportRequest.status.in_(("Open", "In Progress"))))


def support_due_by(branch_ids: set[int] | None, due_by: datetime) -> int:
    """Open requests whose reply deadline has passed or falls before `due_by`."""
    stmt = select(func.count()).select_from(SupportRequest).where(SupportRequest.status.in_(("Open", "In Progress")), SupportRequest.sla_due_at <= due_by)
    return _count(_branch(stmt, SupportRequest.branch_id, branch_ids))


def support_needing_attention(branch_ids: set[int] | None, due_by: datetime) -> int:
    """Open requests near or past their reply deadline, or where the student wrote last (the Student support badge)."""
    from repositories import support as support_repo
    return support_repo.needing_attention(branch_ids, due_by)


def pending_recoveries(branch_ids: set[int] | None) -> int:
    stmt = (select(func.count()).select_from(AttendanceRecovery).join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
            .join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id).join(Batch, Batch.batch_id == ClassSession.batch_id)
            .where(AttendanceRecovery.status == "Requested"))
    return _count(_branch(stmt, Batch.branch_id, branch_ids))


def pending_corrections(branch_ids: set[int] | None) -> int:
    stmt = (select(func.count()).select_from(AttendanceCorrection).join(ClassSession, ClassSession.session_id == AttendanceCorrection.session_id)
            .join(Batch, Batch.batch_id == ClassSession.batch_id).where(AttendanceCorrection.status == "Pending"))
    return _count(_branch(stmt, Batch.branch_id, branch_ids))


def curriculum_awaiting_approval() -> int:
    return _count(select(func.count()).select_from(CurriculumVersion).where(CurriculumVersion.status == "Under Review"))


def locked_users(now: datetime) -> int:
    return _count(select(func.count()).select_from(User).where(User.is_active, User.locked_until > now))


# ---------------------------------------------------------------- getting started

def student_has_batch(student_id: int) -> bool:
    return db.session.execute(select(exists().where(Enrolment.student_id == student_id, BatchAllocation.enrolment_id == Enrolment.enrolment_id,
                                                    BatchAllocation.status == "Active"))).scalar_one()


def student_joined_a_class(student_id: int) -> bool:
    return db.session.execute(select(exists().where(Enrolment.student_id == student_id, AttendanceRecord.enrolment_id == Enrolment.enrolment_id,
                                                    AttendanceRecord.status.in_(("Present", "Late"))))).scalar_one()


def student_submitted_a_task(student_id: int) -> bool:
    return db.session.execute(select(exists().where(AssignmentSubmission.student_id == student_id))).scalar_one()


def trainer_opened_a_class(user_id: int) -> bool:
    return db.session.execute(select(exists().where(ClassSession.trainer_user_id == user_id, ClassSession.state.in_(("Live", "Delivered"))))).scalar_one()


def trainer_marked_attendance(user_id: int) -> bool:
    return db.session.execute(select(exists().where(AttendanceRecord.marked_by == user_id))).scalar_one()


def trainer_graded_a_submission(user_id: int) -> bool:
    return db.session.execute(select(exists().where(SubmissionReview.reviewer_user_id == user_id))).scalar_one()


def branch_has_batches(branch_ids: set[int] | None) -> bool:
    return _count(_branch(select(func.count()).select_from(Batch), Batch.branch_id, branch_ids)) > 0


def branch_has_allocations(branch_ids: set[int] | None) -> bool:
    stmt = select(func.count()).select_from(BatchAllocation).join(Batch, Batch.batch_id == BatchAllocation.batch_id).where(BatchAllocation.status == "Active")
    return _count(_branch(stmt, Batch.branch_id, branch_ids)) > 0


def branch_has_classes(branch_ids: set[int] | None) -> bool:
    stmt = select(func.count()).select_from(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
    return _count(_branch(stmt, Batch.branch_id, branch_ids)) > 0


def user_added_staff(user_id: int) -> bool:
    return db.session.execute(select(exists().where(AuditLog.actor_user_id == user_id, AuditLog.action == "USER_CREATED"))).scalar_one()


def setup_reviewed() -> bool:
    """Someone has started on the integrations register: at least one integration is no longer 'Not Configured'."""
    return db.session.execute(select(exists().where(Integration.configuration_status != "Not Configured"))).scalar_one()

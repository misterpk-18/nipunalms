"""Attendance records, recoveries and corrections: queries only."""
from datetime import date, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select

from config.database import db
from config.timezone import IST
from repositories import class_sessions as class_sessions_repo
from models import (
    AttendanceCorrection, AttendanceRecord, AttendanceRecovery, Batch, BatchAllocation, ClassSession, Enrolment, Student,
)


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=IST)


# ---------------------------------------------------------------- sessions and their registers

get_session = class_sessions_repo.get_session  # one implementation, in the delivery repository


def allocated_enrolments(batch_id: int) -> list[Enrolment]:
    """Enrolments holding a seat in the batch now, in student-name order (the register's rows)."""
    stmt = (
        select(Enrolment)
        .join(BatchAllocation, BatchAllocation.enrolment_id == Enrolment.enrolment_id)
        .join(Student, Student.student_id == Enrolment.student_id)
        .where(BatchAllocation.batch_id == batch_id, BatchAllocation.status == "Active")
        .order_by(Student.full_name, Enrolment.enrolment_id)
    )
    return list(db.session.execute(stmt).unique().scalars())


def has_seat_history(enrolment_id: int, batch_id: int) -> bool:
    """The enrolment holds, or once held, a seat in the batch."""
    return db.session.execute(
        select(BatchAllocation.allocation_id).where(BatchAllocation.enrolment_id == enrolment_id, BatchAllocation.batch_id == batch_id).limit(1)
    ).first() is not None


def records_for_session(session_id: int) -> dict[int, AttendanceRecord]:
    stmt = select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    return {r.enrolment_id: r for r in db.session.execute(stmt).unique().scalars()}


def get_record(attendance_id: int) -> AttendanceRecord | None:
    return db.session.get(AttendanceRecord, attendance_id)


def find_record(session_id: int, enrolment_id: int) -> AttendanceRecord | None:
    return db.session.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id, AttendanceRecord.enrolment_id == enrolment_id)
    ).unique().scalar_one_or_none()


def register_sessions_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int], now: datetime, lock_days: int) -> Select:
    """Live / Delivered sessions of the visible batches with how many seats are marked, newest first.

    Columns: ClassSession, allocated seats, marked seats (marked among the seats held now).
    """
    allocated = (
        select(func.count(func.distinct(BatchAllocation.enrolment_id)))
        .where(BatchAllocation.batch_id == ClassSession.batch_id, BatchAllocation.status == "Active")
        .correlate(ClassSession)
        .scalar_subquery()
    )
    marked = (
        select(func.count(AttendanceRecord.attendance_id))
        .join(BatchAllocation, and_(BatchAllocation.enrolment_id == AttendanceRecord.enrolment_id,
                                    BatchAllocation.batch_id == ClassSession.batch_id, BatchAllocation.status == "Active"))
        .where(AttendanceRecord.session_id == ClassSession.session_id)
        .correlate(ClassSession)
        .scalar_subquery()
    )
    stmt = (
        select(ClassSession, allocated.label("allocated"), marked.label("marked"))
        .join(Batch, Batch.batch_id == ClassSession.batch_id)
        .where(ClassSession.state.in_(("Live", "Delivered")))
        .order_by(ClassSession.starts_at.desc(), ClassSession.session_id.desc())
    )
    if branch_ids is not None:
        stmt = stmt.where(or_(Batch.branch_id.in_(branch_ids), Batch.batch_id.in_(batch_ids)))
    if filters.get("batch_id"):
        stmt = stmt.where(ClassSession.batch_id == filters["batch_id"])
    if filters.get("from"):
        stmt = stmt.where(ClassSession.starts_at >= _start_of_day(filters["from"]))
    if filters.get("to"):
        stmt = stmt.where(ClassSession.starts_at < _start_of_day(filters["to"] + timedelta(days=1)))
    lock_cutoff = now - timedelta(days=lock_days)
    match filters.get("attendance"):
        case "pending":
            stmt = stmt.where(marked < allocated, ClassSession.ends_at > lock_cutoff)
        case "marked":
            stmt = stmt.where(marked >= allocated, allocated > 0)
        case "locked":
            stmt = stmt.where(ClassSession.ends_at <= lock_cutoff)
    return stmt


# ---------------------------------------------------------------- a student's own view

def student_session_rows(enrolment_id: int, joining_date: date | None) -> list[tuple[ClassSession, AttendanceRecord | None]]:
    """Live / Delivered sessions of the enrolment's batches (since the joining date once there is one), newest first."""
    batch_ids = select(BatchAllocation.batch_id).where(BatchAllocation.enrolment_id == enrolment_id)
    stmt = (
        select(ClassSession, AttendanceRecord)
        .outerjoin(AttendanceRecord, and_(AttendanceRecord.session_id == ClassSession.session_id,
                                          AttendanceRecord.enrolment_id == enrolment_id))
        .where(ClassSession.batch_id.in_(batch_ids), ClassSession.state.in_(("Live", "Delivered")))
        .order_by(ClassSession.starts_at.desc(), ClassSession.session_id.desc())
    )
    if joining_date is not None:
        stmt = stmt.where(ClassSession.starts_at >= _start_of_day(joining_date))
    return [(s, r) for s, r in db.session.execute(stmt).unique().all()]


# ---------------------------------------------------------------- recoveries

def get_recovery(recovery_id: int) -> AttendanceRecovery | None:
    return db.session.get(AttendanceRecovery, recovery_id)


def live_recovery(attendance_id: int) -> AttendanceRecovery | None:
    """The absence's recovery that is Requested, Approved or Completed (a rejected one no longer counts)."""
    return db.session.execute(
        select(AttendanceRecovery).where(AttendanceRecovery.attendance_id == attendance_id,
                                         AttendanceRecovery.status.in_(("Requested", "Approved", "Completed")))
    ).unique().scalar_one_or_none()


def recoveries_by_attendance(attendance_ids: list[int]) -> dict[int, AttendanceRecovery]:
    if not attendance_ids:
        return {}
    stmt = select(AttendanceRecovery).where(AttendanceRecovery.attendance_id.in_(attendance_ids),
                                            AttendanceRecovery.status.in_(("Requested", "Approved", "Completed")))
    return {r.attendance_id: r for r in db.session.execute(stmt).unique().scalars()}


def open_recovery_count(enrolment_id: int) -> int:
    """Recoveries still to be finished (Requested or Approved) for the enrolment."""
    return db.session.execute(
        select(func.count()).select_from(AttendanceRecovery)
        .join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
        .where(AttendanceRecord.enrolment_id == enrolment_id, AttendanceRecovery.status.in_(("Requested", "Approved")))
    ).scalar_one()


def recoveries_stmt(filters: dict, scope_condition) -> Select:
    """Recoveries of enrolments matching scope_condition (an Enrolment-column expression), newest first."""
    stmt = (
        select(AttendanceRecovery)
        .join(AttendanceRecord, AttendanceRecord.attendance_id == AttendanceRecovery.attendance_id)
        .join(Enrolment, Enrolment.enrolment_id == AttendanceRecord.enrolment_id)
        .where(scope_condition)
        .order_by(AttendanceRecovery.recovery_id.desc())
    )
    if filters.get("status"):
        stmt = stmt.where(AttendanceRecovery.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.join(ClassSession, ClassSession.session_id == AttendanceRecord.session_id).where(
            ClassSession.batch_id == filters["batch_id"])
    if filters.get("enrolment_id"):
        stmt = stmt.where(AttendanceRecord.enrolment_id == filters["enrolment_id"])
    return stmt


# ---------------------------------------------------------------- corrections

def get_correction(correction_id: int) -> AttendanceCorrection | None:
    return db.session.get(AttendanceCorrection, correction_id)


def pending_correction(session_id: int, enrolment_id: int) -> AttendanceCorrection | None:
    return db.session.execute(
        select(AttendanceCorrection).where(AttendanceCorrection.session_id == session_id,
                                           AttendanceCorrection.enrolment_id == enrolment_id,
                                           AttendanceCorrection.status == "Pending")
    ).unique().scalar_one_or_none()


def pending_correction_keys(session_ids: list[int]) -> set[tuple[int, int]]:
    """(session_id, enrolment_id) pairs with a correction awaiting a decision."""
    if not session_ids:
        return set()
    stmt = select(AttendanceCorrection.session_id, AttendanceCorrection.enrolment_id).where(
        AttendanceCorrection.session_id.in_(session_ids), AttendanceCorrection.status == "Pending")
    return {(s, e) for s, e in db.session.execute(stmt).all()}


def corrections_stmt(filters: dict, scope_condition) -> Select:
    stmt = (
        select(AttendanceCorrection)
        .join(Enrolment, Enrolment.enrolment_id == AttendanceCorrection.enrolment_id)
        .where(scope_condition)
        .order_by(AttendanceCorrection.correction_id.desc())
    )
    if filters.get("status"):
        stmt = stmt.where(AttendanceCorrection.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.join(ClassSession, ClassSession.session_id == AttendanceCorrection.session_id).where(
            ClassSession.batch_id == filters["batch_id"])
    return stmt

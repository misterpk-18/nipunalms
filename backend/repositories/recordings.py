"""Recordings and recording exceptions."""
from datetime import datetime

from sqlalchemy import Select, exists, func, or_, select

from config.database import db
from models import Batch, BatchAllocation, ClassSession, Integration, Recording, RecordingException

DRIVE_INTEGRATION = "GOOGLE_DRIVE_RECORDINGS"


def get_session(session_id: int) -> ClassSession | None:
    return db.session.get(ClassSession, session_id)


def get_recording(recording_id: int) -> Recording | None:
    return db.session.get(Recording, recording_id)


def recordings_of_session(session_id: int) -> list[Recording]:
    return list(db.session.execute(select(Recording).where(Recording.session_id == session_id).order_by(Recording.part_no)).scalars())


def next_part_no(session_id: int) -> int:
    return (db.session.execute(select(func.max(Recording.part_no)).where(Recording.session_id == session_id)).scalar() or 0) + 1


def drive_verification_status() -> str:
    """Whether Drive recording capture / playback is verified (the integrations register): Verified, Not Verified, ..."""
    return db.session.execute(
        select(Integration.verification_status).where(Integration.integration_code == DRIVE_INTEGRATION)
    ).scalar() or "Not Verified"


def _visible(stmt: Select, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    if branch_ids is None:
        return stmt
    return stmt.where(or_(Batch.branch_id.in_(branch_ids), Batch.batch_id.in_(batch_ids)))


def list_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    """Recordings of the visible batches (their branches, or batches the user teaches), in session order, newest first."""
    stmt = (
        select(Recording)
        .join(ClassSession, ClassSession.session_id == Recording.session_id)
        .join(Batch, Batch.batch_id == ClassSession.batch_id)
        .order_by(ClassSession.starts_at.desc(), Recording.part_no)
    )
    stmt = _visible(stmt, branch_ids, batch_ids)
    for column, attribute in (("session_id", Recording.session_id), ("status", Recording.status), ("batch_id", ClassSession.batch_id),
                              ("branch_id", Batch.branch_id), ("course_id", Batch.course_id)):
        if filters.get(column) is not None:
            stmt = stmt.where(attribute == filters[column])
    return stmt


def allocations_for_enrolments(enrolment_ids: list[int]) -> list[BatchAllocation]:
    """Allocations that still carry entitlement to a batch's recordings: current ones and ones ended by a transfer."""
    if not enrolment_ids:
        return []
    stmt = select(BatchAllocation).where(BatchAllocation.enrolment_id.in_(enrolment_ids),
                                         BatchAllocation.status.in_(("Active", "Transferred")))
    return list(db.session.execute(stmt.order_by(BatchAllocation.effective_from)).scalars())


def for_batches(batch_ids: set[int], filters: dict) -> list[Recording]:
    if not batch_ids:
        return []
    stmt = (
        select(Recording)
        .join(ClassSession, ClassSession.session_id == Recording.session_id)
        .where(ClassSession.batch_id.in_(batch_ids))
        .order_by(ClassSession.starts_at.desc(), Recording.part_no)
    )
    if filters.get("status"):
        stmt = stmt.where(Recording.status == filters["status"])
    if filters.get("session_id"):
        stmt = stmt.where(Recording.session_id == filters["session_id"])
    return list(db.session.execute(stmt).scalars())


def delivered_sessions_without_recording(cutoff: datetime) -> list[ClassSession]:
    """Delivered sessions that ended (were marked delivered) before the cutoff and have no recording of any status."""
    stmt = (
        select(ClassSession)
        .where(ClassSession.state == "Delivered", ClassSession.delivered_at <= cutoff,
               ~exists().where(Recording.session_id == ClassSession.session_id))
        .order_by(ClassSession.delivered_at, ClassSession.session_id)
    )
    return list(db.session.execute(stmt).scalars())


# ---------------------------------------------------------------- exceptions

def get_exception(exception_id: int) -> RecordingException | None:
    return db.session.get(RecordingException, exception_id)


def open_exception(session_id: int, issue_type: str) -> RecordingException | None:
    return db.session.execute(
        select(RecordingException).where(RecordingException.session_id == session_id, RecordingException.issue_type == issue_type,
                                         RecordingException.status != "Resolved")
    ).scalar_one_or_none()


def unresolved_exceptions() -> list[RecordingException]:
    stmt = select(RecordingException).where(RecordingException.status != "Resolved").order_by(RecordingException.exception_id)
    return list(db.session.execute(stmt).scalars())


def unresolved_for_session(session_id: int, issue_types: tuple[str, ...]) -> list[RecordingException]:
    stmt = select(RecordingException).where(RecordingException.session_id == session_id, RecordingException.status != "Resolved",
                                            RecordingException.issue_type.in_(issue_types))
    return list(db.session.execute(stmt).scalars())


def exceptions_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    """Exceptions at the visible branches (or of batches the user teaches); open ones first, then newest."""
    stmt = (
        select(RecordingException)
        .join(ClassSession, ClassSession.session_id == RecordingException.session_id)
        .join(Batch, Batch.batch_id == ClassSession.batch_id)
        .order_by((RecordingException.status == "Resolved"), RecordingException.exception_id.desc())
    )
    stmt = _visible(stmt, branch_ids, batch_ids)
    for column, attribute in (("status", RecordingException.status), ("issue_type", RecordingException.issue_type),
                              ("branch_id", RecordingException.branch_id), ("batch_id", ClassSession.batch_id),
                              ("session_id", RecordingException.session_id)):
        if filters.get(column) is not None:
            stmt = stmt.where(attribute == filters[column])
    return stmt

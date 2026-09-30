"""Class sessions: detail, conflicts, change history, reschedule requests, Meet log, delivery counts, student visibility."""
from datetime import date, datetime, timedelta

from sqlalchemy import DateTime, Select, cast, exists, func, or_, select

from config.database import db
from config.timezone import IST
from models import (
    Batch, BatchAllocation, ClassSession, CurriculumModule, CurriculumTopic, MeetEvent, SessionChange,
    SessionChangeRequest,
)


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=IST)


def list_stmt(filters: dict, branch_ids: set[int] | None, trainer_batch_ids: set[int], enrolment_ids: set[int]) -> Select:
    """Class sessions in time order: those of the user's branches (None = all), of the batches they teach, or of batches
    their own enrolments are (or were) allocated to; narrowed by batch / branch / course / state / trainer / Meet status,
    'upcoming', and IST dates (from and to both inclusive)."""
    stmt = select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id).order_by(ClassSession.starts_at, ClassSession.session_id)
    if branch_ids is not None:
        visible = Batch.batch_id.in_(trainer_batch_ids)
        if branch_ids:
            visible = visible | Batch.branch_id.in_(branch_ids)
        if enrolment_ids:
            visible = visible | _student_allocation_condition(list(enrolment_ids))
        stmt = stmt.where(visible)
    if filters.get("batch_id"):
        stmt = stmt.where(ClassSession.batch_id == filters["batch_id"])
    if filters.get("branch_id"):
        stmt = stmt.where(Batch.branch_id == filters["branch_id"])
    if filters.get("course_id"):
        stmt = stmt.where(Batch.course_id == filters["course_id"])
    if filters.get("state"):
        stmt = stmt.where(ClassSession.state == filters["state"])
    if filters.get("trainer_user_id"):
        stmt = stmt.where(ClassSession.trainer_user_id == filters["trainer_user_id"])
    if filters.get("meet_status"):
        stmt = stmt.where(ClassSession.meet_status == filters["meet_status"])
    if filters.get("topic_ids"):
        stmt = stmt.where(ClassSession.topic_id.in_(filters["topic_ids"]))
    if filters.get("upcoming"):
        stmt = stmt.where(ClassSession.state.in_(("Scheduled", "Rescheduled", "Live")), ClassSession.ends_at >= func.now())
    if filters.get("from"):
        stmt = stmt.where(ClassSession.starts_at >= _start_of_day(filters["from"]))
    if filters.get("to"):
        stmt = stmt.where(ClassSession.starts_at < _start_of_day(filters["to"] + timedelta(days=1)))
    return stmt


def get_session(session_id: int) -> ClassSession | None:
    return db.session.get(ClassSession, session_id)


def get_session_for_update(session_id: int) -> ClassSession | None:
    """The session, row-locked so two state changes on it are serialised."""
    return db.session.execute(
        select(ClassSession).where(ClassSession.session_id == session_id).with_for_update(of=ClassSession)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def trainer_conflict(trainer_user_id: int, starts_at: datetime, ends_at: datetime, exclude_session_id: int | None = None) -> ClassSession | None:
    """An open session of this trainer that overlaps the window (a trainer cannot teach two classes at once)."""
    stmt = select(ClassSession).where(
        ClassSession.trainer_user_id == trainer_user_id,
        ClassSession.state.in_(("Scheduled", "Live", "Rescheduled")),
        ClassSession.starts_at < ends_at,
        ClassSession.ends_at > starts_at,
    )
    if exclude_session_id:
        stmt = stmt.where(ClassSession.session_id != exclude_session_id)
    return db.session.execute(stmt.limit(1)).scalars().first()


def room_conflict(branch_id: int, room: str, starts_at: datetime, ends_at: datetime, exclude_session_id: int | None = None) -> ClassSession | None:
    """An open session in the same room of the same branch that overlaps the window."""
    stmt = (
        select(ClassSession).join(Batch, Batch.batch_id == ClassSession.batch_id)
        .where(Batch.branch_id == branch_id, func.lower(ClassSession.room) == room.lower(),
               ClassSession.state.in_(("Scheduled", "Live", "Rescheduled")),
               ClassSession.starts_at < ends_at, ClassSession.ends_at > starts_at)
    )
    if exclude_session_id:
        stmt = stmt.where(ClassSession.session_id != exclude_session_id)
    return db.session.execute(stmt.limit(1)).scalars().first()


# ---------------------------------------------------------------- history

def changes(session_id: int) -> list[SessionChange]:
    stmt = select(SessionChange).where(SessionChange.session_id == session_id).order_by(SessionChange.created_at, SessionChange.change_id)
    return list(db.session.execute(stmt).scalars())


def meet_events(session_id: int) -> list[MeetEvent]:
    stmt = select(MeetEvent).where(MeetEvent.session_id == session_id).order_by(MeetEvent.created_at, MeetEvent.event_id)
    return list(db.session.execute(stmt).scalars())


def change_counts(session_ids: list[int]) -> dict[int, int]:
    """Reschedules / cancellations / trainer changes recorded per session."""
    if not session_ids:
        return {}
    rows = db.session.execute(
        select(SessionChange.session_id, func.count()).where(SessionChange.session_id.in_(session_ids)).group_by(SessionChange.session_id)
    )
    return dict(rows.all())


# ---------------------------------------------------------------- reschedule requests

def get_request(request_id: int) -> SessionChangeRequest | None:
    return db.session.get(SessionChangeRequest, request_id)


def get_request_for_update(request_id: int) -> SessionChangeRequest | None:
    return db.session.execute(
        select(SessionChangeRequest).where(SessionChangeRequest.request_id == request_id).with_for_update(of=SessionChangeRequest)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def open_request(session_id: int) -> SessionChangeRequest | None:
    return db.session.execute(
        select(SessionChangeRequest).where(SessionChangeRequest.session_id == session_id, SessionChangeRequest.status == "Open")
    ).scalar_one_or_none()


def open_request_ids(session_ids: list[int]) -> dict[int, int]:
    """session_id -> id of its open reschedule request."""
    if not session_ids:
        return {}
    rows = db.session.execute(
        select(SessionChangeRequest.session_id, SessionChangeRequest.request_id)
        .where(SessionChangeRequest.session_id.in_(session_ids), SessionChangeRequest.status == "Open")
    )
    return dict(rows.all())


def requests_stmt(filters: dict, branch_ids: set[int] | None, batch_ids: set[int]) -> Select:
    """Reschedule requests of the visible batches, newest first."""
    stmt = (
        select(SessionChangeRequest)
        .join(ClassSession, ClassSession.session_id == SessionChangeRequest.session_id)
        .join(Batch, Batch.batch_id == ClassSession.batch_id)
        .order_by(SessionChangeRequest.created_at.desc(), SessionChangeRequest.request_id.desc())
    )
    if branch_ids is not None:
        stmt = stmt.where(Batch.branch_id.in_(branch_ids) | Batch.batch_id.in_(batch_ids))
    if filters.get("status"):
        stmt = stmt.where(SessionChangeRequest.status == filters["status"])
    if filters.get("batch_id"):
        stmt = stmt.where(ClassSession.batch_id == filters["batch_id"])
    if filters.get("branch_id"):
        stmt = stmt.where(Batch.branch_id == filters["branch_id"])
    return stmt


# ---------------------------------------------------------------- delivery counts

def state_counts_by_batch(batch_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per batch: delivered, upcoming (Scheduled / Rescheduled / Live) and cancelled sessions."""
    if not batch_ids:
        return {}
    rows = db.session.execute(
        select(ClassSession.batch_id, ClassSession.state, func.count())
        .where(ClassSession.batch_id.in_(batch_ids)).group_by(ClassSession.batch_id, ClassSession.state)
    )
    result: dict[int, dict[str, int]] = {}
    for batch_id, state, count in rows:
        counts = result.setdefault(batch_id, {"delivered": 0, "upcoming": 0, "cancelled": 0})
        counts["delivered" if state == "Delivered" else "cancelled" if state == "Cancelled" else "upcoming"] += count
    return result


def trainer_open_sessions(batch_id: int, trainer_user_id: int) -> list[ClassSession]:
    """Sessions of the batch this trainer has yet to teach (Scheduled / Rescheduled / Live)."""
    stmt = select(ClassSession).where(ClassSession.batch_id == batch_id, ClassSession.trainer_user_id == trainer_user_id,
                                      ClassSession.state.in_(("Scheduled", "Rescheduled", "Live")))
    return list(db.session.execute(stmt).scalars())


def delivered_in_batch(batch_id: int) -> list[ClassSession]:
    stmt = select(ClassSession).where(ClassSession.batch_id == batch_id, ClassSession.state == "Delivered").order_by(ClassSession.starts_at)
    return list(db.session.execute(stmt).scalars())


# ---------------------------------------------------------------- what a student may see

def _student_allocation_condition(enrolment_ids):
    """The session's batch holds (or held, up to the day the allocation ended) one of these enrolments."""
    ended_at = func.timezone("Asia/Kolkata", cast(BatchAllocation.effective_to + timedelta(days=1), DateTime))
    return exists().where(
        BatchAllocation.enrolment_id.in_(enrolment_ids),
        BatchAllocation.batch_id == ClassSession.batch_id,
        or_(BatchAllocation.status == "Active", ClassSession.starts_at < ended_at),
    )


def student_sessions_stmt(enrolment_ids: set[int] | list[int]) -> Select:
    """Sessions of batches the enrolments are allocated to (a transferred-out batch only up to the transfer), in time order."""
    if not enrolment_ids:
        return select(ClassSession).where(False).order_by(ClassSession.starts_at)
    return select(ClassSession).where(_student_allocation_condition(list(enrolment_ids))).order_by(ClassSession.starts_at, ClassSession.session_id)


def student_can_see_session(enrolment_ids: set[int], session_id: int) -> bool:
    if not enrolment_ids:
        return False
    stmt = select(ClassSession.session_id).where(ClassSession.session_id == session_id, _student_allocation_condition(list(enrolment_ids)))
    return db.session.execute(stmt).first() is not None


def module_topic_ids(module_ids: list[int]) -> dict[int, list[int]]:
    if not module_ids:
        return {}
    rows = db.session.execute(
        select(CurriculumTopic.module_id, CurriculumTopic.topic_id).where(CurriculumTopic.module_id.in_(module_ids))
        .order_by(CurriculumTopic.sort_order)
    )
    result: dict[int, list[int]] = {}
    for module_id, topic_id in rows:
        result.setdefault(module_id, []).append(topic_id)
    return result


def topic_module_ids(topic_ids: list[int]) -> dict[int, int]:
    if not topic_ids:
        return {}
    return dict(db.session.execute(select(CurriculumTopic.topic_id, CurriculumTopic.module_id).where(CurriculumTopic.topic_id.in_(topic_ids))).all())


def topic_version_ids(topic_ids: list[int]) -> dict[int, int]:
    """topic_id -> curriculum_version_id (through its module)."""
    if not topic_ids:
        return {}
    rows = db.session.execute(
        select(CurriculumTopic.topic_id, CurriculumModule.curriculum_version_id)
        .join(CurriculumModule, CurriculumModule.module_id == CurriculumTopic.module_id)
        .where(CurriculumTopic.topic_id.in_(topic_ids))
    )
    return dict(rows.all())


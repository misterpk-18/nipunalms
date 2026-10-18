"""Today's guided class flow (db 112): saved progress, covered topics, the "no Meet link" request, and the trainer's classes
that still have no class log."""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from config.database import db
from repositories import catalog as catalog_repo
from models import (
    ClassFlowProgress, ClassSession, ClassSessionTopic, CourseModule, CourseTopic, MeetEvent,
)

LINK_REQUESTED = "Link requested"
NOT_LOGGED_STATES = ("Scheduled", "Rescheduled", "Live")


# ---------------------------------------------------------------- saved progress

def get_progress(session_id: int) -> ClassFlowProgress | None:
    return db.session.get(ClassFlowProgress, session_id)


def save_progress(session_id: int, step: str, draft: dict, user_id: int) -> None:
    stmt = insert(ClassFlowProgress).values(session_id=session_id, step=step, draft=draft, updated_by=user_id, updated_at=func.now())
    db.session.execute(stmt.on_conflict_do_update(
        index_elements=["session_id"], set_={"step": step, "draft": draft, "updated_by": user_id, "updated_at": func.now()}))
    db.session.expire_all()


def clear_progress(session_id: int) -> None:
    db.session.execute(delete(ClassFlowProgress).where(ClassFlowProgress.session_id == session_id))


# ---------------------------------------------------------------- covered topics

def covered_topics(session_ids: list[int]) -> dict[int, list[CourseTopic]]:
    """session_id -> the topics logged as covered, in curriculum order."""
    out: dict[int, list[CourseTopic]] = {i: [] for i in session_ids}
    if session_ids:
        stmt = (select(ClassSessionTopic.session_id, CourseTopic)
                .join(CourseTopic, CourseTopic.topic_id == ClassSessionTopic.topic_id)
                .join(CourseModule, CourseModule.module_id == CourseTopic.module_id)
                .where(ClassSessionTopic.session_id.in_(session_ids))
                .order_by(CourseModule.sort_order, CourseTopic.sort_order))
        for session_id, topic in db.session.execute(stmt):
            out[session_id].append(topic)
    return out


def replace_covered_topics(session_id: int, topic_ids: list[int]) -> None:
    db.session.execute(delete(ClassSessionTopic).where(ClassSessionTopic.session_id == session_id))
    for topic_id in dict.fromkeys(topic_ids):
        db.session.add(ClassSessionTopic(session_id=session_id, topic_id=topic_id))
    db.session.flush()


def outline_topics(course_id: int, component_id: int | None) -> list[tuple[CourseModule, CourseTopic]]:
    """Every topic of one course outline (the course's own, or a combo track's) with its module, in order (what a class log can tick)."""
    return [(module, topic) for module in catalog_repo.outline_for(course_id, component_id) for topic in module.topics]


# ---------------------------------------------------------------- "no Meet link"

def link_requested_at(session_id: int) -> datetime | None:
    """When the trainer last asked the Branch Manager for a link (a later link or a removal does not clear the history)."""
    return db.session.execute(select(func.max(MeetEvent.created_at)).where(
        MeetEvent.session_id == session_id, MeetEvent.event_type == LINK_REQUESTED)).scalar_one()


# ---------------------------------------------------------------- classes without a class log

def unlogged_stmt(trainer_user_id: int, since: datetime, now: datetime):
    """The trainer's classes that ended and were never logged (not Delivered or Cancelled), leaving out classes
    still waiting for the Branch Manager's approval; oldest first."""
    return (select(ClassSession).where(
        ClassSession.trainer_user_id == trainer_user_id, ClassSession.state.in_(NOT_LOGGED_STATES),
        ClassSession.approval_status != "Pending", ClassSession.ends_at < now, ClassSession.ends_at >= since)
        .order_by(ClassSession.starts_at, ClassSession.session_id))


def unlogged_sessions(trainer_user_id: int, since: datetime, now: datetime, limit: int | None = None) -> list[ClassSession]:
    stmt = unlogged_stmt(trainer_user_id, since, now)
    if limit:
        stmt = stmt.limit(limit)
    return list(db.session.execute(stmt).scalars().unique())


def unlogged_count(trainer_user_id: int, since: datetime, now: datetime) -> int:
    return db.session.execute(select(func.count()).select_from(unlogged_stmt(trainer_user_id, since, now).order_by(None).subquery())).scalar_one()

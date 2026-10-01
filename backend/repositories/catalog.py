"""Courses, components and curriculum versions."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import (
    Batch, Course, CourseComponent, CurriculumEvent, CurriculumModule, CurriculumTopic, CurriculumVersion, Enrolment,
    EnrolmentTrack,
)


def get_course(course_id: int) -> Course | None:
    return db.session.get(Course, course_id)


def get_course_by_code(course_code: str) -> Course | None:
    return db.session.execute(select(Course).where(Course.course_code == course_code)).scalar_one_or_none()


def list_courses() -> list[Course]:
    stmt = select(Course).options(selectinload(Course.components)).order_by(Course.course_code)
    return list(db.session.execute(stmt).scalars())


def get_component_by_track_code(track_code: str) -> CourseComponent | None:
    return db.session.execute(
        select(CourseComponent).where(CourseComponent.track_code == track_code)
    ).scalar_one_or_none()


def get_component_by_course(parent_course_id: int, component_course_id: int) -> CourseComponent | None:
    """The combo's track for a component course (how the CRM's combo_courses rows identify it)."""
    return db.session.execute(
        select(CourseComponent).where(CourseComponent.parent_course_id == parent_course_id,
                                      CourseComponent.component_course_id == component_course_id)
    ).scalar_one_or_none()


def components_of(course_id: int) -> list[CourseComponent]:
    stmt = select(CourseComponent).where(CourseComponent.parent_course_id == course_id).order_by(CourseComponent.sort_order)
    return list(db.session.execute(stmt).scalars())


def component_usage(component_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per component: enrolment tracks and curriculum versions that point at it (either blocks removing it)."""
    usage = {cid: {"enrolment_tracks": 0, "curriculum_versions": 0} for cid in component_ids}
    if not component_ids:
        return usage
    for column, key in ((EnrolmentTrack.component_id, "enrolment_tracks"), (CurriculumVersion.component_id, "curriculum_versions")):
        for cid, n in db.session.execute(select(column, func.count()).where(column.in_(component_ids)).group_by(column)):
            usage[cid][key] = n
    return usage


def enrolments_using_components(component_ids: list[int]) -> int:
    return db.session.execute(
        select(func.count(func.distinct(EnrolmentTrack.enrolment_id))).where(EnrolmentTrack.component_id.in_(component_ids))
    ).scalar()


def active_curriculum_version_id(course_id: int, component_id: int | None = None) -> int | None:
    """The Active curriculum version of a course (or of one of its tracks); None when none is mapped."""
    return db.session.execute(select(func.active_curriculum_version(course_id, component_id))).scalar()


def get_curriculum_version(curriculum_version_id: int) -> CurriculumVersion | None:
    return db.session.get(CurriculumVersion, curriculum_version_id)


# ---------------------------------------------------------------- curriculum management

def get_version_for_update(curriculum_version_id: int) -> CurriculumVersion | None:
    """The version, row-locked so two status changes on it are serialised."""
    return db.session.execute(
        select(CurriculumVersion).where(CurriculumVersion.curriculum_version_id == curriculum_version_id)
        .with_for_update(of=CurriculumVersion).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def list_versions(filters: dict) -> list[CurriculumVersion]:
    stmt = select(CurriculumVersion).order_by(
        CurriculumVersion.course_id, CurriculumVersion.component_id.nulls_first(), CurriculumVersion.curriculum_version_id.desc())
    if filters.get("course_id"):
        stmt = stmt.where(CurriculumVersion.course_id == filters["course_id"])
    if "component_id" in filters:
        stmt = stmt.where(CurriculumVersion.component_id == filters["component_id"])
    if filters.get("status"):
        stmt = stmt.where(CurriculumVersion.status == filters["status"])
    return list(db.session.execute(stmt).scalars())


def get_module(module_id: int) -> CurriculumModule | None:
    return db.session.get(CurriculumModule, module_id)


def get_topic(topic_id: int) -> CurriculumTopic | None:
    return db.session.get(CurriculumTopic, topic_id)


def get_component(component_id: int) -> CourseComponent | None:
    return db.session.get(CourseComponent, component_id)


def content_counts(version_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per version: modules, topics and required topics."""
    if not version_ids:
        return {}
    rows = db.session.execute(
        select(CurriculumModule.curriculum_version_id, func.count(func.distinct(CurriculumModule.module_id)),
               func.count(CurriculumTopic.topic_id), func.count(CurriculumTopic.topic_id).filter(CurriculumTopic.is_required))
        .outerjoin(CurriculumTopic, CurriculumTopic.module_id == CurriculumModule.module_id)
        .where(CurriculumModule.curriculum_version_id.in_(version_ids)).group_by(CurriculumModule.curriculum_version_id)
    )
    return {vid: {"modules": m, "topics": t, "required_topics": r} for vid, m, t, r in rows}


def usage_counts(version_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per version: batches, enrolments and combo tracks that point at it."""
    if not version_ids:
        return {}
    usage = {vid: {"batches": 0, "enrolments": 0, "tracks": 0} for vid in version_ids}
    for column, key in ((Batch.curriculum_version_id, "batches"), (Enrolment.curriculum_version_id, "enrolments"),
                        (EnrolmentTrack.curriculum_version_id, "tracks")):
        for vid, count in db.session.execute(select(column, func.count()).where(column.in_(version_ids)).group_by(column)):
            usage[vid][key] = count
    return usage


def add_event(version: CurriculumVersion, action: str, from_status: str | None, to_status: str, actor_user_id: int | None,
              note: str | None = None) -> CurriculumEvent:
    event = CurriculumEvent(curriculum_version_id=version.curriculum_version_id, action=action, from_status=from_status,
                            to_status=to_status, actor_user_id=actor_user_id, note=note)
    db.session.add(event)
    return event


def events_of(curriculum_version_id: int) -> list[CurriculumEvent]:
    stmt = select(CurriculumEvent).where(CurriculumEvent.curriculum_version_id == curriculum_version_id).order_by(
        CurriculumEvent.created_at, CurriculumEvent.event_id)
    return list(db.session.execute(stmt).scalars())


def last_event(curriculum_version_id: int, action: str) -> CurriculumEvent | None:
    stmt = select(CurriculumEvent).where(
        CurriculumEvent.curriculum_version_id == curriculum_version_id, CurriculumEvent.action == action
    ).order_by(CurriculumEvent.event_id.desc()).limit(1)
    return db.session.execute(stmt).scalars().first()


def next_module_order(curriculum_version_id: int) -> int:
    highest = db.session.execute(
        select(func.max(CurriculumModule.sort_order)).where(CurriculumModule.curriculum_version_id == curriculum_version_id)).scalar()
    return (highest or 0) + 1


def next_topic_order(module_id: int) -> int:
    highest = db.session.execute(select(func.max(CurriculumTopic.sort_order)).where(CurriculumTopic.module_id == module_id)).scalar()
    return (highest or 0) + 1


def pending_enrolments(course_id: int) -> list[Enrolment]:
    """Enrolments of the course, or combo enrolments with a track built on it, still waiting for a curriculum version."""
    track_enrolments = (
        select(EnrolmentTrack.enrolment_id)
        .join(CourseComponent, CourseComponent.component_id == EnrolmentTrack.component_id)
        .where(CourseComponent.component_course_id == course_id)
    )
    stmt = (
        select(Enrolment)
        .where(Enrolment.status == "Curriculum Mapping Pending",
               or_(Enrolment.course_id == course_id, Enrolment.enrolment_id.in_(track_enrolments)))
        .order_by(Enrolment.enrolment_id)
    )
    return list(db.session.execute(stmt).scalars())


def pending_enrolment_counts() -> dict[int, int]:
    """course_id -> enrolments waiting in Curriculum Mapping Pending."""
    return dict(db.session.execute(
        select(Enrolment.course_id, func.count()).where(Enrolment.status == "Curriculum Mapping Pending").group_by(Enrolment.course_id)
    ).all())


def batches_without_version(course_id: int) -> list[Batch]:
    stmt = select(Batch).where(Batch.course_id == course_id, Batch.curriculum_version_id.is_(None),
                               Batch.state.not_in(("Completed", "Cancelled")))
    return list(db.session.execute(stmt).scalars())

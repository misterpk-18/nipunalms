"""Courses, combo components and their outlines (modules and topics)."""
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import AssessmentRequirement, Batch, Course, CourseComponent, CourseModule, CourseTopic, EnrolmentTrack


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
    """Per component: enrolment tracks and outline modules that point at it (either blocks removing it)."""
    usage = {cid: {"enrolment_tracks": 0, "modules": 0} for cid in component_ids}
    if not component_ids:
        return usage
    for column, key in ((EnrolmentTrack.component_id, "enrolment_tracks"), (CourseModule.component_id, "modules")):
        for cid, n in db.session.execute(select(column, func.count()).where(column.in_(component_ids)).group_by(column)):
            usage[cid][key] = n
    return usage


def enrolments_using_components(component_ids: list[int]) -> int:
    return db.session.execute(
        select(func.count(func.distinct(EnrolmentTrack.enrolment_id))).where(EnrolmentTrack.component_id.in_(component_ids))
    ).scalar()


# ---------------------------------------------------------------- the course outline

def get_course_for_update(course_id: int) -> Course | None:
    """The course, row-locked so two outline edits on it are serialised."""
    return db.session.execute(
        select(Course).where(Course.course_id == course_id).with_for_update(of=Course).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def get_module(module_id: int) -> CourseModule | None:
    return db.session.get(CourseModule, module_id)


def get_topic(topic_id: int) -> CourseTopic | None:
    return db.session.get(CourseTopic, topic_id)


def get_component(component_id: int) -> CourseComponent | None:
    return db.session.get(CourseComponent, component_id)


def outline_modules(course_id: int) -> list[CourseModule]:
    """Every live (not archived) module of the course with its topics: the course's own first, then each combo track's."""
    stmt = (select(CourseModule).options(selectinload(CourseModule.topics))
            .where(CourseModule.course_id == course_id, CourseModule.is_archived.is_(False))
            .order_by(CourseModule.component_id.nulls_first(), CourseModule.sort_order))
    return list(db.session.execute(stmt).scalars())


def outline_modules_of(course_ids: list[int]) -> dict[int, list[CourseModule]]:
    """Live modules (with topics) of several courses, whole-course modules first."""
    out: dict[int, list[CourseModule]] = {i: [] for i in course_ids}
    if course_ids:
        stmt = (select(CourseModule).options(selectinload(CourseModule.topics))
                .where(CourseModule.course_id.in_(course_ids), CourseModule.is_archived.is_(False))
                .order_by(CourseModule.course_id, CourseModule.component_id.nulls_first(), CourseModule.sort_order))
        for module in db.session.execute(stmt).scalars():
            out[module.course_id].append(module)
    return out


def module_counts(course_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per course: live modules, topics and required topics."""
    if not course_ids:
        return {}
    rows = db.session.execute(
        select(CourseModule.course_id, func.count(func.distinct(CourseModule.module_id)),
               func.count(CourseTopic.topic_id), func.count(CourseTopic.topic_id).filter(CourseTopic.is_required))
        .outerjoin(CourseTopic, CourseTopic.module_id == CourseModule.module_id)
        .where(CourseModule.course_id.in_(course_ids), CourseModule.is_archived.is_(False)).group_by(CourseModule.course_id)
    )
    counts = {cid: {"modules": m, "topics": t, "required_topics": r} for cid, m, t, r in rows}
    return {cid: counts.get(cid, {"modules": 0, "topics": 0, "required_topics": 0}) for cid in course_ids}


def next_module_order(course_id: int, component_id: int | None) -> int:
    stmt = select(func.max(CourseModule.sort_order)).where(CourseModule.course_id == course_id, CourseModule.is_archived.is_(False),
                                                           CourseModule.component_id.is_(None) if component_id is None
                                                           else CourseModule.component_id == component_id)
    return (db.session.execute(stmt).scalar() or 0) + 1


def next_topic_order(module_id: int) -> int:
    highest = db.session.execute(select(func.max(CourseTopic.sort_order)).where(CourseTopic.module_id == module_id)).scalar()
    return (highest or 0) + 1


def open_batches_of(course_id: int) -> list[Batch]:
    """Batches of the course that have not finished (the ones an outline edit changes the plan of)."""
    stmt = select(Batch).where(Batch.course_id == course_id, Batch.state.not_in(("Completed", "Cancelled", "Archived")))
    return list(db.session.execute(stmt).scalars())


def assessment_requirements(course_id: int) -> list[AssessmentRequirement]:
    stmt = select(AssessmentRequirement).where(AssessmentRequirement.course_id == course_id).order_by(AssessmentRequirement.requirement_id)
    return list(db.session.execute(stmt).scalars())


def get_requirement(requirement_id: int) -> AssessmentRequirement | None:
    return db.session.get(AssessmentRequirement, requirement_id)


def outline_for(course_id: int, component_id: int | None = None) -> list[CourseModule]:
    """The live modules (with topics) one outline holds: the course's own (component_id None) or one combo track's, which follows
    the standalone course it is pinned to when it has a pin."""
    if component_id is not None:
        component = db.session.get(CourseComponent, component_id)
        if component is not None and component.pinned_course_id is not None:
            course_id, component_id = component.pinned_course_id, None
    stmt = (select(CourseModule).options(selectinload(CourseModule.topics))
            .where(CourseModule.course_id == course_id, CourseModule.is_archived.is_(False),
                   CourseModule.component_id.is_(None) if component_id is None else CourseModule.component_id == component_id)
            .order_by(CourseModule.sort_order))
    return list(db.session.execute(stmt).scalars())


def followed_outlines(enrolment) -> list[tuple[int, int | None]]:
    """(course_id, component_id) of the outlines an enrolment studies, in study order: each combo track it holds, else the course."""
    if enrolment.tracks:
        return [(e.pinned_course_id, None) if (e := t.component).pinned_course_id else (e.parent_course_id, e.component_id)
                for t in enrolment.tracks]
    return [(enrolment.course_id, None)]


def track_labels(component_ids: set[int | None]) -> dict[int, dict]:
    """Combo track behind each component id (None = the whole course, which has no track)."""
    ids = {i for i in component_ids if i}
    if not ids:
        return {}
    rows = db.session.execute(select(CourseComponent).where(CourseComponent.component_id.in_(ids))).scalars()
    return {c.component_id: {"track_code": c.track_code, "track_name": c.track_name} for c in rows}

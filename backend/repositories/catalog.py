"""Courses, components and curriculum versions."""
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import Course, CourseComponent, CurriculumVersion


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


def active_curriculum_version_id(course_id: int, component_id: int | None = None) -> int | None:
    """The Active curriculum version of a course (or of one of its tracks); None when none is mapped."""
    return db.session.execute(select(func.active_curriculum_version(course_id, component_id))).scalar()


def get_curriculum_version(curriculum_version_id: int) -> CurriculumVersion | None:
    return db.session.get(CurriculumVersion, curriculum_version_id)

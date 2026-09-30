"""Content items, versions, review history and the placement choices offered to authors."""
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import (
    ActivityEvent, Batch, ContentItem, ContentReview, ContentVersion, CourseComponent, CurriculumModule, CurriculumTopic,
    CurriculumVersion, Enrolment,
)


def get_item(content_item_id: int) -> ContentItem | None:
    return db.session.get(ContentItem, content_item_id)


def get_topic(topic_id: int) -> CurriculumTopic | None:
    return db.session.get(CurriculumTopic, topic_id)


def get_module(module_id: int) -> CurriculumModule | None:
    return db.session.get(CurriculumModule, module_id)


def get_version(curriculum_version_id: int) -> CurriculumVersion | None:
    return db.session.get(CurriculumVersion, curriculum_version_id)


def next_version_no(content_item_id: int) -> int:
    return (db.session.execute(
        select(func.max(ContentVersion.version_no)).where(ContentVersion.content_item_id == content_item_id)
    ).scalar() or 0) + 1


def reviews_of(content_item_id: int) -> list[ContentReview]:
    stmt = select(ContentReview).where(ContentReview.content_item_id == content_item_id).order_by(ContentReview.acted_at, ContentReview.review_id)
    return list(db.session.execute(stmt).scalars())


def _has_released_version():
    return exists().where(ContentVersion.content_item_id == ContentItem.content_item_id, ContentVersion.status == "Released")


def list_stmt(filters: dict, branch_ids: set[int] | None, owner_user_id: int, batch_ids: set[int]) -> Select:
    """Items the staff member sees: those at their branches (None = all), that they authored, or of batches they teach."""
    stmt = select(ContentItem).options(selectinload(ContentItem.versions)).order_by(ContentItem.updated_at.desc(), ContentItem.content_item_id.desc())
    if branch_ids is not None:
        stmt = stmt.where(or_(ContentItem.branch_id.in_(branch_ids), ContentItem.owner_user_id == owner_user_id,
                              ContentItem.batch_id.in_(batch_ids)))
    for column in ("course_id", "batch_id", "branch_id", "module_id", "topic_id", "content_type", "owner_user_id"):
        if filters.get(column) is not None:
            stmt = stmt.where(getattr(ContentItem, column) == filters[column])
    if filters.get("status"):
        stmt = stmt.where(ContentItem.status.in_(filters["status"]))
    if filters.get("q"):
        stmt = stmt.where(ContentItem.title.ilike(f"%{filters['q']}%"))
    return stmt


def released_candidates(branch_ids: set[int], course_ids: set[int], filters: dict) -> list[ContentItem]:
    """Released, not retired items at these branches for these courses; the caller applies the exact audience rules."""
    if not branch_ids or not course_ids:
        return []
    stmt = (
        select(ContentItem)
        .options(selectinload(ContentItem.versions))
        .where(ContentItem.retired_at.is_(None), _has_released_version(), ContentItem.branch_id.in_(branch_ids),
               ContentItem.course_id.in_(course_ids))
        .order_by(ContentItem.content_item_id.desc())
    )
    for column in ("course_id", "module_id", "topic_id", "content_type"):
        if filters.get(column) is not None:
            stmt = stmt.where(getattr(ContentItem, column) == filters[column])
    if filters.get("q"):
        stmt = stmt.where(ContentItem.title.ilike(f"%{filters['q']}%"))
    return list(db.session.execute(stmt).scalars())


def audience_enrolments(branch_id: int, course_id: int) -> list[Enrolment]:
    """Enrolments that could be entitled to an item of this course at this branch (started, not withdrawn)."""
    stmt = (
        select(Enrolment)
        .options(selectinload(Enrolment.tracks))
        .where(Enrolment.service_branch_id == branch_id, Enrolment.course_id == course_id,
               Enrolment.status.not_in(("Withdrawn", "Provisioning Pending")))
    )
    return list(db.session.execute(stmt).scalars())


def track_labels(curriculum_version_ids: set[int]) -> dict[int, dict]:
    """Combo track behind each curriculum version (versions of a whole course have none)."""
    ids = {i for i in curriculum_version_ids if i}
    if not ids:
        return {}
    stmt = (
        select(CurriculumVersion.curriculum_version_id, CourseComponent)
        .join(CourseComponent, CourseComponent.component_id == CurriculumVersion.component_id)
        .where(CurriculumVersion.curriculum_version_id.in_(ids))
    )
    return {version_id: {"track_code": c.track_code, "track_name": c.track_name} for version_id, c in db.session.execute(stmt).all()}


def batches_for_authoring(branch_ids: set[int] | None, batch_ids: set[int]) -> list[Batch]:
    """Open batches whose content the user may manage: at their branches (None = all) or that they teach."""
    stmt = select(Batch).where(Batch.state.not_in(("Completed", "Cancelled"))).order_by(Batch.branch_id, Batch.batch_code)
    if branch_ids is not None:
        stmt = stmt.where(or_(Batch.branch_id.in_(branch_ids), Batch.batch_id.in_(batch_ids)))
    return list(db.session.execute(stmt).scalars())


def versions_with_modules(course_id: int, batch_version_id: int | None) -> list[CurriculumVersion]:
    """The batch's curriculum version plus the Active track versions of the course, with modules and topics loaded."""
    stmt = (
        select(CurriculumVersion)
        .options(selectinload(CurriculumVersion.modules).selectinload(CurriculumModule.topics))
        .where(CurriculumVersion.course_id == course_id,
               or_(CurriculumVersion.status == "Active", CurriculumVersion.curriculum_version_id == batch_version_id))
        .order_by(CurriculumVersion.component_id.nulls_first(), CurriculumVersion.curriculum_version_id)
    )
    return list(db.session.execute(stmt).scalars())


def record_activity(student_id: int, enrolment_id: int | None, kind: str, detail: dict) -> None:
    db.session.add(ActivityEvent(student_id=student_id, enrolment_id=enrolment_id, kind=kind, detail=detail))

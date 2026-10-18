"""Content items, versions, review history and the placement choices offered to authors."""
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import (
    ActivityEvent, Batch, ContentItem, ContentReview, ContentVersion, CourseComponent, CourseModule, CourseTopic,
    Enrolment,
)
from repositories import catalog as catalog_repo


def get_item(content_item_id: int) -> ContentItem | None:
    return db.session.get(ContentItem, content_item_id)


def get_topic(topic_id: int) -> CourseTopic | None:
    return db.session.get(CourseTopic, topic_id)


def get_module(module_id: int) -> CourseModule | None:
    return db.session.get(CourseModule, module_id)


def next_version_no(content_item_id: int) -> int:
    return (db.session.execute(
        select(func.max(ContentVersion.version_no)).where(ContentVersion.content_item_id == content_item_id)
    ).scalar() or 0) + 1


def reviews_of(content_item_id: int) -> list[ContentReview]:
    stmt = select(ContentReview).where(ContentReview.content_item_id == content_item_id).order_by(ContentReview.acted_at, ContentReview.review_id)
    return list(db.session.execute(stmt).scalars())


def latest_decisions(item_ids: list[int]) -> dict[int, ContentReview]:
    """The newest "Changes Requested" / "Rejected" review of each item's current version (what the author has to act on)."""
    if not item_ids:
        return {}
    latest_version = (select(func.max(ContentVersion.content_version_id)).where(ContentVersion.content_item_id == ContentReview.content_item_id)
                      .correlate(ContentReview).scalar_subquery())
    stmt = (select(ContentReview)
            .where(ContentReview.content_item_id.in_(item_ids), ContentReview.action.in_(("Changes Requested", "Rejected")),
                   ContentReview.content_version_id == latest_version)
            .order_by(ContentReview.acted_at, ContentReview.review_id))
    return {review.content_item_id: review for review in db.session.execute(stmt).scalars().unique()}  # the newest wins


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
    """Released, not retired, student-facing items at these branches for these courses; the caller applies the exact audience
    rules."""
    if not branch_ids or not course_ids:
        return []
    stmt = (
        select(ContentItem)
        .options(selectinload(ContentItem.versions))
        .where(ContentItem.retired_at.is_(None), ContentItem.staff_only.is_(False), _has_released_version(), ContentItem.branch_id.in_(branch_ids),
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


def track_labels(component_ids: set[int | None]) -> dict[int, dict]:
    """Combo track behind each component id (a whole-course module has none)."""
    return catalog_repo.track_labels(component_ids)


def batches_for_authoring(branch_ids: set[int] | None, batch_ids: set[int]) -> list[Batch]:
    """Open batches whose content the user may manage: at their branches (None = all) or that they teach."""
    stmt = select(Batch).where(Batch.state.not_in(("Completed", "Cancelled"))).order_by(Batch.branch_id, Batch.batch_code)
    if branch_ids is not None:
        stmt = stmt.where(or_(Batch.branch_id.in_(branch_ids), Batch.batch_id.in_(batch_ids)))
    return list(db.session.execute(stmt).scalars())


def outlines_of(course_id: int) -> list[tuple[int | None, list[CourseModule]]]:
    """The course's outlines with modules and topics: the whole course first, then each combo track that has modules."""
    groups: dict[int | None, list[CourseModule]] = {}
    for module in catalog_repo.outline_modules(course_id):
        groups.setdefault(module.component_id, []).append(module)
    return sorted(groups.items(), key=lambda kv: (kv[0] is not None, kv[0] or 0))



def record_activity(student_id: int, enrolment_id: int | None, kind: str, detail: dict) -> None:
    db.session.add(ActivityEvent(student_id=student_id, enrolment_id=enrolment_id, kind=kind, detail=detail))


def claims(item_ids: list[int]) -> dict[int, ContentReview]:
    """For items under review: the "Review Started" entry of the current version (who has it open)."""
    if not item_ids:
        return {}
    latest_version = (select(func.max(ContentVersion.content_version_id)).where(ContentVersion.content_item_id == ContentReview.content_item_id)
                      .correlate(ContentReview).scalar_subquery())
    stmt = (select(ContentReview).where(ContentReview.content_item_id.in_(item_ids), ContentReview.action == "Review Started",
                                        ContentReview.content_version_id == latest_version).order_by(ContentReview.acted_at, ContentReview.review_id))
    return {review.content_item_id: review for review in db.session.execute(stmt).scalars().unique()}


def count_by_status(branch_ids: set[int] | None) -> dict[str, int]:
    stmt = select(ContentItem.status, func.count()).where(ContentItem.retired_at.is_(None)).group_by(ContentItem.status)
    if branch_ids is not None:
        stmt = stmt.where(ContentItem.branch_id.in_(branch_ids))
    return {str(status): n for status, n in db.session.execute(stmt).all()}

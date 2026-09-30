"""Assignments, their submissions and reviews."""
from sqlalchemy import Select, and_, func, select

from config.database import db
from models import (
    Assignment, AssignmentSubmission, BatchAllocation, CurriculumModule, CurriculumTopic, CurriculumVersion, Enrolment, SubmissionReview,
)


def get_assignment(assignment_id: int) -> Assignment | None:
    return db.session.get(Assignment, assignment_id)


def list_stmt(filters: dict, batch_clause=None) -> Select:
    """Assignments (any status) narrowed by the filters; batch_clause restricts them to the caller's batches."""
    stmt = select(Assignment).order_by(Assignment.due_at.desc(), Assignment.assignment_id.desc())
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Assignment.batch_id))
    if filters.get("batch_id"):
        stmt = stmt.where(Assignment.batch_id == filters["batch_id"])
    if filters.get("status"):
        stmt = stmt.where(Assignment.status == filters["status"])
    if filters.get("reviewer_id"):
        stmt = stmt.where(Assignment.reviewer_user_id == filters["reviewer_id"])
    if filters.get("is_required") is not None:
        stmt = stmt.where(Assignment.is_required == filters["is_required"])
    return stmt


def released_for_batches(batch_ids: set[int], now) -> list[Assignment]:
    """What students of these batches see: released and past their release time (withdrawn work is hidden)."""
    if not batch_ids:
        return []
    stmt = (
        select(Assignment)
        .where(Assignment.batch_id.in_(batch_ids), Assignment.status == "Released", Assignment.release_at <= now)
        .order_by(Assignment.due_at, Assignment.assignment_id)
    )
    return list(db.session.execute(stmt).scalars())


# ---------------------------------------------------------------- submissions

def get_submission(submission_id: int) -> AssignmentSubmission | None:
    return db.session.get(AssignmentSubmission, submission_id)


def versions_of(assignment_id: int, enrolment_id: int) -> list[AssignmentSubmission]:
    """Every version a student submitted for the assignment, oldest first."""
    stmt = (
        select(AssignmentSubmission)
        .where(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.enrolment_id == enrolment_id)
        .order_by(AssignmentSubmission.version_no)
    )
    return list(db.session.execute(stmt).scalars())


def versions_for_enrolments(enrolment_ids: set[int], assignment_ids: list[int]) -> dict[tuple[int, int], list[AssignmentSubmission]]:
    """(assignment id, enrolment id) -> versions, oldest first, for a student's whole task list in one query."""
    if not enrolment_ids or not assignment_ids:
        return {}
    stmt = (
        select(AssignmentSubmission)
        .where(AssignmentSubmission.enrolment_id.in_(enrolment_ids), AssignmentSubmission.assignment_id.in_(assignment_ids))
        .order_by(AssignmentSubmission.version_no)
    )
    grouped: dict[tuple[int, int], list[AssignmentSubmission]] = {}
    for submission in db.session.execute(stmt).scalars():
        grouped.setdefault((submission.assignment_id, submission.enrolment_id), []).append(submission)
    return grouped


def latest_submissions_stmt(filters: dict, batch_clause=None) -> Select:
    """The newest version per student and assignment, narrowed by the filters (review queue and per-assignment lists)."""
    latest = (
        select(AssignmentSubmission.assignment_id, AssignmentSubmission.enrolment_id,
               func.max(AssignmentSubmission.version_no).label("version_no"))
        .group_by(AssignmentSubmission.assignment_id, AssignmentSubmission.enrolment_id)
        .subquery()
    )
    stmt = (
        select(AssignmentSubmission)
        .join(latest, and_(AssignmentSubmission.assignment_id == latest.c.assignment_id,
                           AssignmentSubmission.enrolment_id == latest.c.enrolment_id,
                           AssignmentSubmission.version_no == latest.c.version_no))
        .join(Assignment, Assignment.assignment_id == AssignmentSubmission.assignment_id)
        .outerjoin(SubmissionReview, SubmissionReview.submission_id == AssignmentSubmission.submission_id)
        .order_by(AssignmentSubmission.submitted_at, AssignmentSubmission.submission_id)
    )
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Assignment.batch_id))
    if filters.get("assignment_id"):
        stmt = stmt.where(AssignmentSubmission.assignment_id == filters["assignment_id"])
    if filters.get("batch_id"):
        stmt = stmt.where(Assignment.batch_id == filters["batch_id"])
    if filters.get("reviewer_id"):
        stmt = stmt.where(Assignment.reviewer_user_id == filters["reviewer_id"])
    status = filters.get("status")
    if status == "Awaiting Review":
        stmt = stmt.where(SubmissionReview.review_id.is_(None))
    elif status in ("Reviewed", "Resubmission Requested"):
        stmt = stmt.where(SubmissionReview.outcome == status)
    return stmt


def submission_counts(assignment_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per assignment: students who submitted, latest versions awaiting review, reviewed, resubmission requested."""
    if not assignment_ids:
        return {}
    stmt = latest_submissions_stmt({}).where(AssignmentSubmission.assignment_id.in_(assignment_ids))
    counts = {a: {"submitted": 0, "awaiting_review": 0, "reviewed": 0, "resubmission_requested": 0} for a in assignment_ids}
    for submission in db.session.execute(stmt).scalars():
        row = counts[submission.assignment_id]
        row["submitted"] += 1
        if submission.review is None:
            row["awaiting_review"] += 1
        elif submission.review.outcome == "Reviewed":
            row["reviewed"] += 1
        else:
            row["resubmission_requested"] += 1
    return counts


def get_review(submission_id: int) -> SubmissionReview | None:
    return db.session.execute(
        select(SubmissionReview).where(SubmissionReview.submission_id == submission_id)
    ).scalar_one_or_none()


def enrolments_in_batch(batch_id: int) -> list[Enrolment]:
    """Enrolments holding a seat in the batch."""
    stmt = (
        select(Enrolment)
        .join(BatchAllocation, BatchAllocation.enrolment_id == Enrolment.enrolment_id)
        .where(BatchAllocation.batch_id == batch_id, BatchAllocation.status == "Active")
        .order_by(Enrolment.enrolment_id)
    )
    return list(db.session.execute(stmt).scalars().unique())


def active_modules(course_id: int) -> list[CurriculumModule]:
    """Modules (with topics) of the Active curriculum versions of a course, including its combo tracks."""
    stmt = (
        select(CurriculumModule)
        .join(CurriculumVersion, CurriculumVersion.curriculum_version_id == CurriculumModule.curriculum_version_id)
        .where(CurriculumVersion.course_id == course_id, CurriculumVersion.status == "Active")
        .order_by(CurriculumVersion.curriculum_version_id, CurriculumModule.sort_order)
    )
    return list(db.session.execute(stmt).scalars().unique())

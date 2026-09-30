"""Tests, their questions, attempts and interview slots."""
from sqlalchemy import Select, func, select

from config.database import db
from models import CurriculumModule, CurriculumTopic, CurriculumVersion, InterviewSlot, Test, TestAttempt, TestQuestion


def get_test(test_id: int) -> Test | None:
    return db.session.get(Test, test_id)


def list_stmt(filters: dict, batch_clause=None) -> Select:
    """Tests (any release status) narrowed by the filters; batch_clause restricts them to the caller's batches."""
    stmt = select(Test).order_by(Test.batch_id, Test.test_id)
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Test.batch_id))
    for column in ("batch_id", "kind", "release_status"):
        if filters.get(column):
            stmt = stmt.where(getattr(Test, column) == filters[column])
    if filters.get("reviewer_id"):
        stmt = stmt.where(Test.reviewer_user_id == filters["reviewer_id"])
    return stmt


def for_batches(batch_ids: set[int]) -> list[Test]:
    """Every test of these batches: a student's list shows all statuses, but only Available ones can be started."""
    if not batch_ids:
        return []
    return list(db.session.execute(select(Test).where(Test.batch_id.in_(batch_ids)).order_by(Test.test_id)).scalars().unique())


def course_of_module(module_id: int) -> int | None:
    return db.session.execute(
        select(CurriculumVersion.course_id).join(CurriculumModule, CurriculumModule.curriculum_version_id == CurriculumVersion.curriculum_version_id)
        .where(CurriculumModule.module_id == module_id)
    ).scalar()


def course_of_topic(topic_id: int) -> int | None:
    return db.session.execute(
        select(CurriculumVersion.course_id)
        .join(CurriculumModule, CurriculumModule.curriculum_version_id == CurriculumVersion.curriculum_version_id)
        .join(CurriculumTopic, CurriculumTopic.module_id == CurriculumModule.module_id)
        .where(CurriculumTopic.topic_id == topic_id)
    ).scalar()


def question_count(test_id: int) -> int:
    return db.session.execute(select(func.count()).select_from(TestQuestion).where(TestQuestion.test_id == test_id)).scalar_one()


def question_counts(test_ids: list[int]) -> dict[int, int]:
    if not test_ids:
        return {}
    rows = db.session.execute(
        select(TestQuestion.test_id, func.count()).where(TestQuestion.test_id.in_(test_ids)).group_by(TestQuestion.test_id)
    )
    return dict(rows.all())


def total_marks(test_id: int):
    return db.session.execute(select(func.coalesce(func.sum(TestQuestion.marks), 0)).where(TestQuestion.test_id == test_id)).scalar_one()


def slot_count(test_id: int) -> int:
    """Interview slots still on offer or booked (cancelled ones do not count)."""
    return db.session.execute(
        select(func.count()).select_from(InterviewSlot).where(InterviewSlot.test_id == test_id, InterviewSlot.status != "Cancelled")
    ).scalar_one()


def attempt_count(test_id: int) -> int:
    return db.session.execute(select(func.count()).select_from(TestAttempt).where(TestAttempt.test_id == test_id)).scalar_one()


# ---------------------------------------------------------------- attempts

def get_attempt(attempt_id: int) -> TestAttempt | None:
    return db.session.get(TestAttempt, attempt_id)


def attempts_of(test_id: int, enrolment_id: int) -> list[TestAttempt]:
    stmt = select(TestAttempt).where(TestAttempt.test_id == test_id, TestAttempt.enrolment_id == enrolment_id).order_by(TestAttempt.attempt_no)
    return list(db.session.execute(stmt).scalars().unique())


def attempts_for_enrolments(enrolment_ids: set[int], test_ids: list[int]) -> dict[tuple[int, int], list[TestAttempt]]:
    """(test id, enrolment id) -> attempts, oldest first."""
    if not enrolment_ids or not test_ids:
        return {}
    stmt = (
        select(TestAttempt)
        .where(TestAttempt.enrolment_id.in_(enrolment_ids), TestAttempt.test_id.in_(test_ids))
        .order_by(TestAttempt.attempt_no)
    )
    grouped: dict[tuple[int, int], list[TestAttempt]] = {}
    for attempt in db.session.execute(stmt).scalars().unique():
        grouped.setdefault((attempt.test_id, attempt.enrolment_id), []).append(attempt)
    return grouped


def attempts_stmt(filters: dict, batch_clause=None) -> Select:
    """Staff view of attempts: the grading queue (grading_status=Awaiting Grading) and per-test lists."""
    stmt = select(TestAttempt).join(Test, Test.test_id == TestAttempt.test_id).where(TestAttempt.status == "Submitted")
    stmt = stmt.order_by(TestAttempt.submitted_at, TestAttempt.attempt_id)
    if batch_clause is not None:
        stmt = stmt.where(batch_clause(Test.batch_id))
    if filters.get("test_id"):
        stmt = stmt.where(TestAttempt.test_id == filters["test_id"])
    if filters.get("batch_id"):
        stmt = stmt.where(Test.batch_id == filters["batch_id"])
    if filters.get("grading_status"):
        stmt = stmt.where(TestAttempt.grading_status == filters["grading_status"])
    if filters.get("reviewer_id"):
        stmt = stmt.where(Test.reviewer_user_id == filters["reviewer_id"])
    return stmt


def graded_attempts(test_id: int, enrolment_id: int) -> list[TestAttempt]:
    return [a for a in attempts_of(test_id, enrolment_id) if a.grading_status == "Graded"]


def expired_in_progress(now) -> list[TestAttempt]:
    """Attempts still open past their server deadline (auto-submitted the next time anyone reads them)."""
    stmt = select(TestAttempt).where(TestAttempt.status == "In Progress", TestAttempt.deadline_at < now)
    return list(db.session.execute(stmt).scalars().unique())


# ---------------------------------------------------------------- interview slots

def get_slot(slot_id: int) -> InterviewSlot | None:
    return db.session.get(InterviewSlot, slot_id)


def slots_of(test_id: int) -> list[InterviewSlot]:
    stmt = select(InterviewSlot).where(InterviewSlot.test_id == test_id).order_by(InterviewSlot.starts_at, InterviewSlot.slot_id)
    return list(db.session.execute(stmt).scalars().unique())


def booked_slots_for(enrolment_ids: set[int], test_ids: list[int]) -> dict[int, InterviewSlot]:
    """test id -> the student's live booking (pending, confirmed or completed) in that mock interview."""
    if not enrolment_ids or not test_ids:
        return {}
    stmt = select(InterviewSlot).where(
        InterviewSlot.enrolment_id.in_(enrolment_ids), InterviewSlot.test_id.in_(test_ids),
        InterviewSlot.status.in_(("Slot Confirmation Pending", "Confirmed", "Completed")),
    )
    return {s.test_id: s for s in db.session.execute(stmt).scalars().unique()}

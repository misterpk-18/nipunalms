"""Assessments: assignments, versioned submissions and reviews, question bank, tests, attempts, interview slots, results."""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, FetchedValue, ForeignKey, Integer, Numeric, SmallInteger, String, Text, BigInteger,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.batches import Batch
from models.catalog import Course, CurriculumModule, CurriculumTopic
from models.enums import _pg_enum
from models.masters import Branch
from models.students import Enrolment, Student

ASSIGNMENT_KINDS = ("Class assignment", "Module assignment", "Practical lab", "Mini project", "Final project")
ASSIGNMENT_STATUSES = ("Draft", "Released", "Withdrawn")
AI_USE_RULES = ("Allowed with disclosure", "Limited to specified uses", "Not permitted")
REVIEW_OUTCOMES = ("Reviewed", "Resubmission Requested")
QUESTION_TYPES = (
    "Single choice", "Multiple choice", "True / False", "Numeric", "Short answer", "Descriptive", "Coding", "Output prediction",
)
QUESTION_STATUSES = ("Draft", "Approved", "Retired")
QUESTION_DIFFICULTIES = ("Easy", "Medium", "Hard")
TEST_KINDS = ("Practice quiz", "Module test", "Coding exercise", "Mock test", "Mock interview", "Final test")
TEST_RELEASE_STATUSES = ("Configuration Pending", "Not Released", "Released", "Closed")
ATTEMPT_STATUSES = ("In Progress", "Submitted")
GRADING_STATUSES = ("Pending", "Awaiting Grading", "Graded")
SLOT_STATUSES = ("Open", "Slot Confirmation Pending", "Confirmed", "Completed", "Cancelled")
RESULT_STATUSES = ("Provisional", "Moderated", "Published")

AssignmentKind = _pg_enum("assignment_kind", ASSIGNMENT_KINDS)
AssignmentStatus = _pg_enum("assignment_status", ASSIGNMENT_STATUSES)
AiUseRule = _pg_enum("ai_use_rule", AI_USE_RULES)
ReviewOutcome = _pg_enum("review_outcome", REVIEW_OUTCOMES)
QuestionType = _pg_enum("question_type", QUESTION_TYPES)
QuestionStatus = _pg_enum("question_status", QUESTION_STATUSES)
QuestionDifficulty = _pg_enum("question_difficulty", QUESTION_DIFFICULTIES)
TestKind = _pg_enum("test_kind", TEST_KINDS)
TestReleaseStatus = _pg_enum("test_release_status", TEST_RELEASE_STATUSES)
AttemptStatus = _pg_enum("attempt_status", ATTEMPT_STATUSES)
GradingStatus = _pg_enum("attempt_grading_status", GRADING_STATUSES)
SlotStatus = _pg_enum("slot_status", SLOT_STATUSES)
ResultStatus = _pg_enum("result_status", RESULT_STATUSES)


def _marks(value: Decimal | None) -> str | None:
    """Marks travel as strings with two decimals, like money."""
    return None if value is None else f"{value:.2f}"


class Assignment(db.Model):
    __tablename__ = "assignments"

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(AssignmentKind, default="Class assignment")
    brief: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list] = mapped_column(JSONB, default=list)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_resubmissions: Mapped[int] = mapped_column(SmallInteger, default=2)
    late_policy: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    ai_use_rule: Mapped[str] = mapped_column(AiUseRule, default="Allowed with disclosure")
    reviewer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    status: Mapped[str] = mapped_column(AssignmentStatus, default="Draft")
    released_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")
    topic: Mapped[CurriculumTopic | None] = relationship(lazy="joined")
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_user_id], lazy="joined")

    def to_summary(self) -> dict:
        return {"assignment_id": self.assignment_id, "assignment_code": self.assignment_code, "title": self.title}

    def to_dict(self, **extra: Any) -> dict:
        module = self.topic.module if self.topic else None
        return {
            **self.to_summary(),
            "batch": self.batch.to_summary(),
            "branch": self.batch.branch.to_summary(),
            "module": {"module_id": module.module_id, "title": module.title} if module else None,
            "topic": {"topic_id": self.topic.topic_id, "title": self.topic.title} if self.topic else None,
            "kind": self.kind,
            "brief": self.brief,
            "attachments": self.attachments,
            "is_required": self.is_required,
            "max_marks": _marks(self.max_marks),
            "release_at": self.release_at,
            "due_at": self.due_at,
            "closes_at": self.closes_at,
            "max_resubmissions": self.max_resubmissions,
            "late_policy": self.late_policy,
            "ai_use_rule": self.ai_use_rule,
            "reviewer": {"user_id": self.reviewer_user_id, "full_name": self.reviewer.full_name},
            "status": self.status,
            "withdrawn_reason": self.withdrawn_reason,
            **extra,
        }


class SubmissionReview(db.Model):
    __tablename__ = "submission_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignment_submissions.submission_id"), unique=True)
    reviewer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    outcome: Mapped[str] = mapped_column(ReviewOutcome)
    feedback: Mapped[str] = mapped_column(Text)
    marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    resubmission_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    reviewer: Mapped[User] = relationship(lazy="joined")

    def to_dict(self, *, with_marks: bool) -> dict:
        """Marks are provisional until the result is published: students only get them once it is."""
        return {
            "review_id": self.review_id,
            "outcome": self.outcome,
            "feedback": self.feedback,
            "marks": _marks(self.marks) if with_marks else None,
            "resubmission_due_at": self.resubmission_due_at,
            "reviewed_at": self.reviewed_at,
            "reviewer": {"user_id": self.reviewer_user_id, "full_name": self.reviewer.full_name},
        }


class AssignmentSubmission(db.Model):
    __tablename__ = "assignment_submissions"

    submission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignments.assignment_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    version_no: Mapped[int] = mapped_column(Integer)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    body_text: Mapped[str | None] = mapped_column(Text)
    link_url: Mapped[str | None] = mapped_column(String(500))
    file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    ai_disclosure: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_started_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))

    assignment: Mapped[Assignment] = relationship(lazy="joined")
    student: Mapped[Student] = relationship(lazy="joined")
    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    review: Mapped[SubmissionReview | None] = relationship(lazy="joined")

    def to_dict(self, *, with_marks: bool = True, with_review: bool = True) -> dict:
        return {
            "submission_id": self.submission_id,
            "submission_code": self.submission_code,
            "assignment": self.assignment.to_summary(),
            "student": self.student.to_summary(),
            "enrolment_id": self.enrolment_id,
            "version_no": self.version_no,
            "attempt_no": self.attempt_no,
            "body_text": self.body_text,
            "link_url": self.link_url,
            "file": ({"filename": self.original_filename, "mime_type": self.mime_type, "size_bytes": self.file_size_bytes}
                     if self.file_path else None),
            "ai_disclosure": self.ai_disclosure,
            "submitted_at": self.submitted_at,
            "is_late": self.is_late,
            "review_started_at": self.review_started_at,
            "review": self.review.to_dict(with_marks=with_marks) if self.review and with_review else None,
        }


class Question(db.Model):
    __tablename__ = "questions"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    question_type: Mapped[str] = mapped_column(QuestionType)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB, default=list)
    answer_key: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(Text)
    marks: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1"))
    difficulty: Mapped[str] = mapped_column(QuestionDifficulty, default="Medium")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[str] = mapped_column(QuestionStatus, default="Draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_question_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("questions.question_id"))
    author_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    topic: Mapped[CurriculumTopic | None] = relationship(lazy="joined")
    author: Mapped[User] = relationship(foreign_keys=[author_user_id], lazy="joined")

    def to_dict(self) -> dict:
        """The staff view, answer key included. Students never receive this shape (see TestQuestion.to_paper)."""
        return {
            "question_id": self.question_id,
            "question_code": self.question_code,
            "course": self.course.to_summary(),
            "branch": self.branch.to_summary(),
            "topic": {"topic_id": self.topic.topic_id, "title": self.topic.title} if self.topic else None,
            "question_type": self.question_type,
            "stem": self.stem,
            "options": self.options,
            "answer_key": self.answer_key,
            "explanation": self.explanation,
            "marks": _marks(self.marks),
            "difficulty": self.difficulty,
            "tags": list(self.tags or []),
            "status": self.status,
            "version": self.version,
            "parent_question_id": self.parent_question_id,
            "author": {"user_id": self.author_user_id, "full_name": self.author.full_name},
            "approved_at": self.approved_at,
        }


class Test(db.Model):
    __tablename__ = "tests"
    __test__ = False  # not a pytest class

    test_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    module_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_modules.module_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(TestKind)
    instructions: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_use_rule: Mapped[str] = mapped_column(AiUseRule, default="Not permitted")
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts_allowed: Mapped[int | None] = mapped_column(Integer)
    pass_marks: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    release_status: Mapped[str] = mapped_column(TestReleaseStatus, default="Configuration Pending")
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")
    module: Mapped[CurriculumModule | None] = relationship(lazy="joined")
    topic: Mapped[CurriculumTopic | None] = relationship(lazy="joined")
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_user_id], lazy="joined")
    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test", order_by="TestQuestion.position", cascade="all, delete-orphan"
    )

    def to_summary(self) -> dict:
        return {"test_id": self.test_id, "test_code": self.test_code, "title": self.title, "kind": self.kind}

    def to_dict(self, **extra: Any) -> dict:
        return {
            **self.to_summary(),
            "batch": self.batch.to_summary(),
            "branch": self.batch.branch.to_summary(),
            "module": {"module_id": self.module.module_id, "title": self.module.title} if self.module else None,
            "topic": {"topic_id": self.topic.topic_id, "title": self.topic.title} if self.topic else None,
            "instructions": self.instructions,
            "is_required": self.is_required,
            "ai_use_rule": self.ai_use_rule,
            "duration_minutes": self.duration_minutes,
            "opens_at": self.opens_at,
            "closes_at": self.closes_at,
            "attempts_allowed": self.attempts_allowed,
            "pass_marks": _marks(self.pass_marks),
            "release_status": self.release_status,
            "approved_at": self.approved_at,
            "released_at": self.released_at,
            "reviewer": {"user_id": self.reviewer_user_id, "full_name": self.reviewer.full_name},
            **extra,
        }


class TestQuestion(db.Model):
    """One question of a test as frozen when it was selected: what every attempt is shown and scored against."""

    __tablename__ = "test_questions"
    __test__ = False  # not a pytest class

    test_id: Mapped[int] = mapped_column(Integer, ForeignKey("tests.test_id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.question_id"), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    question_version: Mapped[int] = mapped_column(Integer)
    question_type: Mapped[str] = mapped_column(QuestionType)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB, default=list)
    answer_key: Mapped[dict] = mapped_column(JSONB)
    marks: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    test: Mapped[Test] = relationship(back_populates="questions")

    def to_paper(self) -> dict:
        """What a student sees: no key, no explanation."""
        return {
            "question_id": self.question_id,
            "position": self.position,
            "question_type": self.question_type,
            "stem": self.stem,
            "options": self.options,
            "marks": _marks(self.marks),
        }

    def to_dict(self) -> dict:
        return {**self.to_paper(), "question_version": self.question_version, "answer_key": self.answer_key}


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"

    answer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_attempts.attempt_id"))
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.question_id"))
    answer: Mapped[Any] = mapped_column(JSONB(none_as_null=True))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    awarded_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_auto_graded: Mapped[bool] = mapped_column(Boolean, default=False)
    grader_feedback: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestAttempt(db.Model):
    __tablename__ = "test_attempts"
    __test__ = False  # not a pytest class

    attempt_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(Integer, ForeignKey("tests.test_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    attempt_no: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submit_reason: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(AttemptStatus, default="In Progress")
    grading_status: Mapped[str] = mapped_column(GradingStatus, default="Pending")
    receipt_code: Mapped[str | None] = mapped_column(String(30), unique=True)
    auto_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    graded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    test: Mapped[Test] = relationship(lazy="joined")
    student: Mapped[Student] = relationship(lazy="joined")
    enrolment: Mapped[Enrolment] = relationship()
    answers: Mapped[list[AttemptAnswer]] = relationship(order_by="AttemptAnswer.question_id", cascade="all, delete-orphan")

    def to_summary(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "attempt_no": self.attempt_no,
            "status": self.status,
            "grading_status": self.grading_status,
            "started_at": self.started_at,
            "submitted_at": self.submitted_at,
            "receipt_code": self.receipt_code,
        }


class InterviewSlot(db.Model):
    __tablename__ = "interview_slots"

    slot_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(Integer, ForeignKey("tests.test_id"))
    trainer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(SlotStatus, default="Open")
    enrolment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("students.student_id"))
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    strengths: Mapped[str | None] = mapped_column(Text)
    improvements: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    test: Mapped[Test] = relationship(lazy="joined")
    trainer: Mapped[User] = relationship(lazy="joined")
    student: Mapped[Student | None] = relationship(lazy="joined")

    def to_dict(self, *, viewer_is_student: bool = False) -> dict:
        """A student sees the offered times and their own booking; other students' names never leave staff APIs."""
        return {
            "slot_id": self.slot_id,
            "test": self.test.to_summary(),
            "trainer": {"user_id": self.trainer_user_id, "full_name": self.trainer.full_name},
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "status": self.status,
            "student": None if viewer_is_student or self.student is None else self.student.to_summary(),
            "booked_at": self.booked_at,
            "confirmed_at": self.confirmed_at,
            "completed_at": self.completed_at,
            "rating": self.rating,
            "strengths": self.strengths,
            "improvements": self.improvements,
            "next_action": self.next_action,
        }


class Result(db.Model):
    __tablename__ = "results"

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    assignment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("assignments.assignment_id"))
    test_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tests.test_id"))
    submission_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("assignment_submissions.submission_id"))
    attempt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("test_attempts.attempt_id"))
    max_marks: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    provisional_marks: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    moderated_marks: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    final_marks: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    status: Mapped[str] = mapped_column(ResultStatus, default="Provisional")
    moderation_reason: Mapped[str | None] = mapped_column(Text)
    moderated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")
    batch: Mapped[Batch] = relationship(lazy="joined")
    assignment: Mapped[Assignment | None] = relationship(lazy="joined")
    test: Mapped[Test | None] = relationship(lazy="joined")

    @property
    def counting_marks(self) -> Decimal:
        """What would be published: the moderated marks when the Academic Coordinator adjusted them, else the trainer's."""
        return self.moderated_marks if self.moderated_marks is not None else self.provisional_marks

    def item(self) -> dict:
        if self.assignment is not None:
            return {"kind": "Assignment", "item_id": self.assignment_id, "code": self.assignment.assignment_code,
                    "title": self.assignment.title, "type": self.assignment.kind}
        return {"kind": "Test", "item_id": self.test_id, "code": self.test.test_code, "title": self.test.title,
                "type": self.test.kind}

    def to_dict(self) -> dict:
        """The staff view: every stage of the marks, so a moderation change is visible."""
        return {
            "result_id": self.result_id,
            "student": self.student.to_summary(),
            "enrolment_id": self.enrolment_id,
            "batch": self.batch.to_summary(),
            "item": self.item(),
            "max_marks": _marks(self.max_marks),
            "provisional_marks": _marks(self.provisional_marks),
            "moderated_marks": _marks(self.moderated_marks),
            "final_marks": _marks(self.final_marks),
            "status": self.status,
            "moderation_reason": self.moderation_reason,
            "moderated_at": self.moderated_at,
            "published_at": self.published_at,
        }

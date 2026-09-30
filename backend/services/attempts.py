"""Test attempts (Module 20 §4-§6): the server owns the clock, the paper and the receipt.

Starting records `started_at` and `deadline_at = min(start + duration, window end)`. A reconnect resumes the same attempt with the
time left. Answers are saved only before the deadline; once it passes, the next read (or save) submits the saved answers once,
with the deadline as the effective submission time, and issues the receipt. Objective questions are scored on submission; written
and coding answers wait for the trainer. Formal results stay provisional until the Academic Coordinator publishes them.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config.database import db
from models import AttemptAnswer, TestAttempt
from repositories import results as results_repo
from repositories import tests as tests_repo
from repositories.common import paginate
from services import assessment_scope as access
from services import results, scope, tests as tests_service
from services.assessment_rules import effective_status, is_formal, visible_score
from services.context import current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.scoring import is_auto_graded, score_answer

MANUAL_TYPES = ("Descriptive", "Coding")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- lifecycle

def _deadline(test, started_at: datetime) -> datetime | None:
    """The server deadline: start + duration, never past the window end; None only for an untimed test without a window end."""
    candidates = []
    if test.duration_minutes:
        candidates.append(started_at + timedelta(minutes=test.duration_minutes))
    if test.closes_at is not None:
        candidates.append(test.closes_at)
    return min(candidates) if candidates else None


def start_attempt(test_id: int) -> tuple[TestAttempt, bool]:
    """Start a new attempt, or resume the one in progress. Returns (attempt, created)."""
    if not access.is_student():
        raise Forbidden("Only students take tests")
    test = tests_service.load_test(test_id)
    enrolment = access.student_seat(test.batch_id)
    now = now_utc()
    attempts = tests_repo.attempts_of(test_id, enrolment.enrolment_id)
    running = next((a for a in attempts if a.status == "In Progress"), None)
    if running is not None:
        expire_if_due(running, now)
        if running.status == "In Progress":
            return running, False

    status = effective_status(test, now)
    if status != "Available":
        raise BusinessRule(f"This test is {status}")
    if test.kind == "Mock interview":
        raise BusinessRule("A mock interview is booked with your trainer, not attempted online")
    if tests_repo.question_count(test_id) == 0:
        raise BusinessRule("This test has no questions yet")
    used = sum(1 for a in attempts if a.status == "Submitted")
    if test.attempts_allowed is not None and used >= test.attempts_allowed:
        raise BusinessRule("You have used every attempt allowed for this test")

    attempt = TestAttempt(test_id=test_id, enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id,
                          attempt_no=len(attempts) + 1, started_at=now, deadline_at=_deadline(test, now))
    db.session.add(attempt)
    db.session.flush()
    return attempt, True


def expire_if_due(attempt: TestAttempt, now: datetime) -> bool:
    """Submit an attempt whose deadline has passed, as of the deadline itself. Returns whether it was submitted now."""
    if attempt.status == "In Progress" and attempt.deadline_at is not None and now > attempt.deadline_at:
        finalize(attempt, "Timeout", attempt.deadline_at)
        return True
    return False


def finalize(attempt: TestAttempt, reason: str, submitted_at: datetime) -> None:
    """Freeze the saved answers, issue the receipt, score what can be scored and queue the rest for the trainer."""
    test = attempt.test
    saved = {a.question_id: a for a in attempt.answers}
    for question in test.questions:  # a blank placeholder for every unanswered question, so it can carry marks
        if question.question_id not in saved:
            row = AttemptAnswer(attempt_id=attempt.attempt_id, question_id=question.question_id, answer=None)
            db.session.add(row)
            saved[question.question_id] = row

    attempt.status, attempt.submitted_at, attempt.submit_reason = "Submitted", submitted_at, reason
    db.session.flush()  # the database issues the receipt
    db.session.refresh(attempt)

    auto_total, manual_pending = Decimal("0"), False
    for question in test.questions:
        row = saved[question.question_id]
        score = score_answer(question.question_type, question.answer_key, row.answer, question.marks)
        if score is None:
            manual_pending = True
            continue
        row.awarded_marks, row.is_auto_graded = score, True
        auto_total += score
    attempt.auto_score = auto_total
    if manual_pending:
        attempt.grading_status = "Awaiting Grading"
    else:
        _complete_grading(attempt, auto_total, None)
    db.session.flush()


def _complete_grading(attempt: TestAttempt, total: Decimal, grader_id: int | None) -> None:
    attempt.total_score, attempt.grading_status = total, "Graded"
    attempt.graded_by, attempt.graded_at = grader_id, now_utc()
    db.session.flush()
    _record_result(attempt)


def _record_result(attempt: TestAttempt) -> None:
    """Formal tests: the best graded attempt is the student's provisional result (published results are never replaced)."""
    test = attempt.test
    if not is_formal(test):
        return
    existing = results_repo.for_test(test.test_id, attempt.enrolment_id)
    if existing is not None and existing.status == "Published":
        return
    best = max(tests_repo.graded_attempts(test.test_id, attempt.enrolment_id), key=lambda a: a.total_score)
    results.upsert_provisional(enrolment=attempt.enrolment, batch_id=test.batch_id, max_marks=Decimal(tests_repo.total_marks(test.test_id)),
                               marks=best.total_score, test_id=test.test_id, attempt_id=best.attempt_id)


# ---------------------------------------------------------------- reads

def load_attempt(attempt_id: int) -> TestAttempt:
    """Students only their own attempts; staff by batch scope. Reading submits an attempt that ran past its deadline."""
    attempt = tests_repo.get_attempt(attempt_id)
    if attempt is None:
        raise NotFound("Attempt not found")
    if access.is_student():
        if attempt.student_id != current_user().student_id:
            raise NotFound("Attempt not found")
    else:
        scope.assert_can_view_batch(attempt.test.batch)
    expire_if_due(attempt, now_utc())
    return attempt


def _remaining_seconds(attempt: TestAttempt, now: datetime) -> int | None:
    if attempt.status != "In Progress" or attempt.deadline_at is None:
        return None
    return max(int((attempt.deadline_at - now).total_seconds()), 0)


def student_payload(attempt: TestAttempt) -> dict:
    """The paper as the student sees it (no keys), their saved answers, the clock and, once graded, the score practice allows."""
    now = now_utc()
    test = attempt.test
    answers = {str(a.question_id): a.answer for a in attempt.answers if a.answer is not None}
    score = visible_score(test, attempt)
    return {
        "attempt": {**attempt.to_summary(), "deadline_at": attempt.deadline_at, "submit_reason": attempt.submit_reason,
                    "remaining_seconds": _remaining_seconds(attempt, now), "score": None if score is None else f"{score:.2f}",
                    "total_marks": f"{tests_repo.total_marks(test.test_id):.2f}"},
        "test": {**test.to_summary(), "duration_minutes": test.duration_minutes, "instructions": test.instructions,
                 "ai_use_rule": test.ai_use_rule, "is_formal": is_formal(test)},
        "questions": [q.to_paper() for q in test.questions],
        "answers": answers,
        "server_time": now,
    }


def staff_payload(attempt: TestAttempt) -> dict:
    """The graders' view: each question with its key, the student's answer, marks and feedback."""
    test = attempt.test
    answers = {a.question_id: a for a in attempt.answers}
    questions = []
    for q in test.questions:
        row = answers.get(q.question_id)
        questions.append({**q.to_dict(), "answer": row.answer if row else None,
                          "awarded_marks": None if row is None or row.awarded_marks is None else f"{row.awarded_marks:.2f}",
                          "is_auto_graded": bool(row and row.is_auto_graded), "grader_feedback": row.grader_feedback if row else None,
                          "needs_grading": q.question_type in MANUAL_TYPES and not (row and row.awarded_marks is not None)})
    can_grade = access.can_manage_batch(test.batch)
    return {
        "attempt": {**attempt.to_summary(), "deadline_at": attempt.deadline_at, "submit_reason": attempt.submit_reason,
                    "auto_score": None if attempt.auto_score is None else f"{attempt.auto_score:.2f}",
                    "total_score": None if attempt.total_score is None else f"{attempt.total_score:.2f}",
                    "total_marks": f"{tests_repo.total_marks(test.test_id):.2f}"},
        "student": attempt.student.to_summary(),
        "test": {**test.to_summary(), "batch": test.batch.to_summary(), "is_formal": is_formal(test)},
        "questions": questions if can_grade or access.can_moderate_batch(test.batch) else [],
        "can_grade": can_grade,
    }


def get_attempt(attempt_id: int) -> dict:
    attempt = load_attempt(attempt_id)
    return student_payload(attempt) if access.is_student() else staff_payload(attempt)


def list_attempts(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Staff: submitted attempts of the tests they see (the grading queue: grading_status=Awaiting Grading)."""
    if filters.pop("reviewer_me", False):
        filters["reviewer_id"] = current_user().user_id
    if filters.get("test_id"):
        tests_service.load_test(filters["test_id"])
    if filters.get("batch_id"):
        access.load_batch(filters["batch_id"])
    items, meta = paginate(tests_repo.attempts_stmt(filters, access.visible_batch_clause), page, per_page)
    rows = []
    for attempt in items:
        answers = {a.question_id: a for a in attempt.answers}
        pending = sum(1 for q in attempt.test.questions if q.question_type in MANUAL_TYPES
                      and not (answers.get(q.question_id) and answers[q.question_id].awarded_marks is not None))
        rows.append({**attempt.to_summary(), "student": attempt.student.to_summary(), "test": attempt.test.to_summary(),
                     "batch": attempt.test.batch.to_summary(), "auto_score": None if attempt.auto_score is None else f"{attempt.auto_score:.2f}",
                     "total_score": None if attempt.total_score is None else f"{attempt.total_score:.2f}",
                     "total_marks": f"{tests_repo.total_marks(attempt.test_id):.2f}", "manual_pending": pending})
    return rows, meta


# ---------------------------------------------------------------- answering

def _own_open_attempt(attempt_id: int) -> TestAttempt:
    if not access.is_student():
        raise Forbidden("Only the student can answer their attempt")
    return load_attempt(attempt_id)


def _check_answer_shape(question, value) -> None:
    """Reject an answer that cannot be a valid response to the question (wrong shape or an option that does not exist)."""
    if value is None:
        return
    keys = {o["key"] for o in question.options}
    kind = question.question_type
    ok = {
        "Single choice": isinstance(value, str) and value in keys,
        "Multiple choice": isinstance(value, list) and set(value) <= keys and all(isinstance(v, str) for v in value),
        "True / False": isinstance(value, bool),
        "Numeric": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(kind, isinstance(value, str) and len(value) <= 20000)
    if not ok:
        raise ValidationError("Invalid request data", {f"answers.{question.question_id}": [f"Not a valid answer for a {kind} question"]})


def _save(attempt: TestAttempt, answers: dict) -> None:
    by_id = {q.question_id: q for q in attempt.test.questions}
    existing = {a.question_id: a for a in attempt.answers}
    parsed: dict[int, object] = {}
    for raw_id, value in answers.items():
        try:
            question_id = int(raw_id)
        except (TypeError, ValueError):
            raise ValidationError("Invalid request data", {"answers": [f"'{raw_id}' is not a question id"]}) from None
        if question_id not in by_id:
            raise ValidationError("Invalid request data", {f"answers.{raw_id}": ["This question is not part of the test"]})
        _check_answer_shape(by_id[question_id], value)
        parsed[question_id] = value
    for question_id, value in parsed.items():
        row = existing.get(question_id)
        if row is None:
            db.session.add(AttemptAnswer(attempt_id=attempt.attempt_id, question_id=question_id, answer=value))
        elif row.answer != value:
            row.answer = value
    db.session.flush()
    db.session.expire(attempt, ["answers"])


def save_answers(attempt_id: int, answers: dict) -> dict:
    """Autosave. After the deadline nothing is accepted: the saved answers are submitted and the response says so."""
    attempt = _own_open_attempt(attempt_id)
    now = now_utc()
    if attempt.status == "Submitted":
        return {"accepted": False, "status": "Submitted", "receipt_code": attempt.receipt_code, "remaining_seconds": None, "saved_at": None}
    _save(attempt, answers)
    db.session.refresh(attempt)
    return {"accepted": True, "status": attempt.status, "receipt_code": None, "remaining_seconds": _remaining_seconds(attempt, now),
            "saved_at": now}


def submit_attempt(attempt_id: int, answers: dict | None) -> dict:
    """Submit for grading and get the receipt. Repeating the call returns the same receipt."""
    attempt = _own_open_attempt(attempt_id)
    if attempt.status == "In Progress":
        if answers:
            _save(attempt, answers)
        finalize(attempt, "Student", now_utc())
    return student_payload(attempt)


# ---------------------------------------------------------------- grading

def grade_attempt(attempt_id: int, grades: list[dict]) -> dict:
    """The trainer marks written and coding answers. When every one is marked the attempt is Graded and, for a formal test,
    the score becomes the student's provisional result."""
    attempt = load_attempt(attempt_id)
    access.assert_can_manage(attempt.test.batch)
    if attempt.status != "Submitted":
        raise BusinessRule("Only a submitted attempt can be graded")
    if attempt.grading_status == "Graded":
        raise BusinessRule("This attempt is already graded")
    by_id = {q.question_id: q for q in attempt.test.questions}
    answers = {a.question_id: a for a in attempt.answers}
    now, user = now_utc(), current_user()
    for grade in grades:
        question = by_id.get(grade["question_id"])
        if question is None:
            raise ValidationError("Invalid request data", {"grades": [f"Question {grade['question_id']} is not part of the test"]})
        if is_auto_graded(question.question_type):
            raise BusinessRule(f"Question {question.position} is scored automatically")
        if grade["marks"] > question.marks:
            raise ValidationError("Invalid request data", {"grades": [f"Question {question.position}: marks can't exceed {question.marks:.2f}"]})
        row = answers.get(question.question_id)
        if row is None:
            row = AttemptAnswer(attempt_id=attempt.attempt_id, question_id=question.question_id, answer=None)
            db.session.add(row)
            answers[question.question_id] = row
        row.awarded_marks, row.grader_feedback = grade["marks"], grade.get("feedback")
        row.graded_by, row.graded_at = user.user_id, now
    db.session.flush()

    if all(answers.get(q.question_id) is not None and answers[q.question_id].awarded_marks is not None for q in attempt.test.questions):
        _complete_grading(attempt, sum((answers[q.question_id].awarded_marks for q in attempt.test.questions), Decimal("0")), user.user_id)
    return staff_payload(attempt)

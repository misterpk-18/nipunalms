"""Rules about a test definition that several services read: what counts as formal, what is still missing, and its status now."""
from datetime import datetime

from models import Test, TestAttempt

FORMAL_KINDS = ("Module test", "Coding exercise", "Final test")

# Approved starting settings per kind (Module 20 §4); the Academic Coordinator confirms course-specific values before release.
# duration in minutes (None = untimed) and attempts allowed (None = repeat within the availability window)
KIND_DEFAULTS = {
    "Practice quiz": {"duration_minutes": None, "attempts_allowed": None},
    "Module test": {"duration_minutes": 30, "attempts_allowed": 1},
    "Final test": {"duration_minutes": 60, "attempts_allowed": 1},
    "Coding exercise": {"duration_minutes": 90, "attempts_allowed": 1},
    "Mock test": {"duration_minutes": 90, "attempts_allowed": 1},
    "Mock interview": {"duration_minutes": 30, "attempts_allowed": 1},
}


def is_formal(test: Test) -> bool:
    """Formal tests need pass marks, Academic Coordinator approval and published results; practice and mocks stay optional."""
    return test.kind in FORMAL_KINDS or test.is_required


def effective_status(test: Test, now: datetime) -> str:
    """The status a student sees: Configuration Pending, Not Released, Scheduled, Available or Closed."""
    if test.release_status != "Released":
        return test.release_status
    if test.opens_at is not None and now < test.opens_at:
        return "Scheduled"
    if test.closes_at is not None and now > test.closes_at:
        return "Closed"
    return "Available"


def configuration_gaps(test: Test, question_count: int, slot_count: int) -> list[str]:
    """What still has to be set before the test can be released (empty = ready)."""
    gaps = []
    if test.kind == "Mock interview":
        if slot_count == 0:
            gaps.append("Offer at least one interview slot")
    elif question_count == 0:
        gaps.append("Select the questions")
    if is_formal(test):
        if test.pass_marks is None:
            gaps.append("Set the pass marks")
        if test.closes_at is None:
            gaps.append("Set the closing time")
        if test.approved_at is None:
            gaps.append("Academic Coordinator approval")
    return gaps


def visible_score(test: Test, attempt: TestAttempt):
    """The score a student may see for an attempt: automated feedback for practice and mocks once graded; never a formal
    score (that waits for publication)."""
    if is_formal(test) or attempt.grading_status != "Graded":
        return None
    return attempt.total_score

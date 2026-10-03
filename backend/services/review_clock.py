"""Review targets (Module 19 §8, Module 20 §8): results are reviewed and ready for publication within 3 / 5 / 7 academic
working days of the accepted submission, counted on the Academic Calendar (services/working_days.py)."""
from datetime import date, datetime

from config.timezone import IST, today_ist
from services import working_days

ASSIGNMENT_TARGET_DAYS = {"Class assignment": 3, "Module assignment": 3, "Practical lab": 3, "Mini project": 5, "Final project": 7}
TEST_TARGET_DAYS = {"Module test": 3, "Mock test": 3, "Mock interview": 3, "Coding exercise": 5, "Final test": 7}


def review_due(kind: str, submitted_at: datetime | None, branch_id: int, *, tests: bool = False) -> dict | None:
    """{due_on, target_days, overdue} for a submission or attempt still to review; None when no target applies."""
    target = (TEST_TARGET_DAYS if tests else ASSIGNMENT_TARGET_DAYS).get(kind)
    if target is None or submitted_at is None:
        return None
    due_on: date = working_days.add_working_days(submitted_at.astimezone(IST).date(), target, branch_id)
    return {"due_on": due_on, "target_days": target, "overdue": today_ist() > due_on}

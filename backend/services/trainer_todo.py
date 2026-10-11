"""What waits for a trainer, counted once for the Today to-do list and the navigation badges (UX plan U12): assignments to
review, test attempts to mark, classes with no class log, and the attendance work (classes still to mark, corrections waiting
for a decision, recoveries to verify)."""
from datetime import datetime

from sqlalchemy import func, select

from config.database import db
from repositories import class_flow as flow_repo
from repositories import tests as tests_repo
from services import assessment_scope, attendance, class_flow, submissions
from services.context import current_user


def assignments_to_review() -> int:
    _, meta = submissions.list_submissions({"status": "Awaiting Review", "reviewer_me": True}, 1, 1)
    return meta["total"]


def attempts_to_mark() -> int:
    stmt = tests_repo.attempts_stmt({"grading_status": "Awaiting Grading", "reviewer_id": current_user().user_id}, assessment_scope.visible_batch_clause)
    return db.session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()


def class_logs_missing(now: datetime, limit: int = 5) -> tuple[int, list]:
    """(how many, the oldest few): the trainer's classes that ended and were never logged."""
    user_id, since = current_user().user_id, class_flow.log_since(now)
    return flow_repo.unlogged_count(user_id, since, now), flow_repo.unlogged_sessions(user_id, since, now, limit)


def attendance_work() -> dict:
    """The three kinds of attendance work in the trainer's batches."""
    classes = attendance.list_register_sessions({"attendance": "pending"}, 1, 1)[1]["total"]
    corrections = attendance.list_corrections({"status": "Pending"}, 1, 1)[1]["total"]
    recoveries = attendance.list_recoveries({"status": "Approved"}, 1, 1)[1]["total"]
    return {"classes": classes, "corrections": corrections, "recoveries": recoveries, "total": classes + corrections + recoveries}

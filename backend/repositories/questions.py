"""Question bank."""
from sqlalchemy import Select, or_, select

from config.database import db
from models import Question


def get_question(question_id: int) -> Question | None:
    return db.session.get(Question, question_id)


def list_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    """Questions of the given branches (None = all), narrowed by course, topic, type, status, difficulty and a text search."""
    stmt = select(Question).order_by(Question.question_id.desc())
    if branch_ids is not None:
        stmt = stmt.where(Question.branch_id.in_(branch_ids))
    for column in ("course_id", "topic_id", "question_type", "status", "difficulty", "branch_id"):
        if filters.get(column):
            stmt = stmt.where(getattr(Question, column) == filters[column])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Question.stem.ilike(pattern), Question.question_code.ilike(pattern), Question.tags.contains([filters["q"].lower()])))
    return stmt

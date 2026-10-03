"""Question bank."""
from sqlalchemy import Select, and_, false, or_, select

from config.database import db
from models import Question


def get_question(question_id: int) -> Question | None:
    return db.session.get(Question, question_id)


def list_stmt(filters: dict, branch_ids: set[int] | None, taught: set[tuple[int, int]], author_user_id: int) -> Select:
    """Questions of the given branches (None = all), of the (branch, course) pairs a trainer teaches and of their own authoring,
    narrowed by course, topic, type, status, difficulty and a text search."""
    stmt = select(Question).order_by(Question.question_id.desc())
    if branch_ids is not None:
        stmt = stmt.where(or_(
            Question.branch_id.in_(branch_ids) if branch_ids else false(),
            Question.author_user_id == author_user_id,
            *(and_(Question.branch_id == branch_id, Question.course_id == course_id) for branch_id, course_id in taught),
        ))
    for column in ("course_id", "topic_id", "question_type", "status", "difficulty", "branch_id"):
        if filters.get(column):
            stmt = stmt.where(getattr(Question, column) == filters[column])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Question.stem.ilike(pattern), Question.question_code.ilike(pattern), Question.tags.contains([filters["q"].lower()])))
    return stmt

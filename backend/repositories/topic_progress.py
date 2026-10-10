"""Reads over the `topic_progress` view (db/109)."""
from sqlalchemy import select

from config.database import db
from models import TopicProgress


def for_enrolment(enrolment_id: int) -> dict[int, TopicProgress]:
    """topic_id -> the enrolment's progress on that topic."""
    stmt = select(TopicProgress).where(TopicProgress.enrolment_id == enrolment_id)
    return {row.topic_id: row for row in db.session.execute(stmt).scalars()}


def for_enrolments(enrolment_ids: list[int]) -> dict[int, dict[int, TopicProgress]]:
    """enrolment_id -> {topic_id -> progress}."""
    out: dict[int, dict[int, TopicProgress]] = {i: {} for i in enrolment_ids}
    if enrolment_ids:
        for row in db.session.execute(select(TopicProgress).where(TopicProgress.enrolment_id.in_(enrolment_ids))).scalars():
            out[row.enrolment_id][row.topic_id] = row
    return out

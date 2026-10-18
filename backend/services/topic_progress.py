"""How far a student is through a course, counted in topics (UX phase U8).

A topic is Done when the student attended its class (or recovered it) or watched its recording, and every required
assignment and required test of the topic is handed in (`topic_progress`, db/109). Module and course percentages are the share
of topics Done. These are the student's own "what have I finished" counts; the four progress measures (delivery, attendance,
required learning, engagement) are separate and keep their own rules.
"""
from dataclasses import dataclass

from models import CourseTopic, Enrolment
from repositories import catalog as catalog_repo
from repositories import topic_progress as repo


@dataclass
class Counts:
    done: int
    total: int

    @property
    def percent(self) -> int | None:
        return round(self.done * 100 / self.total) if self.total else None

    def to_dict(self) -> dict:
        return {"done": self.done, "total": self.total, "percent": self.percent}


def followed_outlines(enrolment: Enrolment) -> list[tuple[int, int | None]]:
    """The outlines the enrolment follows as (course_id, component_id), in the order a student studies them: each combo track,
    else the course's one."""
    return catalog_repo.followed_outlines(enrolment)


def ordered_topics(outline: tuple[int, int | None]) -> list[CourseTopic]:
    return [topic for module in catalog_repo.outline_for(*outline) for topic in module.topics]


def rows_for(enrolment_id: int) -> dict:
    """topic_id -> the enrolment's progress row for that topic."""
    return repo.for_enrolment(enrolment_id)


def module_counts(enrolment_id: int) -> dict[int, Counts]:
    counts: dict[int, Counts] = {}
    for row in repo.for_enrolment(enrolment_id).values():
        c = counts.setdefault(row.module_id, Counts(0, 0))
        c.total += 1
        c.done += row.is_done
    return counts


def course_counts(enrolment: Enrolment, rows: dict | None = None) -> Counts:
    """Topics Done out of every topic of the outlines the enrolment follows."""
    rows = repo.for_enrolment(enrolment.enrolment_id) if rows is None else rows
    return Counts(sum(r.is_done for r in rows.values()), len(rows))


def outline_counts(enrolment_id: int) -> dict[tuple[int, int | None], Counts]:
    """Topics Done per outline, keyed (course_id, component_id)."""
    counts: dict[tuple[int, int | None], Counts] = {}
    for row in repo.for_enrolment(enrolment_id).values():
        c = counts.setdefault((row.course_id, row.component_id), Counts(0, 0))
        c.total += 1
        c.done += row.is_done
    return counts


def continue_topic(enrolment: Enrolment, rows: dict | None = None) -> dict | None:
    """Where to carry on: the first topic, in study order, that is not Done. None when every topic is Done or the course has no outline yet."""
    rows = repo.for_enrolment(enrolment.enrolment_id) if rows is None else rows
    for outline in followed_outlines(enrolment):
        for topic in ordered_topics(outline):
            progress = rows.get(topic.topic_id)
            if progress is not None and not progress.is_done:
                return {"topic_id": topic.topic_id, "title": topic.title, "title_te": topic.title_te,
                        "module": {"module_id": topic.module.module_id, "title": topic.module.title, "title_te": topic.module.title_te},
                        "status": progress.status}
    return None


def next_topic(enrolment: Enrolment, topic_id: int) -> dict | None:
    """The topic after this one in study order, within the same outline."""
    for outline in followed_outlines(enrolment):
        topics = ordered_topics(outline)
        for index, topic in enumerate(topics):
            if topic.topic_id == topic_id:
                after = topics[index + 1] if index + 1 < len(topics) else None
                return None if after is None else {"topic_id": after.topic_id, "title": after.title, "title_te": after.title_te}
    return None

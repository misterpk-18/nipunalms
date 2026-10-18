"""The topic hub (`GET /me/topics/{id}`, UX phase U8): everything a student has for one topic on one page: its classes, the
recording, materials, assignments and tests, how far they are, and the next topic. Only topics of the student's own courses
are reachable (anything else is a 404, as on the topic page)."""
from sqlalchemy import select

from config.database import db
from models import AttendanceRecord
from repositories import content as content_repo
from services import assignments as assignments_service
from services import content as content_service
from services import learning, recordings, topic_progress
from services import tests as tests_service
from services.errors import Forbidden

ALL = 500  # a student's task list is short; one page holds it


def _attendance(session_ids: list[int], enrolment_id: int) -> dict[int, str]:
    if not session_ids:
        return {}
    stmt = select(AttendanceRecord.session_id, AttendanceRecord.status).where(AttendanceRecord.session_id.in_(session_ids),
                                                                            AttendanceRecord.enrolment_id == enrolment_id)
    return {session_id: str(status) for session_id, status in db.session.execute(stmt).all()}


def _work(topic_id: int, enrolment_id: int) -> tuple[list[dict], list[dict]]:
    """The topic's released assignments and its tests, each with the student's own state (the rows the task screens show)."""
    def mine(rows: list[dict]) -> list[dict]:
        return [r for r in rows if r["topic"] and r["topic"]["topic_id"] == topic_id and r["my"]["enrolment_id"] == enrolment_id]

    assignments, _ = assignments_service.list_assignments({}, 1, ALL)
    tests, _ = tests_service.list_tests({}, 1, ALL)
    return mine(assignments), mine(tests)


def get_hub(topic_id: int) -> dict:
    page = learning.get_topic(topic_id)
    context = page.context
    if context is None:
        raise Forbidden("This is a student view")
    enrolment, topic = context.enrolment, page.topic

    progress = topic_progress.rows_for(enrolment.enrolment_id).get(topic.topic_id)
    session_ids = [s.session_id for s in page.sessions]
    attendance = _attendance(session_ids, enrolment.enrolment_id)
    assignment_rows, test_rows = _work(topic.topic_id, enrolment.enrolment_id)
    track = content_repo.track_labels({topic.module.component_id}).get(topic.module.component_id)

    return {
        "topic": {"topic_id": topic.topic_id, "title": topic.title, "title_te": topic.title_te, "outcome": topic.outcome,
                  "is_required": topic.is_required, "instructional_minutes": topic.instructional_minutes},
        "module": {"module_id": topic.module.module_id, "title": topic.module.title, "title_te": topic.module.title_te},
        "track": track,
        "enrolment": enrolment.to_summary(),
        "progress": progress.to_dict() if progress else None,
        "sessions": [{**s.to_summary(), "mode": s.mode, "trainer": s.trainer.full_name, "attendance": attendance.get(s.session_id)}
                     for s in page.sessions],
        "recordings": [r for r in recordings.student_recordings({}) if r["topic"] and r["topic"]["topic_id"] == topic.topic_id
                       and r["enrolment"]["enrolment_id"] == enrolment.enrolment_id],
        "materials": content_service.student_resources({"topic_id": topic.topic_id}),
        "assignments": assignment_rows,
        "tests": test_rows,
        "next_topic": topic_progress.next_topic(enrolment, topic.topic_id),
    }

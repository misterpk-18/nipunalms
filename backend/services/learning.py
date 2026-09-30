"""Module and topic pages. Staff read any curriculum; a learner reaches only modules and topics of the curriculum versions
their own enrolments (and combo tracks) point at, and sees only their own class sessions."""
from dataclasses import dataclass

from config.database import db
from models import ClassSession, CurriculumModule, CurriculumTopic, Enrolment, EnrolmentTrack
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories import students as students_repo
from services import class_sessions as class_sessions_service
from services import delivery_access, my_courses, scope
from services.context import current_user
from services.errors import NotFound


@dataclass
class Context:
    """Where a learner's enrolment reaches this curriculum: the enrolment, and the combo track if the version belongs to one."""
    enrolment: Enrolment
    track: EnrolmentTrack | None


@dataclass
class ModulePage:
    module: CurriculumModule
    context: Context | None
    topics: list[tuple[CurriculumTopic, int]]  # topic, the learner's session count (0 for staff)
    status: str | None


@dataclass
class TopicPage:
    topic: CurriculumTopic
    context: Context | None
    sessions: list[ClassSession]


def _context(version_id: int) -> Context | None:
    """The learner's enrolment (and track) that uses this curriculum version; None when none does."""
    for enrolment in students_repo.enrolments_of_student(current_user().student_id):
        if enrolment.curriculum_version_id == version_id:
            return Context(enrolment, None)
        for track in enrolment.tracks:
            if track.curriculum_version_id == version_id:
                return Context(enrolment, track)
    return None


def _reach(version_id: int) -> Context | None:
    """Staff: any curriculum (no context). Learner: their own versions only, else 404."""
    if not delivery_access.is_student_only():
        return None
    context = _context(version_id)
    if context is None:
        raise NotFound("Not found")
    return context


def _my_sessions(context: Context | None, topic_ids: set[int]) -> list[ClassSession]:
    if context is not None:
        return [s for s in class_sessions_service.sessions_for_enrolment(context.enrolment.enrolment_id) if s.topic_id in topic_ids]
    stmt = sessions_repo.list_stmt({"topic_ids": topic_ids}, scope.visible_branch_ids(), scope.trainer_batch_ids(), set())
    return list(db.session.execute(stmt).scalars())


def get_module(module_id: int) -> ModulePage:
    module = catalog_repo.get_module(module_id)
    if module is None:
        raise NotFound("Module not found")
    context = _reach(module.curriculum_version_id)
    sessions = _my_sessions(context, {t.topic_id for t in module.topics})
    topics = [(t, sum(1 for s in sessions if s.topic_id == t.topic_id and s.state != "Cancelled")) for t in module.topics]
    status = my_courses.module_status(module, sessions)[0] if context is not None else None
    return ModulePage(module, context, topics, status)


def get_topic(topic_id: int) -> TopicPage:
    topic = catalog_repo.get_topic(topic_id)
    if topic is None:
        raise NotFound("Topic not found")
    context = _reach(topic.module.curriculum_version_id)
    return TopicPage(topic, context, _my_sessions(context, {topic.topic_id}))

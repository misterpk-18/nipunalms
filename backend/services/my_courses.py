"""The learner's course views: My Courses, a course (with its combo tracks and modules), a track, and the upcoming schedule.

Only the learner's own enrolments are reachable; anything else is a 404. Progress here is what the Delivery slice can count:
sessions delivered out of sessions planned (not cancelled) in the batch. The four progress measures (attendance, required
learning, engagement) come from the attendance slice and are not computed here.
"""
from dataclasses import dataclass, field

from sqlalchemy import select

from config.database import db
from models import AttendanceRecord, Batch, ClassSession, CourseModule, Enrolment, EnrolmentTrack, FinanceSummary
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories import students as students_repo
from services import class_sessions as class_sessions_service
from services import recordings as recordings_service
from services import topic_progress
from services.context import current_user
from services.errors import Forbidden, NotFound

UPCOMING_STATES = ("Scheduled", "Rescheduled", "Live")


@dataclass
class ModuleRow:
    module: CourseModule
    topic_count: int
    required_topic_count: int
    session_count: int
    delivered_count: int
    status: str
    topics_done: int = 0


@dataclass
class TrackRow:
    track: EnrolmentTrack
    delivery: dict
    topics: topic_progress.Counts | None = None


@dataclass
class EnrolmentView:
    enrolment: Enrolment
    batch: Batch | None
    trainers: list
    delivery: dict
    explanation: str
    linked_admission_code: str | None
    topics: topic_progress.Counts | None = None  # topics Done of all topics (db/109)
    continue_topic: dict | None = None
    tracks: list[TrackRow] = field(default_factory=list)
    modules: list[ModuleRow] = field(default_factory=list)
    next_sessions: list[ClassSession] = field(default_factory=list)
    finance: FinanceSummary | None = None


@dataclass
class TrackView:
    enrolment: Enrolment
    track: EnrolmentTrack
    delivery: dict
    modules: list[ModuleRow]


def _student_id() -> int:
    student_id = current_user().student_id
    if student_id is None:
        raise Forbidden("Only a learner has course enrolments")
    return student_id


def _own_enrolment(enrolment_id: int) -> Enrolment:
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment is None or enrolment.student_id != _student_id():
        raise NotFound("Enrolment not found")
    return enrolment


def delivery_counts(sessions: list[ClassSession]) -> dict:
    """Delivered / upcoming / cancelled sessions and the delivered share of the planned (not cancelled) ones."""
    delivered = sum(s.state == "Delivered" for s in sessions)
    upcoming = sum(s.state in UPCOMING_STATES for s in sessions)
    planned = delivered + upcoming
    return {"delivered": delivered, "upcoming": upcoming, "cancelled": sum(s.state == "Cancelled" for s in sessions), "planned": planned,
            "percent": round(delivered * 100 / planned) if planned else None}


def explain_status(enrolment: Enrolment, batch: Batch | None) -> str:
    """What the enrolment's status means for the learner, in the prototype's wording."""
    branch = enrolment.service_branch.branch_name
    match enrolment.status:
        case "Provisioning Pending":
            return enrolment.benefit_note or "Your access is being set up. Course content opens once the qualifying payment is verified."
        case "Allocation Pending":
            return "Your course is confirmed. Your branch will allocate you to a batch before your first class."
        case "Allocated — awaiting first regular class":
            where = f" to batch {batch.batch_code}" if batch else ""
            return f"You are allocated{where}. Your Joining Date is set when you attend your first confirmed regular class (a demo does not count)."
        case "Active":
            return "In progress."
        case "Paused":
            return f"Paused. Ask your Branch Manager — {branch} — to resume."
        case "Completed":
            return "You have completed this course."
        case _:
            return "This enrolment has been withdrawn."


def _batch_of(enrolment: Enrolment) -> Batch | None:
    allocation = batches_repo.active_allocation(enrolment.enrolment_id)
    return allocation.batch if allocation else None


def _track_outline(track: EnrolmentTrack) -> tuple[int, int | None]:
    """(course_id, component_id) of the outline the track follows: its own, or the standalone course it is pinned to."""
    component = track.component
    return (component.pinned_course_id, None) if component.pinned_course_id else (component.parent_course_id, component.component_id)


def _track_sessions(sessions: list[ClassSession], outline: tuple[int, int | None]) -> list[ClassSession]:
    topic_ids = [s.topic_id for s in sessions if s.topic_id]
    keys = sessions_repo.topic_outline_keys(topic_ids)
    return [s for s in sessions if s.topic_id and keys.get(s.topic_id) == outline]


def module_status(module: CourseModule, sessions: list[ClassSession]) -> tuple[str, int, int]:
    """Not scheduled / Scheduled / In delivery / Delivered for a module, from the learner's sessions on its topics, plus
    how many of those sessions count (not cancelled) and how many were delivered."""
    topic_ids = {t.topic_id for t in module.topics}
    counted = [s for s in sessions if s.topic_id in topic_ids and s.state != "Cancelled"]
    delivered = sum(s.state == "Delivered" for s in counted)
    if not counted:
        return "Not scheduled", 0, 0
    if delivered == len(counted):
        return "Delivered", len(counted), delivered
    if delivered or any(s.state == "Live" for s in counted):
        return "In delivery", len(counted), delivered
    return "Scheduled", len(counted), delivered


def _module_rows(modules: list[CourseModule], sessions: list[ClassSession], done: dict | None = None) -> list[ModuleRow]:
    """Modules of an outline with what the learner's sessions say about each, and how many of its topics are Done."""
    rows = []
    for module in modules:
        status, session_count, delivered = module_status(module, sessions)
        counts = (done or {}).get(module.module_id)
        rows.append(ModuleRow(module, len(module.topics), sum(t.is_required for t in module.topics), session_count, delivered, status,
                              counts.done if counts else 0))
    return rows


def list_enrolments() -> list[EnrolmentView]:
    """Every enrolment under the learner's one Student Master, with its batch, status explanation and delivery counts."""
    views = []
    for enrolment in students_repo.enrolments_of_student(_student_id()):
        batch = _batch_of(enrolment)
        sessions = class_sessions_service.sessions_for_enrolment(enrolment.enrolment_id)
        view = EnrolmentView(enrolment, batch, [t for t in batch.trainers if t.to_date is None] if batch else [], delivery_counts(sessions),
                             explain_status(enrolment, batch), _linked_admission(enrolment))
        rows = topic_progress.rows_for(enrolment.enrolment_id)
        view.topics, view.continue_topic = topic_progress.course_counts(enrolment, rows), topic_progress.continue_topic(enrolment, rows)
        views.append(view)
    return views


def _linked_admission(enrolment: Enrolment) -> str | None:
    """A complimentary course points at the paid admission that earned it."""
    if enrolment.parent_enrolment_id is None:
        return None
    return students_repo.get_enrolment(enrolment.parent_enrolment_id).admission.admission_code


def get_enrolment(enrolment_id: int) -> EnrolmentView:
    """The course overview: admission reference, branches, batch, trainers, curriculum, tracks, modules and what is coming up."""
    enrolment = _own_enrolment(enrolment_id)
    batch = _batch_of(enrolment)
    sessions = class_sessions_service.sessions_for_enrolment(enrolment.enrolment_id)
    view = EnrolmentView(enrolment, batch, [t for t in batch.trainers if t.to_date is None] if batch else [], delivery_counts(sessions),
                         explain_status(enrolment, batch), _linked_admission(enrolment))
    rows = topic_progress.rows_for(enrolment.enrolment_id)
    view.topics, view.continue_topic = topic_progress.course_counts(enrolment, rows), topic_progress.continue_topic(enrolment, rows)
    by_outline = topic_progress.outline_counts(enrolment.enrolment_id)
    view.tracks = [TrackRow(t, delivery_counts(_track_sessions(sessions, _track_outline(t))), by_outline.get(_track_outline(t)))
                   for t in enrolment.tracks]
    view.modules = _module_rows(catalog_repo.outline_for(enrolment.course_id), sessions, topic_progress.module_counts(enrolment.enrolment_id))
    view.next_sessions = [s for s in sessions if s.state in UPCOMING_STATES][:3]
    view.finance = students_repo.get_finance_summary(enrolment.admission_id)
    return view


def get_track(enrolment_id: int, enrolment_track_id: int) -> TrackView:
    enrolment = _own_enrolment(enrolment_id)
    track = students_repo.get_track(enrolment_track_id)
    if track is None or track.enrolment_id != enrolment.enrolment_id:
        raise NotFound("Track not found")
    outline = _track_outline(track)
    sessions = _track_sessions(class_sessions_service.sessions_for_enrolment(enrolment.enrolment_id), outline)
    return TrackView(enrolment, track, delivery_counts(sessions),
                     _module_rows(catalog_repo.outline_for(*outline), sessions, topic_progress.module_counts(enrolment.enrolment_id)))


@dataclass
class SchedulePage:
    rows: list
    meta: dict
    by_batch: dict
    past: bool = False
    attendance: dict = field(default_factory=dict)  # Past tab: session id -> the learner's attendance status
    recording: dict = field(default_factory=dict)   # Past tab: session id -> the recording to watch


def schedule(filters: dict, page: int, per_page: int) -> SchedulePage:
    """The learner's classes across the batches they are allocated to (optionally one course) with the enrolment each belongs to.

    Coming (the default): everything still to happen, soonest first, cancelled and moved classes included so the learner sees
    why a class is not on. Past (`past`): classes that have ended, newest first, with the learner's attendance and recording.
    """
    student_id = _student_id()
    filters = dict(filters)
    past = bool(filters.pop("past", False))
    rows, meta = class_sessions_service.list_sessions({**filters, "window": "past" if past else "coming"}, page, per_page)
    enrolments = {e.enrolment_id: e for e in students_repo.enrolments_of_student(student_id)}
    allocations = batches_repo.active_allocations(list(enrolments))
    result = SchedulePage(rows, meta, {a.batch_id: enrolments[a.enrolment_id] for a in allocations.values()}, past)
    if past:
        result.attendance, result.recording = _past_details([r.session.session_id for r in rows], set(enrolments))
    return result


def _past_details(session_ids: list[int], enrolment_ids: set[int]) -> tuple[dict[int, str], dict[int, dict]]:
    """Session id -> the learner's attendance status, and session id -> the recording to watch (a playable one first). A class
    the learner has no mark or recording for has no entry."""
    if not session_ids:
        return {}, {}
    stmt = select(AttendanceRecord.session_id, AttendanceRecord.status).where(
        AttendanceRecord.session_id.in_(session_ids), AttendanceRecord.enrolment_id.in_(enrolment_ids))
    attendance = {session_id: str(status) for session_id, status in db.session.execute(stmt).all()}
    recording: dict[int, dict] = {}
    for entry in recordings_service.student_recordings({}):
        session_id = entry["session"]["session_id"]
        if session_id not in session_ids:
            continue
        mine = {"recording_id": entry["recording_id"], "status": entry["status"], "playable": entry["playable"]}
        if session_id not in recording or (mine["playable"] and not recording[session_id]["playable"]):
            recording[session_id] = mine
    return attendance, recording

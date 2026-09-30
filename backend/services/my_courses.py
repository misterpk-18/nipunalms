"""The learner's course views: My Courses, a course (with its combo tracks and modules), a track, and the upcoming schedule.

Only the learner's own enrolments are reachable; anything else is a 404. Progress here is what the Delivery slice can count:
sessions delivered out of sessions planned (not cancelled) in the batch. The four progress measures (attendance, required
learning, engagement) come from the attendance slice and are not computed here.
"""
from dataclasses import dataclass, field

from models import Batch, ClassSession, CurriculumModule, CurriculumVersion, Enrolment, EnrolmentTrack, FinanceSummary
from repositories import batches as batches_repo
from repositories import class_sessions as sessions_repo
from repositories import students as students_repo
from services import class_sessions as class_sessions_service
from services.context import current_user
from services.errors import Forbidden, NotFound

UPCOMING_STATES = ("Scheduled", "Rescheduled", "Live")


@dataclass
class ModuleRow:
    module: CurriculumModule
    topic_count: int
    required_topic_count: int
    session_count: int
    delivered_count: int
    status: str


@dataclass
class TrackRow:
    track: EnrolmentTrack
    delivery: dict


@dataclass
class EnrolmentView:
    enrolment: Enrolment
    batch: Batch | None
    trainers: list
    delivery: dict
    explanation: str
    linked_admission_code: str | None
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
        case "Curriculum Mapping Pending":
            return f"Curriculum Mapping Pending · Recovery Owner: Academic Coordinator — {branch}. Your Admission and receipt are preserved."
        case "Allocation Pending":
            return "Your course is confirmed. Your Academic Coordinator will allocate you to a batch before your first class."
        case "Allocated — awaiting first regular class":
            where = f" to batch {batch.batch_code}" if batch else ""
            return f"You are allocated{where}. Your Joining Date is set when you attend your first confirmed regular class (a demo does not count)."
        case "Active":
            return "In progress."
        case "Paused":
            return f"Paused. Ask your Academic Coordinator — {branch} — to resume."
        case "Completed":
            return "You have completed this course."
        case _:
            return "This enrolment has been withdrawn."


def _batch_of(enrolment: Enrolment) -> Batch | None:
    allocation = batches_repo.active_allocation(enrolment.enrolment_id)
    return allocation.batch if allocation else None


def _track_sessions(sessions: list[ClassSession], version_id: int | None) -> list[ClassSession]:
    if version_id is None:
        return []
    topic_ids = [s.topic_id for s in sessions if s.topic_id]
    versions = sessions_repo.topic_version_ids(topic_ids)
    return [s for s in sessions if s.topic_id and versions.get(s.topic_id) == version_id]


def module_status(module: CurriculumModule, sessions: list[ClassSession]) -> tuple[str, int, int]:
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


def _module_rows(version: CurriculumVersion | None, sessions: list[ClassSession]) -> list[ModuleRow]:
    """Modules of a version with what the learner's sessions say about each."""
    rows = []
    for module in version.modules if version else []:
        status, session_count, delivered = module_status(module, sessions)
        rows.append(ModuleRow(module, len(module.topics), sum(t.is_required for t in module.topics), session_count, delivered, status))
    return rows


def list_enrolments() -> list[EnrolmentView]:
    """Every enrolment under the learner's one Student Master, with its batch, status explanation and delivery counts."""
    views = []
    for enrolment in students_repo.enrolments_of_student(_student_id()):
        batch = _batch_of(enrolment)
        sessions = class_sessions_service.sessions_for_enrolment(enrolment.enrolment_id)
        views.append(EnrolmentView(enrolment, batch, [t for t in batch.trainers if t.to_date is None] if batch else [], delivery_counts(sessions),
                                   explain_status(enrolment, batch), _linked_admission(enrolment)))
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
    view.tracks = [TrackRow(t, delivery_counts(_track_sessions(sessions, t.curriculum_version_id))) for t in enrolment.tracks]
    view.modules = _module_rows(enrolment.curriculum_version, sessions)
    view.next_sessions = [s for s in sessions if s.state in UPCOMING_STATES][:3]
    view.finance = students_repo.get_finance_summary(enrolment.admission_id)
    return view


def get_track(enrolment_id: int, enrolment_track_id: int) -> TrackView:
    enrolment = _own_enrolment(enrolment_id)
    track = students_repo.get_track(enrolment_track_id)
    if track is None or track.enrolment_id != enrolment.enrolment_id:
        raise NotFound("Track not found")
    sessions = _track_sessions(class_sessions_service.sessions_for_enrolment(enrolment.enrolment_id), track.curriculum_version_id)
    return TrackView(enrolment, track, delivery_counts(sessions), _module_rows(track.curriculum_version, sessions))


def schedule(filters: dict, page: int, per_page: int):
    """Upcoming sessions across the batches the learner is allocated to (optionally one course), soonest first, with the enrolment each belongs to."""
    _student_id()
    rows, meta = class_sessions_service.list_sessions({**filters, "upcoming": True}, page, per_page)
    enrolments = {e.enrolment_id: e for e in students_repo.enrolments_of_student(_student_id())}
    allocations = batches_repo.active_allocations(list(enrolments))
    by_batch = {a.batch_id: enrolments[a.enrolment_id] for a in allocations.values()}
    return rows, meta, by_batch

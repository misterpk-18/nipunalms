"""Recordings of actual class sessions, recording exceptions, and the recording-check job (Module 17).

A recording is a controlled reference to the one media asset of a Class Session; the LMS never copies the video and
never calls Google. Whether Drive capture and playback are verified is read from the integrations register.

  Academic Coordinator (branch) / Super Admin   register, release, hold, mark partial or unavailable, resolve exceptions
  Branch Manager                                 sees the branch, can resolve exceptions as cover
  Trainer                                        sees recordings and exceptions of the batches they teach
  Student                                        sees recordings of batches their enrolments are (or were) allocated to,
                                                 while the enrolment's access window is open

Escalation clock from the class end: 4 h Academic Coordinator review, 24 h Branch Manager and Super Admin, 48 h Founder / CEO.
"""
from datetime import datetime, timedelta, timezone

from config.database import db
from models import ClassSession, Enrolment, Recording, RecordingException
from repositories import batches as batches_repo
from repositories import content as content_repo
from repositories import recordings as recordings_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, scope, student_library
from services.context import actor_id, current_user
from services.errors import BusinessRule, Forbidden, NotFound
from services.notifications import notify

ESCALATION_STEPS = ((48, "Founder / CEO"), (24, "Branch Manager and Super Admin"), (4, "Academic Coordinator review"))
WATCHABLE = ("Released", "Partial")
STATUS_NOTES = {
    "Processing": "The recording is being prepared.",
    "Held": "Held for review by the Academic Coordinator. You will be told when it is available.",
    "Unavailable": "No recording is available for this class yet.",
    "Expired": "Access to this recording has ended.",
}
ROLE_LABELS = {"ACADEMIC_COORDINATOR": "Academic Coordinator", "SUPER_ADMIN": "Super Admin", "BRANCH_MANAGER": "Branch Manager"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- scope

def _visible_session(session_id: int) -> ClassSession:
    """A class session at the user's branches or of a batch they teach; anything else is a 404."""
    session = recordings_repo.get_session(session_id)
    user = current_user()
    if session is not None:
        branch_ids = scope.visible_branch_ids(user)
        if branch_ids is None or session.batch.branch_id in branch_ids or session.batch_id in scope.trainer_batch_ids(user):
            return session
    raise NotFound("Class session not found")


def _is_manager(session: ClassSession) -> bool:
    user = current_user()
    return user.has_role("SUPER_ADMIN") or user.has_role("ACADEMIC_COORDINATOR", branch_id=session.batch.branch_id)


def _require_manager(session: ClassSession) -> None:
    if not _is_manager(session):
        raise Forbidden("Only the Academic Coordinator of this branch or a Super Admin manages recordings")


def _get_recording(recording_id: int) -> Recording:
    recording = recordings_repo.get_recording(recording_id)
    if recording is None:
        raise NotFound("Recording not found")
    _visible_session(recording.session_id)
    return recording


def _get_managed_recording(recording_id: int) -> Recording:
    recording = _get_recording(recording_id)
    _require_manager(recording.session)
    return recording


# ---------------------------------------------------------------- notices

def _batch_student_user_ids(batch_id: int) -> list[int]:
    user_ids = []
    for enrolment_id in batches_repo.enrolment_ids_in_batches({batch_id}):
        enrolment = students_repo.get_enrolment(enrolment_id)
        user = users_repo.get_by_student_id(enrolment.student_id) if enrolment else None
        if user is not None and user.user_id not in user_ids:
            user_ids.append(user.user_id)
    return user_ids


def _notify_students(session: ClassSession, recording: Recording, title: str, body: str, kind: str) -> None:
    notify(category="Recording", title=title, body=body, link="/recordings", recipient_user_ids=_batch_student_user_ids(session.batch_id),
           branch_id=session.batch.branch_id, event_key=f"recording-{kind}-{recording.recording_id}-{int(_now().timestamp())}")


# ---------------------------------------------------------------- exceptions

def owner_label(exception: RecordingException) -> str:
    label = ROLE_LABELS[exception.owner_role]
    return label if exception.owner_role == "SUPER_ADMIN" else f"{label} {exception.branch.short_code}"


def _age_hours(exception: RecordingException, now: datetime) -> int:
    """Hours since the class ended (the clock of Module 17 §6)."""
    return max(0, int((now - exception.session.ends_at).total_seconds() // 3600))


def escalation_for(exception: RecordingException, now: datetime) -> str | None:
    if exception.status == "Resolved":
        return None
    age = _age_hours(exception, now)
    return next((label for hours, label in ESCALATION_STEPS if age >= hours), None)


def exception_dict(exception: RecordingException) -> dict:
    now = _now()
    return exception.to_dict(owner_label(exception), _age_hours(exception, now), escalation_for(exception, now))


def _raise(session: ClassSession, issue_type: str, issue: str, *, recording: Recording | None = None, auto: bool = True) -> RecordingException:
    """Open an exception for the session unless one is already open for the same issue (repeated checks do not pile up)."""
    existing = recordings_repo.open_exception(session.session_id, issue_type)
    if existing is not None:
        return existing
    owner_role = "SUPER_ADMIN" if issue_type == "Integration Unavailable" else "ACADEMIC_COORDINATOR"
    exception = RecordingException(session_id=session.session_id, recording_id=recording.recording_id if recording else None,
                                   branch_id=session.batch.branch_id, issue_type=issue_type, issue=issue, owner_role=owner_role,
                                   auto_raised=auto, raised_by=actor_id())
    db.session.add(exception)
    db.session.flush()
    db.session.refresh(exception)
    audit.record("RECORDING_EXCEPTION_RAISED", "recording_exception", exception.exception_code,
                 new={"session": session.session_code, "issue_type": issue_type, "issue": issue, "owner_role": owner_role},
                 branch_id=exception.branch_id)
    notify(category="Recording", title=f"{exception.exception_code}: {issue_type} recording — {session.title}", body=issue,
           link="/academic/recording-exceptions", role_code=owner_role, branch_id=exception.branch_id,
           event_key=f"rx-raised-{exception.exception_code}", action_required=True)
    return exception


def _resolve_open(session: ClassSession, issue_types: tuple[str, ...], note: str) -> None:
    for exception in recordings_repo.unresolved_for_session(session.session_id, issue_types):
        exception.status = "Resolved"
        exception.resolved_at = _now()
        exception.resolved_by = actor_id()
        exception.resolution_note = note
        audit.record("RECORDING_EXCEPTION_RESOLVED", "recording_exception", exception.exception_code,
                     old={"status": "Open"}, new={"status": "Resolved"}, reason=note, branch_id=exception.branch_id)
    db.session.flush()


def _can_act_on(exception: RecordingException) -> bool:
    user = current_user()
    if user.has_role("SUPER_ADMIN"):
        return True
    return exception.owner_role != "SUPER_ADMIN" and user.has_role("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", branch_id=exception.branch_id)


def _get_exception(exception_id: int) -> RecordingException:
    exception = recordings_repo.get_exception(exception_id)
    if exception is None:
        raise NotFound("Recording exception not found")
    _visible_session(exception.session_id)
    return exception


def raise_manual(data: dict) -> RecordingException:
    """Staff raise an exception for a session (e.g. a trainer's report that the class was not captured)."""
    session = _visible_session(data["session_id"])
    if session.state == "Cancelled":
        raise BusinessRule("A cancelled class session has no recording")
    exception = _raise(session, data["issue_type"], data["issue"], auto=False)
    return exception


def start_exception(exception_id: int) -> RecordingException:
    exception = _get_exception(exception_id)
    if not _can_act_on(exception):
        raise Forbidden("This exception is owned by " + owner_label(exception))
    if exception.status != "Open":
        raise BusinessRule(f"{exception.exception_code} is {exception.status}")
    exception.status = "In Progress"
    exception.owner_user_id = current_user().user_id
    db.session.flush()
    db.session.refresh(exception)
    audit.record("RECORDING_EXCEPTION_STARTED", "recording_exception", exception.exception_code, old={"status": "Open"},
                 new={"status": "In Progress"}, branch_id=exception.branch_id)
    return exception


def resolve_exception(exception_id: int, note: str) -> RecordingException:
    exception = _get_exception(exception_id)
    if not _can_act_on(exception):
        raise Forbidden("This exception is owned by " + owner_label(exception))
    if exception.status == "Resolved":
        raise BusinessRule(f"{exception.exception_code} is already resolved")
    old_status = exception.status
    exception.status = "Resolved"
    exception.resolved_at = _now()
    exception.resolved_by = current_user().user_id
    exception.resolution_note = note
    if exception.owner_user_id is None:
        exception.owner_user_id = current_user().user_id
    db.session.flush()
    db.session.refresh(exception)
    audit.record("RECORDING_EXCEPTION_RESOLVED", "recording_exception", exception.exception_code, old={"status": old_status},
                 new={"status": "Resolved"}, reason=note, branch_id=exception.branch_id)
    return exception


def list_exceptions(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    user = current_user()
    rows, meta = paginate(recordings_repo.exceptions_stmt(filters, scope.visible_branch_ids(user), scope.trainer_batch_ids(user)),
                          page, per_page)
    return [exception_dict(e) for e in rows], meta


def get_exception_detail(exception_id: int) -> dict:
    return exception_dict(_get_exception(exception_id))


# ---------------------------------------------------------------- recordings (staff)

def register(data: dict) -> Recording:
    """Register a recording part against an actual class session. It starts as Processing (or Unavailable when none exists)."""
    session = _visible_session(data["session_id"])
    _require_manager(session)
    if session.state == "Cancelled":
        raise BusinessRule("A cancelled class session has no recording")
    status = data.get("status", "Processing")
    if status == "Processing" and session.state == "Scheduled":
        raise BusinessRule("The class has not been delivered yet; register a recording after it is delivered")
    recording = Recording(session_id=session.session_id, part_no=recordings_repo.next_part_no(session.session_id), status=status,
                          source=data.get("source", "Google Drive"), media_ref=data.get("media_ref"),
                          duration_minutes=data.get("duration_minutes"), download_allowed=data.get("download_allowed", False),
                          created_by=current_user().user_id)
    db.session.add(recording)
    db.session.flush()
    db.session.refresh(recording)
    audit.record("RECORDING_REGISTERED", "recording", recording.recording_code,
                 new={"session": session.session_code, "part": recording.part_no, "status": status, "source": recording.source},
                 branch_id=session.batch.branch_id)
    return recording


def update(recording_id: int, data: dict) -> Recording:
    """Record where the media is (Drive file id), its length, source and download policy. Policy changes are audited."""
    recording = _get_managed_recording(recording_id)
    old = {key: getattr(recording, key) for key in data}
    for key, value in data.items():
        setattr(recording, key, value)
    db.session.flush()
    audit.record("RECORDING_UPDATED", "recording", recording.recording_code, old=old, new=dict(data),
                 branch_id=recording.session.batch.branch_id)
    return recording


def release(recording_id: int) -> Recording:
    """Release to the batch: needs the media reference and a delivered class. Closes open hold / partial / unavailable exceptions."""
    recording = _get_managed_recording(recording_id)
    session = recording.session
    if recording.status == "Released":
        raise BusinessRule("The recording is already released")
    if recording.status == "Expired":
        raise BusinessRule("An expired recording cannot be released")
    if session.state != "Delivered":
        raise BusinessRule("Only a delivered class can have its recording released; a planned or cancelled class is not proof of teaching")
    if not recording.media_ref:
        raise BusinessRule("Add the Drive file reference before releasing the recording")
    old_status = recording.status
    recording.status = "Released"
    recording.released_at = recording.released_at or _now()
    recording.released_by = current_user().user_id
    recording.hold_reason = None
    recording.partial_note = None
    audit.record("RECORDING_RELEASED", "recording", recording.recording_code, old={"status": old_status}, new={"status": "Released"},
                 branch_id=session.batch.branch_id)
    _resolve_open(session, ("Held", "Partial", "Unavailable"), f"Recording {recording.recording_code} released")
    _notify_students(session, recording, f"Recording available: {session.title}",
                     f"The recording of {session.title} is ready to watch.", "released")
    return recording


def hold(recording_id: int, reason: str) -> Recording:
    """Withdraw the recording from students while it is reviewed (e.g. sensitive content). Raises an exception."""
    recording = _get_managed_recording(recording_id)
    session = recording.session
    if recording.status in ("Held", "Expired"):
        raise BusinessRule(f"The recording is already {recording.status}")
    old_status = recording.status
    recording.status = "Held"
    recording.hold_reason = reason
    audit.record("RECORDING_HELD", "recording", recording.recording_code, old={"status": old_status}, new={"status": "Held"},
                 reason=reason, branch_id=session.batch.branch_id)
    _raise(session, "Held", f"Held for review — {reason}", recording=recording, auto=True)
    _notify_students(session, recording, f"Recording temporarily unavailable: {session.title}",
                     "It is being reviewed; you will be told when it is available.", "held")
    return recording


def mark_partial(recording_id: int, note: str) -> Recording:
    """Only part of the class was captured. Students can still watch what exists; the missing part stays open as an exception."""
    recording = _get_managed_recording(recording_id)
    session = recording.session
    if recording.status in ("Partial", "Expired"):
        raise BusinessRule(f"The recording is already {recording.status}")
    if not recording.media_ref:
        raise BusinessRule("Add the Drive file reference before marking a recording partial")
    old_status = recording.status
    recording.status = "Partial"
    recording.partial_note = note
    recording.released_at = recording.released_at or _now()
    audit.record("RECORDING_PARTIAL", "recording", recording.recording_code, old={"status": old_status}, new={"status": "Partial"},
                 reason=note, branch_id=session.batch.branch_id)
    _raise(session, "Partial", f"Partial recording — {note}", recording=recording, auto=True)
    _notify_students(session, recording, f"Partial recording: {session.title}", note, "partial")
    return recording


def mark_unavailable(recording_id: int, reason: str) -> Recording:
    recording = _get_managed_recording(recording_id)
    session = recording.session
    if recording.status in ("Unavailable", "Expired"):
        raise BusinessRule(f"The recording is already {recording.status}")
    old_status = recording.status
    recording.status = "Unavailable"
    audit.record("RECORDING_UNAVAILABLE", "recording", recording.recording_code, old={"status": old_status},
                 new={"status": "Unavailable"}, reason=reason, branch_id=session.batch.branch_id)
    _raise(session, "Unavailable", reason, recording=recording, auto=True)
    return recording


def list_recordings(filters: dict, page: int, per_page: int) -> tuple[list[Recording], dict]:
    user = current_user()
    return paginate(recordings_repo.list_stmt(filters, scope.visible_branch_ids(user), scope.trainer_batch_ids(user)), page, per_page)


def get_recording_detail(recording_id: int) -> tuple[Recording, list[dict]]:
    recording = _get_recording(recording_id)
    exceptions = [exception_dict(e) for e in recordings_repo.unresolved_for_session(recording.session_id, ("Partial", "Held", "Unavailable", "Integration Unavailable"))]
    return recording, exceptions


# ---------------------------------------------------------------- the recording-check job

def check_missing_recordings(now: datetime | None = None) -> dict:
    """Delivered sessions with no recording after N hours get an Unavailable placeholder and an exception; open exceptions
    that reach 24 h / 48 h are escalated once (Branch Manager + Super Admin, then Founder / CEO)."""
    now = now or _now()
    cutoff = now - timedelta(hours=settings_repo.get_int("recording_check_hours", 4))
    drive_status = recordings_repo.drive_verification_status()
    raised = 0
    for session in recordings_repo.delivered_sessions_without_recording(cutoff):
        recording = Recording(session_id=session.session_id, part_no=1, status="Unavailable", source="Google Drive")
        db.session.add(recording)
        db.session.flush()
        if session.mode != "Classroom" and drive_status != "Verified":
            issue_type, issue = "Integration Unavailable", f"Google Drive recording capture is {drive_status}; the class was not captured automatically"
        else:
            issue_type, issue = "Unavailable", "No recording mapped to actual Class Session"
        _raise(session, issue_type, issue, recording=recording, auto=True)
        raised += 1

    escalated = 0
    for exception in recordings_repo.unresolved_exceptions():
        age = _age_hours(exception, now)
        if age < 24:
            continue
        escalated += 1  # notices are deduplicated per exception and step, so a repeat run tells nobody twice
        title = f"{exception.exception_code} unresolved for {age} hours"
        body = f"{exception.issue_type} recording — {exception.session.title}. Owner: {owner_label(exception)}."
        for role_code in ("BRANCH_MANAGER", "SUPER_ADMIN"):
            notify(category="Recording", title=title, body=body, link="/academic/recording-exceptions", role_code=role_code,
                   branch_id=exception.branch_id, event_key=f"rx-escalated-24-{exception.exception_code}", action_required=True)
        if age >= 48:
            notify(category="Recording", title=title, body=body + " A remedy plan is needed.", link="/academic/recording-exceptions",
                   role_code="FOUNDER_CEO", branch_id=exception.branch_id, event_key=f"rx-escalated-48-{exception.exception_code}")
    return {"missing_recordings": raised, "escalated": escalated}


# ---------------------------------------------------------------- student views

def _student_recording_entries(ctx: student_library.StudentContext, recordings: list[Recording],
                               enrolment_by_batch: dict[int, Enrolment]) -> list[dict]:
    versions = {r.session.topic.module.curriculum_version_id for r in recordings if r.session.topic}
    tracks = content_repo.track_labels(versions)
    entries = []
    for recording in recordings:
        session = recording.session
        enrolment = enrolment_by_batch[session.batch_id]
        window = ctx.windows[enrolment.enrolment_id]
        access_state = window.describe("Recording", ctx.today)
        playable = recording.status in WATCHABLE and access_state["state"] != "Expired"
        topic = session.topic
        entries.append({
            "recording_id": recording.recording_id,
            "recording_code": recording.recording_code,
            "session": {"session_id": session.session_id, "session_code": session.session_code, "title": session.title,
                        "starts_at": session.starts_at, "ends_at": session.ends_at, "mode": session.mode, "state": session.state,
                        "trainer": {"user_id": session.trainer_user_id, "full_name": session.trainer.full_name}},
            "course": session.batch.course.to_summary(),
            "track": tracks.get(topic.module.curriculum_version_id) if topic else None,
            "topic": {"topic_id": topic.topic_id, "title": topic.title} if topic else None,
            "batch": session.batch.to_summary(),
            "part_no": recording.part_no,
            "status": recording.status,
            "status_note": recording.partial_note if recording.status == "Partial" else STATUS_NOTES.get(recording.status),
            "duration_minutes": recording.duration_minutes,
            "released_at": recording.released_at,
            "download_allowed": recording.download_allowed,
            "enrolment": enrolment.to_summary(),
            "access": access_state,
            "playable": playable,
        })
    return entries


def _student_batches(ctx: student_library.StudentContext) -> dict[int, Enrolment]:
    """Batch -> the enrolment entitled through it (the latest allocation wins when a batch appears twice)."""
    allocations = recordings_repo.allocations_for_enrolments([e.enrolment_id for e in ctx.enrolments])
    by_id = {e.enrolment_id: e for e in ctx.enrolments}
    return {a.batch_id: by_id[a.enrolment_id] for a in allocations}


def student_recordings(filters: dict) -> list[dict]:
    """Recordings of the sessions of the student's batches, with expiry and download policy per enrolment."""
    ctx = student_library.student_context()
    enrolment_by_batch = _student_batches(ctx)
    recordings = recordings_repo.for_batches(set(enrolment_by_batch), filters)
    return _student_recording_entries(ctx, recordings, enrolment_by_batch)


def watch(recording_id: int) -> dict:
    """Start watching: entitlement and expiry are checked now, and the view is recorded as learning activity."""
    ctx = student_library.student_context()
    enrolment_by_batch = _student_batches(ctx)
    recording = recordings_repo.get_recording(recording_id)
    if recording is None or recording.session.batch_id not in enrolment_by_batch:
        raise NotFound("Recording not found")
    enrolment = enrolment_by_batch[recording.session.batch_id]
    window = ctx.windows[enrolment.enrolment_id]
    if recording.status not in WATCHABLE:
        raise BusinessRule(STATUS_NOTES.get(recording.status, "This recording cannot be watched"))
    if window.state("Recording", ctx.today) == "Expired":
        raise BusinessRule(f"Your access to recordings for {enrolment.course.title} ended on {window.expiry['Recording']:%d %b %Y}. "
                           "You can request an extension from the Recordings screen.")
    content_repo.record_activity(ctx.student_id, enrolment.enrolment_id, "recording_view",
                                 {"recording_id": recording.recording_id, "session_code": recording.session.session_code})
    drive_status = recordings_repo.drive_verification_status()
    return {
        "recording_id": recording.recording_id,
        "recording_code": recording.recording_code,
        "session_title": recording.session.title,
        "status": recording.status,
        "status_note": recording.partial_note if recording.status == "Partial" else None,
        "download_allowed": recording.download_allowed,
        "playback": {
            "mode": "download" if recording.download_allowed else "stream",
            "source": recording.source,
            "integration_status": drive_status,
            "available": recording.source == "Google Drive" and drive_status == "Verified",
            "message": None if drive_status == "Verified" else
            f"Playback needs the Google Drive recording integration, which is {drive_status}. Nothing is played from Drive yet.",
        },
    }

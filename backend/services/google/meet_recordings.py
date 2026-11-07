"""Class recordings without anyone pressing Record (docs/INTEGRATIONS.md Part B §5.6).

Auto-record. Once a class's Calendar event has its Meet link (`class_events.handle_upsert`), a `MEET_AUTO_RECORD` job asks the
Meet REST API, as the branch calendar mailbox that organises the meeting, to record it automatically: `GET spaces/{meeting code}`
gives the space id (kept in `class_sessions.meet_space_id`), then `PATCH spaces/{id}` sets
`config.artifactConfig.recordingConfig.autoRecordingGeneration = ON`. Meet then starts recording as soon as someone allowed to
record joins. A job that dies tells the Branch Managers to record that class by hand. Switch: `GOOGLE_MEET`, as for the event.

Import. The `recording-import` job (every minute) looks at online classes that ended within IMPORT_WINDOW, have a Meet space and are
not yet marked done (`class_sessions.conference_record_id`). It lists the space's conferences and their recordings, and for each
file Google has generated: registers it on the class as Processing with the Drive file id (`recordings.attach_from_meet`, which
also fills in a placeholder left by `recording-check` and resolves its exception), shares the file with the batch's Google Group
as a reader (so the batch's students and trainers can play it), and asks the Branch Managers to release it. Once every
conference of the class has ended and every recording has its file, the class is marked done and not asked about again.
Switch: `GOOGLE_DRIVE_RECORDINGS` (Drive recording capture and playback), the same row the student player reads.

Domain-wide delegation needs, on top of the existing scopes: `meetings.space.settings` (auto-record a space Calendar made),
`meetings.space.readonly` (read its conferences and recordings) and `drive` (share a recording file the LMS did not create).
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config.database import db
from models import ClassSession
from repositories import google as google_repo
from repositories import users as users_repo
from services import delivery_notices, integrations
from services import recordings as recordings_service
from services.google import client
from services.google.client import GoogleError

logger = logging.getLogger(__name__)

MEET_INTEGRATION = "GOOGLE_MEET"
RECORDINGS_INTEGRATION = "GOOGLE_DRIVE_RECORDINGS"
KIND_AUTO_RECORD = "MEET_AUTO_RECORD"
ENTITY = "class_session"
SPACES = "https://meet.googleapis.com/v2/spaces"
CONFERENCES = "https://meet.googleapis.com/v2/conferenceRecords"
FILES = "https://www.googleapis.com/drive/v3/files"
RECORDING_MASK = "config.artifactConfig.recordingConfig.autoRecordingGeneration"
IMPORT_WINDOW = timedelta(hours=12)  # Google usually has the file within an hour of the meeting's end
IMPORT_LIMIT = 50
_MEETING_CODE = re.compile(r"meet\.google\.com/([a-z]+-[a-z]+-[a-z]+)", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_enabled() -> bool:
    return client.is_configured() and integrations.is_verified(MEET_INTEGRATION)


def import_enabled() -> bool:
    return client.is_configured() and integrations.is_verified(RECORDINGS_INTEGRATION)


def meeting_code(link: str | None) -> str | None:
    match = _MEETING_CODE.search(link or "")
    return match.group(1).lower() if match else None


def _meet(method: str, url: str, mailbox: str, scope: str, *, body: dict | None = None, params: dict | None = None) -> dict:
    return client.request(method, url, subject=mailbox, scopes=[scope], body=body, params=params)


def _bm_ids(session: ClassSession) -> list[int]:
    return users_repo.user_ids_with_role("BRANCH_MANAGER", session.batch.branch_id)


# ---------------------------------------------------------------- auto-record (a google-sync job per class)

def enqueue_auto_record(session: ClassSession) -> None:
    """The class has a Meet link from its Calendar event and its space is not set to record yet: queue the setting."""
    if is_enabled() and session.mode != "Classroom" and session.meet_link and not session.meet_space_id:
        google_repo.enqueue(KIND_AUTO_RECORD, ENTITY, session.session_id)


def handle_auto_record(session_id: int) -> str:
    session = db.session.get(ClassSession, session_id)
    if session is None:
        return "class no longer exists"
    if session.state in ("Cancelled", "Delivered") or session.mode == "Classroom":
        return f"class is {session.state if session.mode != 'Classroom' else 'in a classroom'}; nothing to record"
    code = meeting_code(session.meet_link)
    if code is None:
        return "the class has no Google Meet link"
    mailbox = google_repo.branch_mailbox(session.batch.branch_id)
    if not mailbox:
        raise GoogleError(f"Branch {session.batch.branch_id} has no calendar mailbox")
    space = _meet("GET", f"{SPACES}/{code}", mailbox, client.MEET_SETTINGS_SCOPE)
    name = space["name"]  # spaces/{id}: a patch takes only the id, never the meeting code
    session.meet_space_id = name.split("/", 1)[1]
    recording = ((space.get("config") or {}).get("artifactConfig") or {}).get("recordingConfig") or {}
    if recording.get("autoRecordingGeneration") == "ON":
        return f"{name} already records automatically"
    _meet("PATCH", f"{SPACES}/{session.meet_space_id}", mailbox, client.MEET_SETTINGS_SCOPE,
          body={"config": {"artifactConfig": {"recordingConfig": {"autoRecordingGeneration": "ON"}}}},
          params={"updateMask": RECORDING_MASK})
    return f"auto-recording on for {name}"


def on_dead(kind: str, entity_id: int, error: str) -> None:
    """Google would not set the class to record itself: the Branch Managers make sure someone records it by hand."""
    session = db.session.get(ClassSession, entity_id)
    if session is None:
        return
    delivery_notices.notify_users(
        _bm_ids(session), title=f"Auto-recording not set: {session.title}",
        body=f"{session.batch.batch_code}: press Record in Google Meet when the class starts. Google said: {error[:300]}",
        event_key=f"meet-auto-record-failed-{session.session_id}", link="/branch/schedule", branch_id=session.batch.branch_id,
        category="Recording", action_required=True)


# ---------------------------------------------------------------- import (the recording-import job)

def _due_sessions(now: datetime) -> list[ClassSession]:
    """Online classes that ended within the window, have a Meet space and are not marked done yet."""
    return list(db.session.execute(
        select(ClassSession).where(
            ClassSession.mode != "Classroom", ClassSession.state.in_(("Live", "Delivered")),
            ClassSession.meet_space_id.is_not(None), ClassSession.conference_record_id.is_(None),
            ClassSession.ends_at <= now, ClassSession.ends_at > now - IMPORT_WINDOW)
        .order_by(ClassSession.ends_at).limit(IMPORT_LIMIT)).scalars().unique())


def _conferences(session: ClassSession, mailbox: str) -> list[dict]:
    """The space's conferences that began around this class (from an hour before it to its end)."""
    since = (session.starts_at - timedelta(hours=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reply = _meet("GET", CONFERENCES, mailbox, client.MEET_READONLY_SCOPE,
                  params={"filter": f'space.name = "spaces/{session.meet_space_id}" AND start_time>="{since}"', "pageSize": 100})
    return reply.get("conferenceRecords") or []


def _recordings(conference: dict, mailbox: str) -> list[dict]:
    reply = _meet("GET", f"https://meet.googleapis.com/v2/{conference['name']}/recordings", mailbox, client.MEET_READONLY_SCOPE,
                  params={"pageSize": 100})
    return reply.get("recordings") or []


def _minutes(recording: dict) -> int | None:
    try:
        start = datetime.fromisoformat(recording["startTime"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(recording["endTime"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    return max(1, round((end - start).total_seconds() / 60))


def _share_with_batch(session: ClassSession, mailbox: str, file_id: str) -> str | None:
    """Let the batch's Google Group (its students and trainers) view the file. Returns a problem to report, or None."""
    item = google_repo.drive_item("batch", session.batch_id, session.batch.branch_id)
    if item is None or not item.group_email:
        return "the batch has no Google Group yet, so only the organizer can open the file"
    try:
        client.request("POST", f"{FILES}/{file_id}/permissions", subject=mailbox, scopes=[client.DRIVE_FULL_SCOPE],
                       body={"type": "group", "role": "reader", "emailAddress": item.group_email},
                       params={"sendNotificationEmail": "false", "supportsAllDrives": "true"})
    except GoogleError as exc:
        return f"sharing with {item.group_email} failed: {exc}"
    return None


def _import_one(session: ClassSession, mailbox: str) -> int:
    """Attach this class's new recording files; mark the class done once nothing more can come. Returns how many were attached."""
    conferences = _conferences(session, mailbox)
    attached, complete = 0, bool(conferences)
    for conference in conferences:
        if not conference.get("endTime"):
            complete = False  # still going: more recordings may follow
        for recording in _recordings(conference, mailbox):
            file_id = ((recording.get("driveDestination") or {}).get("file") or "").strip()
            if recording.get("state") != "FILE_GENERATED" or not file_id:
                complete = False
                continue
            added = recordings_service.attach_from_meet(session, file_id, _minutes(recording))
            if added is None:
                continue  # attached on an earlier run
            problem = _share_with_batch(session, mailbox, file_id)
            attached += 1
            delivery_notices.notify_users(
                _bm_ids(session), title=f"Recording ready to release: {session.title}",
                body=f"{session.batch.batch_code} · {added.recording_code}, part {added.part_no}"
                     + (f". Note: {problem}" if problem else ". Check it, then release it to the students."),
                event_key=f"recording-imported-{added.recording_id}", link="/branch/recordings",
                branch_id=session.batch.branch_id, category="Recording", action_required=True)
    if complete:
        session.conference_record_id = conferences[-1]["name"].split("/", 1)[1]  # done: not asked about again
    return attached


def import_recordings(now: datetime | None = None) -> dict:
    """The recording-import job. One class's failure is logged and retried next minute; the others go on."""
    if not import_enabled():
        return {"skipped": "Google is not configured or Drive recording capture is not verified"}
    now = now or _now()
    result = {"checked": 0, "attached": 0, "failed": 0}
    for session_id in [s.session_id for s in _due_sessions(now)]:
        session = db.session.get(ClassSession, session_id)
        mailbox = google_repo.branch_mailbox(session.batch.branch_id)
        if not mailbox:
            continue
        result["checked"] += 1
        try:
            result["attached"] += _import_one(session, mailbox)
            db.session.commit()
        except GoogleError as exc:
            db.session.rollback()
            result["failed"] += 1
            logger.warning("recording import for class %s failed: %s", session_id, exc)
    return result

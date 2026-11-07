"""Meet auto-recording and the recording-import job (services/google/meet_recordings.py). No test reaches Google: `client.request`
is replaced by a fake that answers like Calendar, Meet and Drive."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import ClassSession, GoogleDriveItem, GoogleJob, Notification, Recording, RecordingException
from services import integrations
from services import recordings as recordings_service
from services.google import client as google_client
from services.google import jobs, meet_recordings
from services.google.client import GoogleError
from tests.test_delivery import call, data, future, iso, world  # noqa: F401

LINK = "https://meet.google.com/abc-defg-hij"
SPACE = "jQCFfuBOdN5z"


class FakeGoogle:
    """Calendar answers with a Meet link; Meet with a space, its conferences and recordings; Drive accepts a share."""

    def __init__(self):
        self.calls = []
        self.auto_record = "OFF"
        self.conferences = []  # [{"name", "endTime"?}]
        self.recordings = {}  # conference name -> [recording]
        self.fail = None

    def __call__(self, method, url, *, subject, scopes, body=None, params=None):
        self.calls.append({"method": method, "url": url, "subject": subject, "scopes": scopes, "body": body, "params": params})
        if self.fail and self.fail[0] in url:
            raise self.fail[1]
        if "calendar/v3" in url:
            event_id = body.get("id") if method == "POST" else url.rsplit("/", 1)[1]
            return {"id": event_id, "hangoutLink": LINK}
        if url.endswith("/spaces/abc-defg-hij"):
            return {"name": f"spaces/{SPACE}", "meetingCode": "abc-defg-hij",
                    "config": {"artifactConfig": {"recordingConfig": {"autoRecordingGeneration": self.auto_record}}}}
        if url.endswith(f"/spaces/{SPACE}") and method == "PATCH":
            self.auto_record = "ON"
            return {"name": f"spaces/{SPACE}"}
        if url.endswith("/conferenceRecords"):
            return {"conferenceRecords": self.conferences}
        if url.endswith("/recordings"):
            name = url.split("/v2/", 1)[1].rsplit("/recordings", 1)[0]
            return {"recordings": self.recordings.get(name, [])}
        if "/permissions" in url:
            return {"id": "perm-1"}
        raise AssertionError(f"unexpected call {method} {url}")


def verify(code, verifier):
    integration = integrations.integrations_repo.get_by_code(code)
    integration.configuration_status, integration.verification_status = "Configured", "Verified"
    integration.verified_by, integration.verified_at, integration.evidence = verifier.user_id, datetime.now(timezone.utc), "Test"
    db.session.commit()


@pytest.fixture
def google(app, monkeypatch, make_user):
    fake = FakeGoogle()
    monkeypatch.setattr(google_client, "request", fake)
    monkeypatch.setattr(google_client, "is_configured", lambda: True)
    admin = make_user(roles=[("SUPER_ADMIN", None)])
    verify("GOOGLE_MEET", admin)
    verify("GOOGLE_DRIVE_RECORDINGS", admin)
    return fake


def online_class(client_, login, people, batch):
    start = future(3)
    body = {"batch_id": batch.batch_id, "title": "Online", "mode": "Live Online", "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}
    return data(call(client_, login, people["ac"], "post", "/class-sessions", json=body), 201)[0]["session_id"]


def session_of(session_id):
    db.session.expire_all()
    return db.session.get(ClassSession, session_id)


def kinds(session_id):
    return [j.kind for j in db.session.execute(select(GoogleJob).where(GoogleJob.entity_id == session_id).order_by(GoogleJob.job_id)).scalars()]


def ended_class(session_id, *, hours_ago=1):
    """Move a linked class into the past and mark it delivered, as the trainer's Finish class would."""
    session = session_of(session_id)
    session.starts_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago + 1)
    session.ends_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    session.state, session.delivered_at = "Delivered", session.ends_at
    db.session.commit()


def recordings_of(session_id):
    db.session.expire_all()
    return list(db.session.execute(select(Recording).where(Recording.session_id == session_id).order_by(Recording.part_no)).scalars())


def linked_with_space(client, login, people, batch, google):
    sid = online_class(client, login, people, batch)
    jobs.run_due()  # the Calendar event and its Meet link
    jobs.run_due()  # auto-record
    return sid


# ---------------------------------------------------------------- auto-record

def test_a_linked_class_is_set_to_record_itself(world, client, login, google):
    people, batch, _ = world
    sid = online_class(client, login, people, batch)
    assert jobs.run_due() == {"done": 1, "retry": 0, "dead": 0}
    assert kinds(sid) == ["CALENDAR_UPSERT", "MEET_AUTO_RECORD"]
    assert jobs.run_due() == {"done": 1, "retry": 0, "dead": 0}

    get, patch = google.calls[-2:]
    assert (get["method"], get["url"]) == ("GET", "https://meet.googleapis.com/v2/spaces/abc-defg-hij")
    assert get["subject"] == "trainer@nipunatechnologies.com" and get["scopes"] == [google_client.MEET_SETTINGS_SCOPE]
    assert (patch["method"], patch["url"]) == ("PATCH", f"https://meet.googleapis.com/v2/spaces/{SPACE}")  # never the meeting code
    assert patch["params"] == {"updateMask": "config.artifactConfig.recordingConfig.autoRecordingGeneration"}
    assert patch["body"] == {"config": {"artifactConfig": {"recordingConfig": {"autoRecordingGeneration": "ON"}}}}
    assert session_of(sid).meet_space_id == SPACE

    # moving the class patches the event again, but the space is set already: no second auto-record job
    later = session_of(sid).starts_at + timedelta(days=1)
    moved = call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule",
                 json={"starts_at": iso(later), "ends_at": iso(later + timedelta(hours=1)), "reason": "Trainer away"})
    assert moved.status_code == 200, moved.get_json()
    jobs.run_due()
    assert kinds(sid).count("MEET_AUTO_RECORD") == 1


def test_a_space_already_recording_is_left_alone(world, client, login, google):
    people, batch, _ = world
    google.auto_record = "ON"
    linked_with_space(client, login, people, batch, google)
    assert not any(c["method"] == "PATCH" and "meet.googleapis.com" in c["url"] for c in google.calls)


def test_when_google_refuses_the_branch_manager_is_told_to_record_by_hand(world, client, login, google):
    people, batch, _ = world
    google.fail = ("/spaces/abc-defg-hij", GoogleError("Google returned 403: insufficient scopes", status=403))
    sid = online_class(client, login, people, batch)
    jobs.run_due()
    assert jobs.run_due() == {"done": 0, "retry": 0, "dead": 1}
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert "Auto-recording not set: Online" in titles
    assert session_of(sid).meet_link == LINK  # the class keeps its link


# ---------------------------------------------------------------- import

def test_a_finished_recording_is_attached_shared_with_the_batch_and_the_class_marked_done(world, client, login, google):
    people, batch, _ = world
    sid = linked_with_space(client, login, people, batch, google)
    db.session.add(GoogleDriveItem(entity_type="batch", entity_id=batch.batch_id, branch_id=batch.branch_id, folder_id="folder-1", folder_name="NIT-GNT-BAT",
                                   group_email="nit-gnt-bat@nipunatechnologies.com"))
    ended_class(sid)

    # the meeting is still going: nothing yet, and the class is asked about again
    google.conferences = [{"name": "conferenceRecords/c1"}]
    google.recordings = {"conferenceRecords/c1": [{"name": "conferenceRecords/c1/recordings/r1", "state": "STARTED"}]}
    assert meet_recordings.import_recordings() == {"checked": 1, "attached": 0, "failed": 0}
    assert recordings_of(sid) == []

    google.conferences = [{"name": "conferenceRecords/c1", "endTime": "2026-11-07T10:00:00Z"}]
    google.recordings = {"conferenceRecords/c1": [{"name": "conferenceRecords/c1/recordings/r1", "state": "FILE_GENERATED",
                                                   "startTime": "2026-11-07T09:00:00Z", "endTime": "2026-11-07T09:55:00Z",
                                                   "driveDestination": {"file": "drive-file-1", "exportUri": "https://drive.google.com/file/d/drive-file-1/view"}}]}
    assert meet_recordings.import_recordings() == {"checked": 1, "attached": 1, "failed": 0}
    [recording] = recordings_of(sid)
    assert (recording.status, recording.media_ref, recording.duration_minutes, recording.source) == ("Processing", "drive-file-1", 55, "Google Drive")

    listing = next(c for c in google.calls if c["url"].endswith("/conferenceRecords"))
    assert listing["params"]["filter"].startswith(f'space.name = "spaces/{SPACE}" AND start_time>=')
    assert listing["scopes"] == [google_client.MEET_READONLY_SCOPE]
    share = next(c for c in google.calls if "/permissions" in c["url"])
    assert share["url"] == "https://www.googleapis.com/drive/v3/files/drive-file-1/permissions"
    assert share["body"] == {"type": "group", "role": "reader", "emailAddress": "nit-gnt-bat@nipunatechnologies.com"}
    assert share["scopes"] == [google_client.DRIVE_FULL_SCOPE] and share["subject"] == "trainer@nipunatechnologies.com"
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert "Recording ready to release: Online" in titles

    # done: never asked about again
    assert session_of(sid).conference_record_id == "c1"
    assert meet_recordings.import_recordings() == {"checked": 0, "attached": 0, "failed": 0}


def test_a_late_file_fills_the_placeholder_and_resolves_the_exception(world, client, login, google):
    people, batch, _ = world
    sid = linked_with_space(client, login, people, batch, google)
    ended_class(sid, hours_ago=5)
    assert recordings_service.check_missing_recordings()["missing_recordings"] == 1
    db.session.commit()

    google.conferences = [{"name": "conferenceRecords/c1", "endTime": "2026-11-07T10:00:00Z"}]
    google.recordings = {"conferenceRecords/c1": [{"name": "r1", "state": "FILE_GENERATED", "driveDestination": {"file": "drive-file-2"}}]}
    assert meet_recordings.import_recordings()["attached"] == 1
    [recording] = recordings_of(sid)
    assert (recording.part_no, recording.status, recording.media_ref) == (1, "Processing", "drive-file-2")
    exceptions = db.session.execute(select(RecordingException).where(RecordingException.session_id == sid)).scalars().all()
    assert exceptions and all(e.status == "Resolved" for e in exceptions)


def test_import_waits_for_the_recordings_switch(world, client, login, google):
    people, batch, _ = world
    integration = integrations.integrations_repo.get_by_code("GOOGLE_DRIVE_RECORDINGS")
    integration.verification_status = "Not Verified"
    db.session.commit()
    assert meet_recordings.import_recordings() == {"skipped": "Google is not configured or Drive recording capture is not verified"}

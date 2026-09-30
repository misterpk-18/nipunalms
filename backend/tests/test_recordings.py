"""Recordings and recording exceptions: registration, release / hold / partial, student access, the recording-check job."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import ActivityEvent, AuditLog, Notification, Recording, RecordingException
from repositories import users as users_repo
from services import recordings as recordings_service
from tests import library_helpers as h
from tests.library_helpers import API, auth, get, post


@pytest.fixture
def world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql):
    return h.build_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql)


@pytest.fixture
def register(client, login, world):
    """register(session=None, **body) -> the new recording, registered by the Guntur coordinator."""

    def _register(session=None, expect=201, **body):
        payload = {"session_id": (session or world.delivered).session_id, "media_ref": "drive-file-1", "duration_minutes": 120, **body}
        response = client.post(f"{API}/recordings", json=payload, headers=auth(login, world.people.ac))
        assert response.status_code == expect, response.get_json()
        return response.get_json()["data"] if expect == 201 else response.get_json()

    return _register


def student_titles(client, login, who):
    return {r["session"]["title"]: r["status"] for r in get(client, "/me/recordings", auth(login, who))}


def actions(entity_id: str) -> list[str]:
    return list(db.session.execute(select(AuditLog.action).where(AuditLog.entity_id == entity_id).order_by(AuditLog.audit_id)).scalars())


# ---------------------------------------------------------------- registering

def test_the_coordinator_registers_a_recording_for_a_delivered_session(client, login, world, register):
    recording = register()
    assert recording["recording_code"].startswith("RCD-") and recording["status"] == "Processing" and recording["part_no"] == 1
    assert recording["session"]["session_code"] == world.delivered.session_code and recording["source"] == "Google Drive"
    assert recording["download_allowed"] is False  # controlled viewing by default
    second = register(media_ref="drive-file-2")
    assert second["part_no"] == 2  # several parts of one class
    assert actions(recording["recording_code"]) == ["RECORDING_REGISTERED"]


def test_registration_rules(client, login, world, register, make_session, run_sql):
    assert register(world.upcoming, expect=422)["error"]["message"].startswith("The class has not been delivered")
    placeholder = register(world.upcoming, status="Unavailable", media_ref=None)  # a placeholder for a class still to come
    assert placeholder["status"] == "Unavailable"
    cancelled = make_session(world.g1, world.people.t1, datetime.now(timezone.utc), state="Cancelled", title="Cancelled")
    assert register(cancelled, expect=422)["error"]["message"] == "A cancelled class session has no recording"
    for who, expected in ((world.people.t1, 403), (world.people.bm, 403), (world.students.s1, 403)):
        response = client.post(f"{API}/recordings", json={"session_id": world.delivered.session_id}, headers=auth(login, who))
        assert response.status_code == expected
    assert client.post(f"{API}/recordings", json={"session_id": world.delivered.session_id}, headers=auth(login, world.people.ac_vij)).status_code == 404
    assert client.post(f"{API}/recordings", json={"session_id": 999999}, headers=auth(login, world.people.ac)).status_code == 404
    assert client.post(f"{API}/recordings", json={}, headers=auth(login, world.people.ac)).status_code == 400
    assert client.post(f"{API}/recordings", json={"session_id": world.delivered.session_id, "source": "Vimeo"},
                       headers=auth(login, world.people.ac)).status_code == 400


def test_update_records_the_media_reference_and_policy(client, login, world, register):
    recording = register(media_ref=None)
    coordinator = auth(login, world.people.ac)
    updated = client.patch(f"{API}/recordings/{recording['recording_id']}", headers=coordinator,
                           json={"media_ref": "drive-abc", "download_allowed": True, "duration_minutes": 118})
    assert updated.status_code == 200 and updated.get_json()["data"]["media_ref"] == "drive-abc"
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "RECORDING_UPDATED")).scalar_one()
    assert entry.old_values["download_allowed"] is False and entry.new_values["download_allowed"] is True
    assert client.patch(f"{API}/recordings/{recording['recording_id']}", headers=coordinator, json={}).status_code == 400


# ---------------------------------------------------------------- release, hold, partial

def test_release_needs_the_media_reference_and_a_delivered_class(client, login, world, register):
    coordinator = auth(login, world.people.ac)
    no_media = register(media_ref=None)
    refused = client.post(f"{API}/recordings/{no_media['recording_id']}/release", headers=coordinator)
    assert refused.status_code == 422 and "Drive file reference" in refused.get_json()["error"]["message"]
    early = register(world.upcoming, status="Unavailable")
    client.patch(f"{API}/recordings/{early['recording_id']}", headers=coordinator, json={"media_ref": "x"})
    assert client.post(f"{API}/recordings/{early['recording_id']}/release", headers=coordinator).status_code == 422


def test_release_makes_the_recording_watchable_and_tells_the_batch(client, login, world, register):
    recording = register()
    assert student_titles(client, login, world.students.s1) == {"OOP basics": "Processing"}
    released = post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    assert released["status"] == "Released" and released["released_at"]
    assert student_titles(client, login, world.students.s1) == {"OOP basics": "Released"}
    assert student_titles(client, login, world.students.s2) == {}  # not allocated to the batch
    assert student_titles(client, login, world.students.s3) == {}  # another branch
    user = users_repo.get_by_student_id(world.students.s1.student_id)
    notice = db.session.execute(select(Notification).where(Notification.recipient_user_id == user.user_id, Notification.category == "Recording")).scalar_one()
    assert notice.title == "Recording available: OOP basics" and notice.link == "/recordings"
    assert actions(recording["recording_code"]) == ["RECORDING_REGISTERED", "RECORDING_RELEASED"]
    assert post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac), 422) is None


def test_student_entry_shows_expiry_download_policy_and_hides_internal_details(client, login, world, register):
    recording = register()
    post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    entry = get(client, "/me/recordings", auth(login, world.students.s1))[0]
    assert entry["access"] == {"state": "Available", "expiry": "2027-03-02", "extended": False}
    assert entry["download_allowed"] is False and entry["playable"] is True and entry["duration_minutes"] == 120
    assert entry["session"]["trainer"]["full_name"] == "Trainer One" and entry["course"]["course_code"] == "NIT-CRS-047"
    assert entry["topic"]["title"] == "OOP & Collections" and "media_ref" not in entry and "hold_reason" not in entry


def test_holding_withdraws_the_recording_and_raises_an_exception(client, login, world, register):
    recording = register()
    coordinator, student = auth(login, world.people.ac), auth(login, world.students.s1)
    post(client, f"/recordings/{recording['recording_id']}/release", coordinator)
    assert client.post(f"{API}/recordings/{recording['recording_id']}/hold", headers=coordinator, json={}).status_code == 400

    held = post(client, f"/recordings/{recording['recording_id']}/hold", coordinator, json={"reason": "Whiteboard shows sample PII"})
    assert held["status"] == "Held" and held["hold_reason"] == "Whiteboard shows sample PII"
    rows = get(client, "/recording-exceptions", coordinator)
    assert len(rows) == 1 and rows[0]["issue_type"] == "Held" and rows[0]["status"] == "Open" and rows[0]["owner"] == "Academic Coordinator GNT"
    assert rows[0]["exception_code"].startswith("RX-") and rows[0]["auto_raised"] is True
    # the student sees it is held, without the reason, and cannot watch it
    entry = get(client, "/me/recordings", student)[0]
    assert entry["status"] == "Held" and entry["playable"] is False and "PII" not in str(entry)
    blocked = client.post(f"{API}/recordings/{recording['recording_id']}/watch", headers=student)
    assert blocked.status_code == 422 and "Held for review" in blocked.get_json()["error"]["message"]
    assert client.post(f"{API}/recordings/{recording['recording_id']}/hold", headers=coordinator, json={"reason": "again"}).status_code == 422

    # releasing again closes the exception
    post(client, f"/recordings/{recording['recording_id']}/release", coordinator)
    resolved = get(client, f"/recording-exceptions/{rows[0]['exception_id']}", coordinator)
    assert resolved["status"] == "Resolved" and "released" in resolved["resolution_note"]
    assert "RECORDING_EXCEPTION_RESOLVED" in actions(rows[0]["exception_code"])


def test_partial_recordings_stay_watchable_and_keep_the_gap_open(client, login, world, register):
    recording = register()
    coordinator, student = auth(login, world.people.ac), auth(login, world.students.s1)
    assert client.post(f"{API}/recordings/{recording['recording_id']}/partial", headers=coordinator, json={"note": "x"}).status_code == 200
    second = register(media_ref=None)
    refused = client.post(f"{API}/recordings/{second['recording_id']}/partial", headers=coordinator, json={"note": "Second hour missing"})
    assert refused.status_code == 422  # a partial recording needs something to watch
    entry = get(client, "/me/recordings", student)[0]
    assert entry["status"] == "Partial" and entry["playable"] is True and entry["status_note"] == "x"
    exception = get(client, "/recording-exceptions", coordinator)[0]
    assert exception["issue_type"] == "Partial" and "Partial recording" in exception["issue"]
    assert post(client, f"/recordings/{recording['recording_id']}/watch", student)["status"] == "Partial"


def test_mark_unavailable_needs_a_reason_and_raises_an_exception(client, login, world, register):
    recording = register()
    coordinator = auth(login, world.people.ac)
    assert client.post(f"{API}/recordings/{recording['recording_id']}/unavailable", headers=coordinator, json={}).status_code == 400
    assert post(client, f"/recordings/{recording['recording_id']}/unavailable", coordinator, json={"reason": "File deleted"})["status"] == "Unavailable"
    assert get(client, "/recording-exceptions?issue_type=Unavailable", coordinator)[0]["issue"] == "File deleted"


def test_only_the_branch_coordinator_or_super_admin_manages_recordings(client, login, world, register):
    recording = register()
    rid = recording["recording_id"]
    for who, expected in ((world.people.t1, 403), (world.people.bm, 403), (world.people.founder, 403), (world.people.ac_vij, 404),
                          (world.students.s1, 403)):
        assert client.post(f"{API}/recordings/{rid}/release", headers=auth(login, who)).status_code == expected
    assert post(client, f"/recordings/{rid}/release", auth(login, world.people.admin))["status"] == "Released"


# ---------------------------------------------------------------- watching

def test_watching_checks_entitlement_and_records_activity(client, login, world, register):
    recording = register()
    rid = recording["recording_id"]
    post(client, f"/recordings/{rid}/release", auth(login, world.people.ac))
    watching = post(client, f"/recordings/{rid}/watch", auth(login, world.students.s1))
    assert watching["playback"]["mode"] == "stream" and watching["playback"]["integration_status"] == "Not Verified"
    assert watching["playback"]["available"] is False and "Not Verified" in watching["playback"]["message"]
    assert "media_ref" not in str(watching)
    event = db.session.execute(select(ActivityEvent).where(ActivityEvent.kind == "recording_view")).scalar_one()
    assert event.student_id == world.students.s1.student_id and event.detail["session_code"] == world.delivered.session_code
    for who in (world.students.s2, world.students.s3):
        assert client.post(f"{API}/recordings/{rid}/watch", headers=auth(login, who)).status_code == 404
    assert client.post(f"{API}/recordings/{rid}/watch", headers=auth(login, world.people.t1)).status_code == 403


def test_watching_reports_a_verified_drive_integration(client, login, world, register, run_sql):
    recording = register()
    post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    run_sql("UPDATE integrations SET verification_status = 'Verified' WHERE integration_code = 'GOOGLE_DRIVE_RECORDINGS'")
    playback = post(client, f"/recordings/{recording['recording_id']}/watch", auth(login, world.students.s1))["playback"]
    assert playback["available"] is True and playback["message"] is None


def test_expired_access_blocks_watching_but_not_the_listing(client, login, world, register, run_sql):
    recording = register()
    post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    run_sql("UPDATE enrolments SET joining_date = :d WHERE student_id = :s", d=h.days_ago(400), s=world.students.s1.student_id)
    student = auth(login, world.students.s1)
    entry = get(client, "/me/recordings", student)[0]
    assert entry["access"]["state"] == "Expired" and entry["playable"] is False
    blocked = client.post(f"{API}/recordings/{recording['recording_id']}/watch", headers=student)
    assert blocked.status_code == 422 and "ended on" in blocked.get_json()["error"]["message"]


def test_a_transfer_keeps_earlier_recordings_visible(client, login, world, register, allocate, make_batch):
    recording = register()
    post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    other = make_batch(1, "NIT-CRS-047", trainers=[world.people.t2], state="Running", curriculum_version_id=world.version_id)
    allocate(world.students.s1, other)  # ends the G1 allocation as Transferred
    assert student_titles(client, login, world.students.s1) == {"OOP basics": "Released"}


def test_no_joining_date_shows_pending_access(client, login, world, register, run_sql):
    recording = register()
    post(client, f"/recordings/{recording['recording_id']}/release", auth(login, world.people.ac))
    run_sql("UPDATE enrolments SET status = 'Allocated — awaiting first regular class', joining_date = NULL WHERE student_id = :s",
            s=world.students.s1.student_id)
    entry = get(client, "/me/recordings", auth(login, world.students.s1))[0]
    assert entry["access"]["state"] == "Pending" and entry["access"]["expiry"] is None and entry["playable"] is True


# ---------------------------------------------------------------- staff lists

def test_recordings_list_is_scoped_by_branch_and_teaching(client, login, world, register):
    recording = register()
    assert [r["recording_id"] for r in get(client, "/recordings", auth(login, world.people.t1))] == [recording["recording_id"]]
    assert get(client, "/recordings", auth(login, world.people.t2)) == []
    assert get(client, "/recordings", auth(login, world.people.ac_vij)) == []
    assert len(get(client, "/recordings", auth(login, world.people.bm))) == 1 == len(get(client, "/recordings", auth(login, world.people.founder)))
    assert len(get(client, f"/recordings?batch_id={world.g1.batch_id}&status=Processing", auth(login, world.people.admin))) == 1
    assert get(client, "/recordings?status=Released", auth(login, world.people.admin)) == []
    detail = get(client, f"/recordings/{recording['recording_id']}", auth(login, world.people.bm))
    assert detail["session"]["batch"]["batch_code"] == world.g1.batch_code and detail["exceptions"] == []
    assert client.get(f"{API}/recordings/{recording['recording_id']}", headers=auth(login, world.people.ac_vij)).status_code == 404
    assert client.get(f"{API}/recordings", headers=auth(login, world.students.s1)).status_code == 403


# ---------------------------------------------------------------- exceptions

def test_exceptions_are_owned_and_resolved_with_a_note(client, login, world, register):
    recording = register()
    coordinator = auth(login, world.people.ac)
    post(client, f"/recordings/{recording['recording_id']}/hold", coordinator, json={"reason": "PII"})
    exception_id = get(client, "/recording-exceptions", coordinator)[0]["exception_id"]

    started = post(client, f"/recording-exceptions/{exception_id}/start", coordinator)
    assert started["status"] == "In Progress" and started["owner_user"]["full_name"] == "AC Guntur"
    assert client.post(f"{API}/recording-exceptions/{exception_id}/start", headers=coordinator).status_code == 422
    assert client.post(f"{API}/recording-exceptions/{exception_id}/resolve", headers=coordinator, json={}).status_code == 400
    # the trainer of the batch sees it but cannot act on it; another branch cannot see it
    assert get(client, f"/recording-exceptions/{exception_id}", auth(login, world.people.t1))["issue_type"] == "Held"
    assert client.post(f"{API}/recording-exceptions/{exception_id}/resolve", headers=auth(login, world.people.t1),
                       json={"resolution_note": "x"}).status_code == 403
    assert client.get(f"{API}/recording-exceptions/{exception_id}", headers=auth(login, world.people.ac_vij)).status_code == 404
    # the Branch Manager covers
    done = post(client, f"/recording-exceptions/{exception_id}/resolve", auth(login, world.people.bm), json={"resolution_note": "Redacted and re-uploaded"})
    assert done["status"] == "Resolved" and done["resolution_note"] == "Redacted and re-uploaded" and done["escalation"] is None
    assert client.post(f"{API}/recording-exceptions/{exception_id}/resolve", headers=coordinator, json={"resolution_note": "again"}).status_code == 422
    assert actions(done["exception_code"]) == ["RECORDING_EXCEPTION_RAISED", "RECORDING_EXCEPTION_STARTED", "RECORDING_EXCEPTION_RESOLVED"]


def test_raising_an_exception_manually_and_filters(client, login, world, register):
    trainer = auth(login, world.people.t1)
    body = {"session_id": world.delivered.session_id, "issue_type": "Unavailable", "issue": "Class was not captured"}
    raised = post(client, "/recording-exceptions", trainer, 201, json=body)
    assert raised["auto_raised"] is False and raised["owner"] == "Academic Coordinator GNT"
    assert post(client, "/recording-exceptions", auth(login, world.people.ac), 201, json=body)["exception_id"] == raised["exception_id"]  # not duplicated
    assert client.post(f"{API}/recording-exceptions", json={**body, "session_id": world.upcoming.session_id}, headers=auth(login, world.people.t2)).status_code == 404
    assert client.post(f"{API}/recording-exceptions", json={**body, "issue_type": "Lost"}, headers=trainer).status_code == 400
    assert client.post(f"{API}/recording-exceptions", json=body, headers=auth(login, world.students.s1)).status_code == 403
    admin = auth(login, world.people.admin)
    assert len(get(client, "/recording-exceptions?status=Open", admin)) == 1
    assert get(client, "/recording-exceptions?status=Resolved", admin) == []
    assert len(get(client, f"/recording-exceptions?branch_id=1&batch_id={world.g1.batch_id}", admin)) == 1
    assert get(client, "/recording-exceptions?branch_id=2", admin) == []


def test_integration_exceptions_belong_to_the_super_admin(client, login, world, make_session):
    live = make_session(world.g1, world.people.t1, datetime.now(timezone.utc) - timedelta(hours=6), mode="Live Online",
                        state="Delivered", delivered_at=datetime.now(timezone.utc) - timedelta(hours=4), title="Live class",
                        meet_status="Pending Verification")
    raised = post(client, "/recording-exceptions", auth(login, world.people.t1), 201,
                  json={"session_id": live.session_id, "issue_type": "Integration Unavailable", "issue": "Organizer licence Pending Verification"})
    assert raised["owner"] == "Super Admin" and raised["owner_role"] == "SUPER_ADMIN"
    exception_id = raised["exception_id"]
    assert client.post(f"{API}/recording-exceptions/{exception_id}/resolve", headers=auth(login, world.people.ac),
                       json={"resolution_note": "x"}).status_code == 403  # technical fault: Super Admin only
    assert post(client, f"/recording-exceptions/{exception_id}/resolve", auth(login, world.people.admin),
                json={"resolution_note": "Licence confirmed"})["status"] == "Resolved"


# ---------------------------------------------------------------- the recording-check job

def _delivered(make_session, world, hours_ago: float, **columns):
    delivered_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return make_session(world.g1, world.people.t1, delivered_at - timedelta(hours=2), state="Delivered", delivered_at=delivered_at,
                        **{"title": f"Class {hours_ago}h ago", **columns})


def test_the_job_flags_delivered_sessions_without_a_recording(app, world, make_session):
    world.delivered.delivered_at = datetime.now(timezone.utc) - timedelta(hours=2)  # inside the 4 hour window: not yet flagged
    world.delivered.ends_at = world.delivered.delivered_at
    old = _delivered(make_session, world, 6)
    online = _delivered(make_session, world, 7, mode="Live Online", meet_status="Pending Verification")
    _delivered(make_session, world, 1)
    make_session(world.g1, world.people.t1, datetime.now(timezone.utc) - timedelta(hours=9), state="Cancelled", title="Cancelled")
    db.session.commit()

    result = recordings_service.check_missing_recordings()
    assert result["missing_recordings"] == 2
    exceptions = {e.session_id: e for e in db.session.execute(select(RecordingException)).scalars()}
    assert exceptions[old.session_id].issue_type == "Unavailable" and exceptions[old.session_id].owner_role == "ACADEMIC_COORDINATOR"
    assert exceptions[old.session_id].issue == "No recording mapped to actual Class Session"
    assert exceptions[online.session_id].issue_type == "Integration Unavailable" and exceptions[online.session_id].owner_role == "SUPER_ADMIN"
    assert all(e.auto_raised for e in exceptions.values())
    placeholder = db.session.execute(select(Recording).where(Recording.session_id == old.session_id)).scalar_one()
    assert placeholder.status == "Unavailable" and placeholder.created_by is None
    # a second run changes nothing, and resolving without a recording does not bring the alert back
    assert recordings_service.check_missing_recordings()["missing_recordings"] == 0
    assert len(list(db.session.execute(select(RecordingException)).scalars())) == 2


def test_the_job_escalates_old_exceptions_once(app, world, make_session):
    world.delivered.delivered_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session = _delivered(make_session, world, 30)
    db.session.commit()
    recordings_service.check_missing_recordings()
    exception = db.session.execute(select(RecordingException)).scalar_one()
    assert recordings_service.escalation_for(exception, datetime.now(timezone.utc)) == "Branch Manager and Super Admin"
    bm_notices = lambda: list(db.session.execute(select(Notification).where(Notification.event_key.like("rx-escalated-24-%"))).scalars())
    assert len(bm_notices()) >= 1  # the Branch Manager and the Super Admin are told
    before = len(bm_notices())
    recordings_service.check_missing_recordings()
    assert len(bm_notices()) == before  # no duplicate notices on the next run

    # 49 hours after the class ended: Founder / CEO as well
    later = datetime.now(timezone.utc) + timedelta(hours=20)
    recordings_service.check_missing_recordings(now=later)
    assert list(db.session.execute(select(Notification).where(Notification.event_key.like("rx-escalated-48-%"))).scalars())
    assert recordings_service.escalation_for(exception, later) == "Founder / CEO"
    assert session.session_id == exception.session_id


def test_the_job_command_runs_from_the_cli(app, world, make_session):
    world.delivered.delivered_at = datetime.now(timezone.utc) - timedelta(hours=1)
    _delivered(make_session, world, 6)
    db.session.commit()
    result = app.test_cli_runner().invoke(args=["jobs", "run", "recording-check"])
    assert result.exit_code == 0 and "recording-check: {'missing_recordings': 1" in result.output
    assert "recording-check" in app.test_cli_runner().invoke(args=["jobs", "list"]).output
    assert app.test_cli_runner().invoke(args=["jobs", "run", "nope"]).exit_code != 0

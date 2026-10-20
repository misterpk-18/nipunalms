"""Google Workspace slice 1 (docs/GOOGLE_WORKSPACE.md): class Calendar events and Meet links through the google-sync job.
No test reaches Google: `client.request` is replaced by a fake that records what would have been sent."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import ClassSession, GoogleJob, MeetEvent, Notification
from repositories import google as google_repo
from services import integrations
from services.google import class_events, jobs
from services.google import client as google_client
from services.google.client import GoogleError
from services.jobs import JOBS
from tests.test_delivery import call, data, future, iso, world  # noqa: F401

LINK = "https://meet.google.com/abc-defg-hij"
OTHER_LINK = "https://meet.google.com/zzz-yyyy-xxx"


class FakeGoogle:
    """Stands in for client.request: remembers each call, answers like Calendar, and can be told to fail."""

    def __init__(self):
        self.calls = []
        self.fail = []  # errors to raise on the next calls, first in first out
        self.link = LINK
        self.existing_ids = set()

    def __call__(self, method, url, *, subject, scopes, body=None, params=None):
        self.calls.append({"method": method, "url": url, "subject": subject, "scopes": scopes, "body": body, "params": params})
        if self.fail:
            error = self.fail.pop(0)
            if error is not None:
                raise error
        if method == "DELETE":
            return {}
        if method == "POST":
            if body["id"] in self.existing_ids:
                raise GoogleError("Google returned 409: The requested identifier already exists.", status=409)
            self.existing_ids.add(body["id"])
            event_id = body["id"]
        else:
            event_id = url.rsplit("/", 1)[1]
        event = {"id": event_id}
        if self.link:
            event["hangoutLink"] = self.link
        return event


def verify_meet(verifier):
    integration = integrations.integrations_repo.get_by_code("GOOGLE_MEET")
    integration.configuration_status, integration.verification_status = "Configured", "Verified"
    integration.verified_by, integration.verified_at, integration.evidence = verifier.user_id, datetime.now(timezone.utc), "Test class event"
    db.session.commit()


@pytest.fixture
def google(app, monkeypatch, make_user):
    """Google configured and GOOGLE_MEET verified, with a fake in place of the network."""
    fake = FakeGoogle()
    monkeypatch.setattr(google_client, "request", fake)
    monkeypatch.setattr(google_client, "is_configured", lambda: True)
    verify_meet(make_user(roles=[("SUPER_ADMIN", None)]))
    return fake


def online_class(client_, login, people, batch, *, days=3, mode="Live Online"):
    start = future(days)
    body = {"batch_id": batch.batch_id, "title": "Online", "mode": mode, "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}
    return data(call(client_, login, people["ac"], "post", "/class-sessions", json=body), 201)[0]["session_id"]


def session_of(session_id):
    db.session.expire_all()
    return db.session.get(ClassSession, session_id)


def jobs_of(session_id):
    return list(db.session.execute(select(GoogleJob).where(GoogleJob.entity_id == session_id).order_by(GoogleJob.job_id)).scalars())


def run():
    return jobs.run_due()


# ---------------------------------------------------------------- the switch

def test_nothing_is_queued_while_google_is_off(world, client, login):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    assert jobs_of(sid) == []
    assert session_of(sid).meet_status == "Pending Verification"
    assert run() == {"skipped": "Google is not configured or its integration is not verified"}


def test_a_verified_register_entry_alone_is_not_enough(world, client, login):
    people, batch, student = world
    verify_meet(people["admin"])
    sid = online_class(client, login, people, batch)  # no service-account key in the tests
    assert jobs_of(sid) == []


def test_classroom_classes_never_queue(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch, mode="Classroom")
    assert jobs_of(sid) == []


# ---------------------------------------------------------------- create, link, move, cancel

def test_a_new_online_class_gets_an_event_and_a_linked_meet(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    [job] = jobs_of(sid)
    assert (job.kind, job.state) == ("CALENDAR_UPSERT", "Queued")
    assert run() == {"done": 1, "retry": 0, "dead": 0}

    [sent] = google.calls
    assert sent["method"] == "POST"
    assert sent["scopes"] == [google_client.CALENDAR_SCOPE]
    assert sent["body"]["id"] == f"lms{sid:010d}"
    assert sent["body"]["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {"type": "hangoutsMeet"}
    assert sent["body"]["attendees"] == [{"email": people["g1"].email}]  # no student holds a seat yet
    assert sent["body"]["summary"].endswith("Online")
    assert sent["params"] == {"conferenceDataVersion": 1, "sendUpdates": "all"}

    session = session_of(sid)
    assert (session.meet_status, session.meet_link, session.calendar_event_id) == ("Linked", LINK, f"lms{sid:010d}")
    events = db.session.execute(select(MeetEvent.event_type, MeetEvent.detail).where(MeetEvent.session_id == sid)).all()
    assert any(kind == "Link associated" and "Google Calendar" in detail for kind, detail in events)
    assert jobs_of(sid)[0].state == "Succeeded"


def test_the_event_is_made_in_the_branch_mailbox(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    from models import Branch
    assert google.calls[0]["subject"] == db.session.get(Branch, batch.branch_id).mailbox
    db.session.execute(db.text("INSERT INTO branch_google_config (branch_id, calendar_mailbox) VALUES (:b, 'classes@example.test')"),
                       {"b": batch.branch_id})
    other = online_class(client, login, people, batch, days=4)
    run()
    assert google.calls[-1]["subject"] == "classes@example.test"
    assert session_of(other).meet_status == "Linked"


def test_moving_a_class_patches_the_same_event(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    start = future(5)
    call(client, login, people["ac"], "post", f"/class-sessions/{sid}/reschedule",
         json={"starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1)), "reason": "Trainer unwell"})
    assert [j.state for j in jobs_of(sid)] == ["Succeeded", "Queued"]
    run()
    patch = google.calls[-1]
    assert patch["method"] == "PATCH" and patch["url"].endswith(f"/events/lms{sid:010d}")
    assert "conferenceData" not in patch["body"]  # the class already has its Meet
    assert datetime.fromisoformat(patch["body"]["start"]["dateTime"]) == start
    assert session_of(sid).meet_link == LINK


def test_cancelling_a_class_deletes_its_event(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    call(client, login, people["ac"], "post", f"/class-sessions/{sid}/cancel", json={"reason": "Holiday"})
    run()
    assert google.calls[-1]["method"] == "DELETE"
    assert session_of(sid).calendar_event_id is None


def test_a_class_that_becomes_a_classroom_class_loses_its_event(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    call(client, login, people["ac"], "patch", f"/class-sessions/{sid}", json={"mode": "Classroom", "room": "Lab 2"})
    run()
    assert google.calls[-1]["method"] == "DELETE"
    session = session_of(sid)
    assert (session.calendar_event_id, session.meet_status, session.meet_link) == (None, "Not Required", None)


def test_a_link_entered_by_hand_is_kept(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    data(call(client, login, people["ac"], "put", f"/class-sessions/{sid}/meet", json={"meet_link": OTHER_LINK}), 200)
    assert run() == {"done": 1, "retry": 0, "dead": 0}
    assert google.calls == []
    assert session_of(sid).meet_link == OTHER_LINK


def test_a_replacement_class_waits_for_approval_before_it_is_queued(world, client, login, google):
    people, batch, student = world
    start = future(3)
    body = {"batch_id": batch.batch_id, "title": "Extra", "mode": "Live Online", "purpose": "Extra", "purpose_reference": "Revision", "owner_user_id": people["ac"].user_id, "due_on": future(3).date().isoformat(),
            "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=1))}
    sid = data(call(client, login, people["ac"], "post", "/class-sessions", json=body), 201)[0]["session_id"]
    assert jobs_of(sid) == []
    data(call(client, login, people["admin"], "post", f"/class-sessions/{sid}/approval", json={"decision": "Approved"}), 200)
    assert [j.kind for j in jobs_of(sid)] == ["CALENDAR_UPSERT"]


# ---------------------------------------------------------------- students are invited

def test_the_students_of_the_batch_are_invited_and_cannot_see_each_other(world, client, login, google, allocate, make_student):  # noqa: F811
    people, batch, student = world
    other = make_student()
    allocate(student, batch)
    allocate(other, batch)
    sid = online_class(client, login, people, batch)
    run()
    body = google.calls[-1]["body"]
    assert [a["email"] for a in body["attendees"]] == [people["g1"].email, student.email, other.email]
    assert body["guestsCanSeeOtherGuests"] is False and google.calls[-1]["params"]["sendUpdates"] == "all"
    assert session_of(sid).meet_status == "Linked"


def test_a_student_of_another_batch_is_not_invited_and_a_shared_class_invites_both(world, client, login, google, allocate, make_student, make_batch):  # noqa: F811
    people, batch, student = world
    other_batch = make_batch(1, trainers=[people["g2"]], state="Running")
    outsider = make_student()
    allocate(outsider, other_batch)
    sid = online_class(client, login, people, batch)
    run()
    assert outsider.email not in [a["email"] for a in google.calls[-1]["body"]["attendees"]]
    db.session.execute(db.text("INSERT INTO session_rosters (session_id, batch_id, coverage_note, verified_by) VALUES (:s, :b, 'Same topic', :u)"),
                       {"s": sid, "b": other_batch.batch_id, "u": people["admin"].user_id})
    db.session.commit()
    class_events.enqueue_upsert(session_of(sid))
    run()
    assert outsider.email in [a["email"] for a in google.calls[-1]["body"]["attendees"]]


def test_a_seat_taken_or_ended_updates_the_invitations_of_upcoming_online_classes(world, client, login, google, allocate, make_student):  # noqa: F811
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    assert [a["email"] for a in google.calls[-1]["body"]["attendees"]] == [people["g1"].email]

    allocate(student, batch)
    assert [j.state for j in jobs_of(sid)] == ["Succeeded", "Queued"]
    run()
    assert student.email in [a["email"] for a in google.calls[-1]["body"]["attendees"]]
    assert google.calls[-1]["method"] == "PATCH"

    from repositories import students as students_repo
    from services import allocations
    allocations.end(next(e for e in students_repo.enrolments_of_student(student.student_id) if e.course_id == batch.course_id))
    db.session.commit()
    run()
    assert student.email not in [a["email"] for a in google.calls[-1]["body"]["attendees"]]


def test_a_class_with_no_event_yet_is_not_queued_by_a_seat_change(world, client, login, google, allocate):  # noqa: F811
    people, batch, student = world
    sid = online_class(client, login, people, batch)  # its create job is still queued, so it already covers a new seat
    allocate(student, batch)
    assert len(jobs_of(sid)) == 1


def test_a_bad_address_is_left_out_rather_than_failing_the_event(world, client, login, google, allocate):  # noqa: F811
    people, batch, student = world
    db.session.execute(db.text("UPDATE students SET email = 'not an address' WHERE student_id = :s"), {"s": student.student_id})
    db.session.commit()
    allocate(student, batch)
    online_class(client, login, people, batch)
    run()
    assert [a["email"] for a in google.calls[-1]["body"]["attendees"]] == [people["g1"].email]


# ---------------------------------------------------------------- retries

def test_repeated_changes_share_one_open_job(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    class_events.enqueue_upsert(session_of(sid))
    class_events.enqueue_upsert(session_of(sid))
    assert len(jobs_of(sid)) == 1


def test_a_retry_after_a_lost_reply_finds_the_same_event(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    google.existing_ids.add(f"lms{sid:010d}")  # the first insert reached Google, its reply did not reach us
    run()
    assert [c["method"] for c in google.calls] == ["POST", "PATCH"]
    assert session_of(sid).meet_status == "Linked"


def test_an_event_deleted_in_calendar_is_made_again(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    run()
    google.fail = [GoogleError("Google returned 404: Not Found", status=404)]
    class_events.enqueue_upsert(session_of(sid))
    run()
    # Calendar keeps a deleted event's id, so the insert meets a 409 and the same event is patched back to life
    assert [c["method"] for c in google.calls[-3:]] == ["PATCH", "POST", "PATCH"]
    assert session_of(sid).meet_status == "Linked"


def test_a_missing_meet_link_is_retried_and_the_event_kept(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    google.link = None  # Google is still making the conference
    assert run() == {"done": 0, "retry": 1, "dead": 0}
    [job] = jobs_of(sid)
    assert job.state == "Failed" and job.attempts == 1 and job.next_attempt_at > datetime.now(timezone.utc) + timedelta(minutes=4)
    session = session_of(sid)
    assert session.calendar_event_id and session.meet_status == "Pending Verification"
    assert run() == {"done": 0, "retry": 0, "dead": 0}  # not due yet

    google.link = LINK
    job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert run() == {"done": 1, "retry": 0, "dead": 0}
    assert google.calls[-1]["method"] == "PATCH"  # the same event, asked again
    assert session_of(sid).meet_link == LINK


def test_backoff_grows_then_the_job_dies_and_the_class_shows_failed(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    waits = []
    for attempt in range(jobs.MAX_ATTEMPTS):
        google.fail = [GoogleError("Google returned 503", status=503, retryable=True)]
        outcome = run()
        [job] = jobs_of(sid)
        if job.state == "Failed":
            waits.append(job.next_attempt_at - datetime.now(timezone.utc))
            job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.session.commit()
    assert outcome == {"done": 0, "retry": 0, "dead": 1}
    assert [round(w.total_seconds() / 60) for w in waits] == [5, 15, 60, 360, 1440]
    [job] = jobs_of(sid)
    assert (job.state, job.attempts) == ("Dead", jobs.MAX_ATTEMPTS) and "503" in job.last_error
    session = session_of(sid)
    assert (session.meet_status, session.meet_link) == ("Unavailable", None)
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert any(t.startswith("Meet association failed") for t in titles)


def test_a_refused_delegation_is_not_retried(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    google.fail = [GoogleError("Google refused the service account for a@b.test: unauthorized_client")]
    assert run() == {"done": 0, "retry": 0, "dead": 1}
    assert session_of(sid).meet_status == "Unavailable"


def test_staff_can_retry_after_a_failure_and_a_dead_job_can_be_requeued(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    google.fail = [GoogleError("nope")]
    run()
    assert session_of(sid).meet_status == "Unavailable"
    data(call(client, login, people["ac"], "post", f"/class-sessions/{sid}/meet/reset"), 200)
    assert [j.state for j in jobs_of(sid)] == ["Dead", "Queued"]
    run()
    assert session_of(sid).meet_status == "Linked"

    class_events.enqueue_upsert(session_of(sid))
    google.fail = [GoogleError("nope")]
    run()
    dead = jobs_of(sid)[-1]
    assert dead.state == "Dead"
    assert jobs.retry_dead(dead.job_id).state == "Queued"
    assert jobs.retry_dead(dead.job_id) is None  # only a dead job can be requeued


def test_a_job_left_running_by_a_crashed_run_is_taken_again(world, client, login, google):
    people, batch, student = world
    sid = online_class(client, login, people, batch)
    [job] = jobs_of(sid)
    job.state, job.started_at = "Running", datetime.now(timezone.utc) - timedelta(minutes=20)
    db.session.commit()
    assert run()["done"] == 1


def test_the_job_is_registered_with_the_other_jobs(app):
    assert "google-sync" in JOBS

"""Google Workspace slice 4 (docs/GOOGLE_WORKSPACE.md §7): what the Super Admin and Founder see and do. No Google is called."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, GoogleJob
from repositories import google as google_repo
from services.google import client as google_client
from tests.test_google_calendar import FakeGoogle, online_class, run, verify_meet
from tests.test_delivery import world  # noqa: F401

API = "/api/v1/google"


@pytest.fixture
def admin(make_user, login):
    user = make_user(roles=[("SUPER_ADMIN", None)])
    return user, login(user.email)


def a_dead_job(world, client, login, monkeypatch):  # noqa: F811
    """A class whose Meet link could not be made: its job is Dead."""
    people, batch, student = world
    fake = FakeGoogle()
    monkeypatch.setattr(google_client, "request", fake)
    monkeypatch.setattr(google_client, "is_configured", lambda: True)
    verify_meet(people["admin"])
    sid = online_class(client, login, people, batch)
    from services.google.client import GoogleError
    fake.fail = [GoogleError("Google refused the service account")]
    run()
    return sid, db.session.execute(select(GoogleJob)).scalars().first()


# ---------------------------------------------------------------- access

def test_only_super_admin_and_founder_see_the_google_screens(client, make_user, login):
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    for role in (("BRANCH_MANAGER", 1), ("TRAINER", 1)):
        who = make_user(roles=[role])
        for path in ("/overview", "/jobs", "/emails", "/branches"):
            assert client.get(API + path, headers=login(who.email)).status_code == 403
    for path in ("/overview", "/jobs", "/emails", "/branches"):
        assert client.get(API + path, headers=login(founder.email)).status_code == 200
        assert client.get(API + path).status_code == 401


# ---------------------------------------------------------------- overview, jobs, retry

def test_the_overview_says_what_is_on_and_what_needs_attention(world, client, login, monkeypatch):  # noqa: F811
    people, batch, student = world
    before = client.get(f"{API}/overview", headers=login(people["admin"].email)).get_json()["data"]
    assert before["configured"] is False and before["problems"] == []
    assert {f["integration_code"]: f["live"] for f in before["features"]} == {"GOOGLE_MEET": False, "GOOGLE_DRIVE": False, "EMAIL": False}

    sid, job = a_dead_job(world, client, login, monkeypatch)
    data = client.get(f"{API}/overview", headers=login(people["admin"].email)).get_json()["data"]
    assert data["configured"] is True and data["jobs"] == {"Dead": 1}
    assert {f["integration_code"]: f["live"] for f in data["features"]}["GOOGLE_MEET"] is True
    [problem] = data["problems"]
    assert problem["state"] == "Dead" and problem["what"] == "Calendar event and Meet link" and "refused" in problem["last_error"]
    assert problem["target"].endswith("Online")


def test_jobs_can_be_filtered_by_state(world, client, login, monkeypatch):  # noqa: F811
    people, batch, student = world
    a_dead_job(world, client, login, monkeypatch)
    headers = login(people["admin"].email)
    assert len(client.get(f"{API}/jobs", headers=headers).get_json()["data"]) == 1
    assert client.get(f"{API}/jobs?state=Dead", headers=headers).get_json()["data"][0]["state"] == "Dead"
    assert client.get(f"{API}/jobs?state=Queued", headers=headers).get_json()["data"] == []
    assert client.get(f"{API}/jobs?state=Nonsense", headers=headers).status_code == 400


def test_a_dead_job_can_be_retried_and_then_works(world, client, login, monkeypatch):  # noqa: F811
    people, batch, student = world
    sid, job = a_dead_job(world, client, login, monkeypatch)
    headers = login(people["admin"].email)
    response = client.post(f"{API}/jobs/{job.job_id}/retry", headers=headers)
    assert response.status_code == 200 and response.get_json()["data"]["state"] == "Queued"
    assert client.post(f"{API}/jobs/{job.job_id}/retry", headers=headers).status_code == 422  # it is queued now, not stuck
    assert run()["done"] == 1
    assert db.session.get(GoogleJob, job.job_id).state == "Succeeded"
    audit = db.session.execute(select(AuditLog).where(AuditLog.action == "GOOGLE_JOB_RETRIED")).scalars().all()
    assert len(audit) == 1 and audit[0].actor_user_id == people["admin"].user_id


def test_a_failed_job_waiting_out_its_backoff_can_be_run_now(world, client, login, monkeypatch):  # noqa: F811
    people, batch, student = world
    sid, job = a_dead_job(world, client, login, monkeypatch)
    job.state, job.attempts, job.next_attempt_at = "Failed", 1, datetime.now(timezone.utc) + timedelta(hours=5)
    db.session.commit()
    data = client.post(f"{API}/jobs/{job.job_id}/retry", headers=login(people["admin"].email)).get_json()["data"]
    assert data["state"] == "Failed"
    assert datetime.fromisoformat(data["next_attempt_at"]) <= datetime.now(timezone.utc) + timedelta(seconds=5)
    assert client.post(f"{API}/jobs/999999/retry", headers=login(people["admin"].email)).status_code == 404


def test_the_email_list_shows_why_a_message_did_not_go(client, make_student, make_user, login):
    make_student(activate=False)
    admin = make_user(roles=[("SUPER_ADMIN", None)])
    rows = client.get(f"{API}/emails?status=Skipped", headers=login(admin.email)).get_json()["data"]
    assert rows and rows[0]["status_note"] == "Email is switched off" and rows[0]["template"] == "student_activation_link"
    assert rows[0]["subject"] is None  # a sign-in link is never kept for a message that will not go
    assert client.get(f"{API}/emails?status=Sent", headers=login(admin.email)).get_json()["data"] == []


# ---------------------------------------------------------------- per-branch settings

def test_branch_settings_show_the_effective_addresses(client, admin):
    user, headers = admin
    rows = client.get(f"{API}/branches", headers=headers).get_json()["data"]
    guntur = next(r for r in rows if r["branch_id"] == 1)
    assert guntur["calendar_mailbox"] is None and guntur["effective_calendar_mailbox"] == guntur["branch_mailbox"]
    assert guntur["effective_gmail_sender"] == guntur["branch_mailbox"]


def test_a_branch_can_use_its_own_calendar_and_sender_and_go_back(client, admin):
    user, headers = admin
    response = client.patch(f"{API}/branches/1", json={"calendar_mailbox": "Classes@Example.test", "gmail_sender": "hello@example.test"}, headers=headers)
    data = response.get_json()["data"]
    assert response.status_code == 200 and data["effective_calendar_mailbox"] == "classes@example.test"
    assert data["effective_gmail_sender"] == "hello@example.test"
    assert google_repo.branch_mailbox(1) == "classes@example.test" and google_repo.gmail_sender(1) == "hello@example.test"
    audit = db.session.execute(select(AuditLog).where(AuditLog.action == "BRANCH_GOOGLE_CONFIG_CHANGED")).scalar_one()
    assert audit.new_values["calendar_mailbox"] == "classes@example.test" and audit.actor_user_id == user.user_id

    back = client.patch(f"{API}/branches/1", json={"calendar_mailbox": None, "gmail_sender": ""}, headers=headers).get_json()["data"]
    assert back["calendar_mailbox"] is None and back["effective_calendar_mailbox"] == back["branch_mailbox"]


def test_branch_settings_are_checked(client, admin):
    user, headers = admin
    assert client.patch(f"{API}/branches/1", json={"calendar_mailbox": "not-an-address"}, headers=headers).status_code == 400
    assert client.patch(f"{API}/branches/1", json={"drive_root_folder_id": "has spaces"}, headers=headers).status_code == 400
    assert client.patch(f"{API}/branches/1", json={}, headers=headers).status_code == 400
    assert client.patch(f"{API}/branches/9999", json={"gmail_sender": "a@example.test"}, headers=headers).status_code == 404


def test_the_drive_folder_cannot_move_once_folders_exist(client, admin):
    user, headers = admin
    assert client.patch(f"{API}/branches/1", json={"drive_root_folder_id": "1AbCdEfGhIjKlMnOp"}, headers=headers).status_code == 200
    google_repo.add_drive_item("branch", 1, 1, None, "1AbCdEfGhIjKlMnOp", "Nipuna LMS")
    db.session.commit()
    again = client.patch(f"{API}/branches/1", json={"drive_root_folder_id": "1ZzZzZzZzZzZzZzZz"}, headers=headers)
    assert again.status_code == 422 and "left behind" in again.get_json()["error"]["message"]
    same = client.patch(f"{API}/branches/1", json={"drive_root_folder_id": "1AbCdEfGhIjKlMnOp", "gmail_sender": "a@example.test"}, headers=headers)
    assert same.status_code == 200


def test_changing_branch_settings_needs_a_recent_password(client, admin, run_sql):
    user, headers = admin
    run_sql("UPDATE user_sessions SET reauthenticated_at = now() - interval '2 hours' WHERE user_id = :u", u=user.user_id)
    stale = client.patch(f"{API}/branches/1", json={"gmail_sender": "a@example.test"}, headers=headers)
    assert stale.status_code == 401 and stale.get_json()["error"]["code"] == "FRESH_AUTH_REQUIRED"
    assert client.get(f"{API}/branches", headers=headers).status_code == 200

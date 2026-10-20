"""Google Workspace slice 2 (docs/GOOGLE_WORKSPACE.md §5.3): the email outbox and the `email-send` job. Gmail is faked: no test
reaches Google."""
import base64
from datetime import datetime, timedelta, timezone
from email import message_from_bytes, policy

import pytest
from sqlalchemy import select

from config.database import db
from models import Branch, EmailOutbox
from services import email_messages, email_templates, emails, integrations
from services.google import client as google_client
from services.google import gmail
from services.google.client import GoogleError
from services.jobs import JOBS
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1"
BASE = "https://lms.example.test"


class FakeGmail:
    """Stands in for gmail.send: remembers each message, and can be told to fail."""

    def __init__(self):
        self.sent, self.fail = [], []

    def __call__(self, sender, to, subject, body):
        if self.fail:
            error = self.fail.pop(0)
            if error is not None:
                raise error
        self.sent.append({"sender": sender, "to": to, "subject": subject, "body": body})
        return f"gmail-{len(self.sent)}"


def rows(*statuses):
    db.session.expire_all()
    query = select(EmailOutbox).order_by(EmailOutbox.outbox_id)
    if statuses:
        query = query.where(EmailOutbox.status.in_(statuses))
    return list(db.session.execute(query).scalars())


def activation_row():
    return next(r for r in rows() if r.template == "student_activation_link")


@pytest.fixture
def email_on(app, monkeypatch, make_user):
    """Gmail configured, the EMAIL register entry verified and the LMS address set."""
    monkeypatch.setattr(google_client, "is_configured", lambda: True)
    app.config["PUBLIC_BASE_URL"] = BASE
    app.config["GOOGLE_DELEGATED_ADMIN"] = "admin@example.test"
    verifier = make_user(roles=[("SUPER_ADMIN", None)])
    integration = integrations.integrations_repo.get_by_code("EMAIL")
    integration.configuration_status, integration.verification_status = "Configured", "Verified"
    integration.verified_by, integration.verified_at, integration.evidence = verifier.user_id, datetime.now(timezone.utc), "Test mail"
    db.session.commit()


# ---------------------------------------------------------------- queueing and the switch

def test_while_email_is_off_the_message_is_kept_as_skipped_without_the_link(make_student):
    make_student(activate=False)
    row = activation_row()
    assert (row.status, row.status_note) == ("Skipped", "Email is switched off")
    assert row.body == "" and row.subject == ""  # a sign-in link is not kept for a message that will not go out
    assert emails.send_pending() == {"state": "Switched off", "sent": 0}


def test_an_activation_email_carries_the_link_and_goes_from_the_branch_mailbox(email_on, make_student):
    student = make_student(activate=False)
    row = activation_row()
    assert row.status == "Queued" and row.to_email == student.email and row.has_secret
    assert f"{BASE}/activate?token={student.token}" in row.body
    assert student.student_code in row.body

    fake = FakeGmail()
    assert emails.send_pending(sender=fake) == {"state": "On", "sent": 1, "retry": 0, "failed": 0}
    [sent] = fake.sent
    assert sent["to"] == student.email and sent["subject"] == "Activate your Nipuna learning account"
    assert sent["sender"] == db.session.get(Branch, row.branch_id).mailbox
    row = activation_row()
    assert row.status == "Sent" and row.provider_message_id == "gmail-1" and row.sent_at
    assert row.body == ""  # the link is forgotten once the message is done
    assert emails.send_pending(sender=fake)["sent"] == 0  # nothing is sent twice


def test_a_branch_can_send_from_its_own_address(email_on, make_student):
    make_student(activate=False)
    branch_id = activation_row().branch_id
    db.session.execute(db.text("INSERT INTO branch_google_config (branch_id, gmail_sender) VALUES (:b, 'hello@example.test')"), {"b": branch_id})
    fake = FakeGmail()
    emails.send_pending(sender=fake)
    assert fake.sent[0]["sender"] == "hello@example.test"


def test_without_the_lms_address_there_is_no_link_to_send(email_on, app, make_student):
    app.config["PUBLIC_BASE_URL"] = None
    make_student(activate=False)
    row = activation_row()
    assert row.status == "Skipped" and "link" in row.status_note


def test_the_same_event_is_queued_once(email_on, make_student, app):
    make_student(activate=False)
    row = activation_row()
    again = emails.enqueue(email_templates.STUDENT_ACTIVATION_LINK, {}, dedupe_key=row.dedupe_key)
    assert again is None
    assert len([r for r in rows() if r.template == "student_activation_link"]) == 1


def test_a_message_past_its_expiry_is_skipped_not_sent(email_on, make_student):
    make_student(activate=False)
    row = activation_row()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    fake = FakeGmail()
    emails.send_pending(sender=fake)
    assert fake.sent == [] and (activation_row().status, activation_row().status_note) == ("Skipped", "Too old to send")


def test_a_reminder_waits_for_the_student_to_choose_email(email_on, world):  # noqa: F811
    from models import Student
    student = db.session.get(Student, world.students.s1.student_id)
    values = {"student": "S", "branch": "B", "class_title": "C", "course": "J", "start": "now", "mode": "M"}
    message = emails.enqueue(email_templates.CLASS_REMINDER, values, dedupe_key="pref-1", student=student)
    assert (message.status, message.status_note) == ("Skipped", "The person switched email off for this kind of message")
    assert emails.enqueue(email_templates.CLASS_REMINDER, {**values, "mode": ""}, dedupe_key="pref-2", student=student).status_note == "No mode"


# ---------------------------------------------------------------- sending, retries

def test_a_timeout_is_retried_with_backoff_then_sent(email_on, make_student):
    make_student(activate=False)
    fake = FakeGmail()
    fake.fail = [GoogleError("Could not reach Google", retryable=True)]
    assert emails.send_pending(sender=fake) == {"state": "On", "sent": 0, "retry": 1, "failed": 0}
    row = activation_row()
    assert row.status == "Queued" and row.attempts == 1 and row.body  # the link is kept for the retry
    assert row.next_attempt_at > datetime.now(timezone.utc) + timedelta(minutes=4)
    assert emails.send_pending(sender=fake)["sent"] == 0  # still waiting

    row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert emails.send_pending(sender=fake)["sent"] == 1


def test_a_refusal_fails_at_once_and_forgets_the_link(email_on, make_student):
    make_student(activate=False)
    fake = FakeGmail()
    fake.fail = [GoogleError("Google returned 403: Delegation denied", status=403)]
    assert emails.send_pending(sender=fake)["failed"] == 1
    row = activation_row()
    assert row.status == "Failed" and "403" in row.status_note and row.body == ""


def test_after_the_last_try_the_message_fails(email_on, make_student):
    make_student(activate=False)
    fake = FakeGmail()
    for _ in range(emails.MAX_ATTEMPTS):
        fake.fail = [GoogleError("Google returned 503", status=503, retryable=True)]
        result = emails.send_pending(sender=fake)
        row = activation_row()
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
    assert result["failed"] == 1 and activation_row().status == "Failed" and activation_row().attempts == emails.MAX_ATTEMPTS


def test_a_send_that_never_finished_is_tried_again(email_on, make_student):
    make_student(activate=False)
    row = activation_row()
    row.attempt_started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.session.commit()
    fake = FakeGmail()
    assert emails.send_pending(sender=fake)["sent"] == 1


# ---------------------------------------------------------------- class reminders

def test_class_reminders_by_email_follow_the_confirmed_class_and_the_students_choice(email_on, world, make_session, run_sql):  # noqa: F811
    now = datetime.now(timezone.utc)
    t1, bm = world.people.t1, world.people.bm.user_id
    soon = make_session(world.batches.b1, t1, now + timedelta(minutes=30), hours=0.5, title="Reminder class", confirmed_at=now, confirmed_by=bm)
    make_session(world.batches.b1, t1, now + timedelta(minutes=65), hours=0.5, title="Not confirmed")
    reminders = lambda: [r for r in rows() if r.template == "class_reminder"]  # noqa: E731

    assert email_messages.class_reminders() == {"emails": 1}
    (message,) = reminders()
    assert message.status == "Skipped" and "switched email off" in message.status_note  # reminders are opt-in

    run_sql("DELETE FROM email_outbox WHERE template = 'class_reminder'")
    from flask import current_app
    with current_app.test_client() as client:
        assert client.put(f"{API}/notifications/preferences", headers=world.h(world.students.s1),
                          json={"preferences": [{"group": "Learning reminders", "channel": "Email", "enabled": True}]}).status_code == 200
    assert email_messages.class_reminders() == {"emails": 1}
    queued = [r for r in reminders() if r.status == "Queued"]
    assert len(queued) == 1 and queued[0].subject == "Reminder: Reminder class starts at " + queued[0].subject.rsplit("starts at ", 1)[1]
    assert queued[0].expires_at == soon.starts_at and queued[0].to_email == world.students.s1.email
    assert email_messages.class_reminders() == {"emails": 0}  # the same class and time is never reminded twice


# ---------------------------------------------------------------- Gmail and the job

def test_gmail_gets_a_well_formed_message_as_the_sending_mailbox(app, monkeypatch):
    calls = []
    monkeypatch.setattr(google_client, "request", lambda method, url, **kw: calls.append((method, url, kw)) or {"id": "m1"})
    assert gmail.send("trainer@example.test", "student@example.test", "Hello — नमस्ते", "Line one\nLine two") == "m1"
    [(method, url, kw)] = calls
    assert (method, url) == ("POST", gmail.SEND_URL)
    assert kw["subject"] == "trainer@example.test" and kw["scopes"] == [google_client.GMAIL_SEND_SCOPE]
    parsed = message_from_bytes(base64.urlsafe_b64decode(kw["body"]["raw"]), policy=policy.default)
    assert (parsed["From"], parsed["To"], parsed["Subject"]) == ("trainer@example.test", "student@example.test", "Hello — नमस्ते")
    assert parsed.get_content().strip() == "Line one\nLine two"


def test_the_job_is_registered_and_does_nothing_while_off(app):
    assert "email-send" in JOBS and JOBS["email-send"]() == {"state": "Switched off", "sent": 0}
    assert "emails" in JOBS["class-reminders"]()

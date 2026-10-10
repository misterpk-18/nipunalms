"""WhatsApp through the CRM (UX phase U6): the outbox, the rules (switch, approved templates, preferences, age, dedupe) and
the job that hands messages to the CRM. The CRM is faked: no test calls a real endpoint."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from config.database import db
from models import Student, WhatsappMessage
from services import whatsapp, whatsapp_messages, whatsapp_templates
from services.whatsapp import NoAnswer
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1"
ALL_TEMPLATES = sorted(whatsapp_templates.TEMPLATES)


@pytest.fixture
def switched_on(run_sql, app):
    """WhatsApp on, every template approved, the CRM endpoint set."""
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    run_sql("UPDATE app_settings SET setting_value = CAST(:v AS jsonb) WHERE setting_key = 'whatsapp_approved_templates'", v=json.dumps(ALL_TEMPLATES))
    app.config["CRM_BASE_URL"] = "http://crm.test/api/v1"


def messages(*statuses):
    rows = db.session.query(WhatsappMessage).order_by(WhatsappMessage.outbox_id).all()
    return [m for m in rows if not statuses or m.status in statuses]


def cancel(client, world, session, reason="the trainer is unwell"):
    response = client.post(f"{API}/class-sessions/{session.session_id}/cancel", json={"reason": reason}, headers=world.h(world.people.bm))
    assert response.status_code == 200, response.get_json()


class FakeCrm:
    """A poster that answers from a list and records the calls."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, payload, key, timeout):
        self.calls.append((url, payload, key))
        answer = self.answers.pop(0) if self.answers else (200, {"data": {"status": "Sent", "provider_message_id": f"wamid.{len(self.calls)}"}})
        if isinstance(answer, Exception):
            raise answer
        return answer


# ---------------------------------------------------------------- queueing

def test_it_ships_switched_off_and_keeps_a_reason_instead_of_sending(client, world):
    cancel(client, world, world.sessions.upcoming)
    rows = messages()
    assert len(rows) == 1 and rows[0].status == "Skipped" and rows[0].status_note == "WhatsApp is switched off"
    assert whatsapp.status()["state"] == "Switched off" and not whatsapp.is_live()


def test_an_unapproved_template_is_skipped(client, world, run_sql, app):
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    cancel(client, world, world.sessions.upcoming)
    assert messages()[0].status_note == "This template is not approved yet"
    assert whatsapp.status()["state"] == "CRM endpoint not available"


def test_cancelling_a_class_queues_one_message_per_student_with_the_template_values(client, world, switched_on):
    cancel(client, world, world.sessions.upcoming, reason="  the trainer\nis unwell ")
    (message,) = messages("Queued")
    assert message.template_name == "nipuna_lms_class_cancelled_u_v1" and message.to_number == "919876500417"
    assert message.lms_user_id and message.recipient_user_id
    student, branch, title, course, planned, reason, next_step = message.params
    assert (student, branch, title) == ("Student One", "Guntur", "Streams and lambdas") and reason == "the trainer is unwell"
    assert "replacement" in next_step and planned.endswith("IST")
    text = whatsapp_templates.render(whatsapp_templates.TEMPLATES[message.template_name], message.params)
    assert "{{" not in text and "\n" not in text
    # the same event is never queued twice
    assert whatsapp.enqueue(whatsapp_templates.CLASS_CANCELLED, dict(zip(whatsapp_templates.CLASS_CANCELLED.params, message.params)),
                            dedupe_key=message.dedupe_key, student=db.session.get(Student, world.students.s1.student_id)) is None


def test_rescheduling_sends_only_for_a_change_of_time(client, world, switched_on):
    s = world.sessions.upcoming
    start = s.starts_at + timedelta(days=1)
    response = client.post(f"{API}/class-sessions/{s.session_id}/reschedule", headers=world.h(world.people.bm),
                           json={"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=2)).isoformat(), "reason": "Trainer clash"})
    assert response.status_code == 200, response.get_json()
    (message,) = messages("Queued")
    assert message.template_name == "nipuna_lms_class_rescheduled_u_v1" and message.dedupe_key.startswith(f"class-rescheduled:{s.session_id}:")
    assert message.params[4] != message.params[5]  # old time, new time


def test_a_student_without_a_number_or_who_switched_it_off_gets_a_skipped_row(client, world, switched_on, run_sql, make_session):
    run_sql("UPDATE students SET mobile = NULL WHERE student_id = :s", s=world.students.s1.student_id)
    cancel(client, world, world.sessions.upcoming)
    assert [m.status_note for m in messages()] == ["No WhatsApp number on file"]

    run_sql("UPDATE students SET mobile = '9876500417' WHERE student_id = :s", s=world.students.s1.student_id)
    assert client.put(f"{API}/notifications/preferences", headers=world.h(world.students.s1),
                      json={"preferences": [{"group": "Service", "channel": "WhatsApp", "enabled": False}]}).status_code == 200
    cancel_again = make_session(world.batches.b1, world.people.t1, datetime.now(timezone.utc) + timedelta(days=4), title="Second class")
    cancel(client, world, cancel_again)
    assert messages()[-1].status_note == "The person switched WhatsApp off for this kind of message"


def test_missing_values_are_never_sent_to_pinbot():
    with pytest.raises(ValueError, match="no value for reason"):
        whatsapp_templates.build(whatsapp_templates.CLASS_CANCELLED, {"student": "A", "branch": "B", "class": "C", "course": "D",
                                                                      "planned_start": "E", "reason": "  ", "next_step": "G"})
    body, button = whatsapp_templates.build(whatsapp_templates.CERTIFICATE_ISSUED, {"student": "A", "branch": "B", "certificate_type": "C",
                                                                                   "course": "D", "number": "NIT-CERT-2026-000123"})
    assert button == ["NIT-CERT-2026-000123"] and len(body) == 5


def test_every_template_body_uses_exactly_its_parameters():
    import re

    for template in whatsapp_templates.TEMPLATES.values():
        slots = sorted(int(n) for n in re.findall(r"\{\{(\d+)\}\}", template.body))
        assert slots == list(range(1, len(template.params) + 1)), template.name
        assert not template.body.startswith("{{") and not template.body.rstrip(". ").endswith("}}"), template.name  # Meta's rule
        assert len(template.body) < 1024


# ---------------------------------------------------------------- class reminders

def test_class_reminders_follow_the_confirmed_class_and_its_time(world, make_session, switched_on, run_sql):
    now = datetime.now(timezone.utc)
    t1, bm = world.people.t1, world.people.bm.user_id
    make_session(world.batches.b1, t1, now + timedelta(minutes=5), hours=0.25, title="Starts too soon", confirmed_at=now, confirmed_by=bm)
    soon = make_session(world.batches.b1, t1, now + timedelta(minutes=30), hours=0.5, title="Reminder class", confirmed_at=now, confirmed_by=bm)
    make_session(world.batches.b1, t1, now + timedelta(minutes=65), hours=0.5, title="Not confirmed")
    make_session(world.batches.b1, t1, now + timedelta(hours=5), hours=1, title="Too far away", confirmed_at=now, confirmed_by=bm)
    # reminders are a kind of message people choose: off until they turn them on
    assert whatsapp_messages.class_reminders() == {"reminders": 1}
    (message,) = messages()
    assert message.status == "Skipped" and "switched WhatsApp off" in message.status_note

    run_sql("DELETE FROM whatsapp_outbox")
    client_headers = world.h(world.students.s1)
    assert world.h  # logged in
    from flask import current_app

    with current_app.test_client() as client:
        assert client.put(f"{API}/notifications/preferences", headers=client_headers,
                          json={"preferences": [{"group": "Learning reminders", "channel": "WhatsApp", "enabled": True}]}).status_code == 200
    assert whatsapp_messages.class_reminders() == {"reminders": 1}
    (message,) = messages("Queued")
    assert message.params[2] == "Reminder class" and message.expires_at == soon.starts_at
    assert whatsapp_messages.class_reminders() == {"reminders": 0}  # the same class and time is never reminded twice


# ---------------------------------------------------------------- the job

def queued_message(world, client, switched_on):
    cancel(client, world, world.sessions.upcoming)
    return messages("Queued")[0]


def test_a_queued_message_is_posted_to_the_crm_and_marked_sent(client, world, switched_on, app):
    message = queued_message(world, client, switched_on)
    crm = FakeCrm()
    result = whatsapp.send_pending(poster=crm)
    assert result == {"state": "On", "sent": 1, "failed": 0}
    url, payload, key = crm.calls[0]
    assert url == "http://crm.test/api/v1/lms/whatsapp" and key == app.config["CRM_SERVICE_KEY"]
    assert payload["template"] == message.template_name and payload["to"] == "919876500417" and payload["dedupe_key"] == message.dedupe_key
    assert payload["params"] == message.params and payload["lms_user_id"] and payload["occurred_at"]
    db.session.refresh(message)
    assert message.status == "Sent" and message.provider_message_id == "wamid.1" and message.sent_at and message.attempt_started_at is None
    assert whatsapp.send_pending(poster=crm)["sent"] == 0 and len(crm.calls) == 1  # nothing is sent twice


def test_the_job_does_nothing_while_the_endpoint_is_not_available(client, world, switched_on, app):
    queued_message(world, client, switched_on)
    app.config["CRM_BASE_URL"] = None
    crm = FakeCrm()
    assert whatsapp.send_pending(poster=crm) == {"state": "CRM endpoint not available", "sent": 0} and crm.calls == []
    assert messages()[0].status == "Queued"


def test_a_timeout_is_never_resent(client, world, switched_on):
    message = queued_message(world, client, switched_on)
    crm = FakeCrm(NoAnswer("timed out"))
    assert whatsapp.send_pending(poster=crm)["failed"] == 1
    db.session.refresh(message)
    assert message.status == "Failed" and "check before resending" in message.status_note
    assert whatsapp.send_pending(poster=crm)["sent"] == 0 and len(crm.calls) == 1


def test_a_busy_crm_is_retried_with_backoff_and_then_given_up_on(client, world, switched_on):
    message = queued_message(world, client, switched_on)
    crm = FakeCrm((503, None))
    whatsapp.send_pending(poster=crm)
    db.session.refresh(message)
    assert message.status == "Queued" and message.attempts == 1 and message.next_attempt_at > datetime.now(timezone.utc)
    assert whatsapp.send_pending(poster=crm)["sent"] == 0 and len(crm.calls) == 1  # still waiting out the backoff

    message.attempts = whatsapp.MAX_ATTEMPTS - 1
    message.next_attempt_at = None
    db.session.commit()
    whatsapp.send_pending(poster=FakeCrm((429, None)))
    db.session.refresh(message)
    assert message.status == "Failed" and "gave up" in message.status_note


def test_a_refused_key_stops_the_run_and_leaves_the_message_queued(client, world, switched_on):
    message = queued_message(world, client, switched_on)
    result = whatsapp.send_pending(poster=FakeCrm((401, None)))
    assert result["state"] == "The CRM refused the service key"
    db.session.refresh(message)
    assert message.status == "Queued" and message.attempts == 0 and message.attempt_started_at is None


def test_the_crms_own_answers_are_recorded(client, world, switched_on):
    message = queued_message(world, client, switched_on)
    whatsapp.send_pending(poster=FakeCrm((200, {"data": {"status": "Skipped", "reason": "Not a test number"}})))
    db.session.refresh(message)
    assert message.status == "Skipped" and message.status_note == "The CRM skipped it: Not a test number"

    for code, body, status in [(200, {"data": {}}, "Failed"), (422, {"error": {"message": "Template does not exist"}}, "Failed"),
                               (409, None, "Sent"), (200, {"data": {"provider_message_id": "wamid.9"}}, "Sent")]:
        row = WhatsappMessage(template_name=message.template_name, dedupe_key=f"x{code}{status}{id(body)}", params=message.params, to_number="919876500417",
                              occurred_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.session.add(row)
        db.session.commit()
        whatsapp.send_pending(poster=FakeCrm((code, body)))
        db.session.refresh(row)
        assert row.status == status, (code, row.status_note)


def test_stale_messages_and_stuck_posts_are_not_sent(client, world, switched_on, run_sql):
    stale = queued_message(world, client, switched_on)
    run_sql("UPDATE whatsapp_outbox SET expires_at = now() - interval '1 minute' WHERE outbox_id = :i", i=stale.outbox_id)
    crm = FakeCrm()
    whatsapp.send_pending(poster=crm)
    db.session.refresh(stale)
    assert stale.status == "Skipped" and stale.status_note == "Too old to send" and crm.calls == []

    stuck = WhatsappMessage(template_name=stale.template_name, dedupe_key="stuck", params=stale.params, to_number="919876500417",
                            occurred_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                            attempts=1, attempt_started_at=datetime.now(timezone.utc) - timedelta(hours=1))
    db.session.add(stuck)
    db.session.commit()
    whatsapp.send_pending(poster=crm)
    db.session.refresh(stuck)
    assert stuck.status == "Failed" and "check before resending" in stuck.status_note and crm.calls == []


# ---------------------------------------------------------------- the channel people see

def test_whatsapp_is_offered_in_preferences_only_when_it_is_live(client, world, switched_on, run_sql, app):
    def channel():
        data = client.get(f"{API}/notifications/preferences", headers=world.h(world.students.s1)).get_json()["data"]
        return next(c for c in data["channels"] if c["channel"] == "WhatsApp")

    assert channel()["live"] is True
    run_sql("UPDATE app_settings SET setting_value = 'false' WHERE setting_key = 'whatsapp_enabled'")
    assert channel()["live"] is False
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    app.config["CRM_BASE_URL"] = None
    assert channel()["live"] is False


def test_the_job_is_registered():
    from services.jobs import JOBS

    assert {"whatsapp-send", "class-reminders"} <= set(JOBS)

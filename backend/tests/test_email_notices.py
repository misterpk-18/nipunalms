"""Emails beside the WhatsApp class and study notices (docs/GOOGLE_WORKSPACE.md §5.3): cancelled and rescheduled classes, a published
result, an issued certificate and a batch change that needs the student's agreement. Gmail is faked."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from config.database import db
from models import Branch, Student
from services import email_messages, email_templates
from tests.test_email_outbox import API, BASE, email_on, rows  # noqa: F401
from tests.services_fixtures import world  # noqa: F401


def notice(template: str):
    return [r for r in rows() if r.template == template]


def cancel(client, world, session, reason="the trainer\nis unwell"):  # noqa: F811
    response = client.post(f"{API}/class-sessions/{session.session_id}/cancel", json={"reason": reason}, headers=world.h(world.people.bm))
    assert response.status_code == 200, response.get_json()


def test_cancelling_a_class_emails_each_student_once(email_on, client, world):  # noqa: F811
    cancel(client, world, world.sessions.upcoming)
    (message,) = notice("class_cancelled")
    assert message.status == "Queued" and message.to_email == world.students.s1.email
    assert message.subject == "Class cancelled: Streams and lambdas"
    assert "Reason: the trainer is unwell" in message.body and "replacement" in message.body and "Hello Student One," in message.body
    assert "{" not in message.body and not message.has_secret
    again = email_messages.emails.enqueue(email_templates.CLASS_CANCELLED, {}, dedupe_key=message.dedupe_key)
    assert again is None and len(notice("class_cancelled")) == 1


def test_a_move_in_time_is_emailed_and_shows_both_times(email_on, client, world):  # noqa: F811
    s = world.sessions.upcoming
    start = s.starts_at + timedelta(days=1)
    response = client.post(f"{API}/class-sessions/{s.session_id}/reschedule", headers=world.h(world.people.bm),
                           json={"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=2)).isoformat(), "reason": "Trainer clash"})
    assert response.status_code == 200, response.get_json()
    (message,) = notice("class_rescheduled")
    assert message.subject == "Class moved: Streams and lambdas" and message.status == "Queued"
    assert "Old time:" in message.body and "New time:" in message.body and message.body.count("IST") == 2


def test_a_student_can_switch_these_emails_off(email_on, client, world):  # noqa: F811
    assert client.put(f"{API}/notifications/preferences", headers=world.h(world.students.s1),
                      json={"preferences": [{"group": "Service", "channel": "Email", "enabled": False}]}).status_code == 200
    cancel(client, world, world.sessions.upcoming)
    (message,) = notice("class_cancelled")
    assert (message.status, message.status_note) == ("Skipped", "The person switched email off for this kind of message")


def test_nothing_is_kept_to_send_while_email_is_off(client, world):  # noqa: F811
    cancel(client, world, world.sessions.upcoming)
    (message,) = notice("class_cancelled")
    assert (message.status, message.status_note) == ("Skipped", "Email is switched off")


# ---------------------------------------------------------------- result, certificate, batch change

def student_and_batch(world):  # noqa: F811
    return db.session.get(Student, world.students.s1.student_id), world.batches.b1


def test_a_published_result_is_emailed(email_on, world):  # noqa: F811
    student, batch = student_and_batch(world)
    result = SimpleNamespace(result_id=7, student_id=student.student_id, batch=batch, published_at=datetime.now(timezone.utc))
    email_messages.result_published(result, "Week 3 test")
    (message,) = notice("result_published")
    assert message.subject == "Your result is published: Week 3 test" and "My Progress" in message.body and message.status == "Queued"


def test_a_certificate_email_carries_the_number_and_a_verify_link(email_on, world, app):  # noqa: F811
    student, batch = student_and_batch(world)
    certificate = SimpleNamespace(certificate_id=3, version=1, student=student, branch_id=batch.branch_id, branch=db.session.get(Branch, batch.branch_id), course=batch.course,
                                  certificate_type="Course Completion Certificate", certificate_number="NIT-CERT-2026-000123")
    email_messages.certificate_issued(certificate)
    (message,) = notice("certificate_issued")
    assert message.subject == "Your certificate is ready: NIT-CERT-2026-000123"
    assert f"{BASE}/verify/NIT-CERT-2026-000123" in message.body and "?" not in message.body.split("here:")[1]

    app.config["PUBLIC_BASE_URL"] = None  # no address to link to: the email still goes, without the link
    email_messages.certificate_issued(SimpleNamespace(**{**vars(certificate), "version": 2}))
    plain = notice("certificate_issued")[-1]
    assert plain.status == "Queued" and "genuine" not in plain.body and plain.body.rstrip().endswith("Nipuna Technologies")


def test_a_batch_change_that_needs_agreement_is_emailed(email_on, world):  # noqa: F811
    student, batch = student_and_batch(world)
    change = SimpleNamespace(change_id=5, batch=batch, current_plan="Tue and Thu, 3 pm", proposed_plan="Mon and Wed, 5 pm", reason="Room clash",
                             reply_by=datetime.now(timezone.utc) + timedelta(days=3))
    email_messages.batch_change_agreement(change, student)
    (message,) = notice("batch_change_agreement")
    assert "Now: Tue and Thu, 3 pm" in message.body and "Proposed: Mon and Wed, 5 pm" in message.body and "Agree or Decline" in message.body


def test_every_template_fills_every_value():
    for template in email_templates.TEMPLATES.values():
        values = {field: f"<{field}>" for field in template.fields}
        subject, body = template.render(values)
        assert "{" not in subject + body and "\n" not in subject, template.name
        assert all(f"<{field}>" in subject + body for field in template.fields), template.name

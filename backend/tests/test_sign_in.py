"""UX phase U7: self-service password reset, staff invites, activation that signs in, unlock, and the sign-in WhatsApp messages."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, PasswordResetCode, StaffInvite, User, WhatsappMessage
from services import password_reset, whatsapp_templates
from tests.conftest import PASSWORD

API = "/api/v1/auth"
NEW_PASSWORD = "A-brand-new-passw0rd"
PHONE = "+919876543210"
NEW_STAFF = {"full_name": "Ravi Kumar", "email": "ravi@nipuna.test", "phone": PHONE, "scopes": [{"role_code": "BRANCH_MANAGER", "branch_id": 1}]}


@pytest.fixture
def switched_on(run_sql, app):
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    run_sql("UPDATE app_settings SET setting_value = CAST(:v AS jsonb) WHERE setting_key = 'whatsapp_approved_templates'",
            v=json.dumps(sorted(whatsapp_templates.TEMPLATES)))
    app.config["CRM_BASE_URL"] = "http://crm.test/api/v1"


@pytest.fixture
def fixed_code(monkeypatch):
    monkeypatch.setattr(password_reset, "new_code", lambda: "482913")
    return "482913"


def ask(client, login):
    return client.post(f"{API}/reset-code", json={"login": login})


def reset(client, login, code, password=NEW_PASSWORD):
    return client.post(f"{API}/reset", json={"login": login, "code": code, "new_password": password})


def outbox(template):
    return db.session.execute(select(WhatsappMessage).where(WhatsappMessage.template_name == template.name)
                              .order_by(WhatsappMessage.outbox_id)).scalars().all()


def audit_actions():
    return db.session.execute(select(AuditLog.action)).scalars().all()


# ---------------------------------------------------------------- the reset code

def test_asking_for_a_code_gives_the_same_answer_whether_or_not_the_account_exists(client, make_user, switched_on, fixed_code):
    user = make_user(phone=PHONE)

    known, unknown = ask(client, user.email), ask(client, "nobody@nipuna.test")

    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json() and "If the account exists" in known.get_json()["data"]["message"]
    assert len(outbox(whatsapp_templates.PASSWORD_RESET_CODE)) == 1  # only the real person got a message


def test_a_code_goes_by_whatsapp_to_the_number_on_file_and_works_once(client, make_user, switched_on, fixed_code):
    user = make_user(phone=PHONE)
    ask(client, user.email.upper())

    (message,) = outbox(whatsapp_templates.PASSWORD_RESET_CODE)
    assert message.status == "Queued" and message.to_number == "919876543210"
    assert message.params == [fixed_code] and message.button_params == [fixed_code]
    assert message.expires_at - message.occurred_at == timedelta(minutes=10)
    row = db.session.execute(select(PasswordResetCode)).scalar_one()
    assert row.code_hash != fixed_code and fixed_code not in row.code_hash  # only a hash is stored

    assert reset(client, user.email, fixed_code).status_code == 204
    assert client.post(f"{API}/login", json={"login": user.email, "password": NEW_PASSWORD}).status_code == 200
    assert client.post(f"{API}/login", json={"login": user.email, "password": PASSWORD}).status_code == 401
    again = reset(client, user.email, fixed_code, "Yet-another-passw0rd")
    assert again.status_code == 400 and "wrong or has expired" in again.get_json()["error"]["message"]
    assert "PASSWORD_RESET_WITH_CODE" in audit_actions()


def test_a_student_asks_with_their_student_id_and_the_code_ends_their_sessions(client, make_student, switched_on, fixed_code, run_sql, login):
    student = make_student()
    run_sql("UPDATE students SET mobile = :m WHERE student_id = :s", m=PHONE, s=student.student_id)
    headers = login(student.student_code)

    ask(client, student.student_code.lower())
    assert reset(client, student.student_code, fixed_code).status_code == 204

    assert client.get(f"{API}/me", headers=headers).status_code == 401
    assert client.post(f"{API}/login", json={"login": student.student_code, "password": NEW_PASSWORD}).status_code == 200


def test_a_wrong_code_five_times_burns_the_code(client, make_user, switched_on, fixed_code):
    user = make_user(phone=PHONE)
    ask(client, user.email)

    for _ in range(5):
        assert reset(client, user.email, "000000").status_code == 400
    assert reset(client, user.email, fixed_code).status_code == 400  # the right code no longer works
    assert db.session.execute(select(PasswordResetCode.used_at)).scalar_one() is not None


def test_an_expired_code_is_refused(client, make_user, switched_on, fixed_code, run_sql):
    user = make_user(phone=PHONE)
    ask(client, user.email)
    run_sql("UPDATE password_reset_codes SET expires_at = now() - interval '1 minute'")

    assert reset(client, user.email, fixed_code).status_code == 400


def test_a_new_code_replaces_the_earlier_one(client, make_user, switched_on, monkeypatch):
    user = make_user(phone=PHONE)
    monkeypatch.setattr(password_reset, "new_code", lambda: "111111")
    ask(client, user.email)
    monkeypatch.setattr(password_reset, "new_code", lambda: "222222")
    ask(client, user.email)

    assert reset(client, user.email, "111111").status_code == 400
    assert reset(client, user.email, "222222").status_code == 204


def test_at_most_five_codes_an_hour(client, make_user, switched_on):
    user = make_user(phone=PHONE)
    for _ in range(7):
        assert ask(client, user.email).status_code == 200

    assert db.session.query(PasswordResetCode).count() == 5
    assert len(outbox(whatsapp_templates.PASSWORD_RESET_CODE)) == 5


def test_a_weak_new_password_is_refused_and_the_code_stays_usable(client, make_user, switched_on, fixed_code):
    user = make_user(phone=PHONE)
    ask(client, user.email)

    assert reset(client, user.email, fixed_code, "short").status_code == 400
    assert reset(client, user.email, fixed_code).status_code == 204


def test_resetting_clears_a_lockout(client, make_user, switched_on, fixed_code):
    user = make_user(phone=PHONE, locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
    ask(client, user.email)

    assert reset(client, user.email, fixed_code).status_code == 204
    assert client.post(f"{API}/login", json={"login": user.email, "password": NEW_PASSWORD}).status_code == 200


def test_no_code_is_sent_to_a_deactivated_account_or_an_unactivated_student(client, make_user, make_student, switched_on):
    gone = make_user(phone=PHONE, is_active=False)
    waiting = make_student(activate=False)

    ask(client, gone.email)
    ask(client, waiting.student_code)

    assert outbox(whatsapp_templates.PASSWORD_RESET_CODE) == []


def test_the_code_is_not_kept_once_the_message_is_done(client, make_user, switched_on, fixed_code):
    from services import whatsapp
    from tests.test_whatsapp import FakeCrm
    user = make_user(phone=PHONE)
    ask(client, user.email)
    db.session.commit()

    whatsapp.send_pending(poster=FakeCrm())

    (message,) = outbox(whatsapp_templates.PASSWORD_RESET_CODE)
    assert message.status == "Sent" and message.params == [] and message.button_params == []


def test_when_whatsapp_is_off_nothing_is_kept_that_holds_the_code(client, make_user, fixed_code):
    user = make_user(phone=PHONE)
    ask(client, user.email)

    (message,) = outbox(whatsapp_templates.PASSWORD_RESET_CODE)
    assert message.status == "Skipped" and message.params == []


# ---------------------------------------------------------------- activation signs the person in

def test_a_student_activating_is_signed_in_and_sees_their_student_id(client, make_student):
    student = make_student(activate=False)

    response = client.post(f"{API}/activate", json={"token": student.token, "password": NEW_PASSWORD})

    data = response.get_json()["data"]
    assert response.status_code == 200 and data["student_code"] == student.student_code and data["home_route"] == "/dashboard"
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert me.status_code == 200 and me.get_json()["data"]["student"]["activation_status"] == "Activated"


def test_the_activation_page_says_who_the_link_is_for_and_how_long_a_password_must_be(client, make_student):
    student = make_student(activate=False)

    data = client.get(f"{API}/activation/{student.token}").get_json()["data"]

    assert data["kind"] == "student" and data["status"] == "valid" and data["password_min_length"] == 10 and data["email"] is None


# ---------------------------------------------------------------- staff invites

def create_staff(client, login, admin, body=None):
    response = client.post("/api/v1/admin/users", json=body or NEW_STAFF, headers=login(admin.email))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_a_new_staff_member_gets_an_invite_link_and_sets_their_own_password(client, make_user, login, switched_on):
    admin = make_user()
    data = create_staff(client, login, admin)

    assert data["invite_path"].startswith("/activate?token=") and data["whatsapp"]["state"] == "Queued"
    assert "temporary_password" not in data  # the link goes by WhatsApp, so no password is spoken
    token = data["invite_path"].split("=", 1)[1]
    (message,) = outbox(whatsapp_templates.STAFF_ACCOUNT_INVITE)
    assert message.params[:3] == ["Ravi Kumar", "Branch Manager", "Guntur"] and message.button_params == [token]

    info = client.get(f"{API}/activation/{token}").get_json()["data"]
    assert info["kind"] == "staff" and info["full_name"] == "Ravi Kumar" and info["email"] == "r••••@nipuna.test" and info["student_code"] is None

    done = client.post(f"{API}/activate", json={"token": token, "password": NEW_PASSWORD})
    assert done.status_code == 200 and done.get_json()["data"]["student_code"] is None
    body = done.get_json()["data"]
    assert body["home_route"] == "/branch" and body["user"]["must_change_password"] is False
    assert client.post(f"{API}/login", json={"login": "ravi@nipuna.test", "password": NEW_PASSWORD}).status_code == 200
    assert client.post(f"{API}/activate", json={"token": token, "password": "Other-passw0rd!"}).status_code == 422  # used
    assert "STAFF_INVITE_ACCEPTED" in audit_actions()


def test_without_whatsapp_the_temporary_password_is_the_fallback_and_the_link_still_works(client, make_user, login):
    admin = make_user()
    data = create_staff(client, login, admin, {**NEW_STAFF, "phone": None})

    assert data["whatsapp"]["state"] == "Skipped" and len(data["temporary_password"]) >= 10
    assert client.post(f"{API}/login", json={"login": "ravi@nipuna.test", "password": data["temporary_password"]}).status_code == 200


def test_resending_an_invite_cancels_the_earlier_link(client, make_user, login, switched_on):
    admin = make_user()
    first = create_staff(client, login, admin)
    user_id = first["user_id"]

    second = client.post(f"/api/v1/admin/users/{user_id}/invite", headers=login(admin.email))

    assert second.status_code == 201
    old, new = first["invite_path"].split("=", 1)[1], second.get_json()["data"]["invite_path"].split("=", 1)[1]
    assert client.get(f"{API}/activation/{old}").get_json()["data"]["status"] == "revoked"
    assert client.get(f"{API}/activation/{new}").get_json()["data"]["status"] == "valid"
    assert db.session.query(StaffInvite).filter(StaffInvite.used_at.is_(None), StaffInvite.revoked_at.is_(None)).count() == 1
    assert "STAFF_INVITE_SENT" in audit_actions()


def test_no_invite_for_someone_who_already_chose_a_password_and_only_a_super_admin_sends_one(client, make_user, login):
    admin, manager = make_user(), make_user(roles=[("BRANCH_MANAGER", 1)])

    assert client.post(f"/api/v1/admin/users/{manager.user_id}/invite", headers=login(admin.email)).status_code == 422
    assert client.post(f"/api/v1/admin/users/{manager.user_id}/invite", headers=login(manager.email)).status_code == 403


def test_an_expired_invite_is_refused(client, make_user, login, run_sql):
    admin = make_user()
    token = create_staff(client, login, admin)["invite_path"].split("=", 1)[1]
    run_sql("UPDATE staff_invites SET expires_at = now() - interval '1 minute'")

    response = client.post(f"{API}/activate", json={"token": token, "password": NEW_PASSWORD})

    assert response.status_code == 422 and response.get_json()["error"]["details"] == {"status": "expired"}


# ---------------------------------------------------------------- student links by WhatsApp

def test_send_new_link_posts_the_activation_template_and_returns_the_copy_fallback(client, make_student, make_user, login, switched_on, run_sql):
    admin = make_user()
    student = make_student(activate=False)
    run_sql("UPDATE students SET mobile = :m WHERE student_id = :s", m=PHONE, s=student.student_id)

    response = client.post(f"/api/v1/students/{student.student_id}/activation", headers=login(admin.email))

    data = response.get_json()["data"]
    assert response.status_code == 201 and data["whatsapp"]["state"] == "Queued" and data["activation_path"].endswith(data["token"])
    newest = outbox(whatsapp_templates.STUDENT_ACTIVATION_LINK)[-1]  # the CRM admission queued the first link; this is the second
    assert newest.status == "Queued" and newest.button_params == [data["token"]] and student.student_code in newest.params


def test_the_link_answer_says_why_nothing_was_sent(client, make_student, make_user, login):
    admin = make_user()
    student = make_student(activate=False)

    data = client.post(f"/api/v1/students/{student.student_id}/activation", headers=login(admin.email)).get_json()["data"]

    assert data["whatsapp"] == {"state": "Skipped", "note": "WhatsApp is switched off"}


def test_the_first_link_is_queued_when_the_crm_admits_a_student(make_student, switched_on):
    student = make_student(activate=False)

    (message,) = outbox(whatsapp_templates.STUDENT_ACTIVATION_LINK)
    assert message.status == "Queued" and message.button_params == [student.token] and student.student_code in message.params


# ---------------------------------------------------------------- unlock

def test_a_super_admin_unlocks_an_account_with_a_reason(client, make_user, login):
    admin = make_user()
    locked = make_user(roles=[("TRAINER", 1)], locked_until=datetime.now(timezone.utc) + timedelta(minutes=10), failed_login_attempts=0)

    assert client.post(f"/api/v1/admin/users/{locked.user_id}/unlock", headers=login(admin.email), json={}).status_code == 400  # a reason is needed
    response = client.post(f"/api/v1/admin/users/{locked.user_id}/unlock", headers=login(admin.email), json={"reason": "Called the front desk"})

    assert response.status_code == 200 and response.get_json()["data"]["is_locked"] is False
    assert db.session.get(User, locked.user_id).locked_until is None
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "USER_UNLOCKED")).scalar_one()
    assert entry.reason == "Called the front desk"
    assert client.post(f"/api/v1/admin/users/{locked.user_id}/unlock", headers=login(admin.email), json={"reason": "again"}).status_code == 422


def test_only_a_super_admin_unlocks(client, make_user, login):
    manager, other = make_user(roles=[("BRANCH_MANAGER", 1)]), make_user(roles=[("TRAINER", 1)])

    assert client.post(f"/api/v1/admin/users/{other.user_id}/unlock", headers=login(manager.email), json={"reason": "x"}).status_code == 403


# ---------------------------------------------------------------- CRM round 6: status events

def sent_message(client, make_user, login, switched_on):
    """A staff invite handed to the CRM, which answered Queued (the normal first answer)."""
    from services import whatsapp
    from tests.test_whatsapp import FakeCrm
    admin = make_user()
    create_staff(client, login, admin)
    db.session.commit()
    crm = FakeCrm((200, {"data": {"status": "Queued", "outbox_id": 27}}))
    whatsapp.send_pending(poster=crm)
    (message,) = outbox(whatsapp_templates.STAFF_ACCOUNT_INVITE)
    return message


def status_event(crm_event, message, status, version, **data):
    return crm_event("WhatsappStatusUpdated", {"dedupe_key": message.dedupe_key, "crm_outbox_id": 27, "status": status,
                                               "provider_message_id": "wamid.1", "reason": None, **data}, source_version=version)


def test_queued_is_the_normal_answer_and_the_status_events_follow_it(client, make_user, login, switched_on, crm_event):
    message = sent_message(client, make_user, login, switched_on)
    assert message.status == "Sent" and message.crm_outbox_id == 27

    assert status_event(crm_event, message, "Sent", 1).status_code == 201
    assert status_event(crm_event, message, "Delivered", 2).status_code == 201
    db.session.refresh(message)
    assert (message.delivery_status, message.delivery_version, message.provider_message_id) == ("Delivered", 2, "wamid.1")

    older = status_event(crm_event, message, "Sent", 1, crm_outbox_id=27)
    assert older.status_code == 200 or older.get_json()["data"]["status"] == "Ignored — stale"
    db.session.refresh(message)
    assert message.delivery_status == "Delivered"


def test_a_failed_event_marks_the_message_failed_with_the_reason(client, make_user, login, switched_on, crm_event):
    message = sent_message(client, make_user, login, switched_on)

    status_event(crm_event, message, "Failed", 3, reason="template does not exist")

    db.session.refresh(message)
    assert message.status == "Failed" and "template does not exist" in message.status_note and message.delivery_status == "Failed"


def test_an_event_for_an_unknown_message_is_answered_without_an_error(client, crm_event):
    response = crm_event("WhatsappStatusUpdated", {"dedupe_key": "nobody:1", "status": "Delivered"}, source_version=1)

    assert response.status_code < 300 and response.get_json()["data"]["status"] == "Ignored — stale"

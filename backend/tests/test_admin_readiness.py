"""Integration readiness and security readiness registers: access, verification rules, audit, integration_status()."""
from sqlalchemy import select, text

from config.database import db
from models import AuditLog, SecurityControl
from services import integrations as integrations_service
from tests.conftest import PASSWORD


def _code(client, headers, code):
    rows = client.get("/api/v1/integrations", headers=headers).get_json()["data"]
    return next(r for r in rows if r["integration_code"] == code)


def _age_fresh_auth(run_sql, user_id):
    run_sql("UPDATE user_sessions SET reauthenticated_at = now() - interval '2 hours' WHERE user_id = :u", u=user_id)


# ---------------------------------------------------------------- integrations

def test_super_admin_and_founder_read_the_register_others_are_refused(client, make_user, login):
    admin = make_user()
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])

    rows = client.get("/api/v1/integrations", headers=login(admin.email)).get_json()["data"]
    assert {"GOOGLE_MEET", "MEET_ORGANIZER_GNT", "MEET_ORGANIZER_VIJ", "HDFC_PAYMENTS", "PRODUCTION_AUTH", "CRM"} <= {r["integration_code"] for r in rows}
    assert client.get("/api/v1/integrations", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/integrations", headers=login(manager.email)).status_code == 403
    assert client.get("/api/v1/integrations").status_code == 401


def test_any_signed_in_user_sees_the_availability_states(client, make_user, login):
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])

    rows = client.get("/api/v1/integrations/status", headers=login(manager.email)).get_json()["data"]

    by_code = {r["integration_code"]: r for r in rows}
    assert by_code["MEET_ORGANIZER_GNT"]["state"] == "Pending Verification"
    assert by_code["WHATSAPP"]["state"] == "Integration Unavailable"
    assert "requirement" not in by_code["WHATSAPP"]


def test_integration_status_service_reads_the_register(app, make_user, login, client):
    assert integrations_service.integration_status("GOOGLE_MEET").state == "Integration Unavailable"
    assert not integrations_service.is_verified("GOOGLE_MEET")
    unknown = integrations_service.integration_status("NOPE")
    assert (unknown.configuration_status, unknown.verification_status) == ("Not Configured", "Not Verified")

    headers = login(make_user().email)
    meet = _code(client, headers, "GOOGLE_MEET")
    client.patch(f"/api/v1/integrations/{meet['integration_id']}", headers=headers,
                 json={"configuration_status": "Configured", "verification_status": "Verified", "evidence": "Test meeting created 30 Sep"})

    assert integrations_service.is_verified("GOOGLE_MEET")
    assert integrations_service.integration_status("GOOGLE_MEET").state == "Verified"


def test_only_a_super_admin_can_update_and_the_update_is_audited(client, make_user, login):
    admin = make_user()
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    headers = login(admin.email)
    drive = _code(client, headers, "GOOGLE_DRIVE_RECORDINGS")
    url = f"/api/v1/integrations/{drive['integration_id']}"

    assert client.patch(url, headers=login(founder.email), json={"notes": "x"}).status_code == 403
    response = client.patch(url, headers=headers, json={"configuration_status": "Misconfigured", "notes": "Wrong shared drive"})

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert (data["configuration_status"], data["notes"], data["last_checked_at"] is not None) == ("Misconfigured", "Wrong shared drive", True)
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "INTEGRATION_UPDATED")).scalar_one()
    assert entry.entity_id == "GOOGLE_DRIVE_RECORDINGS" and entry.actor_user_id == admin.user_id
    assert entry.old_values == {"configuration_status": "Not Configured", "notes": "Recording capability must be verified per organizer"}
    assert entry.new_values["configuration_status"] == "Misconfigured"


def test_update_needs_fresh_authentication(client, make_user, login, run_sql):
    admin = make_user()
    headers = login(admin.email)
    email = _code(client, headers, "EMAIL")
    _age_fresh_auth(run_sql, admin.user_id)

    response = client.patch(f"/api/v1/integrations/{email['integration_id']}", headers=headers, json={"notes": "x"})

    assert response.status_code == 401 and response.get_json()["error"]["code"] == "FRESH_AUTH_REQUIRED"
    assert client.post("/api/v1/auth/reauthenticate", headers=headers, json={"password": PASSWORD}).status_code == 204
    assert client.patch(f"/api/v1/integrations/{email['integration_id']}", headers=headers, json={"notes": "x"}).status_code == 200


def test_verified_needs_configured_setup_and_evidence(client, make_user, login):
    headers = login(make_user().email)
    whatsapp = _code(client, headers, "WHATSAPP")
    url = f"/api/v1/integrations/{whatsapp['integration_id']}"

    not_configured = client.patch(url, headers=headers, json={"verification_status": "Verified", "evidence": "Sent a test message"})
    no_evidence = client.patch(url, headers=headers, json={"configuration_status": "Configured", "verification_status": "Verified"})
    blank_evidence = client.patch(url, headers=headers, json={"configuration_status": "Configured", "verification_status": "Verified", "evidence": "  "})

    assert not_configured.status_code == 422 and "Configured" in not_configured.get_json()["error"]["message"]
    assert no_evidence.status_code == 422 and no_evidence.get_json()["error"]["details"] == {"evidence": ["Describe how it was verified"]}
    assert blank_evidence.status_code == 422
    assert _code(client, headers, "WHATSAPP")["verification_status"] == "Not Verified"


def test_verifying_records_who_and_when_and_unconfiguring_drops_the_verification(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    crm = _code(client, headers, "CRM")
    url = f"/api/v1/integrations/{crm['integration_id']}"

    verified = client.patch(url, headers=headers, json={"verification_status": "Verified", "evidence": "Event 4711 applied end to end"}).get_json()["data"]
    assert (verified["verified_by"], verified["evidence"]) == (admin.user_id, "Event 4711 applied end to end")
    assert verified["verified_at"] is not None

    dropped = client.patch(url, headers=headers, json={"configuration_status": "Misconfigured"}).get_json()["data"]
    assert (dropped["verification_status"], dropped["verified_by"], dropped["verified_at"]) == ("Not Verified", None, None)


def test_the_database_refuses_verified_without_evidence(app, run_sql):
    try:
        run_sql("UPDATE integrations SET verification_status = 'Verified' WHERE integration_code = 'CRM'")
    except Exception as exc:  # noqa: BLE001 - psycopg error wrapped by SQLAlchemy
        assert "integrations_verified_needs_evidence" in str(exc)
        db.session.rollback()
    else:
        raise AssertionError("expected the CHECK constraint to reject the update")


def test_update_validation(client, make_user, login):
    headers = login(make_user().email)
    rows = client.get("/api/v1/integrations", headers=headers).get_json()["data"]
    url = f"/api/v1/integrations/{rows[0]['integration_id']}"

    assert client.patch(url, headers=headers, json={}).status_code == 400
    assert client.patch(url, headers=headers, json={"configuration_status": "Fine"}).status_code == 400
    assert client.patch("/api/v1/integrations/9999", headers=headers, json={"notes": "x"}).status_code == 404


# ---------------------------------------------------------------- security controls

def test_security_controls_are_seeded_and_readable_by_super_admin_and_founder(client, make_user, login):
    admin = make_user()
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    trainer = make_user(roles=[("TRAINER", 1)])

    rows = client.get("/api/v1/security-controls", headers=login(admin.email)).get_json()["data"]

    codes = {r["control_code"] for r in rows}
    assert {"SCOPE_ENFORCEMENT", "SESSION_IDLE", "SESSION_MAX", "FRESH_AUTH", "LOGIN_LOCKOUT", "UNIQUE_LMS_LOGIN", "ACTIVATION_TOKEN",
            "AUDIT_IMMUTABLE", "FILE_ACCESS", "EXPORT_SCOPING", "AI_DATA_SCOPE", "BACKUPS"} <= codes
    assert all(r["verification_status"] != "Verified" for r in rows)
    assert client.get("/api/v1/security-controls", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/security-controls", headers=login(trainer.email)).status_code == 403


def test_a_control_is_verified_with_evidence_and_audited(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    control = next(r for r in client.get("/api/v1/security-controls", headers=headers).get_json()["data"] if r["control_code"] == "AUDIT_IMMUTABLE")
    url = f"/api/v1/security-controls/{control['control_id']}"

    refused = client.patch(url, headers=headers, json={"verification_status": "Verified"})
    accepted = client.patch(url, headers=headers, json={"verification_status": "Verified", "evidence": "UPDATE on audit_log raised an error in staging"})

    assert refused.status_code == 422
    data = accepted.get_json()["data"]
    assert (data["verification_status"], data["verified_by"]) == ("Verified", admin.user_id)
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "SECURITY_CONTROL_UPDATED")).scalar_one()
    assert entry.entity_id == "AUDIT_IMMUTABLE" and entry.new_values["verification_status"] == "Verified"
    assert db.session.execute(select(SecurityControl.verified_by).where(SecurityControl.control_code == "AUDIT_IMMUTABLE")).scalar() == admin.user_id


def test_control_updates_are_super_admin_only(client, make_user, login):
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    admin_headers = login(make_user().email)
    control = client.get("/api/v1/security-controls", headers=admin_headers).get_json()["data"][0]

    response = client.patch(f"/api/v1/security-controls/{control['control_id']}", headers=login(founder.email), json={"notes": "x"})

    assert response.status_code == 403
    assert client.get("/api/v1/security-controls/9999", headers=admin_headers).status_code == 404


def test_audit_log_stays_append_only(app, make_user, login, client):
    headers = login(make_user().email)
    control = client.get("/api/v1/security-controls", headers=headers).get_json()["data"][0]
    client.patch(f"/api/v1/security-controls/{control['control_id']}", headers=headers, json={"notes": "checked"})
    entry = db.session.execute(select(AuditLog)).scalars().first()

    try:
        db.session.execute(text("UPDATE audit_log SET reason = 'edited' WHERE audit_id = :id"), {"id": entry.audit_id})
    except Exception as exc:  # noqa: BLE001
        assert "audit_log" in str(exc)
        db.session.rollback()
    else:
        raise AssertionError("audit_log must reject updates")

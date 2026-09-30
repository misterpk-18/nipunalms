"""Student Accounts: search, detail, activation link, suspend / reactivate, revoke sessions."""
from sqlalchemy import select

from config.database import db
from models import AuditLog
from tests.conftest import PASSWORD


def _audit(action):
    return db.session.execute(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.audit_id.desc())).scalars().first()


def _student_login(client, student, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"login": student.student_code, "password": password})


def test_only_super_admin_administers_and_the_founder_reads(client, make_user, login, make_student):
    student = make_student()
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    coordinator = make_user(roles=[("ACADEMIC_COORDINATOR", 1)])
    url = f"/api/v1/admin/students/{student.student_id}"

    assert client.get("/api/v1/admin/students", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/admin/students", headers=login(coordinator.email)).status_code == 403
    assert client.post(f"{url}/suspend", headers=login(founder.email), json={"reason": "x"}).status_code == 403
    assert client.post(f"{url}/revoke-sessions", headers=login(coordinator.email), json={}).status_code == 403


def test_search_by_student_id_name_and_email_with_activation_and_enrolment_summary(client, make_user, login, make_student):
    admin = make_user()
    anvitha = make_student(email="anvitha.k@example.test")
    invited = make_student(activate=False, name="Pending Learner", email="pending@example.test")
    headers = login(admin.email)

    everyone = client.get("/api/v1/admin/students", headers=headers).get_json()
    assert everyone["meta"]["total"] == 2

    by_code = client.get(f"/api/v1/admin/students?q={anvitha.student_code.lower()}", headers=headers).get_json()["data"]
    assert [s["student_code"] for s in by_code] == [anvitha.student_code]
    row = by_code[0]
    assert row["activation_status"] == "Activated" and row["has_password"] is True and row["is_login_active"] is True
    assert row["lms_user_id"] == anvitha.student_code and row["enrolment_total"] == 1 and row["service_branch"]["branch_code"] == "NIT-GNT"

    assert [s["student_code"] for s in client.get("/api/v1/admin/students?q=pending", headers=headers).get_json()["data"]] == [invited.student_code]
    assert [s["student_code"] for s in client.get("/api/v1/admin/students?q=k@example", headers=headers).get_json()["data"]] == [anvitha.student_code]
    pending = client.get("/api/v1/admin/students?activation_status=Activation Pending", headers=headers).get_json()["data"]
    assert [s["student_code"] for s in pending] == [invited.student_code] and pending[0]["has_password"] is False
    assert client.get("/api/v1/admin/students?branch_id=2", headers=headers).get_json()["data"] == []
    assert client.get("/api/v1/admin/students?activation_status=Nope", headers=headers).status_code == 400


def test_detail_shows_enrolments_activation_state_and_recent_audit(client, make_user, login, make_student):
    admin = make_user()
    student = make_student(activate=False)
    headers = login(admin.email)
    client.post(f"/api/v1/students/{student.student_id}/activation", headers=headers)

    data = client.get(f"/api/v1/admin/students/{student.student_id}", headers=headers).get_json()["data"]

    assert data["enrolments"][0]["course_code"] == "NIT-CRS-047" and data["enrolments"][0]["status"] in ("Allocation Pending", "Curriculum Mapping Pending")
    assert data["activation"]["status"] == "valid" and "token" not in data["activation"]
    assert data["audit"][0]["action"] == "ACTIVATION_REISSUED"
    assert data["suspension"] is None
    assert client.get("/api/v1/admin/students/99999", headers=headers).status_code == 404


def test_the_activation_link_is_issued_once_and_shown_once(client, make_user, login, make_student):
    admin = make_user()
    student = make_student(activate=False)
    headers = login(admin.email)

    issued = client.post(f"/api/v1/students/{student.student_id}/activation", headers=headers).get_json()["data"]

    assert issued["token"] and issued["token"] != student.token
    detail = client.get(f"/api/v1/admin/students/{student.student_id}", headers=headers).get_json()["data"]
    assert issued["token"] not in str(detail)
    assert client.post("/api/v1/auth/activate", json={"token": student.token, "password": "Another-passw0rd"}).status_code == 422  # the old link is void
    assert client.post("/api/v1/auth/activate", json={"token": issued["token"], "password": "Another-passw0rd"}).status_code == 200


def test_suspend_blocks_the_student_ends_sessions_and_cancels_the_activation_link(client, make_user, login, make_student):
    admin = make_user()
    student = make_student()
    student_headers = login(student.student_code)
    headers = login(admin.email)
    url = f"/api/v1/admin/students/{student.student_id}"
    assert client.get(f"/api/v1/students/{student.student_id}", headers=student_headers).status_code == 200

    assert client.post(f"{url}/suspend", headers=headers, json={}).status_code == 400
    response = client.post(f"{url}/suspend", headers=headers, json={"reason": "Fee dispute escalated by branch"})

    data = response.get_json()["data"]
    assert response.status_code == 200 and data["activation_status"] == "Suspended" and data["is_login_active"] is False
    assert client.get(f"/api/v1/students/{student.student_id}", headers=student_headers).status_code == 401
    assert _student_login(client, student).status_code == 401
    assert client.post(f"{url}/suspend", headers=headers, json={"reason": "again"}).status_code == 422
    assert client.post(f"/api/v1/students/{student.student_id}/activation", headers=headers).status_code == 422  # no link for a suspended account
    entry = _audit("STUDENT_SUSPENDED")
    assert entry.actor_user_id == admin.user_id and entry.reason == "Fee dispute escalated by branch"
    assert entry.old_values == {"activation_status": "Activated"} and entry.branch_id == 1
    detail = client.get(url, headers=headers).get_json()["data"]
    assert detail["suspension"]["reason"] == "Fee dispute escalated by branch"


def test_reactivate_restores_an_activated_student_who_can_sign_in_again(client, make_user, login, make_student):
    admin = make_user()
    student = make_student()
    headers = login(admin.email)
    url = f"/api/v1/admin/students/{student.student_id}"
    assert client.post(f"{url}/reactivate", headers=headers, json={}).status_code == 422  # not suspended
    client.post(f"{url}/suspend", headers=headers, json={"reason": "Investigation"})

    response = client.post(f"{url}/reactivate", headers=headers, json={"reason": "Cleared"})

    assert response.get_json()["data"]["activation_status"] == "Activated"
    assert _student_login(client, student).status_code == 200
    assert _audit("STUDENT_REACTIVATED").reason == "Cleared"


def test_a_student_who_never_activated_returns_to_account_created_and_needs_a_new_link(client, make_user, login, make_student):
    admin = make_user()
    student = make_student(activate=False)
    headers = login(admin.email)
    url = f"/api/v1/admin/students/{student.student_id}"

    client.post(f"{url}/suspend", headers=headers, json={"reason": "Wrong person invited"})
    restored = client.post(f"{url}/reactivate", headers=headers, json={}).get_json()["data"]

    assert restored["activation_status"] == "Account Created" and restored["has_password"] is False
    assert client.post("/api/v1/auth/activate", json={"token": student.token, "password": "Another-passw0rd"}).status_code == 422
    fresh = client.post(f"/api/v1/students/{student.student_id}/activation", headers=headers).get_json()["data"]["token"]
    assert client.post("/api/v1/auth/activate", json={"token": fresh, "password": "Another-passw0rd"}).status_code == 200


def test_revoke_sessions_signs_the_student_out_everywhere(client, make_user, login, make_student):
    admin = make_user()
    student = make_student()
    first, second = login(student.student_code), login(student.student_code)
    headers = login(admin.email)

    response = client.post(f"/api/v1/admin/students/{student.student_id}/revoke-sessions", headers=headers, json={"reason": "Lost phone"})

    assert response.get_json()["data"] == {"sessions_ended": 2}
    assert client.get(f"/api/v1/students/{student.student_id}", headers=first).status_code == 401
    assert client.get(f"/api/v1/students/{student.student_id}", headers=second).status_code == 401
    assert _student_login(client, student).status_code == 200  # revoking sessions does not suspend
    assert _audit("STUDENT_SESSIONS_REVOKED").reason == "Lost phone"


def test_list_reports_active_sessions_per_student(client, make_user, login, make_student):
    admin = make_user()
    student = make_student()
    login(student.student_code)
    login(student.student_code)

    row = client.get(f"/api/v1/admin/students?q={student.student_code}", headers=login(admin.email)).get_json()["data"][0]

    assert row["active_sessions"] == 2 and row["last_login_at"] is not None


def test_actions_on_an_unknown_student_are_not_found(client, make_user, login):
    headers = login(make_user().email)

    for action, body in (("suspend", {"reason": "x"}), ("reactivate", {}), ("revoke-sessions", {})):
        assert client.post(f"/api/v1/admin/students/9999/{action}", headers=headers, json=body).status_code == 404

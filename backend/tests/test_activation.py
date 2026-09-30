"""Student activation: token status, activate, reuse, expiry, and staff issue / reissue."""
from sqlalchemy import select

from config.database import db
from models import AuditLog, Role, Student, StudentActivation, UserRoleScope
from tests.conftest import PASSWORD

NEW_PASSWORD = "My-own-passw0rd"


def token_status(client, token):
    return client.get(f"/api/v1/auth/activation/{token}")


def activate(client, token, password=NEW_PASSWORD):
    return client.post("/api/v1/auth/activate", json={"token": token, "password": password})


# ---------------------------------------------------------------- token status and activation

def test_valid_token_shows_status_and_a_masked_student_id(client, make_student):
    student = make_student(activate=False)

    response = token_status(client, student.token)

    data = response.get_json()["data"]
    assert response.status_code == 200 and data["status"] == "valid"
    assert data["student_code"].startswith("NIT-STU-") and "••••" in data["student_code"]
    assert data["student_code"] != student.student_code
    assert data["full_name"] == "Anvitha K." and data["expires_at"]


def test_unknown_token_is_not_found(client):
    assert token_status(client, "not-a-real-token").status_code == 404
    assert activate(client, "not-a-real-token").status_code == 404


def test_activation_sets_the_password_marks_activated_and_creates_the_student_scope(client, make_student):
    student = make_student(activate=False)

    response = activate(client, student.token)

    assert response.status_code == 200
    assert response.get_json()["data"] == {"activated": True, "student_code": student.student_code}
    assert db.session.get(Student, student.student_id).activation_status == "Activated"
    scopes = db.session.execute(select(UserRoleScope.branch_id).join(Role).where(Role.role_code == "STUDENT")).scalars().all()
    assert scopes == [1]
    login = client.post("/api/v1/auth/login", json={"login": student.student_code, "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert client.post("/api/v1/auth/login", json={"login": student.student_code, "password": "other"}).status_code == 401
    assert "ACCOUNT_ACTIVATED" in db.session.execute(select(AuditLog.action)).scalars().all()


def test_a_token_cannot_be_reused(client, make_student):
    student = make_student(activate=False)
    assert activate(client, student.token).status_code == 200

    again = activate(client, student.token, "Another-passw0rd")

    assert again.status_code == 422 and again.get_json()["error"]["details"] == {"status": "used"}
    assert token_status(client, student.token).get_json()["data"]["status"] == "used"
    assert client.post("/api/v1/auth/login", json={"login": student.student_code, "password": "Another-passw0rd"}).status_code == 401


def test_an_expired_token_is_refused(client, make_student, run_sql):
    student = make_student(activate=False)
    run_sql("UPDATE student_activations SET expires_at = now() - interval '1 minute'")

    assert token_status(client, student.token).get_json()["data"]["status"] == "expired"
    response = activate(client, student.token)

    assert response.status_code == 422 and response.get_json()["error"]["details"] == {"status": "expired"}
    assert db.session.get(Student, student.student_id).activation_status == "Activation Pending"


def test_activation_enforces_the_password_length(client, make_student):
    student = make_student(activate=False)

    response = activate(client, student.token, "short")

    assert response.status_code == 400 and "password" in response.get_json()["error"]["details"]
    assert token_status(client, student.token).get_json()["data"]["status"] == "valid"  # not consumed


def test_only_the_hash_of_a_token_is_stored(client, make_student):
    student = make_student(activate=False)

    stored = db.session.execute(select(StudentActivation.token_hash)).scalars().all()

    assert stored and student.token not in stored


# ---------------------------------------------------------------- staff issue / reissue

def issue(client, headers, student_id):
    return client.post(f"/api/v1/students/{student_id}/activation", headers=headers)


def test_branch_manager_reissues_a_token_and_the_old_one_stops_working(client, make_student, make_user, login):
    student = make_student(activate=False)
    headers = login(make_user(roles=[("BRANCH_MANAGER", 1)]).email)

    response = issue(client, headers, student.student_id)

    data = response.get_json()["data"]
    assert response.status_code == 201
    assert data["student_code"] == student.student_code and data["token"] != student.token
    assert data["activation_path"] == f"/activate?token={data['token']}" and data["expires_at"]
    assert token_status(client, student.token).get_json()["data"]["status"] == "revoked"
    assert activate(client, student.token).status_code == 422
    assert activate(client, data["token"]).status_code == 200
    actions = db.session.execute(select(AuditLog.action)).scalars().all()
    assert "ACTIVATION_REISSUED" in actions


def test_super_admin_and_coordinator_at_the_branch_can_issue(client, make_student, make_user, login):
    student = make_student(activate=False)

    for role in (("SUPER_ADMIN", None), ("ACADEMIC_COORDINATOR", 1)):
        headers = login(make_user(roles=[role]).email)
        assert issue(client, headers, student.student_id).status_code == 201


def test_other_branch_managers_and_unauthorised_roles_cannot_issue(client, make_student, make_user, login):
    student = make_student(activate=False)  # serviced at Guntur

    other_branch = issue(client, login(make_user(roles=[("BRANCH_MANAGER", 2)]).email), student.student_id)
    trainer = issue(client, login(make_user(roles=[("TRAINER", 1)]).email), student.student_id)
    founder = issue(client, login(make_user(roles=[("FOUNDER_CEO", None)]).email), student.student_id)
    student_user = issue(client, login(make_student().student_code), student.student_id)

    assert other_branch.status_code == 404  # outside scope looks like a missing record
    assert (trainer.status_code, founder.status_code, student_user.status_code) == (403, 403, 403)
    assert issue(client, login(make_user(roles=[("SUPER_ADMIN", None)]).email), 999999).status_code == 404


def test_issuing_needs_fresh_authentication(client, make_student, make_user, login, run_sql):
    student = make_student(activate=False)
    user = make_user(roles=[("BRANCH_MANAGER", 1)])
    headers = login(user.email)
    run_sql("UPDATE user_sessions SET reauthenticated_at = now() - interval '1 hour'")

    stale = issue(client, headers, student.student_id)
    assert stale.status_code == 401 and stale.get_json()["error"]["code"] == "FRESH_AUTH_REQUIRED"

    assert client.post("/api/v1/auth/reauthenticate", headers=headers, json={"password": PASSWORD}).status_code == 204
    assert issue(client, headers, student.student_id).status_code == 201


def test_an_activated_student_cannot_be_issued_a_token(client, make_student, make_user, login):
    student = make_student()

    response = issue(client, login(make_user(roles=[("BRANCH_MANAGER", 1)]).email), student.student_id)

    assert response.status_code == 422 and "already activated" in response.get_json()["error"]["message"]

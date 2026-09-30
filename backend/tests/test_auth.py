"""Login (staff email, Student ID, student email), lockout, forced password change, profile shape."""
import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, UserSession
from services.security import hash_token
from tests.conftest import PASSWORD

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def login_response(client, login, password=PASSWORD):
    return client.post(LOGIN, json={"login": login, "password": password})


# ---------------------------------------------------------------- staff email login

def test_staff_login_returns_token_and_the_exact_profile_shape(client, make_user):
    user = make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM Guntur")

    response = login_response(client, user.email.upper())  # email is case-insensitive
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert set(data) == {"token", "expires_at", "user", "scopes", "allowed_branches", "workspaces", "home_route", "student"}
    assert data["user"] == {"user_id": user.user_id, "full_name": "BM Guntur", "email": user.email,
                            "must_change_password": False, "student_id": None}
    assert set(data["scopes"][0]) == {"scope_id", "role_code", "role_name", "branch_id", "branch_code", "branch_name",
                                      "is_company_wide"}
    assert [(s["role_code"], s["branch_code"], s["is_company_wide"]) for s in data["scopes"]] == [("BRANCH_MANAGER", "NIT-GNT", False)]
    assert data["allowed_branches"] == [{"branch_id": 1, "branch_code": "NIT-GNT", "branch_name": "Guntur"}]
    assert data["workspaces"] == ["branch"] and data["home_route"] == "/branch"
    assert data["student"] is None
    assert data["expires_at"]

    stored_ids = db.session.execute(select(UserSession.session_id).where(UserSession.user_id == user.user_id)).scalars().all()
    assert stored_ids == [hash_token(data["token"])]  # only the hash is stored


@pytest.mark.parametrize(
    "roles, workspaces, home_route, branch_count",
    [
        ([("TRAINER", 1)], ["trainer"], "/trainer", 1),
        ([("ACADEMIC_COORDINATOR", 2)], ["academic"], "/academic", 1),
        ([("BRANCH_MANAGER", 2)], ["branch"], "/branch", 1),
        ([("SUPER_ADMIN", None)], ["admin", "academic", "branch"], "/admin", 2),
        ([("FOUNDER_CEO", None)], ["founder", "admin", "branch"], "/founder", 2),
        ([("TRAINER", 1), ("ACADEMIC_COORDINATOR", 1)], ["academic", "trainer"], "/academic", 1),
    ],
)
def test_workspaces_home_route_and_branches_follow_the_roles(client, make_user, roles, workspaces, home_route, branch_count):
    user = make_user(roles=roles)

    data = login_response(client, user.email).get_json()["data"]

    assert data["workspaces"] == workspaces
    assert data["home_route"] == home_route
    assert len(data["allowed_branches"]) == branch_count
    assert client.get(ME, headers={"Authorization": f"Bearer {data['token']}"}).get_json()["data"]["home_route"] == home_route


def test_me_returns_the_same_profile_as_login(client, make_user):
    user = make_user(roles=[("SUPER_ADMIN", None)])
    login_data = login_response(client, user.email).get_json()["data"]

    me = client.get(ME, headers={"Authorization": f"Bearer {login_data['token']}"}).get_json()["data"]

    assert me == {k: v for k, v in login_data.items() if k not in ("token", "expires_at")}


# ---------------------------------------------------------------- Student ID and student email login

def test_student_logs_in_with_student_id_in_any_case_or_with_email(client, make_student):
    student = make_student()

    by_id = login_response(client, student.student_code)
    by_lower_id = login_response(client, f"  {student.student_code.lower()} ")
    by_email = login_response(client, student.email.upper())

    for response in (by_id, by_lower_id, by_email):
        assert response.status_code == 200, response.get_json()
    data = by_id.get_json()["data"]
    assert data["workspaces"] == ["student"] and data["home_route"] == "/dashboard"
    assert data["user"]["student_id"] == student.student_id
    assert data["student"] == {
        "student_id": student.student_id, "student_code": student.student_code, "full_name": "Anvitha K.", "name_te": None,
        "preferred_language": "en", "activation_status": "Activated", "service_branch_id": 1}
    assert [(s["role_code"], s["branch_id"]) for s in data["scopes"]] == [("STUDENT", 1)]
    assert data["allowed_branches"] == [{"branch_id": 1, "branch_code": "NIT-GNT", "branch_name": "Guntur"}]


def test_student_login_records_learning_activity(client, make_student):
    student = make_student()

    login_response(client, student.student_code)

    kinds = db.session.execute(db.text("SELECT kind FROM activity_events WHERE student_id = :s"), {"s": student.student_id}).scalars().all()
    assert kinds == ["login"]


def test_student_cannot_log_in_before_activation(client, make_student):
    student = make_student(activate=False)

    assert login_response(client, student.student_code).status_code == 401
    assert login_response(client, student.student_code, "").status_code == 400


def test_unknown_student_id_wrong_password_and_unknown_email_get_the_same_error(client, make_student, make_user):
    student = make_student()
    user = make_user()

    responses = [
        login_response(client, "NIT-STU-2026-999999"),
        login_response(client, student.student_code, "not-the-password"),
        login_response(client, user.email, "not-the-password"),
        login_response(client, "nobody@nipuna.test"),
    ]

    assert {r.status_code for r in responses} == {401}
    assert len({str(r.get_json()) for r in responses}) == 1


# ---------------------------------------------------------------- lockout and other rules

def test_account_locks_after_five_failures_for_staff_and_students(client, make_user, make_student):
    user = make_user()
    student = make_student()

    for login_value in (user.email, student.student_code):
        statuses = [login_response(client, login_value, "wrong-password").status_code for _ in range(5)]
        locked = login_response(client, login_value)  # correct password, but locked

        assert statuses == [401] * 5
        assert locked.status_code == 429
        assert locked.get_json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_inactive_user_cannot_log_in(client, make_user):
    assert login_response(client, make_user(is_active=False).email).status_code == 401


def test_user_without_active_access_cannot_log_in(client, make_user):
    response = login_response(client, make_user(roles=[]).email)

    assert response.status_code == 403
    assert "no active access" in response.get_json()["error"]["message"]


def test_login_validates_input(client):
    response = client.post(LOGIN, json={})

    assert response.status_code == 400
    assert set(response.get_json()["error"]["details"]) == {"login", "password"}


def test_login_is_audited(client, make_user):
    user = make_user()
    login_response(client, user.email)

    actions = db.session.execute(select(AuditLog.action, AuditLog.actor_user_id)).all()
    assert ("LOGIN", user.user_id) in actions


# ---------------------------------------------------------------- sessions

def test_protected_endpoints_need_a_valid_token(client):
    assert client.get(ME).status_code == 401
    assert client.get(ME, headers={"Authorization": "Bearer made-up"}).status_code == 401
    assert client.get(ME, headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_revokes_the_session(client, make_user, login):
    headers = login(make_user().email)

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get(ME, headers=headers).status_code == 401


def test_own_sessions_are_listed_and_can_be_revoked(client, make_user, login):
    user = make_user()
    first, second = login(user.email), login(user.email)

    sessions = client.get("/api/v1/auth/sessions", headers=first).get_json()["data"]
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1

    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/v1/auth/sessions/{other['session_id']}", headers=first).status_code == 204
    assert client.get(ME, headers=second).status_code == 401
    assert client.get(ME, headers=first).status_code == 200


def test_idle_and_expired_sessions_are_rejected(client, make_user, login, run_sql):
    headers = login(make_user().email)

    run_sql("UPDATE user_sessions SET last_seen_at = now() - interval '31 minutes'")

    assert client.get(ME, headers=headers).status_code == 401


# ---------------------------------------------------------------- forced password change

def test_temporary_password_must_be_changed_before_anything_else(client, make_user, login):
    user = make_user(roles=[("TRAINER", 1)], must_change_password=True)
    headers = login(user.email)

    assert client.get(ME, headers=headers).status_code == 200
    blocked = client.get("/api/v1/batches", headers=headers)
    assert blocked.status_code == 403 and blocked.get_json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    changed = client.post("/api/v1/auth/change-password", headers=headers,
                          json={"current_password": PASSWORD, "new_password": "Brand-new-passw0rd"})
    assert changed.status_code == 204
    assert client.get("/api/v1/batches", headers=headers).status_code == 200
    assert login_response(client, user.email, "Brand-new-passw0rd").status_code == 200
    assert login_response(client, user.email).status_code == 401


def test_change_password_rules(client, make_user, login):
    headers = login(make_user().email)

    def change(current, new):
        return client.post("/api/v1/auth/change-password", headers=headers, json={"current_password": current, "new_password": new})

    assert change("wrong-password", "Brand-new-passw0rd").status_code == 400
    assert change(PASSWORD, PASSWORD).status_code == 400
    assert change(PASSWORD, "short").status_code == 400


def test_reauthenticate_checks_the_password(client, make_user, login):
    headers = login(make_user().email)

    assert client.post("/api/v1/auth/reauthenticate", headers=headers, json={"password": "nope"}).status_code == 400
    assert client.post("/api/v1/auth/reauthenticate", headers=headers, json={"password": PASSWORD}).status_code == 204

"""Users & Access: staff list, create with a temporary password, role scopes, deactivate / reactivate, password reset."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config.database import db
from models import AuditLog, User, UserRoleScope
from tests.conftest import PASSWORD

NEW_USER = {"full_name": "Trainer N. Newhire", "email": "New.Hire@nipuna.test", "scopes": [{"role_code": "TRAINER", "branch_id": 1}]}


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def _audit(action):
    return db.session.execute(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.audit_id.desc())).scalars().first()


def test_only_super_admin_manages_users_and_the_founder_reads(client, make_user, login):
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    target = make_user(roles=[("TRAINER", 1)])

    assert client.get("/api/v1/admin/users", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/admin/users", headers=login(manager.email)).status_code == 403
    assert client.post("/api/v1/admin/users", headers=login(founder.email), json=NEW_USER).status_code == 403
    assert client.post(f"/api/v1/admin/users/{target.user_id}/deactivate", headers=login(manager.email), json={"reason": "x"}).status_code == 403


def test_list_shows_staff_with_scopes_filters_and_no_students(client, make_user, login, make_student):
    admin = make_user(full_name="Aaa Admin")
    trainer = make_user(roles=[("TRAINER", 2)], full_name="Zed Trainer")
    make_student()

    everyone = client.get("/api/v1/admin/users", headers=login(admin.email)).get_json()
    by_id = {u["user_id"]: u for u in everyone["data"]}
    assert set(by_id) == {admin.user_id, trainer.user_id}
    assert by_id[trainer.user_id]["scopes"][0]["role_code"] == "TRAINER" and by_id[trainer.user_id]["scopes"][0]["branch_code"] == "NIT-VIJ"
    assert everyone["meta"]["total"] == 2

    trainers = client.get("/api/v1/admin/users?role_code=TRAINER&branch_id=2", headers=login(admin.email)).get_json()["data"]
    assert [u["user_id"] for u in trainers] == [trainer.user_id]
    assert client.get("/api/v1/admin/users?branch_id=1&role_code=TRAINER", headers=login(admin.email)).get_json()["data"] == []
    assert [u["user_id"] for u in client.get("/api/v1/admin/users?q=zed", headers=login(admin.email)).get_json()["data"]] == [trainer.user_id]


def test_create_generates_a_temporary_password_that_must_be_changed(client, make_user, login):
    admin = make_user()

    response = client.post("/api/v1/admin/users", headers=login(admin.email), json=NEW_USER)

    data = response.get_json()["data"]
    assert response.status_code == 201 and data["email"] == "new.hire@nipuna.test" and data["must_change_password"] is True
    assert data["scopes"][0]["role_code"] == "TRAINER" and len(data["temporary_password"]) >= 10
    listed = client.get(f"/api/v1/admin/users/{data['user_id']}", headers=login(admin.email)).get_json()["data"]
    assert "temporary_password" not in listed

    signed_in = client.post("/api/v1/auth/login", json={"login": "new.hire@nipuna.test", "password": data["temporary_password"]})
    assert signed_in.status_code == 200
    token = {"Authorization": f"Bearer {signed_in.get_json()['data']['token']}"}
    assert client.get("/api/v1/batches", headers=token).get_json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    entry = _audit("USER_CREATED")
    assert entry.actor_user_id == admin.user_id and entry.new_values["email"] == "new.hire@nipuna.test"
    assert "password" not in str(entry.new_values).lower()


def test_create_validates_email_role_and_branch(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    post = lambda **changes: client.post("/api/v1/admin/users", headers=headers, json={**NEW_USER, **changes})  # noqa: E731

    assert post(email=admin.email).status_code == 409
    assert post(scopes=[]).status_code == 400
    assert post(scopes=[{"role_code": "STUDENT", "branch_id": 1}]).status_code == 400
    assert post(scopes=[{"role_code": "TRAINER"}]).status_code == 400
    assert post(scopes=[{"role_code": "TRAINER", "branch_id": 99}]).status_code == 400
    assert post(scopes=[{"role_code": "SUPER_ADMIN", "branch_id": 1}]).status_code == 400
    assert post(email="not-an-email").status_code == 400
    assert post(scopes=[{"role_code": "TRAINER", "branch_id": 1}, {"role_code": "TRAINER", "branch_id": 1}]).status_code == 409
    both = post(scopes=[{"role_code": "TRAINER", "branch_id": 1}, {"role_code": "ACADEMIC_COORDINATOR", "branch_id": 2}])
    assert both.status_code == 201 and len(both.get_json()["data"]["scopes"]) == 2


def test_grant_and_revoke_a_scope_with_audit(client, make_user, login):
    admin = make_user()
    target = make_user(roles=[("TRAINER", 1)])
    headers = login(admin.email)

    granted = client.post(f"/api/v1/admin/users/{target.user_id}/scopes", headers=headers, json={"role_code": "ACADEMIC_COORDINATOR", "branch_id": 1})
    scopes = granted.get_json()["data"]["scopes"]
    assert granted.status_code == 201 and {s["role_code"] for s in scopes} == {"TRAINER", "ACADEMIC_COORDINATOR"}
    assert client.post(f"/api/v1/admin/users/{target.user_id}/scopes", headers=headers,
                       json={"role_code": "ACADEMIC_COORDINATOR", "branch_id": 1}).status_code == 409

    coordinator = next(s for s in scopes if s["role_code"] == "ACADEMIC_COORDINATOR")
    revoke_url = f"/api/v1/admin/users/{target.user_id}/scopes/{coordinator['scope_id']}/revoke"
    assert client.post(revoke_url, headers=headers, json={}).status_code == 400  # a reason is required
    revoked = client.post(revoke_url, headers=headers, json={"reason": "Moved back to teaching"})
    assert [s["role_code"] for s in revoked.get_json()["data"]["scopes"]] == ["TRAINER"]
    assert client.post(revoke_url, headers=headers, json={"reason": "again"}).status_code == 404
    assert _audit("SCOPE_GRANTED").new_values["role_code"] == "ACADEMIC_COORDINATOR"
    assert _audit("SCOPE_REVOKED").reason == "Moved back to teaching"
    row = db.session.get(UserRoleScope, coordinator["scope_id"])
    assert row.revoked_by == admin.user_id and row.revoked_at is not None


def test_a_revoked_scope_can_be_granted_again(client, make_user, login):
    admin = make_user()
    target = make_user(roles=[("TRAINER", 1)])
    headers = login(admin.email)
    scope_id = client.get(f"/api/v1/admin/users/{target.user_id}", headers=headers).get_json()["data"]["scopes"][0]["scope_id"]
    client.post(f"/api/v1/admin/users/{target.user_id}/scopes/{scope_id}/revoke", headers=headers, json={"reason": "leave"})

    again = client.post(f"/api/v1/admin/users/{target.user_id}/scopes", headers=headers, json={"role_code": "TRAINER", "branch_id": 1})

    assert again.status_code == 201


def test_temporary_access_is_limited_to_seven_days(client, make_user, login):
    admin = make_user()
    target = make_user(roles=[("TRAINER", 1)])
    headers = login(admin.email)
    url = f"/api/v1/admin/users/{target.user_id}/scopes"
    body = {"role_code": "ACADEMIC_COORDINATOR", "branch_id": 1}

    assert client.post(url, headers=headers, json={**body, "expires_at": _iso(timedelta(days=8))}).status_code == 422
    assert client.post(url, headers=headers, json={**body, "expires_at": _iso(timedelta(days=-1))}).status_code == 400
    ok = client.post(url, headers=headers, json={**body, "expires_at": _iso(timedelta(days=6))})
    assert ok.status_code == 201 and any(s["expires_at"] for s in ok.get_json()["data"]["scopes"])


def test_deactivate_ends_sessions_and_blocks_login_until_reactivated(client, make_user, login):
    admin = make_user()
    target = make_user(roles=[("TRAINER", 1)])
    target_headers = login(target.email)
    headers = login(admin.email)
    assert client.get("/api/v1/batches", headers=target_headers).status_code == 200

    assert client.post(f"/api/v1/admin/users/{target.user_id}/deactivate", headers=headers, json={}).status_code == 400
    response = client.post(f"/api/v1/admin/users/{target.user_id}/deactivate", headers=headers, json={"reason": "Left the company"})

    assert response.status_code == 200 and response.get_json()["data"]["is_active"] is False
    assert client.get("/api/v1/batches", headers=target_headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": target.email, "password": PASSWORD}).status_code == 401
    assert client.post(f"/api/v1/admin/users/{target.user_id}/deactivate", headers=headers, json={"reason": "again"}).status_code == 422
    assert _audit("USER_DEACTIVATED").reason == "Left the company"

    assert client.post(f"/api/v1/admin/users/{target.user_id}/reactivate", headers=headers, json={}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"login": target.email, "password": PASSWORD}).status_code == 200
    assert client.post(f"/api/v1/admin/users/{target.user_id}/reactivate", headers=headers, json={}).status_code == 422


def test_the_last_super_admin_and_yourself_are_protected(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    my_scope = client.get(f"/api/v1/admin/users/{admin.user_id}", headers=headers).get_json()["data"]["scopes"][0]["scope_id"]

    assert client.post(f"/api/v1/admin/users/{admin.user_id}/deactivate", headers=headers, json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/v1/admin/users/{admin.user_id}/scopes/{my_scope}/revoke", headers=headers, json={"reason": "x"}).status_code == 422

    other = make_user()
    other_scope = client.get(f"/api/v1/admin/users/{other.user_id}", headers=headers).get_json()["data"]["scopes"][0]["scope_id"]
    assert client.post(f"/api/v1/admin/users/{other.user_id}/scopes/{other_scope}/revoke", headers=headers, json={"reason": "x"}).status_code == 200
    # `other` no longer holds the role, so deactivating them is allowed
    assert client.post(f"/api/v1/admin/users/{other.user_id}/deactivate", headers=headers, json={"reason": "x"}).status_code == 200


def test_reset_password_gives_a_temporary_password_and_ends_sessions(client, make_user, login, run_sql):
    admin = make_user()
    target = make_user(roles=[("BRANCH_MANAGER", 1)])
    target_headers = login(target.email)
    run_sql("UPDATE users SET failed_login_attempts = 3, locked_until = now() + interval '10 minutes' WHERE user_id = :u", u=target.user_id)

    response = client.post(f"/api/v1/admin/users/{target.user_id}/reset-password", headers=login(admin.email))

    data = response.get_json()["data"]
    assert response.status_code == 200 and data["must_change_password"] is True and data["is_locked"] is False
    assert client.get("/api/v1/batches", headers=target_headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": target.email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": target.email, "password": data["temporary_password"]}).status_code == 200
    assert "temporary_password" not in str(_audit("PASSWORD_RESET").new_values)


def test_update_profile_fields_and_email_conflict(client, make_user, login):
    admin = make_user()
    other = make_user()
    target = make_user(roles=[("TRAINER", 1)])
    headers = login(admin.email)
    url = f"/api/v1/admin/users/{target.user_id}"

    ok = client.patch(url, headers=headers, json={"full_name": "Trainer Renamed", "phone": "9876543210"})
    assert ok.get_json()["data"]["full_name"] == "Trainer Renamed" and ok.get_json()["data"]["phone"] == "+919876543210"
    assert client.patch(url, headers=headers, json={"email": other.email}).status_code == 409
    assert client.patch(url, headers=headers, json={}).status_code == 400
    entry = _audit("USER_UPDATED")
    assert set(entry.new_values) == {"full_name", "phone"} and entry.old_values["phone"] is None


def test_students_are_not_reachable_through_the_staff_endpoints(client, make_user, login, make_student):
    admin = make_user()
    student = make_student()
    student_user = db.session.execute(select(User).where(User.student_id == student.student_id)).scalar_one()

    assert client.get(f"/api/v1/admin/users/{student_user.user_id}", headers=login(admin.email)).status_code == 404
    assert client.post(f"/api/v1/admin/users/{student_user.user_id}/reset-password", headers=login(admin.email)).status_code == 404

"""One role per account (db/118 split, db/119 constraint) and the Users & Access rule that follows from it."""
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from models import Role, SplitAccountHandout, User, UserRoleScope, UserSession

MIGRATION = (Path(__file__).resolve().parents[2] / "db" / "118_split_multi_role_accounts.sql").read_text()
SPLIT_BLOCK = MIGRATION[MIGRATION.index("DO $$"):]  # the data split, without the table and function (already in the test DB)


def _role_id(code: str) -> int:
    return db.session.execute(select(Role.role_id).where(Role.role_code == code)).scalar_one()


def _live(user_id: int) -> list[tuple[str, int | None]]:
    rows = db.session.execute(
        select(Role.role_code, UserRoleScope.branch_id).join(UserRoleScope, UserRoleScope.role_id == Role.role_id)
        .where(UserRoleScope.user_id == user_id, UserRoleScope.revoked_at.is_(None)).order_by(Role.role_code, UserRoleScope.branch_id)
    ).all()
    return [(code, branch) for code, branch in rows]


def _give(user_id: int, code: str, branch_id: int | None) -> None:
    db.session.add(UserRoleScope(user_id=user_id, role_id=_role_id(code), branch_id=branch_id))
    db.session.flush()


def _run_split() -> None:
    db.session.execute(db.text(SPLIT_BLOCK))
    db.session.expire_all()


@pytest.fixture
def legacy_multi_role(make_user):
    """Users with several roles, which only exist in data from before the constraint: the trigger is dropped for the test (DDL rolls back)."""
    db.session.execute(db.text("DROP TRIGGER trg_user_role_scopes_one_role ON user_role_scopes"))

    def _make(roles, **kwargs):
        user = make_user(roles=[roles[0]], **kwargs)
        for code, branch in roles[1:]:
            _give(user.user_id, code, branch)
        return user

    return _make


# ---------------------------------------------------------------- the split

def test_split_keeps_the_highest_role_and_moves_the_rest_to_new_accounts(legacy_multi_role):
    user = legacy_multi_role([("TRAINER", 1), ("BRANCH_MANAGER", 1)], email="Asha.Rao@nipuna.test", phone="9000000001")
    db.session.add(UserSession(session_id="s" * 64, user_id=user.user_id, expires_at=db.func.now() + db.text("interval '1 day'")))
    db.session.flush()

    _run_split()

    assert _live(user.user_id) == [("BRANCH_MANAGER", 1)]
    handout = db.session.execute(select(SplitAccountHandout).where(SplitAccountHandout.split_from_user_id == user.user_id)).scalar_one()
    new = db.session.get(User, handout.user_id)
    assert new.email == "Asha.Rao.trainer@nipuna.test" and new.password_hash is None and new.must_change_password is True
    assert new.phone == "9000000001" and _live(new.user_id) == [("TRAINER", 1)]
    assert handout.role_id == _role_id("TRAINER") and handout.branch_id == 1
    assert handout.invite_id is None and handout.handed_out_at is None
    assert db.session.get(UserSession, "s" * 64).revoked_at is not None


def test_split_orders_roles_and_keeps_a_managers_branches_together(legacy_multi_role):
    user = legacy_multi_role([("FOUNDER_CEO", None), ("SUPER_ADMIN", None), ("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)], email="boss@nipuna.test")

    _run_split()

    assert _live(user.user_id) == [("FOUNDER_CEO", None)]
    new = {db.session.get(Role, h.role_id).role_code: h for h in db.session.execute(select(SplitAccountHandout)).scalars()}
    assert set(new) == {"SUPER_ADMIN", "BRANCH_MANAGER"}
    assert db.session.get(User, new["SUPER_ADMIN"].user_id).email == "boss.superadmin@nipuna.test"
    manager = db.session.get(User, new["BRANCH_MANAGER"].user_id)
    assert manager.email == "boss.branchmanager@nipuna.test" and _live(manager.user_id) == [("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)]


def test_split_gives_each_extra_trainer_branch_its_own_account_and_avoids_taken_emails(legacy_multi_role, make_user):
    make_user(roles=[("TRAINER", 1)], email="kiran.trainer@nipuna.test")  # the obvious name is taken
    user = legacy_multi_role([("TRAINER", 1), ("TRAINER", 2)], email="kiran@nipuna.test")

    _run_split()

    handout = db.session.execute(select(SplitAccountHandout).where(SplitAccountHandout.split_from_user_id == user.user_id)).scalar_one()
    assert db.session.get(User, handout.user_id).email == "kiran.trainer2@nipuna.test"
    assert _live(user.user_id) == [("TRAINER", 1)] and _live(handout.user_id) == [("TRAINER", 2)]


def test_split_leaves_single_role_users_and_multi_branch_managers_alone(make_user):
    trainer = make_user(roles=[("TRAINER", 1)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)])

    _run_split()

    assert _live(trainer.user_id) == [("TRAINER", 1)] and _live(manager.user_id) == [("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)]
    assert db.session.execute(select(SplitAccountHandout)).first() is None


# ---------------------------------------------------------------- the constraint

def test_the_database_refuses_a_second_live_role(make_user):
    user = make_user(roles=[("TRAINER", 1)])
    with pytest.raises(DBAPIError):
        _give(user.user_id, "BRANCH_MANAGER", 1)
    db.session.rollback()


def test_the_database_refuses_a_second_trainer_branch_but_allows_several_manager_branches(make_user):
    trainer = make_user(roles=[("TRAINER", 1)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    with pytest.raises(DBAPIError):
        _give(trainer.user_id, "TRAINER", 2)
    db.session.rollback()
    _give(manager.user_id, "BRANCH_MANAGER", 2)
    assert _live(manager.user_id) == [("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)]


def test_a_revoked_role_does_not_block_a_new_one(make_user):
    user = make_user(roles=[("TRAINER", 1)])
    db.session.execute(db.text("UPDATE user_role_scopes SET revoked_at = now() WHERE user_id = :u"), {"u": user.user_id})
    _give(user.user_id, "BRANCH_MANAGER", 1)
    assert _live(user.user_id) == [("BRANCH_MANAGER", 1)]


# ---------------------------------------------------------------- Users & Access

def test_create_user_rejects_two_roles_but_allows_several_branches_for_a_manager(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    base = {"full_name": "Two Roles", "email": "two@nipuna.test"}

    two_roles = client.post("/api/v1/admin/users", headers=headers, json={**base, "scopes": [
        {"role_code": "TRAINER", "branch_id": 1}, {"role_code": "BRANCH_MANAGER", "branch_id": 1}]})
    two_trainer_branches = client.post("/api/v1/admin/users", headers=headers, json={**base, "scopes": [
        {"role_code": "TRAINER", "branch_id": 1}, {"role_code": "TRAINER", "branch_id": 2}]})
    managers = client.post("/api/v1/admin/users", headers=headers, json={**base, "scopes": [
        {"role_code": "BRANCH_MANAGER", "branch_id": 1}, {"role_code": "BRANCH_MANAGER", "branch_id": 2}]})

    assert two_roles.status_code == 422 and two_trainer_branches.status_code == 422
    assert managers.status_code == 201 and len(managers.get_json()["data"]["scopes"]) == 2


def test_grant_scope_only_adds_a_branch_to_a_branch_manager(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    trainer = make_user(roles=[("TRAINER", 1)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])

    second_role = client.post(f"/api/v1/admin/users/{trainer.user_id}/scopes", headers=headers, json={"role_code": "BRANCH_MANAGER", "branch_id": 1})
    second_branch = client.post(f"/api/v1/admin/users/{trainer.user_id}/scopes", headers=headers, json={"role_code": "TRAINER", "branch_id": 2})
    manager_role = client.post(f"/api/v1/admin/users/{manager.user_id}/scopes", headers=headers, json={"role_code": "TRAINER", "branch_id": 1})
    manager_branch = client.post(f"/api/v1/admin/users/{manager.user_id}/scopes", headers=headers, json={"role_code": "BRANCH_MANAGER", "branch_id": 2})

    assert (second_role.status_code, second_branch.status_code, manager_role.status_code) == (422, 422, 422)
    assert manager_branch.status_code == 201 and _live(manager.user_id) == [("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)]


# ---------------------------------------------------------------- hand-out

def _handout(make_user, role="TRAINER"):
    source = make_user(roles=[("BRANCH_MANAGER", 1)])
    account = make_user(roles=[(role, 1)], password="Temp-Passw0rd-xyz", email="split.trainer@nipuna.test")
    db.session.execute(db.text("UPDATE users SET password_hash = NULL, must_change_password = TRUE WHERE user_id = :u"), {"u": account.user_id})
    handout = SplitAccountHandout(user_id=account.user_id, split_from_user_id=source.user_id, role_id=_role_id(role), branch_id=1)
    db.session.add(handout)
    db.session.flush()
    db.session.commit()
    return handout.handout_id, account


def test_handout_list_link_and_mark_for_super_admin_and_founder(client, make_user, login):
    handout_id, account = _handout(make_user)
    admin, founder = make_user(), make_user(roles=[("FOUNDER_CEO", None)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    assert client.get("/api/v1/admin/users/handouts", headers=login(manager.email)).status_code == 403

    for who in (admin, founder):
        rows = client.get("/api/v1/admin/users/handouts", headers=login(who.email)).get_json()["data"]
        assert [r["email"] for r in rows if r["handout_id"] == handout_id] == ["split.trainer@nipuna.test"]
    first = next(r for r in rows if r["handout_id"] == handout_id)
    assert first["link_status"] == "none" and first["role_code"] == "TRAINER" and first["handed_out_at"] is None

    headers = login(founder.email)
    issued = client.post(f"/api/v1/admin/users/handouts/{handout_id}/link", headers=headers).get_json()["data"]
    assert issued["invite_path"].startswith("/activate?token=") and issued["link_status"] == "valid"
    token = issued["invite_path"].split("=", 1)[1]
    listed = client.get("/api/v1/admin/users/handouts", headers=headers).get_json()["data"]
    assert "invite_path" not in next(r for r in listed if r["handout_id"] == handout_id)

    reissued = client.post(f"/api/v1/admin/users/handouts/{handout_id}/link", headers=headers).get_json()["data"]
    assert reissued["invite_path"].split("=", 1)[1] != token  # the earlier link is replaced
    assert client.post("/api/v1/auth/activate", json={"token": token, "password": "Brand-New-Passw0rd!"}).status_code in (400, 409, 422)

    marked = client.post(f"/api/v1/admin/users/handouts/{handout_id}/handed-out", headers=headers)
    assert marked.status_code == 200 and marked.get_json()["data"]["handed_out_at"] is not None
    assert client.post(f"/api/v1/admin/users/handouts/{handout_id}/handed-out", headers=headers).status_code == 422

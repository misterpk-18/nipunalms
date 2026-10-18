"""Role separation R3: the session carries one role (and a Branch Manager's branch), and every endpoint is authorised against it.

Each role reaches only its own workspace; a person with two accounts cannot reach one account's data from the other; a Branch Manager
sees one branch (the one picked at sign-in); Super Admin and Founder read across branches and decide, but do not run a branch.
"""
from datetime import timedelta

import pytest

from config.timezone import today_ist
from tests.conftest import PASSWORD

API = "/api/v1"


def sign_in(client, user, **extra):
    return client.post(f"{API}/auth/login", json={"login": user.email, "password": PASSWORD, **extra})


def headers_of(response):
    return {"Authorization": f"Bearer {response.get_json()['data']['token']}"}


@pytest.fixture
def people(make_user):
    return {
        "student_user": None,
        "trainer": make_user(roles=[("TRAINER", 1)], full_name="Trainer One"),
        "bm1": make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM Guntur"),
        "bm2": make_user(roles=[("BRANCH_MANAGER", 2)], full_name="BM Vijayawada"),
        "bm_both": make_user(roles=[("BRANCH_MANAGER", 1), ("BRANCH_MANAGER", 2)], full_name="BM Both"),
        "admin": make_user(roles=[("SUPER_ADMIN", None)], full_name="Super Admin"),
        "founder": make_user(roles=[("FOUNDER_CEO", None)], full_name="Founder"),
    }


@pytest.fixture
def h(client, people):
    """Authorization headers by role key (the two-branch Branch Manager picks branch 1)."""
    out = {key: headers_of(sign_in(client, user)) for key, user in people.items() if user is not None and key != "bm_both"}
    return out


@pytest.fixture
def batches(make_batch, people):
    return {
        "g": make_batch(1, trainers=[people["trainer"]], state="Running"),
        "v": make_batch(2, state="Running"),
    }


# ---------------------------------------------------------------- the session carries the role

def test_the_session_stores_the_role_and_the_branch(client, people, run_sql):
    sign_in(client, people["bm1"])
    sign_in(client, people["admin"])

    rows = run_sql("SELECT user_id, role_code, branch_id FROM user_sessions ORDER BY created_at").all()

    assert [(r.user_id, r.role_code, r.branch_id) for r in rows] == [
        (people["bm1"].user_id, "BRANCH_MANAGER", 1), (people["admin"].user_id, "SUPER_ADMIN", None)]


def test_a_session_whose_role_was_taken_away_is_signed_out(client, people, run_sql):
    headers = headers_of(sign_in(client, people["bm1"]))
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200

    run_sql("UPDATE user_role_scopes SET revoked_at = now() WHERE user_id = :u", u=people["bm1"].user_id)

    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


# ---------------------------------------------------------------- Branch Manager with several branches

def test_a_branch_manager_with_two_branches_signs_in_then_picks_one(client, people, batches):
    response = sign_in(client, people["bm_both"])
    data = response.get_json()["data"]
    headers = headers_of(response)

    assert response.status_code == 200
    assert data["needs_branch"] is True and data["branch"] is None and data["workspace"] == "branch" and data["home_route"] == "/branch"
    assert [b["branch_id"] for b in data["branches"]] == [1, 2]
    # nothing else works until a branch is picked
    refused = client.get(f"{API}/batches", headers=headers)
    assert refused.status_code == 403 and refused.get_json()["error"]["code"] == "BRANCH_REQUIRED"
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200

    # a branch that is not on the account is refused and nothing changes
    assert client.post(f"{API}/auth/branch", json={"branch_id": 999}, headers=headers).status_code == 403
    assert client.get(f"{API}/batches", headers=headers).status_code == 403

    picked = client.post(f"{API}/auth/branch", json={"branch_id": 2}, headers=headers)
    me = picked.get_json()["data"]
    assert picked.status_code == 200 and me["needs_branch"] is False and me["branch"]["branch_id"] == 2
    assert [b["branch_id"] for b in me["allowed_branches"]] == [2] and [s["branch_id"] for s in me["scopes"]] == [2]
    assert client.get(f"{API}/auth/me", headers=headers).get_json()["data"]["branch"]["branch_id"] == 2

    # one pick per session
    again = client.post(f"{API}/auth/branch", json={"branch_id": 1}, headers=headers)
    assert again.status_code == 422


def test_a_branch_manager_who_picked_one_branch_sees_only_that_branch(client, people, batches):
    headers = headers_of(sign_in(client, people["bm_both"], branch_id=1))

    listed = client.get(f"{API}/batches", headers=headers).get_json()["data"]

    assert {b["batch_id"] for b in listed} == {batches["g"].batch_id}
    assert client.get(f"{API}/batches/{batches['g'].batch_id}", headers=headers).status_code == 200
    assert client.get(f"{API}/batches/{batches['v'].batch_id}", headers=headers).status_code == 404  # his other branch: not this session
    assert client.get(f"{API}/auth/me", headers=headers).get_json()["data"]["branch"]["branch_id"] == 1


def test_the_same_manager_signing_in_again_can_pick_the_other_branch(client, people, batches):
    first = headers_of(sign_in(client, people["bm_both"], branch_id=1))
    second = headers_of(sign_in(client, people["bm_both"], branch_id=2))

    assert {b["batch_id"] for b in client.get(f"{API}/batches", headers=first).get_json()["data"]} == {batches["g"].batch_id}
    assert {b["batch_id"] for b in client.get(f"{API}/batches", headers=second).get_json()["data"]} == {batches["v"].batch_id}


def test_signing_in_with_a_branch_outside_the_account_is_refused_and_starts_no_session(client, people, run_sql):
    response = sign_in(client, people["bm1"], branch_id=2)  # holds Guntur only

    assert response.status_code == 403
    assert run_sql("SELECT count(*) FROM user_sessions WHERE user_id = :u", u=people["bm1"].user_id).scalar_one() == 0


def test_a_manager_with_one_branch_gets_it_without_picking(client, people):
    data = sign_in(client, people["bm2"]).get_json()["data"]

    assert data["needs_branch"] is False and data["branch"]["branch_id"] == 2 and data["branches"] == []


def test_change_branch_ends_the_session(client, people):
    headers = headers_of(sign_in(client, people["bm_both"], branch_id=1))

    assert client.post(f"{API}/auth/change-branch", headers=headers).status_code == 204
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_only_a_branch_manager_picks_or_changes_branch(client, h):
    assert client.post(f"{API}/auth/branch", json={"branch_id": 1}, headers=h["trainer"]).status_code == 403
    assert client.post(f"{API}/auth/change-branch", headers=h["admin"]).status_code == 403


# ---------------------------------------------------------------- one workspace per role

WORKSPACE_PROBES = {  # a read that belongs to one workspace only
    "trainer": "/trainer/today",
    "admin": "/admin/needs-action",
    "branch": "/branch/my-work",
}


def test_each_role_reaches_only_its_own_workspace(client, people, h, make_student):
    student = make_student()
    student_headers = headers_of(client.post(f"{API}/auth/login", json={"login": student.student_code, "password": PASSWORD}))
    probes = {
        "student": ("/me/home", student_headers),
        "trainer": (WORKSPACE_PROBES["trainer"], h["trainer"]),
        "bm1": (WORKSPACE_PROBES["branch"], h["bm1"]),
        "admin": (WORKSPACE_PROBES["admin"], h["admin"]),
        "founder": ("/founder/inbox", h["founder"]),
    }
    for role, (path, headers) in probes.items():
        assert client.get(f"{API}{path}", headers=headers).status_code == 200, role

    def code(path, headers):
        return client.get(f"{API}{path}", headers=headers).status_code

    # nobody reaches a workspace that is not their role's
    assert code("/trainer/today", h["bm1"]) == 403 and code("/trainer/today", h["admin"]) == 403 and code("/trainer/today", student_headers) == 403
    assert code("/admin/needs-action", h["trainer"]) == 403 and code("/admin/needs-action", h["bm1"]) == 403
    assert code("/admin/needs-action", student_headers) == 403
    assert code("/me/home", h["trainer"]) == 403 and code("/me/home", h["bm1"]) == 403 and code("/me/home", h["admin"]) == 403
    assert code("/branch/my-work", h["trainer"]) == 403 and code("/branch/my-work", student_headers) == 403
    # Super Admin and Founder have no branch workspace of their own (no implicit workspaces): their home is theirs
    assert code("/branch/my-work", h["admin"]) == 403 and code("/branch/my-work", h["founder"]) == 403
    assert code("/trainer/today", h["founder"]) == 403 and code("/me/home", h["founder"]) == 403

    # one workspace and one home route each
    me = lambda headers: client.get(f"{API}/auth/me", headers=headers).get_json()["data"]  # noqa: E731
    assert [me(h[k])["workspaces"] for k in ("trainer", "bm1", "admin", "founder")] == [["trainer"], ["branch"], ["admin"], ["founder"]]
    assert [me(h[k])["home_route"] for k in ("trainer", "bm1", "admin", "founder")] == ["/trainer", "/branch", "/admin", "/founder"]


def test_a_person_with_two_accounts_cannot_reach_one_accounts_data_from_the_other(client, make_user, make_batch, batches):
    """Role separation splits a Branch Manager who also trains into two accounts; each opens only its own work."""
    manager = make_user(roles=[("BRANCH_MANAGER", 1)], email="asha.bm@nipuna.test", full_name="Asha")
    teacher = make_user(roles=[("TRAINER", 1)], email="asha.trainer@nipuna.test", full_name="Asha (trainer)")
    own = make_batch(1, trainers=[teacher], state="Running")
    as_manager = headers_of(sign_in(client, manager))
    as_trainer = headers_of(sign_in(client, teacher))

    # the trainer account has no manager powers, even though the same person manages the branch with the other one
    assert client.get(f"{API}/branch/my-work", headers=as_trainer).status_code == 403
    assert client.post(f"{API}/batches/{own.batch_id}/state", json={"state": "On Hold", "reason": "x"}, headers=as_trainer).status_code == 403
    assert client.get(f"{API}/trainer/batches", headers=as_trainer).status_code == 200
    # the manager account teaches nothing and has no trainer workspace
    assert client.get(f"{API}/trainer/batches", headers=as_manager).status_code == 403
    assert client.get(f"{API}/trainer/today", headers=as_manager).status_code == 403
    # each sees the batch through its own role only: the manager through the branch, the trainer through teaching it
    assert client.get(f"{API}/batches/{own.batch_id}", headers=as_manager).status_code == 200
    assert client.get(f"{API}/batches/{own.batch_id}", headers=as_trainer).status_code == 200
    other = batches["g"]  # Guntur batch the trainer does not teach
    assert client.get(f"{API}/batches/{other.batch_id}", headers=as_trainer).status_code == 404
    assert client.get(f"{API}/batches/{other.batch_id}", headers=as_manager).status_code == 200


# ---------------------------------------------------------------- Branch Manager, one branch

def test_a_branch_manager_cannot_see_or_change_another_branch(client, h, batches):
    gnt, vij = batches["g"], batches["v"]

    assert {b["batch_id"] for b in client.get(f"{API}/batches", headers=h["bm1"]).get_json()["data"]} == {gnt.batch_id}
    assert client.get(f"{API}/batches/{vij.batch_id}", headers=h["bm1"]).status_code == 404
    assert client.post(f"{API}/batches/{vij.batch_id}/state", json={"state": "On Hold", "reason": "x"}, headers=h["bm1"]).status_code == 404
    assert client.get(f"{API}/academic/reports?branch_id=2", headers=h["bm1"]).status_code == 404
    assert client.get(f"{API}/batches/{gnt.batch_id}", headers=h["bm2"]).status_code == 404


# ---------------------------------------------------------------- Super Admin and Founder: read across branches, no branch actions

@pytest.mark.parametrize("who", ["admin", "founder"])
def test_super_admin_and_founder_read_across_branches_with_a_branch_filter(client, h, batches, who):
    gnt, vij = batches["g"], batches["v"]

    everything = client.get(f"{API}/batches", headers=h[who]).get_json()["data"]
    assert {b["batch_id"] for b in everything} >= {gnt.batch_id, vij.batch_id}
    only_vij = client.get(f"{API}/batches?branch_id=2", headers=h[who]).get_json()["data"]
    assert {b["batch_id"] for b in only_vij} == {vij.batch_id}
    assert client.get(f"{API}/batches/{vij.batch_id}", headers=h[who]).status_code == 200
    for path in ("/admin/students", "/attendance/sessions", "/progress/students", "/enrolments", "/support-requests", "/academic/reports",
                 "/academic/reports?branch_id=2", "/issues", "/finance-summaries"):
        assert client.get(f"{API}{path}", headers=h[who]).status_code == 200, path


@pytest.mark.parametrize("who", ["admin", "founder"])
def test_super_admin_and_founder_have_no_branch_day_to_day_actions(client, h, batches, people, who):
    gnt = batches["g"]
    attempts = [
        ("post", "/batches", {"course_id": 1, "branch_id": 1, "capacity": 10}),
        ("patch", f"/batches/{gnt.batch_id}", {"display_name": "x"}),
        ("post", f"/batches/{gnt.batch_id}/state", {"state": "On Hold", "reason": "x"}),
        ("post", f"/batches/{gnt.batch_id}/confirm", {}),
        ("post", f"/batches/{gnt.batch_id}/allocations", {"enrolment_ids": [1]}),
        ("post", "/enrolments/1/deallocate", {"reason": "x"}),
        ("post", "/class-sessions", {"batch_id": gnt.batch_id}),
        ("post", "/results/publish", {}),
        ("post", "/content-items/1/review", {"decision": "Approved"}),
        ("post", "/recordings/1/release", {}),
        ("post", "/certificates/1/issue", {}),
        ("post", "/completion-reviews/1/decision", {"decision": "Approved"}),
        ("put", "/attendance/sessions/1", {"entries": []}),
        ("post", "/attendance/recoveries/1/decision", {"decision": "Approved"}),
        ("get", "/branch/my-work", None),
    ]
    for method, path, body in attempts:
        response = getattr(client, method)(f"{API}{path}", headers=h[who], **({"json": body} if body is not None else {}))
        assert response.status_code == 403, (who, method, path, response.status_code)


# ---------------------------------------------------------------- Founder has everything Super Admin has

def test_the_founder_can_do_what_the_super_admin_can(client, h, people, make_user, run_sql):
    locked = make_user(roles=[("TRAINER", 1)], full_name="Locked Trainer")
    run_sql("UPDATE users SET locked_until = now() + interval '1 hour' WHERE user_id = :u", u=locked.user_id)

    for who in ("admin", "founder"):
        assert client.get(f"{API}/admin/users", headers=h[who]).status_code == 200
        assert client.get(f"{API}/admin/needs-action", headers=h[who]).status_code == 200
        assert client.get(f"{API}/admin/setup", headers=h[who]).status_code == 200
        assert client.get(f"{API}/founder/inbox", headers=h[who]).status_code == 200
        assert client.get(f"{API}/admin/crm-sync/summary", headers=h[who]).status_code == 200
        assert client.get(f"{API}/ai-controls/status", headers=h[who]).status_code == 200
        assert client.get(f"{API}/audit-log", headers=h[who]).status_code == 200
    # a write that used to be Super Admin only (after fresh auth: signing in counts)
    unlocked = client.post(f"{API}/admin/users/{locked.user_id}/unlock", json={"reason": "Cleared"}, headers=h["founder"])
    assert unlocked.status_code in (200, 204), unlocked.get_json()
    # the roles that are not company-wide cannot
    assert client.get(f"{API}/admin/users", headers=h["bm1"]).status_code == 403
    assert client.get(f"{API}/founder/inbox", headers=h["trainer"]).status_code == 403


def test_the_founder_adds_a_company_holiday_and_decides_branch_closures_like_the_super_admin(client, h):
    start = today_ist() + timedelta(days=40)
    body = {"kind": "Company Holiday", "branch_id": None, "starts_on": start.isoformat(), "ends_on": start.isoformat(), "reason": "Annual"}
    for who in ("admin", "founder"):
        added = client.post(f"{API}/calendar/closures", json={**body, "title": f"Company day {who}"}, headers=h[who])
        assert added.status_code == 201, (who, added.get_json())
    # a branch closure proposed by a Branch Manager waits; either of them decides it, the Branch Manager cannot (decision 18)
    proposal = {**body, "kind": "Branch Closure", "branch_id": 1, "title": "Flooding"}
    proposed = client.post(f"{API}/calendar/closures", json=proposal, headers=h["bm1"])
    assert proposed.status_code == 201 and proposed.get_json()["data"]["status"] == "Pending"
    closure_id = proposed.get_json()["data"]["closure_id"]
    assert client.post(f"{API}/calendar/closures/{closure_id}/decision", json={"decision": "Approved"}, headers=h["bm1"]).status_code == 403
    assert client.post(f"{API}/calendar/closures/{closure_id}/decision", json={"decision": "Approved"}, headers=h["founder"]).status_code == 200
    assert client.post(f"{API}/calendar/closures", json={**proposal, "branch_id": 2}, headers=h["bm1"]).status_code == 404  # another branch


# ---------------------------------------------------------------- navigation counts and Getting started follow the session

def test_nav_counts_and_getting_started_read_the_role_from_the_session(client, h, make_student):
    student = make_student()
    student_headers = headers_of(client.post(f"{API}/auth/login", json={"login": student.student_code, "password": PASSWORD}))
    expected = {"student": "student", "trainer": "trainer", "bm1": "branch", "admin": "admin", "founder": "founder"}
    heads = {**h, "student": student_headers}
    for key, workspace in expected.items():
        plain = client.get(f"{API}/me/getting-started", headers=heads[key])
        assert plain.status_code == 200 and plain.get_json()["data"]["workspace"] == workspace, key
        # the old query parameter is accepted and ignored, even when it names another workspace
        ignored = client.get(f"{API}/me/getting-started?workspace=admin", headers=heads[key])
        assert ignored.get_json()["data"]["workspace"] == workspace, key
        assert client.get(f"{API}/me/nav-counts", headers=heads[key]).status_code == 200, key
        assert client.get(f"{API}/me/nav-counts?workspace=founder&branch_id=2", headers=heads[key]).status_code == 200, key

    founder_counts = client.get(f"{API}/me/nav-counts", headers=h["founder"]).get_json()["data"]
    assert {"inbox", "curriculum", "certificates", "access", "home", "crm_sync", "issues", "users"} <= set(founder_counts)
    steps = client.get(f"{API}/me/getting-started", headers=h["founder"]).get_json()["data"]["steps"]
    assert [s["key"] for s in steps] == ["staff", "setup"] and all(s["to"].startswith("/founder/") for s in steps)
    assert client.get(f"{API}/notifications/overview", headers=h["founder"]).status_code == 200

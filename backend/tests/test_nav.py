"""The shell's reads: navigation count badges, the Getting started steps and the Ctrl/Cmd+K record search."""
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1"


def counts(client, world, person, workspace, expect=200, extra=""):
    response = client.get(f"{API}/me/nav-counts?workspace={workspace}{extra}", headers=world.h(person))
    assert response.status_code == expect, response.get_json()
    return response.get_json().get("data")


def steps(client, world, person, workspace):
    response = client.get(f"{API}/me/getting-started?workspace={workspace}", headers=world.h(person))
    assert response.status_code == 200, response.get_json()
    return {s["key"]: s["done"] for s in response.get_json()["data"]["steps"]}


def found(client, world, person, text):
    response = client.get(f"{API}/search", query_string={"q": text}, headers=world.h(person))
    assert response.status_code == 200, response.get_json()
    return {(r["kind"], r["title"]) for r in response.get_json()["data"]}


# ---------------------------------------------------------------- nav counts

def test_each_role_gets_the_counts_of_its_own_workspace(client, world):
    assert set(counts(client, world, world.students.s1, "student")) == {"tasks", "support"}
    assert set(counts(client, world, world.people.t1, "trainer")) == {"to_grade", "support", "attendance", "class_logs"}
    assert {"waiting", "requests", "issues", "support", "attendance"} <= set(counts(client, world, world.people.bm, "branch"))
    assert set(counts(client, world, world.people.admin, "admin")) == {"crm_sync", "issues", "users"}
    assert set(counts(client, world, world.people.founder, "founder")) == {"inbox", "curriculum", "certificates", "access"}


def test_a_workspace_the_user_does_not_hold_is_refused(client, world):
    counts(client, world, world.students.s1, "trainer", expect=403)
    counts(client, world, world.people.t1, "branch", expect=403)
    counts(client, world, world.people.bm, "admin", expect=403)
    assert client.get(f"{API}/me/nav-counts?workspace=nonsense", headers=world.h(world.people.bm)).status_code == 400
    assert client.get(f"{API}/me/nav-counts", headers=world.h(world.people.bm)).status_code == 400


def test_branch_counts_follow_the_branch_and_its_scope(client, world):
    assert counts(client, world, world.people.bm, "branch")["support"] == 0
    # the second branch holds student three, waiting for a batch; the first branch's manager does not see it
    assert counts(client, world, world.people.bm_vij, "branch")["waiting"] >= counts(client, world, world.people.bm, "branch")["waiting"]
    counts(client, world, world.people.bm, "branch", expect=404, extra="&branch_id=2")
    assert counts(client, world, world.people.admin, "branch", extra="&branch_id=2")["waiting"] == counts(client, world, world.people.bm_vij, "branch")["waiting"]


def test_support_due_soon_counts_for_the_branch_manager(client, world, run_sql):
    reply = client.post(f"{API}/support-requests", json={"category": "LMS", "subject": "Cannot open the recording", "details": "It never loads"},
                        headers=world.h(world.students.s1))
    assert reply.status_code == 201, reply.get_json()
    run_sql("UPDATE support_requests SET sla_due_at = now() + interval '1 day'")
    assert counts(client, world, world.people.bm, "branch")["support"] == 0
    run_sql("UPDATE support_requests SET sla_due_at = now() - interval '1 hour'")
    assert counts(client, world, world.people.bm, "branch")["support"] == 1
    assert counts(client, world, world.people.bm_vij, "branch")["support"] == 0


# ---------------------------------------------------------------- getting started

def test_getting_started_ticks_itself(client, world, run_sql):
    s1 = steps(client, world, world.students.s1, "student")
    assert s1 == {"activate": True, "batch": True, "class": False, "task": False}
    assert steps(client, world, world.students.s3, "student")["batch"] is False

    assert steps(client, world, world.people.t1, "trainer")["class"] is True  # the seeded delivered class is theirs
    assert steps(client, world, world.people.t2, "trainer")["class"] is False

    branch = steps(client, world, world.people.bm, "branch")
    assert branch["batch"] is True and branch["allocate"] is True and branch["classes"] is True
    assert steps(client, world, world.people.bm_vij, "branch") == {"batch": False, "allocate": False, "classes": False}

    assert set(steps(client, world, world.people.admin, "admin")) == {"staff", "setup"}
    assert steps(client, world, world.people.founder, "founder") == {}
    assert client.get(f"{API}/me/getting-started?workspace=trainer", headers=world.h(world.students.s1)).status_code == 403


# ---------------------------------------------------------------- search

def test_search_returns_only_records_the_user_may_open(client, world):
    # the Branch Manager of Guntur: their students and batches, not Vijayawada's student
    guntur = found(client, world, world.people.bm, "Student")
    assert ("student", "Student One") in guntur and ("student", "Student Two") in guntur and ("student", "Student Three") not in guntur
    assert ("student", "Student Three") in found(client, world, world.people.bm_vij, "Student Three")
    assert ("student", "Student Three") in found(client, world, world.people.admin, "Student Three")


def test_a_trainer_finds_only_students_and_batches_they_teach(client, world):
    assert found(client, world, world.people.t1, "Student") == {("student", "Student One")}
    batches = {title for kind, title in found(client, world, world.people.t1, "NIT") if kind == "batch"}
    assert len(batches) == 1


def test_students_get_no_record_search_and_short_text_finds_nothing(client, world):
    assert found(client, world, world.students.s1, "Student") == set()
    assert found(client, world, world.people.admin, "S") == set()
    assert found(client, world, world.people.admin, "%") == set()  # a wildcard is text, not a pattern
    assert client.get(f"{API}/search?q=Student").status_code == 401

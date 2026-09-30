"""Record scope: what each role sees, through the helpers and through the read endpoints. Outside scope is a 404."""
from datetime import datetime

import pytest

from config.database import db
from config.timezone import IST
from services import scope
from tests import helpers
from services.context import CurrentUser, Scope
from services.errors import NotFound
from repositories import batches as batches_repo
from repositories import students as students_repo


@pytest.fixture
def world(make_user, make_student, make_batch, make_session, allocate):
    """Guntur: batches G1 (trainer g1) and G2 (trainer g2), students s1 in G1, s2 in G2.
    Vijayawada: batch V1 (trainer v1), student s3 in V1 (plus a Guntur-serviced course, not allocated)."""
    people = {
        "g1": make_user(roles=[("TRAINER", 1)], full_name="Trainer G1"),
        "g2": make_user(roles=[("TRAINER", 1)], full_name="Trainer G2"),
        "v1": make_user(roles=[("TRAINER", 2)], full_name="Trainer V1"),
        "ac_gnt": make_user(roles=[("ACADEMIC_COORDINATOR", 1)]),
        "ac_vij": make_user(roles=[("ACADEMIC_COORDINATOR", 2)]),
        "bm_gnt": make_user(roles=[("BRANCH_MANAGER", 1)]),
        "admin": make_user(roles=[("SUPER_ADMIN", None)]),
        "founder": make_user(roles=[("FOUNDER_CEO", None)]),
    }
    batches = {
        "G1": make_batch(1, trainers=[people["g1"]], state="Running"),
        "G2": make_batch(1, trainers=[people["g2"]], state="Running"),
        "V1": make_batch(2, trainers=[people["v1"]], state="Running"),
    }
    students = {
        "s1": make_student(),
        "s2": make_student(),
        "s3": make_student(service="NIT-VIJ", collecting="NIT-GNT", admission_id="A-VIJ"),
    }
    allocate(students["s1"], batches["G1"])
    allocate(students["s2"], batches["G2"])
    allocate(students["s3"], batches["V1"])
    for name, batch in batches.items():
        make_session(batch, people["g1" if name == "G1" else "g2" if name == "G2" else "v1"],
                     datetime(2026, 10, 1, 10, 0, tzinfo=IST), title=f"{name} session")
    return people, batches, students


def as_user(user_id, roles, student_id=None):
    """A CurrentUser for calling the scope helpers directly."""
    scopes = tuple(Scope(i, role, role, branch, branch is None) for i, (role, branch) in enumerate(roles, 1))
    return CurrentUser(user_id=user_id, email=None, full_name="Test", student_id=student_id, session_id="s",
                       must_change_password=False, has_fresh_auth=True, scopes=scopes)


def codes(response):
    return sorted(b["batch_code"] for b in response.get_json()["data"])


# ---------------------------------------------------------------- helpers

def test_visible_branch_ids_per_role():
    assert scope.visible_branch_ids(as_user(1, [("SUPER_ADMIN", None)])) is None
    assert scope.visible_branch_ids(as_user(1, [("FOUNDER_CEO", None)])) is None
    assert scope.visible_branch_ids(as_user(1, [("ACADEMIC_COORDINATOR", 1)])) == {1}
    assert scope.visible_branch_ids(as_user(1, [("BRANCH_MANAGER", 1), ("ACADEMIC_COORDINATOR", 2)])) == {1, 2}
    assert scope.visible_branch_ids(as_user(1, [("TRAINER", 1)])) == set()
    assert scope.visible_branch_ids(as_user(1, [("STUDENT", 1)], student_id=5)) == set()


def test_require_branch_is_a_404_outside_the_users_branches():
    scope.require_branch(1, as_user(1, [("ACADEMIC_COORDINATOR", 1)]))
    scope.require_branch(2, as_user(1, [("SUPER_ADMIN", None)]))
    with pytest.raises(NotFound):
        scope.require_branch(2, as_user(1, [("ACADEMIC_COORDINATOR", 1)]))
    with pytest.raises(NotFound):
        scope.require_branch(1, as_user(1, [("TRAINER", 1)]))


def test_trainer_batch_ids_only_lists_assigned_batches(world):
    people, batches, _ = world

    g1 = as_user(people["g1"].user_id, [("TRAINER", 1)])

    assert scope.trainer_batch_ids(g1) == {batches["G1"].batch_id}
    assert scope.trainer_batch_ids(as_user(people["ac_gnt"].user_id, [("ACADEMIC_COORDINATOR", 1)])) == set()


def test_ended_trainer_assignment_no_longer_counts(world, run_sql):
    people, batches, _ = world
    run_sql("UPDATE batch_trainers SET to_date = CURRENT_DATE - 1, from_date = CURRENT_DATE - 30 WHERE batch_id = :b",
            b=batches["G1"].batch_id)

    assert scope.trainer_batch_ids(as_user(people["g1"].user_id, [("TRAINER", 1)])) == set()


def test_student_enrolment_ids_are_only_the_students_own(world):
    _, _, students = world
    user = as_user(1, [("STUDENT", 1)], student_id=students["s1"].student_id)

    own = scope.student_enrolment_ids(user)

    assert own == {e["enrolment_id"] for e in students["s1"].enrolments}
    assert scope.student_batch_ids(user) == {world[1]["G1"].batch_id}
    assert scope.student_enrolment_ids(as_user(1, [("TRAINER", 1)])) == set()


def test_assert_can_view_batch_and_enrolment(world):
    people, batches, students = world
    ac_gnt = as_user(1, [("ACADEMIC_COORDINATOR", 1)])
    trainer = as_user(people["g1"].user_id, [("TRAINER", 1)])
    student = as_user(2, [("STUDENT", 1)], student_id=students["s1"].student_id)
    enrolment = {name: students_repo.get_enrolment(s.enrolments[0]["enrolment_id"]) for name, s in students.items()}

    scope.assert_can_view_batch(batches["G2"], ac_gnt)
    scope.assert_can_view_batch(batches["G1"], trainer)
    scope.assert_can_view_batch(batches["G1"], student)
    for viewer, batch in ((ac_gnt, "V1"), (trainer, "G2"), (student, "G2")):
        with pytest.raises(NotFound):
            scope.assert_can_view_batch(batches[batch], viewer)

    scope.assert_can_view_enrolment(enrolment["s2"], ac_gnt)
    scope.assert_can_view_enrolment(enrolment["s1"], trainer)
    scope.assert_can_view_enrolment(enrolment["s1"], student)
    for viewer, name in ((ac_gnt, "s3"), (trainer, "s2"), (student, "s2")):
        with pytest.raises(NotFound):
            scope.assert_can_view_enrolment(enrolment[name], viewer)


# ---------------------------------------------------------------- batches

def test_trainer_sees_only_assigned_batches(world, client, login):
    people, batches, _ = world
    headers = login(people["g1"].email)

    assert codes(client.get("/api/v1/batches", headers=headers)) == [batches["G1"].batch_code]
    assert client.get(f"/api/v1/batches/{batches['G1'].batch_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/batches/{batches['G2'].batch_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/batches/{batches['V1'].batch_id}", headers=headers).status_code == 404


def test_coordinator_sees_only_their_branch(world, client, login):
    people, batches, _ = world
    gnt, vij = login(people["ac_gnt"].email), login(people["ac_vij"].email)

    assert codes(client.get("/api/v1/batches", headers=gnt)) == sorted([batches["G1"].batch_code, batches["G2"].batch_code])
    assert codes(client.get("/api/v1/batches", headers=vij)) == [batches["V1"].batch_code]
    assert client.get(f"/api/v1/batches/{batches['V1'].batch_id}", headers=gnt).status_code == 404
    # asking for another branch's batches through a filter returns nothing, not an error
    assert codes(client.get("/api/v1/batches?branch_id=2", headers=gnt)) == []


def test_student_sees_only_the_batch_they_are_allocated_to(world, client, login):
    _, batches, students = world

    headers = login(students["s1"].student_code)

    assert codes(client.get("/api/v1/batches", headers=headers)) == [batches["G1"].batch_code]
    assert client.get(f"/api/v1/batches/{batches['G2'].batch_id}", headers=headers).status_code == 404


def test_admin_and_founder_see_everything_and_filters_work(world, client, login):
    people, batches, _ = world
    everything = sorted(b.batch_code for b in batches.values())

    for who in ("admin", "founder"):
        headers = login(people[who].email)
        assert codes(client.get("/api/v1/batches", headers=headers)) == everything
    headers = login(people["admin"].email)
    assert codes(client.get("/api/v1/batches?branch_id=2", headers=headers)) == [batches["V1"].batch_code]
    assert len(client.get("/api/v1/batches?state=Running", headers=headers).get_json()["data"]) == 3
    assert codes(client.get("/api/v1/batches?state=Forming", headers=headers)) == []
    listing = client.get("/api/v1/batches?per_page=2", headers=headers).get_json()
    assert listing["meta"] == {"page": 1, "per_page": 2, "total": 3, "pages": 2}


def test_batch_detail_shape(world, client, login):
    people, batches, _ = world

    data = client.get(f"/api/v1/batches/{batches['G1'].batch_id}", headers=login(people["ac_gnt"].email)).get_json()["data"]

    assert data["batch_code"] == batches["G1"].batch_code and data["batch_code"].startswith("NIT-GNT-BAT-")
    assert data["allocated_count"] == 1 and data["capacity"] == 30
    assert data["course"]["course_code"] == "NIT-CRS-047" and data["branch"]["branch_code"] == "NIT-GNT"
    assert [(t["full_name"], t["role"]) for t in data["trainers"]] == [("Trainer G1", "Lead")]


# ---------------------------------------------------------------- class sessions

def test_class_sessions_follow_batch_scope(world, client, login):
    people, batches, students = world

    def titles(headers, query=""):
        response = client.get(f"/api/v1/class-sessions{query}", headers=headers)
        assert response.status_code == 200, response.get_json()
        return [s["title"] for s in response.get_json()["data"]]

    assert titles(login(people["g1"].email)) == ["G1 session"]
    assert titles(login(people["ac_gnt"].email)) == ["G1 session", "G2 session"]
    assert titles(login(people["admin"].email)) == ["G1 session", "G2 session", "V1 session"]
    assert titles(login(students["s3"].student_code)) == ["V1 session"]

    ac = login(people["ac_gnt"].email)
    assert client.get(f"/api/v1/class-sessions?batch_id={batches['V1'].batch_id}", headers=ac).status_code == 404
    assert titles(ac, f"?batch_id={batches['G2'].batch_id}") == ["G2 session"]


def test_class_sessions_date_window_is_in_ist(world, client, login, make_session):
    people, batches, _ = world
    headers = login(people["admin"].email)
    make_session(batches["G1"], people["g1"], datetime(2026, 10, 2, 0, 30, tzinfo=IST), title="just after midnight IST")

    def titles(query):
        return [s["title"] for s in client.get(f"/api/v1/class-sessions?{query}", headers=headers).get_json()["data"]]

    assert titles("from=2026-10-02&to=2026-10-02") == ["just after midnight IST"]
    assert "just after midnight IST" not in titles("from=2026-10-01&to=2026-10-01")
    assert sorted(titles("from=2026-10-01&to=2026-10-02"))[:2] == ["G1 session", "G2 session"]


# ---------------------------------------------------------------- students

def test_student_detail_scope(world, client, login):
    people, batches, students = world
    s1, s2, s3 = (students[k].student_id for k in ("s1", "s2", "s3"))

    def get(who_headers, student_id):
        return client.get(f"/api/v1/students/{student_id}", headers=who_headers)

    own = login(students["s1"].student_code)
    assert get(own, s1).status_code == 200 and get(own, s2).status_code == 404

    trainer = login(people["g1"].email)  # teaches s1's batch only
    assert get(trainer, s1).status_code == 200 and get(trainer, s2).status_code == 404

    coordinator = login(people["ac_gnt"].email)
    assert get(coordinator, s1).status_code == 200 and get(coordinator, s3).status_code == 404

    assert get(login(people["admin"].email), s3).status_code == 200
    assert get(login(people["admin"].email), 999999).status_code == 404


def test_student_detail_hides_enrolments_serviced_at_another_branch(world, client, login, crm_event):
    people, batches, students = world
    # s1 buys a second course, serviced (and collected) at Vijayawada
    second = helpers.admission_data(person_id="P-1", admission_id="A-VIJ2", course="NIT-CRS-019", service="NIT-VIJ")
    assert crm_event("AdmissionQualified", second).status_code == 201
    gnt = login(people["ac_gnt"].email)
    vij = login(people["ac_vij"].email)

    gnt_view = client.get(f"/api/v1/students/{students['s1'].student_id}", headers=gnt).get_json()["data"]
    vij_view = client.get(f"/api/v1/students/{students['s1'].student_id}", headers=vij).get_json()["data"]
    own_view = client.get(f"/api/v1/students/{students['s1'].student_id}", headers=login(students["s1"].student_code)).get_json()["data"]

    assert [e["course"]["course_code"] for e in gnt_view["enrolments"]] == ["NIT-CRS-047"]
    assert [e["course"]["course_code"] for e in vij_view["enrolments"]] == ["NIT-CRS-019"]
    assert [e["course"]["course_code"] for e in own_view["enrolments"]] == ["NIT-CRS-047", "NIT-CRS-019"]
    assert gnt_view["enrolments"][0]["batch"]["batch_code"] == batches["G1"].batch_code
    assert own_view["enrolments"][1]["service_branch"]["branch_code"] == "NIT-VIJ"


# ---------------------------------------------------------------- reference

def test_reference_lists_are_staff_only_and_branch_limited(world, client, login):
    people, _, students = world

    assert client.get("/api/v1/reference/branches", headers=login(students["s1"].student_code)).status_code == 403

    branches = client.get("/api/v1/reference/branches", headers=login(people["ac_gnt"].email)).get_json()["data"]
    assert [b["branch_code"] for b in branches] == ["NIT-GNT"]

    admin = login(people["admin"].email)
    trainers = client.get("/api/v1/reference/staff?role=TRAINER&branch_id=2", headers=admin).get_json()["data"]
    assert [t["full_name"] for t in trainers] == ["Trainer V1"]
    roles = client.get("/api/v1/reference/roles", headers=admin).get_json()["data"]
    assert [r["role_code"] for r in roles] == ["STUDENT", "TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"]
    assert client.get("/api/v1/reference/staff?branch_id=2", headers=login(people["ac_gnt"].email)).status_code == 404

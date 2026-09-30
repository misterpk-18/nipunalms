"""Exception queue: one view over the slices' own open exceptions, branch scope, and the audited recovery step log."""
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from config.database import db
from models import AuditLog
from tests.library_helpers import API, auth, get, post


@pytest.fixture
def world(catalog, make_user, make_student, make_batch, make_session, run_sql):
    """Guntur: a Curriculum Mapping Pending enrolment, an Allocation Pending one and an unresolved recording exception.
    Vijayawada: a Curriculum Mapping Pending enrolment. Company-wide: a failed CRM event and a failed integration."""
    people = SimpleNamespace(
        ac_g=make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="AC Guntur"),
        ac_v=make_user(roles=[("ACADEMIC_COORDINATOR", 2)], full_name="AC Vijayawada"),
        bm_g=make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM Guntur"),
        sa=make_user(roles=[("SUPER_ADMIN", None)], full_name="Super Admin"),
        founder=make_user(roles=[("FOUNDER_CEO", None)], full_name="Founder"),
        trainer=make_user(roles=[("TRAINER", 1)], full_name="Trainer G"),
    )
    g_mapping = make_student(course="NIT-CRS-052", person_id="P-GM", admission_id="A-GM", email="gm@example.test")
    g_alloc = make_student(course="NIT-CRS-047", person_id="P-GA", admission_id="A-GA", email="ga@example.test")
    v_mapping = make_student(course="NIT-CRS-052", person_id="P-VM", admission_id="A-VM", email="vm@example.test",
                             service="NIT-VIJ", collecting="NIT-VIJ", original="NIT-VIJ")
    batch = make_batch(branch_id=1, trainers=(people.trainer,))
    from datetime import datetime, timezone
    session = make_session(batch, people.trainer, datetime(2026, 9, 20, 10, tzinfo=timezone.utc), state="Delivered", delivered_at=datetime(2026, 9, 20, 12, tzinfo=timezone.utc))
    run_sql("INSERT INTO recording_exceptions (session_id, branch_id, issue_type, issue, owner_role) "
            "VALUES (:s, 1, 'Held', 'Recording held for review', 'ACADEMIC_COORDINATOR')", s=session.session_id)
    run_sql("INSERT INTO crm_events (event_id, event_type, source_version, occurred_at, payload, status, error) "
            "VALUES ('evt-failed', 'AdmissionQualified', 1, now(), '{}', 'Failed', 'Unknown course')")
    run_sql("UPDATE integrations SET verification_status = 'Failed' WHERE integration_code = 'EMAIL'")
    return SimpleNamespace(people=people, g_mapping=g_mapping, g_alloc=g_alloc, v_mapping=v_mapping)


def rows_of(client, login, who, query=""):
    response = client.get(f"{API}/exceptions{query}", headers=auth(login, who))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def test_coordinator_sees_only_their_branch(client, login, world):
    rows = rows_of(client, login, world.people.ac_g)
    by_source = {r["source"] for r in rows}
    assert by_source == {"CURRICULUM_MAPPING", "ALLOCATION", "RECORDING"}
    assert all(r["branch"]["branch_id"] == 1 for r in rows)
    assert {r["reference"] for r in rows if r["source"] == "CURRICULUM_MAPPING"} == {world.g_mapping.enrolments[0]["enrolment_code"]}

    other = rows_of(client, login, world.people.ac_v)
    assert {r["source"] for r in other} == {"CURRICULUM_MAPPING"} and all(r["branch"]["branch_id"] == 2 for r in other)


def test_company_wide_items_are_for_the_super_admin_and_founder(client, login, world):
    everything = rows_of(client, login, world.people.sa)
    assert {"CRM_EVENT", "INTEGRATION"} <= {r["source"] for r in everything}
    assert {r["branch"]["branch_id"] for r in everything if r["branch"]} == {1, 2}
    crm = next(r for r in everything if r["source"] == "CRM_EVENT")
    assert crm["branch"] is None and crm["queue"] == "CRM/LMS sync" and crm["link"] == "/admin/crm-sync"
    assert len(rows_of(client, login, world.people.founder)) == len(everything)
    # a branch manager reads their own branch and none of the company-wide items
    assert {r["source"] for r in rows_of(client, login, world.people.bm_g)} == {"CURRICULUM_MAPPING", "ALLOCATION", "RECORDING"}


def test_filters_by_source_branch_and_state(client, login, world):
    sa = world.people.sa
    mapping = rows_of(client, login, sa, "?source=CURRICULUM_MAPPING")
    assert len(mapping) == 2
    assert [r["branch"]["branch_id"] for r in rows_of(client, login, sa, "?source=CURRICULUM_MAPPING&branch_id=2")] == [2]
    assert {r["source"] for r in rows_of(client, login, sa, "?state=Failed")} == {"CRM_EVENT", "INTEGRATION"}
    # a branch filter cannot widen a coordinator's scope
    assert rows_of(client, login, world.people.ac_g, "?branch_id=2") == []
    assert client.get(f"{API}/exceptions?source=NOPE", headers=auth(login, sa)).status_code == 400


def test_rows_without_a_named_owner_say_so(client, login, world):
    rows = rows_of(client, login, world.people.sa)
    assert all(r["awaiting_owner"] and r["owner"] is None for r in rows)
    assert {r["owner_label"] for r in rows if r["source"] == "CURRICULUM_MAPPING"} == {"Academic Coordinator — Guntur", "Academic Coordinator — Vijayawada"}
    assert len(rows_of(client, login, world.people.sa, "?awaiting_owner=false")) == 0


def test_staff_without_a_queue_role_are_refused(client, login, world):
    assert client.get(f"{API}/exceptions", headers=auth(login, world.people.trainer)).status_code == 403
    assert client.get(f"{API}/exceptions", headers=auth(login, world.g_mapping)).status_code == 403
    assert client.get(f"{API}/exceptions").status_code == 401


def test_logging_a_step_is_audited_and_names_the_owner(client, login, world):
    ref = world.g_mapping.enrolments[0]
    item = next(r for r in rows_of(client, login, world.people.ac_g) if r["source"] == "CURRICULUM_MAPPING")
    path = f"/exceptions/CURRICULUM_MAPPING/{item['source_id']}/steps"
    data = post(client, path, auth(login, world.people.ac_g), expect=201, json={"reason": "Curriculum v2 sent for approval"})
    assert data["step"]["reason"] == "Curriculum v2 sent for approval" and data["step"]["logged_by"]["full_name"] == "AC Guntur"
    assert data["exception"]["state"] == "Recovery In Progress" and data["exception"]["step_count"] == 1
    assert data["exception"]["owner"]["full_name"] == "AC Guntur" and data["exception"]["awaiting_owner"] is False
    assert ref["enrolment_code"] == data["exception"]["reference"]

    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "EXCEPTION_STEP_LOGGED")).scalar_one()
    assert entry.reason == "Curriculum v2 sent for approval" and entry.branch_id == 1
    assert entry.entity_id == f"CURRICULUM_MAPPING:{item['source_id']}" and entry.actor_user_id == world.people.ac_g.user_id

    steps = get(client, path, auth(login, world.people.bm_g))
    assert [s["reason"] for s in steps] == ["Curriculum v2 sent for approval"]
    # the next step is listed newest first
    post(client, path, auth(login, world.people.sa), expect=201, json={"reason": "Approved, re-mapping now"})
    assert [s["reason"] for s in get(client, path, auth(login, world.people.ac_g))][0] == "Approved, re-mapping now"


def test_a_step_needs_a_reason(client, login, world):
    item = next(r for r in rows_of(client, login, world.people.ac_g) if r["source"] == "ALLOCATION")
    path = f"{API}/exceptions/ALLOCATION/{item['source_id']}/steps"
    for body in ({}, {"reason": ""}, {"reason": "  "}, {"reason": "ok"}):
        assert client.post(path, headers=auth(login, world.people.ac_g), json=body).status_code == 400
    assert db.session.execute(select(AuditLog).where(AuditLog.action == "EXCEPTION_STEP_LOGGED")).first() is None


def test_steps_are_permission_checked_and_branch_scoped(client, login, world):
    item = next(r for r in rows_of(client, login, world.people.ac_g) if r["source"] == "CURRICULUM_MAPPING")
    path = f"{API}/exceptions/CURRICULUM_MAPPING/{item['source_id']}/steps"
    body = {"json": {"reason": "Trying to log a step"}}
    # read-only roles
    assert client.post(path, headers=auth(login, world.people.bm_g), **body).status_code == 403
    assert client.post(path, headers=auth(login, world.people.founder), **body).status_code == 403
    assert client.post(path, headers=auth(login, world.people.trainer), **body).status_code == 403
    # another branch's coordinator cannot see the item, so it is a 404 (reading its steps too)
    assert client.post(path, headers=auth(login, world.people.ac_v), **body).status_code == 404
    assert client.get(path, headers=auth(login, world.people.ac_v)).status_code == 404
    # company-wide items are the Super Admin's
    crm = next(r for r in rows_of(client, login, world.people.sa) if r["source"] == "CRM_EVENT")
    crm_path = f"{API}/exceptions/CRM_EVENT/{crm['source_id']}/steps"
    assert client.post(crm_path, headers=auth(login, world.people.ac_g), **body).status_code == 404
    assert client.post(crm_path, headers=auth(login, world.people.sa), **body).status_code == 201
    assert client.post(f"{API}/exceptions/NOPE/1/steps", headers=auth(login, world.people.sa), **body).status_code == 404
    assert client.post(f"{API}/exceptions/CRM_EVENT/99999/steps", headers=auth(login, world.people.sa), **body).status_code == 404


def test_an_exception_leaves_the_queue_when_its_slice_resolves_it(client, login, world, run_sql):
    before = rows_of(client, login, world.people.sa)
    run_sql("UPDATE crm_events SET status = 'Applied', error = NULL WHERE event_id = 'evt-failed'")
    run_sql("UPDATE recording_exceptions SET status = 'Resolved', resolved_at = now(), resolution_note = 'Released' WHERE status <> 'Resolved'")
    after = rows_of(client, login, world.people.sa)
    assert len(before) - len(after) == 2
    assert not {"CRM_EVENT", "RECORDING"} & {r["source"] for r in after}


def test_recovery_steps_are_append_only(client, login, world, run_sql):
    item = next(r for r in rows_of(client, login, world.people.ac_g) if r["source"] == "ALLOCATION")
    post(client, f"/exceptions/ALLOCATION/{item['source_id']}/steps", auth(login, world.people.ac_g), expect=201, json={"reason": "Batch opens Monday"})
    with pytest.raises(Exception, match="append-only"):
        db.session.execute(text("DELETE FROM exception_recovery_steps"))
    db.session.rollback()

"""db 098: the batch timetable (days, times, room) set by the coordinator, and what the CRM's sales staff pull: timetable,
readiness and seats left (the CRM's sales playbook, round 3)."""
from datetime import datetime, timedelta, timezone

import pytest

from tests import helpers

API = "/api/v1"
STATUS = f"{API}/integrations/crm/status"
HEADERS = {"X-Service-Key": "test-crm-service-key"}
TIMETABLE = {"schedule_days": ["wed", "Mon", "Fri"], "start_time": "18:30", "end_time": "20:30", "location": "Guntur Lab 2"}


@pytest.fixture
def coordinator(login, make_user):
    return login(make_user(roles=[("ACADEMIC_COORDINATOR", 1)]).email)


def _create(client, coordinator, catalog, **extra) -> dict:
    from repositories import catalog as catalog_repo

    body = {"course_id": catalog_repo.get_course_by_code("NIT-CRS-047").course_id, "branch_id": 1, "capacity": 2,
            "mode": "Classroom", "planned_start": "2026-10-12", **extra}
    response = client.post(f"{API}/batches", json=body, headers=coordinator)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _pulled(client, run_sql, batch_code: str) -> dict:
    (batch,) = [b for b in client.get(STATUS, headers=HEADERS, query_string={
        "since": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}).get_json()["data"]["batches"]
        if b["lms_course_id"] == batch_code]
    run_sql("UPDATE batch_crm_state SET changed_at = now() - interval '1 hour'")  # so the next pull shows only new changes
    return batch


def test_a_coordinator_sets_the_timetable_and_the_crm_pulls_it(client, coordinator, catalog, run_sql):
    batch = _create(client, coordinator, catalog, **TIMETABLE)

    assert {k: batch[k] for k in TIMETABLE} == {"schedule_days": ["Mon", "Wed", "Fri"], "start_time": "18:30",
                                                "end_time": "20:30", "location": "Guntur Lab 2"}
    pulled = _pulled(client, run_sql, batch["batch_code"])
    assert {k: pulled[k] for k in ("schedule_days", "start_time", "end_time", "location", "readiness", "seats_left")} == \
        {"schedule_days": "Mon, Wed, Fri", "start_time": "18:30", "end_time": "20:30", "location": "Guntur Lab 2",
         "readiness": batch["readiness"], "seats_left": 2}


def test_a_change_and_a_clear_come_back_in_the_next_pull(client, coordinator, catalog, run_sql):
    batch = _create(client, coordinator, catalog, **TIMETABLE)
    _pulled(client, run_sql, batch["batch_code"])
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    moved = client.patch(f"{API}/batches/{batch['batch_id']}", json={"start_time": "19:00", "end_time": "21:00"}, headers=coordinator)
    assert moved.status_code == 200, moved.get_json()
    assert _pulled(client, run_sql, batch["batch_code"])["start_time"] == "19:00"

    cleared = client.patch(f"{API}/batches/{batch['batch_id']}",
                           json={"schedule_days": None, "start_time": None, "end_time": None, "location": None}, headers=coordinator)
    assert cleared.status_code == 200, cleared.get_json()
    pulled = _pulled(client, run_sql, batch["batch_code"])
    assert (pulled["schedule_days"], pulled["start_time"], pulled["end_time"], pulled["location"]) == (None, None, None, None)
    assert client.get(STATUS, headers=HEADERS, query_string={"since": since}).get_json()["data"]["batches"] == []  # nothing new


@pytest.mark.parametrize("body, field", [
    ({"start_time": "18:30"}, "end_time"),
    ({"start_time": "20:30", "end_time": "18:30"}, "end_time"),
    ({"schedule_days": ["Mon", "Funday"]}, "schedule_days"),
    ({"start_time": "6pm", "end_time": "8pm"}, "start_time"),
])
def test_an_impossible_timetable_is_refused(client, coordinator, catalog, body, field):
    from repositories import catalog as catalog_repo

    response = client.post(f"{API}/batches", headers=coordinator, json={
        "course_id": catalog_repo.get_course_by_code("NIT-CRS-047").course_id, "branch_id": 1, "capacity": 2, **body})

    assert response.status_code == 400 and field in response.get_json()["error"]["details"]


def test_a_live_online_batch_has_no_room(client, coordinator, catalog):
    batch = _create(client, coordinator, catalog, **{**TIMETABLE, "mode": "Live Online"})

    assert batch["location"] is None and batch["start_time"] == "18:30"


def test_seats_left_follows_allocations(client, coordinator, catalog, crm_event, run_sql):
    batch = _create(client, coordinator, catalog)
    crm_event("AdmissionQualified", helpers.admission_data())
    enrolment_id = run_sql("SELECT enrolment_id FROM enrolments").scalar_one()

    allocated = client.post(f"{API}/batches/{batch['batch_id']}/allocations", json={"enrolment_id": enrolment_id}, headers=coordinator)

    assert allocated.status_code == 201, allocated.get_json()
    assert _pulled(client, run_sql, batch["batch_code"])["seats_left"] == 1

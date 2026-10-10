"""Rounds 3 and 5 (docs/CRM_INTEGRATION.md): the crm_admission_id / crm_person_id filter on the pull, and the CRM holding no
curriculum (db 104). The LMS maps an admission to its course's Active version itself and never waits on the CRM."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.database import db
from tests import helpers

API = "/api/v1"
STATUS = f"{API}/integrations/crm/status"
HEADERS = {"X-Service-Key": "test-crm-service-key"}
CURRICULUM_KEYS = ("curriculum_status", "curriculum_version_label")


def _pull(client, since=None, **filters) -> dict:
    query = {"since": since or (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), **filters}
    response = client.get(STATUS, headers=HEADERS, query_string=query)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def _scalar(sql: str, **params):
    return db.session.execute(text(sql), params).scalar_one()


# ---------------------------------------------------------------- the CRM holds no curriculum (round 5)

def test_a_new_admission_is_mapped_by_the_lms_and_allocated_with_no_crm_mapping(client, catalog, crm_event, make_user, login):
    from repositories import catalog as catalog_repo

    coordinator = login(make_user(roles=[("BRANCH_MANAGER", 1)]).email)
    batch = client.post(f"{API}/batches", headers=coordinator, json={
        "course_id": catalog_repo.get_course_by_code("NIT-CRS-047").course_id, "branch_id": 1, "capacity": 2,
        "mode": "Classroom", "planned_start": "2026-10-12"}).get_json()["data"]  # the LMS gives it the Active version
    response = crm_event("AdmissionQualified", helpers.admission_data())  # no AdmissionCurriculumMapped follows, ever
    assert response.status_code == 201, response.get_json()
    assert _scalar("SELECT cv.version_label FROM enrolments e JOIN curriculum_versions cv USING (curriculum_version_id)") == "CV 5.1"
    assert _scalar("SELECT status::text FROM enrolments") == "Allocation Pending"

    allocated = client.post(f"{API}/batches/{batch['batch_id']}/allocations", headers=coordinator,
                            json={"enrolment_id": _scalar("SELECT enrolment_id FROM enrolments")})

    assert allocated.status_code == 201, allocated.get_json()
    assert _scalar("SELECT status::text FROM enrolments") == "Allocated — awaiting first regular class"
    (academic,) = _pull(client)["academics"]
    assert academic["enrolment_status"] == "Scheduled" and len(academic["allocations"]) == 1


def test_the_pull_carries_no_curriculum(client, catalog, crm_event, make_batch):
    make_batch(crm_batch_id="GNT-B-0007")
    crm_event("AdmissionQualified", helpers.admission_data(enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]))

    data = _pull(client)

    assert "curriculum_versions" not in data
    (academic,) = data["academics"]
    (batch,) = data["batches"]
    assert not set(CURRICULUM_KEYS) & set(academic) and "curriculum_version_label" not in batch
    assert batch["crm_batch_id"] == "GNT-B-0007" and academic["allocations"][0]["crm_batch_id"] == "GNT-B-0007"


def test_the_catalogue_mirror_and_the_retired_event_are_gone(client, catalog, crm_event, run_sql):
    assert _scalar("SELECT to_regclass('curriculum_version_crm_state') IS NULL") is True
    assert _scalar("SELECT count(*) FROM information_schema.columns "
                   "WHERE table_name = 'admissions' AND column_name = 'curriculum_source_version'") == 0
    crm_event("AdmissionQualified", helpers.admission_data())

    response = crm_event("AdmissionCurriculumMapped", {"crm_admission_id": "A-100", "course_code": "NIT-CRS-047",
                                                       "curriculum_version_label": "CV 5.1"})

    assert response.status_code == 400 and "event_type" in response.get_json()["error"]["details"]
    assert _scalar("SELECT count(*) FROM crm_events WHERE event_type = 'AdmissionCurriculumMapped'") == 0


def test_a_new_version_going_active_changes_nothing_the_crm_pulls(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data())
    since = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()

    run_sql("UPDATE curriculum_versions SET status = 'Retired' WHERE version_label = 'CV 5.1'")
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status, approved_at) SELECT course_id, 'CV 5.2', "
            "'Active', now() FROM courses WHERE course_code = 'NIT-CRS-047'")

    data = _pull(client, since)
    assert (data["academics"], data["batches"]) == ([], []) and "curriculum_versions" not in data


# ---------------------------------------------------------------- the filter

def test_the_pull_can_be_narrowed_to_one_admission_or_person(client, catalog, crm_event, make_batch):
    make_batch(crm_batch_id="GNT-B-0007")
    make_batch(course_code="NIT-CRS-019")
    crm_event("AdmissionQualified", helpers.admission_data(person_id="21", admission_id="6", email="meera@example.test",
                                                           enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]))
    crm_event("AdmissionQualified", helpers.admission_data(person_id="21", admission_id="7", email="meera@example.test",
                                                           course="NIT-CRS-019"))
    crm_event("AdmissionQualified", helpers.admission_data(person_id="30", admission_id="9", email="ravi@example.test"))

    one = _pull(client, crm_admission_id="6")

    assert one["filter"] == {"crm_admission_id": "6"}
    assert [p["crm_person_id"] for p in one["persons"]] == ["21"]
    assert [a["crm_admission_id"] for a in one["admissions"]] == ["6"]
    assert [a["crm_admission_id"] for a in one["academics"]] == ["6"]
    assert [b["crm_batch_id"] for b in one["batches"]] == ["GNT-B-0007"]

    person = _pull(client, crm_person_id="21")
    assert sorted(a["crm_admission_id"] for a in person["admissions"]) == ["6", "7"]

    nobody = _pull(client, crm_admission_id="404")
    assert {k: nobody[k] for k in ("persons", "admissions", "academics", "batches", "certificates")} == \
        {"persons": [], "admissions": [], "academics": [], "batches": [], "certificates": []}
    assert "filter" not in _pull(client)

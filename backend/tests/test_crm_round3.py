"""Round 3: curriculum mapping from the CRM (docs/CRM_INTEGRATION.md §5, db 097): the catalogue in
the status pull, AdmissionCurriculumMapped, and the crm_admission_id / crm_person_id filter on the pull."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.database import db
from tests import helpers

STATUS = "/api/v1/integrations/crm/status"
HEADERS = {"X-Service-Key": "test-crm-service-key"}


def _pull(client, since=None, **filters) -> dict:
    query = {"since": since or (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), **filters}
    response = client.get(STATUS, headers=HEADERS, query_string=query)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def _scalar(sql: str, **params):
    return db.session.execute(text(sql), params).scalar_one()


def _versions(data, course_code) -> dict[str, dict]:
    return {v["version_label"]: v for v in data["curriculum_versions"] if v["course_code"] == course_code}


def mapped(crm_event, label, *, admission_id="A-100", course="NIT-CRS-047", track=None, source_version=1, **extra):
    data = {"crm_admission_id": admission_id, "admission_code": "NIT-GNT-2026-000100", "course_code": course,
            "track_code": track, "curriculum_version_label": label, "mapped_by_email": "coordinator.gnt@nipuna.test",
            "reason": None, **extra}
    return crm_event("AdmissionCurriculumMapped", data, source_version=source_version)


def _active_052(run_sql, label="CV 3.0") -> None:
    """An Active NIT-CRS-052 version written directly, so nothing auto-maps the waiting enrolments (as a CRM-only test)."""
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status, approved_at) "
            "SELECT course_id, :l, 'Active', now() FROM courses WHERE course_code = 'NIT-CRS-052'", l=label)


def _error(response) -> tuple[int, str, str]:
    error = response.get_json()["error"]
    return response.status_code, error["code"], error["message"]


# ---------------------------------------------------------------- the catalogue in the pull

def test_the_pull_carries_every_curriculum_version_in_the_crms_three_statuses(client, catalog, run_sql):
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status) SELECT course_id, 'CV 3.0', 'Under Review' "
            "FROM courses WHERE course_code = 'NIT-CRS-052'")

    data = _pull(client)

    java = _versions(data, "NIT-CRS-047")["CV 5.1"]
    assert {k: java[k] for k in ("track_code", "status", "lms_status")} == {"track_code": None, "status": "Active", "lms_status": "Active"}
    assert java["published_at"]  # a version made Active directly: its approval time
    assert _versions(data, "NIT-CRS-052")["CV 3.0"] | {"published_at": None} == {
        "course_code": "NIT-CRS-052", "track_code": None, "version_label": "CV 3.0", "status": "Draft",
        "lms_status": "Under Review", "published_at": None}
    tracks = {v["track_code"] for v in data["curriculum_versions"] if v["course_code"] == "NIT-CRS-018"}
    assert tracks == {None, "NIT-CRS-018/T1", "NIT-CRS-018/T2", "NIT-CRS-018/T3"}


def test_only_changed_versions_come_back_and_a_retired_one_keeps_its_published_at(client, catalog, run_sql):
    run_sql("UPDATE curriculum_version_crm_state SET changed_at = now() - interval '1 hour'")
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    assert _pull(client, since)["curriculum_versions"] == []

    run_sql("UPDATE curriculum_versions SET status = 'Retired' WHERE version_label = 'CV 5.1'")
    (retired,) = _pull(client, since)["curriculum_versions"]

    assert (retired["version_label"], retired["status"]) == ("CV 5.1", "Retired")
    assert retired["published_at"]


def test_a_deleted_draft_comes_back_as_a_retired_tombstone(client, catalog, run_sql):
    run_sql("INSERT INTO curriculum_versions (course_id, version_label) SELECT course_id, 'CV 9.9' FROM courses "
            "WHERE course_code = 'NIT-CRS-047'")
    run_sql("DELETE FROM curriculum_versions WHERE version_label = 'CV 9.9'")

    gone = _versions(_pull(client), "NIT-CRS-047")["CV 9.9"]

    assert (gone["status"], gone["lms_status"]) == ("Retired", "Deleted")


# ---------------------------------------------------------------- AdmissionCurriculumMapped

def test_a_crm_mapping_moves_a_waiting_enrolment_to_allocation_pending(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data(course="NIT-CRS-052"))
    assert _scalar("SELECT status::text FROM enrolments") == "Curriculum Mapping Pending"
    _active_052(run_sql)

    response = mapped(crm_event, "CV 3.0", course="NIT-CRS-052")

    assert response.status_code == 201, response.get_json()
    result = response.get_json()["data"]["result"]
    assert (result["curriculum_status"], result["curriculum_version_label"], result["changed"]) == ("Mapped", "CV 3.0", True)
    assert _scalar("SELECT status::text FROM enrolments") == "Allocation Pending"
    (academic,) = _pull(client)["academics"]
    assert (academic["curriculum_status"], academic["curriculum_version_label"]) == ("Mapped", "CV 3.0")
    assert _scalar("SELECT reason IS NULL FROM audit_log WHERE action = 'CURRICULUM_MAPPED_BY_CRM'") is True


def test_mapping_the_version_the_lms_already_mapped_just_confirms_it(client, catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data())  # auto-mapped to CV 5.1
    data = {"crm_admission_id": "A-100", "course_code": "NIT-CRS-047", "track_code": None,
            "curriculum_version_label": "CV 5.1", "mapped_by_email": "coordinator.gnt@nipuna.test"}

    first = crm_event("AdmissionCurriculumMapped", data, event_id="evt-map-1")
    replay = crm_event("AdmissionCurriculumMapped", data, event_id="evt-map-1")

    assert first.status_code == 201 and first.get_json()["data"]["result"]["changed"] is False
    assert replay.status_code == 200 and replay.get_json()["data"]["replayed"] is True
    assert replay.get_json()["data"]["result"] == first.get_json()["data"]["result"]


def test_unknown_or_unpublished_labels_are_refused_with_a_message_for_staff(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data())
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status) SELECT course_id, 'CV 6.0', 'Draft' "
            "FROM courses WHERE course_code = 'NIT-CRS-047'")

    assert _error(mapped(crm_event, "CV 7.7")) == (422, "BUSINESS_RULE", "There is no curriculum CV 7.7 for NIT-CRS-047 in the LMS")
    status, code, message = _error(mapped(crm_event, "CV 6.0"))
    assert (status, code) == (422, "BUSINESS_RULE")
    assert message == "CV 6.0 is Draft in the LMS, so it can't be mapped. The Active version for NIT-CRS-047 is CV 5.1"
    assert _error(mapped(crm_event, "CV 5.1", course="NIT-CRS-019"))[2] == "Admission ADM-GNT-2026-000100 is for NIT-CRS-047, not NIT-CRS-019"


def test_an_admission_that_has_not_arrived_is_retryable(client, catalog, crm_event):
    status, code, message = _error(mapped(crm_event, "CV 5.1", admission_id="A-404"))

    assert (status, code) == (422, "NOT_YET_APPLIED") and "has not been applied yet" in message


def test_a_change_after_allocation_is_refused(client, catalog, crm_event, make_batch, run_sql):
    make_batch(crm_batch_id="GNT-B-0007")
    crm_event("AdmissionQualified", helpers.admission_data(enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]))
    run_sql("UPDATE curriculum_versions SET status = 'Retired' WHERE version_label = 'CV 5.1'")
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status, approved_at) SELECT course_id, 'CV 5.2', "
            "'Active', now() FROM courses WHERE course_code = 'NIT-CRS-047'")

    status, code, message = _error(mapped(crm_event, "CV 5.2"))

    assert (status, code) == (409, "CONFLICT")
    assert message.endswith("on CV 5.1. Change the curriculum in the LMS together with the allocation")
    assert _scalar("SELECT cv.version_label FROM enrolments e JOIN curriculum_versions cv USING (curriculum_version_id)") == "CV 5.1"


def test_an_unallocated_enrolment_moves_off_a_retired_version(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data())
    run_sql("UPDATE curriculum_versions SET status = 'Retired' WHERE version_label = 'CV 5.1'")
    run_sql("INSERT INTO curriculum_versions (course_id, version_label, status, approved_at) SELECT course_id, 'CV 5.2', "
            "'Active', now() FROM courses WHERE course_code = 'NIT-CRS-047'")

    response = mapped(crm_event, "CV 5.2", reason="New syllabus before allocation")

    assert response.status_code == 201 and response.get_json()["data"]["result"]["changed"] is True
    assert _scalar("SELECT reason FROM audit_log WHERE action = 'CURRICULUM_MAPPED_BY_CRM'") == "New syllabus before allocation"


def test_withdrawn_and_stale_mappings(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data())
    assert mapped(crm_event, "CV 5.1", source_version=5).status_code == 201
    stale = mapped(crm_event, "CV 5.1", source_version=4)
    assert stale.get_json()["data"]["status"] == "Ignored — stale"

    crm_event("AdmissionCancelled", {"crm_admission_id": "A-100", "reason": "Left"}, source_version=2)
    assert _error(mapped(crm_event, "CV 5.1", source_version=6))[:2] == (409, "CONFLICT")


def test_a_combo_track_is_mapped_by_its_track_code(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.combo_admission_data())
    run_sql("UPDATE enrolment_tracks SET curriculum_version_id = NULL WHERE component_id = "
            "(SELECT component_id FROM course_components WHERE track_code = 'NIT-CRS-019')")
    run_sql("UPDATE enrolments SET status = 'Curriculum Mapping Pending' WHERE course_id = "
            "(SELECT course_id FROM courses WHERE course_code = 'NIT-CRS-018')")

    response = mapped(crm_event, "CV 1.3", course="NIT-CRS-018", track="NIT-CRS-019")  # the booster's own course version

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["result"]["curriculum_status"] == "Mapped"
    assert _error(mapped(crm_event, "CV 1.3", course="NIT-CRS-018", track="NIT-CRS-018/T9", source_version=2))[2] == \
        "NIT-CRS-018 has no track NIT-CRS-018/T9"


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
    assert {v["course_code"] for v in one["curriculum_versions"]} == {"NIT-CRS-047"}

    person = _pull(client, crm_person_id="21")
    assert sorted(a["crm_admission_id"] for a in person["admissions"]) == ["6", "7"]
    assert {v["course_code"] for v in person["curriculum_versions"]} == {"NIT-CRS-047", "NIT-CRS-019"}

    nobody = _pull(client, crm_admission_id="404")
    assert {k: nobody[k] for k in ("persons", "admissions", "academics", "batches", "certificates", "curriculum_versions")} == \
        {"persons": [], "admissions": [], "academics": [], "batches": [], "certificates": [], "curriculum_versions": []}
    assert "filter" not in _pull(client)

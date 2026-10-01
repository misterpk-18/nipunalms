"""Fixes from the CRM's round-1 run ("nipuna crm-docs/CRM_TO_LMS_FIXES_ROUND1.md", F2–F8)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from config.database import db
from tests import helpers

STATUS = "/api/v1/integrations/crm/status"
HEADERS = {"X-Service-Key": "test-crm-service-key"}


def _scalar(sql: str, **params):
    return db.session.execute(text(sql), params).scalar_one()


def _components(course_code: str) -> list[str]:
    return list(db.session.execute(text(
        "SELECT cc.track_code FROM course_components cc JOIN courses c ON c.course_id = cc.parent_course_id"
        " WHERE c.course_code = :code ORDER BY cc.sort_order"), {"code": course_code}).scalars())


@pytest.fixture
def combo(crm_event):
    """NIT-CRS-900: a combo of three single courses (no curriculum)."""
    for code in ("NIT-CRS-101", "NIT-CRS-102", "NIT-CRS-103"):
        assert crm_event("CourseUpserted", {"course_code": code, "course_title": f"Course {code[-3:]}"}).status_code == 201
    data = {"course_code": "NIT-CRS-900", "course_title": "Combo", "is_combo": True, "status": "Active",
            "components": [{"component_course_code": code, "is_bonus": False, "sort_order": n}
                           for n, code in enumerate(("NIT-CRS-101", "NIT-CRS-102", "NIT-CRS-103"), 1)]}
    assert crm_event("CourseUpserted", data).status_code == 201
    return data


# ---------------------------------------------------------------- F2: CourseUpserted reconciles components

def test_a_component_left_out_of_the_event_is_removed(crm_event, combo):
    response = crm_event("CourseUpserted", {**combo, "components": combo["components"][:2]}, source_version=2)

    assert response.status_code == 201
    assert response.get_json()["data"]["result"]["components"] == 2
    assert _components("NIT-CRS-900") == ["NIT-CRS-900/T1", "NIT-CRS-900/T2"]


def test_a_combo_turned_single_keeps_no_components(crm_event, combo):
    response = crm_event("CourseUpserted", {"course_code": "NIT-CRS-900", "course_title": "Now single", "is_combo": False},
                         source_version=2)

    assert response.status_code == 201
    assert _components("NIT-CRS-900") == []
    assert _scalar("SELECT is_combo FROM courses WHERE course_code = 'NIT-CRS-900'") is False


def test_a_component_in_use_is_never_removed_and_the_event_changes_nothing(crm_event, combo, run_sql):
    enrolled = crm_event("AdmissionQualified", helpers.admission_data(course="NIT-CRS-900"))
    assert enrolled.status_code == 201, enrolled.get_json()
    single = {"course_code": "NIT-CRS-900", "course_title": "Now single", "is_combo": False}

    refused = crm_event("CourseUpserted", single, event_id="evt-single", source_version=2)

    assert refused.status_code == 422
    message = refused.get_json()["error"]["message"]
    assert "NIT-CRS-900/T1, NIT-CRS-900/T2, NIT-CRS-900/T3" in message and "1 enrolment(s)" in message
    row = db.session.execute(text("SELECT is_combo, title, source_version FROM courses WHERE course_code = 'NIT-CRS-900'")).one()
    assert tuple(row) == (True, "Combo", 1)
    assert len(_components("NIT-CRS-900")) == 3
    assert _scalar("SELECT status::text FROM crm_events WHERE event_id = 'evt-single'") == "Failed"

    # Once the enrolment is withdrawn and its tracks removed, the same event applies
    assert crm_event("AdmissionCancelled", {"crm_admission_id": "A-100", "reason": "Moved"}, source_version=2).status_code == 201
    run_sql("DELETE FROM enrolment_tracks")
    again = crm_event("CourseUpserted", single, event_id="evt-single", source_version=2)
    assert again.status_code == 200 and again.get_json()["data"]["status"] == "Applied"
    assert _components("NIT-CRS-900") == []


def test_curriculum_written_for_a_track_also_blocks_removing_it(catalog, crm_event):
    data = {**helpers.catalog_courses()[-1], "is_combo": False, "components": []}

    refused = crm_event("CourseUpserted", data, source_version=2)

    assert refused.status_code == 422
    message = refused.get_json()["error"]["message"]
    # The three main tracks have curriculum versions; the unused booster track alone would have been removed
    assert "NIT-CRS-018/T1, NIT-CRS-018/T2, NIT-CRS-018/T3 are" in message and "0 enrolment(s) and 3 curriculum version(s)" in message
    assert len(_components("NIT-CRS-018")) == 4


def test_the_database_refuses_a_single_course_with_components(combo, run_sql):
    with pytest.raises(DBAPIError, match="still has combo components"):
        run_sql("UPDATE courses SET is_combo = false WHERE course_code = 'NIT-CRS-900'")
    db.session.rollback()


# ---------------------------------------------------------------- F4: the CRM's documented field names

MINIMAL = {  # docs/CRM_INTEGRATION.md §2.1 minimal example, as written
    "person": {"person_id": 148, "person_code": "PER-GNT-00148", "full_name": "Anvitha K.",
               "phone": "9876543210", "email": "anvitha@example.test", "preferred_language": "English"},
    "admission": {"admission_id": 1001, "admission_code": "NIT-GNT-2026-000001", "course_code": "NIT-CRS-047",
                  "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT",
                  "delivery_mode": "Classroom", "admission_date": "2026-09-28"},
}


def test_the_documented_minimal_admission_is_accepted(catalog, crm_event):
    response = crm_event("AdmissionQualified", MINIMAL)

    assert response.status_code == 201, response.get_json()
    row = db.session.execute(text("SELECT s.crm_person_id, a.crm_admission_id FROM students s JOIN admissions a USING (student_id)")).one()
    assert tuple(row) == ("148", "1001")


def test_the_lms_named_id_wins_over_its_alias(catalog, crm_event):
    data = {"person": {**MINIMAL["person"], "crm_person_id": 149},
            "admission": {**MINIMAL["admission"], "crm_admission_id": 1002}}
    data["admission"]["complimentary_of_admission_id"] = 999  # alias of complimentary_of_crm_admission_id: unknown admission

    response = crm_event("AdmissionQualified", data)

    assert response.status_code == 422 and "'999'" in response.get_json()["error"]["message"]
    del data["admission"]["complimentary_of_admission_id"]
    assert crm_event("AdmissionQualified", data).status_code == 201
    row = db.session.execute(text("SELECT s.crm_person_id, a.crm_admission_id FROM students s JOIN admissions a USING (student_id)")).one()
    assert tuple(row) == ("149", "1002")


# ---------------------------------------------------------------- F5: field limits as long as the CRM's

def test_a_255_character_course_title_is_accepted(crm_event):
    title = "T" * 255
    assert crm_event("CourseUpserted", {"course_code": "NIT-CRS-901", "course_title": title}).status_code == 201
    assert _scalar("SELECT title FROM courses WHERE course_code = 'NIT-CRS-901'") == title
    assert crm_event("CourseUpserted", {"course_code": "NIT-CRS-902", "course_title": "T" * 256}).status_code == 400


def test_a_long_cancellation_reason_is_accepted(catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data())
    reason = "Refund requested. " * 90  # 1,620 characters

    response = crm_event("AdmissionCancelled", {"crm_admission_id": "A-100", "reason": reason}, source_version=2)

    assert response.status_code == 201
    assert _scalar("SELECT reason FROM audit_log WHERE action = 'ADMISSION_CANCELLED'") == reason.strip()


# ---------------------------------------------------------------- F6: seed rows stay out of the status pull

def test_rows_marked_as_seed_data_are_not_pulled(client, catalog, crm_event, make_batch, run_sql):
    before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    make_batch(crm_batch_id="CRM-BAT-101")
    crm_event("AdmissionQualified", helpers.admission_data(person_id="CRM-PER-1001", admission_id="CRM-ADM-214"))
    run_sql("UPDATE students SET seed_data = true; UPDATE admissions SET seed_data = true; UPDATE batches SET seed_data = true")
    make_batch(crm_batch_id="17")
    crm_event("AdmissionQualified", helpers.admission_data(person_id="21", admission_id="6", email="meera@example.test"))

    data = client.get(STATUS, headers=HEADERS, query_string={"since": before}).get_json()["data"]

    assert [p["crm_person_id"] for p in data["persons"]] == ["21"]
    assert [a["crm_admission_id"] for a in data["admissions"]] == ["6"]
    assert [a["crm_admission_id"] for a in data["academics"]] == ["6"]
    assert [b["crm_batch_id"] for b in data["batches"]] == ["17"]


# ---------------------------------------------------------------- F7: activation for CRM-provisioned students

def test_a_coordinator_reissues_the_link_of_a_crm_provisioned_student(client, catalog, crm_event, make_user, login):
    provisioned = crm_event("AdmissionQualified", helpers.admission_data()).get_json()["data"]
    student_id = provisioned["result"]["student_id"]
    row = db.session.execute(text("SELECT channel, issued_by FROM student_activations WHERE student_id = :s"), {"s": student_id}).one()
    assert tuple(row) == ("CRM provisioning", None)  # the CRM drops this token: the student cannot use it

    coordinator = login(make_user(roles=[("ACADEMIC_COORDINATOR", 1)]).email)
    issued = client.post(f"/api/v1/students/{student_id}/activation", headers=coordinator)

    assert issued.status_code == 201
    token = issued.get_json()["data"]["token"]
    assert client.post("/api/v1/auth/activate", json={"token": provisioned["activation_token"], "password": "Correct-horse-1"}).status_code == 422
    assert client.post("/api/v1/auth/activate", json={"token": token, "password": "Correct-horse-1"}).status_code == 200


def test_students_waiting_on_an_undelivered_crm_link_can_be_listed(client, catalog, crm_event, make_user, login):
    for n in (1, 2, 3):
        crm_event("AdmissionQualified", helpers.admission_data(person_id=f"P-{n}", admission_id=f"A-{n}", email=f"s{n}@example.test"))
    admin = login(make_user(roles=[("SUPER_ADMIN", None)]).email)
    second = _scalar("SELECT student_id FROM students WHERE crm_person_id = 'P-2'")
    assert client.post(f"/api/v1/students/{second}/activation", headers=admin).status_code == 201

    def listed(channel):
        page = client.get("/api/v1/admin/students", headers=admin,
                          query_string={"activation_status": "Activation Pending", "activation_channel": channel}).get_json()
        return sorted(s["email"] for s in page["data"])

    assert listed("CRM provisioning") == ["s1@example.test", "s3@example.test"]
    assert listed("Staff issued") == ["s2@example.test"]
    assert client.get("/api/v1/admin/students", headers=admin, query_string={"activation_channel": "Email"}).status_code == 400


# ---------------------------------------------------------------- F8: a repeated AdmissionQualified is a full refresh

def test_requalifying_refreshes_the_person_and_admission_but_never_the_learning(catalog, crm_event, make_batch):
    batch = make_batch(crm_batch_id="GNT-B-1")
    first = crm_event("AdmissionQualified", helpers.admission_data()).get_json()["data"]
    assert crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "enrolments": [
        {"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-1"}]}, source_version=2).status_code == 201
    status = _scalar("SELECT status::text FROM enrolments")

    again = helpers.admission_data(name="Anvitha Kumari", email=None)
    again["admission"]["planned_start_date"] = "2026-11-02"
    response = crm_event("AdmissionQualified", again, source_version=3)

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["activation_token"] is None and data["result"]["student_id"] == first["result"]["student_id"]
    row = db.session.execute(text("SELECT s.full_name, s.email, a.planned_start_date::text FROM students s JOIN admissions a USING (student_id)")).one()
    assert tuple(row) == ("Anvitha Kumari", None, "2026-11-02")  # null email = cleared in the CRM
    assert _scalar("SELECT status::text FROM enrolments") == status == "Allocated — awaiting first regular class"
    assert _scalar("SELECT count(*) FROM batch_allocations WHERE batch_id = :b AND status = 'Active'", b=batch.batch_id) == 1
    assert _scalar("SELECT count(*) FROM student_activations") == 1
    assert _scalar("SELECT count(*) FROM users WHERE student_id IS NOT NULL") == 1


def test_a_field_the_crm_does_not_send_is_kept(catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data(name_te="అన్విత"))
    crm_event("AdmissionQualified", helpers.admission_data(), source_version=2)  # no name_te key at all
    assert _scalar("SELECT name_te FROM students") == "అన్విత"
    crm_event("AdmissionQualified", helpers.admission_data(name_te=None), source_version=3)
    assert _scalar("SELECT name_te FROM students") is None

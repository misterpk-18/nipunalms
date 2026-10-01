"""What the CRM stores about the LMS: lms_user_id, per-admission lms_status, batch link; outbox and pull endpoint."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config.database import db
from models import Batch, CrmOutbox
from tests import helpers
from tests.conftest import SERVICE_KEY

STATUS = "/api/v1/integrations/crm/status"
HEADERS = {"X-Service-Key": SERVICE_KEY}


def lms_status(admission_id: int) -> str:
    return db.session.execute(db.text("SELECT lms_status::text FROM admission_lms_status WHERE admission_id = :a"),
                              {"a": admission_id}).scalar_one()


def outbox(event_type=None) -> list[CrmOutbox]:
    stmt = select(CrmOutbox).order_by(CrmOutbox.outbox_id)
    if event_type:
        stmt = stmt.where(CrmOutbox.event_type == event_type)
    return list(db.session.execute(stmt).scalars())


def status_changes(crm_admission_id=None) -> list[str]:
    return [o.payload["lms_status"] for o in outbox("AdmissionLmsStatusChanged")
            if crm_admission_id in (None, o.payload["crm_admission_id"])]


# ---------------------------------------------------------------- lms_user_id

def test_lms_user_id_is_the_student_code_and_stays_the_same(client, catalog, crm_event):
    first = crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-x").get_json()["data"]["result"]
    replay = crm_event("AdmissionQualified", helpers.admission_data(), event_id="evt-x").get_json()["data"]["result"]
    second = crm_event("AdmissionQualified", helpers.admission_data(admission_id="A-101", course="NIT-CRS-019")).get_json()["data"]["result"]
    updated = crm_event("AdmissionQualified", helpers.admission_data(name="Anvitha Kolli"), source_version=2).get_json()["data"]["result"]

    ids = {first["lms_user_id"], replay["lms_user_id"], second["lms_user_id"], updated["lms_user_id"]}

    assert ids == {first["student_code"]} and len(ids) == 1
    assert len(outbox("LmsAccountProvisioned")) == 1  # provisioned once, however many admissions and replays


def test_lms_user_id_and_codes_cannot_be_changed_and_students_are_never_deleted(client, catalog, crm_event, run_sql):
    import pytest
    from sqlalchemy.exc import DBAPIError

    crm_event("AdmissionQualified", helpers.admission_data())

    for statement in ("UPDATE students SET lms_user_id = 'X'", "UPDATE students SET student_code = 'X'",
                      "UPDATE students SET crm_person_id = 'X'", "DELETE FROM students"):
        with pytest.raises(DBAPIError):
            run_sql(statement)
        db.session.rollback()


def test_provisioning_is_reported_with_the_persons_ids(client, catalog, crm_event):
    result = crm_event("AdmissionQualified", helpers.admission_data(person_id="CRM-77")).get_json()["data"]["result"]

    (row,) = outbox("LmsAccountProvisioned")

    assert row.status == "Pending"
    assert row.payload["crm_person_id"] == "CRM-77" and row.payload["lms_user_id"] == result["student_code"]
    assert datetime.fromisoformat(row.payload["provisioned_at"]).tzinfo is not None


# ---------------------------------------------------------------- lms_status transitions

def test_status_moves_from_not_created_to_invited_to_active_to_inactive_and_completed(client, catalog, crm_event, make_student, run_sql):
    student = make_student(activate=False)
    admission_id = student.admission_id

    assert lms_status(admission_id) == "Invited"
    assert student.enrolments[0]["status"] == "Allocation Pending"

    activated = client.post("/api/v1/auth/activate", json={"token": student.token, "password": "My-own-passw0rd"})
    assert activated.status_code == 200
    assert lms_status(admission_id) == "Active"

    crm_admission_id = db.session.execute(db.text("SELECT crm_admission_id FROM admissions")).scalar_one()
    crm_event("AdmissionUpdated", {"crm_admission_id": crm_admission_id, "status": "Paused"}, source_version=2)
    assert lms_status(admission_id) == "Inactive"

    crm_event("AdmissionUpdated", {"crm_admission_id": crm_admission_id, "status": "Active"}, source_version=3)
    assert lms_status(admission_id) == "Active"

    run_sql("UPDATE enrolments SET status = 'Completed'")
    assert lms_status(admission_id) == "Completed"

    assert status_changes() == ["Invited", "Active", "Inactive", "Active", "Completed"]


def test_status_not_created_without_an_lms_login(client, catalog, crm_event, run_sql):
    result = crm_event("AdmissionQualified", helpers.admission_data()).get_json()["data"]["result"]

    run_sql("UPDATE students SET provisioned_at = NULL")

    assert lms_status(result["admission_id"]) == "Not Created"


def test_cancelling_and_suspending_make_an_admission_inactive(client, catalog, crm_event, make_student, run_sql):
    cancelled = make_student()
    suspended = make_student()

    crm_event("AdmissionCancelled", {"crm_admission_id": db.session.execute(
        db.text("SELECT crm_admission_id FROM admissions WHERE admission_id = :a"), {"a": cancelled.admission_id}).scalar_one()},
        source_version=2)
    run_sql("UPDATE students SET activation_status = 'Suspended' WHERE student_id = :s", s=suspended.student_id)

    assert lms_status(cancelled.admission_id) == "Inactive"
    assert lms_status(suspended.admission_id) == "Inactive"


def test_status_is_per_admission_not_per_student(client, catalog, crm_event, make_student, run_sql):
    student = make_student(person_id="P-9", admission_id="A-1")
    crm_event("AdmissionQualified", helpers.admission_data(person_id="P-9", admission_id="A-2", course="NIT-CRS-019"))
    second_id = db.session.execute(db.text("SELECT admission_id FROM admissions WHERE crm_admission_id = 'A-2'")).scalar_one()

    run_sql("UPDATE enrolments SET status = 'Completed' WHERE admission_id = :a", a=student.admission_id)

    assert lms_status(student.admission_id) == "Completed"
    assert lms_status(second_id) == "Active"


def test_one_outbox_row_per_status_change_and_none_for_unchanged_status(client, catalog, crm_event, make_student, login):
    student = make_student(admission_id="A-1")
    before = len(outbox())

    client.post("/api/v1/auth/login", json={"login": student.student_code, "password": "Correct-horse-1"})  # activity only
    crm_event("AdmissionUpdated", {"crm_admission_id": "A-1", "mode": "Hybrid"}, source_version=2)  # no status change

    assert len(outbox()) == before
    assert status_changes("A-1") == ["Invited", "Active"]


def test_admission_lms_status_view_carries_last_activity(client, catalog, make_student):
    student = make_student()
    assert db.session.execute(db.text("SELECT lms_last_activity_at FROM admission_lms_status WHERE admission_id = :a"),
                              {"a": student.admission_id}).scalar_one() is None  # not started

    client.post("/api/v1/auth/login", json={"login": student.student_code, "password": "Correct-horse-1"})

    assert db.session.execute(db.text("SELECT lms_last_activity_at FROM admission_lms_status WHERE admission_id = :a"),
                              {"a": student.admission_id}).scalar_one() is not None


# ---------------------------------------------------------------- batch link

def test_linking_a_crm_batch_queues_batch_linked_once_per_change(app, catalog, make_batch, run_sql):
    batch = make_batch(crm_batch_id="CRM-B-1")

    (row,) = outbox("BatchLinked")
    assert row.payload == {"crm_batch_id": "CRM-B-1", "lms_course_id": batch.batch_code}

    run_sql("UPDATE batches SET capacity = 40")  # unrelated change
    assert len(outbox("BatchLinked")) == 1
    run_sql("UPDATE batches SET crm_batch_id = 'CRM-B-2'")
    assert [o.payload["crm_batch_id"] for o in outbox("BatchLinked")] == ["CRM-B-1", "CRM-B-2"]
    assert make_batch().crm_batch_id is None and len(outbox("BatchLinked")) == 2  # unlinked batches queue nothing


def test_crm_batch_is_mirrored_when_the_lms_batch_is_linked(client, catalog, crm_event, make_batch):
    batch = make_batch(crm_batch_id="CRM-B-1", state="Running")
    enrolment = {"course_code": "NIT-CRS-047", "crm_batch_id": "CRM-B-1"}

    result = crm_event("AdmissionQualified", helpers.admission_data(enrolments=[enrolment])).get_json()["data"]["result"]

    assert result["enrolments"][0]["status"] == "Allocated — awaiting first regular class"
    assert result["warnings"] == []
    seats = db.session.execute(db.text("SELECT batch_id, status::text FROM batch_allocations")).all()
    assert seats == [(batch.batch_id, "Active")]


def test_unlinked_or_full_crm_batches_leave_the_enrolment_unallocated_with_a_warning(client, catalog, crm_event, make_batch):
    make_batch(crm_batch_id="CRM-FULL", capacity=1)
    crm_event("AdmissionQualified", helpers.admission_data(
        person_id="P-1", admission_id="A-1", email="p1@example.test", enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "CRM-FULL"}]))

    full = crm_event("AdmissionQualified", helpers.admission_data(
        person_id="P-2", admission_id="A-2", email="p2@example.test", enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "CRM-FULL"}]))
    unlinked = crm_event("AdmissionQualified", helpers.admission_data(
        person_id="P-3", admission_id="A-3", email="p3@example.test", enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "CRM-NONE"}]))

    for response, phrase in ((full, "is full"), (unlinked, "not linked")):
        result = response.get_json()["data"]["result"]
        assert result["enrolments"][0]["status"] == "Allocation Pending"
        assert phrase in result["warnings"][0]


def test_admission_updated_can_allocate_to_a_linked_batch(client, catalog, crm_event, make_batch):
    batch = make_batch(crm_batch_id="CRM-B-1")
    crm_event("AdmissionQualified", helpers.admission_data())

    response = crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "enrolments": [
        {"course_code": "NIT-CRS-047", "crm_batch_id": "CRM-B-1"}]}, source_version=2)

    assert response.status_code == 201
    assert db.session.execute(db.text("SELECT status::text FROM enrolments")).scalar_one() == "Allocated — awaiting first regular class"
    assert db.session.execute(db.text("SELECT batch_id FROM batch_allocations")).scalar_one() == batch.batch_id


# ---------------------------------------------------------------- pull endpoint

def test_status_endpoint_needs_the_service_key(client):
    assert client.get(STATUS).status_code == 401
    assert client.get(STATUS, headers={"X-Service-Key": "wrong"}).status_code == 401
    assert client.get(STATUS, headers=HEADERS).status_code == 200


def test_status_endpoint_returns_what_changed_since(client, catalog, crm_event, make_student, make_batch):
    before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    student = make_student(person_id="CRM-P-5", admission_id="CRM-A-5")
    make_batch(crm_batch_id="CRM-B-5")

    data = client.get(STATUS, headers=HEADERS, query_string={"since": before}).get_json()["data"]

    assert data["persons"] == [{"crm_person_id": "CRM-P-5", "lms_user_id": student.student_code,
                                "lms_provisioned_at": data["persons"][0]["lms_provisioned_at"]}]
    assert data["persons"][0]["lms_provisioned_at"]
    (admission,) = data["admissions"]
    assert admission["crm_admission_id"] == "CRM-A-5" and admission["lms_status"] == "Active"
    assert admission["lms_last_activity_at"] is None and admission["lms_last_synced_at"]
    (batch,) = [b for b in data["batches"] if b["crm_batch_id"] == "CRM-B-5"]
    assert batch["lms_course_id"] == db.session.execute(select(Batch.batch_code).where(Batch.crm_batch_id == "CRM-B-5")).scalar_one()
    assert batch["course_code"] and batch["branch_code"] and batch["status"] in ("Planned", "Open", "In Progress")


def test_status_endpoint_is_empty_when_nothing_changed_and_reports_new_activity(client, catalog, make_student, run_sql):
    student = make_student(admission_id="CRM-A-6")
    after = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    empty = client.get(STATUS, headers=HEADERS, query_string={"since": after}).get_json()["data"]
    assert (empty["persons"], empty["admissions"], empty["batches"]) == ([], [], [])

    # The status itself changed long ago; only new learning activity can make the admission show up again
    run_sql("UPDATE admission_lms_state SET status_changed_at = now() - interval '1 hour', changed_at = now() - interval '1 hour'")
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    assert client.get(STATUS, headers=HEADERS, query_string={"since": since}).get_json()["data"]["admissions"] == []

    client.post("/api/v1/auth/login", json={"login": student.student_code, "password": "Correct-horse-1"})
    active = client.get(STATUS, headers=HEADERS, query_string={"since": since}).get_json()["data"]

    assert [a["crm_admission_id"] for a in active["admissions"]] == ["CRM-A-6"]
    assert active["admissions"][0]["lms_last_activity_at"] is not None


def test_status_since_must_be_a_timestamp(client):
    assert client.get(STATUS, headers=HEADERS, query_string={"since": "yesterday"}).status_code == 400
    assert client.get(STATUS, headers=HEADERS, query_string={"since": "2026-09-01T00:00:00Z"}).status_code == 200

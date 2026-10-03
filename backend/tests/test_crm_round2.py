"""The status pull the CRM applies in round 2 (docs/CRM_INTEGRATION.md §5, db 095)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from config.database import db
from tests import helpers
from tests.test_certificates import issued, w  # noqa: F401  (w is the shared attendance-world fixture)

STATUS = "/api/v1/integrations/crm/status"
HEADERS = {"X-Service-Key": "test-crm-service-key"}


def _pull(client, since: str) -> dict:
    response = client.get(STATUS, headers=HEADERS, query_string={"since": since})
    assert response.status_code == 200
    return response.get_json()["data"]


def _scalar(sql: str, **params):
    return db.session.execute(text(sql), params).scalar_one()


# ---------------------------------------------------------------- Q1: as_of as the next since

def test_pulling_again_from_as_of_returns_nothing_when_nothing_changed(client, catalog, crm_event, make_batch):
    before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    make_batch(crm_batch_id="17")
    crm_event("AdmissionQualified", helpers.admission_data(person_id="21", admission_id="6"))

    first = _pull(client, before)
    second = _pull(client, first["as_of"])

    assert [a["crm_admission_id"] for a in first["academics"]] == ["6"] and first["persons"] and first["batches"]
    assert {k: second[k] for k in ("persons", "admissions", "academics", "batches", "certificates")} == \
        {"persons": [], "admissions": [], "academics": [], "batches": [], "certificates": []}


def test_as_of_stays_below_a_transaction_that_is_still_open(client, app):
    """Its rows will be stamped with its start time and appear only at commit: the next pull must still return them."""
    other = db.engine.connect()
    try:
        other.begin()
        started = other.execute(text("SELECT now()")).scalar_one()  # CURRENT_TIMESTAMP of everything it will write

        as_of = datetime.fromisoformat(_pull(client, "2026-01-01T00:00:00+00:00")["as_of"])

        assert as_of < started
    finally:
        other.rollback()
        other.close()

    assert datetime.fromisoformat(_pull(client, "2026-01-01T00:00:00+00:00")["as_of"]) >= started


def test_provisioning_is_stamped_by_the_database_clock(client, catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data())

    assert _scalar("SELECT provisioned_at = now() FROM students WHERE crm_person_id = 'P-100'") is True


def test_late_recorded_activity_is_still_pulled(client, catalog, make_student, run_sql):
    """Activity recorded now with an earlier occurred_at moves last activity, so the admission changed now."""
    student = make_student(admission_id="CRM-A-7")
    run_sql("UPDATE admission_lms_state SET status_changed_at = now() - interval '1 hour', changed_at = now() - interval '1 hour'")
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    assert _pull(client, since)["admissions"] == []

    run_sql("INSERT INTO activity_events (student_id, kind, occurred_at) VALUES (:s, 'resource_view', now() - interval '2 days')",
            s=student.student_id)
    (admission,) = _pull(client, since)["admissions"]

    assert admission["crm_admission_id"] == "CRM-A-7"
    assert datetime.fromisoformat(admission["lms_last_activity_at"]) < datetime.fromisoformat(since)


# ---------------------------------------------------------------- Q2: what the CRM mirrors is never deleted

@pytest.mark.parametrize("table", ["batches", "batch_allocations"])
def test_batches_and_allocations_cannot_be_deleted(client, catalog, crm_event, make_batch, run_sql, table):
    make_batch(crm_batch_id="GNT-B-0007")
    crm_event("AdmissionQualified", helpers.admission_data(enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]))
    assert _scalar("SELECT count(*) FROM batch_allocations") == 1

    with pytest.raises(DBAPIError, match="never deleted"):
        run_sql(f"DELETE FROM {table}")


def test_a_numbered_certificate_cannot_be_deleted_but_an_unnumbered_draft_can(client, w, run_sql):
    cid, _ = issued(client, w)
    run_sql("""INSERT INTO certificates (certificate_type, enrolment_id, student_id, course_id, branch_id, holder_name)
               SELECT 'Internship Certificate', enrolment_id, student_id, course_id, branch_id, holder_name
               FROM certificates WHERE certificate_id = :c""", c=cid)

    run_sql("DELETE FROM certificates WHERE certificate_number IS NULL")
    with pytest.raises(DBAPIError, match="never deleted"):
        run_sql("DELETE FROM certificates WHERE certificate_id = :c", c=cid)


# ---------------------------------------------------------------- Q4: combo allocations per track

def test_a_combo_allocation_names_its_track_and_component_course(client, catalog, crm_event, make_batch, run_sql):
    crm_event("AdmissionQualified", helpers.combo_admission_data())
    combo_batch = make_batch(course_code="NIT-CRS-018")
    run_sql("""INSERT INTO batch_allocations (enrolment_id, enrolment_track_id, batch_id)
               SELECT t.enrolment_id, t.enrolment_track_id, :b FROM enrolment_tracks t
               JOIN course_components c ON c.component_id = t.component_id
               WHERE c.track_code IN ('NIT-CRS-018/T1', 'NIT-CRS-019') ORDER BY c.sort_order""",
            b=combo_batch.batch_id)

    academic = _scalar("SELECT academic FROM admission_lms_state s JOIN admissions a USING (admission_id) WHERE a.crm_admission_id = 'A-100'")

    # A main track with no course of its own reports the combo's code; the included booster its own course
    assert [(a["course_code"], a["track_code"], a["lms_course_id"], a["status"]) for a in academic["allocations"]] == \
        [("NIT-CRS-018", "NIT-CRS-018/T1", combo_batch.batch_code, "Active"),
         ("NIT-CRS-019", "NIT-CRS-019", combo_batch.batch_code, "Active")]


def test_a_single_course_allocation_has_no_track(client, catalog, crm_event, make_batch):
    make_batch(crm_batch_id="GNT-B-0007")
    crm_event("AdmissionQualified", helpers.admission_data(enrolments=[{"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]))

    (allocation,) = _scalar("SELECT academic FROM admission_lms_state")["allocations"]

    assert (allocation["course_code"], allocation["track_code"]) == ("NIT-CRS-047", None)


# ---------------------------------------------------------------- the CRM's batch-allocation escalation, now in the LMS

def test_an_enrolment_without_a_seat_a_day_before_its_start_is_escalated_once(client, catalog, crm_event, make_user):
    from config.timezone import today_ist
    from services import batch_allocations

    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    for admission_id, days in (("A-101", 1), ("A-102", 5), ("A-103", 0)):
        data = helpers.admission_data(person_id=f"P-{admission_id}", admission_id=admission_id, email=f"{admission_id}@example.test")
        data["admission"]["planned_start_date"] = (today_ist() + timedelta(days=days)).isoformat()
        assert crm_event("AdmissionQualified", data).status_code == 201
    crm_event("AdmissionCancelled", {"crm_admission_id": "A-103", "reason": "Refund"}, source_version=2)

    assert batch_allocations.escalate_unallocated() == 1
    assert batch_allocations.escalate_unallocated() == 0  # once per enrolment
    titles = list(db.session.execute(text("SELECT title FROM notifications WHERE recipient_user_id = :u AND action_status = 'Open'"),
                                      {"u": manager.user_id}).scalars())
    assert [t for t in titles if t.startswith("Allocate a batch now")] == \
        [f"Allocate a batch now: Anvitha K. (ADM-GNT-2026-000101) starts {(today_ist() + timedelta(days=1)).isoformat()}"]

"""db 005: events exactly as the live CRM would send them, and the academic / batch state the LMS sends back."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.database import db
from tests import helpers

HEADERS = {"X-Service-Key": "test-crm-service-key"}
STATUS = "/api/v1/integrations/crm/status"


def _outbox(event_type: str) -> list[dict]:
    rows = db.session.execute(text("SELECT payload FROM crm_outbox WHERE event_type = :t ORDER BY outbox_id"), {"t": event_type})
    return [row[0] for row in rows]


def _scalar(sql: str, **params):
    return db.session.execute(text(sql), params).scalar_one()


# ---------------------------------------------------------------- CRM → LMS in the CRM's own vocabulary

def test_admission_in_crm_vocabulary_is_mapped(client, catalog, crm_event):
    data = helpers.admission_data()
    data["person"] = {"crm_person_id": 148, "person_code": "PER-GNT-00148", "full_name": "Anvitha K.",
                      "phone": "+919876543210", "preferred_language": "Telugu"}
    data["admission"].update(crm_admission_id=214, admission_code="NIT-GNT-2026-000214", delivery_mode="Online",
                             seat_type="Future Plan", planned_start_date="2026-10-12")
    data["admission"].pop("mode")
    del data["enrolments"]  # a CRM admission is one course

    response = crm_event("AdmissionQualified", data)

    assert response.status_code == 201, response.get_json()
    row = db.session.execute(text(
        "SELECT s.crm_person_id, s.crm_person_code, s.mobile, s.preferred_language, a.crm_admission_id, a.mode::text,"
        " a.seat_type, a.planned_start_date::text, e.kind::text, e.mode::text"
        " FROM students s JOIN admissions a USING (student_id) JOIN enrolments e USING (admission_id)")).one()
    assert tuple(row) == ("148", "PER-GNT-00148", "+919876543210", "te", "214", "Live Online", "Future Plan",
                          "2026-10-12", "Standalone", "Live Online")


def test_course_upserted_from_crm_combo_courses_derives_tracks(client, crm_event):
    for code, title in (("NIT-CRS-101", "Python & SQL Foundations"), ("NIT-CRS-102", "Machine Learning"),
                        ("NIT-CRS-019", "Microsoft Power BI")):
        assert crm_event("CourseUpserted", {"course_code": code, "course_title": title, "category": "Data"}).status_code == 201
    combo = {"course_code": "NIT-CRS-018", "course_title": "Data Science combo", "is_combo": True, "status": "Active",
             "components": [{"component_course_code": "NIT-CRS-102", "is_bonus": False, "sort_order": 2},
                            {"component_course_code": "NIT-CRS-101", "is_bonus": False, "sort_order": 1},
                            {"component_course_code": "NIT-CRS-019", "is_bonus": True, "sort_order": 3}]}

    assert crm_event("CourseUpserted", combo).status_code == 201
    assert crm_event("CourseUpserted", combo, source_version=2).status_code == 201  # a re-send changes nothing

    tracks = db.session.execute(text("SELECT track_code, track_name, role::text FROM course_components ORDER BY sort_order")).all()
    assert [tuple(t) for t in tracks] == [("NIT-CRS-018/T1", "Python & SQL Foundations", "Main track"),
                                          ("NIT-CRS-018/T2", "Machine Learning", "Main track"),
                                          ("NIT-CRS-019", "Microsoft Power BI", "Included booster")]


def test_archived_course_is_accepted(client, crm_event):
    response = crm_event("CourseUpserted", {"course_code": "NIT-CRS-900", "title": "Retired course", "status": "Archived"})
    assert response.status_code == 201
    assert _scalar("SELECT status::text FROM courses WHERE course_code = 'NIT-CRS-900'") == "Archived"


def test_complimentary_course_as_its_own_crm_admission(client, catalog, crm_event):
    assert crm_event("AdmissionQualified", helpers.admission_data(admission_id="A-1")).status_code == 201
    free = helpers.admission_data(admission_id="A-2", course="NIT-CRS-052")
    free["admission"].update(complimentary_of_crm_admission_id="A-1", access_until="2027-03-31")
    del free["enrolments"]

    response = crm_event("AdmissionQualified", free)

    assert response.status_code == 201, response.get_json()
    row = db.session.execute(text(
        "SELECT e.kind::text, e.benefit_gate_met, e.access_end::text, p.admission_id = paid.admission_id,"
        "       a.complimentary_of_admission_id = paid.admission_id"
        " FROM enrolments e JOIN admissions a ON a.admission_id = e.admission_id"
        " JOIN enrolments p ON p.enrolment_id = e.parent_enrolment_id"
        " JOIN admissions paid ON paid.crm_admission_id = 'A-1' WHERE a.crm_admission_id = 'A-2'")).one()
    assert tuple(row) == ("Complimentary", True, "2027-03-31", True, True)
    # One student for both admissions; each admission has its own LMS status for the CRM
    assert _scalar("SELECT count(*) FROM students") == 1
    assert _scalar("SELECT count(*) FROM admission_lms_state") == 2


def test_complimentary_before_its_paid_admission_fails_and_can_be_retried(client, catalog, crm_event):
    free = helpers.admission_data(admission_id="A-2", course="NIT-CRS-052")
    free["admission"]["complimentary_of_crm_admission_id"] = "A-1"
    del free["enrolments"]

    first = crm_event("AdmissionQualified", free, event_id="free-1")
    assert first.status_code == 422 and "A-1" in first.get_json()["error"]["message"]

    crm_event("AdmissionQualified", helpers.admission_data(admission_id="A-1"))
    assert crm_event("AdmissionQualified", free, event_id="free-1").status_code == 200  # same event again: applied now
    assert _scalar("SELECT status::text FROM crm_events WHERE event_id = 'free-1'") == "Applied"


def test_finance_summary_carries_the_crm_balances(client, catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data())
    data = helpers.finance_data(pending_verification=5000, waived="0", refunded=0, payment_completion="Part Paid",
                                invoice_numbers=["INV-GNT-2627-0001"],
                                installments=[{"installment_no": 1, "due_date": "2026-09-28", "amount": 15000, "covered": 10000,
                                               "balance": 5000, "due_position": "Overdue"},
                                              {"installment_no": 2, "due_date": "2026-10-10", "amount": 15000}])

    assert crm_event("FinanceSummaryUpdated", data).status_code == 201
    row = db.session.execute(text("SELECT pending_verification::text, payment_completion, invoice_numbers, installments"
                                  " FROM finance_summaries")).one()
    assert row[0] == "5000.00" and row[1] == "Part Paid" and row[2] == ["INV-GNT-2627-0001"]
    assert row[3][0] == {"installment_no": 1, "due_date": "2026-09-28", "amount": "15000.00", "covered": "10000.00",
                         "balance": "5000.00", "due_position": "Overdue"}
    assert row[3][1]["covered"] == "0.00"


# ---------------------------------------------------------------- LMS → CRM: academic state per admission

def test_academic_state_follows_the_enrolment_in_crm_vocabulary(client, catalog, crm_event, make_batch, run_sql):
    batch = make_batch(crm_batch_id="GNT-B-0007")
    crm_event("AdmissionQualified", helpers.admission_data())
    (queued,) = _outbox("AdmissionAcademicsChanged")
    assert queued["crm_admission_id"] == "A-100"
    assert (queued["enrolment_status"], queued["curriculum_status"], queued["curriculum_version_label"]) == \
        ("Awaiting Batch Allocation", "Mapped", "CV 5.1")
    assert queued["allocations"] == [] and queued["joining_date"] is None

    crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "enrolments": [
        {"course_code": "NIT-CRS-047", "crm_batch_id": "GNT-B-0007"}]}, source_version=2)
    scheduled = _outbox("AdmissionAcademicsChanged")[-1]
    assert scheduled["enrolment_status"] == "Scheduled"
    assert [(a["course_code"], a["lms_course_id"], a["crm_batch_id"], a["status"]) for a in scheduled["allocations"]] == \
        [("NIT-CRS-047", batch.batch_code, "GNT-B-0007", "Active")]

    run_sql("UPDATE enrolments SET joining_date = DATE '2026-10-01', status = 'Active'")
    joined = _outbox("AdmissionAcademicsChanged")[-1]
    assert joined["enrolment_status"] == "In Progress" and joined["joining_date"] == "2026-10-01"
    assert joined["allocations"][0]["joining_date"] == "2026-10-01"

    run_sql("UPDATE enrolments SET status = 'Completed'")
    completed = _outbox("AdmissionAcademicsChanged")[-1]
    assert completed["enrolment_status"] == "Completed" and completed["academic_completed_at"]


def test_academic_state_is_queued_once_per_change(client, catalog, crm_event, run_sql):
    crm_event("AdmissionQualified", helpers.admission_data())
    run_sql("UPDATE crm_outbox SET status = 'Delivered', delivered_at = now()")
    run_sql("UPDATE enrolments SET benefit_note = 'unrelated'")
    run_sql("UPDATE enrolments SET status = status")
    assert len(_outbox("AdmissionAcademicsChanged")) == 1  # nothing the CRM shows changed

    run_sql("UPDATE enrolments SET status = 'Paused'")
    run_sql("UPDATE enrolments SET status = 'Allocation Pending'")  # before delivery: one pending row, latest state
    assert [p["enrolment_status"] for p in _outbox("AdmissionAcademicsChanged")] == \
        ["Awaiting Batch Allocation", "Awaiting Batch Allocation"]


def test_unmapped_curriculum_reports_mapping_pending(client, catalog, crm_event):
    crm_event("AdmissionQualified", helpers.admission_data(course="NIT-CRS-052"))

    (queued,) = _outbox("AdmissionAcademicsChanged")
    assert (queued["enrolment_status"], queued["curriculum_status"], queued["curriculum_version_label"]) == \
        ("Awaiting Batch Allocation", "Mapping Pending", None)


def test_combo_admission_reports_its_combo_enrolment(client, catalog, crm_event):
    crm_event("AdmissionQualified", helpers.combo_admission_data())
    (queued,) = [p for p in _outbox("AdmissionAcademicsChanged") if p["crm_admission_id"] == "A-100"][-1:]

    # The combo is one CRM admission (the complimentary 052 enrolment rides on it here, as in the prototype)
    assert queued["enrolment_status"] == "Awaiting Batch Allocation" and queued["curriculum_status"] == "Mapped"


# ---------------------------------------------------------------- LMS → CRM: batches

def test_batch_is_mirrored_to_the_crm_in_its_vocabulary(client, catalog, make_batch, make_user, run_sql):
    trainer = make_user(roles=[("TRAINER", 1)], email="trainer.g1@nipuna.test")
    batch = make_batch(trainers=(trainer,), mode="Live Online", planned_start=datetime(2026, 10, 1).date(), capacity=25)

    (queued,) = _outbox("BatchUpserted")
    assert queued == {"lms_course_id": batch.batch_code, "crm_batch_id": None, "course_code": "NIT-CRS-047",
                      "branch_code": "NIT-GNT", "delivery_mode": "Online", "status": "Planned", "capacity": 25,
                      "start_date": "2026-10-01", "end_date": None, "curriculum_version_label": None,
                      "lead_trainer_email": "trainer.g1@nipuna.test", "trainer_emails": ["trainer.g1@nipuna.test"]}

    run_sql("UPDATE batches SET state = 'Running' WHERE batch_id = :id", id=batch.batch_id)
    (latest,) = _outbox("BatchUpserted")  # not yet delivered: the pending row now carries the latest state
    assert latest["status"] == "In Progress"

    run_sql("UPDATE crm_outbox SET status = 'Delivered', delivered_at = now()")
    run_sql("UPDATE batches SET readiness_reason = NULL WHERE batch_id = :id", id=batch.batch_id)  # not shown to the CRM
    run_sql("UPDATE batches SET state = 'Completed' WHERE batch_id = :id", id=batch.batch_id)
    assert [p["status"] for p in _outbox("BatchUpserted")] == ["In Progress", "Completed"]


def test_status_pull_includes_academics_and_batches(client, catalog, crm_event, make_batch):
    before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    make_batch(crm_batch_id="GNT-B-0001")
    crm_event("AdmissionQualified", helpers.admission_data())

    data = client.get(STATUS, headers=HEADERS, query_string={"since": before}).get_json()["data"]

    assert [a["crm_admission_id"] for a in data["academics"]] == ["A-100"]
    assert data["academics"][0]["enrolment_status"] == "Awaiting Batch Allocation"
    assert [b["crm_batch_id"] for b in data["batches"]] == ["GNT-B-0001"]

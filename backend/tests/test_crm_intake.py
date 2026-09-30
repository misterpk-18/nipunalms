"""CRM event intake: courses, admissions, idempotency, stale events, cancellation, finance."""
from sqlalchemy import func, select

from config.database import db
from models import Admission, CrmEvent, Enrolment, FinanceSummary, Notification, Student, User
from tests import helpers
from tests.conftest import SERVICE_KEY

EVENTS = "/api/v1/integrations/crm/events"


def count(model) -> int:
    return db.session.execute(select(func.count()).select_from(model)).scalar()


def qualify(crm_event, data=None, **kwargs):
    response = crm_event("AdmissionQualified", data or helpers.admission_data(), **kwargs)
    assert response.status_code in (200, 201), response.get_json()
    return response.get_json()["data"]


# ---------------------------------------------------------------- service key

def test_events_need_the_service_key(crm_event, client):
    assert crm_event("CourseUpserted", {}, key=None).status_code == 401
    assert crm_event("CourseUpserted", {}, key="wrong-key").status_code == 401
    assert client.get(EVENTS).status_code == 401  # the inbox listing is for Super Admin sessions, not the service key


def test_envelope_is_validated(client):
    response = client.post(EVENTS, json={"event_type": "Nope"}, headers={"X-Service-Key": SERVICE_KEY})

    assert response.status_code == 400
    assert set(response.get_json()["error"]["details"]) >= {"event_id", "event_type", "source_version", "occurred_at", "data"}


# ---------------------------------------------------------------- CourseUpserted

def test_course_upserted_creates_the_combo_structure(catalog, client, make_user, login):
    admin = make_user(roles=[("SUPER_ADMIN", None)])

    courses = client.get("/api/v1/reference/courses", headers=login(admin.email)).get_json()["data"]

    combo = next(c for c in courses if c["course_code"] == "NIT-CRS-018")
    assert combo["is_combo"] is True
    assert [c["track_code"] for c in combo["components"]] == [
        "NIT-CRS-018/T1", "NIT-CRS-018/T2", "NIT-CRS-018/T3", "NIT-CRS-019"]
    assert combo["components"][3]["role"] == "Included booster"
    assert combo["components"][3]["component_course"]["course_code"] == "NIT-CRS-019"


def test_course_upserted_updates_and_ignores_older_versions(catalog, crm_event):
    newer = {"course_code": "NIT-CRS-047", "title": "Java Full Stack Developer v2"}
    assert crm_event("CourseUpserted", newer, source_version=3).status_code == 201

    older = crm_event("CourseUpserted", {"course_code": "NIT-CRS-047", "title": "Old title"}, source_version=2)

    assert older.get_json()["data"]["status"] == "Ignored — stale"
    title = db.session.execute(db.text("SELECT title FROM courses WHERE course_code = 'NIT-CRS-047'")).scalar()
    assert title == "Java Full Stack Developer v2"


def test_course_with_an_unknown_component_course_fails_and_is_stored(crm_event):
    data = {"course_code": "NIT-CRS-900", "title": "Combo", "is_combo": True,
            "components": [{"track_code": "NIT-CRS-900/T1", "track_name": "T1", "component_course_code": "NIT-CRS-404"}]}

    response = crm_event("CourseUpserted", data, event_id="evt-bad-course")

    assert response.status_code == 422
    event = db.session.execute(select(CrmEvent).where(CrmEvent.event_id == "evt-bad-course")).scalar_one()
    assert event.status == "Failed" and "NIT-CRS-404" in event.error


# ---------------------------------------------------------------- AdmissionQualified

def test_admission_qualified_creates_exactly_one_student_login_and_enrolment(catalog, crm_event):
    data = qualify(crm_event)

    result = data["result"]
    assert data["status"] == "Applied" and data["replayed"] is False
    assert result["student_code"].startswith("NIT-STU-")
    assert result["lms_user_id"] == result["student_code"]
    assert result["lms_status"] == "Invited"
    assert result["activation_status"] == "Activation Pending"
    assert [(e["course_code"], e["kind"], e["status"]) for e in result["enrolments"]] == [
        ("NIT-CRS-047", "Standalone", "Allocation Pending")]
    assert data["activation_token"]  # the CRM gets the raw token once

    assert (count(Student), count(Admission), count(Enrolment)) == (1, 1, 1)
    user = db.session.execute(select(User).where(User.student_id == result["student_id"])).scalar_one()
    assert user.password_hash is None and user.email == "anvitha.sample@example.test"


def test_second_admission_of_the_same_person_reuses_the_student_and_login(catalog, crm_event):
    first = qualify(crm_event)["result"]

    second = qualify(crm_event, helpers.admission_data(admission_id="A-101", course="NIT-CRS-019"))

    assert second["result"]["student_id"] == first["student_id"]
    assert second["activation_token"] is None
    assert (count(Student), count(User), count(Admission), count(Enrolment)) == (1, 1, 2, 2)


def test_combo_gets_tracks_and_complimentary_is_linked_to_the_parent(catalog, crm_event):
    result = qualify(crm_event, helpers.combo_admission_data())["result"]

    by_course = {e["course_code"]: e for e in result["enrolments"]}
    assert by_course["NIT-CRS-018"]["kind"] == "Combo" and by_course["NIT-CRS-018"]["status"] == "Allocation Pending"
    # NIT-CRS-052 has no Active curriculum version, so its complimentary enrolment waits for mapping
    assert by_course["NIT-CRS-052"]["kind"] == "Complimentary"
    assert by_course["NIT-CRS-052"]["status"] == "Curriculum Mapping Pending"

    combo = db.session.get(Enrolment, by_course["NIT-CRS-018"]["enrolment_id"])
    complimentary = db.session.get(Enrolment, by_course["NIT-CRS-052"]["enrolment_id"])
    assert complimentary.parent_enrolment_id == combo.enrolment_id
    assert complimentary.admission_id == combo.admission_id
    assert [t.component.track_code for t in combo.tracks] == [
        "NIT-CRS-018/T1", "NIT-CRS-018/T2", "NIT-CRS-018/T3", "NIT-CRS-019"]
    assert all(t.curriculum_version_id for t in combo.tracks)
    assert combo.curriculum_version.version_label == "Parent Programme v2026.1"


def test_complimentary_benefit_gate_not_met_stays_provisioning_pending(catalog, crm_event):
    data = helpers.combo_admission_data()
    data["enrolments"][1]["benefit_gate"] = {"met": False, "note": "Second instalment not yet verified"}

    result = qualify(crm_event, data)["result"]

    statuses = {e["course_code"]: e["status"] for e in result["enrolments"]}
    assert statuses["NIT-CRS-052"] == "Provisioning Pending"


def test_complimentary_needs_a_parent_and_a_gate(catalog, crm_event):
    data = helpers.combo_admission_data()
    del data["enrolments"][1]["parent_course_code"]
    del data["enrolments"][1]["benefit_gate"]

    response = crm_event("AdmissionQualified", data)

    assert response.status_code == 400
    assert set(response.get_json()["error"]["details"]["enrolments"]["1"]) == {"parent_course_code", "benefit_gate"}


def test_enrolment_waits_for_curriculum_when_no_version_is_active(catalog, crm_event):
    result = qualify(crm_event, helpers.admission_data(course="NIT-CRS-052"))["result"]

    assert result["enrolments"][0]["status"] == "Curriculum Mapping Pending"


def test_qualification_notifies_the_branch_academic_coordinator_once(catalog, crm_event, make_user):
    coordinator = make_user(roles=[("ACADEMIC_COORDINATOR", 1)])
    other_branch = make_user(roles=[("ACADEMIC_COORDINATOR", 2)])

    qualify(crm_event, event_id="evt-notify")
    qualify(crm_event, event_id="evt-notify")  # replay

    recipients = db.session.execute(select(Notification.recipient_user_id)).scalars().all()
    assert recipients == [coordinator.user_id] and other_branch.user_id not in recipients


def test_unknown_course_fails_then_succeeds_when_resent_after_the_course_arrives(client, crm_event, catalog):
    data = helpers.admission_data(course="NIT-CRS-500", enrolments=[{"course_code": "NIT-CRS-500"}])
    failed = crm_event("AdmissionQualified", data, event_id="evt-late-course")
    assert failed.status_code == 422
    assert count(Student) == 0  # the partial work of a failed event is rolled back

    assert crm_event("CourseUpserted", {"course_code": "NIT-CRS-500", "title": "New"}).status_code == 201
    retried = crm_event("AdmissionQualified", data, event_id="evt-late-course")

    assert retried.status_code == 200 and retried.get_json()["data"]["status"] == "Applied"
    event = db.session.execute(select(CrmEvent).where(CrmEvent.event_id == "evt-late-course")).scalar_one()
    assert event.retries == 1 and event.error is None
    assert count(Student) == 1


def test_super_admin_can_list_and_retry_failed_events(client, crm_event, catalog, make_user, login):
    admin = login(make_user(roles=[("SUPER_ADMIN", None)]).email)
    data = helpers.admission_data(course="NIT-CRS-501", enrolments=[{"course_code": "NIT-CRS-501"}])
    crm_event("AdmissionQualified", data, event_id="evt-retry")
    crm_event("CourseUpserted", {"course_code": "NIT-CRS-501", "title": "Later"})

    failed = client.get(f"{EVENTS}?status=Failed", headers=admin).get_json()
    event = failed["data"][0]
    assert event["event_id"] == "evt-retry" and event["payload"]["admission"]["crm_admission_id"] == "A-100"

    retried = client.post(f"{EVENTS}/{event['crm_event_id']}/retry", headers=admin)
    assert retried.status_code == 200 and retried.get_json()["data"]["status"] == "Applied"
    assert client.post(f"{EVENTS}/{event['crm_event_id']}/retry", headers=admin).status_code == 422  # only failed ones

    trainer = login(make_user(roles=[("TRAINER", 1)]).email)
    assert client.get(EVENTS, headers=trainer).status_code == 403


# ---------------------------------------------------------------- idempotency and versions

def test_replaying_an_event_returns_the_original_result_without_new_records(catalog, crm_event):
    first = qualify(crm_event, event_id="evt-replay")

    replay = qualify(crm_event, event_id="evt-replay")

    assert replay["replayed"] is True and first["replayed"] is False
    assert replay["result"] == first["result"]
    assert replay["activation_token"] is None
    assert (count(Student), count(User), count(Admission), count(Enrolment), count(CrmEvent)) == (1, 1, 1, 1, 5)  # 4 courses + 1


def test_same_event_id_with_a_different_payload_is_a_conflict(catalog, crm_event):
    qualify(crm_event, event_id="evt-conflict")

    response = crm_event("AdmissionQualified", helpers.admission_data(name="Someone Else"), event_id="evt-conflict")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "CONFLICT"


def test_older_source_version_is_ignored_and_never_overwrites_newer_state(catalog, crm_event):
    qualify(crm_event, helpers.admission_data(), source_version=5)
    assert crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "status": "Paused"}, source_version=7).status_code == 201

    stale = crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "status": "Active"}, source_version=6)
    late_qualified = crm_event("AdmissionQualified", helpers.admission_data(), source_version=4, event_id="evt-old")

    assert stale.get_json()["data"]["status"] == "Ignored — stale"
    assert late_qualified.get_json()["data"]["status"] == "Ignored — stale"
    admission = db.session.execute(select(Admission)).scalar_one()
    assert admission.crm_status == "Paused" and admission.source_version == 7
    assert db.session.execute(select(Enrolment.status)).scalar_one() == "Paused"


# ---------------------------------------------------------------- AdmissionUpdated / AdmissionCancelled

def test_pause_and_resume(catalog, crm_event):
    qualify(crm_event)

    crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "status": "Paused"}, source_version=2)
    assert db.session.execute(select(Enrolment.status)).scalar_one() == "Paused"

    crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "status": "Active", "mode": "Hybrid"}, source_version=3)
    assert db.session.execute(select(Enrolment.status)).scalar_one() == "Allocation Pending"
    assert db.session.execute(select(Enrolment.mode)).scalar_one() == "Hybrid"


def test_service_branch_transfer_moves_the_enrolments_and_asks_the_new_coordinator(catalog, crm_event, make_user):
    coordinator = make_user(roles=[("ACADEMIC_COORDINATOR", 2)])
    qualify(crm_event)

    response = crm_event("AdmissionUpdated", {"crm_admission_id": "A-100", "service_branch_code": "NIT-VIJ"}, source_version=2)

    assert response.get_json()["data"]["result"]["changes"] == ["service branch transferred"]
    assert db.session.execute(select(Enrolment.service_branch_id)).scalar_one() == 2
    assert db.session.execute(select(Admission.service_branch_id)).scalar_one() == 2
    recipients = db.session.execute(select(Notification.recipient_user_id).where(Notification.category == "Enrolment")).scalars().all()
    assert recipients == [coordinator.user_id]


def test_updating_an_unknown_admission_fails(crm_event):
    assert crm_event("AdmissionUpdated", {"crm_admission_id": "A-404", "status": "Paused"}, source_version=2).status_code == 422


def test_cancellation_withdraws_only_that_admissions_enrolments(catalog, crm_event):
    qualify(crm_event, helpers.combo_admission_data())
    qualify(crm_event, helpers.admission_data(admission_id="A-101", course="NIT-CRS-047"))

    response = crm_event("AdmissionCancelled", {"crm_admission_id": "A-100", "reason": "Refunded"}, source_version=2)

    assert response.get_json()["data"]["result"]["enrolments_withdrawn"] == 2  # the combo and its complimentary course
    rows = db.session.execute(
        select(Admission.crm_admission_id, Admission.crm_status, Enrolment.status).join(Enrolment, Enrolment.admission_id == Admission.admission_id)
        .order_by(Admission.crm_admission_id, Enrolment.enrolment_id)).all()
    assert rows == [("A-100", "Cancelled", "Withdrawn"), ("A-100", "Cancelled", "Withdrawn"),
                    ("A-101", "Active", "Allocation Pending")]


# ---------------------------------------------------------------- FinanceSummaryUpdated

def test_finance_summary_is_upserted_and_stale_versions_ignored(catalog, crm_event):
    qualify(crm_event)

    assert crm_event("FinanceSummaryUpdated", helpers.finance_data(), source_version=2).status_code == 201
    summary = db.session.execute(select(FinanceSummary)).scalar_one()
    assert str(summary.balance) == "20000.00" and summary.receipts[0]["receipt_number"] == "GNT-R-2627-00001"

    crm_event("FinanceSummaryUpdated", helpers.finance_data(verified_paid=20000, balance=10000), source_version=3)
    db.session.refresh(summary)
    assert str(summary.verified_paid) == "20000.00" and count(FinanceSummary) == 1

    stale = crm_event("FinanceSummaryUpdated", helpers.finance_data(verified_paid=1, balance=29999), source_version=2)
    db.session.refresh(summary)
    assert stale.get_json()["data"]["status"] == "Ignored — stale"
    assert str(summary.verified_paid) == "20000.00"


def test_finance_summary_for_an_unknown_admission_fails(crm_event):
    assert crm_event("FinanceSummaryUpdated", helpers.finance_data("A-404")).status_code == 422


# ---------------------------------------------------------------- curriculum mapping

def test_a_reserved_seat_waits_for_curriculum_then_the_enrolment_moves_on(catalog, crm_event, make_batch, run_sql):
    batch = make_batch(1, course_code="NIT-CRS-052", crm_batch_id="CRM-B-52")
    data = helpers.admission_data(course="NIT-CRS-052", enrolments=[{"course_code": "NIT-CRS-052", "crm_batch_id": "CRM-B-52"}])

    first = qualify(crm_event, data)["result"]
    assert first["enrolments"][0]["status"] == "Curriculum Mapping Pending"  # seat held, no curriculum yet
    assert db.session.execute(db.text("SELECT batch_id FROM batch_allocations")).scalar_one() == batch.batch_id

    run_sql("""INSERT INTO curriculum_versions (course_id, version_label, status, approved_at)
               SELECT course_id, 'CV 1.0', 'Active', now() FROM courses WHERE course_code = 'NIT-CRS-052'""")
    resent = qualify(crm_event, data, source_version=2)["result"]

    assert resent["enrolments"][0]["status"] == "Allocated — awaiting first regular class"


def test_a_booster_uses_the_version_written_for_it_in_the_combo_before_the_course_own(catalog, crm_event, run_sql):
    run_sql("""INSERT INTO curriculum_versions (course_id, component_id, version_label, status, approved_at)
               SELECT parent_course_id, component_id, 'Booster CV 1.3', 'Active', now()
               FROM course_components WHERE track_code = 'NIT-CRS-019'""")

    result = qualify(crm_event, helpers.combo_admission_data())["result"]

    combo = db.session.get(Enrolment, next(e for e in result["enrolments"] if e["kind"] == "Combo")["enrolment_id"])
    booster = next(t for t in combo.tracks if t.component.track_code == "NIT-CRS-019")
    assert booster.curriculum_version.version_label == "Booster CV 1.3"

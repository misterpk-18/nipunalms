"""Rules the database itself enforces, whatever the application does."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from models import BatchAllocation, Course, Enrolment, Student
from services import allocations
from services.errors import BusinessRule
from tests import helpers


def fails(run_sql, statement, **params):
    """The statement must be rejected by the database; the failed statement is rolled back."""
    with pytest.raises(DBAPIError):
        run_sql(statement, **params)
    db.session.rollback()


@pytest.fixture
def one_student(catalog, crm_event):
    result = crm_event("AdmissionQualified", helpers.admission_data()).get_json()["data"]["result"]
    return db.session.get(Student, result["student_id"]), db.session.get(Enrolment, result["enrolments"][0]["enrolment_id"])


# ---------------------------------------------------------------- generated codes

def test_codes_are_generated_in_the_documented_formats(one_student, make_user, make_batch, make_session):
    student, enrolment = one_student
    trainer = make_user(roles=[("TRAINER", 1)])
    batch = make_batch(1, trainers=[trainer])
    vij_batch = make_batch(2, trainers=[])
    session = make_session(batch, trainer, datetime(2026, 10, 1, 10, tzinfo=timezone.utc))

    year = datetime.now().year
    assert student.student_code == f"NIT-STU-{year}-000001" and student.lms_user_id == student.student_code
    assert enrolment.enrolment_code == "ENR-000001"
    assert batch.batch_code == f"NIT-GNT-BAT-{year}-000001"
    assert vij_batch.batch_code == f"NIT-VIJ-BAT-{year}-000001"
    assert session.session_code == "SES-000001"


def test_supplied_codes_are_kept_and_generation_skips_taken_codes(catalog, crm_event, run_sql, make_batch):
    crm_event("AdmissionQualified", helpers.admission_data(person_id="P-1", admission_id="A-1"))
    code = db.session.execute(select(Student.student_code)).scalar_one()
    counter_before = db.session.execute(db.text("SELECT last_value FROM code_counters WHERE counter_key LIKE 'STU-%'")).scalar_one()
    run_sql("UPDATE code_counters SET last_value = :v WHERE counter_key LIKE 'STU-%'", v=counter_before - 1)  # next code would collide

    crm_event("AdmissionQualified", helpers.admission_data(person_id="P-2", admission_id="A-2", email="p2@example.test"))

    codes = db.session.execute(select(Student.student_code).order_by(Student.student_id)).scalars().all()
    assert codes[0] == code and len(set(codes)) == 2
    assert make_batch(1, batch_code="NIT-GNT-BAT-2026-000042").batch_code == "NIT-GNT-BAT-2026-000042"


# ---------------------------------------------------------------- uniqueness

def test_crm_person_and_admission_ids_are_unique(one_student, run_sql):
    student, _ = one_student
    fails(run_sql, """INSERT INTO students (crm_person_id, full_name, original_branch_id, service_branch_id)
                      VALUES ('P-100', 'Duplicate', 1, 1)""")
    fails(run_sql, """INSERT INTO admissions (crm_admission_id, admission_code, student_id, course_id, original_branch_id,
                      service_branch_id, collecting_branch_id, source_version)
                      SELECT crm_admission_id, 'ADM-OTHER', student_id, course_id, 1, 1, 1, 1 FROM admissions""")


def test_one_lms_login_per_student(one_student, run_sql):
    student, _ = one_student

    fails(run_sql, "INSERT INTO users (full_name, student_id) VALUES ('Second login', :s)", s=student.student_id)


def test_a_login_needs_an_email_or_a_student(run_sql):
    fails(run_sql, "INSERT INTO users (full_name) VALUES ('Nobody')")


def test_student_ids_cannot_be_deleted(one_student, run_sql):
    fails(run_sql, "DELETE FROM students")


def test_course_codes_and_track_codes_are_unique(catalog, run_sql):
    fails(run_sql, "INSERT INTO courses (course_code, title) VALUES ('NIT-CRS-047', 'Again')")
    fails(run_sql, """INSERT INTO course_components (parent_course_id, track_code, track_name)
                      SELECT parent_course_id, track_code, 'Again' FROM course_components LIMIT 1""")


def test_only_combo_courses_have_components_and_one_active_version_each(catalog, run_sql):
    fails(run_sql, """INSERT INTO course_components (parent_course_id, track_code, track_name)
                      SELECT course_id, 'NIT-CRS-047/T1', 'Track' FROM courses WHERE course_code = 'NIT-CRS-047'""")
    fails(run_sql, """INSERT INTO curriculum_versions (course_id, version_label, status, approved_at)
                      SELECT course_id, 'CV 5.2', 'Active', now() FROM courses WHERE course_code = 'NIT-CRS-047'""")


# ---------------------------------------------------------------- enrolment rules

def test_complimentary_needs_a_parent_and_paid_ones_cannot_have_one(one_student, run_sql):
    _, enrolment = one_student
    course_id = db.session.execute(select(Course.course_id).where(Course.course_code == "NIT-CRS-052")).scalar_one()
    base = """INSERT INTO enrolments (admission_id, student_id, course_id, kind, parent_enrolment_id, service_branch_id, status)
              VALUES (:a, :s, :c, :k, :p, 1, 'Allocation Pending')"""
    common = {"a": enrolment.admission_id, "s": enrolment.student_id, "c": course_id}

    fails(run_sql, base, k="Complimentary", p=None, **common)
    fails(run_sql, base, k="Standalone", p=enrolment.enrolment_id, **common)
    run_sql(base, k="Complimentary", p=enrolment.enrolment_id, **common)  # the valid shape is accepted


def test_active_enrolment_needs_a_joining_date_and_combo_kind_matches_the_course(one_student, run_sql):
    _, enrolment = one_student

    fails(run_sql, "UPDATE enrolments SET status = 'Active'")
    fails(run_sql, "UPDATE enrolments SET kind = 'Combo'")
    run_sql("UPDATE enrolments SET status = 'Active', joining_date = CURRENT_DATE")


def test_one_enrolment_per_course_per_admission(one_student, run_sql):
    fails(run_sql, """INSERT INTO enrolments (admission_id, student_id, course_id, kind, service_branch_id, status)
                      SELECT admission_id, student_id, course_id, kind, 1, status FROM enrolments""")


# ---------------------------------------------------------------- batches

def test_batch_capacity_is_enforced_by_the_database(one_student, catalog, crm_event, make_batch, run_sql):
    _, first = one_student
    second = db.session.get(Enrolment, crm_event("AdmissionQualified", helpers.admission_data(
        person_id="P-2", admission_id="A-2", email="p2@example.test")).get_json()["data"]["result"]["enrolments"][0]["enrolment_id"])
    batch = make_batch(1, capacity=1)

    run_sql("INSERT INTO batch_allocations (enrolment_id, batch_id) VALUES (:e, :b)", e=first.enrolment_id, b=batch.batch_id)
    fails(run_sql, "INSERT INTO batch_allocations (enrolment_id, batch_id) VALUES (:e, :b)", e=second.enrolment_id, b=batch.batch_id)
    fails(run_sql, "UPDATE batches SET capacity = 0")
    run_sql("UPDATE batches SET capacity = 2")


def test_service_refuses_a_full_batch_with_a_readable_error(one_student, make_batch):
    _, enrolment = one_student
    batch = make_batch(1, capacity=1, state="Running")
    allocations.allocate(enrolment, batch)

    other = Enrolment(admission_id=enrolment.admission_id, student_id=enrolment.student_id, course_id=enrolment.course_id,
                      kind="Standalone", service_branch_id=1, status="Allocation Pending")
    with pytest.raises(BusinessRule, match="is full"):
        allocations.allocate(other, batch)


def test_one_active_allocation_per_enrolment_and_history_is_kept(one_student, make_batch, run_sql):
    _, enrolment = one_student
    first, second = make_batch(1, state="Running"), make_batch(1, state="Running")

    original = allocations.allocate(enrolment, first)
    db.session.commit()
    fails(run_sql, "INSERT INTO batch_allocations (enrolment_id, batch_id) VALUES (:e, :b)", e=enrolment.enrolment_id, b=second.batch_id)

    moved = allocations.allocate(enrolment, second)  # the service ends the first one properly

    history = db.session.execute(select(BatchAllocation.status).where(BatchAllocation.enrolment_id == enrolment.enrolment_id)
                                 .order_by(BatchAllocation.allocation_id)).scalars().all()
    assert history == ["Transferred", "Active"] and moved.batch_id == second.batch_id
    assert original.effective_to is not None


def test_allocation_must_match_course_and_branch(one_student, make_batch, run_sql):
    _, enrolment = one_student
    wrong_branch = make_batch(2)
    wrong_course = make_batch(1, course_code="NIT-CRS-019")

    for batch in (wrong_branch, wrong_course):
        fails(run_sql, "INSERT INTO batch_allocations (enrolment_id, batch_id) VALUES (:e, :b)", e=enrolment.enrolment_id, b=batch.batch_id)
        with pytest.raises(BusinessRule):
            allocations.allocate(enrolment, batch)


def test_only_trainers_of_the_branch_can_be_assigned(make_user, make_batch, run_sql):
    batch = make_batch(1)
    guntur = make_user(roles=[("TRAINER", 1)])
    vijayawada = make_user(roles=[("TRAINER", 2)])
    coordinator = make_user(roles=[("ACADEMIC_COORDINATOR", 1)])

    run_sql("INSERT INTO batch_trainers (batch_id, trainer_user_id, role) VALUES (:b, :u, 'Lead')", b=batch.batch_id, u=guntur.user_id)
    for user in (vijayawada, coordinator):
        fails(run_sql, "INSERT INTO batch_trainers (batch_id, trainer_user_id) VALUES (:b, :u)", b=batch.batch_id, u=user.user_id)


def test_only_one_lead_trainer_per_batch(make_user, make_batch, run_sql):
    batch = make_batch(1)
    first, second = make_user(roles=[("TRAINER", 1)]), make_user(roles=[("TRAINER", 1)])

    run_sql("INSERT INTO batch_trainers (batch_id, trainer_user_id, role) VALUES (:b, :u, 'Lead')", b=batch.batch_id, u=first.user_id)
    fails(run_sql, "INSERT INTO batch_trainers (batch_id, trainer_user_id, role) VALUES (:b, :u, 'Lead')", b=batch.batch_id, u=second.user_id)


def test_not_ready_batches_need_a_reason_and_dates_must_be_ordered(make_batch, run_sql):
    batch = make_batch(1)

    fails(run_sql, "UPDATE batches SET readiness = 'Blocked'")
    run_sql("UPDATE batches SET readiness = 'Blocked', readiness_reason = 'Curriculum mapping pending'")
    fails(run_sql, "UPDATE batches SET planned_start = '2026-10-10', planned_end = '2026-10-01'")


# ---------------------------------------------------------------- class sessions

def test_session_must_end_after_it_starts_and_be_taught_by_a_batch_trainer(make_user, make_batch, make_session):
    trainer, outsider = make_user(roles=[("TRAINER", 1)]), make_user(roles=[("TRAINER", 1)])
    batch = make_batch(1, trainers=[trainer])
    start = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)

    with pytest.raises(DBAPIError):
        make_session(batch, trainer, start, hours=0)
    db.session.rollback()
    with pytest.raises(DBAPIError):
        make_session(batch, outsider, start)
    db.session.rollback()
    assert make_session(batch, trainer, start).state == "Scheduled"


def test_delivered_sessions_have_a_delivery_time_and_classrooms_have_no_meet_link(make_user, make_batch, make_session, run_sql):
    trainer = make_user(roles=[("TRAINER", 1)])
    batch = make_batch(1, trainers=[trainer])
    make_session(batch, trainer, datetime(2026, 10, 1, 10, tzinfo=timezone.utc))

    fails(run_sql, "UPDATE class_sessions SET state = 'Delivered'")
    fails(run_sql, "UPDATE class_sessions SET meet_link = 'https://meet.example.test/x', meet_status = 'Linked'")
    run_sql("UPDATE class_sessions SET state = 'Delivered', delivered_at = now()")
    run_sql("UPDATE class_sessions SET mode = 'Live Online', meet_link = 'https://meet.example.test/x', meet_status = 'Linked'")


# ---------------------------------------------------------------- foundation

def test_audit_log_is_append_only(app, make_user, run_sql):
    run_sql("INSERT INTO audit_log (action, entity_type, entity_id) VALUES ('TEST', 'thing', '1')")

    fails(run_sql, "UPDATE audit_log SET action = 'CHANGED'")
    fails(run_sql, "DELETE FROM audit_log")


def test_role_scopes_follow_the_company_wide_rule(make_user, run_sql):
    user = make_user(roles=[])

    fails(run_sql, """INSERT INTO user_role_scopes (user_id, role_id, branch_id)
                      SELECT :u, role_id, 1 FROM roles WHERE role_code = 'SUPER_ADMIN'""", u=user.user_id)
    fails(run_sql, """INSERT INTO user_role_scopes (user_id, role_id) SELECT :u, role_id FROM roles WHERE role_code = 'TRAINER'""", u=user.user_id)


def test_seeded_reference_data(app, run_sql):
    branches = db.session.execute(db.text("SELECT branch_code, mailbox FROM branches ORDER BY branch_id")).all()
    roles = db.session.execute(db.text("SELECT role_code FROM roles ORDER BY role_id")).scalars().all()
    integrations = db.session.execute(db.text("SELECT integration_code FROM integrations")).scalars().all()
    settings = db.session.execute(db.text("SELECT setting_key FROM app_settings")).scalars().all()

    assert branches == [("NIT-GNT", "trainer@nipunatechnologies.com"), ("NIT-VIJ", "contactus@nipunatechnologies.com")]
    assert roles == ["STUDENT", "TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"]
    assert {"GOOGLE_WORKSPACE", "GOOGLE_MEET", "GOOGLE_DRIVE_RECORDINGS", "CRM", "WHATSAPP", "EMAIL", "TELEPHONY",
            "AI_PROVIDER"} == set(integrations)
    assert {"session_idle_minutes", "session_max_minutes", "activation_token_hours", "recording_access_days",
            "ai_daily_limit"} <= set(settings)
    assert db.session.execute(db.text("SELECT setting_value FROM app_settings WHERE setting_key = 'activation_token_hours'")).scalar_one() == 72

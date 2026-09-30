"""Students, activation tokens, admissions, enrolments and finance summaries."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from config.database import db
from models import (
    Admission, AdmissionLmsState, Enrolment, EnrolmentTrack, FinanceSummary, Student, StudentActivation,
)


# ---------------------------------------------------------------- students

def get_student(student_id: int) -> Student | None:
    return db.session.get(Student, student_id)


def get_student_by_code(student_code: str) -> Student | None:
    return db.session.execute(
        select(Student).where(func.upper(Student.student_code) == student_code.strip().upper())
    ).scalar_one_or_none()


def get_student_by_crm_person_id(crm_person_id: str) -> Student | None:
    return db.session.execute(select(Student).where(Student.crm_person_id == crm_person_id)).scalar_one_or_none()


# ---------------------------------------------------------------- activation tokens

def find_activation(token_hash: str) -> StudentActivation | None:
    return db.session.execute(
        select(StudentActivation).where(StudentActivation.token_hash == token_hash)
    ).scalar_one_or_none()


def outstanding_activation(student_id: int) -> StudentActivation | None:
    """The unused, unrevoked token of a student (it may be expired)."""
    return db.session.execute(
        select(StudentActivation).where(
            StudentActivation.student_id == student_id,
            StudentActivation.used_at.is_(None),
            StudentActivation.revoked_at.is_(None),
        )
    ).scalar_one_or_none()


def revoke_outstanding_activation(student_id: int, now: datetime) -> None:
    token = outstanding_activation(student_id)
    if token is not None:
        token.revoked_at = now
        db.session.flush()  # free the one-outstanding-token slot before a new token is inserted


# ---------------------------------------------------------------- admissions

def get_admission(admission_id: int) -> Admission | None:
    return db.session.get(Admission, admission_id)


def get_admission_by_crm_id(crm_admission_id: str) -> Admission | None:
    return db.session.execute(
        select(Admission).where(Admission.crm_admission_id == crm_admission_id)
    ).scalar_one_or_none()


def admissions_of_student(student_id: int) -> list[Admission]:
    stmt = select(Admission).where(Admission.student_id == student_id).order_by(Admission.admission_id)
    return list(db.session.execute(stmt).scalars())


def lms_status_of(admission_id: int) -> str | None:
    """The admission's last recorded LMS status (kept current by database triggers)."""
    return db.session.execute(
        select(AdmissionLmsState.lms_status).where(AdmissionLmsState.admission_id == admission_id)
    ).scalar()


def get_finance_summary(admission_id: int) -> FinanceSummary | None:
    return db.session.get(FinanceSummary, admission_id)


# ---------------------------------------------------------------- enrolments

def get_enrolment(enrolment_id: int) -> Enrolment | None:
    return db.session.get(Enrolment, enrolment_id)


def enrolments_of_admission(admission_id: int) -> list[Enrolment]:
    stmt = select(Enrolment).where(Enrolment.admission_id == admission_id).order_by(Enrolment.enrolment_id)
    return list(db.session.execute(stmt).scalars())


def enrolments_of_student(student_id: int) -> list[Enrolment]:
    stmt = (
        select(Enrolment)
        .options(selectinload(Enrolment.tracks))
        .where(Enrolment.student_id == student_id)
        .order_by(Enrolment.enrolment_id)
    )
    return list(db.session.execute(stmt).scalars())


def find_enrolment(admission_id: int, course_id: int) -> Enrolment | None:
    return db.session.execute(
        select(Enrolment).where(Enrolment.admission_id == admission_id, Enrolment.course_id == course_id)
    ).scalar_one_or_none()


def get_track(enrolment_track_id: int) -> EnrolmentTrack | None:
    return db.session.get(EnrolmentTrack, enrolment_track_id)

"""The Certificate Register: queries only."""
from sqlalchemy import Select, func, or_, select

from config.database import db
from models import Admission, Certificate, CertificateChangeRequest, CertificateFinancialException, CertificateStatusHistory, Student


def get_certificate(certificate_id: int) -> Certificate | None:
    return db.session.get(Certificate, certificate_id)


def live_entry(enrolment_id: int, certificate_type: str) -> Certificate | None:
    """The enrolment's current register entry of this type (every earlier version is Superseded)."""
    return db.session.execute(
        select(Certificate).where(Certificate.enrolment_id == enrolment_id, Certificate.certificate_type == certificate_type,
                                  Certificate.status != "Superseded")
    ).unique().scalar_one_or_none()


def live_entries(enrolment_id: int) -> list[Certificate]:
    stmt = select(Certificate).where(Certificate.enrolment_id == enrolment_id, Certificate.status != "Superseded").order_by(Certificate.certificate_id)
    return list(db.session.execute(stmt).unique().scalars())


def versions(certificate_number: str) -> list[Certificate]:
    """Every version issued under a number, oldest first."""
    stmt = select(Certificate).where(Certificate.certificate_number == certificate_number).order_by(Certificate.version)
    return list(db.session.execute(stmt).unique().scalars())


def versions_by_number(certificate_number: str) -> list[Certificate]:
    """Every version under a number (any letter case), oldest first."""
    stmt = (select(Certificate).where(func.upper(Certificate.certificate_number) == certificate_number.strip().upper())
            .order_by(Certificate.version))
    return list(db.session.execute(stmt).unique().scalars())


def status_history(certificate_id: int) -> list[CertificateStatusHistory]:
    stmt = (select(CertificateStatusHistory).where(CertificateStatusHistory.certificate_id == certificate_id)
            .order_by(CertificateStatusHistory.changed_at, CertificateStatusHistory.history_id))
    return list(db.session.execute(stmt).scalars())


# ---------------------------------------------------------------- change requests and financial exceptions

def get_request(request_id: int) -> CertificateChangeRequest | None:
    return db.session.get(CertificateChangeRequest, request_id)


def pending_request(certificate_id: int) -> CertificateChangeRequest | None:
    return db.session.execute(
        select(CertificateChangeRequest).where(CertificateChangeRequest.certificate_id == certificate_id,
                                               CertificateChangeRequest.status == "Pending")
    ).unique().scalar_one_or_none()


def requests_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    stmt = (select(CertificateChangeRequest).join(Certificate, Certificate.certificate_id == CertificateChangeRequest.certificate_id)
            .order_by(CertificateChangeRequest.requested_at.desc(), CertificateChangeRequest.request_id.desc()))
    if branch_ids is not None:
        stmt = stmt.where(Certificate.branch_id.in_(branch_ids))
    for column in ("status", "kind"):
        if filters.get(column):
            stmt = stmt.where(getattr(CertificateChangeRequest, column) == filters[column])
    return stmt


def get_exception(exception_id: int) -> CertificateFinancialException | None:
    return db.session.get(CertificateFinancialException, exception_id)


def pending_exception(admission_id: int) -> CertificateFinancialException | None:
    return db.session.execute(
        select(CertificateFinancialException).where(CertificateFinancialException.admission_id == admission_id,
                                                    CertificateFinancialException.status == "Pending")
    ).unique().scalar_one_or_none()


def approved_exception(admission_id: int, certificate_type: str) -> CertificateFinancialException | None:
    return db.session.execute(
        select(CertificateFinancialException).where(
            CertificateFinancialException.admission_id == admission_id, CertificateFinancialException.status == "Approved",
            CertificateFinancialException.certificate_types.contains([certificate_type]),
        ).order_by(CertificateFinancialException.decided_at.desc()).limit(1)
    ).unique().scalars().first()


def exceptions_stmt(filters: dict, branch_ids: set[int] | None) -> Select:
    stmt = (select(CertificateFinancialException).join(Admission, Admission.admission_id == CertificateFinancialException.admission_id)
            .order_by(CertificateFinancialException.requested_at.desc(), CertificateFinancialException.exception_id.desc()))
    if branch_ids is not None:
        stmt = stmt.where(Admission.service_branch_id.in_(branch_ids))
    if filters.get("status"):
        stmt = stmt.where(CertificateFinancialException.status == filters["status"])
    return stmt


def latest_by_number(certificate_number: str) -> Certificate | None:
    stmt = (
        select(Certificate).where(func.upper(Certificate.certificate_number) == certificate_number.strip().upper())
        .order_by(Certificate.version.desc()).limit(1)
    )
    return db.session.execute(stmt).unique().scalars().first()


def register_stmt(filters: dict, branch_ids: set[int] | None, student_id: int | None = None) -> Select:
    """Register entries (every version) visible to the caller: their branches, or a student's own, newest first."""
    stmt = select(Certificate).join(Student, Student.student_id == Certificate.student_id).order_by(
        Certificate.certificate_id.desc())
    if student_id is not None:
        stmt = stmt.where(Certificate.student_id == student_id)
    elif branch_ids is not None:
        stmt = stmt.where(Certificate.branch_id.in_(branch_ids))
    if filters.get("branch_id"):
        stmt = stmt.where(Certificate.branch_id == filters["branch_id"])
    if filters.get("status"):
        stmt = stmt.where(Certificate.status == filters["status"])
    if filters.get("certificate_type"):
        stmt = stmt.where(Certificate.certificate_type == filters["certificate_type"])
    if filters.get("course_id"):
        stmt = stmt.where(Certificate.course_id == filters["course_id"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Student.full_name.ilike(pattern), Student.student_code.ilike(pattern),
                              Certificate.certificate_number.ilike(pattern), Certificate.holder_name.ilike(pattern)))
    return stmt

"""The LMS Certificate Register."""
from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, FetchedValue, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.attendance_enums import CertificateStatus, CertificateType
from models.enums import _pg_enum
from models.catalog import Course
from models.masters import Branch
from models.students import Admission, Enrolment, Student

APPROVAL_STATUSES = ("Pending", "Approved", "Rejected")
REQUEST_KINDS = ("Correction", "Revocation", "Reinstatement")
ApprovalStatus = _pg_enum("approval_status", APPROVAL_STATUSES)
CertificateRequestKind = _pg_enum("certificate_request_kind", REQUEST_KINDS)


def _user_ref(user: User | None) -> dict | None:
    return None if user is None else {"user_id": user.user_id, "full_name": user.full_name}


class Certificate(db.Model):
    """One version of one register entry. A reissue adds a version with the same number; the earlier one is Superseded."""

    __tablename__ = "certificates"

    certificate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_number: Mapped[str | None] = mapped_column(String(30), server_default=FetchedValue())  # trigger, at first issue
    certificate_type: Mapped[str] = mapped_column(CertificateType)
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(CertificateStatus, default="Not Yet Eligible")
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    holder_name: Mapped[str] = mapped_column(String(150))
    completion_review_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("completion_reviews.review_id"))
    issue_date: Mapped[date | None] = mapped_column(Date, server_default=FetchedValue())
    reason: Mapped[str | None] = mapped_column(Text)
    recommended_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    recommended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    revoked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_certificate_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("certificates.certificate_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    student: Mapped[Student] = relationship(lazy="joined")
    course: Mapped[Course] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")

    @property
    def version_label(self) -> str:
        """'v2 (reissue)' style text for the register's Version column."""
        if self.status == "Superseded":
            return f"v{self.version} (superseded)"
        if self.status == "Revoked":
            return f"v{self.version} (revoked)"
        if self.certificate_number is None:
            return "Number allocated at first issue"
        return f"v{self.version}" + (" (reissue)" if self.version > 1 else "")

    def to_dict(self, actions: list[str] | None = None) -> dict:
        """actions: what the current user may do to this entry now (computed by the service)."""
        return {
            "certificate_id": self.certificate_id,
            "certificate_number": self.certificate_number,
            "certificate_type": self.certificate_type,
            "version": self.version,
            "version_label": self.version_label,
            "status": self.status,
            "enrolment": self.enrolment.to_summary(),
            "student": self.student.to_summary(),
            "course": self.course.to_summary(),
            "branch": self.branch.to_summary(),
            "holder_name": self.holder_name,
            "issue_date": self.issue_date,
            "reason": self.reason,
            "recommended_at": self.recommended_at,
            "approved_at": self.approved_at,
            "revoked_at": self.revoked_at,
            "supersedes_certificate_id": self.supersedes_certificate_id,
            "created_at": self.created_at,
            "actions": actions or [],
        }


class CertificateFinancialException(db.Model):
    """A Founder / CEO or Super Admin decision that lets certificates go ahead while the fee is not cleared (Module 22 §5).
    It does not waive the debt."""

    __tablename__ = "certificate_financial_exceptions"

    exception_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_id: Mapped[int] = mapped_column(Integer, ForeignKey("admissions.admission_id"))
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    certificate_types: Mapped[list[str]] = mapped_column(ARRAY(CertificateType))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    admission: Mapped[Admission] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "exception_id": self.exception_id,
            "admission": {"admission_id": self.admission.admission_id, "admission_code": self.admission.admission_code},
            "outstanding_amount": f"{self.outstanding_amount:.2f}",
            "certificate_types": list(self.certificate_types),
            "reason": self.reason,
            "status": self.status,
            "requested_by": _user_ref(self.requester),
            "requested_at": self.requested_at,
            "decided_by": _user_ref(self.decider),
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }


class CertificateChangeRequest(db.Model):
    """A correction / reissue, revocation or reinstatement waiting for an independent approver (Module 22 §7, §8)."""

    __tablename__ = "certificate_change_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(Integer, ForeignKey("certificates.certificate_id"))
    kind: Mapped[str] = mapped_column(CertificateRequestKind)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    resulting_certificate_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("certificates.certificate_id"))

    certificate: Mapped[Certificate] = relationship(foreign_keys=[certificate_id], lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self, actions: list[str] | None = None) -> dict:
        certificate = self.certificate
        return {
            "request_id": self.request_id,
            "certificate": {"certificate_id": certificate.certificate_id, "certificate_number": certificate.certificate_number,
                            "certificate_type": certificate.certificate_type, "version": certificate.version,
                            "status": certificate.status, "holder_name": certificate.holder_name,
                            "course": certificate.course.to_summary(), "branch": certificate.branch.to_summary()},
            "kind": self.kind,
            "reason": self.reason,
            "evidence": self.evidence,
            "changes": self.changes,
            "status": self.status,
            "requested_by": _user_ref(self.requester),
            "requested_at": self.requested_at,
            "decided_by": _user_ref(self.decider),
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
            "resulting_certificate_id": self.resulting_certificate_id,
            "actions": actions or [],
        }


class CertificateStatusHistory(db.Model):
    """Every status change of a register entry (written by a trigger), so a revoked interval survives a reinstatement."""

    __tablename__ = "certificate_status_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(Integer, ForeignKey("certificates.certificate_id"))
    from_status: Mapped[str | None] = mapped_column(CertificateStatus)
    to_status: Mapped[str] = mapped_column(CertificateStatus)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        return {"from_status": self.from_status, "to_status": self.to_status, "changed_at": self.changed_at}


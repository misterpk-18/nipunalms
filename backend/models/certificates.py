"""The LMS Certificate Register."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.attendance_enums import CertificateStatus, CertificateType
from models.catalog import Course
from models.masters import Branch
from models.students import Enrolment, Student


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

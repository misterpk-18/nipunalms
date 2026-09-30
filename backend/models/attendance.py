"""Attendance records, recoveries for absences, and correction requests."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, FetchedValue, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.attendance_enums import AttendanceStatus, CorrectionStatus, RecoveryMethod, RecoveryStatus
from models.batches import ClassSession
from models.students import Enrolment, Student


def student_summary(enrolment: Enrolment) -> dict:
    """The enrolment's student as {student_id, student_code, full_name} (one identity-map lookup per student)."""
    return db.session.get(Student, enrolment.student_id).to_summary()


def session_summary(session: ClassSession) -> dict:
    return {
        "session_id": session.session_id,
        "session_code": session.session_code,
        "title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "batch": session.batch.to_summary(),
    }


class AttendanceRecord(db.Model):
    """One student's trainer-confirmed attendance for one actual Class Session."""

    __tablename__ = "attendance_records"

    attendance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    status: Mapped[str] = mapped_column(AttendanceStatus)
    remarks: Mapped[str | None] = mapped_column(Text)
    marked_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    corrected_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    session: Mapped[ClassSession] = relationship(lazy="joined")
    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    marker: Mapped[User] = relationship(foreign_keys=[marked_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "attendance_id": self.attendance_id,
            "status": self.status,
            "remarks": self.remarks,
            "marked_by": {"user_id": self.marked_by, "full_name": self.marker.full_name},
            "marked_at": self.marked_at,
            "corrected_at": self.corrected_at,
        }


class AttendanceRecovery(db.Model):
    """Recovery for an absence (REC-0041): requested, approved by the Academic Coordinator, completed with evidence."""

    __tablename__ = "attendance_recoveries"

    recovery_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recovery_code: Mapped[str] = mapped_column(String(20), unique=True, server_default=FetchedValue())  # trigger
    attendance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("attendance_records.attendance_id"))
    method: Mapped[str] = mapped_column(RecoveryMethod)
    status: Mapped[str] = mapped_column(RecoveryStatus, default="Requested")
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date)
    completed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    attendance: Mapped[AttendanceRecord] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")

    def to_summary(self) -> dict:
        return {"recovery_id": self.recovery_id, "recovery_code": self.recovery_code, "status": self.status, "method": self.method}

    def to_dict(self) -> dict:
        return {
            **self.to_summary(),
            "attendance_id": self.attendance_id,
            "session": session_summary(self.attendance.session),
            "enrolment": self.attendance.enrolment.to_summary(),
            "student": student_summary(self.attendance.enrolment),
            "reason": self.reason,
            "requested_by": {"user_id": self.requested_by, "full_name": self.requester.full_name},
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
            "target_date": self.target_date,
            "completed_at": self.completed_at,
            "evidence_note": self.evidence_note,
        }


class AttendanceCorrection(db.Model):
    """A request to change (or, after the lock, to enter) an attendance entry; an independent reviewer decides."""

    __tablename__ = "attendance_corrections"

    correction_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    requested_status: Mapped[str] = mapped_column(AttendanceStatus)
    previous_status: Mapped[str | None] = mapped_column(AttendanceStatus)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(CorrectionStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    session: Mapped[ClassSession] = relationship(lazy="joined")
    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "correction_id": self.correction_id,
            "session": session_summary(self.session),
            "enrolment": self.enrolment.to_summary(),
            "student": student_summary(self.enrolment),
            "previous_status": self.previous_status,
            "requested_status": self.requested_status,
            "reason": self.reason,
            "status": self.status,
            "requested_by": {"user_id": self.requested_by, "full_name": self.requester.full_name},
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }

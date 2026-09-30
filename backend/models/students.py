"""Students, activation tokens, the CRM admission projection, enrolments, finance summaries and the CRM inbox / outbox."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.catalog import Course, CourseComponent, CurriculumVersion
from models.enums import (
    ActivationStatus, AdmissionStatus, CrmEventStatus, DeliveryMode, EnrolmentKind, EnrolmentStatus, LmsStatus,
    OutboxStatus,
)
from models.masters import Branch


class Student(db.Model):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    crm_person_id: Mapped[str] = mapped_column(String(100), unique=True)
    crm_person_code: Mapped[str | None] = mapped_column(String(30))  # the CRM's readable code, display only
    lms_user_id: Mapped[str] = mapped_column(String(100), unique=True, server_default=FetchedValue())  # trigger
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    full_name: Mapped[str] = mapped_column(String(150))
    name_te: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    mobile: Mapped[str | None] = mapped_column(String(30))
    original_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    service_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    preferred_language: Mapped[str] = mapped_column(String(2), default="en")
    activation_status: Mapped[str] = mapped_column(ActivationStatus, default="Account Created")
    mfa_status: Mapped[str] = mapped_column(String(30), default="Not Configured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    original_branch: Mapped[Branch] = relationship(foreign_keys=[original_branch_id], lazy="joined")
    service_branch: Mapped[Branch] = relationship(foreign_keys=[service_branch_id], lazy="joined")

    def to_summary(self) -> dict:
        return {"student_id": self.student_id, "student_code": self.student_code, "full_name": self.full_name}

    def to_profile(self) -> dict:
        """The student block of the login / profile response."""
        return {
            "student_id": self.student_id,
            "student_code": self.student_code,
            "full_name": self.full_name,
            "name_te": self.name_te,
            "preferred_language": self.preferred_language,
            "activation_status": self.activation_status,
            "service_branch_id": self.service_branch_id,
        }

    def to_dict(self) -> dict:
        return {
            **self.to_profile(),
            "crm_person_id": self.crm_person_id,
            "crm_person_code": self.crm_person_code,
            "lms_user_id": self.lms_user_id,
            "provisioned_at": self.provisioned_at,
            "email": self.email,
            "mobile": self.mobile,
            "original_branch": self.original_branch.to_summary(),
            "service_branch": self.service_branch.to_summary(),
            "mfa_status": self.mfa_status,
        }


class StudentActivation(db.Model):
    """An activation token; only its SHA-256 is stored."""

    __tablename__ = "student_activations"

    activation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    channel: Mapped[str] = mapped_column(String(30))
    issued_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")

    def status(self, now: datetime) -> str:
        """valid / used / revoked / expired."""
        if self.used_at is not None:
            return "used"
        if self.revoked_at is not None:
            return "revoked"
        return "expired" if self.expires_at <= now else "valid"


class Admission(db.Model):
    """The CRM Admission as projected into the LMS."""

    __tablename__ = "admissions"

    admission_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crm_admission_id: Mapped[str] = mapped_column(String(100), unique=True)
    admission_code: Mapped[str] = mapped_column(String(50), unique=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    original_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    service_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    collecting_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    crm_status: Mapped[str] = mapped_column(AdmissionStatus, default="Active")
    mode: Mapped[str] = mapped_column(DeliveryMode, default="Classroom")
    admission_date: Mapped[date | None] = mapped_column(Date)
    complimentary_of_admission_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admissions.admission_id"))
    seat_type: Mapped[str | None] = mapped_column(String(20))  # Confirmed Seat / Future Plan (CRM delivery plan)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    source_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course] = relationship(lazy="joined")
    original_branch: Mapped[Branch] = relationship(foreign_keys=[original_branch_id], lazy="joined")
    service_branch: Mapped[Branch] = relationship(foreign_keys=[service_branch_id], lazy="joined")
    collecting_branch: Mapped[Branch] = relationship(foreign_keys=[collecting_branch_id], lazy="joined")

    def to_summary(self) -> dict:
        return {
            "admission_id": self.admission_id,
            "admission_code": self.admission_code,
            "crm_admission_id": self.crm_admission_id,
        }

    def to_dict(self, lms_status: str | None = None) -> dict:
        return {
            **self.to_summary(),
            "student_id": self.student_id,
            "course": self.course.to_summary(),
            "original_branch": self.original_branch.to_summary(),
            "service_branch": self.service_branch.to_summary(),
            "collecting_branch": self.collecting_branch.to_summary(),
            "crm_status": self.crm_status,
            "mode": self.mode,
            "admission_date": self.admission_date,
            "complimentary_of_admission_id": self.complimentary_of_admission_id,
            "seat_type": self.seat_type,
            "planned_start_date": self.planned_start_date,
            "lms_status": lms_status,
        }


class Enrolment(db.Model):
    __tablename__ = "enrolments"

    enrolment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    admission_id: Mapped[int] = mapped_column(Integer, ForeignKey("admissions.admission_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    kind: Mapped[str] = mapped_column(EnrolmentKind)
    parent_enrolment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    curriculum_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    service_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    mode: Mapped[str] = mapped_column(DeliveryMode, default="Classroom")
    status: Mapped[str] = mapped_column(EnrolmentStatus)
    joining_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set by trigger on Completed
    access_start: Mapped[date | None] = mapped_column(Date)
    access_end: Mapped[date | None] = mapped_column(Date)
    certificate_status: Mapped[str] = mapped_column(String(100), default="Not Yet Eligible")
    benefit_gate_met: Mapped[bool | None] = mapped_column(Boolean)
    benefit_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    admission: Mapped[Admission] = relationship(lazy="joined")
    course: Mapped[Course] = relationship(lazy="joined")
    curriculum_version: Mapped[CurriculumVersion | None] = relationship(lazy="joined")
    service_branch: Mapped[Branch] = relationship(lazy="joined")
    parent: Mapped["Enrolment | None"] = relationship(remote_side=[enrolment_id])
    tracks: Mapped[list["EnrolmentTrack"]] = relationship(
        back_populates="enrolment", order_by="EnrolmentTrack.enrolment_track_id", cascade="all, delete-orphan"
    )

    def to_summary(self) -> dict:
        return {
            "enrolment_id": self.enrolment_id,
            "enrolment_code": self.enrolment_code,
            "course": self.course.to_summary(),
            "kind": self.kind,
            "status": self.status,
        }

    def to_dict(self, batch: dict | None = None) -> dict:
        """batch: summary of the active allocation's batch, looked up by the caller (None = not allocated)."""
        return {
            **self.to_summary(),
            "student_id": self.student_id,
            "admission": self.admission.to_summary(),
            "parent_enrolment_id": self.parent_enrolment_id,
            "curriculum_version": self.curriculum_version.to_summary() if self.curriculum_version else None,
            "service_branch": self.service_branch.to_summary(),
            "collecting_branch": self.admission.collecting_branch.to_summary(),
            "mode": self.mode,
            "joining_date": self.joining_date,
            "access_start": self.access_start,
            "access_end": self.access_end,
            "certificate_status": self.certificate_status,
            "benefit_gate_met": self.benefit_gate_met,
            "benefit_note": self.benefit_note,
            "batch": batch,
            "tracks": [t.to_dict() for t in self.tracks],
        }


class EnrolmentTrack(db.Model):
    __tablename__ = "enrolment_tracks"

    enrolment_track_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    component_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_components.component_id"))
    curriculum_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))

    enrolment: Mapped[Enrolment] = relationship(back_populates="tracks")
    component: Mapped[CourseComponent] = relationship(lazy="joined")
    curriculum_version: Mapped[CurriculumVersion | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "enrolment_track_id": self.enrolment_track_id,
            "track_code": self.component.track_code,
            "track_name": self.component.track_name,
            "role": self.component.role,
            "curriculum_version": self.curriculum_version.to_summary() if self.curriculum_version else None,
        }


class FinanceSummary(db.Model):
    """Read-only projection of the CRM's money for one admission."""

    __tablename__ = "finance_summaries"

    admission_id: Mapped[int] = mapped_column(Integer, ForeignKey("admissions.admission_id"), primary_key=True)
    fee_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    verified_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    next_due_date: Mapped[date | None] = mapped_column(Date)
    next_due_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    receipts: Mapped[list] = mapped_column(JSONB, default=list)
    pending_verification: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # claims, never counted as paid
    waived: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    refunded: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    payment_completion: Mapped[str | None] = mapped_column(String(20))
    invoice_numbers: Mapped[list] = mapped_column(JSONB, default=list)
    installments: Mapped[list] = mapped_column(JSONB, default=list)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "admission_id": self.admission_id,
            "fee_total": self.fee_total,
            "verified_paid": self.verified_paid,
            "balance": self.balance,
            "next_due_date": self.next_due_date,
            "next_due_amount": self.next_due_amount,
            "receipts": self.receipts,
            "pending_verification": self.pending_verification,
            "waived": self.waived,
            "refunded": self.refunded,
            "payment_completion": self.payment_completion,
            "invoice_numbers": self.invoice_numbers,
            "installments": self.installments,
            "as_of": self.as_of,
        }


class AdmissionLmsState(db.Model):
    """Last LMS status per admission (kept by triggers); what the CRM pull endpoint reads."""

    __tablename__ = "admission_lms_state"

    admission_id: Mapped[int] = mapped_column(Integer, ForeignKey("admissions.admission_id"), primary_key=True)
    lms_status: Mapped[str] = mapped_column(LmsStatus)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    academic: Mapped[dict | None] = mapped_column(JSONB)  # last academic state queued for the CRM (db 005)
    academic_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    admission: Mapped[Admission] = relationship(lazy="joined")


class CrmEvent(db.Model):
    """An event received from the CRM, with what happened to it."""

    __tablename__ = "crm_events"

    crm_event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    event_type: Mapped[str] = mapped_column(String(50))
    source_version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(CrmEventStatus, default="Received")
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def to_dict(self, include_payload: bool = False) -> dict:
        data = {
            "crm_event_id": self.crm_event_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source_version": self.source_version,
            "occurred_at": self.occurred_at,
            "status": self.status,
            "error": self.error,
            "retries": self.retries,
            "received_at": self.received_at,
            "processed_at": self.processed_at,
        }
        if include_payload:
            data["payload"] = self.payload
            data["result"] = self.result
        return data


class CrmOutbox(db.Model):
    """A value the CRM stores about the LMS, queued in the same transaction as the change."""

    __tablename__ = "crm_outbox"

    outbox_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), unique=True, server_default=FetchedValue())
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(OutboxStatus, default="Pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        return {
            "outbox_id": self.outbox_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "status": self.status,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
        }

"""Placement & career support: career profile, CV versions, opportunities, applications and verified outcomes."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.catalog import Course
from models.masters import Branch
from models.students import Student

READINESS_LEVELS = ("Not Assessed", "In Preparation", "Ready for referral")
SKILL_CONFIDENCE = ("Verified", "Student Reported", "Verification Pending")
WORK_MODES = ("On-site", "Remote", "Hybrid", "Any")
CV_REVIEW_STATUSES = ("Pending Review", "Reviewed", "Changes Requested", "Superseded")
OPPORTUNITY_STATUSES = ("Draft", "Verification Pending", "Active", "On Hold", "Closed", "Expired")
EMPLOYMENT_TYPES = ("Full-time", "Internship", "Contract")
OPPORTUNITY_WORK_MODES = ("On-site", "Remote", "Hybrid")
APPLICATION_STATUSES = (
    "Applied", "Shortlisted", "Interview Scheduled", "Interview Attended", "Selected", "Offer Received", "Offer Accepted",
    "Joined", "Rejected", "Student Declined", "Position Closed", "Withdrawn",
)
# The employer decided or the student left: nothing follows
CLOSED_APPLICATION_STATUSES = ("Joined", "Rejected", "Student Declined", "Position Closed", "Withdrawn")
OUTCOME_TYPES = ("Offer Received", "Offer Accepted", "Joined")


class CareerProfile(db.Model):
    __tablename__ = "career_profiles"

    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"), primary_key=True)
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    support_start: Mapped[date | None] = mapped_column(Date)
    support_end: Mapped[date | None] = mapped_column(Date)
    support_extension_reason: Mapped[str | None] = mapped_column(Text)
    preferred_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    work_mode: Mapped[str | None] = mapped_column(String(20))
    qualification: Mapped[str | None] = mapped_column(String(200))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str | None] = mapped_column(String(20))
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    availability: Mapped[str | None] = mapped_column(String(200))
    sharing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    sharing_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    readiness: Mapped[str] = mapped_column(String(30), default="Not Assessed")
    readiness_note: Mapped[str | None] = mapped_column(Text)
    readiness_reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    readiness_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")

    def to_dict(self, completeness: dict) -> dict:
        return {
            "student": self.student.to_summary(),
            "opted_in": self.opted_in,
            "opted_in_at": self.opted_in_at,
            "support_start": self.support_start,
            "support_end": self.support_end,
            "support_extension_reason": self.support_extension_reason,
            "preferred_roles": self.preferred_roles,
            "preferred_locations": self.preferred_locations,
            "work_mode": self.work_mode,
            "qualification": self.qualification,
            "graduation_year": self.graduation_year,
            "experience_level": self.experience_level,
            "skills": self.skills,
            "portfolio_url": self.portfolio_url,
            "availability": self.availability,
            "sharing_consent": self.sharing_consent,
            "sharing_consent_at": self.sharing_consent_at,
            "readiness": self.readiness,
            "readiness_note": self.readiness_note,
            "readiness_reviewed_at": self.readiness_reviewed_at,
            "completeness": completeness,
        }


class CvDocument(db.Model):
    __tablename__ = "cv_documents"

    cv_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    version_no: Mapped[int] = mapped_column(Integer, server_default=FetchedValue())  # trigger
    label: Mapped[str] = mapped_column(String(150))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(20), default="Pending Review")
    review_feedback: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_summary(self) -> dict:
        return {"cv_id": self.cv_id, "version_no": self.version_no, "label": self.label}

    def to_dict(self) -> dict:
        return {
            **self.to_summary(),
            "student_id": self.student_id,
            "original_filename": self.original_filename,
            "file_size_bytes": self.file_size_bytes,
            "review_status": self.review_status,
            "review_feedback": self.review_feedback,
            "reviewed_at": self.reviewed_at,
            "uploaded_at": self.uploaded_at,
        }


class Opportunity(db.Model):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_code: Mapped[str] = mapped_column(String(20), unique=True, server_default=FetchedValue())  # trigger
    title: Mapped[str] = mapped_column(String(200))
    employer_name: Mapped[str] = mapped_column(String(200))
    employer_source: Mapped[str | None] = mapped_column(String(300))
    employment_type: Mapped[str] = mapped_column(String(20), default="Full-time")
    work_mode: Mapped[str] = mapped_column(String(20), default="On-site")
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.course_id"))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    compensation_text: Mapped[str] = mapped_column(String(200), default="Not Disclosed")
    openings: Mapped[int | None] = mapped_column(Integer)
    closing_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="Draft")
    verification_source: Mapped[str | None] = mapped_column(String(300))
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course | None] = relationship(lazy="joined")
    branch: Mapped[Branch | None] = relationship(lazy="joined")
    creator: Mapped[User] = relationship(foreign_keys=[created_by], lazy="joined")
    verifier: Mapped[User | None] = relationship(foreign_keys=[verified_by], lazy="joined")

    def to_summary(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_code": self.opportunity_code,
            "title": self.title,
            "employer_name": self.employer_name,
        }

    def to_student_dict(self) -> dict:
        """What a student may see: the verified public facts, never the verification trail or employer contacts."""
        return {
            **self.to_summary(),
            "employment_type": self.employment_type,
            "work_mode": self.work_mode,
            "location": self.location,
            "description": self.description,
            "required_skills": self.required_skills,
            "course": self.course.to_summary() if self.course else None,
            "compensation_text": self.compensation_text,
            "openings": self.openings,
            "closing_date": self.closing_date,
        }

    def to_dict(self) -> dict:
        return {
            **self.to_student_dict(),
            "employer_source": self.employer_source,
            "branch": self.branch.to_summary() if self.branch else None,
            "status": self.status,
            "verification_source": self.verification_source,
            "verified_by": self.verifier.to_summary() if self.verifier else None,
            "verified_at": self.verified_at,
            "created_by": self.creator.to_summary(),
            "created_at": self.created_at,
        }


class Application(db.Model):
    __tablename__ = "applications"

    application_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    opportunity_id: Mapped[int] = mapped_column(Integer, ForeignKey("opportunities.opportunity_id"))
    hiring_cycle: Mapped[str] = mapped_column(String(30), default="Current")
    source: Mapped[str] = mapped_column(String(20), default="Nipuna-referred")
    cv_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cv_documents.cv_id"))
    status: Mapped[str] = mapped_column(String(30), default="Applied")
    interview_round: Mapped[str | None] = mapped_column(String(100))
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")
    opportunity: Mapped[Opportunity] = relationship(lazy="joined")
    cv: Mapped[CvDocument | None] = relationship(lazy="joined")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", order_by="ApplicationEvent.application_event_id"
    )

    def to_dict(self, *, include_events: bool = False) -> dict:
        data = {
            "application_id": self.application_id,
            "student": self.student.to_summary(),
            "opportunity": self.opportunity.to_summary(),
            "hiring_cycle": self.hiring_cycle,
            "source": self.source,
            "cv": self.cv.to_summary() if self.cv else None,
            "status": self.status,
            "closed": self.status in CLOSED_APPLICATION_STATUSES,
            "interview_round": self.interview_round,
            "interview_at": self.interview_at,
            "status_note": self.status_note,
            "applied_at": self.applied_at,
            "updated_at": self.updated_at,
        }
        if include_events:
            data["events"] = [e.to_dict() for e in self.events]
        return data


class ApplicationEvent(db.Model):
    """One status an application passed through (written by a database trigger)."""

    __tablename__ = "application_events"

    application_event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.application_id"))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    application: Mapped[Application] = relationship(back_populates="events")

    def to_dict(self) -> dict:
        return {
            "from_status": self.from_status,
            "to_status": self.to_status,
            "note": self.note,
            "actor_user_id": self.actor_user_id,
            "occurred_at": self.occurred_at,
        }


class PlacementOutcome(db.Model):
    __tablename__ = "placement_outcomes"

    outcome_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    application_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("applications.application_id"))
    outcome_type: Mapped[str] = mapped_column(String(20))
    employer_name: Mapped[str] = mapped_column(String(200))
    role_title: Mapped[str] = mapped_column(String(200))
    event_date: Mapped[date] = mapped_column(Date)
    compensation_text: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20), default="Placement records")
    verification_status: Mapped[str] = mapped_column(String(30), default="Pending Verification")
    evidence_note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "outcome_id": self.outcome_id,
            "student": self.student.to_summary(),
            "application_id": self.application_id,
            "outcome_type": self.outcome_type,
            "employer_name": self.employer_name,
            "role_title": self.role_title,
            "event_date": self.event_date,
            "compensation_text": self.compensation_text,
            "source": self.source,
            "verification_status": self.verification_status,
            "evidence_note": self.evidence_note,
            "verified_at": self.verified_at,
        }

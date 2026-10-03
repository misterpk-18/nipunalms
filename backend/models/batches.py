"""Batches, batch trainers, allocations and class sessions."""
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.catalog import Course, CurriculumTopic, CurriculumVersion
from models.enums import (
    AllocationStatus, BatchReadiness, BatchState, BatchTrainerRole, DeliveryMode, MeetStatus, SessionState,
)
from models.masters import Branch

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# The register's words for the stored Meet statuses
MEET_STATUS_LABELS = {"Not Required": "Not Required", "Pending Verification": "Pending Verification", "Linked": "Associated", "Unavailable": "Failed"}


class Batch(db.Model):
    __tablename__ = "batches"

    batch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(40), unique=True, server_default=FetchedValue())  # trigger
    crm_batch_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    crm_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    curriculum_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    capacity: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(DeliveryMode, default="Classroom")
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    # The timetable sales can promise (db 098): ISO weekdays 1 = Mon … 7 = Sun, IST times, the room
    schedule_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(BatchState, default="Forming")
    readiness: Mapped[str] = mapped_column(BatchReadiness, default="Ready")
    readiness_reason: Mapped[str | None] = mapped_column(Text)
    recovery_owner: Mapped[str | None] = mapped_column(String(100))
    seed_data: Mapped[bool] = mapped_column(Boolean, default=False)  # made-up CRM batch ID from `flask seed-dev` (db 090)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    curriculum_version: Mapped[CurriculumVersion | None] = relationship(lazy="joined")
    trainers: Mapped[list["BatchTrainer"]] = relationship(
        back_populates="batch", order_by="BatchTrainer.batch_trainer_id", cascade="all, delete-orphan"
    )

    def to_summary(self) -> dict:
        return {"batch_id": self.batch_id, "batch_code": self.batch_code, "course_code": self.course.course_code}

    def to_dict(self, allocated_count: int = 0) -> dict:
        return {
            "batch_id": self.batch_id,
            "batch_code": self.batch_code,
            "crm_batch_id": self.crm_batch_id,
            "course": self.course.to_summary(),
            "branch": self.branch.to_summary(),
            "curriculum_version": self.curriculum_version.to_summary() if self.curriculum_version else None,
            "capacity": self.capacity,
            "allocated_count": allocated_count,
            "is_full": allocated_count >= self.capacity,
            "mode": self.mode,
            "planned_start": self.planned_start,
            "planned_end": self.planned_end,
            "schedule_days": [WEEKDAYS[d - 1] for d in self.schedule_days or []],
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "location": self.location,
            "state": self.state,
            "readiness": self.readiness,
            "readiness_reason": self.readiness_reason,
            "recovery_owner": self.recovery_owner,
            "trainers": [t.to_dict() for t in self.trainers if t.to_date is None],
        }


class BatchTrainer(db.Model):
    __tablename__ = "batch_trainers"

    batch_trainer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    trainer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    role: Mapped[str] = mapped_column(BatchTrainerRole, default="Co-trainer")
    from_date: Mapped[date] = mapped_column(Date, server_default=db.func.current_date())
    to_date: Mapped[date | None] = mapped_column(Date)

    batch: Mapped[Batch] = relationship(back_populates="trainers")
    trainer: Mapped[User] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {"batch_trainer_id": self.batch_trainer_id, "user_id": self.trainer_user_id, "full_name": self.trainer.full_name,
                "role": self.role, "from_date": self.from_date, "to_date": self.to_date}


class BatchAllocation(db.Model):
    __tablename__ = "batch_allocations"

    allocation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    enrolment_track_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolment_tracks.enrolment_track_id"))
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    status: Mapped[str] = mapped_column(AllocationStatus, default="Active")
    effective_from: Mapped[date] = mapped_column(Date, server_default=db.func.current_date())
    effective_to: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "allocation_id": self.allocation_id,
            "enrolment_id": self.enrolment_id,
            "batch": self.batch.to_summary(),
            "status": self.status,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "reason": self.reason,
        }


class ClassSession(db.Model):
    """An actual class session: one delivery of a topic to a batch at a time."""

    __tablename__ = "class_sessions"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(DeliveryMode)
    trainer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    room: Mapped[str | None] = mapped_column(String(100))
    meet_link: Mapped[str | None] = mapped_column(String(500))
    meet_status: Mapped[str] = mapped_column(MeetStatus, default="Not Required")
    state: Mapped[str] = mapped_column(SessionState, default="Scheduled")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")
    topic: Mapped[CurriculumTopic | None] = relationship(lazy="joined")
    trainer: Mapped[User] = relationship(lazy="joined")

    def to_summary(self) -> dict:
        return {"session_id": self.session_id, "session_code": self.session_code, "title": self.title,
                "starts_at": self.starts_at, "ends_at": self.ends_at, "state": self.state}

    def to_dict(self, *, include_link: bool = True, join: dict | None = None) -> dict:
        """include_link: staff see the Meet link; a learner gets it only through `join`, when joining is open."""
        return {
            "session_id": self.session_id,
            "session_code": self.session_code,
            "batch": self.batch.to_summary(),
            "branch": self.batch.branch.to_summary(),
            "course": self.batch.course.to_summary(),
            "topic": {"topic_id": self.topic.topic_id, "title": self.topic.title, "module_id": self.topic.module_id} if self.topic else None,
            "title": self.title,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "mode": self.mode,
            "trainer": {"user_id": self.trainer_user_id, "full_name": self.trainer.full_name},
            "room": self.room,
            "meet_link": self.meet_link if include_link else None,
            "meet_status": self.meet_status,
            "meet_status_label": MEET_STATUS_LABELS[self.meet_status],
            "organizer_email": self.batch.branch.mailbox if self.mode != "Classroom" else None,
            "join": join,
            "state": self.state,
            "delivered_at": self.delivered_at,
            "notes": self.notes,
        }


class BatchCrmState(db.Model):
    """Last batch state queued for the CRM (kept by triggers, db 005); what the CRM pull endpoint reads."""

    __tablename__ = "batch_crm_state"

    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


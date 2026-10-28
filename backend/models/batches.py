"""Batches, batch trainers, allocations and class sessions."""
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.catalog import Course, CourseComponent, CourseTopic
from models.enums import (
    AllocationStatus, BatchReadiness, BatchState, BatchTrainerRole, DeliveryMode, MeetStatus, SessionState,
)
from models.masters import Branch

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Module 15's names for the stored states. The stored values stay as they were (the CRM and the views read them).
BATCH_STATE_LABELS = {"Forming": "Draft", "Proposed": "Proposed", "Starting": "Confirmed", "Running": "In Progress",
                      "Full": "In Progress (Full)", "On Hold": "On Hold", "Completed": "Completed", "Cancelled": "Cancelled",
                      "Archived": "Archived"}


def session_state_label(state: str, confirmed: bool, outcome: str | None) -> str:
    """Planned / Confirmed / Rescheduled / In Progress / Held / Partially Held / Cancelled (Module 15 §15)."""
    if state == "Delivered":
        return outcome or "Held"
    if state == "Live":
        return "In Progress"
    if state == "Scheduled":
        return "Confirmed" if confirmed else "Planned"
    return state


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
    # Module 15 (db 103): type, pattern and display name; the creating branch stays in the code, branch_id is the service branch
    display_name: Mapped[str | None] = mapped_column(String(200))
    batch_type: Mapped[str] = mapped_column(String(20), default="Group")
    schedule_pattern: Mapped[str] = mapped_column(String(20), default="Regular")
    creating_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"), server_default=FetchedValue())
    component_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_components.component_id"))
    classroom_capacity: Mapped[int | None] = mapped_column(Integer)
    lab_capacity: Mapped[int | None] = mapped_column(Integer)
    online_capacity: Mapped[int | None] = mapped_column(Integer)
    recording_provision: Mapped[str | None] = mapped_column(String(20))
    recording_terms: Mapped[str | None] = mapped_column(Text)
    held_from_state: Mapped[str | None] = mapped_column(BatchState)
    proposed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_note: Mapped[str | None] = mapped_column(Text)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_checklist: Mapped[list | None] = mapped_column(JSONB)
    meet_series_link: Mapped[str | None] = mapped_column(String(500))
    meet_space_id: Mapped[str | None] = mapped_column(String(200))
    calendar_series_id: Mapped[str | None] = mapped_column(String(200))
    seed_data: Mapped[bool] = mapped_column(Boolean, default=False)  # made-up CRM batch ID from `flask seed-dev` (db 090)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined", foreign_keys=[branch_id])
    creating_branch: Mapped[Branch] = relationship(lazy="joined", foreign_keys=[creating_branch_id], viewonly=True)
    component: Mapped[CourseComponent | None] = relationship(lazy="joined")
    proposer: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[proposed_by], viewonly=True)
    confirmer: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[confirmed_by], viewonly=True)
    trainers: Mapped[list["BatchTrainer"]] = relationship(
        back_populates="batch", order_by="BatchTrainer.batch_trainer_id", cascade="all, delete-orphan"
    )

    def to_summary(self) -> dict:
        return {"batch_id": self.batch_id, "batch_code": self.batch_code, "course_code": self.course.course_code,
                "display_name": self.display_name}

    def to_dict(self, allocated_count: int = 0) -> dict:
        return {
            "batch_id": self.batch_id,
            "batch_code": self.batch_code,
            "display_name": self.display_name,
            "crm_batch_id": self.crm_batch_id,
            "course": self.course.to_summary(),
            "component": {"component_id": self.component.component_id, "track_code": self.component.track_code,
                          "track_name": self.component.track_name} if self.component else None,
            "branch": self.branch.to_summary(),
            "creating_branch": self.creating_branch.to_summary(),
            "batch_type": self.batch_type,
            "schedule_pattern": self.schedule_pattern,
            "capacity": self.capacity,
            "classroom_capacity": self.classroom_capacity,
            "lab_capacity": self.lab_capacity,
            "online_capacity": self.online_capacity,
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
            "state_label": BATCH_STATE_LABELS[self.state],
            "held_from_state": self.held_from_state,
            "recording_provision": self.recording_provision,
            "recording_terms": self.recording_terms,
            "proposed_by": _person(self.proposer),
            "proposed_at": self.proposed_at,
            "proposal_note": self.proposal_note,
            "confirmed_by": _person(self.confirmer),
            "confirmed_at": self.confirmed_at,
            "meet_series_link": self.meet_series_link,
            "meet_space_id": self.meet_space_id,
            "calendar_series_id": self.calendar_series_id,
            "readiness": self.readiness,
            "readiness_reason": self.readiness_reason,
            "recovery_owner": self.recovery_owner,
            "trainers": [t.to_dict() for t in self.trainers if t.to_date is None],
        }


def _person(user: User | None) -> dict | None:
    return None if user is None else {"user_id": user.user_id, "full_name": user.full_name}


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
            "enrolment_track_id": self.enrolment_track_id,
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
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_topics.topic_id"))
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
    # Module 15 §15-16, Module 16 (db 103)
    original_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    original_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    live_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_outcome: Mapped[str | None] = mapped_column(String(20), server_default=FetchedValue(), server_onupdate=FetchedValue())
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    delivered_minutes: Mapped[int | None] = mapped_column(Integer)
    unfulfilled_note: Mapped[str | None] = mapped_column(Text)
    log_overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delay_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str] = mapped_column(String(20), default="Regular")
    replaces_session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    purpose_reference: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(20), default="Not Required")
    proposed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    due_on: Mapped[date | None] = mapped_column(Date)
    replacement_waiver: Mapped[str | None] = mapped_column(Text)
    room_override_reason: Mapped[str | None] = mapped_column(Text)
    hosting_branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"), server_default=FetchedValue())
    meet_space_id: Mapped[str | None] = mapped_column(String(200))
    calendar_event_id: Mapped[str | None] = mapped_column(String(200))
    calendar_series_id: Mapped[str | None] = mapped_column(String(200))
    conference_record_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")
    topic: Mapped[CourseTopic | None] = relationship(lazy="joined")
    trainer: Mapped[User] = relationship(lazy="joined", foreign_keys=[trainer_user_id])
    owner: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[owner_user_id], viewonly=True)

    @property
    def state_label(self) -> str:
        return session_state_label(self.state, self.confirmed_at is not None, self.delivery_outcome)

    @property
    def planned_minutes(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds() // 60)

    def to_summary(self) -> dict:
        return {"session_id": self.session_id, "session_code": self.session_code, "title": self.title,
                "starts_at": self.starts_at, "ends_at": self.ends_at, "state": self.state, "state_label": self.state_label}

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
            "organizer_email": self.batch.branch.organizer_mailbox if self.mode != "Classroom" else None,
            "join": join,
            "state": self.state,
            "state_label": self.state_label,
            "delivered_at": self.delivered_at,
            "notes": self.notes,
            "original_starts_at": self.original_starts_at,
            "original_ends_at": self.original_ends_at,
            "confirmed_at": self.confirmed_at,
            "live_at": self.live_at,
            "purpose": self.purpose,
            "replaces_session_id": self.replaces_session_id,
            "approval_status": self.approval_status,
            "delivery_outcome": self.delivery_outcome,
            "actual_start": self.actual_start,
            "actual_end": self.actual_end,
            "break_minutes": self.break_minutes,
            "planned_minutes": self.planned_minutes,
            "delivered_minutes": self.delivered_minutes,
            "unfulfilled_note": self.unfulfilled_note,
            "hosting_branch_id": self.hosting_branch_id,
            **({} if not include_link else {
                "purpose_reference": self.purpose_reference,
                "owner": _person(self.owner),
                "due_on": self.due_on,
                "replacement_waiver": self.replacement_waiver,
                "room_override_reason": self.room_override_reason,
                "log_overdue_at": self.log_overdue_at,
                "meet_space_id": self.meet_space_id,
                "calendar_event_id": self.calendar_event_id,
                "calendar_series_id": self.calendar_series_id,
                "conference_record_id": self.conference_record_id,
            }),
        }


class BatchCrmState(db.Model):
    """Last batch state queued for the CRM (kept by triggers, db 005); what the CRM pull endpoint reads."""

    __tablename__ = "batch_crm_state"

    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


"""Delivery history: curriculum review trail, batch events, session changes, reschedule requests, Meet association log."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.batches import ClassSession
from models.enums import CurriculumStatus, MeetStatus, RescheduleRequestStatus


class CurriculumEvent(db.Model):
    """One step in a curriculum version's life (created, submitted, approved, activated, ...)."""

    __tablename__ = "curriculum_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    action: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(CurriculumStatus)
    to_status: Mapped[str] = mapped_column(CurriculumStatus)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    actor: Mapped[User | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "action": self.action,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "actor": self.actor.to_summary() if self.actor else None,
            "note": self.note,
            "created_at": self.created_at,
        }


class BatchEvent(db.Model):
    """History of a batch: state, readiness, trainer and curriculum changes with who and why."""

    __tablename__ = "batch_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    event_type: Mapped[str] = mapped_column(String(40))
    from_value: Mapped[str | None] = mapped_column(String(200))
    to_value: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    actor: Mapped[User | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "reason": self.reason,
            "actor": self.actor.to_summary() if self.actor else None,
            "created_at": self.created_at,
        }


class SessionChange(db.Model):
    """A reschedule, cancellation or substitute trainer, with the original slot kept."""

    __tablename__ = "session_changes"

    change_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    change_type: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    old_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    new_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    old_trainer_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    new_trainer_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    notice_hours: Mapped[Decimal] = mapped_column(Numeric(8, 1))
    short_notice: Mapped[bool] = mapped_column(Boolean, default=False)
    changed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    old_trainer: Mapped[User | None] = relationship(foreign_keys=[old_trainer_user_id], lazy="joined")
    new_trainer: Mapped[User | None] = relationship(foreign_keys=[new_trainer_user_id], lazy="joined")
    changer: Mapped[User | None] = relationship(foreign_keys=[changed_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type,
            "reason": self.reason,
            "old_starts_at": self.old_starts_at,
            "old_ends_at": self.old_ends_at,
            "new_starts_at": self.new_starts_at,
            "new_ends_at": self.new_ends_at,
            "old_trainer": self.old_trainer.to_summary() if self.old_trainer else None,
            "new_trainer": self.new_trainer.to_summary() if self.new_trainer else None,
            "notice_hours": self.notice_hours,
            "short_notice": self.short_notice,
            "changed_by": self.changer.to_summary() if self.changer else None,
            "created_at": self.created_at,
        }


class SessionChangeRequest(db.Model):
    """A trainer's request to move a session; an Academic Coordinator or Branch Manager approves or rejects it."""

    __tablename__ = "session_change_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    proposed_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proposed_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(RescheduleRequestStatus, default="Open")
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    session: Mapped[ClassSession] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "session": {
                "session_id": self.session.session_id,
                "session_code": self.session.session_code,
                "title": self.session.title,
                "starts_at": self.session.starts_at,
                "ends_at": self.session.ends_at,
                "state": self.session.state,
                "batch": self.session.batch.to_summary(),
            },
            "requested_by": self.requester.to_summary(),
            "proposed_starts_at": self.proposed_starts_at,
            "proposed_ends_at": self.proposed_ends_at,
            "reason": self.reason,
            "status": self.status,
            "decided_by": self.decider.to_summary() if self.decider else None,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
            "created_at": self.created_at,
        }


class MeetEvent(db.Model):
    """One entry in a session's Meet association log (the LMS records state; it never calls Google)."""

    __tablename__ = "meet_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    event_type: Mapped[str] = mapped_column(String(30))
    meet_status: Mapped[str] = mapped_column(MeetStatus)
    organizer_email: Mapped[str | None] = mapped_column(String(255))
    meet_link: Mapped[str | None] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    actor: Mapped[User | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "meet_status": self.meet_status,
            "organizer_email": self.organizer_email,
            "meet_link": self.meet_link,
            "detail": self.detail,
            "actor": self.actor.to_summary() if self.actor else None,
            "created_at": self.created_at,
        }

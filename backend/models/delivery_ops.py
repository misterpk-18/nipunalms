"""Batch and class operations (db 103, Modules 15 and 16): capacity and transfer requests, material changes and agreements,
merge / split successions, completion handovers, cover requests, hosts and guests, link incidents, Meet participation,
disruptions, shared-class rosters, student slot preferences and job runs."""
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.batches import WEEKDAYS, Batch, ClassSession
from models.certificates import ApprovalStatus
from models.enums import DeliveryMode


def _user(user: User | None) -> dict | None:
    return None if user is None else {"user_id": user.user_id, "full_name": user.full_name}


def _session(session: ClassSession) -> dict:
    return {**session.to_summary(), "batch": session.batch.to_summary(), "branch_id": session.batch.branch_id}


class _Requested:
    """Who asked and who decided, for request tables with requested_by / decided_by."""

    def decision_dict(self) -> dict:
        return {"status": self.status, "requested_by": _user(self.requester), "requested_at": self.requested_at,
                "decided_by": _user(self.decider), "decided_at": self.decided_at, "decision_note": self.decision_note}


class BatchCapacityRequest(_Requested, db.Model):
    __tablename__ = "batch_capacity_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    from_capacity: Mapped[int] = mapped_column(Integer)
    to_capacity: Mapped[int] = mapped_column(Integer)
    classroom_capacity: Mapped[int | None] = mapped_column(Integer)
    lab_capacity: Mapped[int | None] = mapped_column(Integer)
    online_capacity: Mapped[int | None] = mapped_column(Integer)
    resource_validation: Mapped[str] = mapped_column(Text)
    academic_review: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    batch: Mapped[Batch] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(lazy="joined", foreign_keys=[requested_by])
    decider: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[decided_by])

    def to_dict(self) -> dict:
        return {"request_id": self.request_id, "batch": self.batch.to_summary(), "from_capacity": self.from_capacity,
                "to_capacity": self.to_capacity, "classroom_capacity": self.classroom_capacity, "lab_capacity": self.lab_capacity,
                "online_capacity": self.online_capacity, "resource_validation": self.resource_validation,
                "academic_review": self.academic_review, **self.decision_dict()}


class BatchTransferRequest(_Requested, db.Model):
    __tablename__ = "batch_transfer_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    enrolment_track_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolment_tracks.enrolment_track_id"))
    from_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    to_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    interbranch: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text)
    acknowledged_warnings: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    destination_confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    destination_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    applied_allocation_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batch_allocations.allocation_id"))

    from_batch: Mapped[Batch | None] = relationship(lazy="joined", foreign_keys=[from_batch_id])
    to_batch: Mapped[Batch] = relationship(lazy="joined", foreign_keys=[to_batch_id])
    requester: Mapped[User] = relationship(lazy="joined", foreign_keys=[requested_by])
    decider: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[decided_by])
    destination_confirmer: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[destination_confirmed_by])

    def to_dict(self, enrolment=None) -> dict:
        return {"request_id": self.request_id, "enrolment_id": self.enrolment_id,
                "enrolment": enrolment.to_summary() if enrolment is not None else None,
                "enrolment_track_id": self.enrolment_track_id,
                "from_batch": self.from_batch.to_summary() if self.from_batch else None, "to_batch": self.to_batch.to_summary(),
                "from_branch_id": self.from_batch.branch_id if self.from_batch else None, "to_branch_id": self.to_batch.branch_id,
                "interbranch": self.interbranch, "reason": self.reason, "acknowledged_warnings": self.acknowledged_warnings,
                "destination_confirmed_by": _user(self.destination_confirmer), "destination_confirmed_at": self.destination_confirmed_at,
                "applied_allocation_id": self.applied_allocation_id, **self.decision_dict()}


class MaterialChange(_Requested, db.Model):
    __tablename__ = "material_changes"

    change_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    kind: Mapped[str] = mapped_column(String(30))
    current_plan: Mapped[str] = mapped_column(Text)
    proposed_plan: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)
    alternative: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Pending Approval")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    applied_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reply_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # students answer by this time (db/109)

    batch: Mapped[Batch] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(lazy="joined", foreign_keys=[requested_by])
    decider: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[decided_by])
    responses: Mapped[list["MaterialChangeResponse"]] = relationship(
        back_populates="change", order_by="MaterialChangeResponse.response_id", cascade="all, delete-orphan")

    def counts(self) -> dict:
        tally = {"Pending": 0, "Agreed": 0, "Declined": 0}
        for r in self.responses:
            tally[r.response] += 1
        return tally

    def to_dict(self, *, include_responses: bool = True) -> dict:
        return {"change_id": self.change_id, "batch": self.batch.to_summary(), "kind": self.kind, "current_plan": self.current_plan,
                "proposed_plan": self.proposed_plan, "reason": self.reason, "changes": self.changes, "alternative": self.alternative,
                "applied_at": self.applied_at, "reply_by": self.reply_by, "response_counts": self.counts(),
                **({"responses": [r.to_dict() for r in self.responses]} if include_responses else {}), **self.decision_dict()}


class MaterialChangeResponse(db.Model):
    __tablename__ = "material_change_responses"

    response_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    change_id: Mapped[int] = mapped_column(Integer, ForeignKey("material_changes.change_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    response: Mapped[str] = mapped_column(String(20), default="Pending")
    note: Mapped[str | None] = mapped_column(Text)
    alternative_arranged: Mapped[str | None] = mapped_column(Text)
    recorded_via: Mapped[str | None] = mapped_column(String(20))
    recorded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    change: Mapped[MaterialChange] = relationship(back_populates="responses")
    recorder: Mapped[User | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {"response_id": self.response_id, "enrolment_id": self.enrolment_id, "response": self.response, "note": self.note,
                "alternative_arranged": self.alternative_arranged, "recorded_via": self.recorded_via,
                "recorded_by": _user(self.recorder), "responded_at": self.responded_at}


class BatchSuccession(_Requested, db.Model):
    __tablename__ = "batch_successions"

    succession_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    from_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    to_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    enrolment_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    effective_from: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    academic_review: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    moved_count: Mapped[int | None] = mapped_column(Integer)

    from_batch: Mapped[Batch] = relationship(lazy="joined", foreign_keys=[from_batch_id])
    to_batch: Mapped[Batch] = relationship(lazy="joined", foreign_keys=[to_batch_id])
    requester: Mapped[User] = relationship(lazy="joined", foreign_keys=[requested_by])
    decider: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[decided_by])

    def to_dict(self) -> dict:
        return {"succession_id": self.succession_id, "kind": self.kind, "from_batch": self.from_batch.to_summary(),
                "to_batch": self.to_batch.to_summary(), "enrolment_ids": self.enrolment_ids, "effective_from": self.effective_from,
                "reason": self.reason, "academic_review": self.academic_review, "moved_count": self.moved_count, **self.decision_dict()}


class BatchHandover(db.Model):
    __tablename__ = "batch_handovers"

    handover_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    plan: Mapped[str] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text)
    destination_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    recorded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    owner: Mapped[User] = relationship(lazy="joined", foreign_keys=[owner_user_id])

    def to_dict(self) -> dict:
        return {"handover_id": self.handover_id, "batch_id": self.batch_id, "enrolment_id": self.enrolment_id, "owner": _user(self.owner),
                "plan": self.plan, "destination": self.destination, "destination_batch_id": self.destination_batch_id,
                "recorded_at": self.recorded_at}


class SessionCoverRequest(db.Model):
    __tablename__ = "session_cover_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    cover_role: Mapped[str] = mapped_column(String(20))
    planned_trainer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    cover_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    reason: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    handover: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_note: Mapped[str | None] = mapped_column(Text)
    decision_note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[ClassSession] = relationship(lazy="joined")
    planned_trainer: Mapped[User] = relationship(lazy="joined", foreign_keys=[planned_trainer_user_id])
    cover: Mapped[User] = relationship(lazy="joined", foreign_keys=[cover_user_id])
    requester: Mapped[User] = relationship(lazy="joined", foreign_keys=[requested_by])
    approver: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[approved_by])
    verifier: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[verified_by])

    def to_dict(self) -> dict:
        return {"request_id": self.request_id, "session": _session(self.session), "cover_role": self.cover_role,
                "planned_trainer": _user(self.planned_trainer), "cover": _user(self.cover), "reason": self.reason, "scope": self.scope,
                "handover": self.handover, "status": self.status, "requested_by": _user(self.requester), "requested_at": self.requested_at,
                "approved_by": _user(self.approver), "approved_at": self.approved_at, "verified_by": _user(self.verifier),
                "verified_at": self.verified_at, "verification_note": self.verification_note, "decision_note": self.decision_note,
                "applied_at": self.applied_at}


class SessionPerson(db.Model):
    __tablename__ = "session_people"

    session_person_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    role: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    guest_name: Mapped[str | None] = mapped_column(String(150))
    guest_email: Mapped[str | None] = mapped_column(String(255))
    purpose: Mapped[str | None] = mapped_column(Text)
    student_agreement: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Approved")
    added_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[user_id])
    adder: Mapped[User] = relationship(lazy="joined", foreign_keys=[added_by])
    decider: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[decided_by])

    def to_dict(self) -> dict:
        return {"session_person_id": self.session_person_id, "session_id": self.session_id, "role": self.role, "user": _user(self.person),
                "guest_name": self.guest_name, "guest_email": self.guest_email, "purpose": self.purpose,
                "student_agreement": self.student_agreement, "status": self.status, "added_by": _user(self.adder),
                "added_at": self.added_at, "decided_by": _user(self.decider), "decided_at": self.decided_at, "removed_at": self.removed_at}


class MeetIncident(db.Model):
    __tablename__ = "meet_incidents"

    incident_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    kind: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    actions_taken: Mapped[str] = mapped_column(Text)
    old_meet_link: Mapped[str | None] = mapped_column(String(500))
    link_replaced: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    participants_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manager_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped[User] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {"incident_id": self.incident_id, "session_id": self.session_id, "kind": self.kind, "description": self.description,
                "actions_taken": self.actions_taken, "old_meet_link": self.old_meet_link, "link_replaced": self.link_replaced,
                "reported_by": _user(self.reporter), "reported_at": self.reported_at,
                "participants_notified_at": self.participants_notified_at, "manager_alerted_at": self.manager_alerted_at}


class MeetParticipation(db.Model):
    __tablename__ = "meet_participation"

    participation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    participant_name: Mapped[str | None] = mapped_column(String(200))
    participant_email: Mapped[str | None] = mapped_column(String(255))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), default="Manual")
    match_status: Mapped[str] = mapped_column(String(20), default="Unmatched")
    matched_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    matched_enrolment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    matched_user: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[matched_user_id])

    def to_dict(self) -> dict:
        return {"participation_id": self.participation_id, "session_id": self.session_id, "participant_name": self.participant_name,
                "participant_email": self.participant_email, "joined_at": self.joined_at, "left_at": self.left_at, "source": self.source,
                "match_status": self.match_status, "matched_user": _user(self.matched_user),
                "matched_enrolment_id": self.matched_enrolment_id, "reviewed_at": self.reviewed_at, "review_note": self.review_note}


class SessionDisruption(db.Model):
    __tablename__ = "session_disruptions"

    disruption_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    kind: Mapped[str] = mapped_column(String(30))
    cause: Mapped[str] = mapped_column(String(20), default="Unknown")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    delay_minutes: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    undelivered_minutes: Mapped[int | None] = mapped_column(Integer)
    recovery_plan: Mapped[str | None] = mapped_column(Text)
    replacement_session_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    status: Mapped[str] = mapped_column(String(20), default="Open")
    raised_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[ClassSession] = relationship(lazy="joined", foreign_keys=[session_id])
    owner: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[owner_user_id])
    resolver: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[resolved_by])

    def to_dict(self) -> dict:
        return {"disruption_id": self.disruption_id, "session": _session(self.session), "kind": self.kind, "cause": self.cause,
                "detected_at": self.detected_at, "delay_minutes": self.delay_minutes, "detail": self.detail,
                "undelivered_minutes": self.undelivered_minutes, "recovery_plan": self.recovery_plan,
                "replacement_session_id": self.replacement_session_id, "owner": _user(self.owner), "status": self.status,
                "raised_by_job": self.raised_by is None, "resolved_by": _user(self.resolver), "resolved_at": self.resolved_at}


class SessionRoster(db.Model):
    """A batch joined to another batch's class (a shared class, Module 15 §4)."""

    __tablename__ = "session_rosters"

    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("batches.batch_id"), primary_key=True)
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    coverage_note: Mapped[str] = mapped_column(Text)
    verified_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch] = relationship(lazy="joined")
    verifier: Mapped[User] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {"session_id": self.session_id, "batch": self.batch.to_summary(), "branch_id": self.batch.branch_id, "topic_id": self.topic_id,
                "coverage_note": self.coverage_note, "verified_by": _user(self.verifier), "verified_at": self.verified_at}


class SlotPreference(db.Model):
    __tablename__ = "slot_preferences"

    preference_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    preferred_days: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    preferred_start: Mapped[time | None] = mapped_column(Time)
    preferred_end: Mapped[time | None] = mapped_column(Time)
    preferred_mode: Mapped[str | None] = mapped_column(DeliveryMode)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Requested")
    status_note: Mapped[str | None] = mapped_column(Text)
    status_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    batch: Mapped[Batch | None] = relationship(lazy="joined")

    def to_dict(self, enrolment=None) -> dict:
        return {"preference_id": self.preference_id, "enrolment_id": self.enrolment_id,
                "enrolment": enrolment.to_summary() if enrolment is not None else None,
                "batch": self.batch.to_summary() if self.batch else None,
                "preferred_days": [WEEKDAYS[d - 1] for d in self.preferred_days or []],
                "preferred_start": self.preferred_start.strftime("%H:%M") if self.preferred_start else None,
                "preferred_end": self.preferred_end.strftime("%H:%M") if self.preferred_end else None,
                "preferred_mode": self.preferred_mode, "note": self.note, "status": self.status, "status_note": self.status_note,
                "status_at": self.status_at, "created_at": self.created_at,
                "reserves_seat": False}


class JobRun(db.Model):
    __tablename__ = "job_runs"

    job_name: Mapped[str] = mapped_column(String(60), primary_key=True)
    last_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {"job_name": self.job_name, "last_started_at": self.last_started_at, "last_finished_at": self.last_finished_at,
                "last_ok_at": self.last_ok_at, "last_result": self.last_result, "last_error": self.last_error}

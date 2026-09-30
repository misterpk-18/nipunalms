"""Support requests and their message thread."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, FetchedValue, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.masters import Branch
from models.students import Enrolment, Student

SUPPORT_CATEGORIES = ("Academic", "LMS", "Account", "Recording access", "Device access", "Other")
SUPPORT_PRIORITIES = ("Normal", "High", "Urgent")
SUPPORT_STATUSES = ("Open", "In Progress", "Waiting on Student", "Resolved", "Closed")
# A request in one of these is still being worked on (it can breach its SLA and be escalated)
SUPPORT_OPEN_STATUSES = ("Open", "In Progress", "Waiting on Student")
OWNER_ROLES = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN")


class SupportRequest(db.Model):
    __tablename__ = "support_requests"

    support_request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_code: Mapped[str] = mapped_column(String(20), unique=True, server_default=FetchedValue())  # trigger
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    enrolment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    category: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(200))
    priority: Mapped[str] = mapped_column(String(10), default="Normal")
    status: Mapped[str] = mapped_column(String(30), default="Open")
    raised_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    raised_via: Mapped[str] = mapped_column(String(20), default="Student")
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    owner_role: Mapped[str] = mapped_column(String(30))
    escalation_level: Mapped[str | None] = mapped_column(String(30))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())  # trigger
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    student: Mapped[Student] = relationship(lazy="joined")
    enrolment: Mapped[Enrolment | None] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    raised_by: Mapped[User] = relationship(foreign_keys=[raised_by_user_id], lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id], lazy="joined")
    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="request", order_by="SupportMessage.support_message_id", cascade="all, delete-orphan"
    )

    def owner_label(self) -> str:
        """'Academic Coordinator — Guntur'; the Super Admin who handles LMS / account issues shows as LMS Support."""
        if self.owner_role == "SUPER_ADMIN":
            return f"LMS Support — {self.branch.branch_name}"
        role = {"TRAINER": "Trainer", "ACADEMIC_COORDINATOR": "Academic Coordinator", "BRANCH_MANAGER": "Branch Manager"}[self.owner_role]
        return f"{role} — {self.branch.branch_name}"

    def to_summary(self, now: datetime) -> dict:
        return {
            "support_request_id": self.support_request_id,
            "request_code": self.request_code,
            "student": self.student.to_summary(),
            "enrolment": self.enrolment.to_summary() if self.enrolment else None,
            "branch": self.branch.to_summary(),
            "category": self.category,
            "subject": self.subject,
            "priority": self.priority,
            "status": self.status,
            "raised_via": self.raised_via,
            "raised_by": self.raised_by.to_summary(),
            "owner": {**self.owner.to_summary(), "role_code": self.owner_role, "label": self.owner_label()},
            "escalation_level": self.escalation_level,
            "escalated_at": self.escalated_at,
            "sla_due_at": self.sla_due_at,
            "sla_breached": self.status in SUPPORT_OPEN_STATUSES and self.sla_due_at < now,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(self, now: datetime, *, include_internal: bool, student_user_id: int | None) -> dict:
        """The full request with its thread. `student_user_id` (the student's login) tells which messages the student wrote."""
        return {
            **self.to_summary(now),
            "escalation_reason": self.escalation_reason,
            "resolution_note": self.resolution_note,
            "resolved_at": self.resolved_at,
            "closed_at": self.closed_at,
            "reopened_count": self.reopened_count,
            "messages": [
                {**m.to_dict(), "from_student": m.author_user_id is not None and m.author_user_id == student_user_id}
                for m in self.messages
                if include_internal or not m.is_internal
            ],
        }


class SupportMessage(db.Model):
    """One line of the thread or of the request's history. Append-only."""

    __tablename__ = "support_messages"

    support_message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    support_request_id: Mapped[int] = mapped_column(Integer, ForeignKey("support_requests.support_request_id"))
    author_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    kind: Mapped[str] = mapped_column(String(20), default="Message")
    body: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    request: Mapped[SupportRequest] = relationship(back_populates="messages")
    author: Mapped[User | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "support_message_id": self.support_message_id,
            "author": self.author.to_summary() if self.author else {"user_id": None, "full_name": "System", "email": None},
            "kind": self.kind,
            "body": self.body,
            "is_internal": self.is_internal,
            "created_at": self.created_at,
        }

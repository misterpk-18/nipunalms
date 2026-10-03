"""The Nipuna Academic Calendar: company holidays and branch closures (db 101)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.certificates import ApprovalStatus
from models.enums import _pg_enum
from models.masters import Branch

CLOSURE_KINDS = ("Company Holiday", "Branch Closure")
CalendarClosureKind = _pg_enum("calendar_closure_kind", CLOSURE_KINDS)


class CalendarClosure(db.Model):
    __tablename__ = "calendar_closures"

    closure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(CalendarClosureKind)
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    branch: Mapped[Branch | None] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "closure_id": self.closure_id,
            "kind": self.kind,
            "branch": self.branch.to_summary() if self.branch else None,
            "starts_on": self.starts_on,
            "ends_on": self.ends_on,
            "title": self.title,
            "reason": self.reason,
            "status": self.status,
            "requested_by": {"user_id": self.requester.user_id, "full_name": self.requester.full_name},
            "requested_at": self.requested_at,
            "decided_by": None if self.decider is None else {"user_id": self.decider.user_id, "full_name": self.decider.full_name},
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }

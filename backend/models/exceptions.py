"""The cross-slice exception queue (the `exception_queue` view, never written) and the recovery steps logged against it."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.masters import Branch

# Must match the `source` values in db/080_exception_queue.sql
EXCEPTION_SOURCES = (
    "CURRICULUM_MAPPING", "ALLOCATION", "PROVISIONING", "RECORDING", "CRM_EVENT", "SUPPORT", "RESULTS", "ACCESS_EXCEPTION", "INTEGRATION",
)


class ExceptionItem(db.Model):
    """One open exception from any slice. Keyed by (source, source_id): the record's id in its own table."""

    __tablename__ = "exception_queue"

    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(100))
    queue: Mapped[str] = mapped_column(String(40))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    title: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    owner_name: Mapped[str | None] = mapped_column(String(150))
    owner_label: Mapped[str | None] = mapped_column(String(100))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(40))
    link: Mapped[str] = mapped_column(String(100))
    step_count: Mapped[int] = mapped_column(Integer)
    last_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    branch: Mapped[Branch | None] = relationship(lazy="joined", viewonly=True)

    def to_dict(self, now: datetime) -> dict:
        owner_label = self.owner_label
        if self.branch is not None and owner_label and owner_label != "Super Admin":
            owner_label = f"{owner_label} — {self.branch.branch_name}"
        return {
            "source": self.source,
            "source_id": self.source_id,
            "reference": self.reference,
            "queue": self.queue,
            "branch": self.branch.to_summary() if self.branch else None,
            "title": self.title,
            "detail": self.detail,
            "owner": {"user_id": self.owner_user_id, "full_name": self.owner_name} if self.owner_user_id else None,
            "owner_label": owner_label,
            "awaiting_owner": self.owner_user_id is None,
            "opened_at": self.opened_at,
            "age_days": max(0, (now - self.opened_at).days),
            "state": self.state,
            "link": self.link,
            "step_count": self.step_count,
            "last_step_at": self.last_step_at,
        }


class ExceptionRecoveryStep(db.Model):
    """Append-only (a trigger blocks UPDATE and DELETE)."""

    __tablename__ = "exception_recovery_steps"

    step_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[int] = mapped_column(Integer)
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    reason: Mapped[str] = mapped_column(Text)
    logged_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    author: Mapped[User] = relationship(lazy="joined", foreign_keys=[logged_by])

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "source": self.source,
            "source_id": self.source_id,
            "reason": self.reason,
            "logged_by": {"user_id": self.author.user_id, "full_name": self.author.full_name},
            "logged_at": self.logged_at,
        }

"""Branches, and the CRM's finance figures per branch."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db


class Branch(db.Model):
    __tablename__ = "branches"

    branch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_code: Mapped[str] = mapped_column(String(20), unique=True)
    short_code: Mapped[str] = mapped_column(String(10), unique=True)
    branch_name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    mailbox: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_version: Mapped[int] = mapped_column(Integer, default=0)  # last BranchUpserted applied; 0 = made in the LMS (db 096)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "branch_code": self.branch_code,
            "short_code": self.short_code,
            "branch_name": self.branch_name,
            "city": self.city,
            "mailbox": self.mailbox,
            "is_active": self.is_active,
        }

    def to_summary(self) -> dict:
        return {"branch_id": self.branch_id, "branch_code": self.branch_code, "branch_name": self.branch_name}


class BranchFinanceSnapshot(db.Model):
    """The CRM's latest finance figures for one branch (BranchFinanceSnapshot event, db 096). Read-only in the LMS."""

    __tablename__ = "branch_finance_snapshots"

    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"), primary_key=True)
    source_version: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_label: Mapped[str | None] = mapped_column(String(50))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    collections_verified: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    collections_target: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    paid_admissions: Mapped[int] = mapped_column(Integer)
    paid_admissions_target: Mapped[int | None] = mapped_column(Integer)
    overdue_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    overdue_count: Mapped[int] = mapped_column(Integer)
    overdue_by_age_band: Mapped[list] = mapped_column(JSONB, default=list)
    verifications_pending: Mapped[int] = mapped_column(Integer)
    verifications_pending_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    verifications_overdue: Mapped[int] = mapped_column(Integer)
    verifications_oldest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followups_overdue: Mapped[int] = mapped_column(Integer)
    broken_promises: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

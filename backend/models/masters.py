"""Branches."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
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

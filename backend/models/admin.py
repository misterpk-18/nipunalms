"""Security readiness register (the integrations register lives in models/system.py)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db
from models.enums import IntegrationConfigurationStatus, IntegrationVerificationStatus


class SecurityControl(db.Model):
    """One security requirement: what is required, whether it is configured, whether it is verified, and the evidence."""

    __tablename__ = "security_controls"

    control_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_code: Mapped[str] = mapped_column(String(50), unique=True)
    category: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    requirement: Mapped[str] = mapped_column(Text)
    configuration_status: Mapped[str] = mapped_column(IntegrationConfigurationStatus)
    verification_status: Mapped[str] = mapped_column(IntegrationVerificationStatus)
    owner: Mapped[str] = mapped_column(String(100))
    evidence: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "control_code": self.control_code,
            "category": self.category,
            "title": self.title,
            "requirement": self.requirement,
            "configuration_status": self.configuration_status,
            "verification_status": self.verification_status,
            "owner": self.owner,
            "evidence": self.evidence,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "last_checked_at": self.last_checked_at,
            "notes": self.notes,
        }

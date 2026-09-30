"""Settings, audit log, integrations register, notifications and learning activity."""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db
from models.enums import (
    IntegrationConfigurationStatus, IntegrationVerificationStatus, NotificationActionStatus, NotificationDeliveryStatus,
)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    setting_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    setting_value: Mapped[Any] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"setting_key": self.setting_key, "setting_value": self.setting_value, "description": self.description}


class AuditLog(db.Model):
    """Append-only (a trigger blocks UPDATE and DELETE)."""

    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "occurred_at": self.occurred_at,
            "actor_user_id": self.actor_user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "branch_id": self.branch_id,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "reason": self.reason,
        }


class Integration(db.Model):
    """One row of the integrations register: what is needed, whether it is configured, whether it is verified."""

    __tablename__ = "integrations"

    integration_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_code: Mapped[str] = mapped_column(String(50), unique=True)
    integration_name: Mapped[str] = mapped_column(String(100))
    requirement: Mapped[str] = mapped_column(Text)
    configuration_status: Mapped[str] = mapped_column(IntegrationConfigurationStatus)
    verification_status: Mapped[str] = mapped_column(IntegrationVerificationStatus)
    owner: Mapped[str] = mapped_column(String(100))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {
            "integration_id": self.integration_id,
            "integration_code": self.integration_code,
            "integration_name": self.integration_name,
            "requirement": self.requirement,
            "configuration_status": self.configuration_status,
            "verification_status": self.verification_status,
            "owner": self.owner,
            "last_checked_at": self.last_checked_at,
            "notes": self.notes,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "evidence": self.evidence,
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    category: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    event_key: Mapped[str] = mapped_column(String(200))
    delivery_status: Mapped[str] = mapped_column(NotificationDeliveryStatus, default="Delivered")
    action_status: Mapped[str] = mapped_column(NotificationActionStatus, default="None")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "category": self.category,
            "title": self.title,
            "body": self.body,
            "link": self.link,
            "delivery_status": self.delivery_status,
            "action_status": self.action_status,
            "read_at": self.read_at,
            "acknowledged_at": self.acknowledged_at,
            "created_at": self.created_at,
        }


class ActivityEvent(db.Model):
    """One learning activity (login, resource view, ...). Feeds engagement and the CRM's last-activity value."""

    __tablename__ = "activity_events"

    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    enrolment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    kind: Mapped[str] = mapped_column(String(50))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

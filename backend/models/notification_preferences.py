"""Notification preferences: one row per user, preference group and channel."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db

PREFERENCE_GROUPS = ("Service", "Learning reminders", "Placement", "Promotions & alumni")
CHANNELS = ("In-app", "WhatsApp", "Email")


class NotificationPreference(db.Model):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), primary_key=True)
    preference_group: Mapped[str] = mapped_column(String(30), primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

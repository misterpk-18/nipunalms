"""The WhatsApp outbox (db/107): messages the LMS hands to the CRM to send on the one company number."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db
from models.enums import _pg_enum

WHATSAPP_STATUSES = ("Queued", "Sent", "Failed", "Skipped")
WhatsappStatus = _pg_enum("whatsapp_status", WHATSAPP_STATUSES)


class WhatsappMessage(db.Model):
    __tablename__ = "whatsapp_outbox"

    outbox_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template_name: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(10), default="en")
    recipient_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    lms_user_id: Mapped[str | None] = mapped_column(String(100))
    to_number: Mapped[str | None] = mapped_column(String(20))
    params: Mapped[list] = mapped_column(JSONB, default=list)
    button_params: Mapped[list] = mapped_column(JSONB, default=list)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(WhatsappStatus, default="Queued")
    status_note: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crm_outbox_id: Mapped[int | None] = mapped_column(Integer)
    delivery_status: Mapped[str | None] = mapped_column(String(20))
    delivery_version: Mapped[int] = mapped_column(Integer, default=0)
    delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"outbox_id": self.outbox_id, "template_name": self.template_name, "recipient_user_id": self.recipient_user_id,
                "dedupe_key": self.dedupe_key, "status": self.status, "status_note": self.status_note, "attempts": self.attempts, "delivery_status": self.delivery_status,
                "occurred_at": self.occurred_at, "sent_at": self.sent_at, "created_at": self.created_at}

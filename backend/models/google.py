"""Google Workspace integration (db 123): per-branch settings and the retry queue every Google call goes through."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db
from models.enums import EmailStatus, GoogleJobState


class BranchGoogleConfig(db.Model):
    """Where a branch's Google things live. An empty mailbox falls back to `branches.mailbox`."""

    __tablename__ = "branch_google_config"

    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"), primary_key=True)
    calendar_mailbox: Mapped[str | None] = mapped_column(String(255))
    drive_root_folder_id: Mapped[str | None] = mapped_column(String(200))
    gmail_sender: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"branch_id": self.branch_id, "calendar_mailbox": self.calendar_mailbox,
                "drive_root_folder_id": self.drive_root_folder_id, "gmail_sender": self.gmail_sender}


class GoogleJob(db.Model):
    """One Google call waiting to be made (or made). At most one open job per (kind, entity)."""

    __tablename__ = "google_jobs"

    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(GoogleJobState, default="Queued")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"job_id": self.job_id, "kind": self.kind, "entity_type": self.entity_type, "entity_id": self.entity_id,
                "state": self.state, "attempts": self.attempts, "next_attempt_at": self.next_attempt_at,
                "finished_at": self.finished_at, "last_error": self.last_error, "created_at": self.created_at}


class EmailOutbox(db.Model):
    """One email waiting to be sent through Gmail, or why it was not (db 124). Same idea as the WhatsApp outbox."""

    __tablename__ = "email_outbox"

    outbox_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template: Mapped[str] = mapped_column(String(60))
    recipient_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    to_email: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    has_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(EmailStatus, default="Queued")
    status_note: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"outbox_id": self.outbox_id, "template": self.template, "recipient_user_id": self.recipient_user_id,
                "dedupe_key": self.dedupe_key, "status": self.status, "status_note": self.status_note, "attempts": self.attempts,
                "occurred_at": self.occurred_at, "sent_at": self.sent_at, "created_at": self.created_at}


class GoogleDriveItem(db.Model):
    """A Drive folder the LMS made: one per branch, per course at a branch and per batch (db 125)."""

    __tablename__ = "google_drive_items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(10))
    entity_id: Mapped[int] = mapped_column(Integer)
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    parent_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("google_drive_items.item_id"))
    folder_id: Mapped[str] = mapped_column(String(200))
    folder_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())


class GoogleDriveGrant(db.Model):
    """One person's share of a folder. `revoked_at` set means it has been removed."""

    __tablename__ = "google_drive_grants"

    grant_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("google_drive_items.item_id"))
    grantee_email: Mapped[str] = mapped_column(String(255))
    grantee_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    role: Mapped[str] = mapped_column(String(10))
    permission_id: Mapped[str] = mapped_column(String(200))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Ask Nipuna: every question and answer, with tokens, cited sources and feedback."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User


# An answer that says it has nothing to go on: the screen then offers to hand the question to a person
UNANSWERED_MARKERS = ("data unavailable / not verified", "i can't see an active enrolment", "i have no curriculum topics")


class AiQuery(db.Model):
    __tablename__ = "ai_queries"

    ai_query_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    student_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("students.student_id"))
    audience: Mapped[str] = mapped_column(String(10))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    action: Mapped[str | None] = mapped_column(String(60))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="Answered")
    refusal_reason: Mapped[str | None] = mapped_column(Text)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    scope_note: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    feedback: Mapped[str | None] = mapped_column(String(20))
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "ai_query_id": self.ai_query_id,
            "audience": self.audience,
            "action": self.action,
            "question": self.question,
            "answer": self.answer,
            "answered": self.status == "Answered" and not any(marker in self.answer.lower() for marker in UNANSWERED_MARKERS),
            "status": self.status,
            "refusal_reason": self.refusal_reason,
            "is_fallback": self.is_fallback,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "sources": self.sources,
            "scope_note": self.scope_note,
            "warnings": self.warnings,
            "feedback": self.feedback,
            "feedback_comment": self.feedback_comment,
            "created_at": self.created_at,
        }


class AiFeatureControl(db.Model):
    """An assistant switched off (Module 24 §11): by audience, company-wide or for one branch, until restored after checks."""

    __tablename__ = "ai_feature_controls"

    control_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audience: Mapped[str] = mapped_column(String(10))  # All / Student / Staff
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    reason: Mapped[str] = mapped_column(Text)
    remediation: Mapped[str | None] = mapped_column(Text)
    disabled_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    disabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    restored_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restoration_note: Mapped[str | None] = mapped_column(Text)

    disabler: Mapped[User] = relationship(foreign_keys=[disabled_by], lazy="joined")
    restorer: Mapped[User | None] = relationship(foreign_keys=[restored_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "audience": self.audience,
            "branch_id": self.branch_id,
            "reason": self.reason,
            "remediation": self.remediation,
            "disabled_by": self.disabled_by,
            "disabled_by_name": self.disabler.full_name,
            "disabled_at": self.disabled_at,
            "restored_by": self.restored_by,
            "restored_by_name": self.restorer.full_name if self.restorer else None,
            "restored_at": self.restored_at,
            "restoration_note": self.restoration_note,
            "active": self.restored_at is None,
        }


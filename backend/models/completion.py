"""Completion reviews: the evidence-based decision that an enrolment is complete."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.attendance import student_summary
from models.attendance_enums import CompletionDecision, CompletionReviewStatus
from models.students import Enrolment


class CompletionReview(db.Model):
    __tablename__ = "completion_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    status: Mapped[str] = mapped_column(CompletionReviewStatus, default="Open")
    opened_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    trainer_recommendation: Mapped[str | None] = mapped_column(CompletionDecision)
    trainer_comment: Mapped[str | None] = mapped_column(Text)
    recommended_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    recommended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(CompletionDecision)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    recommender: Mapped[User | None] = relationship(foreign_keys=[recommended_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "enrolment": self.enrolment.to_summary(),
            "student": student_summary(self.enrolment),
            "status": self.status,
            "trainer_recommendation": self.trainer_recommendation,
            "trainer_comment": self.trainer_comment,
            "recommended_by": {"user_id": self.recommended_by, "full_name": self.recommender.full_name} if self.recommender else None,
            "recommended_at": self.recommended_at,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "decided_by": {"user_id": self.decided_by, "full_name": self.decider.full_name} if self.decider else None,
            "decided_at": self.decided_at,
            "evidence": self.evidence,
            "created_at": self.created_at,
        }

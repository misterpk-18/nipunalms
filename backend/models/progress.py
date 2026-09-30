"""The four progress measures per enrolment, read from the `enrolment_progress` SQL view (never written)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import db


def _number(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


class EnrolmentProgress(db.Model):
    """One row per enrolment: Delivery, Attendance, Required learning and Engagement, each with its own basis.

    The measures are deliberately separate; there is no combined score (Module 21). A percentage is None when its
    denominator is empty ("Not Yet Calculable"), never 0.
    """

    __tablename__ = "enrolment_progress"

    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer)
    course_id: Mapped[int] = mapped_column(Integer)
    service_branch_id: Mapped[int] = mapped_column(Integer)
    delivered_sessions: Mapped[int] = mapped_column(Integer)
    planned_sessions: Mapped[int] = mapped_column(Integer)
    delivery_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    delivered_since_joining: Mapped[int] = mapped_column(Integer)
    marked_sessions: Mapped[int] = mapped_column(Integer)
    unmarked_sessions: Mapped[int] = mapped_column(Integer)
    present_count: Mapped[int] = mapped_column(Integer)
    late_count: Mapped[int] = mapped_column(Integer)
    absent_count: Mapped[int] = mapped_column(Integer)
    excused_count: Mapped[int] = mapped_column(Integer)
    recovered_count: Mapped[int] = mapped_column(Integer)
    attendance_state: Mapped[str] = mapped_column(String(20))
    attendance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    attendance_alert: Mapped[bool] = mapped_column(Boolean)
    required_topics: Mapped[int] = mapped_column(Integer)
    covered_topics: Mapped[int] = mapped_column(Integer)
    required_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    events_recent: Mapped[int] = mapped_column(Integer)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engagement_level: Mapped[str] = mapped_column(String(20))

    def to_measures(self, *, threshold: int, window_days: int) -> dict:
        """The four measures with the counts each is based on."""
        return {
            "delivery": {
                "delivered_sessions": self.delivered_sessions,
                "planned_sessions": self.planned_sessions,
                "percent": _number(self.delivery_pct),
            },
            "attendance": {
                "state": self.attendance_state,
                "percent": _number(self.attendance_pct),
                "provisional": self.attendance_state == "Partial Data",
                "delivered_since_joining": self.delivered_since_joining,
                "marked": self.marked_sessions,
                "unmarked": self.unmarked_sessions,
                "present": self.present_count,
                "late": self.late_count,
                "absent": self.absent_count,
                "excused": self.excused_count,
                "recovered": self.recovered_count,
                "alert_threshold": threshold,
                "alert": self.attendance_alert,
            },
            "required_learning": {
                "required_topics": self.required_topics,
                "covered_topics": self.covered_topics,
                "percent": _number(self.required_pct),
            },
            "engagement": {
                "level": self.engagement_level,
                "events_in_window": self.events_recent,
                "window_days": window_days,
                "last_activity_at": self.last_activity_at,
            },
        }


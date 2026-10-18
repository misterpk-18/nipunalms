"""Courses, combo components and the course outline (modules, topics). There are no curriculum versions (db/121)."""
from datetime import datetime

from decimal import Decimal

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.enums import ComponentRole, CourseStatus


class Course(db.Model):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    is_combo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(CourseStatus, default="Active")
    source_version: Mapped[int] = mapped_column(Integer, default=1)
    # LMS-owned (the CRM never sets them): verified standard hours and the completion rules, edited with the outline (db/121)
    hours_verified_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    hours_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_profile: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    components: Mapped[list["CourseComponent"]] = relationship(
        back_populates="parent", foreign_keys="CourseComponent.parent_course_id",
        order_by="CourseComponent.sort_order", cascade="all, delete-orphan",
    )

    def to_summary(self) -> dict:
        return {"course_id": self.course_id, "course_code": self.course_code, "title": self.title}

    def to_dict(self, include_components: bool = False) -> dict:
        data = {
            **self.to_summary(),
            "category": self.category,
            "is_combo": self.is_combo,
            "status": self.status,
        }
        if include_components:
            data["components"] = [c.to_dict() for c in self.components]
        return data


class CourseComponent(db.Model):
    """A track of a combo course; an included booster is also a course of its own."""

    __tablename__ = "course_components"

    component_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    component_course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.course_id"))
    track_code: Mapped[str] = mapped_column(String(50), unique=True)
    track_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(ComponentRole, default="Main track")
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Reusing a standalone course's curriculum for this component needs a recorded equivalence review (Module 14 §3)
    equivalence_note: Mapped[str | None] = mapped_column(Text)
    equivalence_reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    equivalence_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Combo track pin: the track follows this standalone course's outline instead of its own (needs the review above)
    pinned_course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.course_id"))

    parent: Mapped[Course] = relationship(back_populates="components", foreign_keys=[parent_course_id])
    component_course: Mapped[Course | None] = relationship(foreign_keys=[component_course_id], lazy="joined")
    pinned_course: Mapped[Course | None] = relationship(foreign_keys=[pinned_course_id], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "track_code": self.track_code,
            "track_name": self.track_name,
            "role": self.role,
            "sort_order": self.sort_order,
            "component_course": self.component_course.to_summary() if self.component_course else None,
            "equivalence_note": self.equivalence_note,
            "equivalence_reviewed_at": self.equivalence_reviewed_at,
            "pinned_course": self.pinned_course.to_summary() if self.pinned_course else None,
        }


class CourseModule(db.Model):
    """A module of a course's outline (`component_id` set: of one combo track's outline)."""

    __tablename__ = "course_modules"

    module_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    component_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_components.component_id"))  # set = a combo track's outline
    title: Mapped[str] = mapped_column(String(200))
    title_te: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    library_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("library_module_versions.library_version_id"))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)  # kept for the data that refers to it, hidden from the outline

    course: Mapped[Course] = relationship(foreign_keys=[course_id])
    component: Mapped[CourseComponent | None] = relationship(foreign_keys=[component_id])
    topics: Mapped[list["CourseTopic"]] = relationship(
        back_populates="module", order_by="CourseTopic.sort_order", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "component_id": self.component_id,
            "title": self.title,
            "title_te": self.title_te,
            "sort_order": self.sort_order,
            "library_version_id": self.library_version_id,
            "topics": [t.to_dict() for t in self.topics],
        }


topic_dependencies = Table(
    "course_topic_dependencies", db.metadata,
    Column("topic_id", Integer, ForeignKey("course_topics.topic_id"), primary_key=True),
    Column("depends_on_topic_id", Integer, ForeignKey("course_topics.topic_id"), primary_key=True),
)


class CourseTopic(db.Model):
    __tablename__ = "course_topics"

    topic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_modules.module_id"))
    title: Mapped[str] = mapped_column(String(200))
    title_te: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)  # kept in step with topic_class by a trigger
    topic_class: Mapped[str | None] = mapped_column(String(12))        # Required / Recommended / Optional
    outcome: Mapped[str | None] = mapped_column(Text)
    instructional_minutes: Mapped[int | None] = mapped_column(Integer)
    independent_minutes: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    evidence: Mapped[str | None] = mapped_column(Text)
    activities: Mapped[str | None] = mapped_column(Text)

    module: Mapped[CourseModule] = relationship(back_populates="topics")
    depends_on: Mapped[list["CourseTopic"]] = relationship(
        secondary="course_topic_dependencies", primaryjoin="CourseTopic.topic_id == course_topic_dependencies.c.topic_id",
        secondaryjoin="CourseTopic.topic_id == course_topic_dependencies.c.depends_on_topic_id", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "title_te": self.title_te,
            "sort_order": self.sort_order,
            "is_required": self.is_required,
            "topic_class": self.topic_class,
            "outcome": self.outcome,
            "instructional_minutes": self.instructional_minutes,
            "independent_minutes": self.independent_minutes,
            "weight": None if self.weight is None else f"{self.weight:.2f}",
            "evidence": self.evidence,
            "activities": self.activities,
            "depends_on": [t.topic_id for t in self.depends_on],
        }

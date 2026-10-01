"""Courses, combo components and curriculum (versions, modules, topics)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.enums import ComponentRole, CourseStatus, CurriculumStatus


class Course(db.Model):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    is_combo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(CourseStatus, default="Active")
    source_version: Mapped[int] = mapped_column(Integer, default=1)
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

    parent: Mapped[Course] = relationship(back_populates="components", foreign_keys=[parent_course_id])
    component_course: Mapped[Course | None] = relationship(foreign_keys=[component_course_id], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "track_code": self.track_code,
            "track_name": self.track_name,
            "role": self.role,
            "sort_order": self.sort_order,
            "component_course": self.component_course.to_summary() if self.component_course else None,
        }


class CurriculumVersion(db.Model):
    __tablename__ = "curriculum_versions"

    curriculum_version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    component_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_components.component_id"))
    version_label: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(CurriculumStatus, default="Draft")
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    modules: Mapped[list["CurriculumModule"]] = relationship(
        back_populates="version", order_by="CurriculumModule.sort_order", cascade="all, delete-orphan"
    )

    def to_summary(self) -> dict:
        return {
            "curriculum_version_id": self.curriculum_version_id,
            "version_label": self.version_label,
            "status": self.status,
        }

    def to_dict(self) -> dict:
        return {
            **self.to_summary(),
            "course_id": self.course_id,
            "component_id": self.component_id,
            "approved_at": self.approved_at,
        }


class CurriculumModule(db.Model):
    __tablename__ = "curriculum_modules"

    module_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    title: Mapped[str] = mapped_column(String(200))
    title_te: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(SmallInteger)

    version: Mapped[CurriculumVersion] = relationship(back_populates="modules")
    topics: Mapped[list["CurriculumTopic"]] = relationship(
        back_populates="module", order_by="CurriculumTopic.sort_order", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "title": self.title,
            "title_te": self.title_te,
            "sort_order": self.sort_order,
            "topics": [t.to_dict() for t in self.topics],
        }


class CurriculumTopic(db.Model):
    __tablename__ = "curriculum_topics"

    topic_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_modules.module_id"))
    title: Mapped[str] = mapped_column(String(200))
    title_te: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)

    module: Mapped[CurriculumModule] = relationship(back_populates="topics")

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "title_te": self.title_te,
            "sort_order": self.sort_order,
            "is_required": self.is_required,
        }

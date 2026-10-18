"""Course extras (db 102, moved onto the course in db/121): required assessments and the reusable module library."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.certificates import ApprovalStatus


class AssessmentRequirement(db.Model):
    __tablename__ = "course_assessment_requirements"

    requirement_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    module_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_modules.module_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("course_topics.topic_id"))
    kind: Mapped[str] = mapped_column(String(10))  # Assignment / Test
    title: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(Text)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    pass_rule: Mapped[str] = mapped_column(Text)
    counts_for_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"requirement_id": self.requirement_id, "course_id": self.course_id, "module_id": self.module_id,
                "topic_id": self.topic_id, "kind": self.kind, "title": self.title, "outcome": self.outcome,
                "weight": f"{self.weight:.2f}", "pass_rule": self.pass_rule, "counts_for_completion": self.counts_for_completion}


class LibraryModule(db.Model):
    __tablename__ = "library_modules"

    library_module_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    versions: Mapped[list["LibraryModuleVersion"]] = relationship(back_populates="module", order_by="LibraryModuleVersion.version_no",
                                                                  lazy="selectin")

    def to_dict(self) -> dict:
        approved = [v for v in self.versions if v.status == "Approved"]
        return {"library_module_id": self.library_module_id, "module_code": self.module_code, "title": self.title,
                "current_version": approved[-1].to_dict() if approved else None,
                "versions": [v.to_dict() for v in self.versions]}


class LibraryModuleVersion(db.Model):
    __tablename__ = "library_module_versions"

    library_version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_module_id: Mapped[int] = mapped_column(Integer, ForeignKey("library_modules.library_module_id"))
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSONB)
    change_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    proposed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    module: Mapped[LibraryModule] = relationship(back_populates="versions")

    def to_dict(self) -> dict:
        return {"library_version_id": self.library_version_id, "version_no": self.version_no, "content": self.content,
                "change_note": self.change_note, "status": self.status, "proposed_by": self.proposed_by,
                "proposed_at": self.proposed_at, "decided_by": self.decided_by, "decided_at": self.decided_at}

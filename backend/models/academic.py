"""Module 14 academic records (db 102): required assessments, combo pins, equivalence rules, individual academic mappings and
credits, branch variations, and the reusable module library."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.catalog import CurriculumVersion
from models.certificates import ApprovalStatus


def _user(user: User | None) -> dict | None:
    return None if user is None else {"user_id": user.user_id, "full_name": user.full_name}


class _Decision:
    """Columns shared by records an approver decides."""

    def decision_dict(self) -> dict:
        return {"status": self.status, "requested_by": _user(self.requester), "requested_at": self.requested_at,
                "decided_by": _user(self.decider), "decided_at": self.decided_at, "decision_note": self.decision_note}


class AssessmentRequirement(db.Model):
    __tablename__ = "curriculum_assessment_requirements"

    requirement_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    module_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_modules.module_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    kind: Mapped[str] = mapped_column(String(10))  # Assignment / Test
    title: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(Text)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    pass_rule: Mapped[str] = mapped_column(Text)
    counts_for_completion: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {"requirement_id": self.requirement_id, "curriculum_version_id": self.curriculum_version_id, "module_id": self.module_id,
                "topic_id": self.topic_id, "kind": self.kind, "title": self.title, "outcome": self.outcome,
                "weight": f"{self.weight:.2f}", "pass_rule": self.pass_rule, "counts_for_completion": self.counts_for_completion}


class VersionComponent(db.Model):
    """A combo parent version's pinned track or booster version (Module 14 §2)."""

    __tablename__ = "curriculum_version_components"

    curriculum_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"), primary_key=True)
    component_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_components.component_id"), primary_key=True)
    component_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))

    component_version: Mapped[CurriculumVersion] = relationship(foreign_keys=[component_version_id], lazy="joined")


class EquivalenceRule(_Decision, db.Model):
    __tablename__ = "equivalence_rules"

    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    to_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {"rule_id": self.rule_id, "from_version_id": self.from_version_id, "to_version_id": self.to_version_id,
                "description": self.description, **self.decision_dict()}


class AcademicMapping(_Decision, db.Model):
    __tablename__ = "academic_mappings"

    mapping_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    enrolment_track_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("enrolment_tracks.enrolment_track_id"))
    from_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    to_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    rule_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equivalence_rules.rule_id"))
    comparison: Mapped[str] = mapped_column(Text)
    migration_plan: Mapped[str] = mapped_column(Text)
    trainer_evidence: Mapped[str | None] = mapped_column(Text)
    student_acceptance: Mapped[str | None] = mapped_column(Text)
    proposed_credits: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    from_version: Mapped[CurriculumVersion | None] = relationship(foreign_keys=[from_version_id], lazy="joined")
    to_version: Mapped[CurriculumVersion] = relationship(foreign_keys=[to_version_id], lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")
    credits: Mapped[list["LearningCredit"]] = relationship(back_populates="mapping", lazy="selectin")

    def to_dict(self) -> dict:
        return {"mapping_id": self.mapping_id, "enrolment_id": self.enrolment_id, "enrolment_track_id": self.enrolment_track_id,
                "from_version": self.from_version.to_summary() if self.from_version else None, "to_version": self.to_version.to_summary(),
                "rule_id": self.rule_id, "comparison": self.comparison, "migration_plan": self.migration_plan,
                "trainer_evidence": self.trainer_evidence, "student_acceptance": self.student_acceptance,
                "proposed_credits": self.proposed_credits, "credits": [c.to_dict() for c in self.credits], **self.decision_dict()}


class LearningCredit(db.Model):
    __tablename__ = "learning_credits"

    credit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    mapping_id: Mapped[int] = mapped_column(Integer, ForeignKey("academic_mappings.mapping_id"))
    original_evidence: Mapped[str] = mapped_column(Text)
    rule_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equivalence_rules.rule_id"))
    reviewed_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    mapping: Mapped[AcademicMapping] = relationship(back_populates="credits")

    def to_dict(self) -> dict:
        return {"credit_id": self.credit_id, "topic_id": self.topic_id, "original_evidence": self.original_evidence,
                "rule_id": self.rule_id, "reviewed_by": self.reviewed_by, "created_at": self.created_at}


class CurriculumVariation(_Decision, db.Model):
    __tablename__ = "curriculum_variations"

    variation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    kind: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    remedial_plan: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ApprovalStatus, default="Pending")
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {"variation_id": self.variation_id, "curriculum_version_id": self.curriculum_version_id, "branch_id": self.branch_id,
                "batch_id": self.batch_id, "topic_id": self.topic_id, "kind": self.kind, "description": self.description,
                "remedial_plan": self.remedial_plan, **self.decision_dict()}


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

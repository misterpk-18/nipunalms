"""Content library (items, versions, review history), recordings, recording exceptions and access extension requests."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.access import User
from models.batches import Batch, ClassSession
from models.catalog import Course, CurriculumModule, CurriculumTopic, CurriculumVersion
from models.enums import _pg_enum
from models.masters import Branch
from models.students import Enrolment, Student

CONTENT_TYPES = ("PDF", "Notes", "Dataset", "Code", "Lab", "Practice material", "Link", "Video link")
LINK_CONTENT_TYPES = ("Link", "Video link")
CONTENT_STATUSES = ("Draft", "Submitted", "Under Review", "Approved", "Released", "Changes Requested", "Rejected", "Retired")
CONTENT_STORAGE_KINDS = ("File", "Link")
CONTENT_REVIEW_ACTIONS = ("Submitted", "Review Started", "Approved", "Changes Requested", "Rejected", "Released", "Retired")
RECORDING_STATUSES = ("Processing", "Released", "Partial", "Held", "Unavailable", "Expired")
RECORDING_SOURCES = ("Google Drive", "Manual upload")
RECORDING_ISSUE_TYPES = ("Partial", "Held", "Unavailable", "Integration Unavailable")
RECORDING_EXCEPTION_STATUSES = ("Open", "In Progress", "Resolved")
EXTENSION_SCOPES = ("Recording", "Material", "Both")
EXTENSION_STATUSES = ("Pending", "Approved", "Rejected")

ContentType = _pg_enum("content_type", CONTENT_TYPES)
ContentStatus = _pg_enum("content_status", CONTENT_STATUSES)
ContentStorageKind = _pg_enum("content_storage_kind", CONTENT_STORAGE_KINDS)
ContentReviewAction = _pg_enum("content_review_action", CONTENT_REVIEW_ACTIONS)
RecordingStatus = _pg_enum("recording_status", RECORDING_STATUSES)
RecordingIssueType = _pg_enum("recording_issue_type", RECORDING_ISSUE_TYPES)
RecordingExceptionStatus = _pg_enum("recording_exception_status", RECORDING_EXCEPTION_STATUSES)
ExtensionScope = _pg_enum("extension_scope", EXTENSION_SCOPES)
ExtensionStatus = _pg_enum("extension_status", EXTENSION_STATUSES)


def _user_ref(user: User | None) -> dict | None:
    return {"user_id": user.user_id, "full_name": user.full_name} if user else None


class ContentItem(db.Model):
    __tablename__ = "content_items"

    content_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(ContentType)
    language: Mapped[str] = mapped_column(String(2), default="en")
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id"))
    curriculum_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_versions.curriculum_version_id"))
    module_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_modules.module_id"))
    topic_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("curriculum_topics.topic_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.batch_id"))
    download_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(ContentStatus, default="Draft")
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    retire_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    course: Mapped[Course] = relationship(lazy="joined")
    curriculum_version: Mapped[CurriculumVersion | None] = relationship(lazy="joined")
    module: Mapped[CurriculumModule | None] = relationship(lazy="joined")
    topic: Mapped[CurriculumTopic | None] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    batch: Mapped[Batch | None] = relationship(lazy="joined")
    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id], lazy="joined")
    versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="item", order_by="ContentVersion.version_no", cascade="all, delete-orphan"
    )

    @property
    def latest_version(self) -> "ContentVersion":
        return self.versions[-1]

    @property
    def released_version(self) -> "ContentVersion | None":
        """The version students open: the newest Released one (none once the item is retired)."""
        if self.retired_at is not None:
            return None
        return next((v for v in reversed(self.versions) if v.status == "Released"), None)

    def placement(self) -> dict:
        return {
            "course": self.course.to_summary(),
            "curriculum_version": self.curriculum_version.to_summary() if self.curriculum_version else None,
            "module": {"module_id": self.module.module_id, "title": self.module.title} if self.module else None,
            "topic": {"topic_id": self.topic.topic_id, "title": self.topic.title} if self.topic else None,
            "branch": self.branch.to_summary(),
            "batch": self.batch.to_summary() if self.batch else None,
        }

    def to_summary(self) -> dict:
        return {"content_item_id": self.content_item_id, "item_code": self.item_code, "title": self.title,
                "content_type": self.content_type}

    def to_dict(self, detail: bool = False) -> dict:
        latest = self.latest_version
        released = self.released_version
        data = {
            **self.to_summary(),
            "description": self.description,
            "language": self.language,
            **self.placement(),
            "download_allowed": self.download_allowed,
            "status": self.status,
            "owner": _user_ref(self.owner),
            "version_no": latest.version_no,
            "released_version_no": released.version_no if released else None,
            "storage_kind": latest.storage_kind,
            "original_filename": latest.original_filename,
            "file_size_bytes": latest.file_size_bytes,
            "url": latest.url,
            "submitted_at": latest.submitted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retired_at": self.retired_at,
            "retire_reason": self.retire_reason,
        }
        if detail:
            data["versions"] = [v.to_dict() for v in self.versions]
        return data


class ContentVersion(db.Model):
    __tablename__ = "content_versions"

    content_version_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("content_items.content_item_id"))
    version_no: Mapped[int] = mapped_column(SmallInteger)
    storage_kind: Mapped[str] = mapped_column(ContentStorageKind)
    file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    url: Mapped[str | None] = mapped_column(String(1000))
    change_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ContentStatus, default="Draft")
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))

    item: Mapped[ContentItem] = relationship(back_populates="versions")
    uploader: Mapped[User] = relationship(foreign_keys=[uploaded_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "content_version_id": self.content_version_id,
            "version_no": self.version_no,
            "storage_kind": self.storage_kind,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "file_size_bytes": self.file_size_bytes,
            "url": self.url,
            "change_summary": self.change_summary,
            "status": self.status,
            "uploaded_by": _user_ref(self.uploader),
            "uploaded_at": self.uploaded_at,
            "submitted_at": self.submitted_at,
            "released_at": self.released_at,
        }


class ContentReview(db.Model):
    __tablename__ = "content_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("content_items.content_item_id"))
    content_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("content_versions.content_version_id"))
    action: Mapped[str] = mapped_column(ContentReviewAction)
    actor_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    comment: Mapped[str | None] = mapped_column(Text)
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    version: Mapped[ContentVersion] = relationship(lazy="joined")
    actor: Mapped[User] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "version_no": self.version.version_no,
            "action": self.action,
            "actor": _user_ref(self.actor),
            "comment": self.comment,
            "acted_at": self.acted_at,
        }


class Recording(db.Model):
    __tablename__ = "recordings"

    recording_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recording_code: Mapped[str] = mapped_column(String(30), unique=True, server_default=FetchedValue())  # trigger
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    part_no: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(RecordingStatus, default="Processing")
    source: Mapped[str] = mapped_column(String(50), default="Google Drive")
    media_ref: Mapped[str | None] = mapped_column(String(500))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    download_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    hold_reason: Mapped[str | None] = mapped_column(Text)
    partial_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    session: Mapped[ClassSession] = relationship(lazy="joined")

    def session_summary(self) -> dict:
        s = self.session
        return {
            "session_id": s.session_id, "session_code": s.session_code, "title": s.title, "starts_at": s.starts_at,
            "ends_at": s.ends_at, "mode": s.mode, "state": s.state, "batch": s.batch.to_summary(),
            "branch": s.batch.branch.to_summary(), "trainer": _user_ref(s.trainer),
            "topic": {"topic_id": s.topic.topic_id, "title": s.topic.title} if s.topic else None,
        }

    def to_dict(self) -> dict:
        return {
            "recording_id": self.recording_id,
            "recording_code": self.recording_code,
            "session": self.session_summary(),
            "part_no": self.part_no,
            "status": self.status,
            "source": self.source,
            "media_ref": self.media_ref,
            "duration_minutes": self.duration_minutes,
            "download_allowed": self.download_allowed,
            "released_at": self.released_at,
            "hold_reason": self.hold_reason,
            "partial_note": self.partial_note,
            "created_at": self.created_at,
        }


class RecordingException(db.Model):
    __tablename__ = "recording_exceptions"

    exception_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exception_code: Mapped[str] = mapped_column(String(20), unique=True, server_default=FetchedValue())  # trigger
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("class_sessions.session_id"))
    recording_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("recordings.recording_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    issue_type: Mapped[str] = mapped_column(RecordingIssueType)
    issue: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(RecordingExceptionStatus, default="Open")
    owner_role: Mapped[str] = mapped_column(String(50))
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    auto_raised: Mapped[bool] = mapped_column(Boolean, default=False)
    raised_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    session: Mapped[ClassSession] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    owner_user: Mapped[User | None] = relationship(foreign_keys=[owner_user_id], lazy="joined")

    def to_dict(self, owner_label: str, age_hours: int, escalation: str | None) -> dict:
        """owner_label ("Academic Coordinator GNT") and the age / escalation step are worked out by the service."""
        s = self.session
        return {
            "exception_id": self.exception_id,
            "exception_code": self.exception_code,
            "session": {"session_id": s.session_id, "session_code": s.session_code, "title": s.title,
                        "starts_at": s.starts_at, "ends_at": s.ends_at, "mode": s.mode, "state": s.state},
            "batch": s.batch.to_summary(),
            "branch": self.branch.to_summary(),
            "recording_id": self.recording_id,
            "issue_type": self.issue_type,
            "issue": self.issue,
            "status": self.status,
            "owner": owner_label,
            "owner_role": self.owner_role,
            "owner_user": _user_ref(self.owner_user),
            "auto_raised": self.auto_raised,
            "opened_at": self.opened_at,
            "age_hours": age_hours,
            "escalation": escalation,
            "resolved_at": self.resolved_at,
            "resolution_note": self.resolution_note,
        }


class AccessExtensionRequest(db.Model):
    __tablename__ = "access_extension_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_code: Mapped[str] = mapped_column(String(20), unique=True, server_default=FetchedValue())  # trigger
    enrolment_id: Mapped[int] = mapped_column(Integer, ForeignKey("enrolments.enrolment_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id"))
    branch_id: Mapped[int] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    scope: Mapped[str] = mapped_column(ExtensionScope)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ExtensionStatus, default="Pending")
    needs_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    original_expiry: Mapped[date] = mapped_column(Date)
    approved_expiry: Mapped[date | None] = mapped_column(Date)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    enrolment: Mapped[Enrolment] = relationship(lazy="joined")
    student: Mapped[Student] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")
    decider: Mapped[User | None] = relationship(foreign_keys=[decided_by], lazy="joined")

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "request_code": self.request_code,
            "enrolment": self.enrolment.to_summary(),
            "student": self.student.to_summary(),
            "branch": self.branch.to_summary(),
            "scope": self.scope,
            "reason": self.reason,
            "status": self.status,
            "needs_exception": self.needs_exception,
            "original_expiry": self.original_expiry,
            "approved_expiry": self.approved_expiry,
            "requested_at": self.requested_at,
            "decided_by": _user_ref(self.decider),
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
        }

"""Import every model here so relationships between modules resolve.

Models map existing tables (schema lives in db/*.sql); they never create tables.
"""
from models.access import ActiveSession, Role, User, UserRoleScope, UserSession
from models.admin import SecurityControl
from models.batches import Batch, BatchAllocation, BatchCrmState, BatchTrainer, ClassSession
from models.catalog import Course, CourseComponent, CurriculumModule, CurriculumTopic, CurriculumVersion
from models.masters import Branch
from models.students import (
    Admission, AdmissionLmsState, CrmEvent, CrmOutbox, Enrolment, EnrolmentTrack, FinanceSummary, Student,
    StudentActivation,
)
from models.system import ActivityEvent, AppSetting, AuditLog, Integration, Notification

__all__ = [
    "ActiveSession", "ActivityEvent", "Admission", "AdmissionLmsState", "AppSetting", "AuditLog", "Batch",
    "BatchAllocation", "BatchCrmState", "BatchTrainer", "Branch", "ClassSession", "Course", "CourseComponent", "CrmEvent", "CrmOutbox",
    "CurriculumModule", "CurriculumTopic", "CurriculumVersion", "Enrolment", "EnrolmentTrack", "FinanceSummary",
    "Integration", "Notification", "Role", "SecurityControl", "Student", "StudentActivation", "User", "UserRoleScope", "UserSession",
]

# Slice S4: attendance, progress, completion review, certificates
from models.attendance import AttendanceCorrection, AttendanceRecord, AttendanceRecovery  # noqa: E402
from models.certificates import Certificate  # noqa: E402
from models.completion import CompletionReview  # noqa: E402
from models.progress import EnrolmentProgress  # noqa: E402

__all__ += ["AttendanceCorrection", "AttendanceRecord", "AttendanceRecovery", "Certificate", "CompletionReview", "EnrolmentProgress"]

# Phase 2 / S2 content & recordings
from models.content import (  # noqa: E402
    AccessExtensionRequest, ContentItem, ContentReview, ContentVersion, Recording, RecordingException,
)

__all__ += [
    "AccessExtensionRequest", "ContentItem", "ContentReview", "ContentVersion", "Recording", "RecordingException",
]

"""Import every model here so relationships between modules resolve.

Models map existing tables (schema lives in db/*.sql); they never create tables.
"""
from models.access import ActiveSession, EmailChangeCode, PasswordResetCode, Role, SplitAccountHandout, StaffInvite, User, UserRoleScope, UserSession
from models.admin import SecurityControl
from models.batches import Batch, BatchAllocation, BatchCrmState, BatchTrainer, ClassSession
from models.assessments import (
    Assignment, AssignmentSubmission, AttemptAnswer, InterviewSlot, Question, Result, SubmissionReview, Test, TestAttempt,
    TestQuestion,
)
from models.catalog import Course, CourseComponent, CourseModule, CourseTopic
from models.masters import Branch, BranchFinanceSnapshot
from models.students import (
    Admission, AdmissionLmsState, CrmEvent, CrmOutbox, Enrolment, EnrolmentTrack, FinanceSummary, Student,
    StudentActivation,
)
from models.system import ActivityEvent, AppSetting, AuditLog, Integration, Notification
from models.delivery import BatchEvent, ClassFlowProgress, ClassSessionTopic, MeetEvent, SessionChange, SessionChangeRequest

__all__ = [
    "Assignment", "AssignmentSubmission", "AttemptAnswer", "InterviewSlot", "Question", "Result", "SubmissionReview", "Test",
    "TestAttempt", "TestQuestion",
    "ActiveSession", "EmailChangeCode", "PasswordResetCode", "StaffInvite", "SplitAccountHandout", "ActivityEvent", "Admission", "AdmissionLmsState", "AppSetting", "AuditLog", "Batch",
    "BatchAllocation", "BatchCrmState", "BatchTrainer", "Branch", "BranchFinanceSnapshot", "ClassSession", "Course", "CourseComponent", "CrmEvent", "CrmOutbox",
    "CourseModule", "CourseTopic", "Enrolment", "EnrolmentTrack", "FinanceSummary",
    "Integration", "Notification", "Role", "SecurityControl", "Student", "StudentActivation", "User", "UserRoleScope", "UserSession",
    "BatchEvent", "ClassFlowProgress", "ClassSessionTopic", "MeetEvent", "SessionChange", "SessionChangeRequest",
]

# Slice S4: attendance, progress, completion review, certificates
from models.attendance import AttendanceCorrection, AttendanceRecord, AttendanceRecovery  # noqa: E402
from models.certificates import (  # noqa: E402
    Certificate, CertificateChangeRequest, CertificateFinancialException, CertificateStatusHistory,
)
from models.completion import CompletionReview  # noqa: E402
from models.progress import EnrolmentProgress, TopicProgress  # noqa: E402

__all__ += ["AttendanceCorrection", "AttendanceRecord", "AttendanceRecovery", "Certificate", "CertificateChangeRequest",
            "CertificateFinancialException", "CertificateStatusHistory", "CompletionReview", "EnrolmentProgress", "TopicProgress"]

# Phase 2 / S2 content & recordings
from models.content import (  # noqa: E402
    AccessExtensionRequest, ContentItem, ContentReview, ContentVersion, Recording, RecordingException,
)

__all__ += [
    "AccessExtensionRequest", "ContentItem", "ContentReview", "ContentVersion", "Recording", "RecordingException",
]

# Phase 3: exception queue (080)
from models.exceptions import ExceptionItem, ExceptionRecoveryStep  # noqa: E402

__all__ += ["ExceptionItem", "ExceptionRecoveryStep"]

# Student services slice (050)
from models.ask_nipuna import AiFeatureControl, AiQuery  # noqa: E402
from models.career import Application, ApplicationEvent, CareerProfile, CvDocument, Opportunity, PlacementOutcome  # noqa: E402
from models.notification_preferences import NotificationPreference  # noqa: E402
from models.support import SupportAttachment, SupportMessage, SupportRequest  # noqa: E402

__all__ += [
    "AiFeatureControl", "AiQuery", "Application", "ApplicationEvent", "CareerProfile", "CvDocument", "NotificationPreference", "Opportunity",
    "PlacementOutcome", "SupportAttachment", "SupportMessage", "SupportRequest",
]

# Gap fix plan phase 4: the Academic Calendar (101)
from models.calendar import CalendarClosure  # noqa: E402

__all__ += ["CalendarClosure"]

# Course extras: required assessments and the reusable module library (102, moved onto the course in 121)
from models.academic import AssessmentRequirement, LibraryModule, LibraryModuleVersion  # noqa: E402

__all__ += ["AssessmentRequirement", "LibraryModule", "LibraryModuleVersion"]

# Gap fix plan phase 6: batches and delivery operations, Modules 15 and 16 (103)
from models.delivery_ops import (  # noqa: E402
    BatchCapacityRequest, BatchHandover, BatchSuccession, BatchTransferRequest, JobRun, MaterialChange, MaterialChangeResponse,
    MeetIncident, MeetParticipation, SessionCoverRequest, SessionDisruption, SessionPerson, SessionRoster, SlotPreference,
)

__all__ += ["BatchCapacityRequest", "BatchHandover", "BatchSuccession", "BatchTransferRequest", "JobRun", "MaterialChange",
            "MaterialChangeResponse", "MeetIncident", "MeetParticipation", "SessionCoverRequest", "SessionDisruption", "SessionPerson",
            "SessionRoster", "SlotPreference"]
from models.whatsapp import WhatsappMessage  # noqa: E402

# Google Workspace integration (db 123)
from models.google import BranchGoogleConfig, EmailOutbox, GoogleDriveGrant, GoogleDriveItem, GoogleJob  # noqa: E402

__all__ += ["BranchGoogleConfig", "EmailOutbox", "GoogleDriveGrant", "GoogleDriveItem", "GoogleJob"]

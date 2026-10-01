"""Import every model here so relationships between modules resolve.

Models map existing tables (schema lives in db/*.sql); they never create tables.
"""
from models.access import ActiveSession, Role, User, UserRoleScope, UserSession
from models.admin import SecurityControl
from models.batches import Batch, BatchAllocation, BatchCrmState, BatchTrainer, ClassSession
from models.assessments import (
    Assignment, AssignmentSubmission, AttemptAnswer, InterviewSlot, Question, Result, SubmissionReview, Test, TestAttempt,
    TestQuestion,
)
from models.catalog import Course, CourseComponent, CurriculumModule, CurriculumTopic, CurriculumVersion
from models.masters import Branch, BranchFinanceSnapshot
from models.students import (
    Admission, AdmissionLmsState, CrmEvent, CrmOutbox, Enrolment, EnrolmentTrack, FinanceSummary, Student,
    StudentActivation,
)
from models.system import ActivityEvent, AppSetting, AuditLog, Integration, Notification
from models.delivery import BatchEvent, CurriculumEvent, MeetEvent, SessionChange, SessionChangeRequest

__all__ = [
    "Assignment", "AssignmentSubmission", "AttemptAnswer", "InterviewSlot", "Question", "Result", "SubmissionReview", "Test",
    "TestAttempt", "TestQuestion",
    "ActiveSession", "ActivityEvent", "Admission", "AdmissionLmsState", "AppSetting", "AuditLog", "Batch",
    "BatchAllocation", "BatchCrmState", "BatchTrainer", "Branch", "BranchFinanceSnapshot", "ClassSession", "Course", "CourseComponent", "CrmEvent", "CrmOutbox",
    "CurriculumModule", "CurriculumTopic", "CurriculumVersion", "Enrolment", "EnrolmentTrack", "FinanceSummary",
    "Integration", "Notification", "Role", "SecurityControl", "Student", "StudentActivation", "User", "UserRoleScope", "UserSession",
    "BatchEvent", "CurriculumEvent", "MeetEvent", "SessionChange", "SessionChangeRequest",
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

# Phase 3: exception queue (080)
from models.exceptions import ExceptionItem, ExceptionRecoveryStep  # noqa: E402

__all__ += ["ExceptionItem", "ExceptionRecoveryStep"]

# Student services slice (050)
from models.ask_nipuna import AiQuery  # noqa: E402
from models.career import Application, ApplicationEvent, CareerProfile, CvDocument, Opportunity, PlacementOutcome  # noqa: E402
from models.notification_preferences import NotificationPreference  # noqa: E402
from models.support import SupportMessage, SupportRequest  # noqa: E402

__all__ += [
    "AiQuery", "Application", "ApplicationEvent", "CareerProfile", "CvDocument", "NotificationPreference", "Opportunity",
    "PlacementOutcome", "SupportMessage", "SupportRequest",
]

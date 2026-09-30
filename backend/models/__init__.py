"""Import every model here so relationships between modules resolve.

Models map existing tables (schema lives in db/*.sql); they never create tables.
"""
from models.access import ActiveSession, Role, User, UserRoleScope, UserSession
from models.batches import Batch, BatchAllocation, BatchTrainer, ClassSession
from models.catalog import Course, CourseComponent, CurriculumModule, CurriculumTopic, CurriculumVersion
from models.masters import Branch
from models.students import (
    Admission, AdmissionLmsState, CrmEvent, CrmOutbox, Enrolment, EnrolmentTrack, FinanceSummary, Student,
    StudentActivation,
)
from models.system import ActivityEvent, AppSetting, AuditLog, Integration, Notification

__all__ = [
    "ActiveSession", "ActivityEvent", "Admission", "AdmissionLmsState", "AppSetting", "AuditLog", "Batch",
    "BatchAllocation", "BatchTrainer", "Branch", "ClassSession", "Course", "CourseComponent", "CrmEvent", "CrmOutbox",
    "CurriculumModule", "CurriculumTopic", "CurriculumVersion", "Enrolment", "EnrolmentTrack", "FinanceSummary",
    "Integration", "Notification", "Role", "Student", "StudentActivation", "User", "UserRoleScope", "UserSession",
]

# Student services slice (050)
from models.ask_nipuna import AiQuery  # noqa: E402
from models.career import Application, ApplicationEvent, CareerProfile, CvDocument, Opportunity, PlacementOutcome  # noqa: E402
from models.notification_preferences import NotificationPreference  # noqa: E402
from models.support import SupportMessage, SupportRequest  # noqa: E402

__all__ += [
    "AiQuery", "Application", "ApplicationEvent", "CareerProfile", "CvDocument", "NotificationPreference", "Opportunity",
    "PlacementOutcome", "SupportMessage", "SupportRequest",
]

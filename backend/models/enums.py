"""Postgres enum types (created by db/*.sql) and their allowed values, used for validation."""
from sqlalchemy.dialects.postgresql import ENUM


def _pg_enum(name: str, values: tuple[str, ...]) -> ENUM:
    return ENUM(*values, name=name, create_type=False)


DELIVERY_MODES = ("Classroom", "Live Online", "Hybrid")
INTEGRATION_CONFIGURATION_STATUSES = ("Not Configured", "Configuration Pending", "Configured", "Misconfigured")
INTEGRATION_VERIFICATION_STATUSES = ("Not Verified", "Pending Verification", "Verified", "Failed")
NOTIFICATION_DELIVERY_STATUSES = ("Delivered", "Failed")
NOTIFICATION_ACTION_STATUSES = ("None", "Open", "Completed")
COURSE_STATUSES = ("Active", "Inactive", "Archived")
COMPONENT_ROLES = ("Main track", "Included booster")
CURRICULUM_STATUSES = ("Draft", "Under Review", "Approved", "Active", "Retired")
ACTIVATION_STATUSES = ("Account Created", "Activation Pending", "Activated", "Suspended")
ACTIVATION_CHANNELS = ("CRM provisioning", "Staff issued")  # student_activations.channel
ADMISSION_STATUSES = ("Active", "Paused", "Cancelled")
ENROLMENT_KINDS = ("Combo", "Standalone", "Separately purchased", "Complimentary")
ENROLMENT_STATUSES = (
    "Provisioning Pending", "Curriculum Mapping Pending", "Allocation Pending",
    "Allocated — awaiting first regular class", "Active", "Paused", "Completed", "Withdrawn",
)
CRM_EVENT_STATUSES = ("Received", "Applied", "Ignored — stale", "Failed")
OUTBOX_STATUSES = ("Pending", "Delivered", "Failed")
LMS_STATUSES = ("Not Created", "Invited", "Active", "Inactive", "Completed")
SEAT_TYPES = ("Confirmed Seat", "Future Plan")
PAYMENT_COMPLETIONS = ("Unpaid", "Part Paid", "Paid")
BATCH_STATES = ("Forming", "Starting", "Running", "Full", "Completed", "Cancelled")
BATCH_READINESS = ("Ready", "Blocked", "Pending Verification")
BATCH_TRAINER_ROLES = ("Lead", "Co-trainer")
ALLOCATION_STATUSES = ("Active", "Ended", "Transferred")
SESSION_STATES = ("Scheduled", "Live", "Delivered", "Cancelled", "Rescheduled")
MEET_STATUSES = ("Not Required", "Pending Verification", "Linked", "Unavailable")

DeliveryMode = _pg_enum("delivery_mode", DELIVERY_MODES)
IntegrationConfigurationStatus = _pg_enum("integration_configuration_status", INTEGRATION_CONFIGURATION_STATUSES)
IntegrationVerificationStatus = _pg_enum("integration_verification_status", INTEGRATION_VERIFICATION_STATUSES)
NotificationDeliveryStatus = _pg_enum("notification_delivery_status", NOTIFICATION_DELIVERY_STATUSES)
NotificationActionStatus = _pg_enum("notification_action_status", NOTIFICATION_ACTION_STATUSES)
CourseStatus = _pg_enum("course_status", COURSE_STATUSES)
ComponentRole = _pg_enum("component_role", COMPONENT_ROLES)
CurriculumStatus = _pg_enum("curriculum_status", CURRICULUM_STATUSES)
ActivationStatus = _pg_enum("student_activation_status", ACTIVATION_STATUSES)
AdmissionStatus = _pg_enum("crm_admission_status", ADMISSION_STATUSES)
EnrolmentKind = _pg_enum("enrolment_kind", ENROLMENT_KINDS)
EnrolmentStatus = _pg_enum("enrolment_status", ENROLMENT_STATUSES)
CrmEventStatus = _pg_enum("crm_event_status", CRM_EVENT_STATUSES)
OutboxStatus = _pg_enum("outbox_status", OUTBOX_STATUSES)
LmsStatus = _pg_enum("lms_status", LMS_STATUSES)
BatchState = _pg_enum("batch_state", BATCH_STATES)
BatchReadiness = _pg_enum("batch_readiness", BATCH_READINESS)
BatchTrainerRole = _pg_enum("batch_trainer_role", BATCH_TRAINER_ROLES)
AllocationStatus = _pg_enum("allocation_status", ALLOCATION_STATUSES)
SessionState = _pg_enum("session_state", SESSION_STATES)
MeetStatus = _pg_enum("meet_status", MEET_STATUSES)

RESCHEDULE_REQUEST_STATUSES = ("Open", "Approved", "Rejected")
RescheduleRequestStatus = _pg_enum("reschedule_request_status", RESCHEDULE_REQUEST_STATUSES)

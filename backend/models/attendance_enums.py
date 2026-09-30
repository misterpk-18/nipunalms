"""Postgres enum types of the attendance / completion / certificate slice (db/040) and their allowed values."""
from models.enums import _pg_enum

ATTENDANCE_STATUSES = ("Present", "Absent", "Late", "Excused")
RECOVERY_METHODS = ("Recording watched", "Extra session", "Assignment")
RECOVERY_STATUSES = ("Requested", "Approved", "Rejected", "Completed")
CORRECTION_STATUSES = ("Pending", "Approved", "Rejected")
COMPLETION_DECISIONS = ("Complete", "Not Yet", "Needs Recovery")
COMPLETION_REVIEW_STATUSES = ("Open", "Decided")
CERTIFICATE_TYPES = ("Course Completion Certificate", "Internship Certificate")
CERTIFICATE_STATUSES = (
    "Not Yet Eligible", "Eligibility Review", "Awaiting Approval", "Approved for Issue", "Issued", "Superseded", "Revoked",
)

AttendanceStatus = _pg_enum("attendance_status", ATTENDANCE_STATUSES)
RecoveryMethod = _pg_enum("recovery_method", RECOVERY_METHODS)
RecoveryStatus = _pg_enum("recovery_status", RECOVERY_STATUSES)
CorrectionStatus = _pg_enum("correction_status", CORRECTION_STATUSES)
CompletionDecision = _pg_enum("completion_decision", COMPLETION_DECISIONS)
CompletionReviewStatus = _pg_enum("completion_review_status", COMPLETION_REVIEW_STATUSES)
CertificateType = _pg_enum("certificate_type", CERTIFICATE_TYPES)
CertificateStatus = _pg_enum("certificate_status", CERTIFICATE_STATUSES)

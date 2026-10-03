"""Background jobs run by `flask --app app jobs run [NAME ...]` (schedule with cron). Each returns a short result for the log.

Later slices register their own jobs by adding to JOBS.
"""
from typing import Callable

from services import attempts as attempts_service
from services import attendance as attendance_service
from services import batch_allocations as batch_allocations_service
from services import recordings as recordings_service
from services import session_ops
from services import support as support_service


def recording_check() -> dict:
    """Raise recording exceptions for delivered classes without a recording, and escalate old ones (4 / 24 / 48 h)."""
    return recordings_service.check_missing_recordings()


def support_escalate_overdue() -> dict:
    """Escalate open support requests past their SLA (app_settings.support_sla_hours) to the Branch Manager."""
    return {"escalated": support_service.escalate_overdue()}


def allocation_escalation() -> dict:
    """Raise enrolments still without a batch 24 hours before their planned start to the Branch Manager."""
    return {"escalated": batch_allocations_service.escalate_unallocated()}


def attempts_expire() -> dict:
    """Submit test attempts still open past their deadline, with the deadline as the submission time (Module 20 §6)."""
    return {"submitted": attempts_service.expire_overdue()}


def attendance_unconfirmed() -> dict:
    """Alert the Academic Coordinator on the next working day about delivered classes with attendance not yet confirmed."""
    return {"alerted": attendance_service.alert_unconfirmed()}


def session_delay_check() -> dict:
    """Tell students when a class is 5 minutes late; record a disruption and alert the coordinator and Branch Manager at 15
    (Module 16 §7). Run every few minutes."""
    return session_ops.check_delays()


def class_log_check() -> dict:
    """Raise a coordinator review task for classes still without a delivery log after their working day (Module 15 §15)."""
    return session_ops.check_class_logs()


JOBS: dict[str, Callable[[], object]] = {
    "allocation-escalation": allocation_escalation,
    "attempts-expire": attempts_expire,
    "attendance-unconfirmed": attendance_unconfirmed,
    "class-log-check": class_log_check,
    "recording-check": recording_check,
    "session-delay-check": session_delay_check,
    "support-escalate-overdue": support_escalate_overdue,
}

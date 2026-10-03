"""Background jobs run by `flask --app app jobs run [NAME ...]` (schedule with cron). Each returns a short result for the log.

Later slices register their own jobs by adding to JOBS.
"""
from typing import Callable

from services import attempts as attempts_service
from services import attendance as attendance_service
from services import batch_allocations as batch_allocations_service
from services import recordings as recordings_service
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


JOBS: dict[str, Callable[[], object]] = {
    "allocation-escalation": allocation_escalation,
    "attempts-expire": attempts_expire,
    "attendance-unconfirmed": attendance_unconfirmed,
    "recording-check": recording_check,
    "support-escalate-overdue": support_escalate_overdue,
}

"""Background jobs run by `flask --app app jobs run [NAME ...]` (schedule with cron). Each returns a short result for the log.

Later slices register their own jobs by adding to JOBS.
"""
from typing import Callable

from services import recordings as recordings_service
from services import support as support_service


def recording_check() -> dict:
    """Raise recording exceptions for delivered classes without a recording, and escalate old ones (4 / 24 / 48 h)."""
    return recordings_service.check_missing_recordings()


def support_escalate_overdue() -> dict:
    """Escalate open support requests past their SLA (app_settings.support_sla_hours) to the Branch Manager."""
    return {"escalated": support_service.escalate_overdue()}


JOBS: dict[str, Callable[[], object]] = {
    "recording-check": recording_check,
    "support-escalate-overdue": support_escalate_overdue,
}

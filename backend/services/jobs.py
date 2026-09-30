"""Background jobs run by `flask --app app jobs run [NAME ...]` (schedule with cron). Each returns a short result for the log.

Later slices register their own jobs by adding to JOBS.
"""
from typing import Callable

from services import recordings as recordings_service


def recording_check() -> dict:
    """Raise recording exceptions for delivered classes without a recording, and escalate old ones (4 / 24 / 48 h)."""
    return recordings_service.check_missing_recordings()


JOBS: dict[str, Callable[[], object]] = {
    "recording-check": recording_check,
}

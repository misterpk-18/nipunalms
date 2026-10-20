"""The `google-sync` job: makes the Google calls that requests queued in `google_jobs`, and retries the ones that fail.

A job is claimed (marked Running) and committed before the first HTTP call, so no database transaction is held open while
Google answers. A timeout, 429 or 5xx is retried after 5 min, 15 min, 1 h, 6 h, 24 h; anything else (a refused delegation, a bad
request) fails at once. After the last retry the job is Dead and the owning feature shows its failure (a Branch Manager task for
a class's Meet link); a Super Admin can requeue a dead job.
"""
import logging
from datetime import datetime, timedelta, timezone

from config.database import db
from models import GoogleJob
from repositories import google as google_repo
from services.google import class_events
from services.google.client import GoogleError

logger = logging.getLogger(__name__)

BACKOFF = (timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1), timedelta(hours=6), timedelta(hours=24))
MAX_ATTEMPTS = len(BACKOFF) + 1
BATCH_SIZE = 50

HANDLERS = {class_events.KIND_UPSERT: class_events.handle_upsert, class_events.KIND_CANCEL: class_events.handle_cancel}
ON_DEAD = {class_events.KIND_UPSERT: class_events.on_dead, class_events.KIND_CANCEL: class_events.on_dead}
ENABLED = {class_events.KIND_UPSERT: class_events.is_enabled, class_events.KIND_CANCEL: class_events.is_enabled}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_due(limit: int = BATCH_SIZE) -> dict:
    """Make the Google calls that are due. Jobs of a switched-off integration are left waiting, not failed."""
    kinds = tuple(kind for kind, enabled in ENABLED.items() if enabled())
    if not kinds:
        return {"skipped": "Google is not configured or its integration is not verified"}
    jobs = google_repo.claim_due(_now(), limit, kinds)
    db.session.commit()
    result = {"done": 0, "retry": 0, "dead": 0}
    for job_id in [job.job_id for job in jobs]:
        result[_run_one(job_id)] += 1
    return result


def _run_one(job_id: int) -> str:
    job = db.session.get(GoogleJob, job_id)
    try:
        note = HANDLERS[job.kind](job.entity_id)
    except GoogleError as exc:
        error, retryable = str(exc), exc.retryable
    except Exception as exc:  # a bug in the handler: undo its half-done work, keep the job's own record
        logger.exception("google job %s failed", job_id)
        db.session.rollback()
        job = db.session.get(GoogleJob, job_id)
        error, retryable = f"Unexpected error: {exc}", True
    else:
        job.state, job.finished_at, job.last_error = "Succeeded", _now(), None
        job.payload = {**(job.payload or {}), "result": note}
        db.session.commit()
        return "done"

    job.attempts += 1
    job.last_error = error[:2000]
    if not retryable or job.attempts >= MAX_ATTEMPTS:
        job.state, job.finished_at = "Dead", _now()
        ON_DEAD[job.kind](job.kind, job.entity_id, error)
        outcome = "dead"
    else:
        job.state, job.next_attempt_at = "Failed", _now() + BACKOFF[job.attempts - 1]
        outcome = "retry"
    db.session.commit()
    return outcome


def retry_dead(job_id: int) -> GoogleJob | None:
    """Put a dead job back in the queue with its attempts cleared (Super Admin)."""
    job = google_repo.get_job(job_id)
    if job is None or job.state != "Dead":
        return None
    job.state, job.attempts, job.next_attempt_at, job.finished_at = "Queued", 0, _now(), None
    db.session.flush()
    return job

"""What the Super Admin and Founder see of the Google Workspace integration (docs/GOOGLE_WORKSPACE.md §7): which features are on, the
queue of Google calls and emails with what went wrong, a retry for a stuck call, and each branch's Google settings."""
import re

from sqlalchemy import select

from config.database import db
from models import Batch, Branch, BranchGoogleConfig, ClassSession, EmailOutbox, GoogleJob
from repositories import email as email_repo
from repositories import google as google_repo
from services import audit, integrations
from services.context import actor_id
from services.errors import BusinessRule, NotFound, ValidationError
from services.google import client, jobs

PROBLEM_STATES = ("Failed", "Dead")
JOB_LABELS = {"CALENDAR_UPSERT": "Calendar event and Meet link", "CALENDAR_CANCEL": "Remove Calendar event", "DRIVE_SYNC": "Drive folder and sharing"}
FEATURES = (("GOOGLE_MEET", "Calendar events and Meet links"), ("GOOGLE_DRIVE", "Drive folders and sharing"), ("EMAIL", "Email through Gmail"))
EMAIL_STATES = ("Queued", "Sent", "Failed", "Skipped")
_FOLDER_ID = re.compile(r"[A-Za-z0-9_-]{10,200}")


def overview() -> dict:
    """The switches, the number of calls and emails in each state, and the ones that need a person to look."""
    configured = client.is_configured()
    features = []
    for code, name in FEATURES:
        status = integrations.integration_status(code)
        features.append({"integration_code": code, "feature": name, "state": status.state, "live": configured and status.is_verified})
    counts = dict(db.session.execute(select(GoogleJob.state, db.func.count()).group_by(GoogleJob.state)).all())
    return {"configured": configured, "features": features, "jobs": counts, "emails": email_repo.counts(),
            "problems": [job_row(j) for j in google_repo.list_jobs(PROBLEM_STATES, 20)]}


def _target(job) -> str:
    if job.entity_type == "class_session":
        session = db.session.get(ClassSession, job.entity_id)
        return f"{session.session_code} · {session.title}" if session else f"Class {job.entity_id} (removed)"
    if job.entity_type == "batch":
        batch = db.session.get(Batch, job.entity_id)
        return f"Batch {batch.batch_code}" if batch else f"Batch {job.entity_id} (removed)"
    return f"{job.entity_type} {job.entity_id}"


def job_row(job) -> dict:
    return {**job.to_dict(), "what": JOB_LABELS.get(job.kind, job.kind), "target": _target(job)}


def list_jobs(state: str | None, limit: int) -> list[dict]:
    return [job_row(j) for j in google_repo.list_jobs((state,) if state else None, limit)]


def retry_job(job_id: int) -> dict:
    """Make a Failed call due now, or put a Dead one back in the queue with its tries cleared."""
    job = google_repo.get_job(job_id)
    if job is None:
        raise NotFound("Job not found")
    if job.state == "Dead":
        jobs.retry_dead(job_id)
    elif job.state == "Failed":
        job.next_attempt_at = db.func.now()
    else:
        raise BusinessRule(f"A {job.state.lower()} job cannot be retried")
    db.session.flush()
    audit.record("GOOGLE_JOB_RETRIED", "google_job", job_id, new={"kind": job.kind, "entity_id": job.entity_id})
    db.session.refresh(job)
    return job_row(job)


def list_emails(status: str | None, limit: int) -> list[dict]:
    query = select(EmailOutbox).order_by(EmailOutbox.outbox_id.desc()).limit(limit)
    if status:
        query = query.where(EmailOutbox.status == status)
    return [{**m.to_dict(), "to_email": m.to_email, "subject": m.subject or None} for m in db.session.execute(query).scalars()]


# ---------------------------------------------------------------- per-branch settings

def _branch_row(branch: Branch, config: BranchGoogleConfig | None) -> dict:
    return {"branch_id": branch.branch_id, "branch_name": branch.branch_name, "branch_mailbox": branch.mailbox,
            "calendar_mailbox": config.calendar_mailbox if config else None, "gmail_sender": config.gmail_sender if config else None,
            "drive_root_folder_id": config.drive_root_folder_id if config else None,
            "effective_calendar_mailbox": (config.calendar_mailbox if config and config.calendar_mailbox else branch.mailbox),
            "effective_gmail_sender": google_repo.gmail_sender(branch.branch_id)}


def branch_configs() -> list[dict]:
    branches = db.session.execute(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.branch_name)).scalars().all()
    return [_branch_row(b, google_repo.branch_config(b.branch_id)) for b in branches]


def update_branch_config(branch_id: int, changes: dict) -> dict:
    """Set a branch's calendar mailbox, email sender or Drive folder. An empty value goes back to the branch mailbox. The Drive
    folder cannot move once the LMS has made folders under the current one: they would be left behind."""
    branch = db.session.get(Branch, branch_id)
    if branch is None:
        raise NotFound("Branch not found")
    config = google_repo.branch_config(branch_id)
    old = _branch_row(branch, config)
    if "drive_root_folder_id" in changes and changes["drive_root_folder_id"]:
        if not _FOLDER_ID.fullmatch(changes["drive_root_folder_id"]):
            raise ValidationError("Invalid Drive folder", {"drive_root_folder_id": ["Paste the folder's id (the last part of its Drive link)"]})
    if "drive_root_folder_id" in changes and changes["drive_root_folder_id"] != old["drive_root_folder_id"]:
        if google_repo.drive_item("branch", branch_id, branch_id) is not None:
            raise BusinessRule("The LMS has already made folders under this branch's Drive folder; they would be left behind")
    if config is None:
        config = BranchGoogleConfig(branch_id=branch_id)
        db.session.add(config)
    for field in ("calendar_mailbox", "gmail_sender", "drive_root_folder_id"):
        if field in changes:
            setattr(config, field, changes[field] or None)
    config.updated_by = actor_id()
    db.session.flush()
    new = _branch_row(branch, config)
    audit.record("BRANCH_GOOGLE_CONFIG_CHANGED", "branch", branch.branch_code, old=old, new=new, branch_id=branch_id)
    return new

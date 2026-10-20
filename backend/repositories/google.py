"""Reads and writes of the Google job queue and the per-branch Google settings."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from config.database import db
from models import Branch, BranchGoogleConfig, GoogleJob

OPEN_STATES = ("Queued", "Running", "Failed")
RUNNING_LIMIT = timedelta(minutes=15)


def enqueue(kind: str, entity_type: str, entity_id: int, payload: dict | None = None) -> None:
    """Add the job unless one is already open for this (kind, entity); a waiting job is made due again, a running one is left alone."""
    inserted = db.session.execute(
        insert(GoogleJob).values(kind=kind, entity_type=entity_type, entity_id=entity_id, payload=payload or {})
        .on_conflict_do_nothing(index_elements=["kind", "entity_type", "entity_id"], index_where=GoogleJob.state.in_(OPEN_STATES))
        .returning(GoogleJob.job_id)).first()
    if inserted is None:
        db.session.execute(
            GoogleJob.__table__.update().where(GoogleJob.kind == kind, GoogleJob.entity_type == entity_type,
                                               GoogleJob.entity_id == entity_id, GoogleJob.state.in_(("Queued", "Failed")))
            .values(next_attempt_at=db.func.now()))


def claim_due(now: datetime, limit: int, kinds: tuple[str, ...]) -> list[GoogleJob]:
    """Mark up to `limit` due jobs of these kinds Running and return them. A job left Running for too long (a crashed run) is taken again."""
    jobs = db.session.execute(
        select(GoogleJob).where(GoogleJob.kind.in_(kinds)).where(
            ((GoogleJob.state.in_(("Queued", "Failed"))) & (GoogleJob.next_attempt_at <= now))
            | ((GoogleJob.state == "Running") & (GoogleJob.started_at <= now - RUNNING_LIMIT)))
        .order_by(GoogleJob.next_attempt_at, GoogleJob.job_id).limit(limit).with_for_update(skip_locked=True)).scalars().all()
    for job in jobs:
        job.state, job.started_at = "Running", now
    db.session.flush()
    return list(jobs)


def list_jobs(states: tuple[str, ...] | None = None, limit: int = 100) -> list[GoogleJob]:
    query = select(GoogleJob).order_by(GoogleJob.updated_at.desc(), GoogleJob.job_id.desc()).limit(limit)
    if states:
        query = query.where(GoogleJob.state.in_(states))
    return list(db.session.execute(query).scalars())


def get_job(job_id: int) -> GoogleJob | None:
    return db.session.get(GoogleJob, job_id)


def branch_config(branch_id: int) -> BranchGoogleConfig | None:
    return db.session.get(BranchGoogleConfig, branch_id)


def branch_mailbox(branch_id: int) -> str | None:
    """Whose calendar holds a branch's class events: the branch's own setting, else the branch mailbox."""
    config = branch_config(branch_id)
    if config is not None and config.calendar_mailbox:
        return config.calendar_mailbox
    branch = db.session.get(Branch, branch_id)
    return branch.mailbox if branch is not None else None


def gmail_sender(branch_id: int | None) -> str | None:
    """Who a branch's email comes from: the branch's own setting, else the branch mailbox."""
    if branch_id is None:
        return None
    config = branch_config(branch_id)
    if config is not None and config.gmail_sender:
        return config.gmail_sender
    branch = db.session.get(Branch, branch_id)
    return branch.mailbox if branch is not None else None

"""The exception queue: every open exception the slices already store, in one place, with a log of recovery steps.

The `exception_queue` view (db/080) unions the slices' own records, so an exception leaves the queue when its slice
resolves it; nothing is copied or closed here. A recovery step is a written, audited note of what is being done; the
person who logs one becomes the named owner of an item that had none.

Who: an Academic Coordinator logs steps and sees the exceptions of their branch; a Branch Manager reads their branch;
the Super Admin sees and logs across all branches, including company-wide items (CRM sync, integrations); the
Founder / CEO reads everything. An item outside the user's scope is a 404.
"""
from datetime import datetime, timezone

from config.database import db
from models import ExceptionItem, ExceptionRecoveryStep
from models.exceptions import EXCEPTION_SOURCES
from repositories import exceptions as exceptions_repo
from repositories.common import paginate
from services import audit, scope
from services.context import current_user
from services.errors import Forbidden, NotFound

STEP_ROLES = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_exceptions(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    rows, meta = paginate(exceptions_repo.list_stmt(filters, scope.visible_branch_ids()), page, per_page)
    now = _now()
    return [row.to_dict(now) for row in rows], meta


def counts(branch_ids: set[int] | None) -> dict:
    """Open exceptions at the branches, for the dashboards."""
    return exceptions_repo.counts(branch_ids)


def _visible_item(source: str, source_id: int) -> ExceptionItem:
    item = exceptions_repo.get_item(source, source_id) if source in EXCEPTION_SOURCES else None
    branch_ids = scope.visible_branch_ids()
    if item is None or (branch_ids is not None and item.branch_id not in branch_ids):
        raise NotFound("Exception not found")
    return item


def _can_log(item: ExceptionItem) -> bool:
    user = current_user()
    if user.has_role("SUPER_ADMIN"):
        return True
    return item.branch_id is not None and user.has_role("ACADEMIC_COORDINATOR", branch_id=item.branch_id)


def list_steps(source: str, source_id: int) -> list[ExceptionRecoveryStep]:
    item = _visible_item(source, source_id)
    return exceptions_repo.steps_of(item.source, item.source_id)


def log_step(source: str, source_id: int, reason: str) -> tuple[ExceptionRecoveryStep, dict]:
    """Record a recovery step (audited). Returns the step and the exception as it now reads."""
    item = _visible_item(source, source_id)
    if not _can_log(item):
        raise Forbidden("Only the Academic Coordinator of this branch or a Super Admin logs recovery steps")
    user = current_user()
    step = exceptions_repo.add_step(item.source, item.source_id, item.branch_id, reason, user.user_id)
    audit.record("EXCEPTION_STEP_LOGGED", "exception", f"{item.source}:{item.source_id}",
                 old={"state": item.state, "owner_user_id": item.owner_user_id},
                 new={"reference": item.reference, "title": item.title, "step_id": step.step_id},
                 reason=reason, branch_id=item.branch_id)
    # The view is derived: read the row again so state, owner and step count reflect the new step
    db.session.expire(item)
    return step, exceptions_repo.get_item(item.source, item.source_id).to_dict(_now())

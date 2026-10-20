"""The exception queue: every open exception the slices already store, in one place, with a log of recovery steps.

The `exception_queue` view (db/080) unions the slices' own records, so an exception leaves the queue when its slice
resolves it; nothing is copied or closed here. A recovery step is a written, audited note of what is being done; the
person who logs one becomes the named owner of an item that had none.

Who: a Branch Manager logs steps and sees the exceptions of their branch; the Super Admin sees and logs across all
branches, including company-wide items (CRM sync, integrations); the Founder / CEO reads everything. An item outside the
user's scope is a 404.
"""
from datetime import datetime, timezone

from config.database import db
from models import ExceptionItem, ExceptionRecoveryStep
from models.exceptions import EXCEPTION_SOURCES
from repositories import exceptions as exceptions_repo
from repositories.common import paginate
from services import audit, scope
from services.context import ACADEMIC_ROLES, ADMIN_ROLES, current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError

STEP_ROLES = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


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
    if user.has_role(*ADMIN_ROLES):
        return True
    return item.branch_id is not None and user.has_role(*ACADEMIC_ROLES, branch_id=item.branch_id)


def list_steps(source: str, source_id: int) -> list[ExceptionRecoveryStep]:
    item = _visible_item(source, source_id)
    return exceptions_repo.steps_of(item.source, item.source_id)


def log_step(source: str, source_id: int, reason: str) -> tuple[ExceptionRecoveryStep, dict]:
    """Record a recovery step (audited). Returns the step and the exception as it now reads."""
    item = _visible_item(source, source_id)
    if not _can_log(item):
        raise Forbidden("Only the Branch Manager of this branch or a Super Admin logs recovery steps")
    user = current_user()
    step = exceptions_repo.add_step(item.source, item.source_id, item.branch_id, reason, user.user_id)
    audit.record("EXCEPTION_STEP_LOGGED", "exception", f"{item.source}:{item.source_id}",
                 old={"state": item.state, "owner_user_id": item.owner_user_id},
                 new={"reference": item.reference, "title": item.title, "step_id": step.step_id},
                 reason=reason, branch_id=item.branch_id)
    # The view is derived: read the row again so state, owner and step count reflect the new step
    db.session.expire(item)
    return step, exceptions_repo.get_item(item.source, item.source_id).to_dict(_now())


# Sources whose own record carries an owner (set where the item is handled): an issue step cannot override it
OWN_OWNER_SOURCES = ("SUPPORT", "RECORDING", "DISRUPTION")


def can_assign(source: str, owner_user_id: int | None) -> bool:
    """A Super Admin or the Founder / CEO may assign an issue unless its own screen already names its owner."""
    return current_user().has_role(*ADMIN_ROLES) and (source not in OWN_OWNER_SOURCES or owner_user_id is None)


def assign(source: str, source_id: int, assignee_user_id: int, note: str | None) -> dict:
    """Super Admin: hand an issue to a member of staff (UX phase U17). It is a recovery step that names its new owner, so the
    list, the owner filter and the counts follow; the person is told. Returns the exception as it now reads."""
    from repositories import admin_users as users_repo
    from services.notifications import notify

    user = current_user()
    if not user.has_role(*ADMIN_ROLES):
        raise Forbidden("Only a Super Admin or the Founder / CEO assigns issues")
    item = _visible_item(source, source_id)
    if not can_assign(item.source, item.owner_user_id):
        raise BusinessRule("This issue's owner is set on the screen that handles it (for example Student support); change it there")
    assignee = users_repo.get_staff_user(assignee_user_id)
    if assignee is None or not assignee.is_active:
        raise ValidationError("Invalid request data", {"assignee_user_id": ["Pick an active staff user"]})
    reason = f"Assigned to {assignee.full_name}" + (f": {note}" if note else "")
    step = exceptions_repo.add_step(item.source, item.source_id, item.branch_id, reason, user.user_id, assigned_to=assignee.user_id)
    audit.record("EXCEPTION_ASSIGNED", "exception", f"{item.source}:{item.source_id}",
                 old={"owner_user_id": item.owner_user_id}, new={"reference": item.reference, "title": item.title, "assigned_to": assignee.user_id,
                                                                  "step_id": step.step_id}, reason=note, branch_id=item.branch_id)
    if assignee.user_id != user.user_id:
        assignee_roles = {s.role.role_code for s in assignee.scopes if s.revoked_at is None}
        home = ("/founder/issues" if "FOUNDER_CEO" in assignee_roles else "/admin/issues" if "SUPER_ADMIN" in assignee_roles
                else "/branch/issues")
        notify(category="Issues", title=f"An issue was assigned to you: {item.title}", body=note or item.detail, link=home,
               recipient_user_ids=[assignee.user_id], event_key=f"issue-assigned:{item.source}:{item.source_id}:{step.step_id}", action_required=True)
    db.session.expire(item)
    return exceptions_repo.get_item(item.source, item.source_id).to_dict(_now())

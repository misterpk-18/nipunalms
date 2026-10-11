"""The Issues inbox (UX phase U15): one list of everything that is wrong or stuck, whatever slice it came from.

It reads the `exception_queue` view (so an item leaves the inbox when its own screen resolves it) and adds what a person
needs to act: a plain type, the age, the owner, and a "Go fix it" link to the screen that holds the work. "Add note" is
the existing recovery step (`POST /exceptions/{source}/{id}/steps`).

Role-aware: a Branch Manager sees the issues of their branches; a Super Admin sees every branch and the company-wide
ones (CRM sync, integrations); the Founder / CEO reads everything. The list is paged (page, per_page up to 100) and the
paging total is exact, so no screen is limited to its first page.
"""
from datetime import datetime, timedelta, timezone

from repositories import exceptions as exceptions_repo
from repositories.common import paginate
from services import scope
from services.context import current_user
from services.errors import Forbidden, ValidationError

# plain type key -> (label, the view sources that belong to it)
TYPES = {
    "students": ("Students", ("ALLOCATION", "PROVISIONING", "CURRICULUM_MAPPING")),
    "classes": ("Classes", ("DISRUPTION", "CLASS_LOG", "REPLACEMENT")),
    "recordings": ("Recordings", ("RECORDING",)),
    "support": ("Student support", ("SUPPORT",)),
    "results": ("Marks and results", ("RESULTS",)),
    "access": ("Access extensions", ("ACCESS_EXCEPTION",)),
    "system": ("Sync and setup", ("CRM_EVENT", "INTEGRATION")),
}
SOURCE_TYPE = {source: key for key, (_, sources) in TYPES.items() for source in sources}
SOURCE_LABELS = {
    "ALLOCATION": "Student waiting for a batch", "PROVISIONING": "Account not ready", "CURRICULUM_MAPPING": "Student waiting for a batch",
    "DISRUPTION": "Class disrupted", "CLASS_LOG": "Class log missing", "REPLACEMENT": "Replacement class owed",
    "RECORDING": "Recording problem", "SUPPORT": "Student request", "RESULTS": "Results to publish",
    "ACCESS_EXCEPTION": "Access extension", "CRM_EVENT": "CRM sync failed", "INTEGRATION": "Integration needs attention",
}
AGES = {"today": ("opened_after", timedelta(days=1)), "over_2": ("opened_before", timedelta(days=2)),
        "over_7": ("opened_before", timedelta(days=7)), "over_30": ("opened_before", timedelta(days=30))}


def fix_link(source: str, source_id: int, branch_id: int | None) -> dict:
    """Where the work for this item is done: `{to, search}` for the router."""
    match source:
        case "ALLOCATION" | "CURRICULUM_MAPPING":
            return {"to": "/branch/waiting", "search": {}}
        case "PROVISIONING":
            return {"to": "/admin/students", "search": {}}
        case "RECORDING":
            return {"to": "/branch/recordings", "search": {"exception": source_id}}
        case "SUPPORT":
            return {"to": "/branch/support", "search": {"request": source_id}}
        case "RESULTS":
            return {"to": "/branch/results", "search": {"batch": source_id}}
        case "ACCESS_EXCEPTION":
            return {"to": "/branch/support", "search": {"tab": "extensions", "request": source_id}}
        case "DISRUPTION":
            return {"to": "/branch/class-day", "search": {}}
        case "CLASS_LOG" | "REPLACEMENT":
            return {"to": "/branch/schedule", "search": {"session": source_id}}
        case "CRM_EVENT":
            return {"to": "/admin/crm-sync", "search": {}}
        case "INTEGRATION":
            return {"to": "/admin/integrations", "search": {}}
    return {"to": "/branch", "search": {}}


def _filters(raw: dict) -> dict:
    user = current_user()
    out: dict = {}
    if raw.get("type"):
        if raw["type"] not in TYPES:
            raise ValidationError("Invalid request data", {"type": ["Not an issue type"]})
        out["sources"] = TYPES[raw["type"]][1]
    now = datetime.now(timezone.utc)
    if raw.get("age"):
        if raw["age"] not in AGES:
            raise ValidationError("Invalid request data", {"age": ["Not an age filter"]})
        key, delta = AGES[raw["age"]]
        out[key] = now - delta
    owner = raw.get("owner")
    if owner == "me":
        out["owner_user_id"] = user.user_id
    elif owner == "none":
        out["awaiting_owner"] = True
    elif owner:
        try:
            out["owner_user_id"] = int(owner)
        except ValueError:
            raise ValidationError("Invalid request data", {"owner": ["Use me, none or a person's id"]}) from None
    for key in ("branch_id", "state"):
        if raw.get(key) is not None:
            out[key] = raw[key]
    return out


def list_issues(raw_filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    user = current_user()
    if not user.has_role("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO"):
        raise Forbidden("You don't have access to issues")
    branch_ids = scope.visible_branch_ids()
    filters = _filters(raw_filters)
    rows, meta = paginate(exceptions_repo.list_stmt(filters, branch_ids), page, per_page)
    now = datetime.now(timezone.utc)
    can_note = user.has_role("BRANCH_MANAGER", "SUPER_ADMIN")
    items = []
    for row in rows:
        data = row.to_dict(now)
        items.append({**data, "id": f"{row.source}:{row.source_id}", "type": SOURCE_TYPE.get(row.source, "system"),
                      "type_label": SOURCE_LABELS.get(row.source, row.queue), "go_fix": fix_link(row.source, row.source_id, row.branch_id),
                      "can_note": can_note and (row.branch_id is not None or user.has_role("SUPER_ADMIN"))})
    by_source = exceptions_repo.counts_by_source(filters, branch_ids)
    meta["counts"] = {key: sum(by_source.get(s, 0) for s in sources) for key, (_, sources) in TYPES.items()}
    meta["counts"]["all"] = sum(meta["counts"].values())
    return items, meta

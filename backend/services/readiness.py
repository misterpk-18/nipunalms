"""Readiness records (integrations and security controls): configuration status, operational verification, evidence.

The two registers share one rule set:
  - "Verified" is a claim about operation: it needs a working (Configured) setup and an evidence note, and records
    who verified it and when;
  - moving a Verified record out of Configured drops it back to Not Verified unless the caller says otherwise;
  - any change to the statuses or the evidence counts as a check (last_checked_at).
"""
from datetime import datetime, timezone

from services import audit
from services.context import actor_id
from services.errors import BusinessRule, ValidationError

FIELDS = ("configuration_status", "verification_status", "owner", "evidence", "notes")

# The plain states the Setup & health screen shows (UX phase U17), and the two statuses each one stands for
SETUP_STATES = ("Not set up", "Set up", "Working", "Broken")


def setup_state(configuration_status: str, verification_status: str) -> str:
    """Broken when it is misconfigured or its last check failed; Working when it was seen working; Set up when configured."""
    if configuration_status == "Misconfigured" or verification_status == "Failed":
        return "Broken"
    if verification_status == "Verified":
        return "Working"
    if configuration_status == "Configured":
        return "Set up"
    return "Not set up"


def statuses_for(state: str, record) -> dict:
    """The configuration and verification statuses that a plain state means for this record."""
    if state == "Not set up":
        return {"configuration_status": "Not Configured", "verification_status": "Not Verified"}
    if state == "Set up":
        pending = record.verification_status == "Pending Verification"
        return {"configuration_status": "Configured", "verification_status": "Pending Verification" if pending else "Not Verified"}
    if state == "Working":
        return {"configuration_status": "Configured", "verification_status": "Verified"}
    configured = record.configuration_status in ("Configured", "Misconfigured")
    return {"configuration_status": "Misconfigured" if not configured else record.configuration_status, "verification_status": "Failed"}


def _owner_changes(owner_user_id: int | None) -> dict:
    """`owner_user_id` and the owner's name (the text column) for a staff pick; None clears the pick."""
    from repositories import admin_users as users_repo

    if owner_user_id is None:
        return {"owner_user_id": None, "owner": "Unassigned"}
    user = users_repo.get_staff_user(owner_user_id)
    if user is None or not user.is_active:
        raise ValidationError("Invalid request data", {"owner_user_id": ["Pick an active staff user"]})
    return {"owner_user_id": user.user_id, "owner": user.full_name}


def apply_update(record, changes: dict, *, audit_action: str, entity_type: str, entity_id) -> bool:
    """Apply validated `changes` to an Integration / SecurityControl and audit what changed. Returns whether anything changed."""
    changes = dict(changes)
    state = changes.pop("state", None)
    if state is not None:
        if "configuration_status" in changes or "verification_status" in changes:
            raise ValidationError("Invalid request data", {"state": ["Send either a state or the two statuses, not both"]})
        changes.update(statuses_for(state, record))
    if "owner_user_id" in changes:
        changes.update(_owner_changes(changes["owner_user_id"]))
    configuration = changes.get("configuration_status", record.configuration_status)
    if ("configuration_status" in changes and configuration != "Configured" and "verification_status" not in changes
            and record.verification_status == "Verified"):
        changes["verification_status"] = "Not Verified"

    verification = changes.get("verification_status", record.verification_status)
    if verification == "Verified":
        if configuration != "Configured":
            raise BusinessRule("Only a Configured setup can be marked Verified", {"verification_status": ["Configure it first"]})
        if not (changes.get("evidence", record.evidence) or "").strip():
            raise BusinessRule("Verification needs an evidence note", {"evidence": ["Describe how it was verified"]})

    changed = {field: value for field, value in changes.items() if getattr(record, field) != value}
    if not changed:
        return False

    old = {field: getattr(record, field) for field in changed}
    for field, value in changed.items():
        setattr(record, field, value)

    now = datetime.now(timezone.utc)
    if verification == "Verified" and (record.verified_at is None or {"verification_status", "evidence"} & changed.keys()):
        record.verified_by, record.verified_at = actor_id(), now
    elif verification != "Verified":
        record.verified_by = record.verified_at = None
    if {"configuration_status", "verification_status", "evidence"} & changed.keys():
        record.last_checked_at = now

    audit.record(audit_action, entity_type, entity_id, old=old, new=changed)
    return True

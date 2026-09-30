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
from services.errors import BusinessRule

FIELDS = ("configuration_status", "verification_status", "owner", "evidence", "notes")


def apply_update(record, changes: dict, *, audit_action: str, entity_type: str, entity_id) -> bool:
    """Apply validated `changes` to an Integration / SecurityControl and audit what changed. Returns whether anything changed."""
    changes = dict(changes)
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

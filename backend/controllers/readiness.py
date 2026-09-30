"""Request rules shared by the two readiness registers (integrations and security controls)."""
from controllers.common import Validator, json_body, require_changes
from models.enums import INTEGRATION_CONFIGURATION_STATUSES, INTEGRATION_VERIFICATION_STATUSES


def parse_update() -> dict:
    """PATCH body: any of configuration_status, verification_status, owner, evidence, notes. Blank text clears a note."""
    v = Validator(json_body())
    v.choice("configuration_status", INTEGRATION_CONFIGURATION_STATUSES)
    v.choice("verification_status", INTEGRATION_VERIFICATION_STATUSES)
    v.string("owner", min_length=1, max_length=100)
    v.string("evidence", nullable=True, max_length=2000)
    v.string("notes", nullable=True, max_length=2000)
    changes = require_changes(v.validate())
    return {field: (value or None) if field in ("evidence", "notes") else value for field, value in changes.items()}

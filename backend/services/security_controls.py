"""Security readiness: the register of security requirements with configuration status, verification and evidence."""
from models import SecurityControl
from repositories import security_controls as controls_repo
from services import readiness
from services.errors import NotFound


def list_controls() -> list[SecurityControl]:
    return controls_repo.list_all()


def get_control(control_id: int) -> SecurityControl:
    control = controls_repo.get(control_id)
    if control is None:
        raise NotFound("Security control not found")
    return control


def update_control(control_id: int, changes: dict) -> SecurityControl:
    """Super Admin: change configuration, verification, owner, evidence or notes (audited)."""
    control = get_control(control_id)
    readiness.apply_update(control, changes, audit_action="SECURITY_CONTROL_UPDATED", entity_type="security_control",
                           entity_id=control.control_code)
    return control

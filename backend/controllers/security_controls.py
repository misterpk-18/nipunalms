from controllers.common import ok
from controllers.readiness import parse_update
from services import security_controls as controls_service


def list_controls():
    return ok([c.to_dict() for c in controls_service.list_controls()])


def get_control(control_id: int):
    return ok(controls_service.get_control(control_id).to_dict())


def update_control(control_id: int):
    return ok(controls_service.update_control(control_id, parse_update()).to_dict())

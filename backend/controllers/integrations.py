from controllers.common import ok
from controllers.readiness import parse_update
from services import integrations as integrations_service


def list_integrations():
    return ok([i.to_dict() for i in integrations_service.list_integrations()])


def list_statuses():
    return ok([s.to_dict() for s in integrations_service.list_statuses()])


def get_integration(integration_id: int):
    return ok(integrations_service.get_integration(integration_id).to_dict())


def update_integration(integration_id: int):
    return ok(integrations_service.update_integration(integration_id, parse_update()).to_dict())

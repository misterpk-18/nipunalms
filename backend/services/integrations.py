"""Integration readiness: the register of what the LMS needs from outside systems, and whether each is verified.

Other slices call `integration_status(code)` / `is_verified(code)` before they rely on an integration, and record an
"Integration Unavailable" / "Pending Verification" state instead of calling out when it is not verified. Nothing in the
LMS calls Google, WhatsApp, email or telephony directly.
"""
from dataclasses import dataclass

from models import Integration
from repositories import integrations as integrations_repo
from services import readiness
from services.errors import NotFound


@dataclass(frozen=True)
class IntegrationStatus:
    integration_code: str
    configuration_status: str
    verification_status: str

    @property
    def is_verified(self) -> bool:
        return self.verification_status == "Verified"

    @property
    def state(self) -> str:
        """The status other screens show: Verified, Pending Verification, or Integration Unavailable."""
        if self.is_verified:
            return "Verified"
        return "Pending Verification" if self.verification_status == "Pending Verification" else "Integration Unavailable"

    def to_dict(self) -> dict:
        return {
            "integration_code": self.integration_code,
            "configuration_status": self.configuration_status,
            "verification_status": self.verification_status,
            "state": self.state,
        }


def integration_status(integration_code: str) -> IntegrationStatus:
    """Current status of an integration by code (e.g. 'GOOGLE_MEET'). An unknown code counts as Not Configured / Not Verified."""
    integration = integrations_repo.get_by_code(integration_code)
    if integration is None:
        return IntegrationStatus(integration_code, "Not Configured", "Not Verified")
    return IntegrationStatus(integration.integration_code, integration.configuration_status, integration.verification_status)


def is_verified(integration_code: str) -> bool:
    return integration_status(integration_code).is_verified


def list_integrations() -> list[Integration]:
    return integrations_repo.list_all()


def list_statuses() -> list[IntegrationStatus]:
    return [IntegrationStatus(i.integration_code, i.configuration_status, i.verification_status) for i in integrations_repo.list_all()]


def get_integration(integration_id: int) -> Integration:
    integration = integrations_repo.get(integration_id)
    if integration is None:
        raise NotFound("Integration not found")
    return integration


def update_integration(integration_id: int, changes: dict) -> Integration:
    """Super Admin: change configuration, verification, owner, evidence or notes (audited)."""
    integration = get_integration(integration_id)
    readiness.apply_update(integration, changes, audit_action="INTEGRATION_UPDATED", entity_type="integration",
                           entity_id=integration.integration_code)
    return integration

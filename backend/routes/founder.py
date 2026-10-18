"""The Founder's workspace: the inbox of everything waiting for them, the AI budget, and the summary of what a curriculum version
would change (UX phase U16). The decisions themselves use the existing endpoints (curriculum, certificates, access extensions)."""
from flask import Blueprint

from controllers import founder as founder_controller
from routes.decorators import fresh_auth, login_required, require_roles
from services.delivery_access import CURRICULUM_APPROVER_ROLES

founder_bp = Blueprint("founder", __name__)


@founder_bp.get("/founder/inbox")
@login_required
@require_roles("FOUNDER_CEO", "SUPER_ADMIN", "BRANCH_MANAGER")  # a Branch Manager gets only their branch's certificate requests
def inbox():
    return founder_controller.get_inbox()


@founder_bp.put("/founder/ai-budget")
@login_required
@require_roles("FOUNDER_CEO", "SUPER_ADMIN")
@fresh_auth
def ai_budget():
    return founder_controller.approve_ai_budget()


@founder_bp.get("/curriculum-versions/<int:curriculum_version_id>/impact")
@login_required
@require_roles(*CURRICULUM_APPROVER_ROLES)
def curriculum_impact(curriculum_version_id: int):
    return founder_controller.curriculum_impact_of(curriculum_version_id)

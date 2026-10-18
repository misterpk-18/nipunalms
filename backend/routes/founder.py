"""The Founder's workspace: the inbox of everything waiting for them and the AI budget (UX phase U16). The decisions themselves use
the existing endpoints (certificates, access extensions)."""
from flask import Blueprint

from controllers import founder as founder_controller
from routes.decorators import fresh_auth, login_required, require_roles

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

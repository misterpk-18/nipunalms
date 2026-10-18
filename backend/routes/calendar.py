from flask import Blueprint

from controllers import calendar as calendar_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.get("/closures")
@login_required
@require_roles(*STAFF_ROLES)
def list_closures():
    return calendar_controller.list_closures()


@calendar_bp.get("/closures/<int:closure_id>")
@login_required
@require_roles(*STAFF_ROLES)
def get_closure(closure_id: int):
    return calendar_controller.get_closure(closure_id)


@calendar_bp.post("/closures")
@login_required
@require_roles("FOUNDER_CEO", "SUPER_ADMIN", "BRANCH_MANAGER")
def create_closure():
    return calendar_controller.create_closure()


@calendar_bp.post("/closures/<int:closure_id>/decision")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def decide_closure(closure_id: int):
    return calendar_controller.decide_closure(closure_id)


@calendar_bp.patch("/closures/<int:closure_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def update_closure(closure_id: int):
    """Edit the title, reason or dates; `dry_run: true` answers with the impact (affected classes) and saves nothing."""
    return calendar_controller.update_closure(closure_id)


@calendar_bp.post("/closures/<int:closure_id>/cancel")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def cancel_closure(closure_id: int):
    """Cancel an entry that is not over (reason required); `dry_run: true` answers with the impact and cancels nothing."""
    return calendar_controller.cancel_closure(closure_id)

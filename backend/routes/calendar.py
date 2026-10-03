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
@require_roles("FOUNDER_CEO", "SUPER_ADMIN", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER")
def create_closure():
    return calendar_controller.create_closure()


@calendar_bp.post("/closures/<int:closure_id>/decision")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
def decide_closure(closure_id: int):
    return calendar_controller.decide_closure(closure_id)

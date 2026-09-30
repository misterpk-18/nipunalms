from flask import Blueprint

from controllers import reference as reference_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES

reference_bp = Blueprint("reference", __name__, url_prefix="/reference")


@reference_bp.get("/branches")
@login_required
@require_roles(*STAFF_ROLES)
def list_branches():
    return reference_controller.list_branches()


@reference_bp.get("/roles")
@login_required
@require_roles(*STAFF_ROLES)
def list_roles():
    return reference_controller.list_roles()


@reference_bp.get("/courses")
@login_required
@require_roles(*STAFF_ROLES)
def list_courses():
    return reference_controller.list_courses()


@reference_bp.get("/staff")
@login_required
@require_roles(*STAFF_ROLES)
def list_staff():
    return reference_controller.list_staff()

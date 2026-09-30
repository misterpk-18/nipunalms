from flask import Blueprint

from controllers import enrolments as enrolments_controller
from routes.decorators import login_required, require_roles
from services.context import ACADEMIC_ROLES, STAFF_ROLES

enrolments_bp = Blueprint("enrolments", __name__)


@enrolments_bp.get("/enrolments")
@login_required
@require_roles(*STAFF_ROLES)
def list_enrolments():
    return enrolments_controller.list_enrolments()


@enrolments_bp.get("/allocation-queue")
@login_required
@require_roles(*ACADEMIC_ROLES)
def allocation_queue():
    return enrolments_controller.allocation_queue()

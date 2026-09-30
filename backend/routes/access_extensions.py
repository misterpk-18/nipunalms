from flask import Blueprint

from controllers import access_extensions as extensions_controller
from routes.decorators import login_required, require_roles

access_extensions_bp = Blueprint("access_extensions", __name__, url_prefix="/access-extension-requests")

DECIDERS = ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


@access_extensions_bp.post("")
@login_required
@require_roles("STUDENT")
def create_request():
    return extensions_controller.create_request()


# A student sees their own requests; deciders see their branches' (the service narrows by role)
@access_extensions_bp.get("")
@login_required
@require_roles("STUDENT", *DECIDERS)
def list_requests():
    return extensions_controller.list_requests()


@access_extensions_bp.get("/<int:request_id>")
@login_required
@require_roles("STUDENT", *DECIDERS)
def get_request(request_id: int):
    return extensions_controller.get_request(request_id)


@access_extensions_bp.post("/<int:request_id>/decision")
@login_required
@require_roles(*DECIDERS)
def decide(request_id: int):
    return extensions_controller.decide(request_id)

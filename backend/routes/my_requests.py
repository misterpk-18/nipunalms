"""The signed-in staff member's own requests: reschedules and attendance corrections (services/my_requests.py)."""
from flask import Blueprint

from controllers import my_requests as my_requests_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES

my_requests_bp = Blueprint("my_requests", __name__)


@my_requests_bp.get("/me/requests")
@login_required
@require_roles(*STAFF_ROLES)
def list_mine():
    return my_requests_controller.list_mine()

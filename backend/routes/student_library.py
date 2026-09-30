from flask import Blueprint

from controllers import student_library as library_controller
from routes.decorators import login_required, require_roles

student_library_bp = Blueprint("student_library", __name__, url_prefix="/me")


@student_library_bp.get("/resources")
@login_required
@require_roles("STUDENT")
def list_resources():
    return library_controller.list_resources()


@student_library_bp.get("/recordings")
@login_required
@require_roles("STUDENT")
def list_recordings():
    return library_controller.list_recordings()


@student_library_bp.get("/access")
@login_required
@require_roles("STUDENT")
def get_access():
    return library_controller.get_access()

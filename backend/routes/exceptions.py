"""The exception queue: open exceptions from every slice, and the recovery steps logged against them."""
from flask import Blueprint

from controllers import exceptions as exceptions_controller
from routes.decorators import login_required, require_roles

exceptions_bp = Blueprint("exceptions", __name__, url_prefix="/exceptions")

READERS = ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
LOGGERS = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")


@exceptions_bp.get("")
@login_required
@require_roles(*READERS)
def list_exceptions():
    return exceptions_controller.list_exceptions()


@exceptions_bp.get("/<string:source>/<int:source_id>/steps")
@login_required
@require_roles(*READERS)
def list_steps(source: str, source_id: int):
    return exceptions_controller.list_steps(source.upper(), source_id)


@exceptions_bp.post("/<string:source>/<int:source_id>/steps")
@login_required
@require_roles(*LOGGERS)
def log_step(source: str, source_id: int):
    return exceptions_controller.log_step(source.upper(), source_id)

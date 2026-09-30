from flask import Blueprint

from controllers import content as content_controller
from routes.decorators import login_required, require_roles

content_bp = Blueprint("content", __name__, url_prefix="/content-items")

STAFF = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
AUTHORS = ("TRAINER", "ACADEMIC_COORDINATOR", "SUPER_ADMIN")
REVIEWERS = ("ACADEMIC_COORDINATOR", "SUPER_ADMIN")


@content_bp.get("")
@login_required
@require_roles(*STAFF)
def list_items():
    return content_controller.list_items()


@content_bp.post("")
@login_required
@require_roles(*AUTHORS)
def create_item():
    return content_controller.create_item()


@content_bp.get("/options")
@login_required
@require_roles(*STAFF)
def placement_options():
    return content_controller.placement_options()


@content_bp.get("/<int:content_item_id>")
@login_required
@require_roles(*STAFF)
def get_item(content_item_id: int):
    return content_controller.get_item(content_item_id)


@content_bp.patch("/<int:content_item_id>")
@login_required
@require_roles(*AUTHORS)
def update_item(content_item_id: int):
    return content_controller.update_item(content_item_id)


@content_bp.post("/<int:content_item_id>/versions")
@login_required
@require_roles(*AUTHORS)
def add_version(content_item_id: int):
    return content_controller.add_version(content_item_id)


@content_bp.post("/<int:content_item_id>/submit")
@login_required
@require_roles(*AUTHORS)
def submit(content_item_id: int):
    return content_controller.submit(content_item_id)


@content_bp.post("/<int:content_item_id>/review")
@login_required
@require_roles(*REVIEWERS)
def review(content_item_id: int):
    return content_controller.review(content_item_id)


@content_bp.post("/<int:content_item_id>/release")
@login_required
@require_roles(*REVIEWERS)
def release(content_item_id: int):
    return content_controller.release(content_item_id)


@content_bp.post("/<int:content_item_id>/retire")
@login_required
@require_roles(*REVIEWERS)
def retire(content_item_id: int):
    return content_controller.retire(content_item_id)


# Open and file retrieval serve students (entitlement + expiry) and staff (preview); the service decides
@content_bp.post("/<int:content_item_id>/open")
@login_required
def open_item(content_item_id: int):
    return content_controller.open_item(content_item_id)


@content_bp.get("/<int:content_item_id>/file")
@login_required
def get_file(content_item_id: int):
    return content_controller.get_file(content_item_id)

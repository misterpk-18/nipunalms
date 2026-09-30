from flask import Blueprint

from controllers import curriculum as curriculum_controller
from routes.decorators import fresh_auth, login_required, require_roles
from services.context import STAFF_ROLES
from services.delivery_access import CURRICULUM_ROLES

curriculum_bp = Blueprint("curriculum", __name__)


@curriculum_bp.get("/curriculum/overview")
@login_required
@require_roles(*STAFF_ROLES)
def overview():
    return curriculum_controller.overview()


@curriculum_bp.get("/curriculum-versions")
@login_required
@require_roles(*STAFF_ROLES)
def list_versions():
    return curriculum_controller.list_versions()


@curriculum_bp.post("/curriculum-versions")
@login_required
@require_roles(*CURRICULUM_ROLES)
def create_version():
    return curriculum_controller.create_version()


@curriculum_bp.get("/curriculum-versions/<int:curriculum_version_id>")
@login_required
@require_roles(*STAFF_ROLES)
def get_version(curriculum_version_id: int):
    return curriculum_controller.get_version(curriculum_version_id)


@curriculum_bp.patch("/curriculum-versions/<int:curriculum_version_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def update_version(curriculum_version_id: int):
    return curriculum_controller.update_version(curriculum_version_id)


@curriculum_bp.delete("/curriculum-versions/<int:curriculum_version_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def delete_version(curriculum_version_id: int):
    return curriculum_controller.delete_version(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/submit")
@login_required
@require_roles(*CURRICULUM_ROLES)
def submit(curriculum_version_id: int):
    return curriculum_controller.submit(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/return")
@login_required
@require_roles(*CURRICULUM_ROLES)
def return_to_draft(curriculum_version_id: int):
    return curriculum_controller.return_to_draft(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/approve")
@login_required
@require_roles(*CURRICULUM_ROLES)
@fresh_auth
def approve(curriculum_version_id: int):
    return curriculum_controller.approve(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/activate")
@login_required
@require_roles(*CURRICULUM_ROLES)
@fresh_auth
def activate(curriculum_version_id: int):
    return curriculum_controller.activate(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/retire")
@login_required
@require_roles(*CURRICULUM_ROLES)
@fresh_auth
def retire(curriculum_version_id: int):
    return curriculum_controller.retire(curriculum_version_id)


@curriculum_bp.post("/curriculum-versions/<int:curriculum_version_id>/modules")
@login_required
@require_roles(*CURRICULUM_ROLES)
def add_module(curriculum_version_id: int):
    return curriculum_controller.add_module(curriculum_version_id)


@curriculum_bp.patch("/curriculum-modules/<int:module_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def update_module(module_id: int):
    return curriculum_controller.update_module(module_id)


@curriculum_bp.delete("/curriculum-modules/<int:module_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def delete_module(module_id: int):
    return curriculum_controller.delete_module(module_id)


@curriculum_bp.post("/curriculum-modules/<int:module_id>/topics")
@login_required
@require_roles(*CURRICULUM_ROLES)
def add_topic(module_id: int):
    return curriculum_controller.add_topic(module_id)


@curriculum_bp.patch("/curriculum-topics/<int:topic_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def update_topic(topic_id: int):
    return curriculum_controller.update_topic(topic_id)


@curriculum_bp.delete("/curriculum-topics/<int:topic_id>")
@login_required
@require_roles(*CURRICULUM_ROLES)
def delete_topic(topic_id: int):
    return curriculum_controller.delete_topic(topic_id)

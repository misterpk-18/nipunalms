from flask import Blueprint

from controllers import batches as batches_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES
from services.delivery_access import MANAGE_ROLES

batches_bp = Blueprint("batches", __name__, url_prefix="/batches")


@batches_bp.get("")
@login_required
def list_batches():
    return batches_controller.list_batches()


@batches_bp.post("")
@login_required
@require_roles(*MANAGE_ROLES)
def create_batch():
    return batches_controller.create_batch()


@batches_bp.get("/<int:batch_id>")
@login_required
def get_batch(batch_id: int):
    return batches_controller.get_batch(batch_id)


@batches_bp.patch("/<int:batch_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def update_batch(batch_id: int):
    return batches_controller.update_batch(batch_id)


@batches_bp.post("/<int:batch_id>/state")
@login_required
@require_roles(*MANAGE_ROLES)
def transition(batch_id: int):
    return batches_controller.transition(batch_id)


@batches_bp.get("/<int:batch_id>/readiness")
@login_required
@require_roles(*STAFF_ROLES)
def get_readiness(batch_id: int):
    return batches_controller.get_readiness(batch_id)


@batches_bp.patch("/<int:batch_id>/readiness")
@login_required
@require_roles(*MANAGE_ROLES)
def set_readiness(batch_id: int):
    return batches_controller.set_readiness(batch_id)


@batches_bp.post("/<int:batch_id>/trainers")
@login_required
@require_roles(*MANAGE_ROLES)
def assign_trainer(batch_id: int):
    return batches_controller.assign_trainer(batch_id)


@batches_bp.patch("/<int:batch_id>/trainers/<int:batch_trainer_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def change_trainer_role(batch_id: int, batch_trainer_id: int):
    return batches_controller.change_trainer_role(batch_id, batch_trainer_id)


@batches_bp.delete("/<int:batch_id>/trainers/<int:batch_trainer_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def end_trainer(batch_id: int, batch_trainer_id: int):
    return batches_controller.end_trainer(batch_id, batch_trainer_id)

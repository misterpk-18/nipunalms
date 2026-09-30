from flask import Blueprint

from controllers import batches as batches_controller
from routes.decorators import login_required

batches_bp = Blueprint("batches", __name__, url_prefix="/batches")


@batches_bp.get("")
@login_required
def list_batches():
    return batches_controller.list_batches()


@batches_bp.get("/<int:batch_id>")
@login_required
def get_batch(batch_id: int):
    return batches_controller.get_batch(batch_id)

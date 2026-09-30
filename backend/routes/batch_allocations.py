from flask import Blueprint

from controllers import batch_allocations as allocations_controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES
from services.delivery_access import MANAGE_ROLES

batch_allocations_bp = Blueprint("batch_allocations", __name__)


@batch_allocations_bp.get("/batches/<int:batch_id>/allocations")
@login_required
@require_roles(*STAFF_ROLES)
def roster(batch_id: int):
    return allocations_controller.roster(batch_id)


@batch_allocations_bp.get("/batches/<int:batch_id>/allocation-review")
@login_required
@require_roles(*MANAGE_ROLES)
def review(batch_id: int):
    return allocations_controller.review(batch_id)


@batch_allocations_bp.post("/batches/<int:batch_id>/allocations")
@login_required
@require_roles(*MANAGE_ROLES)
def allocate(batch_id: int):
    return allocations_controller.allocate(batch_id)


@batch_allocations_bp.post("/enrolments/<int:enrolment_id>/transfer")
@login_required
@require_roles(*MANAGE_ROLES)
def transfer(enrolment_id: int):
    return allocations_controller.transfer(enrolment_id)


@batch_allocations_bp.post("/enrolments/<int:enrolment_id>/deallocate")
@login_required
@require_roles(*MANAGE_ROLES)
def deallocate(enrolment_id: int):
    return allocations_controller.deallocate(enrolment_id)

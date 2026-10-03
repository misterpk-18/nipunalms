from flask import Blueprint

from controllers import batch_operations as controller
from routes.decorators import login_required, require_roles
from services.context import STAFF_ROLES
from services.delivery_access import MANAGE_ROLES

batch_operations_bp = Blueprint("batch_operations", __name__)
DECIDERS = ("BRANCH_MANAGER", "SUPER_ADMIN")


# ---------------------------------------------------------------- capacity increases

@batch_operations_bp.post("/batches/<int:batch_id>/capacity-requests")
@login_required
@require_roles(*MANAGE_ROLES)
def request_capacity(batch_id: int):
    return controller.request_capacity(batch_id)


@batch_operations_bp.get("/batch-capacity-requests")
@login_required
@require_roles(*MANAGE_ROLES, "FOUNDER_CEO")
def list_capacity_requests():
    return controller.list_capacity_requests()


@batch_operations_bp.post("/batch-capacity-requests/<int:request_id>/decision")
@login_required
@require_roles(*DECIDERS)
def decide_capacity(request_id: int):
    return controller.decide_capacity(request_id)


# ---------------------------------------------------------------- transfers

@batch_operations_bp.post("/enrolments/<int:enrolment_id>/transfer-requests")
@login_required
@require_roles(*MANAGE_ROLES)
def request_transfer(enrolment_id: int):
    return controller.request_transfer(enrolment_id)


@batch_operations_bp.get("/batch-transfer-requests")
@login_required
@require_roles(*MANAGE_ROLES, "FOUNDER_CEO")
def list_transfer_requests():
    return controller.list_transfer_requests()


@batch_operations_bp.post("/batch-transfer-requests/<int:request_id>/destination")
@login_required
@require_roles(*MANAGE_ROLES)
def confirm_destination(request_id: int):
    return controller.confirm_destination(request_id)


@batch_operations_bp.post("/batch-transfer-requests/<int:request_id>/decision")
@login_required
@require_roles(*DECIDERS)
def decide_transfer(request_id: int):
    return controller.decide_transfer(request_id)


# ---------------------------------------------------------------- material changes and agreement

@batch_operations_bp.post("/batches/<int:batch_id>/material-changes")
@login_required
@require_roles(*MANAGE_ROLES)
def propose_change(batch_id: int):
    return controller.propose_change(batch_id)


@batch_operations_bp.get("/material-changes")
@login_required
@require_roles(*STAFF_ROLES)
def list_changes():
    return controller.list_changes()


@batch_operations_bp.get("/material-changes/<int:change_id>")
@login_required
@require_roles(*STAFF_ROLES)
def get_change(change_id: int):
    return controller.get_change(change_id)


@batch_operations_bp.post("/material-changes/<int:change_id>/decision")
@login_required
@require_roles(*DECIDERS)
def decide_change(change_id: int):
    return controller.decide_change(change_id)


@batch_operations_bp.post("/material-changes/<int:change_id>/responses")
@login_required
@require_roles(*MANAGE_ROLES)
def record_response(change_id: int):
    return controller.record_response(change_id)


@batch_operations_bp.post("/material-changes/<int:change_id>/apply")
@login_required
@require_roles(*MANAGE_ROLES)
def apply_change(change_id: int):
    return controller.apply_change(change_id)


@batch_operations_bp.post("/material-changes/<int:change_id>/withdraw")
@login_required
@require_roles(*MANAGE_ROLES)
def withdraw_change(change_id: int):
    return controller.withdraw_change(change_id)


@batch_operations_bp.get("/me/material-changes")
@login_required
@require_roles("STUDENT")
def my_changes():
    return controller.my_changes()


@batch_operations_bp.post("/me/material-changes/<int:change_id>/response")
@login_required
@require_roles("STUDENT")
def respond_as_student(change_id: int):
    return controller.respond_as_student(change_id)


# ---------------------------------------------------------------- merge / split

@batch_operations_bp.post("/batch-successions")
@login_required
@require_roles(*MANAGE_ROLES)
def request_succession():
    return controller.request_succession()


@batch_operations_bp.get("/batch-successions")
@login_required
@require_roles(*MANAGE_ROLES, "FOUNDER_CEO")
def list_successions():
    return controller.list_successions()


@batch_operations_bp.post("/batch-successions/<int:succession_id>/decision")
@login_required
@require_roles(*DECIDERS)
def decide_succession(succession_id: int):
    return controller.decide_succession(succession_id)


# ---------------------------------------------------------------- slot preferences

@batch_operations_bp.get("/me/slot-options")
@login_required
@require_roles("STUDENT")
def slot_options():
    return controller.slot_options()


@batch_operations_bp.get("/me/slot-preferences")
@login_required
@require_roles("STUDENT")
def my_preferences():
    return controller.my_preferences()


@batch_operations_bp.post("/me/slot-preferences")
@login_required
@require_roles("STUDENT")
def create_preference():
    return controller.create_preference()


@batch_operations_bp.post("/me/slot-preferences/<int:preference_id>/withdraw")
@login_required
@require_roles("STUDENT")
def withdraw_preference(preference_id: int):
    return controller.withdraw_preference(preference_id)


@batch_operations_bp.get("/slot-preferences")
@login_required
@require_roles(*MANAGE_ROLES, "FOUNDER_CEO")
def list_preferences():
    return controller.list_preferences()


@batch_operations_bp.patch("/slot-preferences/<int:preference_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def set_preference_status(preference_id: int):
    return controller.set_preference_status(preference_id)

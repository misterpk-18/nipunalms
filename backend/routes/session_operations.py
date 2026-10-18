from flask import Blueprint

from controllers import session_operations as controller
from routes.decorators import login_required, require_roles
from services.context import ADMIN_ROLES, STAFF_ROLES
from services.delivery_access import MANAGE_ROLES

session_operations_bp = Blueprint("session_operations", __name__)
TEACHING_ROLES = ("TRAINER", *MANAGE_ROLES)


@session_operations_bp.get("/meet-operations")
@login_required
@require_roles(*STAFF_ROLES)
def operations_view():
    return controller.operations_view()


@session_operations_bp.get("/class-sessions/<int:session_id>/operations")
@login_required
@require_roles(*STAFF_ROLES)
def operations_detail(session_id: int):
    return controller.operations_detail(session_id)


# ---------------------------------------------------------------- hosts, backups and guests

@session_operations_bp.post("/class-sessions/<int:session_id>/people")
@login_required
@require_roles(*MANAGE_ROLES)
def add_person(session_id: int):
    return controller.add_person(session_id)


@session_operations_bp.post("/session-people/<int:person_id>/decision")
@login_required
@require_roles(*MANAGE_ROLES, *ADMIN_ROLES)  # the Founder / Super Admin only for a Branch Manager's own guest (the service refuses others)
def decide_guest(person_id: int):
    return controller.decide_guest(person_id)


@session_operations_bp.delete("/session-people/<int:person_id>")
@login_required
@require_roles(*MANAGE_ROLES)
def remove_person(person_id: int):
    return controller.remove_person(person_id)


# ---------------------------------------------------------------- incidents and participation

@session_operations_bp.post("/class-sessions/<int:session_id>/meet-incidents")
@login_required
@require_roles(*TEACHING_ROLES)
def report_incident(session_id: int):
    return controller.report_incident(session_id)


@session_operations_bp.post("/class-sessions/<int:session_id>/participation")
@login_required
@require_roles(*MANAGE_ROLES)
def record_participation(session_id: int):
    return controller.record_participation(session_id)


@session_operations_bp.get("/meet-participation/unmatched")
@login_required
@require_roles(*MANAGE_ROLES, *ADMIN_ROLES)
def list_unmatched():
    return controller.list_unmatched()


@session_operations_bp.post("/meet-participation/<int:participation_id>/review")
@login_required
@require_roles(*MANAGE_ROLES)
def review_participation(participation_id: int):
    return controller.review_participation(participation_id)


# ---------------------------------------------------------------- disruptions

@session_operations_bp.get("/session-disruptions")
@login_required
@require_roles(*STAFF_ROLES)
def list_disruptions():
    return controller.list_disruptions()


@session_operations_bp.post("/class-sessions/<int:session_id>/disruptions")
@login_required
@require_roles(*TEACHING_ROLES)
def record_disruption(session_id: int):
    return controller.record_disruption(session_id)


@session_operations_bp.post("/session-disruptions/<int:disruption_id>/resolve")
@login_required
@require_roles(*MANAGE_ROLES)
def resolve_disruption(disruption_id: int):
    return controller.resolve_disruption(disruption_id)


# ---------------------------------------------------------------- cover

@session_operations_bp.post("/class-sessions/<int:session_id>/cover-requests")
@login_required
@require_roles(*MANAGE_ROLES)
def request_cover(session_id: int):
    return controller.request_cover(session_id)


@session_operations_bp.get("/session-cover-requests")
@login_required
@require_roles(*STAFF_ROLES)
def list_cover():
    return controller.list_cover()


@session_operations_bp.post("/session-cover-requests/<int:request_id>/decision")
@login_required
@require_roles(*MANAGE_ROLES, *ADMIN_ROLES)  # the Founder / Super Admin only for a Branch Manager's own request
def decide_cover(request_id: int):
    return controller.decide_cover(request_id)


@session_operations_bp.post("/session-cover-requests/<int:request_id>/verification")
@login_required
@require_roles("BRANCH_MANAGER")
def verify_cover(request_id: int):
    return controller.verify_cover(request_id)


# ---------------------------------------------------------------- shared classes

@session_operations_bp.post("/class-sessions/<int:session_id>/rosters")
@login_required
@require_roles("BRANCH_MANAGER")
def add_roster(session_id: int):
    return controller.add_roster(session_id)


@session_operations_bp.delete("/class-sessions/<int:session_id>/rosters/<int:batch_id>")
@login_required
@require_roles("BRANCH_MANAGER")
def remove_roster(session_id: int, batch_id: int):
    return controller.remove_roster(session_id, batch_id)

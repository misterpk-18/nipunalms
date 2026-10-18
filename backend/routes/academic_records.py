from flask import Blueprint

from controllers import academic_records as controller
from routes.decorators import fresh_auth, login_required, require_roles
from services.context import STAFF_ROLES

academic_records_bp = Blueprint("academic_records", __name__)
EDITORS = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


@academic_records_bp.get("/equivalence-rules")
@login_required
@require_roles(*STAFF_ROLES)
def list_rules():
    return controller.list_rules()


@academic_records_bp.post("/equivalence-rules")
@login_required
@require_roles(*EDITORS)
def request_rule():
    return controller.request_rule()


@academic_records_bp.post("/equivalence-rules/<int:rule_id>/decision")
@login_required
@require_roles("FOUNDER_CEO", "SUPER_ADMIN")
@fresh_auth
def decide_rule(rule_id: int):
    return controller.decide_rule(rule_id)


@academic_records_bp.get("/academic-mappings")
@login_required
@require_roles(*STAFF_ROLES)
def list_mappings():
    return controller.list_mappings()


@academic_records_bp.post("/enrolments/<int:enrolment_id>/academic-mappings")
@login_required
@require_roles("TRAINER", *EDITORS)
def request_mapping(enrolment_id: int):
    return controller.request_mapping(enrolment_id)


@academic_records_bp.post("/academic-mappings/<int:mapping_id>/decision")
@login_required
@require_roles(*EDITORS)
@fresh_auth
def decide_mapping(mapping_id: int):
    return controller.decide_mapping(mapping_id)


@academic_records_bp.get("/curriculum-variations")
@login_required
@require_roles(*STAFF_ROLES)
def list_variations():
    return controller.list_variations()


@academic_records_bp.post("/curriculum-variations")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def create_variation():
    return controller.create_variation()


@academic_records_bp.post("/curriculum-variations/<int:variation_id>/decision")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def decide_variation(variation_id: int):
    return controller.decide_variation(variation_id)


@academic_records_bp.get("/curriculum-library")
@login_required
@require_roles(*STAFF_ROLES)
def list_library():
    return controller.list_library()


@academic_records_bp.post("/curriculum-modules/<int:module_id>/library")
@login_required
@require_roles(*EDITORS)
def save_to_library(module_id: int):
    return controller.save_to_library(module_id)


@academic_records_bp.post("/curriculum-library/<int:library_module_id>/versions")
@login_required
@require_roles(*EDITORS)
def propose_library_version(library_module_id: int):
    return controller.propose_library_version(library_module_id)


@academic_records_bp.post("/curriculum-library-versions/<int:library_version_id>/decision")
@login_required
@require_roles(*EDITORS)
def decide_library_version(library_version_id: int):
    return controller.decide_library_version(library_version_id)


@academic_records_bp.post("/curriculum-versions/<int:curriculum_version_id>/library-modules")
@login_required
@require_roles(*EDITORS)
def insert_library_module(curriculum_version_id: int):
    return controller.insert_library_module(curriculum_version_id)

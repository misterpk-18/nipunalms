"""Certificate Register endpoints, the student's own list and the public verification."""
from flask import Blueprint

from controllers import certificates as certificates_controller
from routes.decorators import fresh_auth, login_required, require_roles

certificates_bp = Blueprint("certificates", __name__)

REGISTER_READERS = ("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")


@certificates_bp.get("/certificates/verify/<number>")
def verify(number: str):
    return certificates_controller.verify(number)


@certificates_bp.get("/certificates")
@login_required
@require_roles(*REGISTER_READERS)
def list_register():
    return certificates_controller.list_register()


@certificates_bp.get("/me/certificates")
@login_required
@require_roles("STUDENT")
def my_certificates():
    return certificates_controller.my_certificates()


@certificates_bp.get("/certificates/<int:certificate_id>")
@login_required
@require_roles("STUDENT", *REGISTER_READERS)
def get_certificate(certificate_id: int):
    return certificates_controller.get_certificate(certificate_id)


@certificates_bp.post("/certificates")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
def create_entry():
    return certificates_controller.create_entry()


@certificates_bp.post("/certificates/<int:certificate_id>/recommendation")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
def recommend(certificate_id: int):
    return certificates_controller.recommend(certificate_id)


@certificates_bp.post("/certificates/<int:certificate_id>/return")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
def return_to_review(certificate_id: int):
    return certificates_controller.return_to_review(certificate_id)


@certificates_bp.post("/certificates/<int:certificate_id>/approval")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
@fresh_auth
def approve(certificate_id: int):
    return certificates_controller.approve(certificate_id)


@certificates_bp.post("/certificates/<int:certificate_id>/issue")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
@fresh_auth
def issue(certificate_id: int):
    return certificates_controller.issue(certificate_id)


@certificates_bp.post("/certificates/<int:certificate_id>/change-requests")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
def request_change(certificate_id: int):
    return certificates_controller.request_change(certificate_id)


@certificates_bp.get("/certificate-requests")
@login_required
@require_roles(*REGISTER_READERS)
def list_requests():
    return certificates_controller.list_requests()


@certificates_bp.post("/certificate-requests/<int:request_id>/decision")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN", "FOUNDER_CEO")
@fresh_auth
def decide_request(request_id: int):
    return certificates_controller.decide_request(request_id)


@certificates_bp.post("/certificates/<int:certificate_id>/financial-exception")
@login_required
@require_roles("BRANCH_MANAGER", "SUPER_ADMIN")
def request_exception(certificate_id: int):
    return certificates_controller.request_exception(certificate_id)


@certificates_bp.get("/certificate-financial-exceptions")
@login_required
@require_roles(*REGISTER_READERS)
def list_exceptions():
    return certificates_controller.list_exceptions()


@certificates_bp.post("/certificate-financial-exceptions/<int:exception_id>/decision")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
@fresh_auth
def decide_exception(exception_id: int):
    return certificates_controller.decide_exception(exception_id)

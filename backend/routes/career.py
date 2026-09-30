from flask import Blueprint

from controllers import career as career_controller
from routes.decorators import fresh_auth, login_required, require_roles
from services.context import ACADEMIC_ROLES, ADMIN_ROLES

career_bp = Blueprint("career", __name__)


# ---------------------------------------------------------------- student (own career support)

@career_bp.get("/me/career")
@login_required
@require_roles("STUDENT")
def overview():
    return career_controller.overview()


@career_bp.put("/me/career/profile")
@login_required
@require_roles("STUDENT")
def update_profile():
    return career_controller.update_profile()


@career_bp.put("/me/career/consent")
@login_required
@require_roles("STUDENT")
def set_consent():
    return career_controller.set_consent()


@career_bp.post("/me/career/cvs")
@login_required
@require_roles("STUDENT")
def upload_cv():
    return career_controller.upload_cv()


@career_bp.post("/me/career/opportunities/<int:opportunity_id>/apply")
@login_required
@require_roles("STUDENT")
def apply(opportunity_id: int):
    return career_controller.apply(opportunity_id)


@career_bp.post("/me/career/applications/<int:application_id>/withdraw")
@login_required
@require_roles("STUDENT")
def withdraw(application_id: int):
    return career_controller.withdraw(application_id)


# ---------------------------------------------------------------- CV files (the student, or staff who see the student)

@career_bp.get("/cv-documents/<int:cv_id>/download")
@login_required
@require_roles("STUDENT", *ACADEMIC_ROLES)
def download_cv(cv_id: int):
    return career_controller.download_cv(cv_id)


# ---------------------------------------------------------------- staff (Academic Coordinator, Branch Manager, Super Admin)

@career_bp.get("/opportunities")
@login_required
@require_roles(*ACADEMIC_ROLES)
def list_opportunities():
    return career_controller.list_opportunities()


@career_bp.post("/opportunities")
@login_required
@require_roles(*ACADEMIC_ROLES)
def create_opportunity():
    return career_controller.create_opportunity()


@career_bp.get("/opportunities/<int:opportunity_id>")
@login_required
@require_roles(*ACADEMIC_ROLES)
def get_opportunity(opportunity_id: int):
    return career_controller.get_opportunity(opportunity_id)


@career_bp.patch("/opportunities/<int:opportunity_id>")
@login_required
@require_roles(*ACADEMIC_ROLES)
def update_opportunity(opportunity_id: int):
    return career_controller.update_opportunity(opportunity_id)


@career_bp.post("/opportunities/<int:opportunity_id>/status")
@login_required
@require_roles(*ACADEMIC_ROLES)
def change_opportunity_status(opportunity_id: int):
    return career_controller.change_opportunity_status(opportunity_id)


@career_bp.get("/career-profiles")
@login_required
@require_roles(*ACADEMIC_ROLES)
def list_profiles():
    return career_controller.list_profiles()


@career_bp.get("/career-profiles/<int:student_id>")
@login_required
@require_roles(*ACADEMIC_ROLES)
def get_student_career(student_id: int):
    return career_controller.get_student_career(student_id)


@career_bp.post("/career-profiles/<int:student_id>/review")
@login_required
@require_roles(*ACADEMIC_ROLES)
def review_profile(student_id: int):
    return career_controller.review_profile(student_id)


@career_bp.post("/career-profiles/<int:student_id>/extend-support")
@login_required
@require_roles(*ADMIN_ROLES)
@fresh_auth
def extend_support(student_id: int):
    return career_controller.extend_support(student_id)


@career_bp.post("/cv-documents/<int:cv_id>/review")
@login_required
@require_roles(*ACADEMIC_ROLES)
def review_cv(cv_id: int):
    return career_controller.review_cv(cv_id)


@career_bp.get("/applications")
@login_required
@require_roles(*ACADEMIC_ROLES)
def list_applications():
    return career_controller.list_applications()


@career_bp.get("/applications/<int:application_id>")
@login_required
@require_roles(*ACADEMIC_ROLES)
def get_application(application_id: int):
    return career_controller.get_application(application_id)


@career_bp.post("/applications/<int:application_id>/status")
@login_required
@require_roles(*ACADEMIC_ROLES)
def change_application_status(application_id: int):
    return career_controller.change_application_status(application_id)


@career_bp.get("/placement-outcomes")
@login_required
@require_roles(*ACADEMIC_ROLES)
def list_outcomes():
    return career_controller.list_outcomes()


@career_bp.post("/placement-outcomes")
@login_required
@require_roles(*ACADEMIC_ROLES)
def record_outcome():
    return career_controller.record_outcome()


@career_bp.get("/placement-outcomes/summary")
@login_required
@require_roles(*ACADEMIC_ROLES)
def outcome_summary():
    return career_controller.outcome_summary()


@career_bp.post("/placement-outcomes/<int:outcome_id>/verify")
@login_required
@require_roles(*ACADEMIC_ROLES)
def verify_outcome(outcome_id: int):
    return career_controller.verify_outcome(outcome_id)

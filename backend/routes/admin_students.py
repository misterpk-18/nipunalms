from flask import Blueprint

from controllers import admin_students as students_controller
from routes.decorators import fresh_auth, login_required, require_roles

admin_students_bp = Blueprint("admin_students", __name__, url_prefix="/admin/students")


@admin_students_bp.get("")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def search():
    return students_controller.search()


@admin_students_bp.get("/<int:student_id>")
@login_required
@require_roles("SUPER_ADMIN", "FOUNDER_CEO")
def get_student(student_id: int):
    return students_controller.get_student(student_id)


@admin_students_bp.post("/<int:student_id>/suspend")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def suspend(student_id: int):
    return students_controller.suspend(student_id)


@admin_students_bp.post("/<int:student_id>/reactivate")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def reactivate(student_id: int):
    return students_controller.reactivate(student_id)


@admin_students_bp.post("/<int:student_id>/revoke-sessions")
@login_required
@require_roles("SUPER_ADMIN")
@fresh_auth
def revoke_sessions(student_id: int):
    return students_controller.revoke_sessions(student_id)

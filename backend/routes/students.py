from flask import Blueprint

from controllers import students as students_controller
from routes.decorators import fresh_auth, login_required, require_roles

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.get("/<int:student_id>")
@login_required
def get_student(student_id: int):
    return students_controller.get_student(student_id)


@students_bp.post("/<int:student_id>/activation")
@login_required
@require_roles("SUPER_ADMIN", "BRANCH_MANAGER", "ACADEMIC_COORDINATOR")
@fresh_auth
def issue_activation(student_id: int):
    return students_controller.issue_activation(student_id)

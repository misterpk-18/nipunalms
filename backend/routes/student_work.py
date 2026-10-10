"""Tasks & Tests: the student's assignments and tests on one list (see services/student_work.py)."""
from flask import Blueprint

from controllers import student_work as controller
from routes.decorators import login_required, require_roles

student_work_bp = Blueprint("student_work", __name__)


@student_work_bp.get("/me/work")
@login_required
@require_roles("STUDENT")
def my_work():
    return controller.my_work()

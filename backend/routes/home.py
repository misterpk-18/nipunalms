"""Landing screens: Student Home and Trainer Today. One summary endpoint each (see services/student_home.py, trainer_workspace.py)."""
from flask import Blueprint

from controllers import home as home_controller
from routes.decorators import login_required, require_roles

home_bp = Blueprint("home", __name__)


@home_bp.get("/me/home")
@login_required
@require_roles("STUDENT")
def my_home():
    return home_controller.my_home()


@home_bp.get("/trainer/today")
@login_required
@require_roles("TRAINER")
def trainer_today():
    return home_controller.trainer_today()

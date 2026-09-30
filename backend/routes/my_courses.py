from flask import Blueprint

from controllers import learning as learning_controller
from controllers import my_courses as my_courses_controller
from routes.decorators import login_required, require_roles

my_courses_bp = Blueprint("my_courses", __name__)


@my_courses_bp.get("/me/enrolments")
@login_required
@require_roles("STUDENT")
def list_enrolments():
    return my_courses_controller.list_enrolments()


@my_courses_bp.get("/me/enrolments/<int:enrolment_id>")
@login_required
@require_roles("STUDENT")
def get_enrolment(enrolment_id: int):
    return my_courses_controller.get_enrolment(enrolment_id)


@my_courses_bp.get("/me/enrolments/<int:enrolment_id>/tracks/<int:enrolment_track_id>")
@login_required
@require_roles("STUDENT")
def get_track(enrolment_id: int, enrolment_track_id: int):
    return my_courses_controller.get_track(enrolment_id, enrolment_track_id)


@my_courses_bp.get("/me/schedule")
@login_required
@require_roles("STUDENT")
def schedule():
    return my_courses_controller.schedule()


@my_courses_bp.get("/modules/<int:module_id>")
@login_required
def get_module(module_id: int):
    return learning_controller.get_module(module_id)


@my_courses_bp.get("/topics/<int:topic_id>")
@login_required
def get_topic(topic_id: int):
    return learning_controller.get_topic(topic_id)

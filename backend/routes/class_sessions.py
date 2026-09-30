from flask import Blueprint

from controllers import class_sessions as class_sessions_controller
from routes.decorators import login_required

class_sessions_bp = Blueprint("class_sessions", __name__, url_prefix="/class-sessions")


@class_sessions_bp.get("")
@login_required
def list_class_sessions():
    return class_sessions_controller.list_class_sessions()

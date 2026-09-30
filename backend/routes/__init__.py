"""The one place that lists every blueprint."""
from flask import Flask

from routes.auth import auth_bp
from routes.batches import batches_bp
from routes.class_sessions import class_sessions_bp
from routes.crm import crm_bp
from routes.health import health_bp
from routes.reference import reference_bp
from routes.students import students_bp

BLUEPRINTS = [
    health_bp,
    auth_bp,
    reference_bp,
    students_bp,
    batches_bp,
    class_sessions_bp,
    crm_bp,
]


# Student services slice (050)
from routes.ask_nipuna import ask_nipuna_bp  # noqa: E402
from routes.career import career_bp  # noqa: E402
from routes.finance import finance_bp  # noqa: E402
from routes.notifications import notifications_bp  # noqa: E402
from routes.profile import profile_bp  # noqa: E402
from routes.support import support_bp, trainer_students_bp  # noqa: E402

BLUEPRINTS += [support_bp, trainer_students_bp, notifications_bp, career_bp, profile_bp, finance_bp, ask_nipuna_bp]


def register_blueprints(app: Flask) -> None:
    prefix = app.config["API_PREFIX"]
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=prefix + (blueprint.url_prefix or ""))

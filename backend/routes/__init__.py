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


def register_blueprints(app: Flask) -> None:
    prefix = app.config["API_PREFIX"]
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=prefix + (blueprint.url_prefix or ""))

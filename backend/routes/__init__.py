"""The one place that lists every blueprint."""
from flask import Flask

from routes.auth import auth_bp
from routes.batches import batches_bp
from routes.class_sessions import class_sessions_bp
from routes.crm import crm_bp
from routes.health import health_bp
from routes.reference import reference_bp
from routes.students import students_bp
from routes.admin_students import admin_students_bp
from routes.admin_users import admin_users_bp
from routes.audit_log import audit_log_bp
from routes.crm_sync import crm_sync_bp
from routes.integrations import integrations_bp
from routes.security_controls import security_controls_bp

# Slice S4: attendance, progress, completion review, certificates
from routes.attendance import attendance_bp
from routes.certificates import certificates_bp
from routes.completion import completion_bp
from routes.progress import progress_bp
from routes.batch_allocations import batch_allocations_bp
from routes.curriculum import curriculum_bp
from routes.enrolments import enrolments_bp
from routes.my_courses import my_courses_bp
from routes.assignments import assignments_bp
from routes.questions import questions_bp
from routes.results import results_bp
from routes.tests import tests_bp

BLUEPRINTS = [
    health_bp,
    auth_bp,
    reference_bp,
    students_bp,
    batches_bp,
    class_sessions_bp,
    crm_bp,
    integrations_bp,
    security_controls_bp,
    admin_users_bp,
    admin_students_bp,
    crm_sync_bp,
    audit_log_bp,
    attendance_bp,
    progress_bp,
    completion_bp,
    certificates_bp,
    batch_allocations_bp,
    curriculum_bp,
    enrolments_bp,
    my_courses_bp,
    assignments_bp,
    questions_bp,
    tests_bp,
    results_bp,
]


def register_blueprints(app: Flask) -> None:
    prefix = app.config["API_PREFIX"]
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=prefix + (blueprint.url_prefix or ""))


# Phase 2 / S2 content & recordings
from routes.access_extensions import access_extensions_bp  # noqa: E402
from routes.content import content_bp  # noqa: E402
from routes.recordings import recording_exceptions_bp, recordings_bp  # noqa: E402
from routes.student_library import student_library_bp  # noqa: E402

BLUEPRINTS += [content_bp, recordings_bp, recording_exceptions_bp, access_extensions_bp, student_library_bp]

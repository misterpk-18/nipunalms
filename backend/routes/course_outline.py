"""Course outlines (db/121): everyone who can see a course reads it; Super Admin and Founder / CEO edit it. Code, title, category,
status and tracks are the CRM's (`CourseUpserted`) and have no edit endpoint."""
from flask import Blueprint

from controllers import course_outline as controller
from routes.decorators import fresh_auth, login_required, require_roles
from services.context import ADMIN_ROLES

course_outline_bp = Blueprint("course_outline", __name__)
VIEWERS = ("BRANCH_MANAGER", *ADMIN_ROLES)


@course_outline_bp.get("/courses")
@login_required
@require_roles(*VIEWERS)
def list_courses():
    return controller.list_courses()


@course_outline_bp.get("/courses/<int:course_id>/outline")
@login_required
def get_outline(course_id: int):
    return controller.get_outline(course_id)


def _edit(rule: str, method: str):
    """Edits: Super Admin and Founder only, with a recent sign-in (they change what running students learn)."""
    def wrap(fn):
        return getattr(course_outline_bp, method)(rule)(login_required(require_roles(*ADMIN_ROLES)(fresh_auth(fn))))
    return wrap


@_edit("/courses/<int:course_id>/modules", "post")
def add_module(course_id: int):
    return controller.add_module(course_id)


@_edit("/course-modules/<int:module_id>", "patch")
def update_module(module_id: int):
    return controller.update_module(module_id)


@_edit("/course-modules/<int:module_id>", "delete")
def delete_module(module_id: int):
    return controller.delete_module(module_id)


@_edit("/course-modules/<int:module_id>/topics", "post")
def add_topic(module_id: int):
    return controller.add_topic(module_id)


@_edit("/course-topics/<int:topic_id>", "patch")
def update_topic(topic_id: int):
    return controller.update_topic(topic_id)


@_edit("/course-topics/<int:topic_id>", "delete")
def delete_topic(topic_id: int):
    return controller.delete_topic(topic_id)


@_edit("/courses/<int:course_id>/hours-verification", "post")
def verify_hours(course_id: int):
    return controller.verify_hours(course_id)


@_edit("/courses/<int:course_id>/completion-profile", "put")
def set_completion_profile(course_id: int):
    return controller.set_completion_profile(course_id)


@_edit("/courses/<int:course_id>/assessment-requirements", "post")
def add_requirement(course_id: int):
    return controller.add_requirement(course_id)


@_edit("/assessment-requirements/<int:requirement_id>", "delete")
def delete_requirement(requirement_id: int):
    return controller.delete_requirement(requirement_id)


@_edit("/courses/<int:course_id>/track-pins", "put")
def pin_track(course_id: int):
    return controller.pin_track(course_id)


@_edit("/course-components/<int:component_id>/equivalence", "post")
def review_equivalence(component_id: int):
    return controller.review_equivalence(component_id)


@course_outline_bp.get("/course-library")
@login_required
@require_roles(*VIEWERS)
def list_library():
    return controller.list_library()


@_edit("/course-modules/<int:module_id>/library", "post")
def save_to_library(module_id: int):
    return controller.save_to_library(module_id)


@_edit("/course-library/<int:library_module_id>/versions", "post")
def propose_library_version(library_module_id: int):
    return controller.propose_library_version(library_module_id)


@_edit("/courses/<int:course_id>/library-modules", "post")
def insert_library_module(course_id: int):
    return controller.insert_library_module(course_id)

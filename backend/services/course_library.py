"""The reusable module library (Module 14 §9), now used from the course outline. A library module has a stable code and explicit
versions. Saving a course module to the library, or changing a library module, creates a version that is usable at once (there is no
approval step). Inserting a library version into a course copies it as a new module that keeps the reference, so courses already
using an earlier version stay on it. Reuse copies content only: it reveals no learners, submissions, results or recordings."""
from datetime import datetime, timezone

from sqlalchemy import func, select

from config.database import db
from models import CourseModule, CourseTopic, LibraryModule, LibraryModuleVersion
from repositories import catalog as catalog_repo
from repositories.common import paginate
from services import audit
from services.context import current_user
from services.course_outline import TOPIC_FIELDS, _changed, _live_module, _require_editor, get_course
from services.errors import NotFound, ValidationError


def _snapshot(module: CourseModule) -> dict:
    return {"title": module.title, "title_te": module.title_te,
            "topics": [{f: (str(getattr(t, f)) if f == "weight" and t.weight is not None else getattr(t, f)) for f in TOPIC_FIELDS}
                       for t in module.topics]}


def _new_version(library_id: int, number: int, module: CourseModule, note: str) -> LibraryModuleVersion:
    me = current_user().user_id
    version = LibraryModuleVersion(library_module_id=library_id, version_no=number, content=_snapshot(module), change_note=note,
                                   proposed_by=me, status="Approved", decided_by=me, decided_at=datetime.now(timezone.utc))
    db.session.add(version)
    db.session.flush()
    return version


def save_to_library(module_id: int) -> LibraryModule:
    """Save a course module as a new reusable library module (version 1)."""
    _require_editor()
    _, module = _live_module(module_id)
    number = (db.session.execute(select(func.count()).select_from(LibraryModule)).scalar_one() or 0) + 1
    library = LibraryModule(module_code=f"LIB-{number:04d}", title=module.title, created_by=current_user().user_id)
    db.session.add(library)
    db.session.flush()
    _new_version(library.library_module_id, 1, module, f"From {module.course.title}")
    db.session.refresh(library)
    audit.record("LIBRARY_MODULE_SAVED", "library_module", library.library_module_id, new={"code": library.module_code})
    return library


def propose_version(library_module_id: int, module_id: int, change_note: str) -> LibraryModuleVersion:
    """A changed library module is a new version; courses keep the version they copied."""
    _require_editor()
    library = db.session.get(LibraryModule, library_module_id)
    if library is None:
        raise NotFound("Library module not found")
    _, module = _live_module(module_id)
    version = _new_version(library.library_module_id, library.versions[-1].version_no + 1, module, change_note)
    audit.record("LIBRARY_VERSION_SAVED", "library_module", library.library_module_id, new={"version_no": version.version_no},
                 reason=change_note)
    return version


def insert_into(course_id: int, library_version_id: int, component_id: int | None = None) -> CourseModule:
    """Copy a library version into the course outline as a new module that references it."""
    _require_editor()
    course = get_course(course_id, lock=True)
    source = db.session.get(LibraryModuleVersion, library_version_id)
    if source is None or source.status != "Approved":
        raise ValidationError("Invalid request data", {"library_version_id": ["A library version"]})
    if component_id is not None and (catalog_repo.get_component(component_id) is None
                                     or catalog_repo.get_component(component_id).parent_course_id != course.course_id):
        raise ValidationError("Invalid request data", {"component_id": ["Not a track of this course"]})
    module = CourseModule(course_id=course.course_id, component_id=component_id, title=source.content["title"],
                          title_te=source.content.get("title_te"), sort_order=catalog_repo.next_module_order(course.course_id, component_id),
                          library_version_id=source.library_version_id)
    db.session.add(module)
    db.session.flush()
    for order, topic in enumerate(source.content["topics"], 1):
        db.session.add(CourseTopic(module_id=module.module_id, sort_order=order, **{f: topic.get(f) for f in TOPIC_FIELDS}))
    if course.hours_verified_at is not None:
        course.hours_verified_by = course.hours_verified_at = None
    db.session.flush()
    db.session.refresh(module)
    _changed(course, f"added the library module \"{module.title}\"", module_id=module.module_id,
             library_version_id=source.library_version_id)
    return module


def list_library(page: int, per_page: int):
    return paginate(select(LibraryModule).order_by(LibraryModule.module_code), page, per_page)

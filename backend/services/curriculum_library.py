"""Reusable academic material (Module 14 §9). A library module has a stable code and explicit versions. Saving a curriculum
module to the library, or changing a library module, proposes a version that another Branch Manager or the Super Admin
approves. A draft curriculum copies an approved library version and keeps the reference, so curricula already using an
earlier version stay on it. Reuse copies content only: it reveals no learners, submissions, results or recordings."""
from datetime import datetime, timezone

from sqlalchemy import func, select

from config.database import db
from models import CurriculumModule, CurriculumTopic, LibraryModule, LibraryModuleVersion
from repositories import catalog as catalog_repo
from repositories.common import paginate
from services import approvals, audit
from services.context import current_user
from services.curriculum import TOPIC_FIELDS, _editable, _version
from services.errors import BusinessRule, NotFound, ValidationError

EDITORS = ("BRANCH_MANAGER", "SUPER_ADMIN")


def _snapshot(module: CurriculumModule) -> dict:
    return {"title": module.title, "title_te": module.title_te,
            "topics": [{f: (str(getattr(t, f)) if f == "weight" and t.weight is not None else getattr(t, f)) for f in TOPIC_FIELDS}
                       for t in module.topics]}


def _module(module_id: int) -> CurriculumModule:
    module = catalog_repo.get_module(module_id)
    if module is None:
        raise NotFound("Module not found")
    return module


def save_to_library(module_id: int) -> LibraryModule:
    """Propose a curriculum module as a new reusable library module (version 1)."""
    module = _module(module_id)
    number = (db.session.execute(select(func.count()).select_from(LibraryModule)).scalar_one() or 0) + 1
    library = LibraryModule(module_code=f"LIB-{number:04d}", title=module.title, created_by=current_user().user_id)
    db.session.add(library)
    db.session.flush()
    db.session.add(LibraryModuleVersion(library_module_id=library.library_module_id, version_no=1, content=_snapshot(module),
                                        change_note=f"From {module.version.version_label}", proposed_by=current_user().user_id))
    db.session.flush()
    db.session.refresh(library)
    audit.record("LIBRARY_MODULE_PROPOSED", "library_module", library.library_module_id, new={"code": library.module_code})
    return library


def propose_version(library_module_id: int, module_id: int, change_note: str) -> LibraryModuleVersion:
    """A changed library module is a new proposed version; curricula keep the version they copied."""
    library = db.session.get(LibraryModule, library_module_id)
    if library is None:
        raise NotFound("Library module not found")
    if any(v.status == "Pending" for v in library.versions):
        raise BusinessRule("A version of this library module is already waiting for review")
    version = LibraryModuleVersion(library_module_id=library.library_module_id, version_no=library.versions[-1].version_no + 1,
                                   content=_snapshot(_module(module_id)), change_note=change_note, proposed_by=current_user().user_id)
    db.session.add(version)
    db.session.flush()
    audit.record("LIBRARY_VERSION_PROPOSED", "library_module", library.library_module_id, new={"version_no": version.version_no},
                 reason=change_note)
    return version


def decide_version(library_version_id: int, decision: str) -> LibraryModuleVersion:
    version = db.session.get(LibraryModuleVersion, library_version_id)
    if version is None:
        raise NotFound("Library version not found")
    if version.status != "Pending":
        raise BusinessRule(f"This version is already {version.status}")
    approvals.require_independent(version.proposed_by, message="An independent reviewer must decide: not the person who proposed it",
                                  requester=version.proposed_by)
    version.status, version.decided_by, version.decided_at = decision, current_user().user_id, datetime.now(timezone.utc)
    db.session.flush()
    audit.record(f"LIBRARY_VERSION_{decision.upper()}", "library_module", version.library_module_id, new={"version_no": version.version_no})
    return version


def insert_into(curriculum_version_id: int, library_version_id: int) -> CurriculumModule:
    """Copy an approved library version into a draft curriculum as a new module that references it."""
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    source = db.session.get(LibraryModuleVersion, library_version_id)
    if source is None or source.status != "Approved":
        raise ValidationError("Invalid request data", {"library_version_id": ["An approved library version"]})
    module = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=source.content["title"],
                              title_te=source.content.get("title_te"), sort_order=catalog_repo.next_module_order(version.curriculum_version_id),
                              library_version_id=source.library_version_id)
    db.session.add(module)
    db.session.flush()
    for order, topic in enumerate(source.content["topics"], 1):
        db.session.add(CurriculumTopic(module_id=module.module_id, sort_order=order, **{f: topic.get(f) for f in TOPIC_FIELDS}))
    if version.hours_verified_at is not None:
        version.hours_verified_by = version.hours_verified_at = None
    db.session.flush()
    db.session.refresh(module)
    return module


def list_library(page: int, per_page: int):
    return paginate(select(LibraryModule).order_by(LibraryModule.module_code), page, per_page)

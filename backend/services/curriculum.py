"""Curriculum management: versions per course (or per combo track), their modules and topics, and the review path.

Draft -> Under Review -> Approved -> Active -> Retired. Content is editable only in a Draft; once submitted a version is a snapshot
that enrolments and batches point at (the database refuses edits to published content). Whoever submits a version cannot approve
it (independent review). Activating a version retires the previous Active one for that course / track, then maps every enrolment
and batch that was waiting in *Curriculum Mapping Pending* and tells the branch that they can now be allocated.
Enrolments and batches already on the older version stay on it.
"""
from dataclasses import dataclass

from config.database import db
from models import Batch, Course, CourseComponent, CurriculumEvent, CurriculumModule, CurriculumTopic, CurriculumVersion, Enrolment
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import users as users_repo
from services import audit, batches as batches_service, delivery_notices
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, NotFound, ValidationError

BLOCKED_PREFIX = "Curriculum Mapping Pending"


@dataclass
class VersionDetail:
    version: CurriculumVersion
    course: Course
    component: CourseComponent | None
    counts: dict[str, int]
    usage: dict[str, int]
    events: list
    blockers: list[str]


@dataclass
class OverviewRow:
    course: Course
    component: CourseComponent | None
    active: CurriculumVersion | None
    latest: CurriculumVersion | None
    readiness: str
    pending_enrolments: int
    borrowed_from: Course | None  # an included booster without its own track version reuses the booster course's Active version


# ---------------------------------------------------------------- reads

def _version(curriculum_version_id: int, *, lock: bool = False) -> CurriculumVersion:
    version = (catalog_repo.get_version_for_update(curriculum_version_id) if lock
               else catalog_repo.get_curriculum_version(curriculum_version_id))
    if version is None:
        raise NotFound("Curriculum version not found")
    return version


def _blockers(version: CurriculumVersion, counts: dict[str, int]) -> list[str]:
    """Why a draft cannot be submitted yet."""
    problems = []
    if not counts["modules"]:
        problems.append("Add at least one module")
    empty = [m.title for m in version.modules if not m.topics]
    if empty:
        problems.append("Modules without topics: " + ", ".join(empty))
    if counts["modules"] and not counts["required_topics"]:
        problems.append("Mark at least one topic as required")
    return problems


def get_version_detail(curriculum_version_id: int) -> VersionDetail:
    version = _version(curriculum_version_id)
    counts = catalog_repo.content_counts([version.curriculum_version_id]).get(version.curriculum_version_id,
                                                                               {"modules": 0, "topics": 0, "required_topics": 0})
    return VersionDetail(
        version=version, course=catalog_repo.get_course(version.course_id),
        component=catalog_repo.get_component(version.component_id) if version.component_id else None,
        counts=counts, usage=catalog_repo.usage_counts([version.curriculum_version_id])[version.curriculum_version_id],
        events=catalog_repo.events_of(version.curriculum_version_id),
        blockers=_blockers(version, counts) if version.status == "Draft" else [],
    )


def list_versions(filters: dict) -> list[VersionDetail]:
    versions = catalog_repo.list_versions(filters)
    ids = [v.curriculum_version_id for v in versions]
    counts, usage = catalog_repo.content_counts(ids), catalog_repo.usage_counts(ids)
    empty = {"modules": 0, "topics": 0, "required_topics": 0}
    courses = {c.course_id: c for c in catalog_repo.list_courses()}
    components = {c.component_id: c for course in courses.values() for c in course.components}
    return [VersionDetail(v, courses[v.course_id], components.get(v.component_id), counts.get(v.curriculum_version_id, empty),
                          usage[v.curriculum_version_id], [], []) for v in versions]


def overview() -> list[OverviewRow]:
    """One row per course (and per track of a combo): the Active version, the newest one in progress, and delivery readiness."""
    versions = catalog_repo.list_versions({})
    pending = catalog_repo.pending_enrolment_counts()
    by_slot: dict[tuple[int, int | None], list[CurriculumVersion]] = {}
    for version in versions:
        by_slot.setdefault((version.course_id, version.component_id), []).append(version)

    def pick(slot) -> tuple[CurriculumVersion | None, CurriculumVersion | None]:
        slot_versions = by_slot.get(slot, [])
        active = next((v for v in slot_versions if v.status == "Active"), None)
        in_progress = next((v for v in slot_versions if v.status in ("Draft", "Under Review", "Approved")), None)
        return active, in_progress or active

    rows = []
    for course in catalog_repo.list_courses():
        slots: list[tuple[CourseComponent | None, Course | None]] = [(None, None)]
        slots += [(c, c.component_course) for c in course.components]
        for component, booster in slots:
            active, latest = pick((course.course_id, component.component_id if component else None))
            borrowed = None
            if active is None and booster is not None:
                active, booster_latest = pick((booster.course_id, None))
                borrowed, latest = (booster, latest or booster_latest) if active else (None, latest)
            rows.append(OverviewRow(course, component, active, latest, "Ready" if active else BLOCKED_PREFIX,
                                    pending.get(course.course_id, 0) if component is None else 0, borrowed))
    return rows


# ---------------------------------------------------------------- create / edit (Draft only)

def _editable(version: CurriculumVersion) -> None:
    if version.status != "Draft":
        raise BusinessRule(f"Curriculum version {version.version_label} is {version.status} and can no longer be edited; create a new draft version")


def create_version(data: dict) -> CurriculumVersion:
    """A new Draft for a course (or one track of a combo), empty or copied from an existing version of the same slot."""
    course = catalog_repo.get_course(data["course_id"])
    if course is None:
        raise ValidationError("Unknown course", {"course_id": ["Not a course"]})
    component_id = data.get("component_id")
    if component_id is not None and component_id not in {c.component_id for c in course.components}:
        raise ValidationError("Unknown track", {"component_id": ["Not a track of this course"]})
    in_progress = [v for v in catalog_repo.list_versions({"course_id": course.course_id})
                   if v.component_id == component_id and v.status in ("Draft", "Under Review")]
    if in_progress:
        raise Conflict(f"{in_progress[0].version_label} is already {in_progress[0].status}; finish or return it before starting another draft")
    if any(v.version_label == data["version_label"] and v.component_id == component_id for v in catalog_repo.list_versions({"course_id": course.course_id})):
        raise Conflict("A version with this label already exists", {"version_label": ["Already used for this course"]})

    version = CurriculumVersion(course_id=course.course_id, component_id=component_id, version_label=data["version_label"], status="Draft")
    db.session.add(version)
    db.session.flush()
    source = None
    if data.get("copy_from_version_id"):
        source = _version(data["copy_from_version_id"])
        if (source.course_id, source.component_id) != (course.course_id, component_id):
            raise ValidationError("Cannot copy", {"copy_from_version_id": ["Not a version of the same course / track"]})
        for module in source.modules:
            copy = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=module.title, title_te=module.title_te,
                                    sort_order=module.sort_order)
            db.session.add(copy)
            db.session.flush()
            for topic in module.topics:
                db.session.add(CurriculumTopic(module_id=copy.module_id, title=topic.title, title_te=topic.title_te, sort_order=topic.sort_order,
                                               is_required=topic.is_required))
    catalog_repo.add_event(version, "Created", None, "Draft", actor_id(), f"Copied from {source.version_label}" if source else None)
    audit.record("CURRICULUM_CREATED", "curriculum_version", version.curriculum_version_id,
                 new={"course_id": course.course_id, "component_id": component_id, "version_label": version.version_label,
                      "copied_from": source.curriculum_version_id if source else None})
    db.session.flush()
    db.session.refresh(version)
    return version


def update_version(curriculum_version_id: int, version_label: str) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    if any(v.version_label == version_label and v.component_id == version.component_id and v.curriculum_version_id != version.curriculum_version_id
           for v in catalog_repo.list_versions({"course_id": version.course_id})):
        raise Conflict("A version with this label already exists", {"version_label": ["Already used for this course"]})
    old = version.version_label
    version.version_label = version_label
    db.session.flush()
    audit.record("CURRICULUM_UPDATED", "curriculum_version", version.curriculum_version_id, old={"version_label": old}, new={"version_label": version_label})
    return version


def delete_version(curriculum_version_id: int) -> None:
    """Discard a Draft nobody uses."""
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    audit.record("CURRICULUM_DELETED", "curriculum_version", version.curriculum_version_id,
                 old={"version_label": version.version_label, "course_id": version.course_id})
    db.session.delete(version)
    db.session.flush()


def _resequence(items: list, moved, position: int | None, attribute: str = "sort_order") -> None:
    """Put `moved` at 1-based `position` (last if None) and renumber 1..n. Two passes because (parent, sort_order) is unique."""
    ordered = [i for i in items if i is not moved]
    ordered.insert(len(ordered) if position is None else max(0, min(position - 1, len(ordered))), moved)
    for offset, item in enumerate(ordered):
        setattr(item, attribute, 10000 + offset)
    db.session.flush()
    for number, item in enumerate(ordered, 1):
        setattr(item, attribute, number)
    db.session.flush()


def _draft_version_of_module(module_id: int) -> tuple[CurriculumVersion, CurriculumModule]:
    module = catalog_repo.get_module(module_id)
    if module is None:
        raise NotFound("Module not found")
    version = _version(module.curriculum_version_id, lock=True)
    _editable(version)
    return version, module


def add_module(curriculum_version_id: int, title: str, title_te: str | None, position: int | None) -> CurriculumModule:
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    module = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=title, title_te=title_te,
                              sort_order=catalog_repo.next_module_order(version.curriculum_version_id))
    db.session.add(module)
    db.session.flush()
    if position is not None:
        db.session.refresh(version)
        _resequence(list(version.modules), module, position)
    return module


def update_module(module_id: int, data: dict) -> CurriculumModule:
    version, module = _draft_version_of_module(module_id)
    for name in ("title", "title_te"):
        if name in data:
            setattr(module, name, data[name])
    if "position" in data:
        db.session.refresh(version)
        _resequence(list(version.modules), module, data["position"])
    db.session.flush()
    return module


def delete_module(module_id: int) -> None:
    version, module = _draft_version_of_module(module_id)
    db.session.delete(module)
    db.session.flush()
    db.session.refresh(version)
    remaining = list(version.modules)
    for number, item in enumerate(remaining, 1):
        item.sort_order = number
    db.session.flush()


def add_topic(module_id: int, data: dict) -> CurriculumTopic:
    _, module = _draft_version_of_module(module_id)
    topic = CurriculumTopic(module_id=module.module_id, title=data["title"], title_te=data.get("title_te"),
                            is_required=data.get("is_required", True), sort_order=catalog_repo.next_topic_order(module.module_id))
    db.session.add(topic)
    db.session.flush()
    if data.get("position") is not None:
        db.session.refresh(module)
        _resequence(list(module.topics), topic, data["position"])
    return topic


def _draft_topic(topic_id: int) -> CurriculumTopic:
    topic = catalog_repo.get_topic(topic_id)
    if topic is None:
        raise NotFound("Topic not found")
    _draft_version_of_module(topic.module_id)
    return topic


def update_topic(topic_id: int, data: dict) -> CurriculumTopic:
    topic = _draft_topic(topic_id)
    for name in ("title", "title_te", "is_required"):
        if name in data:
            setattr(topic, name, data[name])
    if "position" in data:
        db.session.refresh(topic.module)
        _resequence(list(topic.module.topics), topic, data["position"])
    db.session.flush()
    return topic


def delete_topic(topic_id: int) -> None:
    topic = _draft_topic(topic_id)
    module = topic.module
    db.session.delete(topic)
    db.session.flush()
    db.session.refresh(module)
    for number, item in enumerate(module.topics, 1):
        item.sort_order = number
    db.session.flush()


# ---------------------------------------------------------------- review path

def _step(version: CurriculumVersion, action: str, to_status: str, note: str | None = None) -> CurriculumEvent:
    """Move the version to a new status, log the step in its review trail and in the audit log."""
    old = version.status
    version.status = to_status
    db.session.flush()
    event = catalog_repo.add_event(version, action, old, to_status, actor_id(), note)
    db.session.flush()
    audit.record(f"CURRICULUM_{action.upper()}", "curriculum_version", version.curriculum_version_id, old={"status": old},
                 new={"status": to_status}, reason=note)
    return event


def submit(curriculum_version_id: int) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Draft":
        raise BusinessRule(f"Only a Draft can be submitted; {version.version_label} is {version.status}")
    counts = catalog_repo.content_counts([version.curriculum_version_id]).get(version.curriculum_version_id, {"modules": 0, "topics": 0, "required_topics": 0})
    problems = _blockers(version, counts)
    if problems:
        raise BusinessRule("The draft is not ready for review: " + "; ".join(problems), {"blockers": problems})
    event = _step(version, "Submitted", "Under Review")
    reviewers = [u for u in _approvers() if u != actor_id()]
    delivery_notices.notify_users(reviewers, title=f"Curriculum awaiting review: {version.version_label}", category="Curriculum",
                                  body=f"{catalog_repo.get_course(version.course_id).course_code} — submitted by {current_user().full_name}",
                                  event_key=f"curriculum-submitted-{event.event_id}",
                                  link="/academic/curriculum", branch_id=None, action_required=True)
    return version


def _approvers() -> list[int]:
    return list(dict.fromkeys(users_repo.user_ids_with_role("SUPER_ADMIN", None) + users_repo.user_ids_with_role("ACADEMIC_COORDINATOR", None)))


def return_to_draft(curriculum_version_id: int, reason: str) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Under Review":
        raise BusinessRule(f"Only a version Under Review can be returned; {version.version_label} is {version.status}")
    submitted = catalog_repo.last_event(version.curriculum_version_id, "Submitted")
    event = _step(version, "Returned", "Draft", reason)
    if submitted is not None and submitted.actor_user_id:
        delivery_notices.notify_users([submitted.actor_user_id], title=f"Curriculum returned: {version.version_label}", category="Curriculum", body=reason,
                                      event_key=f"curriculum-returned-{event.event_id}",
                                      link="/academic/curriculum", branch_id=None)
    return version


def approve(curriculum_version_id: int) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Under Review":
        raise BusinessRule(f"Only a version Under Review can be approved; {version.version_label} is {version.status}")
    submitted = catalog_repo.last_event(version.curriculum_version_id, "Submitted")
    if submitted is not None and submitted.actor_user_id == actor_id():
        raise BusinessRule("The person who submitted a curriculum version cannot approve it; ask another reviewer")
    version.approved_by, version.approved_at = actor_id(), db.func.now()
    _step(version, "Approved", "Approved")
    db.session.refresh(version)
    return version


def activate(curriculum_version_id: int) -> tuple[CurriculumVersion, dict]:
    """Make an Approved version the Active one (retiring the previous Active version) and map everything that was waiting for it."""
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Approved":
        raise BusinessRule(f"Only an Approved version can be activated; {version.version_label} is {version.status}")
    previous_id = catalog_repo.active_curriculum_version_id(version.course_id, version.component_id)
    if previous_id is not None:
        previous = _version(previous_id, lock=True)
        _step(previous, "Retired", "Retired", f"Replaced by {version.version_label}")
    _step(version, "Activated", "Active")
    released = _release_mapping(version)
    audit.record("CURRICULUM_MAPPING_RELEASED", "curriculum_version", version.curriculum_version_id, new=released)
    return version, released


def retire(curriculum_version_id: int, reason: str | None) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status not in ("Approved", "Active"):
        raise BusinessRule(f"Only an Approved or Active version can be retired; {version.version_label} is {version.status}")
    _step(version, "Retired", "Retired", reason)
    return version


# ---------------------------------------------------------------- what activation releases

def _release_mapping(version: CurriculumVersion) -> dict:
    """Give the new Active version to every enrolment, combo track and batch that had none, and re-evaluate enrolments in
    Curriculum Mapping Pending: fully mapped ones go to Allocation Pending (or straight back to Allocated if a seat was reserved)."""
    version_id = version.curriculum_version_id
    mapped_batches = 0
    if version.component_id is None:
        for enrolment in catalog_repo.pending_enrolments(version.course_id):
            if enrolment.course_id == version.course_id and enrolment.curriculum_version_id is None:
                enrolment.curriculum_version_id = version_id
            for track in enrolment.tracks:
                own = catalog_repo.active_curriculum_version_id(enrolment.course_id, track.component_id)
                if track.curriculum_version_id is None and own is None and track.component.component_course_id == version.course_id:
                    track.curriculum_version_id = version_id  # an included booster uses the booster course's own version
        for batch in catalog_repo.batches_without_version(version.course_id):
            _map_batch(batch, version)
            mapped_batches += 1
    else:
        for enrolment in catalog_repo.pending_enrolments(version.course_id):
            for track in enrolment.tracks:
                if track.component_id == version.component_id and track.curriculum_version_id is None:
                    track.curriculum_version_id = version_id
    db.session.flush()

    released: list[Enrolment] = []
    for enrolment in catalog_repo.pending_enrolments(version.course_id):
        if enrolment.status == "Curriculum Mapping Pending" and enrolment.curriculum_version_id is not None \
                and all(t.curriculum_version_id for t in enrolment.tracks):
            enrolment.status = ("Allocated — awaiting first regular class" if batches_repo.active_allocation(enrolment.enrolment_id)
                                else "Allocation Pending")
            released.append(enrolment)
    db.session.flush()

    by_branch: dict[int, list[Enrolment]] = {}
    for enrolment in released:
        by_branch.setdefault(enrolment.service_branch_id, []).append(enrolment)
        delivery_notices.notify_student(enrolment.student_id, title=f"Your curriculum is ready: {enrolment.course.title}",
                                        body="Your course content is mapped. Your Academic Coordinator will allocate you to a batch.",
                                        event_key=f"curriculum-released-{enrolment.enrolment_id}-{version_id}", link="/my-courses",
                                        branch_id=enrolment.service_branch_id)
    for branch_id, group in by_branch.items():
        delivery_notices.notify_branch_managers(branch_id, title=f"{len(group)} enrolment(s) ready for batch allocation", category="Enrolment",
                                                body=f"{version.version_label} was activated for {group[0].course.course_code}.",
                                                event_key=f"curriculum-released-branch-{branch_id}-{version_id}", link="/academic/batches",
                                                action_required=True)
    return {"enrolments_released": len(released), "batches_mapped": mapped_batches}


def _map_batch(batch: Batch, version: CurriculumVersion) -> None:
    """A batch that waited for a curriculum gets the version; if that was the only thing blocking it, it becomes Ready."""
    batch.curriculum_version_id = version.curriculum_version_id
    db.session.flush()
    batches_repo.add_event(batch.batch_id, "Curriculum mapped", to_value=version.version_label, actor_user_id=actor_id())
    if batch.readiness == "Blocked" and (batch.readiness_reason or "").startswith(BLOCKED_PREFIX):
        db.session.refresh(batch)
        allocated = batches_repo.allocated_counts([batch.batch_id]).get(batch.batch_id, 0)
        suggestion = batches_service.suggested_readiness(batch, batches_service.readiness_checks(batch, allocated))
        batches_service.apply_readiness(batch, suggestion["readiness"], suggestion["readiness_reason"], suggestion["recovery_owner"],
                                        note=f"{version.version_label} activated")


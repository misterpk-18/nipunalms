"""Curriculum management: versions per course (or per combo track), their modules and topics, and the review path.

Draft -> Under Review -> Approved -> Active -> Retired. Content is editable only in a Draft; once submitted a version is a snapshot
that enrolments and batches point at (the database refuses edits to published content). Branch Managers draft, submit and
review; the Founder / CEO or Super Admin approve, activate and retire (Module 14 §5), and whoever submitted a version cannot
approve it (independent review). Activating a version retires the previous Active one for that course / track, then gives it
to every batch of the course that had none and to the enrolments still without one. Nothing waits for a curriculum: a student
can be allocated without one and follows the version of their batch. Enrolments and batches already on the older version stay on it.

Module 14: each topic has an outcome, a Required / Recommended / Optional class, estimated minutes, a progress weight,
evidence and (only where necessary) dependencies; a version has verified hours, a completion profile and its required
assessments; a combo's parent version pins its track and booster versions. A version is submitted only when its required
learning is fully described — missing rules never default to pass.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from config.database import db
from models import (
    AssessmentRequirement, Batch, Course, CourseComponent, CurriculumEvent, CurriculumModule, CurriculumTopic, CurriculumVersion,
    Enrolment, VersionComponent,
)
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import users as users_repo
from services import approvals, audit, batches as batches_service, delivery_notices
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, NotFound, ValidationError

BLOCKED_PREFIX = "Curriculum Mapping Pending"  # readiness reason of a batch blocked before db/105; unblocked when it gets a version


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
    waiting_batches: int
    borrowed_from: Course | None  # an included booster without its own track version reuses the booster course's Active version


# ---------------------------------------------------------------- reads

def _version(curriculum_version_id: int, *, lock: bool = False) -> CurriculumVersion:
    version = (catalog_repo.get_version_for_update(curriculum_version_id) if lock
               else catalog_repo.get_curriculum_version(curriculum_version_id))
    if version is None:
        raise NotFound("Curriculum version not found")
    return version


TOPIC_FIELDS = ("title", "title_te", "topic_class", "outcome", "instructional_minutes", "independent_minutes", "weight", "evidence",
                "activities")
PROFILE_KEYS = ("attendance_minimum_pct", "pass_mark_pct", "recovery_rule", "reassessment_rule")


def is_combo_parent(version: CurriculumVersion) -> bool:
    return version.component_id is None and catalog_repo.get_course(version.course_id).is_combo


def totals(version: CurriculumVersion) -> dict:
    """Module 14 §6: standard instructional, independent learning and total effort, in minutes. A combo parent adds its pinned
    tracks, with the included booster shown separately; topics without an estimate are counted, never guessed."""
    topics = [t for m in version.modules for t in m.topics]
    instructional = sum(t.instructional_minutes or 0 for t in topics)
    independent = sum(t.independent_minutes or 0 for t in topics)
    unestimated = sum(1 for t in topics if t.instructional_minutes is None)
    booster = None
    if is_combo_parent(version):
        for pin in catalog_repo.version_components(version.curriculum_version_id):
            part = totals(pin.component_version)
            component = catalog_repo.get_component(pin.component_id)
            if component.role == "Included booster":
                booster = {"track_code": component.track_code, **{k: part[k] for k in ("instructional_minutes", "independent_minutes", "total_minutes")}}
            instructional += part["instructional_minutes"]
            independent += part["independent_minutes"]
            unestimated += part["unestimated_topics"]
    return {"instructional_minutes": instructional, "independent_minutes": independent, "total_minutes": instructional + independent,
            "unestimated_topics": unestimated, "hours_verified": version.hours_verified_at is not None,
            "hours_verified_at": version.hours_verified_at, "booster": booster}


def _blockers(version: CurriculumVersion, counts: dict[str, int]) -> list[str]:
    """Why a draft cannot be submitted yet (Module 14 §5: verified outcomes, hours, evidence and weights, and a completion
    profile; a combo parent pins every track and booster)."""
    problems = []
    combo_parent = is_combo_parent(version)
    if not counts["modules"] and not combo_parent:
        problems.append("Add at least one module")
    empty = [m.title for m in version.modules if not m.topics]
    if empty:
        problems.append("Modules without topics: " + ", ".join(empty))
    if counts["modules"] and not counts["required_topics"]:
        problems.append("Mark at least one topic as required")
    required = [t for m in version.modules for t in m.topics if t.topic_class == "Required"]
    for label, missing in (("an outcome", lambda t: not (t.outcome or "").strip()),
                           ("estimated instructional minutes", lambda t: t.instructional_minutes is None),
                           ("a progress weight", lambda t: not t.weight),
                           ("evidence of completion", lambda t: not (t.evidence or "").strip())):
        names = [t.title for t in required if missing(t)]
        if names:
            problems.append(f"Required topics without {label}: " + ", ".join(names[:5]) + (" …" if len(names) > 5 else ""))
    if counts["modules"] and version.hours_verified_at is None:
        problems.append("Verify the standard instructional hours")
    profile = version.completion_profile or {}
    if not all(profile.get(key) not in (None, "") for key in PROFILE_KEYS):
        problems.append("Complete the completion profile (attendance minimum, pass mark, recovery and reassessment rules)")
    if combo_parent:
        course = catalog_repo.get_course(version.course_id)
        pinned = {p.component_id for p in catalog_repo.version_components(version.curriculum_version_id)}
        unpinned = [c.track_code for c in course.components if c.component_id not in pinned]
        if unpinned:
            problems.append("Pin a version for every track and the booster: " + ", ".join(unpinned))
    return problems


def _incomplete_topics(version: CurriculumVersion) -> list[dict]:
    """Required topics that still lack what a submission needs, with the plain names of what is missing."""
    checks = (("outcome", lambda t: not (t.outcome or "").strip()), ("estimated minutes", lambda t: t.instructional_minutes is None),
              ("progress weight", lambda t: not t.weight), ("evidence of completion", lambda t: not (t.evidence or "").strip()))
    rows = []
    for module in version.modules:
        for topic in module.topics:
            if topic.topic_class != "Required":
                continue
            missing = [label for label, test in checks if test(topic)]
            if missing:
                rows.append({"topic_id": topic.topic_id, "module_id": module.module_id, "title": topic.title, "module_title": module.title,
                             "missing": missing})
    return rows


def checklist(version: CurriculumVersion, counts: dict[str, int]) -> dict:
    """The submit checklist of a draft, in the order a person works through it: modules, topic details, hours, completion rules,
    required assessments, then submit. Incomplete topics are listed by name so the screen can mark them."""
    combo_parent = is_combo_parent(version)
    empty_modules = [m.title for m in version.modules if not m.topics]
    incomplete = _incomplete_topics(version)
    profile = version.completion_profile or {}
    profile_missing = [key for key in PROFILE_KEYS if profile.get(key) in (None, "")]
    requirements = catalog_repo.assessment_requirements(version.curriculum_version_id)
    steps = [
        {"key": "modules", "label": "Modules", "required": not combo_parent,
         "done": combo_parent or (counts["modules"] > 0 and not empty_modules),
         "hint": "Add at least one module, each with topics." if not empty_modules else "These modules have no topics yet: " + ", ".join(empty_modules),
         "items": [{"title": t} for t in empty_modules]},
        {"key": "topics", "label": "Topic details", "required": True,
         "done": counts["required_topics"] > 0 and not incomplete,
         "hint": ("Mark at least one topic as required." if not counts["required_topics"]
                  else "Every required topic needs an outcome, estimated minutes, a weight and evidence of completion."),
         "items": incomplete},
        {"key": "hours", "label": "Hours", "required": True, "done": version.hours_verified_at is not None or not counts["modules"],
         "hint": "Check the standard teaching hours from the topic minutes, then confirm them.", "items": []},
        {"key": "rules", "label": "Completion rules", "required": True, "done": not profile_missing,
         "hint": "Set the attendance minimum, pass mark and the recovery and reassessment rules.", "items": []},
        {"key": "assessments", "label": "Required assessments", "required": False, "done": bool(requirements),
         "hint": "List the tests or assignments a student must pass to complete the course (recommended).", "items": []},
    ]
    if combo_parent:
        course = catalog_repo.get_course(version.course_id)
        pinned = {p.component_id for p in catalog_repo.version_components(version.curriculum_version_id)}
        unpinned = [c.track_code for c in course.components if c.component_id not in pinned]
        steps.insert(0, {"key": "tracks", "label": "Tracks and booster", "required": True, "done": not unpinned,
                         "hint": "Pin a version for every track and the booster.", "items": [{"title": t} for t in unpinned]})
    blockers = _blockers(version, counts)
    next_step = next((s["key"] for s in steps if s["required"] and not s["done"]), None)
    return {"steps": steps, "ready": not blockers, "next": next_step}


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


def version_extras(version: CurriculumVersion) -> dict:
    """What the version page shows beyond its modules: totals, profile, required assessments, pins."""
    return {
        "totals": totals(version),
        "completion_profile": version.completion_profile,
        "assessment_requirements": [r.to_dict() for r in catalog_repo.assessment_requirements(version.curriculum_version_id)],
        "components": [{"component_id": p.component_id, "component_version": p.component_version.to_summary()}
                       for p in catalog_repo.version_components(version.curriculum_version_id)],
    }


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
    waiting = catalog_repo.batch_counts_without_version()
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
            if active is None and booster is not None and component.equivalence_reviewed_at is not None:
                active, booster_latest = pick((booster.course_id, None))
                borrowed, latest = (booster, latest or booster_latest) if active else (None, latest)
            rows.append(OverviewRow(course, component, active, latest, "Ready" if active else BLOCKED_PREFIX,
                                    waiting.get(course.course_id, 0) if component is None else 0, borrowed))
    return rows


# ---------------------------------------------------------------- create / edit (Draft only)

def _editable(version: CurriculumVersion) -> None:
    if version.status != "Draft":
        raise BusinessRule(f"Curriculum version {version.version_label} is {version.status} and can no longer be edited; create a new draft version")


def next_label(course_id: int, component_id: int | None) -> str:
    """The name of the next draft: the newest version's name with its last number raised (CV 1.3 -> CV 1.4), else "Version 1"."""
    import re
    versions = [v for v in catalog_repo.list_versions({"course_id": course_id}) if v.component_id == component_id]
    taken = {v.version_label for v in versions}
    base = next((v for v in versions if v.status == "Active"), None) or (max(versions, key=lambda v: v.curriculum_version_id) if versions else None)
    if base is None:
        return "Version 1"
    match = re.match(r"^(.*?)(\d+)$", base.version_label.strip())
    if match is None:
        number = 2
        while f"{base.version_label} ({number})" in taken:
            number += 1
        return f"{base.version_label} ({number})"
    prefix, number = match.group(1), int(match.group(2))
    while f"{prefix}{number + 1}" in taken:
        number += 1
    return f"{prefix}{number + 1}"


def active_version_of(course_id: int, component_id: int | None) -> CurriculumVersion | None:
    return next((v for v in catalog_repo.list_versions({"course_id": course_id}) if v.component_id == component_id and v.status == "Active"), None)


def create_version(data: dict) -> CurriculumVersion:
    """A new Draft for a course (or one track of a combo). The name is made for you unless given. It copies the Active version of
    the same slot unless `copy_from_version_id` names another one or `blank` is set (U15)."""
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
    label = (data.get("version_label") or "").strip() or next_label(course.course_id, component_id)
    if any(v.version_label == label and v.component_id == component_id for v in catalog_repo.list_versions({"course_id": course.course_id})):
        raise Conflict("A version with this label already exists", {"version_label": ["Already used for this course"]})
    if not data.get("copy_from_version_id") and not data.get("blank"):
        active = active_version_of(course.course_id, component_id)
        if active is not None:
            data = {**data, "copy_from_version_id": active.curriculum_version_id}

    version = CurriculumVersion(course_id=course.course_id, component_id=component_id, version_label=label, status="Draft")
    db.session.add(version)
    db.session.flush()
    source = None
    if data.get("copy_from_version_id"):
        source = _version(data["copy_from_version_id"])
        if (source.course_id, source.component_id) != (course.course_id, component_id):
            raise ValidationError("Cannot copy", {"copy_from_version_id": ["Not a version of the same course / track"]})
        _copy_content(source, version)
    catalog_repo.add_event(version, "Created", None, "Draft", actor_id(), f"Copied from {source.version_label}" if source else None)
    audit.record("CURRICULUM_CREATED", "curriculum_version", version.curriculum_version_id,
                 new={"course_id": course.course_id, "component_id": component_id, "version_label": version.version_label,
                      "copied_from": source.curriculum_version_id if source else None})
    db.session.flush()
    db.session.refresh(version)
    return version


def _copy_content(source: CurriculumVersion, version: CurriculumVersion) -> None:
    """Modules, topics (with their Module 14 fields and dependencies), required assessments, the completion profile and pins.
    Verified hours are not copied: the new draft's hours are verified again."""
    topic_ids: dict[int, int] = {}
    module_ids: dict[int, int] = {}
    for module in source.modules:
        copy = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=module.title, title_te=module.title_te,
                                sort_order=module.sort_order, library_version_id=module.library_version_id)
        db.session.add(copy)
        db.session.flush()
        module_ids[module.module_id] = copy.module_id
        for topic in module.topics:
            new = CurriculumTopic(module_id=copy.module_id, sort_order=topic.sort_order, **{f: getattr(topic, f) for f in TOPIC_FIELDS})
            db.session.add(new)
            db.session.flush()
            topic_ids[topic.topic_id] = new.topic_id
    for module in source.modules:
        for topic in module.topics:
            for dependency in topic.depends_on:
                catalog_repo.add_dependency(topic_ids[topic.topic_id], topic_ids[dependency.topic_id])
    for req in catalog_repo.assessment_requirements(source.curriculum_version_id):
        db.session.add(AssessmentRequirement(
            curriculum_version_id=version.curriculum_version_id, module_id=module_ids.get(req.module_id), topic_id=topic_ids.get(req.topic_id),
            kind=req.kind, title=req.title, outcome=req.outcome, weight=req.weight, pass_rule=req.pass_rule,
            counts_for_completion=req.counts_for_completion))
    for pin in catalog_repo.version_components(source.curriculum_version_id):
        db.session.add(VersionComponent(curriculum_version_id=version.curriculum_version_id, component_id=pin.component_id,
                                        component_version_id=pin.component_version_id))
    version.completion_profile = source.completion_profile
    db.session.flush()


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


def _topic_values(data: dict) -> dict:
    """The topic fields in a request; the legacy `is_required` flag maps to Required / Optional."""
    values = {f: data[f] for f in TOPIC_FIELDS if f in data}
    if "topic_class" not in values and "is_required" in data:
        values["topic_class"] = "Required" if data["is_required"] else "Optional"
    return values


def add_topic(module_id: int, data: dict) -> CurriculumTopic:
    version, module = _draft_version_of_module(module_id)
    values = {"topic_class": "Required", **_topic_values(data)}
    topic = CurriculumTopic(module_id=module.module_id, sort_order=catalog_repo.next_topic_order(module.module_id), **values)
    db.session.add(topic)
    db.session.flush()
    db.session.refresh(topic)
    _hours_changed(version)
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


def _hours_changed(version: CurriculumVersion) -> None:
    """Changing the teaching plan's minutes needs the hours verified again."""
    if version.hours_verified_at is not None:
        version.hours_verified_by = version.hours_verified_at = None


def update_topic(topic_id: int, data: dict) -> CurriculumTopic:
    topic = _draft_topic(topic_id)
    values = _topic_values(data)
    if {"instructional_minutes", "independent_minutes"} & values.keys():
        _hours_changed(topic.module.version)
    for name, value in values.items():
        setattr(topic, name, value)
    if "depends_on" in data:
        set_dependencies(topic, data["depends_on"])
    if "position" in data:
        db.session.refresh(topic.module)
        _resequence(list(topic.module.topics), topic, data["position"])
    db.session.flush()
    db.session.refresh(topic)
    return topic


def set_dependencies(topic: CurriculumTopic, depends_on: list[int]) -> None:
    """Only where academically necessary (Module 14 §4): prerequisites inside the same version, without cycles."""
    version_id = topic.module.curriculum_version_id
    targets = []
    for topic_id in dict.fromkeys(depends_on):
        other = catalog_repo.get_topic(topic_id)
        if other is None or other.module.curriculum_version_id != version_id or other.topic_id == topic.topic_id:
            raise ValidationError("Invalid request data", {"depends_on": [f"Topic {topic_id} is not another topic of this version"]})
        targets.append(other)
    graph = {t.topic_id: {d.topic_id for d in t.depends_on} for m in topic.module.version.modules for t in m.topics}
    graph[topic.topic_id] = {t.topic_id for t in targets}
    if _has_cycle(graph):
        raise ValidationError("Invalid request data", {"depends_on": ["These dependencies would form a loop"]})
    topic.depends_on = targets
    db.session.flush()


def _has_cycle(graph: dict[int, set[int]]) -> bool:
    visiting, done = set(), set()

    def visit(node: int) -> bool:
        if node in done:
            return False
        if node in visiting:
            return True
        visiting.add(node)
        if any(visit(n) for n in graph.get(node, ())):
            return True
        visiting.discard(node)
        done.add(node)
        return False

    return any(visit(n) for n in graph)


# ---------------------------------------------------------------- hours, completion profile, required assessments, pins

def verify_hours(curriculum_version_id: int) -> CurriculumVersion:
    """The Branch Manager verifies standard instructional hours from the detailed teaching plan (Module 14 §5)."""
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    current = totals(version)
    if current["unestimated_topics"]:
        raise BusinessRule(f"{current['unestimated_topics']} topic(s) have no instructional estimate; hours stay Pending")
    version.hours_verified_by, version.hours_verified_at = actor_id(), datetime.now(timezone.utc)
    db.session.flush()
    audit.record("CURRICULUM_HOURS_VERIFIED", "curriculum_version", version.curriculum_version_id,
                 new={k: current[k] for k in ("instructional_minutes", "independent_minutes", "total_minutes")})
    return version


def set_completion_profile(curriculum_version_id: int, profile: dict) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    old = version.completion_profile
    version.completion_profile = {key: profile.get(key) for key in PROFILE_KEYS}
    db.session.flush()
    audit.record("CURRICULUM_COMPLETION_PROFILE", "curriculum_version", version.curriculum_version_id, old=old, new=version.completion_profile)
    return version


def add_requirement(curriculum_version_id: int, data: dict) -> AssessmentRequirement:
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    for key, getter in (("module_id", catalog_repo.get_module), ("topic_id", catalog_repo.get_topic)):
        if data.get(key):
            item = getter(data[key])
            item_version = item.curriculum_version_id if key == "module_id" else item.module.curriculum_version_id if item else None
            if item is None or item_version != version.curriculum_version_id:
                raise ValidationError("Invalid request data", {key: ["Not part of this version"]})
    requirement = AssessmentRequirement(curriculum_version_id=version.curriculum_version_id, **data)
    db.session.add(requirement)
    db.session.flush()
    return requirement


def delete_requirement(requirement_id: int) -> None:
    requirement = catalog_repo.get_requirement(requirement_id)
    if requirement is None:
        raise NotFound("Assessment requirement not found")
    _editable(_version(requirement.curriculum_version_id, lock=True))
    db.session.delete(requirement)
    db.session.flush()


def pin_component(curriculum_version_id: int, component_id: int, component_version_id: int) -> VersionComponent:
    """A combo parent version records the exact version of each track and the booster (Module 14 §2). A version of another
    course (a standalone curriculum reused for the component) needs the component's equivalence review first (§3)."""
    version = _version(curriculum_version_id, lock=True)
    _editable(version)
    if not is_combo_parent(version):
        raise BusinessRule("Only a combo's parent programme version pins track versions")
    component = catalog_repo.get_component(component_id)
    if component is None or component.parent_course_id != version.course_id:
        raise ValidationError("Invalid request data", {"component_id": ["Not a track of this combo"]})
    pinned = _version(component_version_id)
    if pinned.status not in ("Approved", "Active"):
        raise BusinessRule(f"{pinned.version_label} is {pinned.status}; pin an Approved or Active version")
    own = (pinned.course_id, pinned.component_id) == (version.course_id, component.component_id)
    borrowed = component.component_course_id is not None and (pinned.course_id, pinned.component_id) == (component.component_course_id, None)
    if not (own or borrowed):
        raise ValidationError("Invalid request data", {"component_version_id": ["Not a version written for this track or its course"]})
    if borrowed and component.equivalence_reviewed_at is None:
        raise BusinessRule(f"Record the equivalence review for {component.track_code} before reusing {pinned.version_label}")
    pin = catalog_repo.get_version_component(version.curriculum_version_id, component.component_id)
    if pin is None:
        pin = VersionComponent(curriculum_version_id=version.curriculum_version_id, component_id=component.component_id,
                               component_version_id=pinned.curriculum_version_id)
        db.session.add(pin)
    else:
        pin.component_version_id = pinned.curriculum_version_id
    db.session.flush()
    return pin


def review_equivalence(component_id: int, note: str) -> CourseComponent:
    """The Branch Manager records that the component's outcomes, scope, depth and assessment match its course's
    standalone curriculum (similar names are not enough, Module 14 §3)."""
    component = catalog_repo.get_component(component_id)
    if component is None:
        raise NotFound("Track not found")
    if component.component_course_id is None:
        raise BusinessRule(f"{component.track_code} has no standalone course to reuse")
    old = component.equivalence_note
    component.equivalence_note, component.equivalence_reviewed_by = note, actor_id()
    component.equivalence_reviewed_at = datetime.now(timezone.utc)
    db.session.flush()
    audit.record("COMPONENT_EQUIVALENCE_REVIEWED", "course_component", component.component_id, old={"note": old}, new={"note": note})
    return component


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
    notified: set[int] = set()
    for role_code, link in APPROVER_LINKS:
        approvers = [u for u in users_repo.user_ids_with_role(role_code, None) if u not in notified]
        notified.update(approvers)
        delivery_notices.notify_users(approvers, title=f"Curriculum awaiting approval: {version.version_label}", category="Curriculum",
                                      body=f"{catalog_repo.get_course(version.course_id).course_code} — submitted by {current_user().full_name}",
                                      event_key=f"curriculum-submitted-{event.event_id}", link=link, branch_id=None, action_required=True)
    return version


# Global curriculum is approved by the Founder / CEO or Super Admin after academic review (Module 14 §5); each opens it
# from their own workspace
APPROVER_LINKS = (("FOUNDER_CEO", "/founder/curriculum"), ("SUPER_ADMIN", "/branch/curriculum"))


def return_to_draft(curriculum_version_id: int, reason: str) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Under Review":
        raise BusinessRule(f"Only a version Under Review can be returned; {version.version_label} is {version.status}")
    submitted = catalog_repo.last_event(version.curriculum_version_id, "Submitted")
    event = _step(version, "Returned", "Draft", reason)
    if submitted is not None and submitted.actor_user_id:
        delivery_notices.notify_users([submitted.actor_user_id], title=f"Curriculum returned: {version.version_label}", category="Curriculum", body=reason,
                                      event_key=f"curriculum-returned-{event.event_id}",
                                      link="/branch/curriculum", branch_id=None)
    return version


def approve(curriculum_version_id: int) -> CurriculumVersion:
    version = _version(curriculum_version_id, lock=True)
    if version.status != "Under Review":
        raise BusinessRule(f"Only a version Under Review can be approved; {version.version_label} is {version.status}")
    submitted = catalog_repo.last_event(version.curriculum_version_id, "Submitted")
    approvals.require_independent(submitted.actor_user_id if submitted else None,
                                  message="The person who submitted a curriculum version cannot approve it; ask another approver")
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
    """Give the new Active version to every batch, enrolment and combo track of the course that had none. A student follows the
    curriculum of their batch, so the students of a batch that waited for a version get it together with the batch."""
    version_id = version.curriculum_version_id
    mapped_batches: list[Batch] = []
    given: list[Enrolment] = []
    pins = {p.component_id: p.component_version_id for p in catalog_repo.version_components(version_id)} if version.component_id is None else {}
    for enrolment in catalog_repo.enrolments_without_version(version.course_id):
        gained = False
        if version.component_id is None and enrolment.course_id == version.course_id and enrolment.curriculum_version_id is None:
            enrolment.curriculum_version_id = version_id
            gained = True
        for track in enrolment.tracks:
            if track.curriculum_version_id is not None:
                continue
            if version.component_id is not None:
                if track.component_id == version.component_id:
                    track.curriculum_version_id = version_id
                    gained = True
            elif enrolment.curriculum_version_id == version_id and track.component_id in pins:
                track.curriculum_version_id = pins[track.component_id]  # the combo parent pins it
                gained = True
            elif catalog_repo.active_curriculum_version_id(enrolment.course_id, track.component_id) is None \
                    and track.component.component_course_id == version.course_id and track.component.equivalence_reviewed_at is not None:
                track.curriculum_version_id = version_id  # a reviewed component reuses its course's own version
                gained = True
        if gained:
            given.append(enrolment)
    if version.component_id is None:
        for batch in catalog_repo.batches_without_version(version.course_id):
            _map_batch(batch, version)
            mapped_batches.append(batch)
    db.session.flush()

    for enrolment in given:
        delivery_notices.notify_student(enrolment.student_id, title=f"Your curriculum is ready: {enrolment.course.title}",
                                        body="Your course content is now available.",
                                        event_key=f"curriculum-released-{enrolment.enrolment_id}-{version_id}", link="/my-courses",
                                        branch_id=enrolment.service_branch_id)
    by_branch: dict[int, list[Batch]] = {}
    for batch in mapped_batches:
        by_branch.setdefault(batch.branch_id, []).append(batch)
    for branch_id, group in by_branch.items():
        delivery_notices.notify_branch_managers(branch_id, title=f"{len(group)} batch(es) now have a curriculum", category="Enrolment",
                                                body=f"{version.version_label} was activated for {group[0].course.course_code}; "
                                                     "its batches and their students follow it.",
                                                event_key=f"curriculum-released-branch-{branch_id}-{version_id}", link="/branch/batches")
    return {"enrolments_released": len(given), "batches_mapped": len(mapped_batches)}


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


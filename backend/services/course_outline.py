"""The course outline: modules and topics live on the course itself (db/121). There are no curriculum versions, drafts or approvals.

Super Admin and Founder / CEO edit the outline, hours, completion rules, required assessments, combo track pins and the reusable
module library; an edit applies at once, tells the Branch Managers of the branches that have open batches of the course, and is
written to the audit log. Everyone who can see the course reads it (Branch Manager, Trainer of a batch of the course, Student with an
enrolment in it). Course code, title, category, status and tracks belong to the CRM (`CourseUpserted`) and are never edited here.

Module 14: each topic has an outcome, a Required / Recommended / Optional class, estimated minutes, a progress weight, evidence and
(only where necessary) dependencies; a course has verified hours, a completion profile and its required assessments; a combo track
may be pinned to a standalone course's outline once its equivalence review is recorded.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from config.database import db
from config.timezone import today_ist
from models import AssessmentRequirement, Batch, Course, CourseComponent, CourseModule, CourseTopic, Enrolment
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import students as students_repo
from services import audit, delivery_notices
from services.context import ADMIN_ROLES, actor_id, current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError

TOPIC_FIELDS = ("title", "title_te", "topic_class", "outcome", "instructional_minutes", "independent_minutes", "weight", "evidence",
                "activities")
PROFILE_KEYS = ("attendance_minimum_pct", "pass_mark_pct", "recovery_rule", "reassessment_rule")


# ---------------------------------------------------------------- access

def can_edit() -> bool:
    return current_user().role_code in ADMIN_ROLES


def _require_editor() -> None:
    if not can_edit():
        raise Forbidden("Only the Super Admin or Founder can change a course outline")


def get_course(course_id: int, *, lock: bool = False) -> Course:
    course = catalog_repo.get_course_for_update(course_id) if lock else catalog_repo.get_course(course_id)
    if course is None:
        raise NotFound("Course not found")
    return course


def assert_can_view(course: Course) -> None:
    """Staff (Branch Manager, Super Admin, Founder) see every course; a trainer the courses of their batches; a student their own."""
    user = current_user()
    if user.role_code in ADMIN_ROLES or user.role_code == "BRANCH_MANAGER":
        return
    if user.role_code == "TRAINER":
        batch_ids = batches_repo.batch_ids_for_trainer(user.user_id, today_ist())
        if batch_ids and db.session.execute(
                select(func.count()).select_from(Batch).where(Batch.batch_id.in_(batch_ids), Batch.course_id == course.course_id)).scalar():
            return
    elif user.student_id is not None:
        if any(e.course_id == course.course_id for e in students_repo.enrolments_of_student(user.student_id)):
            return
    raise NotFound("Course not found")


# ---------------------------------------------------------------- reads

def _resolved_tracks(course: Course, modules: list[CourseModule]) -> list[dict]:
    """Each combo track with its outline: its own modules, or the pinned standalone course's whole outline."""
    own: dict[int | None, list[CourseModule]] = {}
    for m in modules:
        own.setdefault(m.component_id, []).append(m)
    tracks = []
    for component in course.components:
        borrowed = component.pinned_course
        mods = ([m for m in catalog_repo.outline_modules(borrowed.course_id) if m.component_id is None]
                if borrowed is not None else own.get(component.component_id, []))
        tracks.append({"component": component, "modules": mods, "borrowed_from": borrowed})
    return tracks


def totals(course: Course, modules: list[CourseModule]) -> dict:
    """Module 14 §6: standard instructional, independent learning and total effort, in minutes. A combo adds its tracks, with the
    included booster shown separately; topics without an estimate are counted, never guessed."""
    def part(mods):
        topics = [t for m in mods for t in m.topics]
        return (sum(t.instructional_minutes or 0 for t in topics), sum(t.independent_minutes or 0 for t in topics),
                sum(1 for t in topics if t.instructional_minutes is None))

    instructional, independent, unestimated = part([m for m in modules if m.component_id is None])
    booster = None
    if course.is_combo:
        for track in _resolved_tracks(course, modules):
            i, n, u = part(track["modules"])
            if track["component"].role == "Included booster":
                booster = {"track_code": track["component"].track_code, "instructional_minutes": i, "independent_minutes": n,
                           "total_minutes": i + n}
            instructional, independent, unestimated = instructional + i, independent + n, unestimated + u
    return {"instructional_minutes": instructional, "independent_minutes": independent, "total_minutes": instructional + independent,
            "unestimated_topics": unestimated, "hours_verified": course.hours_verified_at is not None,
            "hours_verified_at": course.hours_verified_at, "booster": booster}


def _course_dict(course: Course) -> dict:
    return {**course.to_dict(include_components=True)}


def get_outline(course_id: int) -> dict:
    """What every role that can see the course reads. Staff get the extras (hours, completion rules, required assessments, usage)."""
    course = get_course(course_id)
    assert_can_view(course)
    modules = catalog_repo.outline_modules(course_id)
    own = [m for m in modules if m.component_id is None]
    data = {
        "course": _course_dict(course),
        "can_edit": can_edit(),
        "counts": catalog_repo.module_counts([course_id])[course_id],
        "modules": [m.to_dict() for m in own],
        "tracks": [{"component": t["component"].to_dict(), "modules": [m.to_dict() for m in t["modules"]],
                    "borrowed_from": t["borrowed_from"].to_summary() if t["borrowed_from"] else None}
                   for t in _resolved_tracks(course, modules)],
    }
    if current_user().role_code in (*ADMIN_ROLES, "BRANCH_MANAGER"):
        data.update({
            "totals": totals(course, modules),
            "completion_profile": course.completion_profile,
            "assessment_requirements": [r.to_dict() for r in catalog_repo.assessment_requirements(course_id)],
            "usage": _usage([course_id])[course_id],
        })
    return data


def _scope_branches() -> set[int] | None:
    """None = every branch (Super Admin, Founder); the Branch Manager's session branch otherwise."""
    user = current_user()
    if user.role_code in ADMIN_ROLES:
        return None
    return {user.active_branch_id} if user.active_branch_id is not None else set()


def _usage(course_ids: list[int]) -> dict[int, dict]:
    """Per course: open batches and students waiting for a batch (the caller's branches), and per branch for company-wide roles."""
    branches = _scope_branches()
    out = {i: {"running_batches": 0, "students_waiting": 0, "active_enrolments": 0, "by_branch": []} for i in course_ids}
    if not course_ids:
        return out
    open_states = ("Completed", "Cancelled", "Archived")
    b_stmt = (select(Batch.course_id, Batch.branch_id, func.count()).where(Batch.course_id.in_(course_ids), Batch.state.not_in(open_states))
              .group_by(Batch.course_id, Batch.branch_id))
    e_stmt = (select(Enrolment.course_id, Enrolment.service_branch_id, Enrolment.status, func.count())
              .where(Enrolment.course_id.in_(course_ids), Enrolment.status.in_(("Active", "Allocation Pending")))
              .group_by(Enrolment.course_id, Enrolment.service_branch_id, Enrolment.status))
    per_branch: dict[tuple[int, int], dict] = {}
    for course_id, branch_id, n in db.session.execute(b_stmt):
        if branches is None or branch_id in branches:
            out[course_id]["running_batches"] += n
            per_branch.setdefault((course_id, branch_id), {"branch_id": branch_id, "running_batches": 0, "active_enrolments": 0})["running_batches"] += n
    for course_id, branch_id, status, n in db.session.execute(e_stmt):
        if branches is None or branch_id in branches:
            key = "active_enrolments" if status == "Active" else "students_waiting"
            out[course_id][key] += n
            if status == "Active":
                per_branch.setdefault((course_id, branch_id), {"branch_id": branch_id, "running_batches": 0, "active_enrolments": 0})["active_enrolments"] += n
    if branches is None:
        from models import Branch
        names = {b.branch_id: b for b in db.session.execute(select(Branch)).scalars()}
        for (course_id, branch_id), row in sorted(per_branch.items()):
            out[course_id]["by_branch"].append({**row, "branch": names[branch_id].to_summary()})
    return out


def list_courses() -> list[dict]:
    courses = catalog_repo.list_courses()
    ids = [c.course_id for c in courses]
    counts, usage = catalog_repo.module_counts(ids), _usage(ids)
    return [{**_course_dict(c), "counts": counts[c.course_id], "usage": usage[c.course_id],
             "hours_verified": c.hours_verified_at is not None} for c in courses]


# ---------------------------------------------------------------- audit and notify

def _changed(course: Course, change: str, **detail) -> None:
    """Every edit: audit it and tell the Branch Managers of the branches with open batches of the course."""
    audit.record("COURSE_OUTLINE_CHANGED", "course", course.course_id, new={"change": change, **detail})
    me = current_user()
    branch_ids = sorted({b.branch_id for b in catalog_repo.open_batches_of(course.course_id)})
    for branch_id in branch_ids:
        delivery_notices.notify_branch_managers(
            branch_id, title=f"{course.title}: course outline changed", body=f"{me.full_name}: {change}.",
            event_key=f"course-outline:{course.course_id}:{uuid.uuid4().hex}", link=f"/branch/courses/{course.course_id}", category="Courses")


# ---------------------------------------------------------------- modules and topics

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


def _siblings(module: CourseModule) -> list[CourseModule]:
    stmt = (select(CourseModule).where(CourseModule.course_id == module.course_id, CourseModule.is_archived.is_(False),
                                       CourseModule.component_id.is_(None) if module.component_id is None
                                       else CourseModule.component_id == module.component_id)
            .order_by(CourseModule.sort_order))
    return list(db.session.execute(stmt).scalars())


def _live_module(module_id: int) -> tuple[Course, CourseModule]:
    module = catalog_repo.get_module(module_id)
    if module is None or module.is_archived:
        raise NotFound("Module not found")
    return get_course(module.course_id, lock=True), module


def add_module(course_id: int, title: str, title_te: str | None, position: int | None, component_id: int | None = None) -> CourseModule:
    _require_editor()
    course = get_course(course_id, lock=True)
    if component_id is not None:
        component = catalog_repo.get_component(component_id)
        if component is None or component.parent_course_id != course.course_id:
            raise ValidationError("Invalid request data", {"component_id": ["Not a track of this course"]})
        if component.pinned_course_id is not None:
            raise BusinessRule(f"{component.track_code} follows another course's outline; unpin it to give it its own modules")
    module = CourseModule(course_id=course.course_id, component_id=component_id, title=title, title_te=title_te,
                          sort_order=catalog_repo.next_module_order(course.course_id, component_id))
    db.session.add(module)
    db.session.flush()
    if position is not None:
        _resequence(_siblings(module), module, position)
    _changed(course, f"added the module \"{title}\"", module_id=module.module_id)
    return module


def update_module(module_id: int, data: dict) -> CourseModule:
    _require_editor()
    course, module = _live_module(module_id)
    old = module.title
    for name in ("title", "title_te"):
        if name in data:
            setattr(module, name, data[name])
    if "position" in data:
        _resequence(_siblings(module), module, data["position"])
    db.session.flush()
    _changed(course, f"renamed the module \"{old}\" to \"{module.title}\"" if module.title != old else f"changed the module \"{old}\"",
             module_id=module.module_id)
    return module


def _used_topic_ids(topic_ids: list[int]) -> set[int]:
    """Topics that classes, content, assignments, questions or tests refer to (they cannot be deleted)."""
    if not topic_ids:
        return set()
    rows = db.session.execute(text("""
        SELECT topic_id FROM class_sessions WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM class_session_topics WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM session_rosters WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM content_items WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM assignments WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM questions WHERE topic_id = ANY(:ids)
        UNION SELECT topic_id FROM tests WHERE topic_id = ANY(:ids)"""), {"ids": topic_ids})
    return {r[0] for r in rows}


def _module_used(module: CourseModule) -> bool:
    if _used_topic_ids([t.topic_id for t in module.topics]):
        return True
    return bool(db.session.execute(text("SELECT 1 FROM content_items WHERE module_id = :m UNION SELECT 1 FROM tests WHERE module_id = :m"),
                                   {"m": module.module_id}).first())


def delete_module(module_id: int) -> dict:
    """Remove a module from the outline. One that classes, content or tests refer to is archived instead (hidden, nothing lost)."""
    _require_editor()
    course, module = _live_module(module_id)
    title, archived = module.title, _module_used(module)
    siblings = _siblings(module)
    if archived:
        module.is_archived = True
    else:
        db.session.delete(module)
    db.session.flush()
    for number, item in enumerate([m for m in siblings if m is not module], 1):
        item.sort_order = number
    db.session.flush()
    _changed(course, f"removed the module \"{title}\"" + (" (kept as archived: classes or content use it)" if archived else ""),
             module_id=module_id, archived=archived)
    return {"archived": archived}


def _topic_values(data: dict) -> dict:
    """The topic fields in a request; the legacy `is_required` flag maps to Required / Optional."""
    values = {f: data[f] for f in TOPIC_FIELDS if f in data}
    if "topic_class" not in values and "is_required" in data:
        values["topic_class"] = "Required" if data["is_required"] else "Optional"
    return values


def _hours_changed(course: Course) -> None:
    """Changing the teaching plan's minutes needs the hours verified again."""
    if course.hours_verified_at is not None:
        course.hours_verified_by = course.hours_verified_at = None


def add_topic(module_id: int, data: dict) -> CourseTopic:
    _require_editor()
    course, module = _live_module(module_id)
    values = {"topic_class": "Required", **_topic_values(data)}
    topic = CourseTopic(module_id=module.module_id, sort_order=catalog_repo.next_topic_order(module.module_id), **values)
    db.session.add(topic)
    db.session.flush()
    db.session.refresh(topic)
    _hours_changed(course)
    if data.get("position") is not None:
        db.session.refresh(module)
        _resequence(list(module.topics), topic, data["position"])
    _changed(course, f"added the topic \"{topic.title}\" to \"{module.title}\"", topic_id=topic.topic_id)
    return topic


def _live_topic(topic_id: int) -> tuple[Course, CourseTopic]:
    topic = catalog_repo.get_topic(topic_id)
    if topic is None or topic.module.is_archived:
        raise NotFound("Topic not found")
    return get_course(topic.module.course_id, lock=True), topic


def update_topic(topic_id: int, data: dict) -> CourseTopic:
    _require_editor()
    course, topic = _live_topic(topic_id)
    values = _topic_values(data)
    if {"instructional_minutes", "independent_minutes"} & values.keys():
        _hours_changed(course)
    old = topic.title
    for name, value in values.items():
        setattr(topic, name, value)
    if "depends_on" in data:
        set_dependencies(topic, data["depends_on"])
    if "position" in data:
        db.session.refresh(topic.module)
        _resequence(list(topic.module.topics), topic, data["position"])
    db.session.flush()
    db.session.refresh(topic)
    _changed(course, f"changed the topic \"{old}\"" + (f" (now \"{topic.title}\")" if topic.title != old else ""), topic_id=topic.topic_id)
    return topic


def set_dependencies(topic: CourseTopic, depends_on: list[int]) -> None:
    """Only where academically necessary (Module 14 §4): prerequisites inside the same outline, without cycles."""
    module = topic.module
    targets = []
    for topic_id in dict.fromkeys(depends_on):
        other = catalog_repo.get_topic(topic_id)
        if (other is None or other.topic_id == topic.topic_id or other.module.course_id != module.course_id
                or other.module.component_id != module.component_id):
            raise ValidationError("Invalid request data", {"depends_on": [f"Topic {topic_id} is not another topic of this outline"]})
        targets.append(other)
    graph = {t.topic_id: {d.topic_id for d in t.depends_on} for m in _siblings(module) for t in m.topics}
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


def delete_topic(topic_id: int) -> None:
    _require_editor()
    course, topic = _live_topic(topic_id)
    if _used_topic_ids([topic.topic_id]):
        raise BusinessRule("Classes, content, assignments, questions or tests use this topic, so it cannot be removed")
    module, title = topic.module, topic.title
    db.session.delete(topic)
    db.session.flush()
    db.session.refresh(module)
    for number, item in enumerate(module.topics, 1):
        item.sort_order = number
    db.session.flush()
    _changed(course, f"removed the topic \"{title}\" from \"{module.title}\"", topic_id=topic_id)


# ---------------------------------------------------------------- hours, completion rules, required assessments, pins

def verify_hours(course_id: int) -> Course:
    """Record that the standard instructional hours were checked against the detailed teaching plan (Module 14 §5)."""
    _require_editor()
    course = get_course(course_id, lock=True)
    current = totals(course, catalog_repo.outline_modules(course_id))
    if current["unestimated_topics"]:
        raise BusinessRule(f"{current['unestimated_topics']} topic(s) have no instructional estimate; hours stay Pending")
    course.hours_verified_by, course.hours_verified_at = actor_id(), datetime.now(timezone.utc)
    db.session.flush()
    _changed(course, "verified the standard hours", **{k: current[k] for k in ("instructional_minutes", "independent_minutes", "total_minutes")})
    return course


def set_completion_profile(course_id: int, profile: dict) -> Course:
    _require_editor()
    course = get_course(course_id, lock=True)
    old = course.completion_profile
    course.completion_profile = {key: profile.get(key) for key in PROFILE_KEYS}
    db.session.flush()
    audit.record("COURSE_OUTLINE_CHANGED", "course", course.course_id, old={"completion_profile": old},
                 new={"change": "changed the completion rules", "completion_profile": course.completion_profile})
    _notify_batches(course, "changed the completion rules")
    return course


def _notify_batches(course: Course, change: str) -> None:
    me = current_user()
    for branch_id in sorted({b.branch_id for b in catalog_repo.open_batches_of(course.course_id)}):
        delivery_notices.notify_branch_managers(
            branch_id, title=f"{course.title}: course outline changed", body=f"{me.full_name}: {change}.",
            event_key=f"course-outline:{course.course_id}:{uuid.uuid4().hex}", link=f"/branch/courses/{course.course_id}", category="Courses")


def add_requirement(course_id: int, data: dict) -> AssessmentRequirement:
    _require_editor()
    course = get_course(course_id, lock=True)
    if data.get("module_id"):
        module = catalog_repo.get_module(data["module_id"])
        if module is None or module.course_id != course.course_id:
            raise ValidationError("Invalid request data", {"module_id": ["Not part of this course"]})
    if data.get("topic_id"):
        topic = catalog_repo.get_topic(data["topic_id"])
        if topic is None or topic.module.course_id != course.course_id:
            raise ValidationError("Invalid request data", {"topic_id": ["Not part of this course"]})
    requirement = AssessmentRequirement(course_id=course.course_id, **data)
    db.session.add(requirement)
    db.session.flush()
    _changed(course, f"added the required {data['kind'].lower()} \"{data['title']}\"", requirement_id=requirement.requirement_id)
    return requirement


def delete_requirement(requirement_id: int) -> None:
    _require_editor()
    requirement = catalog_repo.get_requirement(requirement_id)
    if requirement is None:
        raise NotFound("Assessment requirement not found")
    course, title = get_course(requirement.course_id, lock=True), requirement.title
    db.session.delete(requirement)
    db.session.flush()
    _changed(course, f"removed the required assessment \"{title}\"", requirement_id=requirement_id)


def review_equivalence(component_id: int, note: str) -> CourseComponent:
    """Record that the track's outcomes, scope, depth and assessment match its course's standalone outline (Module 14 §3)."""
    _require_editor()
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


def pin_track(course_id: int, component_id: int, pinned_course_id: int | None) -> Course:
    """A combo track follows a standalone course's outline (needs the equivalence review), or goes back to its own (None)."""
    _require_editor()
    course = get_course(course_id, lock=True)
    component = catalog_repo.get_component(component_id)
    if not course.is_combo or component is None or component.parent_course_id != course.course_id:
        raise ValidationError("Invalid request data", {"component_id": ["Not a track of this combo"]})
    if pinned_course_id is not None:
        if pinned_course_id == course.course_id or catalog_repo.get_course(pinned_course_id) is None:
            raise ValidationError("Invalid request data", {"pinned_course_id": ["Pick another course"]})
        if component.component_course_id != pinned_course_id:
            raise ValidationError("Invalid request data", {"pinned_course_id": ["Only the track's own standalone course can be reused"]})
        if component.equivalence_reviewed_at is None:
            raise BusinessRule(f"Record the equivalence review for {component.track_code} before reusing another course's outline")
    old = component.pinned_course_id
    component.pinned_course_id = pinned_course_id
    db.session.flush()
    db.session.refresh(component)
    _changed(course, f"pinned {component.track_code} to another course's outline" if pinned_course_id
             else f"unpinned {component.track_code} (it uses its own modules)", component_id=component_id, old_pinned_course_id=old,
             pinned_course_id=pinned_course_id)
    return course

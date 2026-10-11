"""What approving a curriculum version would change and who it affects, in plain words: the Founder's side panel (U16).

Compares the version with the one that is Active for the same course (or track) by module and topic titles, adds up the learning
hours, and counts the batches and students that would pick it up (those with no curriculum yet) or stay on the older one."""
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from services import curriculum as curriculum_service
from services.errors import NotFound


def _titles(version) -> tuple[list[str], dict[str, list[str]]]:
    modules = [m.title for m in version.modules]
    return modules, {m.title: [t.title for t in m.topics] for m in version.modules}


def _hours(minutes: int) -> str:
    hours = minutes / 60
    return f"{hours:g} hours"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def impact(curriculum_version_id: int) -> dict:
    version = catalog_repo.get_curriculum_version(curriculum_version_id)
    if version is None:
        raise NotFound("Curriculum version not found")
    course = catalog_repo.get_course(version.course_id)
    detail = curriculum_service.get_version_detail(curriculum_version_id)
    previous_id = catalog_repo.active_curriculum_version_id(version.course_id, version.component_id)
    previous = catalog_repo.get_curriculum_version(previous_id) if previous_id and previous_id != curriculum_version_id else None

    modules, topics = _titles(version)
    old_modules, old_topics = _titles(previous) if previous else ([], {})
    new_topic_set = {(m, t) for m, ts in topics.items() for t in ts}
    old_topic_set = {(m, t) for m, ts in old_topics.items() for t in ts}
    added = sorted(t for _, t in new_topic_set - old_topic_set) if previous else []
    removed = sorted(t for _, t in old_topic_set - new_topic_set)
    modules_added = [m for m in modules if m not in old_modules] if previous else []
    modules_removed = [m for m in old_modules if m not in modules]
    minutes = curriculum_service.totals(version)["total_minutes"]
    before_minutes = curriculum_service.totals(previous)["total_minutes"] if previous else None

    waiting_batches = catalog_repo.batches_without_version(version.course_id) if version.component_id is None else []
    staying = catalog_repo.open_batches_on(previous.curriculum_version_id) if previous else []
    allocated = batches_repo.allocated_counts([b.batch_id for b in waiting_batches + staying])
    getting_students = sum(allocated.get(b.batch_id, 0) for b in waiting_batches)
    staying_students = sum(allocated.get(b.batch_id, 0) for b in staying)

    lines = []
    if previous is None:
        lines.append(f"{course.title} has no active curriculum yet. This would be its first: "
                     f"{_plural(detail.counts['modules'], 'module')}, {_plural(detail.counts['topics'], 'topic')}, about {_hours(minutes)} of learning.")
    else:
        parts = []
        if modules_added or modules_removed:
            parts.append(f"{_plural(len(modules_added), 'module')} added, {_plural(len(modules_removed), 'module')} removed")
        parts.append(f"{_plural(len(added), 'topic')} added, {_plural(len(removed), 'topic')} removed")
        lines.append(f"Compared with {previous.version_label}: " + "; ".join(parts) + ".")
        if before_minutes is not None and before_minutes != minutes:
            lines.append(f"Learning time goes from {_hours(before_minutes)} to {_hours(minutes)}.")
        elif not (added or removed or modules_added or modules_removed):
            lines.append("The modules and topics have the same titles; the changes are in the details of the topics, hours or rules.")
    affected = []
    if waiting_batches:
        affected.append(f"{_plural(len(waiting_batches), 'batch', 'batches')} with no curriculum yet "
                        f"({_plural(getting_students, 'student')}) would get it as soon as it is active.")
    if staying:
        affected.append(f"{_plural(len(staying), 'batch', 'batches')} ({_plural(staying_students, 'student')}) stay on {previous.version_label}.")
    if not affected:
        affected.append("No batch is waiting for it, and no running batch changes." if previous is None else "No running batch is affected.")

    submitted = catalog_repo.last_event(curriculum_version_id, "Submitted")
    return {
        "curriculum_version_id": curriculum_version_id,
        "version_label": version.version_label,
        "status": version.status,
        "activate_on": version.activate_on,
        "course": course.to_summary(),
        "previous": previous.to_summary() if previous else None,
        "submitted_by": ({"user_id": submitted.actor_user_id, "full_name": submitted.actor.full_name} if submitted and submitted.actor_user_id else None),
        "submitted_at": submitted.created_at if submitted else None,
        "what_changes": lines,
        "who_is_affected": affected,
        "added_topics": added[:30],
        "removed_topics": removed[:30],
        "batches_getting_it": len(waiting_batches),
        "batches_staying": len(staying),
        "outline": [{"module": m, "topics": ts} for m, ts in topics.items()],
        "total_minutes": minutes,
    }

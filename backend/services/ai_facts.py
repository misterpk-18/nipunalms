"""The facts Ask Nipuna may use, gathered for the signed-in user and nothing else (Module 24: "the application checks
identity, entitlement and purpose before retrieval").

A student's facts cover their own enrolments, the curriculum of those enrolments, the class sessions of the batches they are
allocated to, and delivery counts. A staff member's facts are batch-level (counts and curriculum) for the batches in their scope
and never name individual students. Other slices add facts (for example due work) by registering a provider:

    register_fact_provider("due_work", lambda student: ({"assignments_due": 2}, [{"type": "assignment", "code": "ASG-8"}]))
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from config.database import db
from config.timezone import IST
from models import Batch, CurriculumVersion, Student
from repositories import ask_nipuna as ask_repo
from repositories import batches as batches_repo
from repositories import students as students_repo
from services import scope
from services.context import CurrentUser

UPCOMING_DAYS = 14
UPCOMING_LIMIT = 10
STAFF_BATCH_LIMIT = 20

# name -> callable(student) returning (facts, sources); registered by the slices that own the data
FACT_PROVIDERS: dict[str, Callable[[Student], tuple[Any, list[dict]]]] = {}

STUDENT_SCOPE = "Answers use only your enrolled courses, their curriculum, your class schedule and your own records."
STAFF_SCOPE = "Answers use only the batches in your scope, as counts and curriculum. No individual student's details are shared."


@dataclass
class Facts:
    data: dict
    sources: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def register_fact_provider(name: str, provider: Callable[[Student], tuple[Any, list[dict]]]) -> None:
    FACT_PROVIDERS[name] = provider


def format_ist(moment: datetime) -> str:
    """'Mon 28 Sep, 10:00' in IST."""
    return moment.astimezone(IST).strftime("%a %d %b, %H:%M")


def _version_facts(version: CurriculumVersion) -> dict:
    return {
        "version": version.version_label,
        "modules": [
            {"title": m.title, "topics": [{"title": t.title, "required": t.is_required} for t in m.topics]} for m in version.modules
        ],
    }


def _session_facts(sessions) -> list[dict]:
    return [
        {
            "code": s.session_code, "title": s.title, "starts": format_ist(s.starts_at), "mode": s.mode, "state": s.state,
            "topic": s.topic.title if s.topic else None, "batch": s.batch.batch_code,
        }
        for s in sessions
    ]


def student_facts(student: Student, now: datetime) -> Facts:
    enrolments = [e for e in students_repo.enrolments_of_student(student.student_id) if e.status != "Withdrawn"]
    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    batch_ids = {a.batch_id for a in allocations.values()}
    facts = Facts(data={"student": {"name": student.full_name, "preferred_language": student.preferred_language}})
    if not enrolments:
        facts.warnings.append("No active enrolment was found on this account.")

    facts.data["enrolments"] = []
    versions: dict[int, CurriculumVersion] = {}
    for e in enrolments:
        allocation = allocations.get(e.enrolment_id)
        facts.data["enrolments"].append({
            "enrolment": e.enrolment_code, "course_code": e.course.course_code, "course": e.course.title, "kind": e.kind,
            "status": e.status, "mode": e.mode, "batch": allocation.batch.batch_code if allocation else None,
        })
        facts.sources.append({"type": "enrolment", "id": e.enrolment_id, "code": e.enrolment_code})
        for version in [e.curriculum_version, *[t.curriculum_version for t in e.tracks]]:
            if version is not None:
                versions[version.curriculum_version_id] = version
        if e.curriculum_version is None and not e.tracks:
            facts.warnings.append(f"{e.course.title}: no curriculum version is mapped yet.")

    facts.data["curriculum"] = [_version_facts(v) for v in versions.values()]
    facts.sources += [{"type": "curriculum_version", "id": v.curriculum_version_id, "code": v.version_label} for v in versions.values()]

    sessions = ask_repo.upcoming_sessions(batch_ids, now, now + timedelta(days=UPCOMING_DAYS), UPCOMING_LIMIT)
    facts.data["upcoming_sessions"] = _session_facts(sessions)
    facts.sources += [{"type": "class_session", "id": s.session_id, "code": s.session_code} for s in sessions]

    counts = ask_repo.session_counts(batch_ids)
    facts.data["delivery"] = [
        {"batch": a.batch.batch_code, "delivered": counts.get(a.batch_id, (0, 0))[0], "planned": counts.get(a.batch_id, (0, 0))[1]}
        for a in allocations.values()
    ]
    facts.sources += [{"type": "batch", "id": a.batch_id, "code": a.batch.batch_code} for a in allocations.values()]

    for name, provider in FACT_PROVIDERS.items():
        provided, sources = provider(student)
        facts.data[name] = provided
        facts.sources += sources
    if "due_work" not in FACT_PROVIDERS:
        facts.warnings.append("Assignments and tests are not connected to Ask Nipuna yet, so due work is not available here.")
    return facts


def staff_facts(user: CurrentUser, now: datetime) -> Facts:
    branch_ids = scope.visible_branch_ids(user)
    stmt = batches_repo.list_stmt({}, branch_ids, scope.trainer_batch_ids(user)).limit(STAFF_BATCH_LIMIT)
    batches: list[Batch] = list(db.session.execute(stmt).scalars())
    batch_ids = {b.batch_id for b in batches}
    allocated = batches_repo.allocated_counts(list(batch_ids))
    counts = ask_repo.session_counts(batch_ids)
    sessions = ask_repo.upcoming_sessions(batch_ids, now, now + timedelta(days=7), UPCOMING_LIMIT)

    facts = Facts(data={"staff": {"name": user.full_name}})
    facts.data["batches"] = [
        {
            "batch": b.batch_code, "course": b.course.title, "state": b.state, "readiness": b.readiness, "capacity": b.capacity,
            "allocated_students": allocated.get(b.batch_id, 0),
            "sessions_delivered": counts.get(b.batch_id, (0, 0))[0], "sessions_planned": counts.get(b.batch_id, (0, 0))[1],
            "curriculum": _version_facts(b.curriculum_version) if b.curriculum_version else None,
        }
        for b in batches
    ]
    facts.data["upcoming_sessions"] = _session_facts(sessions)
    facts.sources += [{"type": "batch", "id": b.batch_id, "code": b.batch_code} for b in batches]
    facts.sources += [{"type": "class_session", "id": s.session_id, "code": s.session_code} for s in sessions]
    if not batches:
        facts.warnings.append("No batches are in your scope.")
    return facts

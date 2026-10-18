"""Create classes from a batch's timetable (UX phase U14): `POST /batches/{id}/generate-sessions`.

The batch already says when it meets: teaching days, start and end time, planned start and end. This turns that into dated
classes, one per teaching day, led by the batch's lead trainer in the batch's room. Days that are company holidays or closures of
the branch are skipped, and so are days the batch already has a class (so running it twice never doubles up). Each class takes
the next curriculum topic that no class of the batch covers yet, when the batch has a curriculum; otherwise it is titled by number.

`preview: true` returns the plan and changes nothing. Creating is all or nothing: a trainer who already teaches at one of the times
blocks it (it cannot be overridden), and a booked room or a student clash needs the Branch Manager's recorded reason, as when
scheduling a class by hand.
"""
from datetime import datetime, timedelta

from sqlalchemy import select

from config.database import db
from config.timezone import IST, today_ist
from models import Batch, ClassSession
from repositories import batches as batches_repo
from services import batches as batches_service
from services import class_sessions, working_days
from services.context import current_user
from services.errors import BusinessRule, Forbidden, ValidationError

MAX_WEEKS = 52


def _taught_topic_ids(batch_id: int) -> set[int]:
    """Topics that a class of this batch (not cancelled) already covers."""
    stmt = select(ClassSession.topic_id).where(ClassSession.batch_id == batch_id, ClassSession.state != "Cancelled",
                                               ClassSession.approval_status != "Rejected", ClassSession.topic_id.is_not(None))
    return set(db.session.execute(stmt).scalars())


def _class_days(batch_id: int) -> set:
    stmt = select(ClassSession.starts_at).where(ClassSession.batch_id == batch_id, ClassSession.state != "Cancelled",
                                                ClassSession.approval_status != "Rejected")
    return {starts.astimezone(IST).date() for starts in db.session.execute(stmt).scalars()}


def _next_topics(batch: Batch) -> list:
    """The curriculum topics still to be scheduled, in course order; optional topics are not scheduled on their own."""
    version = batch.curriculum_version
    if version is None:
        return []
    taught = _taught_topic_ids(batch.batch_id)
    return [t for m in version.modules for t in m.topics if t.topic_id not in taught and t.topic_class != "Optional"]


def _window(batch: Batch, data: dict) -> tuple:
    first = max(data.get("from_date") or batch.planned_start or today_ist(), today_ist())
    last = data.get("until") or batch.planned_end
    if last is None:
        raise ValidationError("An end date is needed", {"until": ["Give the date the classes run until, or set the batch's planned end date"]})
    if last < first:
        raise ValidationError("Invalid dates", {"until": ["Must not be before the first class"]})
    return first, min(last, first + timedelta(weeks=MAX_WEEKS))


def plan(batch: Batch, data: dict) -> dict:
    """The classes the batch's timetable calls for, and the days left out with the reason."""
    if batch.state in batches_service.CLOSED_STATES or batch.state == "On Hold":
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    if not batch.schedule_days or batch.start_time is None or batch.end_time is None:
        raise BusinessRule("Set the teaching days and the class times on the batch first")
    lead = batches_repo.lead_trainer(batch.batch_id)
    if lead is None:
        raise BusinessRule("The batch has no lead trainer yet; assign one first")
    first, last = _window(batch, data)
    now = datetime.now(IST)
    closed = working_days.closure_reasons(first, last, batch.branch_id)
    booked = _class_days(batch.batch_id)
    topics = _next_topics(batch)
    already = len(booked)
    room = batch.location if batch.mode != "Live Online" else None

    classes, skipped, day, truncated = [], [], first, False
    while day <= last:
        if day.isoweekday() in batch.schedule_days:
            starts = datetime.combine(day, batch.start_time, tzinfo=IST)
            ends = datetime.combine(day, batch.end_time, tzinfo=IST)
            if day in closed:
                skipped.append({"date": day, "reason": closed[day]})
            elif day in booked:
                skipped.append({"date": day, "reason": "The batch already has a class this day"})
            elif starts <= now:
                skipped.append({"date": day, "reason": "The class time has already passed"})
            elif len(classes) >= class_sessions.MAX_SESSIONS_PER_REQUEST:
                truncated = True
                break
            else:
                topic = topics[len(classes)] if len(classes) < len(topics) else None
                blocked, warnings = class_sessions.conflicts_for(batch, lead.trainer_user_id, starts, ends, room)
                classes.append({"starts_at": starts, "ends_at": ends, "title": topic.title if topic else f"{batch.course.title}: class {already + len(classes) + 1}",
                                "topic_id": topic.topic_id if topic else None, "blocked": blocked, "warnings": warnings})
        day += timedelta(days=1)
    return {"batch": batch.to_summary(), "trainer": {"user_id": lead.trainer_user_id, "full_name": lead.trainer.full_name}, "room": room, "mode": batch.mode,
            "from": first, "until": last, "classes": classes, "skipped": skipped, "truncated": truncated,
            "blocking": sorted({c["blocked"] for c in classes if c["blocked"]}), "warnings": sorted({w for c in classes for w in c["warnings"]})}


def generate(batch_id: int, data: dict) -> dict:
    """Preview the classes (`preview`), or create them. Returns the plan, and the created classes when it created any."""
    batch = batches_service.load_managed_batch(batch_id)
    result = plan(batch, data)
    result["created"] = []
    if data.get("preview"):
        return result
    if not result["classes"]:
        raise BusinessRule("There are no classes to create: every teaching day in these dates is already planned, closed or past")
    if result["blocking"]:
        raise BusinessRule("The classes cannot be created: " + "; ".join(result["blocking"]), {"blocking": result["blocking"]})
    if result["warnings"]:
        if not data.get("override_reason"):
            raise BusinessRule("; ".join(result["warnings"]) + ". The Branch Manager may override with a recorded reason", {"warnings": result["warnings"]})
        if not current_user().has_role(*batches_service.CONFIRM_ROLES, branch_id=batch.branch_id):
            raise Forbidden("Only the Branch Manager of this branch can override a scheduling warning")
    items = [(c["starts_at"], c["ends_at"], c["title"], c["topic_id"]) for c in result["classes"]]
    created = class_sessions.create_series(batch, result["trainer"]["user_id"], items,
                                            {"room": result["room"], "override_reason": data.get("override_reason")})
    result["created"] = [s.to_dict() for s in created]
    return result


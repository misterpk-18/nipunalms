"""Class sessions: scoped reads, scheduling (single and weekly), confirm / start / deliver, reschedule and cancel with history
and notices, trainers' reschedule requests, and Meet association.

A session is one dated delivery of a topic to a batch (Module 15 §15). Its stored states keep their names and are shown as
Planned (Scheduled), Confirmed (Scheduled and confirmed), In Progress (Live), Held / Partially Held (Delivered with that
outcome), Rescheduled and Cancelled. Scheduling never marks anything delivered: the trainer starts it and logs the actual
start, end, breaks and any unfulfilled portion, and only Delivered sessions count as taught. A reschedule keeps the row and its
original slot; a cancellation is never a student absence and leaves a replacement owed until a Replacement class or a
recorded waiver accounts for it. Replacement, remedial and extra classes are proposed by the coordinator and approved by the
Branch Manager before students see them (§16). All times are IST for people, timestamptz in the database.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from config.database import db
from config.timezone import IST
from models import Batch, ClassSession, SessionChange, SessionChangeRequest, SessionPerson
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import approvals, audit, delivery_access, delivery_notices, meet, scope
from services import batches as batches_service
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

OPEN_STATES = ("Scheduled", "Rescheduled")
PURPOSES = ("Regular", "Replacement", "Remedial", "Extra")
MEET_IDS = ("meet_space_id", "calendar_event_id", "calendar_series_id", "conference_record_id")
MAX_SESSIONS_PER_REQUEST = 60
MAX_SESSION_HOURS = 12
START_OPENS_BEFORE = timedelta(minutes=60)
START_STAYS_OPEN_AFTER = timedelta(hours=6)
SHORT_NOTICE = timedelta(hours=24)
MEET_LINK = re.compile(r"https://meet\.google\.com/[A-Za-z0-9\-_/?=&.]+")


@dataclass
class SessionRow:
    session: ClassSession
    join: dict | None
    open_request_id: int | None
    changes_count: int


@dataclass
class SessionDetail:
    session: ClassSession
    join: dict | None
    allocated_count: int
    changes: list = field(default_factory=list)
    meet_events: list = field(default_factory=list)
    open_request: SessionChangeRequest | None = None
    organizer_note: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slot(starts_at: datetime, ends_at: datetime) -> str:
    """'Thu 1 Oct 2026, 10:00–12:00 IST'."""
    start, end = starts_at.astimezone(IST), ends_at.astimezone(IST)
    return f"{start:%a} {start.day} {start:%b %Y}, {start:%H:%M}–{end:%H:%M} IST"


# ---------------------------------------------------------------- reads

def assert_can_view_session(session: ClassSession) -> None:
    """Owners of a branch the class serves, the trainers of its batches, the class's own trainer (an approved substitute) and
    learners allocated to one of its batches (up to a transfer out of it); 404 otherwise."""
    branch_ids = scope.visible_branch_ids()
    batch_ids = sessions_repo.session_batch_ids(session.session_id)
    if branch_ids is None or session.batch.branch_id in branch_ids or set(batch_ids) & scope.trainer_batch_ids():
        return
    user = current_user()
    if user.has_role("TRAINER") and session.trainer_user_id == user.user_id:
        return
    if branch_ids and len(batch_ids) > 1 and {b.branch_id for b in map(batches_repo.get_batch, batch_ids[1:])} & branch_ids:
        return
    if sessions_repo.student_can_see_session(scope.student_enrolment_ids(), session.session_id):
        return
    raise NotFound("Class session not found")


def _join_for(session: ClassSession) -> dict | None:
    """Learners get the Join state (and the link only while joining is open); staff read the link directly."""
    if not delivery_access.is_student_only():
        return None
    state = meet.join_state(session, _now())
    return {**state, "url": session.meet_link if state["enabled"] else None}


def list_sessions(filters: dict, page: int, per_page: int) -> tuple[list[SessionRow], dict]:
    """Sessions the user may see in time order (IST date window from / to inclusive)."""
    if filters.get("batch_id"):
        batch = batches_repo.get_batch(filters["batch_id"])
        if batch is None:
            raise NotFound("Batch not found")
        scope.assert_can_view_batch(batch)
    filters = dict(filters)
    if filters.pop("mine", False):
        filters["trainer_user_id"] = actor_id()
    stmt = sessions_repo.list_stmt(filters, scope.visible_branch_ids(), scope.trainer_batch_ids(), scope.student_enrolment_ids())
    sessions, meta = paginate(stmt, page, per_page)
    ids = [s.session_id for s in sessions]
    requests, changes = sessions_repo.open_request_ids(ids), sessions_repo.change_counts(ids)
    return [SessionRow(s, _join_for(s), requests.get(s.session_id), changes.get(s.session_id, 0)) for s in sessions], meta


def get_session(session_id: int) -> SessionDetail:
    session = sessions_repo.get_session(session_id)
    if session is None:
        raise NotFound("Class session not found")
    assert_can_view_session(session)
    allocated = batches_repo.allocated_counts([session.batch_id]).get(session.batch_id, 0)
    if delivery_access.is_student_only():
        return SessionDetail(session, _join_for(session), allocated)
    return SessionDetail(session, None, allocated, changes=sessions_repo.changes(session_id), meet_events=sessions_repo.meet_events(session_id),
                         open_request=sessions_repo.open_request(session_id), organizer_note=meet.integration_note())


def delivered_sessions(batch_id: int) -> list[ClassSession]:
    """The sessions of a batch that were actually taught (state Delivered), oldest first. For attendance and progress."""
    return sessions_repo.delivered_in_batch(batch_id)


def sessions_for_enrolment(enrolment_id: int) -> list[ClassSession]:
    """Every session of the batches the enrolment is (or was) allocated to, in time order. A batch it was transferred out of
    counts only up to the transfer. No scope check: callers apply their own."""
    return list(db.session.execute(sessions_repo.student_sessions_stmt({enrolment_id})).scalars())


# ---------------------------------------------------------------- loading for a change

def _load_for_change(session_id: int, *, allow_own_trainer: bool = False) -> ClassSession:
    """The session, row-locked: 404 outside the user's scope; 403 unless they manage its branch (or, when allowed, teach it)."""
    session = sessions_repo.get_session_for_update(session_id)
    if session is None:
        raise NotFound("Class session not found")
    assert_can_view_session(session)
    user = current_user()
    teaches = allow_own_trainer and user.has_role("TRAINER") and session.trainer_user_id == user.user_id
    if not (delivery_access.can_manage_branch(session.batch.branch_id) or teaches):
        raise Forbidden("You don't have access to this action")
    return session


def _require_open(session: ClassSession, action: str) -> None:
    if session.state not in OPEN_STATES:
        raise BusinessRule(f"Session {session.session_code} is {session.state} and cannot be {action}")


def _check_conflicts(batch: Batch, trainer_user_id: int, starts_at: datetime, ends_at: datetime, room: str | None, *,
                     override_reason: str | None, exclude_session_id: int | None = None, advisory: bool = True) -> list[str]:
    """Module 15 §10. Blocked (cannot be overridden): the trainer, or a host / backup / assistant of the class, already has
    a class then. Advisory: the room is booked, or the class's students have another class then. Only the Branch Manager
    (or a Super Admin) overrides an advisory warning, with a recorded reason. Returns the warnings overridden."""
    clash = sessions_repo.trainer_conflict(trainer_user_id, starts_at, ends_at, exclude_session_id)
    if clash is not None:
        raise BusinessRule(f"The trainer already teaches {clash.session_code} ({clash.title}) on {_slot(clash.starts_at, clash.ends_at)}")
    if exclude_session_id:
        helpers = [p.user_id for p in _people(exclude_session_id) if p.user_id and p.role != "Host"]
        busy = sessions_repo.people_conflict(helpers, starts_at, ends_at, exclude_session_id)
        if busy is not None:
            raise BusinessRule(f"A backup or assistant of this class is busy with {busy.session_code} on {_slot(busy.starts_at, busy.ends_at)}")
    if not advisory:
        return []
    warnings = []
    if room:
        booked = sessions_repo.room_conflict(batch.branch_id, room, starts_at, ends_at, exclude_session_id)
        if booked is not None:
            warnings.append(f"{room} is already used by {booked.session_code} ({booked.title}) on {_slot(booked.starts_at, booked.ends_at)}")
    batch_ids = sessions_repo.session_batch_ids(exclude_session_id) if exclude_session_id else [batch.batch_id]
    others = sessions_repo.student_conflicts(batch_ids, starts_at, ends_at, exclude_session_id)
    if others:
        warnings.append("Students of this class also attend " + ", ".join(f"{o.session_code} ({o.batch.batch_code})" for o in others))
    if warnings:
        if not override_reason:
            raise BusinessRule("; ".join(warnings) + ". The Branch Manager may override with a recorded reason", {"warnings": warnings})
        if not current_user().has_role(*batches_service.CONFIRM_ROLES, branch_id=batch.branch_id):
            raise Forbidden("Only the Branch Manager of this branch or a Super Admin can override a scheduling warning")
    return warnings


def _people(session_id: int) -> list[SessionPerson]:
    return list(db.session.execute(select(SessionPerson).where(SessionPerson.session_id == session_id,
                                                               SessionPerson.removed_at.is_(None))).scalars())


def _check_future(starts_at: datetime, ends_at: datetime, field: str = "starts_at") -> None:
    if ends_at <= starts_at:
        raise ValidationError("Invalid time", {"ends_at": ["Must be after the start"]})
    if ends_at - starts_at > timedelta(hours=MAX_SESSION_HOURS):
        raise ValidationError("Invalid time", {"ends_at": [f"A class runs at most {MAX_SESSION_HOURS} hours"]})
    if starts_at <= _now():
        raise ValidationError("Invalid time", {field: ["Schedule in the future"]})


def _valid_topic(batch: Batch, topic_id: int) -> None:
    topic = catalog_repo.get_topic(topic_id)
    if topic is None or topic.module.version.course_id != batch.course_id:
        raise ValidationError("Invalid topic", {"topic_id": ["Not a topic of this batch's course"]})


def _assigned_trainer(batch: Batch, trainer_user_id: int) -> None:
    if trainer_user_id not in {t.trainer_user_id for t in batch.trainers if t.to_date is None}:
        raise ValidationError("Invalid trainer", {"trainer_user_id": ["Not currently assigned to this batch; request cover instead"]})


def _notify_students(session: ClassSession, *, title: str, body: str, event_key: str) -> None:
    """The students of every batch the class serves (a shared class has several)."""
    for batch_id in sessions_repo.session_batch_ids(session.session_id):
        delivery_notices.notify_batch_students(batch_id, title=title, body=body, event_key=event_key, link=f"/sessions/{session.session_id}",
                                               branch_id=session.batch.branch_id)


# ---------------------------------------------------------------- create

def _occurrences(starts_at: datetime, ends_at: datetime, recurrence: dict | None) -> list[tuple[datetime, datetime]]:
    """The first slot, or the weekly pattern: the same IST clock time on the chosen weekdays (Monday = 0) until `until` / `count` sessions."""
    if not recurrence:
        return [(starts_at, ends_at)]
    first = starts_at.astimezone(IST)
    duration = ends_at - starts_at
    weekdays = set(recurrence.get("weekdays") or [first.weekday()])
    count, until = recurrence.get("count"), recurrence.get("until")
    slots, day = [], first.date()
    while len(slots) < (count or MAX_SESSIONS_PER_REQUEST) and (until is None or day <= until) and day <= first.date() + timedelta(weeks=52):
        if day.weekday() in weekdays:
            begin = datetime.combine(day, first.timetz().replace(tzinfo=None), tzinfo=IST)
            slots.append((begin, begin + duration))
        day += timedelta(days=1)
    return slots


def _validate_purpose(batch: Batch, data: dict) -> None:
    """Module 15 §16: a Replacement names the cancelled or undelivered class it delivers; a Remedial class names its evidence
    and recovery plan; an Extra class names the approved addition. Each has an owner and a deadline."""
    purpose = data.get("purpose", "Regular")
    if purpose == "Regular":
        return
    if purpose == "Replacement":
        original = sessions_repo.get_session(data.get("replaces_session_id") or 0)
        if original is None or original.batch_id != batch.batch_id:
            raise ValidationError("Invalid replacement", {"replaces_session_id": ["Name a class of this batch"]})
        if not (original.state == "Cancelled" or original.delivery_outcome == "Partially Held"):
            raise ValidationError("Invalid replacement", {"replaces_session_id": ["Only a cancelled or partially held class is replaced"]})
        data.setdefault("topic_id", original.topic_id)
    elif not data.get("purpose_reference"):
        raise ValidationError("A reference is required", {"purpose_reference": [
            "The evidence and individual recovery plan" if purpose == "Remedial" else "The approved addition"]})
    if not data.get("owner_user_id") or not data.get("due_on"):
        raise ValidationError("An owner and deadline are required", {"owner_user_id": ["Name who sees it through, and by when (due_on)"]})


def create_sessions(data: dict) -> list[ClassSession]:
    """Schedule one class, or a weekly series (`recurrence`: weekdays, and count or until). All or nothing. A replacement,
    remedial or extra class waits for the Branch Manager's approval before its students are told."""
    batch = batches_service.load_managed_batch(data["batch_id"])
    if batch.state in batches_service.CLOSED_STATES or batch.state == "On Hold":
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    _check_future(data["starts_at"], data["ends_at"])
    _validate_purpose(batch, data)
    purpose = data.get("purpose", "Regular")
    if purpose != "Regular" and data.get("recurrence"):
        raise ValidationError("One class at a time", {"recurrence": [f"A {purpose.lower()} class is scheduled singly"]})
    trainer_id = data.get("trainer_user_id")
    if trainer_id is None:
        lead = batches_repo.lead_trainer(batch.batch_id)
        if lead is None:
            raise ValidationError("Invalid trainer", {"trainer_user_id": ["The batch has no lead trainer; choose a trainer"]})
        trainer_id = lead.trainer_user_id
    _assigned_trainer(batch, trainer_id)
    if data.get("topic_id"):
        _valid_topic(batch, data["topic_id"])

    slots = _occurrences(data["starts_at"], data["ends_at"], data.get("recurrence"))
    if len(slots) > MAX_SESSIONS_PER_REQUEST:
        raise ValidationError("Too many sessions", {"recurrence": [f"At most {MAX_SESSIONS_PER_REQUEST} sessions at a time"]})
    mode = data.get("mode") or batch.mode
    created = []
    pending = purpose != "Regular"
    for begin, finish in slots:
        overridden = _check_conflicts(batch, trainer_id, begin, finish, data.get("room"), override_reason=data.get("override_reason"))
        session = ClassSession(batch_id=batch.batch_id, topic_id=data.get("topic_id"), title=data["title"], starts_at=begin, ends_at=finish,
                               mode=mode, trainer_user_id=trainer_id, room=data.get("room"), notes=data.get("notes"),
                               meet_status=meet.initial_status(mode), purpose=purpose, replaces_session_id=data.get("replaces_session_id"),
                               purpose_reference=data.get("purpose_reference"), owner_user_id=data.get("owner_user_id"),
                               due_on=data.get("due_on"), approval_status="Pending" if pending else "Not Required",
                               proposed_by=actor_id() if pending else None,
                               room_override_reason=data.get("override_reason") if overridden else None,
                               **{k: data[k] for k in MEET_IDS if data.get(k)})
        db.session.add(session)
        db.session.flush()  # keeps later occurrences of the same series from clashing with this one
        if session.meet_status != "Not Required":
            db.session.refresh(session)
            meet.record(session, "Requested", "Awaiting the organizer link (" + meet.integration_note() + ")")
        created.append(session)

    first = created[0]
    audit.record("SESSION_CREATED", "class_session", first.session_id, branch_id=batch.branch_id,
                 new={"batch_id": batch.batch_id, "count": len(created), "first_starts_at": first.starts_at, "title": first.title,
                      "purpose": purpose, "override_reason": first.room_override_reason})
    if pending:
        delivery_notices.notify_users(users_repo.user_ids_with_role("BRANCH_MANAGER", batch.branch_id), category="Session",
                                      action_required=True, title=f"Approve a {purpose.lower()} class: {first.title}",
                                      body=f"{batch.batch_code} · {_slot(first.starts_at, first.ends_at)}",
                                      event_key=f"session-purpose-{first.session_id}", link="/academic/schedule", branch_id=batch.branch_id)
        return created
    if len(created) == 1:
        title, body = f"New class: {first.title}", _slot(first.starts_at, first.ends_at)
    else:
        title, body = f"{len(created)} new classes: {first.title}", f"From {_slot(first.starts_at, first.ends_at)}"
    delivery_notices.notify_batch_students(batch.batch_id, title=title, body=body, event_key=f"sessions-created-{first.session_id}",
                                           link=f"/sessions/{first.session_id}", branch_id=batch.branch_id)
    delivery_notices.notify_users([trainer_id], title=title, body=body, event_key=f"sessions-created-{first.session_id}",
                                  link="/trainer/sessions", branch_id=batch.branch_id)
    return created


def decide_purpose(session_id: int, decision: str, note: str | None) -> ClassSession:
    """The Branch Manager (or Super Admin), not the proposer, approves the trainer, time and resources of a replacement,
    remedial or extra class. A rejected proposal is cancelled and owes nothing."""
    session = _load_for_change(session_id)
    if not current_user().has_role(*batches_service.CONFIRM_ROLES, branch_id=session.batch.branch_id):
        raise Forbidden("Only the Branch Manager of this branch or a Super Admin approves this class")
    if session.approval_status != "Pending":
        raise BusinessRule(f"Session {session.session_code} is not waiting for approval")
    approvals.require_independent(session.proposed_by, message="The person who proposed the class cannot approve it")
    session.approved_by, session.approved_at = actor_id(), _now()
    if decision == "Rejected":
        if not note:
            raise ValidationError("A reason is required", {"note": ["Say why the class is not approved"]})
        session.approval_status = "Rejected"
        change = _change(session, "Cancelled", f"Not approved: {note}")
        session.state = "Cancelled"
        db.session.add(change)
        db.session.flush()
        return session
    session.approval_status = "Approved"
    db.session.flush()
    audit.record("SESSION_PURPOSE_APPROVED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=note,
                 new={"purpose": session.purpose, "replaces_session_id": session.replaces_session_id})
    title, body = f"New {session.purpose.lower()} class: {session.title}", _slot(session.starts_at, session.ends_at)
    _notify_students(session, title=title, body=body, event_key=f"sessions-created-{session.session_id}")
    delivery_notices.notify_users([session.trainer_user_id, session.proposed_by], title=title, body=body,
                                  event_key=f"sessions-created-{session.session_id}", link="/trainer/sessions", branch_id=session.batch.branch_id)
    return session


def confirm(session_id: int) -> ClassSession:
    """Planned -> Confirmed: an approved class with its trainer and room, and for an online class the organizer's link and a
    named backup host (Module 16 §3, §5)."""
    session = _load_for_change(session_id)
    _require_open(session, "confirmed")
    if session.approval_status == "Pending":
        raise BusinessRule("The Branch Manager has not approved this class yet")
    missing = []
    if session.mode in ("Classroom", "Hybrid") and not session.room:
        missing.append("a room")
    if session.mode != "Classroom":
        if session.meet_status != "Linked":
            missing.append("the organizer's Meet link")
        if not any(p.role == "Backup" for p in _people(session.session_id)):
            missing.append("a named backup host")
    if missing:
        raise BusinessRule(f"Session {session.session_code} cannot be confirmed without " + ", ".join(missing))
    session.confirmed_at, session.confirmed_by = _now(), actor_id()
    db.session.flush()
    audit.record("SESSION_CONFIRMED", "class_session", session.session_id, branch_id=session.batch.branch_id)
    return session


def waive_replacement(session_id: int, reason: str) -> ClassSession:
    """A cancelled class that needs no replacement (the topic was covered elsewhere, the learning was accounted for)."""
    session = _load_for_change(session_id)
    if session.state != "Cancelled":
        raise BusinessRule("Only a cancelled class can have its replacement waived")
    session.replacement_waiver = reason
    db.session.flush()
    audit.record("SESSION_REPLACEMENT_WAIVED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=reason)
    return session


# ---------------------------------------------------------------- edit, reschedule, cancel

def update_session(session_id: int, data: dict) -> ClassSession:
    """Title, topic, room, notes, mode and (with a reason) a substitute trainer. Time changes are reschedules."""
    session = _load_for_change(session_id)
    _require_open(session, "edited")
    batch = session.batch
    old = {"title": session.title, "topic_id": session.topic_id, "room": session.room, "mode": session.mode,
           "trainer_user_id": session.trainer_user_id, "notes": session.notes}

    if "topic_id" in data and data["topic_id"] is not None:
        _valid_topic(batch, data["topic_id"])
    if "trainer_user_id" in data and data["trainer_user_id"] != session.trainer_user_id:
        if not data.get("reason"):
            raise ValidationError("A reason is required", {"reason": ["Required to change the trainer"]})
        if not current_user().has_role(*batches_service.CONFIRM_ROLES, branch_id=batch.branch_id):
            raise Forbidden("The Branch Manager approves a change of trainer; request cover for the class instead")
        _assigned_trainer(batch, data["trainer_user_id"])
        _check_conflicts(batch, data["trainer_user_id"], session.starts_at, session.ends_at, None, override_reason=None,
                         exclude_session_id=session.session_id, advisory=False)
        change = _change(session, "Trainer changed", data["reason"], new_trainer=data["trainer_user_id"])
        db.session.add(change)
        db.session.flush()
        session.trainer_user_id = data["trainer_user_id"]
        delivery_notices.notify_users([data["trainer_user_id"], old["trainer_user_id"]], title=f"Trainer changed: {session.title}",
                                      body=f"{_slot(session.starts_at, session.ends_at)}. {data['reason']}",
                                      event_key=f"session-change-{change.change_id}", link="/trainer/sessions", branch_id=batch.branch_id)
    if "room" in data and data["room"] and data["room"] != session.room:
        if _check_conflicts(batch, session.trainer_user_id, session.starts_at, session.ends_at, data["room"],
                            override_reason=data.get("override_reason"), exclude_session_id=session.session_id):
            session.room_override_reason = data["override_reason"]
    for name in ("title", "topic_id", "room", "notes", *MEET_IDS):
        if name in data:
            setattr(session, name, data[name])
    if "mode" in data and data["mode"] != session.mode:
        _change_mode(session, data["mode"])
    db.session.flush()
    db.session.refresh(session)
    audit.record("SESSION_UPDATED", "class_session", session.session_id, branch_id=batch.branch_id, old=old,
                 new={"title": session.title, "topic_id": session.topic_id, "room": session.room, "mode": session.mode,
                      "trainer_user_id": session.trainer_user_id, "notes": session.notes}, reason=data.get("reason"))
    return session


def _change_mode(session: ClassSession, mode: str) -> None:
    """A classroom class needs no Meet; a class that becomes online waits for its organizer link."""
    session.mode = mode
    if mode == "Classroom":
        session.meet_link, session.meet_status = None, "Not Required"
    elif session.meet_status == "Not Required":
        session.meet_status = "Pending Verification"
        db.session.flush()
        meet.record(session, "Requested", "Class became " + mode)


def _change(session: ClassSession, change_type: str, reason: str, *, new_start: datetime | None = None, new_end: datetime | None = None,
            new_trainer: int | None = None, emergency: dict | None = None) -> SessionChange:
    notice = session.starts_at - _now()
    return SessionChange(session_id=session.session_id, change_type=change_type, reason=reason, old_starts_at=session.starts_at,
                         old_ends_at=session.ends_at, new_starts_at=new_start, new_ends_at=new_end, old_trainer_user_id=session.trainer_user_id,
                         new_trainer_user_id=new_trainer, notice_hours=round(notice.total_seconds() / 3600, 1),
                         short_notice=notice < SHORT_NOTICE, changed_by=actor_id(),
                         emergency_reason=(emergency or {}).get("emergency_reason"), next_action=(emergency or {}).get("next_action"))


def _require_emergency_detail(session: ClassSession, emergency: dict | None) -> None:
    """Module 15 §14: less than 24 hours' notice is an emergency; say why advance notice was impossible and what happens next."""
    if session.starts_at - _now() >= SHORT_NOTICE or session.approval_status == "Pending":
        return
    missing = [f for f in ("emergency_reason", "next_action") if not (emergency or {}).get(f)]
    if missing:
        raise ValidationError("Less than 24 hours' notice", {f: ["Required for a change inside 24 hours"] for f in missing})


def _notify_change(session: ClassSession, change: SessionChange, title: str, body: str) -> None:
    if session.approval_status == "Pending":
        return  # its students were never told about it
    key = f"session-change-{change.change_id}"
    notice = ""
    if change.short_notice:
        notice = " Short notice (less than 24 hours)."
        if change.emergency_reason:
            notice += f" Why: {change.emergency_reason}. Next: {change.next_action}."
    _notify_students(session, title=title, body=body + notice, event_key=key)
    delivery_notices.notify_users([session.trainer_user_id], title=title, body=body + notice, event_key=key, link="/trainer/sessions",
                                  branch_id=session.batch.branch_id)


def _apply_reschedule(session: ClassSession, starts_at: datetime, ends_at: datetime, reason: str, *, override_reason: str | None,
                      emergency: dict | None = None) -> SessionChange:
    _require_open(session, "rescheduled")
    _check_future(starts_at, ends_at, "starts_at")
    _require_emergency_detail(session, emergency)
    if _check_conflicts(session.batch, session.trainer_user_id, starts_at, ends_at, session.room, override_reason=override_reason,
                        exclude_session_id=session.session_id):
        session.room_override_reason = override_reason
    change = _change(session, "Rescheduled", reason, new_start=starts_at, new_end=ends_at, emergency=emergency)
    old_slot = _slot(session.starts_at, session.ends_at)
    session.starts_at, session.ends_at, session.state = starts_at, ends_at, "Rescheduled"
    session.confirmed_at = session.confirmed_by = None  # a moved class is confirmed again
    db.session.add(change)
    db.session.flush()
    audit.record("SESSION_RESCHEDULED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=reason,
                 old={"starts_at": change.old_starts_at, "ends_at": change.old_ends_at}, new={"starts_at": starts_at, "ends_at": ends_at})
    _notify_change(session, change, f"Class rescheduled: {session.title}", f"Was {old_slot}; now {_slot(starts_at, ends_at)}. {reason}")
    return change


def reschedule(session_id: int, starts_at: datetime, ends_at: datetime, reason: str, override_reason: str | None = None,
               emergency: dict | None = None) -> ClassSession:
    session = _load_for_change(session_id)
    _apply_reschedule(session, starts_at, ends_at, reason, override_reason=override_reason, emergency=emergency)
    return session


def cancel(session_id: int, reason: str, emergency: dict | None = None) -> ClassSession:
    """Cancel an upcoming class. The batch's students and the trainer are told; a cancelled class is never a student absence,
    and it owes a replacement until one is scheduled or a waiver is recorded."""
    session = _load_for_change(session_id)
    _require_open(session, "cancelled")
    _require_emergency_detail(session, emergency)
    change = _change(session, "Cancelled", reason, emergency=emergency)
    slot = _slot(session.starts_at, session.ends_at)
    session.state = "Cancelled"
    db.session.add(change)
    pending = sessions_repo.open_request(session.session_id)
    if pending is not None:
        pending.status, pending.decided_by, pending.decided_at, pending.decision_note = "Rejected", actor_id(), _now(), "The session was cancelled"
    db.session.flush()
    audit.record("SESSION_CANCELLED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=reason,
                 old={"state": "Scheduled", "starts_at": change.old_starts_at})
    _notify_change(session, change, f"Class cancelled: {session.title}", f"{slot}. {reason}")
    return session


# ---------------------------------------------------------------- teaching: start, deliver

def start(session_id: int) -> ClassSession:
    """The trainer (or a manager covering) opens the class: Scheduled / Rescheduled -> Live, from 60 minutes before it begins."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    _require_open(session, "started")
    now = _now()
    if now < session.starts_at - START_OPENS_BEFORE:
        raise BusinessRule("A class can be started up to 60 minutes before it begins")
    if now > session.ends_at + START_STAYS_OPEN_AFTER:
        raise BusinessRule("This class ended more than 6 hours ago; mark it Delivered instead")
    if session.approval_status == "Pending":
        raise BusinessRule("The Branch Manager has not approved this class yet")
    session.state, session.live_at = "Live", now
    db.session.flush()
    return session


def deliver(session_id: int, log: dict) -> ClassSession:
    """The trainer's class log (Module 15 §15, Module 16 §7): Live (or an open class whose time has begun) -> Delivered, with
    the actual start and end, breaks, delivered minutes, and Held or Partially Held with what was not delivered. Missing times
    default to when the class was started and its scheduled end."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    if session.state not in ("Live", *OPEN_STATES):
        raise BusinessRule(f"Session {session.session_id} is {session.state} and cannot be marked Delivered")
    if session.approval_status == "Pending":
        raise BusinessRule("The Branch Manager has not approved this class yet")
    now = _now()
    if session.state != "Live" and now < session.starts_at:
        raise BusinessRule("The class has not started yet")
    actual_start = log.get("actual_start") or session.live_at or session.starts_at
    actual_end = log.get("actual_end") or (min(now, session.ends_at) if now > actual_start else session.ends_at)
    if actual_end <= actual_start:
        raise ValidationError("Invalid times", {"actual_end": ["Must be after the actual start"]})
    if actual_end > now + timedelta(minutes=5):
        raise ValidationError("Invalid times", {"actual_end": ["Cannot be in the future"]})
    breaks = log.get("break_minutes") or 0
    minutes = int((actual_end - actual_start).total_seconds() // 60) - breaks
    if minutes < 0:
        raise ValidationError("Invalid breaks", {"break_minutes": ["Breaks are longer than the class"]})
    outcome = log.get("outcome") or "Held"
    if outcome == "Partially Held" and not log.get("unfulfilled_note"):
        raise ValidationError("Say what was not delivered", {"unfulfilled_note": ["Required for a partially held class"]})
    session.state, session.delivered_at, session.delivery_outcome = "Delivered", now, outcome
    session.actual_start, session.actual_end, session.break_minutes, session.delivered_minutes = actual_start, actual_end, breaks, minutes
    session.unfulfilled_note = log.get("unfulfilled_note") if outcome == "Partially Held" else None
    if log.get("notes"):
        session.notes = log["notes"]
    db.session.flush()
    audit.record("SESSION_DELIVERED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"delivered_at": now, "starts_at": session.starts_at, "outcome": outcome, "delivered_minutes": minutes,
                      "planned_minutes": session.planned_minutes})
    if outcome == "Partially Held":
        delivery_notices.notify_branch_managers(session.batch.branch_id, title=f"Partially held: {session.title}", category="Session",
                                                body=f"{session.batch.batch_code} · {session.unfulfilled_note}", action_required=True,
                                                event_key=f"session-partial-{session.session_id}", link="/academic/schedule")
    return session


def save_notes(session_id: int, notes: str) -> ClassSession:
    """Session notes at close-out: the teaching trainer (or a manager covering) writes them once the class is Live or Delivered."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    if session.state not in ("Live", "Delivered"):
        raise BusinessRule(f"Notes can be saved once the class is Live or Delivered (this one is {session.state})")
    previous, session.notes = session.notes, notes
    db.session.flush()
    audit.record("SESSION_NOTES_SAVED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 old={"notes": previous}, new={"notes": notes})
    return session


# ---------------------------------------------------------------- reschedule requests

def request_reschedule(session_id: int, proposed_starts_at: datetime, proposed_ends_at: datetime, reason: str) -> SessionChangeRequest:
    """A trainer asks to move a class they teach; the branch's coordinators and manager decide."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    _require_open(session, "rescheduled")
    _check_future(proposed_starts_at, proposed_ends_at, "proposed_starts_at")
    if sessions_repo.open_request(session.session_id) is not None:
        raise Conflict("This session already has an open reschedule request")
    request = SessionChangeRequest(session_id=session.session_id, requested_by=actor_id(), proposed_starts_at=proposed_starts_at,
                                   proposed_ends_at=proposed_ends_at, reason=reason)
    db.session.add(request)
    db.session.flush()
    delivery_notices.notify_branch_managers(
        session.batch.branch_id, title=f"Reschedule requested: {session.title}", category="Session", action_required=True,
        body=f"{session.trainer.full_name} asks to move {_slot(session.starts_at, session.ends_at)} to {_slot(proposed_starts_at, proposed_ends_at)}. {reason}",
        event_key=f"reschedule-request-{request.request_id}", link="/academic/schedule")
    return request


def list_requests(filters: dict, page: int, per_page: int) -> tuple[list[SessionChangeRequest], dict]:
    if delivery_access.is_student_only():
        raise Forbidden("You don't have access to this action")
    return paginate(sessions_repo.requests_stmt(filters, scope.visible_branch_ids(), scope.trainer_batch_ids()), page, per_page)


def _load_request(request_id: int) -> SessionChangeRequest:
    request = sessions_repo.get_request_for_update(request_id)
    if request is None:
        raise NotFound("Reschedule request not found")
    assert_can_view_session(request.session)
    delivery_access.assert_can_manage_branch(request.session.batch.branch_id)
    if request.status != "Open":
        raise BusinessRule(f"The request is already {request.status}")
    return request


def approve_request(request_id: int, note: str | None, override_reason: str | None = None,
                    emergency: dict | None = None) -> SessionChangeRequest:
    """Approving moves the session to the proposed slot (the same checks and notices as a direct reschedule)."""
    request = _load_request(request_id)
    session = sessions_repo.get_session_for_update(request.session_id)
    _apply_reschedule(session, request.proposed_starts_at, request.proposed_ends_at, f"Trainer request: {request.reason}",
                      override_reason=override_reason, emergency=emergency)
    request.status, request.decided_by, request.decided_at, request.decision_note = "Approved", actor_id(), _now(), note
    db.session.flush()
    delivery_notices.notify_users([request.requested_by], title=f"Reschedule approved: {session.title}", category="Session",
                                  body=f"Now {_slot(session.starts_at, session.ends_at)}", event_key=f"reschedule-decision-{request.request_id}",
                                  link="/trainer/sessions", branch_id=session.batch.branch_id)
    return request


def reject_request(request_id: int, note: str) -> SessionChangeRequest:
    request = _load_request(request_id)
    request.status, request.decided_by, request.decided_at, request.decision_note = "Rejected", actor_id(), _now(), note
    db.session.flush()
    delivery_notices.notify_users([request.requested_by], title=f"Reschedule not approved: {request.session.title}", category="Session", body=note,
                                  event_key=f"reschedule-decision-{request.request_id}", link="/trainer/sessions",
                                  branch_id=request.session.batch.branch_id)
    return request


# ---------------------------------------------------------------- Meet association (recorded, never called)

def _load_online_session(session_id: int) -> ClassSession:
    session = _load_for_change(session_id)
    _require_open(session, "changed")
    if session.mode == "Classroom":
        raise BusinessRule("A classroom session has no Meet")
    return session


def associate_meet(session_id: int, meet_link: str, ids: dict | None = None) -> ClassSession:
    """Record the organizer's Meet link for an online class (the manual entry Module 16 allows while automatic creation is
    unverified), with the Meet space, Calendar event / series and conference identifiers when known. One link never serves
    unrelated batches (§3): a link already used by another batch's open class is refused."""
    if not MEET_LINK.fullmatch(meet_link):
        raise ValidationError("Invalid Meet link", {"meet_link": ["Must be a https://meet.google.com/… link"]})
    session = _load_online_session(session_id)
    other = meet.link_used_elsewhere(meet_link, session)
    if other is not None:
        raise BusinessRule(f"That link is used by {other.session_code} of batch {other.batch.batch_code}; each batch needs its own link")
    session.meet_link, session.meet_status = meet_link, "Linked"
    for key, value in (ids or {}).items():
        if key in MEET_IDS and value:
            setattr(session, key, value)
    db.session.flush()
    meet.record(session, "Link associated", "Entered manually; " + meet.integration_note())
    audit.record("MEET_LINK_SET", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"meet_link": meet_link, **{k: v for k, v in (ids or {}).items() if v}})
    return session


def mark_meet_failed(session_id: int, detail: str) -> ClassSession:
    """The association could not be made: the class shows Failed and the branch owners get a recovery task."""
    session = _load_online_session(session_id)
    session.meet_link, session.meet_status = None, "Unavailable"
    db.session.flush()
    event = meet.record(session, "Association failed", detail)
    db.session.flush()
    delivery_notices.notify_branch_managers(
        session.batch.branch_id, title=f"Meet association failed: {session.title}", category="Session", action_required=True,
        body=f"{_slot(session.starts_at, session.ends_at)}. {detail}", event_key=f"meet-failed-{event.event_id}", link="/academic/schedule")
    return session


def reset_meet(session_id: int) -> ClassSession:
    """Retry: remove the link or the failure and go back to Pending Verification (idempotent)."""
    session = _load_online_session(session_id)
    if session.meet_status == "Pending Verification":
        return session
    event = "Link removed" if session.meet_status == "Linked" else "Association retried"
    session.meet_link, session.meet_status = None, "Pending Verification"
    db.session.flush()
    meet.record(session, event)
    return session


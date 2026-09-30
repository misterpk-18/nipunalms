"""Class sessions: scoped reads, scheduling (single and weekly), start / deliver, reschedule and cancel with history and
notices, trainers' reschedule requests, and Meet association.

A session is one dated delivery of a topic to a batch. Scheduling a session never marks anything delivered: a trainer starts
it (Live) and marks it Delivered, and only Delivered sessions count as taught (S4 attendance reads them through
`delivered_sessions`). A reschedule keeps the same row (state Rescheduled) and writes the original slot to `session_changes`;
a cancellation is never a student absence. All times are IST for people, timestamptz in the database.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config.database import db
from config.timezone import IST
from models import Batch, ClassSession, SessionChange, SessionChangeRequest
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import class_sessions as sessions_repo
from repositories.common import paginate
from services import audit, delivery_access, delivery_notices, meet, scope
from services import batches as batches_service
from services.context import actor_id, current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

OPEN_STATES = ("Scheduled", "Rescheduled")
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
    """Branch owners, the batch's trainers, and learners allocated to the batch (up to a transfer out of it); 404 otherwise."""
    branch_ids = scope.visible_branch_ids()
    if branch_ids is None or session.batch.branch_id in branch_ids or session.batch_id in scope.trainer_batch_ids():
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
                     acknowledge_room: bool, exclude_session_id: int | None = None) -> None:
    """A trainer cannot teach two classes at once (blocked). A room already booked is a warning to acknowledge."""
    clash = sessions_repo.trainer_conflict(trainer_user_id, starts_at, ends_at, exclude_session_id)
    if clash is not None:
        raise BusinessRule(f"The trainer already teaches {clash.session_code} ({clash.title}) on {_slot(clash.starts_at, clash.ends_at)}")
    if room:
        booked = sessions_repo.room_conflict(batch.branch_id, room, starts_at, ends_at, exclude_session_id)
        if booked is not None and not acknowledge_room:
            raise BusinessRule(f"{room} is already used by {booked.session_code} ({booked.title}) on {_slot(booked.starts_at, booked.ends_at)}; "
                               "confirm to double-book it", {"room": [f"Already booked for {booked.session_code}"]})


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
        raise ValidationError("Invalid trainer", {"trainer_user_id": ["Not currently assigned to this batch"]})


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


def create_sessions(data: dict) -> list[ClassSession]:
    """Schedule one class, or a weekly series (`recurrence`: weekdays, and count or until). All or nothing."""
    batch = batches_service.load_managed_batch(data["batch_id"])
    if batch.state in batches_service.CLOSED_STATES:
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    _check_future(data["starts_at"], data["ends_at"])
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
    for begin, finish in slots:
        _check_conflicts(batch, trainer_id, begin, finish, data.get("room"), acknowledge_room=data.get("acknowledge_room_conflict", False))
        session = ClassSession(batch_id=batch.batch_id, topic_id=data.get("topic_id"), title=data["title"], starts_at=begin, ends_at=finish,
                               mode=mode, trainer_user_id=trainer_id, room=data.get("room"), notes=data.get("notes"),
                               meet_status=meet.initial_status(mode))
        db.session.add(session)
        db.session.flush()  # keeps later occurrences of the same series from clashing with this one
        if session.meet_status != "Not Required":
            db.session.refresh(session)
            meet.record(session, "Requested", "Awaiting the organizer link (" + meet.integration_note() + ")")
        created.append(session)

    first = created[0]
    audit.record("SESSION_CREATED", "class_session", first.session_id, branch_id=batch.branch_id,
                 new={"batch_id": batch.batch_id, "count": len(created), "first_starts_at": first.starts_at, "title": first.title})
    if len(created) == 1:
        title, body = f"New class: {first.title}", _slot(first.starts_at, first.ends_at)
    else:
        title, body = f"{len(created)} new classes: {first.title}", f"From {_slot(first.starts_at, first.ends_at)}"
    delivery_notices.notify_batch_students(batch.batch_id, title=title, body=body, event_key=f"sessions-created-{first.session_id}",
                                           link=f"/sessions/{first.session_id}", branch_id=batch.branch_id)
    delivery_notices.notify_users([trainer_id], title=title, body=body, event_key=f"sessions-created-{first.session_id}",
                                  link="/trainer/sessions", branch_id=batch.branch_id)
    return created


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
        _assigned_trainer(batch, data["trainer_user_id"])
        _check_conflicts(batch, data["trainer_user_id"], session.starts_at, session.ends_at, None, acknowledge_room=True,
                         exclude_session_id=session.session_id)
        change = _change(session, "Trainer changed", data["reason"], new_trainer=data["trainer_user_id"])
        db.session.add(change)
        db.session.flush()
        session.trainer_user_id = data["trainer_user_id"]
        delivery_notices.notify_users([data["trainer_user_id"], old["trainer_user_id"]], title=f"Trainer changed: {session.title}",
                                      body=f"{_slot(session.starts_at, session.ends_at)}. {data['reason']}",
                                      event_key=f"session-change-{change.change_id}", link="/trainer/sessions", branch_id=batch.branch_id)
    if "room" in data and data["room"] and data["room"] != session.room:
        _check_conflicts(batch, session.trainer_user_id, session.starts_at, session.ends_at, data["room"],
                         acknowledge_room=data.get("acknowledge_room_conflict", False), exclude_session_id=session.session_id)
    for name in ("title", "topic_id", "room", "notes"):
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
            new_trainer: int | None = None) -> SessionChange:
    notice = session.starts_at - _now()
    return SessionChange(session_id=session.session_id, change_type=change_type, reason=reason, old_starts_at=session.starts_at,
                         old_ends_at=session.ends_at, new_starts_at=new_start, new_ends_at=new_end, old_trainer_user_id=session.trainer_user_id,
                         new_trainer_user_id=new_trainer, notice_hours=round(notice.total_seconds() / 3600, 1),
                         short_notice=notice < SHORT_NOTICE, changed_by=actor_id())


def _notify_change(session: ClassSession, change: SessionChange, title: str, body: str) -> None:
    key = f"session-change-{change.change_id}"
    notice = " Short notice (less than 24 hours)." if change.short_notice else ""
    delivery_notices.notify_batch_students(session.batch_id, title=title, body=body + notice, event_key=key, link=f"/sessions/{session.session_id}",
                                           branch_id=session.batch.branch_id)
    delivery_notices.notify_users([session.trainer_user_id], title=title, body=body + notice, event_key=key, link="/trainer/sessions",
                                  branch_id=session.batch.branch_id)


def _apply_reschedule(session: ClassSession, starts_at: datetime, ends_at: datetime, reason: str, *, acknowledge_room: bool) -> SessionChange:
    _require_open(session, "rescheduled")
    _check_future(starts_at, ends_at, "starts_at")
    _check_conflicts(session.batch, session.trainer_user_id, starts_at, ends_at, session.room, acknowledge_room=acknowledge_room,
                     exclude_session_id=session.session_id)
    change = _change(session, "Rescheduled", reason, new_start=starts_at, new_end=ends_at)
    old_slot = _slot(session.starts_at, session.ends_at)
    session.starts_at, session.ends_at, session.state = starts_at, ends_at, "Rescheduled"
    db.session.add(change)
    db.session.flush()
    audit.record("SESSION_RESCHEDULED", "class_session", session.session_id, branch_id=session.batch.branch_id, reason=reason,
                 old={"starts_at": change.old_starts_at, "ends_at": change.old_ends_at}, new={"starts_at": starts_at, "ends_at": ends_at})
    _notify_change(session, change, f"Class rescheduled: {session.title}", f"Was {old_slot}; now {_slot(starts_at, ends_at)}. {reason}")
    return change


def reschedule(session_id: int, starts_at: datetime, ends_at: datetime, reason: str, acknowledge_room: bool = False) -> ClassSession:
    session = _load_for_change(session_id)
    _apply_reschedule(session, starts_at, ends_at, reason, acknowledge_room=acknowledge_room)
    return session


def cancel(session_id: int, reason: str) -> ClassSession:
    """Cancel an upcoming class. The batch's students and the trainer are told; a cancelled class is never a student absence."""
    session = _load_for_change(session_id)
    _require_open(session, "cancelled")
    change = _change(session, "Cancelled", reason)
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
    session.state = "Live"
    db.session.flush()
    return session


def deliver(session_id: int, notes: str | None) -> ClassSession:
    """Record that the class was actually taught: Live (or an open class whose time has begun) -> Delivered."""
    session = _load_for_change(session_id, allow_own_trainer=True)
    if session.state not in ("Live", *OPEN_STATES):
        raise BusinessRule(f"Session {session.session_id} is {session.state} and cannot be marked Delivered")
    now = _now()
    if session.state != "Live" and now < session.starts_at:
        raise BusinessRule("The class has not started yet")
    session.state, session.delivered_at = "Delivered", now
    if notes:
        session.notes = notes
    db.session.flush()
    audit.record("SESSION_DELIVERED", "class_session", session.session_id, branch_id=session.batch.branch_id,
                 new={"delivered_at": now, "starts_at": session.starts_at})
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


def approve_request(request_id: int, note: str | None, acknowledge_room: bool = False) -> SessionChangeRequest:
    """Approving moves the session to the proposed slot (the same checks and notices as a direct reschedule)."""
    request = _load_request(request_id)
    session = sessions_repo.get_session_for_update(request.session_id)
    _apply_reschedule(session, request.proposed_starts_at, request.proposed_ends_at, f"Trainer request: {request.reason}",
                      acknowledge_room=acknowledge_room)
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


def associate_meet(session_id: int, meet_link: str) -> ClassSession:
    """Record the organizer's Meet link for an online class (the manual entry Module 16 allows while automatic creation is unverified)."""
    if not MEET_LINK.fullmatch(meet_link):
        raise ValidationError("Invalid Meet link", {"meet_link": ["Must be a https://meet.google.com/… link"]})
    session = _load_online_session(session_id)
    session.meet_link, session.meet_status = meet_link, "Linked"
    db.session.flush()
    meet.record(session, "Link associated", "Entered manually; " + meet.integration_note())
    audit.record("MEET_LINK_SET", "class_session", session.session_id, branch_id=session.batch.branch_id, new={"meet_link": meet_link})
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


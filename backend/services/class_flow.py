"""Today's guided class flow: the only way a trainer runs a class (UX plan U12).

A class moves through Start class -> Join -> Attendance -> Class log; the last step saves the whole log through
`class_sessions.deliver` (outcome, actual times, break, what was not delivered, topics covered, attendance, notes). A class that
can no longer be started (it ended more than 6 hours ago) has just the Class log; attendance is then marked once it is logged.

Where the trainer stands, and the half-finished log, are saved on the server (`class_flow_progress`, db 112) so a refresh or
another device resumes at the same step. What happened to the class (Scheduled / Live / Delivered) stays the truth: the saved
step is only ever clamped to what that state allows. "No Meet link" is a one-click request to the Branch Managers.
"""
from datetime import datetime, timedelta, timezone

from config.database import db
from repositories import class_flow as flow_repo
from repositories import class_sessions as sessions_repo
from repositories import recordings as recordings_repo
from repositories import settings as settings_repo
from services import attendance, class_sessions, delivery_notices, meet
from services.context import actor_id, current_user
from services.errors import BusinessRule, Forbidden, NotFound

STEPS = ("open", "join", "attendance", "log")
LATE_STEPS = ("log",)
OUTCOMES = ("Held", "Partially Held")
OPEN = class_sessions.OPEN_STATES
MAX_TOPICS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def log_since(now: datetime) -> datetime:
    """How far back a class without a log still counts as missing (days, as the Branch Manager's check job uses)."""
    return now - timedelta(days=settings_repo.get_int("class_log_lookback_days", 14))


def _steps(session, now: datetime) -> tuple[str, ...]:
    """The steps this class still needs: a finished class none; one that can no longer be started just the log."""
    if session.state in ("Delivered", "Cancelled"):
        return ()
    if session.state in OPEN and now > session.ends_at + class_sessions.START_STAYS_OPEN_AFTER:
        return LATE_STEPS
    return STEPS


def _bounds(session, steps: tuple[str, ...]) -> tuple[int, int]:
    """(lowest, highest) step index the class's state allows: not started -> only the first; started -> from Join on."""
    if session.state == "Live":
        return (1, len(steps) - 1) if steps == STEPS else (0, 0)
    return 0, 0


def _clamp(session, steps: tuple[str, ...], wanted: str | None) -> str | None:
    if not steps:
        return None
    low, high = _bounds(session, steps)
    index = steps.index(wanted) if wanted in steps else low
    return steps[min(max(index, low), high)]


def clean_draft(raw: dict) -> dict:
    """Keep only the fields of a class log, in their own types (the strict checks happen when the class is logged)."""
    out: dict = {}
    for key in ("actual_start", "actual_end", "unfulfilled_note", "notes"):
        if key in raw:
            out[key] = (raw[key] or "").strip()[:2000] or None
    if "outcome" in raw and raw["outcome"] in OUTCOMES:
        out["outcome"] = raw["outcome"]
    if "break_minutes" in raw:
        out["break_minutes"] = raw["break_minutes"] if isinstance(raw["break_minutes"], int) and 0 <= raw["break_minutes"] <= 600 else None
    if "topic_ids" in raw:
        out["topic_ids"] = [t for t in dict.fromkeys(raw["topic_ids"] or []) if isinstance(t, int)][:MAX_TOPICS]
    return out


def _topic_options(session) -> list[dict]:
    """The topics a class log can tick: the whole outline of the planned topic (else of the batch's course or track), by module."""
    if session.topic:
        course_id, component_id = session.topic.module.course_id, session.topic.module.component_id
    else:
        course_id, component_id = session.batch.course_id, session.batch.component_id
    return [{"topic_id": topic.topic_id, "title": topic.title, "module": module.title} for module, topic in flow_repo.outline_topics(course_id, component_id)]


def item(session, now: datetime | None = None) -> dict:
    """One class as Today's flow shows it. `step` is None for a finished class."""
    now = now or _now()
    register = attendance.get_register(session.session_id)
    summary = register.summary()
    steps = _steps(session, now)
    saved = flow_repo.get_progress(session.session_id) if steps else None
    recordings = recordings_repo.recordings_of_session(session.session_id)
    covered = flow_repo.covered_topics([session.session_id])[session.session_id]
    requested_at = flow_repo.link_requested_at(session.session_id) if session.mode != "Classroom" and session.meet_status != "Linked" else None
    start_opens_at = session.starts_at - class_sessions.START_OPENS_BEFORE
    return {
        "session_id": session.session_id,
        "session_code": session.session_code,
        "title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "mode": session.mode,
        "room": session.room,
        "state": session.state,
        "state_label": session.state_label,
        "live_at": session.live_at,
        "delivered_at": session.delivered_at,
        "notes": session.notes,
        "batch": session.batch.to_summary(),
        "topic": {"topic_id": session.topic.topic_id, "title": session.topic.title} if session.topic else None,
        "meet": {"status": session.meet_status, "label": meet.status_label(session.meet_status), "link": session.meet_link,
                 "organizer_email": meet.organizer_email(session) if session.mode != "Classroom" else None, "link_requested_at": requested_at},
        "attendance": {**summary, "locked": register.locked, "can_mark": register.can_mark},
        "recording": {"count": len(recordings), "mapping": "Mapped" if recordings else "Pending Verification"},
        "approval_status": session.approval_status,
        "flow": {
            "steps": list(steps),
            "step": _clamp(session, steps, saved.step if saved else None),
            "draft": saved.draft if saved else {},
            "can_start": session.state in OPEN and session.approval_status != "Pending" and now >= start_opens_at,
            "start_opens_at": start_opens_at,
            "awaiting_approval": session.approval_status == "Pending",
            "topic_options": _topic_options(session) if steps else [],
        },
        "log": {
            "outcome": session.delivery_outcome, "actual_start": session.actual_start, "actual_end": session.actual_end,
            "break_minutes": session.break_minutes, "delivered_minutes": session.delivered_minutes, "planned_minutes": session.planned_minutes,
            "unfulfilled_note": session.unfulfilled_note,
            "topics": [{"topic_id": t.topic_id, "title": t.title} for t in covered],
        } if session.state == "Delivered" else None,
    }


def _own_session(session):
    if session.trainer_user_id != current_user().user_id:
        raise Forbidden("Only the trainer who teaches this class can run it")
    return session


def _teaching_session(session_id: int):
    """The class, row-locked; only the trainer who teaches it (a Branch Manager runs classes from the schedule, not Today)."""
    return _own_session(class_sessions.load_for_change(session_id, allow_own_trainer=True))


def get(session_id: int) -> dict:
    session = sessions_repo.get_session(session_id)
    if session is None:
        raise NotFound("Class session not found")
    class_sessions.assert_can_view_session(session)
    return item(_own_session(session))


def save_progress(session_id: int, step: str | None, draft: dict | None) -> dict:
    """Remember where the trainer is and what they have typed in the class log so far."""
    session = _teaching_session(session_id)
    now = _now()
    steps = _steps(session, now)
    if not steps:
        raise BusinessRule(f"This class is {session.state.lower()}; there is nothing left to run")
    if step is not None and step not in steps:
        raise BusinessRule("That step is not part of this class's flow")
    saved = flow_repo.get_progress(session_id)
    target = _clamp(session, steps, step or (saved.step if saved else None))
    merged = {**(saved.draft if saved else {}), **clean_draft(draft or {})}
    flow_repo.save_progress(session_id, target, merged, actor_id())
    return item(session, now)


def ask_for_meet_link(session_id: int) -> dict:
    """"No Meet link": tell the branch's Branch Managers this class needs one. The trainer carries on with the flow. Asking
    again while the link is still missing does not send a second message."""
    session = _teaching_session(session_id)
    if session.mode == "Classroom":
        raise BusinessRule("A classroom class needs no Meet link")
    if session.state not in (*OPEN, "Live"):
        raise BusinessRule(f"This class is {session.state.lower()}")
    if session.meet_status == "Linked":
        raise BusinessRule("This class already has a Meet link")
    if flow_repo.link_requested_at(session_id) is None:
        event = meet.record(session, flow_repo.LINK_REQUESTED, f"{session.trainer.full_name} asked for a Meet link from the class flow")
        db.session.flush()
        slot = class_sessions._slot(session.starts_at, session.ends_at)
        delivery_notices.notify_branch_managers(
            session.batch.branch_id, title=f"Meet link needed: {session.title}", category="Session", action_required=True,
            body=f"{session.batch.batch_code} · {slot}. {session.trainer.full_name} cannot find a link for this class.",
            event_key=f"meet-link-requested-{event.event_id}", link="/branch/class-day")
    return item(session)


def compact(session) -> dict:
    """A class in a plain list (tomorrow's classes, the classes that still need a log)."""
    return {
        "session_id": session.session_id, "title": session.title, "starts_at": session.starts_at, "ends_at": session.ends_at,
        "mode": session.mode, "room": session.room, "state": session.state, "state_label": session.state_label,
        "batch": session.batch.to_summary(), "topic": {"topic_id": session.topic.topic_id, "title": session.topic.title} if session.topic else None,
    }

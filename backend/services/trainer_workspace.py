"""The trainer's own workspace: Today (`GET /trainer/today`) and Reports (`GET /trainer/reports`).

Everything is limited to the batches the trainer is assigned to, through services/scope.py. Nothing is calculated from scratch:
the tiles read the class sessions (S1), the review queue (S3) and the support flags (S5); the reports read the progress view (S4)
and the S3 review timestamps. The "Today's flow" stepper on the client drives the existing endpoints (start / deliver a session,
the attendance register, session notes) - this response only says where each of today's sessions stands.
"""
from datetime import datetime, time, timedelta, timezone

from config.timezone import IST, today_ist
from models import ClassSession
from repositories import batches as batches_repo
from repositories import progress as progress_repo
from repositories import recordings as recordings_repo
from repositories import reports as reports_repo
from repositories import settings as settings_repo
from services import attendance, meet, scope, submissions, support
from services.cards import safe_card
from services.context import current_user
from services.errors import Forbidden

SCOPE_NOTE = "Trainers see only assigned batches and students. No leads, finance, refunds or global Course Master administration."
WEEK_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_day(day) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def _require_trainer() -> int:
    user = current_user()
    if not user.has_role("TRAINER"):
        raise Forbidden("This is a trainer view")
    return user.user_id


# ---------------------------------------------------------------- Today

def _sessions_tile(user_id: int, now: datetime) -> dict:
    """Assigned sessions still to be taught in the next 7 days (today counts as day one)."""
    today = today_ist()
    sessions = reports_repo.sessions_of_trainer(user_id, now - timedelta(hours=2), _start_of_day(today + timedelta(days=WEEK_DAYS)),
                                                states=reports_repo.OPEN_SESSION_STATES)
    upcoming = [s for s in sessions if s.ends_at >= now]
    return {"state": "Ready", "count": len(upcoming), "window_days": WEEK_DAYS, "next_starts_at": upcoming[0].starts_at if upcoming else None}


def _reviews_tile(now: datetime) -> dict:
    """Latest submissions with no review yet, for assignments this trainer reviews; the oldest one's age."""
    rows, meta = submissions.list_submissions({"status": "Awaiting Review", "reviewer_me": True}, 1, 1)  # oldest first
    oldest = rows[0].submitted_at if rows else None
    return {"state": "Ready", "count": meta["total"], "oldest_submitted_at": oldest,
            "oldest_age_days": (now - oldest).days if oldest else None}


def _flags_tile() -> dict:
    students = support.assigned_students()
    flagged = {row["student"]["student_id"] for row in students if row["open_requests"]}
    return {"state": "Ready", "count": len(flagged), "assigned_students": len({row["student"]["student_id"] for row in students})}


def _session_item(session: ClassSession) -> dict:
    register = attendance.get_register(session.session_id)
    summary = register.summary()
    recordings = recordings_repo.recordings_of_session(session.session_id)
    return {
        "session_id": session.session_id,
        "session_code": session.session_code,
        "title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "mode": session.mode,
        "room": session.room,
        "state": session.state,
        "delivered_at": session.delivered_at,
        "notes": session.notes,
        "batch": session.batch.to_summary(),
        "topic": {"topic_id": session.topic.topic_id, "title": session.topic.title} if session.topic else None,
        "meet": {"status": session.meet_status, "label": meet.status_label(session.meet_status), "link": session.meet_link,
                 "organizer_email": session.batch.branch.mailbox if session.mode != "Classroom" else None},
        "attendance": {**summary, "locked": register.locked, "can_mark": register.can_mark},
        "recording": {"count": len(recordings), "mapping": "Mapped" if recordings else "Pending Verification"},
    }


def _today_sessions(user_id: int, now: datetime) -> dict:
    today = today_ist()
    sessions = reports_repo.sessions_of_trainer(user_id, _start_of_day(today), _start_of_day(today + timedelta(days=1)))
    sessions = [s for s in sessions if s.state != "Cancelled"]
    return {"state": "Ready" if sessions else "Empty", "date": today, "sessions": [_session_item(s) for s in sessions],
            "message": None if sessions else "No assigned session scheduled today."}


def today() -> dict:
    user_id = _require_trainer()
    now = _now()
    batch_ids = scope.trainer_batch_ids()
    return {
        "as_of": now,
        "scope_note": SCOPE_NOTE,
        "assigned_batches": len(batch_ids),
        "tiles": {
            "sessions": safe_card("trainer_sessions", lambda: _sessions_tile(user_id, now)),
            "reviews": safe_card("trainer_reviews", lambda: _reviews_tile(now)),
            "support_flags": safe_card("trainer_flags", _flags_tile),
        },
        "today": safe_card("trainer_today", lambda: _today_sessions(user_id, now)),
    }


# ---------------------------------------------------------------- Reports

def review_turnaround(timings: list[tuple[datetime | None, datetime | None]]) -> dict:
    """Hours from submission to review. A pair with a missing or impossible timestamp is left out and makes the figure Partial Data."""
    usable = [(s, r) for s, r in timings if s is not None and r is not None and r >= s]
    missing = len(timings) - len(usable)
    if not timings:
        return {"state": "Empty", "reviewed": 0, "missing_timestamps": 0, "average_hours": None, "message": "No submission has been reviewed yet."}
    hours = [(r - s).total_seconds() / 3600 for s, r in usable]
    average = round(sum(hours) / len(hours), 1) if hours else None
    state = "Partial Data" if missing else "Calculated"
    return {
        "state": state, "reviewed": len(timings), "measured": len(usable), "missing_timestamps": missing, "average_hours": average,
        "message": f"{missing} reviewed submission(s) are missing timestamps and are left out." if missing else None,
    }


def _batch_rows(batch_ids: set[int]) -> list[dict]:
    condition = progress_repo.enrolment_scope_condition(set(), batch_ids, set())
    summaries = {item["batch"].batch_id: item for item in progress_repo.batch_summaries(condition, None) if item["batch"].batch_id in batch_ids}
    rows = []
    for batch_id in sorted(batch_ids):
        item = summaries.get(batch_id)
        batch = item["batch"] if item else batches_repo.get_batch(batch_id)
        rows.append({
            "batch": batch.to_summary(), "batch_state": batch.state, "students": item["students"] if item else 0,
            "delivery": {"percent": item["avg_delivery"] if item else None},
            "attendance": {
                "percent": item["avg_attendance"] if item else None,
                "partial_data": item["partial_data"] if item else 0,
                "state": "Empty" if not item or item["avg_attendance"] is None else "Partial Data" if item["partial_data"] else "Calculated",
            },
            "alerts": item["alerts"] if item else 0,
        })
    return rows


def _engagement(batch_ids: set[int], now: datetime) -> dict:
    """Latest learning activity across the trainer's students; with none inside the window it is Stale, never zero."""
    window = settings_repo.get_int("engagement_window_days", 14)
    progress = progress_repo.progress_by_enrolment(sorted(batches_repo.enrolment_ids_in_batches(batch_ids)))
    latest = max((p.last_activity_at for p in progress.values() if p.last_activity_at), default=None)
    stale = latest is None or now - latest > timedelta(days=window)
    return {"state": "Stale" if stale else "Fresh", "refreshed_at": latest, "window_days": window, "students": len(progress),
            "message": "No learning activity recorded for these students yet." if latest is None
            else f"Latest learning activity {latest.astimezone(IST):%d %b %Y}." if stale else None}


def reports() -> dict:
    user_id = _require_trainer()
    now = _now()
    batch_ids = scope.trainer_batch_ids()
    return {
        "as_of": now,
        "scope_note": SCOPE_NOTE,
        "batches": safe_card("trainer_report_batches", lambda: {"state": "Ready" if batch_ids else "Empty", "rows": _batch_rows(batch_ids),
                                                                 "message": None if batch_ids else "You are not assigned to a batch yet."}),
        "review_turnaround": safe_card("trainer_report_reviews", lambda: review_turnaround(reports_repo.review_timings(reviewer_user_id=user_id))),
        "engagement": safe_card("trainer_report_engagement", lambda: _engagement(batch_ids, now)),
    }

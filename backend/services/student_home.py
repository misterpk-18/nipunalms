"""Student Home (`GET /me/home`): one response that aggregates what the other slices already compute for the signed-in student.

Nothing is calculated here. Each card reads an existing service (sessions and Meet state from S1, recordings from S2, due work
from S3, the four progress measures, attendance and the certificate register from S4, career / support / Ask Nipuna from S5) and
reports `state`: "Ready", "Empty" (nothing to show yet) or "Unavailable" (the source failed; the other cards still render).
Engagement is never shown as zero: with no recent activity it is reported as Stale.
"""
import logging
from datetime import datetime, timedelta, timezone

from config.database import db
from models import ClassSession, Enrolment, Student
from repositories import content as content_repo
from repositories import students as students_repo
from services import ask_nipuna, attendance, career, class_sessions, due_work, meet, progress, recordings, support
from services.cards import safe_card
from services.context import current_user
from services.errors import Forbidden

logger = logging.getLogger(__name__)

UPCOMING_STATES = ("Scheduled", "Rescheduled", "Live")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _student() -> Student:
    student_id = current_user().student_id
    student = students_repo.get_student(student_id) if student_id is not None else None
    if student is None:
        raise Forbidden("This is a student view")
    return student


def _primary(blocks: list[dict]) -> dict | None:
    """The enrolment the home screen is about: the first Active one, else the first being studied."""
    return next((b for b in blocks if b["enrolment"]["status"] == "Active"), blocks[0] if blocks else None)


# ---------------------------------------------------------------- cards

def _next_class() -> dict:
    rows, _ = class_sessions.list_sessions({"upcoming": True}, 1, 1)
    if not rows:
        return {"state": "Empty", "message": "No class is scheduled yet."}
    row = rows[0]
    session = row.session
    join = row.join or {"enabled": False, "reason": "Joining is not available."}
    return {
        "state": "Ready",
        "session_id": session.session_id,
        "session_code": session.session_code,
        "title": session.topic.title if session.topic else session.title,
        "session_title": session.title,
        "starts_at": session.starts_at,
        "ends_at": session.ends_at,
        "mode": session.mode,
        "room": session.room,
        "class_state": session.state,
        "trainer": {"user_id": session.trainer_user_id, "full_name": session.trainer.full_name},
        "batch": session.batch.to_summary(),
        "meet_status": session.meet_status,
        "meet_status_label": meet.status_label(session.meet_status),
        "organizer_email": session.batch.branch.mailbox if session.mode != "Classroom" else None,
        "join": {"enabled": join["enabled"], "reason": join["reason"], "url": join.get("url")},
    }


def _due_work(student: Student) -> dict:
    """{due_work: the Due Work tile, upcoming_work: the Upcoming Assignment / Test card} from the same open-work rules the Tasks and Tests screens use."""
    assignments, tests = due_work.open_items(student)
    nearest = min(assignments, key=lambda item: item[0].due_at, default=None)
    tile = {
        "state": "Ready" if assignments or tests else "Empty",
        "assignments": len(assignments),
        "required_assignments": sum(1 for a, _ in assignments if a.is_required),
        "tests": len(tests),
        "nearest": None if nearest is None else {
            "kind": "assignment", "id": nearest[0].assignment_id, "code": nearest[0].assignment_code, "title": nearest[0].title,
            "due_at": nearest[0].due_at, "state": nearest[1], "is_required": nearest[0].is_required,
        },
        "message": None if assignments or tests else "Nothing is due right now.",
    }

    def when(test) -> datetime:
        return test.opens_at if test.opens_at and test.opens_at > _now() else (test.closes_at or test.opens_at or _now())

    upcoming = min(tests, key=lambda item: when(item[0]), default=None)
    card = {"state": "Empty", "message": "No test is scheduled."} if upcoming is None else {
        "state": "Ready", "id": upcoming[0].test_id, "code": upcoming[0].test_code, "title": upcoming[0].title, "kind": upcoming[0].kind,
        "status": upcoming[1], "opens_at": upcoming[0].opens_at, "closes_at": upcoming[0].closes_at,
    }
    return {"due_work": tile, "upcoming_work": card}


def _course_progress(block: dict | None) -> dict:
    if block is None:
        return {"state": "Empty", "message": "Progress appears once you are studying a course."}
    delivery = block["delivery"]
    return {
        "state": "Ready" if delivery["percent"] is not None else "Empty",
        "enrolment": block["enrolment"],
        "delivered_sessions": delivery["delivered_sessions"],
        "planned_sessions": delivery["planned_sessions"],
        "percent": delivery["percent"],
        "message": None if delivery["percent"] is not None else "No class is planned yet, so delivery cannot be calculated.",
    }


def _continue_learning(enrolment_id: int | None) -> dict:
    """Track -> module -> topic of the last class taught, else the next scheduled one."""
    if enrolment_id is None:
        return {"state": "Empty", "message": "Your learning path appears once you are studying a course."}
    sessions: list[ClassSession] = [s for s in class_sessions.sessions_for_enrolment(enrolment_id) if s.topic_id]
    delivered = [s for s in sessions if s.state == "Delivered"]
    upcoming = [s for s in sessions if s.state in UPCOMING_STATES]
    if delivered:
        session, basis = max(delivered, key=lambda s: s.starts_at), "Last class taught"
    elif upcoming:
        session, basis = min(upcoming, key=lambda s: s.starts_at), "Next class"
    else:
        return {"state": "Empty", "message": "No class has a curriculum topic yet."}
    topic = session.topic
    module = topic.module
    track = content_repo.track_labels({module.curriculum_version_id}).get(module.curriculum_version_id)
    return {
        "state": "Ready", "basis": basis, "track": track,
        "module": {"module_id": module.module_id, "title": module.title},
        "topic": {"topic_id": topic.topic_id, "title": topic.title},
    }


def _latest_recording() -> dict:
    released = [r for r in recordings.student_recordings({}) if r["status"] == "Released"]
    if not released:
        return {"state": "Empty", "message": "No recording has been released yet."}
    entry = released[0]
    return {
        "state": "Ready",
        "recording_id": entry["recording_id"],
        "title": entry["session"]["title"],
        "class_date": entry["session"]["starts_at"],
        "status": entry["status"],
        "access_state": entry["access"]["state"],
        "access_until": entry["access"]["expiry"],
        "playable": entry["playable"],
    }


def _attendance_alert(enrolment: Enrolment | None) -> dict:
    if enrolment is None:
        return {"state": "Empty", "message": "Attendance appears once you are studying a course."}
    data = attendance.enrolment_attendance(enrolment)
    summary = data["summary"]
    absences = [r for r in data["rows"] if r["status"] == "Absent"]
    latest = max(absences, key=lambda r: r["session"]["starts_at"], default=None)
    return {
        "state": "Ready" if summary["state"] != "Not started" else "Empty",
        "attendance_state": summary["state"],
        "percent": summary["percent"],
        "alert": summary["alert"],
        "alert_threshold": summary["alert_threshold"],
        "latest_absence": None if latest is None else {
            "session_title": latest["session"]["title"], "starts_at": latest["session"]["starts_at"],
            "can_request_recovery": latest["can_request_recovery"], "recovery": latest["recovery"],
        },
        "message": None if summary["state"] != "Not started" else "Attendance starts once your Joining Date is confirmed.",
    }


def _certificate(block: dict | None) -> dict:
    if block is None:
        return {"state": "Empty", "message": "No certificate yet."}
    return {"state": "Ready", "status": block["certificate_status"], "enrolment": block["enrolment"]}


def _career(student: Student) -> dict:
    return {"state": "Ready", **career.home_summary(student.student_id)}


def _support() -> dict:
    rows, _ = support.list_requests({"open": True}, 1, 5)
    now = _now()
    requests = [{"request_code": r.request_code, "subject": r.subject, "status": r.status, "owner": r.owner_label(),
                 "sla_breached": r.to_summary(now)["sla_breached"]} for r in rows]
    return {"state": "Ready" if requests else "Empty", "open_count": len(requests), "requests": requests,
            "message": None if requests else "No open request."}


def _ask_nipuna() -> dict:
    status = ask_nipuna.status()
    return {"state": "Ready", "status": status.status, "mode": status.mode, "used": status.usage.used, "limit": status.usage.limit,
            "resets_at": status.usage.resets_at}


def _engagement(block: dict | None, now: datetime) -> dict:
    """Freshness of engagement data. `refreshed_at` is the latest learning activity the LMS recorded for the enrolment; with none
    inside the engagement window the data is Stale (never reported as zero)."""
    if block is None:
        return {"state": "Empty", "refreshed_at": None, "message": "Engagement appears once you are studying a course."}
    engagement = block["engagement"]
    refreshed = engagement["last_activity_at"]
    window = timedelta(days=engagement["window_days"])
    stale = refreshed is None or now - refreshed > window
    return {
        "state": "Stale" if stale else "Fresh", "refreshed_at": refreshed, "window_days": engagement["window_days"],
        "level": None if stale else engagement["level"],
        "message": ("No learning activity has been recorded yet; shown as Stale rather than as zero." if refreshed is None
                    else f"Last learning activity was recorded {refreshed:%d %b %Y}; shown as Stale rather than as zero.") if stale else None,
    }


# ---------------------------------------------------------------- the response

def my_home() -> dict:
    student = _student()
    now = _now()
    blocks: list[dict] = []
    try:
        with db.session.begin_nested():
            blocks = progress.my_progress()
    except Exception:  # noqa: BLE001
        logger.exception("Student Home: progress failed")
    primary = _primary(blocks)
    enrolment = students_repo.get_enrolment(primary["enrolment"]["enrolment_id"]) if primary else None

    due = safe_card("due_work", lambda: _due_work(student))
    failed = "due_work" not in due  # _card returned its Unavailable marker for both cards
    return {
        "student": {
            "student_id": student.student_id, "student_code": student.student_code, "full_name": student.full_name,
            "name_te": student.name_te, "service_branch": student.service_branch.to_summary(),
        },
        "as_of": now,
        "primary_enrolment": primary["enrolment"] if primary else None,
        "next_class": safe_card("next_class", _next_class),
        "due_work": due if failed else due["due_work"],
        "course_progress": safe_card("course_progress", lambda: _course_progress(primary)),
        "continue_learning": safe_card("continue_learning", lambda: _continue_learning(enrolment.enrolment_id if enrolment else None)),
        "latest_recording": safe_card("latest_recording", _latest_recording),
        "upcoming_work": due if failed else due["upcoming_work"],
        "attendance_alert": safe_card("attendance_alert", lambda: _attendance_alert(enrolment)),
        "certificate": safe_card("certificate", lambda: _certificate(primary)),
        "career": safe_card("career", lambda: _career(student)),
        "support": safe_card("support", _support),
        "ask_nipuna": safe_card("ask_nipuna", _ask_nipuna),
        "engagement": safe_card("engagement", lambda: _engagement(primary, now)),
    }

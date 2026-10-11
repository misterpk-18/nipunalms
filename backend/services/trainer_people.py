"""The trainer's People screens (UX plan U13): the Students list with search and a batch filter, the Batches list, and one page for
a batch (`GET /trainer/batches/<id>`) and for a student (`GET /trainer/students/<id>`).

Everything is limited to the batches the trainer is assigned to (services/scope.py): anything else is a 404. A student's page shows
the student only inside those batches, so it never reveals contact details, fees or another trainer's classes.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from models import ClassSession, ContentItem
from repositories import assignments as assignments_repo
from repositories import attendance as attendance_repo
from repositories import batches as batches_repo
from repositories import progress as progress_repo
from repositories import results as results_repo
from services import class_flow, scope, support, trainer_risk
from services.context import current_user
from services.errors import Forbidden, NotFound

OPEN_SESSION_STATES = ("Scheduled", "Rescheduled", "Live")
LIST_LIMIT = 8


def _require_trainer() -> set[int]:
    if not current_user().has_role("TRAINER"):
        raise Forbidden("This is a trainer view")
    return scope.trainer_batch_ids()


def _number(value) -> float | None:
    return None if value is None else float(value)


def _measures(progress) -> dict:
    """The progress figures a trainer needs on a row (None when the figure cannot be calculated yet)."""
    if progress is None:
        return {"attendance_pct": None, "attendance_state": None, "delivery_pct": None, "required_pct": None, "unmarked": 0, "last_activity_at": None}
    return {"attendance_pct": _number(progress.attendance_pct), "attendance_state": progress.attendance_state,
            "delivery_pct": _number(progress.delivery_pct), "required_pct": _number(progress.required_pct),
            "unmarked": progress.unmarked_sessions, "last_activity_at": progress.last_activity_at}


# ---------------------------------------------------------------- Students

def students(q: str | None = None, batch_id: int | None = None) -> list[dict]:
    """The trainer's students (one row per active seat) with attendance, the reasons they are at risk and any open support flag.
    `q` matches name or student ID; `batch_id` narrows to one batch (404 when it is not the trainer's)."""
    batch_ids = _require_trainer()
    if batch_id is not None:
        if batch_id not in batch_ids:
            raise NotFound("Batch not found")
        batch_ids = {batch_id}
    rows = trainer_risk.seats(batch_ids)
    needle = (q or "").strip().lower()
    if needle:
        rows = [r for r in rows if needle in r[0].full_name.lower() or needle in r[0].student_code.lower()]
    progress = progress_repo.progress_by_enrolment(sorted({e.enrolment_id for _, _, e in rows}))
    reasons = trainer_risk.reasons_by_seat(rows)
    flags = support.open_requests_for([s.student_id for s, _, _ in rows])
    return [{
        "student": student.to_summary(),
        "batch": batch.to_summary(),
        "enrolment": enrolment.to_summary(),
        "open_requests": [r.to_summary(datetime.now(timezone.utc)) for r in flags.get(student.student_id, [])],
        "flag": f"Open — {flags[student.student_id][0].category}" if flags.get(student.student_id) else "None",
        **_measures(progress.get(enrolment.enrolment_id)),
        "reasons": reasons.get((batch.batch_id, enrolment.enrolment_id), []),
    } for student, batch, enrolment in rows]


# ---------------------------------------------------------------- Batches

def _next_session(batch_id: int, now: datetime) -> ClassSession | None:
    stmt = (select(ClassSession).where(ClassSession.batch_id == batch_id, ClassSession.state.in_(OPEN_SESSION_STATES), ClassSession.ends_at >= now)
            .order_by(ClassSession.starts_at).limit(1))
    return db.session.execute(stmt).unique().scalars().first()


def batches() -> list[dict]:
    """The trainer's batches, each with its seats, next class and how many students need attention."""
    batch_ids = _require_trainer()
    if not batch_ids:
        return []
    now = datetime.now(timezone.utc)
    rows = trainer_risk.seats(batch_ids)
    counts = batches_repo.allocated_counts(sorted(batch_ids))
    risky: dict[int, int] = {}
    reasons = trainer_risk.reasons_by_seat(rows)
    for _, batch, enrolment in rows:
        if reasons.get((batch.batch_id, enrolment.enrolment_id)):
            risky[batch.batch_id] = risky.get(batch.batch_id, 0) + 1
    summaries = {s["batch"].batch_id: s for s in progress_repo.batch_summaries(progress_repo.enrolment_scope_condition(set(), batch_ids, set()), None)
                 if s["batch"].batch_id in batch_ids}
    result = []
    for batch_id in sorted(batch_ids):
        batch = batches_repo.get_batch(batch_id)
        upcoming = _next_session(batch_id, now)
        summary = summaries.get(batch_id)
        result.append({
            "batch": batch.to_dict(allocated_count=counts.get(batch_id, 0)),
            "students": counts.get(batch_id, 0),
            "at_risk": risky.get(batch_id, 0),
            "next_class": class_flow.compact(upcoming) if upcoming else None,
            "attendance_pct": summary["avg_attendance"] if summary else None,
            "delivery_pct": summary["avg_delivery"] if summary else None,
        })
    result.sort(key=lambda r: r["batch"]["batch_code"])
    return result


def _load_batch(batch_id: int):
    if batch_id not in _require_trainer():
        raise NotFound("Batch not found")
    batch = batches_repo.get_batch(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    return batch


def batch_page(batch_id: int) -> dict:
    """One batch: classes coming up and recent, the roster with who needs attention, content, assignments and progress."""
    batch = _load_batch(batch_id)
    now = datetime.now(timezone.utc)
    user = current_user()

    coming = db.session.execute(
        select(ClassSession).where(ClassSession.batch_id == batch_id, ClassSession.state.in_(OPEN_SESSION_STATES), ClassSession.ends_at >= now)
        .order_by(ClassSession.starts_at).limit(LIST_LIMIT)).unique().scalars().all()
    recent = db.session.execute(
        select(ClassSession).where(ClassSession.batch_id == batch_id, ClassSession.state != "Cancelled", ClassSession.starts_at < now,
                                   ClassSession.state.not_in(OPEN_SESSION_STATES))
        .order_by(ClassSession.starts_at.desc()).limit(LIST_LIMIT)).unique().scalars().all()

    rows = trainer_risk.seats({batch_id})
    progress = progress_repo.progress_by_enrolment(sorted({e.enrolment_id for _, _, e in rows}))
    reasons = trainer_risk.reasons_by_seat(rows)
    flags = support.open_requests_for([s.student_id for s, _, _ in rows])
    roster = [{
        "student": student.to_summary(),
        "enrolment": enrolment.to_summary(),
        "open_requests": len(flags.get(student.student_id, [])),
        **_measures(progress.get(enrolment.enrolment_id)),
        "reasons": reasons.get((batch_id, enrolment.enrolment_id), []),
    } for student, _, enrolment in rows]

    assignments = list(db.session.execute(assignments_repo.list_stmt({"batch_id": batch_id}).limit(LIST_LIMIT)).unique().scalars())
    counts = assignments_repo.submission_counts([a.assignment_id for a in assignments])
    content_stmt = (select(ContentItem).where(ContentItem.batch_id == batch_id).order_by(ContentItem.updated_at.desc()).limit(LIST_LIMIT))
    content = list(db.session.execute(content_stmt).unique().scalars())

    summary = next((s for s in progress_repo.batch_summaries(progress_repo.enrolment_scope_condition(set(), {batch_id}, set()), None)
                    if s["batch"].batch_id == batch_id), None)
    return {
        "batch": batch.to_dict(allocated_count=len(roster)),
        "sessions": {"coming": [class_flow.compact(s) for s in coming], "recent": [class_flow.compact(s) for s in recent]},
        "roster": roster,
        "assignments": [{**a.to_dict(), "counts": counts.get(a.assignment_id)} for a in assignments],
        "content": [{"content_item_id": i.content_item_id, "item_code": i.item_code, "title": i.title, "content_type": i.content_type,
                     "status": i.status, "version_no": i.latest_version.version_no, "updated_at": i.updated_at} for i in content],
        "progress": {
            "students": summary["students"] if summary else len(roster),
            "delivery_pct": summary["avg_delivery"] if summary else None,
            "attendance_pct": summary["avg_attendance"] if summary else None,
            "required_pct": summary["avg_required"] if summary else None,
            "alerts": summary["alerts"] if summary else 0,
            "at_risk": sum(1 for r in roster if r["reasons"]),
        },
        "can_run_classes": user.has_role("TRAINER"),
    }


# ---------------------------------------------------------------- Student

def _assignment_rows(batch_id: int, enrolment_id: int, now: datetime) -> list[dict]:
    assignments = assignments_repo.released_for_batches({batch_id}, now)
    handed_in = assignments_repo.versions_for_enrolments({enrolment_id}, [a.assignment_id for a in assignments])
    rows = []
    for assignment in assignments:
        versions = handed_in.get((assignment.assignment_id, enrolment_id))
        latest = versions[-1] if versions else None
        review = latest.review if latest else None
        if latest is None:
            state = "Not submitted"
        elif review is not None:
            state = review.outcome
        else:
            state = "Under Review" if latest.review_started_at else "Submitted"
        rows.append({
            "assignment": assignment.to_summary(),
            "is_required": assignment.is_required,
            "due_at": assignment.due_at,
            "state": state,
            "overdue": latest is None and assignment.due_at < now,
            "late": bool(latest and latest.is_late),
            "submitted_at": latest.submitted_at if latest else None,
            "marks": f"{review.marks:.2f}" if review is not None and review.marks is not None else None,
            "max_marks": f"{assignment.max_marks:.2f}",
            "submission_id": latest.submission_id if latest else None,
            "to_grade": latest is not None and review is None,
        })
    return rows


def _result_rows(enrolment_id: int) -> list[dict]:
    rows = []
    for result in results_repo.for_enrolments({enrolment_id}):
        item = result.item()
        marks = result.final_marks if result.final_marks is not None else result.moderated_marks if result.moderated_marks is not None else result.provisional_marks
        rows.append({"item": item, "status": result.status, "marks": f"{marks:.2f}", "max_marks": f"{result.max_marks:.2f}"})
    return rows


def student_page(student_id: int) -> dict:
    """One student inside the trainer's batches: progress, attendance, work, results and support flags."""
    batch_ids = _require_trainer()
    seats = [row for row in trainer_risk.seats(batch_ids) if row[0].student_id == student_id]
    if not seats:
        raise NotFound("Student not found")
    now = datetime.now(timezone.utc)
    student = seats[0][0]
    reasons = trainer_risk.reasons_by_seat(seats)
    progress = progress_repo.progress_by_enrolment(sorted({e.enrolment_id for _, _, e in seats}))
    enrolments = []
    for _, batch, enrolment in seats:
        batch_sessions = [(s, r) for s, r in attendance_repo.student_session_rows(enrolment.enrolment_id) if s.batch_id == batch.batch_id]
        enrolments.append({
            "enrolment": enrolment.to_summary(),
            "batch": batch.to_summary(),
            **_measures(progress.get(enrolment.enrolment_id)),
            "reasons": reasons.get((batch.batch_id, enrolment.enrolment_id), []),
            "attendance": [{"session_id": s.session_id, "title": s.title, "starts_at": s.starts_at, "status": r.status if r else None}
                           for s, r in batch_sessions[:15]],
            "assignments": _assignment_rows(batch.batch_id, enrolment.enrolment_id, now),
            "results": _result_rows(enrolment.enrolment_id),
        })
    requests, _ = support.list_requests({"student_id": student_id}, 1, 10)
    return {
        "student": student.to_summary(),
        "enrolments": enrolments,
        "flags": support.to_summaries(requests),
    }

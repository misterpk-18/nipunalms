"""Students at risk in the trainer's batches (UX plan U13): `GET /trainer/at-risk`, and the reasons shown on a student's own page.

A student is at risk when at least one of these holds, each with the place where the trainer can act on it:
  attendance      below the alert percentage (after three marked classes)      -> the student's page
  work            required tasks not handed in after their due time, or handed in late in the last 30 days -> the student's page
  unmarked        delivered classes with no attendance mark for the student      -> Attendance
  review_overdue  the student's work has waited past its review target          -> the grading screen for that item
Nothing here is a score: every reason carries the figures it comes from.
"""
from datetime import datetime, timedelta, timezone

from config.timezone import today_ist
from repositories import assignments as assignments_repo
from repositories import batches as batches_repo
from repositories import progress as progress_repo
from repositories import settings as settings_repo
from repositories import support as support_repo
from services import scope, trainer_grading
from services.context import current_user
from services.errors import Forbidden


# A late hand-in counts for a month, so one old slip does not keep a student on the list
LATE_WINDOW = timedelta(days=30)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _reason(kind: str, label: str, detail: str, to: str, action: str) -> dict:
    return {"kind": kind, "label": label, "detail": detail, "to": to, "action": action}


def seats(batch_ids: set[int]) -> list[tuple]:
    """(student, batch, enrolment) for every active seat in these batches (a student with two courses appears twice)."""
    return support_repo.assigned_students(batch_ids)


def reasons_by_seat(rows: list[tuple]) -> dict[tuple[int, int], list[dict]]:
    """{(batch id, enrolment id): [reason]} for the given seats; a seat with no reasons is left out."""
    if not rows:
        return {}
    now = datetime.now(timezone.utc)
    batch_ids = {batch.batch_id for _, batch, _ in rows}
    enrolment_ids = sorted({enrolment.enrolment_id for _, _, enrolment in rows})
    progress = progress_repo.progress_by_enrolment(enrolment_ids)
    threshold = settings_repo.get_int("attendance_alert_threshold", 75)

    # Required work that is already past its due time, and what each student handed in for it
    due = [a for batch_id in batch_ids for a in assignments_repo.released_for_batches({batch_id}, now) if a.due_at < now and a.is_required]
    handed_in = assignments_repo.versions_for_enrolments(set(enrolment_ids), [a.assignment_id for a in due])

    # Work that has waited longer than its review target, by student
    overdue_reviews: dict[tuple[int, int], dict] = {}
    for item in trainer_grading.queue():
        if item["overdue"] and item["batch"]["batch_id"] in batch_ids:
            overdue_reviews.setdefault((item["batch"]["batch_id"], item["student"]["student_id"]), item)

    reasons: dict[tuple[int, int], list[dict]] = {}
    for student, batch, enrolment in rows:
        key = (batch.batch_id, enrolment.enrolment_id)
        found: list[dict] = []
        measures = progress.get(enrolment.enrolment_id)
        if measures is not None and measures.attendance_alert:
            found.append(_reason("attendance", "Low attendance", f"Attendance is {measures.attendance_pct}%, below {threshold}%.",
                                 f"/trainer/students/{student.student_id}", "Open student"))
        missing = late = 0
        for assignment in (a for a in due if a.batch_id == batch.batch_id):
            versions = handed_in.get((assignment.assignment_id, enrolment.enrolment_id))
            if not versions:
                missing += 1
            elif versions[0].is_late and versions[0].submitted_at >= now - LATE_WINDOW:
                late += 1
        if missing or late:
            parts = ([f"{_plural(missing, 'required task')} not handed in"] if missing else []) + ([f"{_plural(late, 'late hand-in')}"] if late else [])
            found.append(_reason("work", "Work missing or late", ", ".join(parts) + ".", f"/trainer/students/{student.student_id}", "Open student"))
        if measures is not None and measures.unmarked_sessions:
            found.append(_reason("unmarked", "Classes not marked", f"{_plural(measures.unmarked_sessions, 'delivered class')} with no attendance mark.",
                                 "/trainer/attendance", "Mark attendance"))
        overdue = overdue_reviews.get((batch.batch_id, student.student_id))
        if overdue is not None:
            found.append(_reason("review_overdue", "Review overdue", f"{overdue['title']} is past its review target.",
                                 f"/trainer/to-grade/{overdue['kind']}/{overdue['id']}", "Grade now"))
        if found:
            reasons[key] = found
    return reasons


def at_risk() -> dict:
    """Per batch: the students at risk, worst first, each with the reasons and where to act."""
    user = current_user()
    if not user.has_role("TRAINER"):
        raise Forbidden("This is a trainer view")
    batch_ids = scope.trainer_batch_ids()
    rows = seats(batch_ids)
    by_seat = reasons_by_seat(rows)
    per_batch = {batch_id: [] for batch_id in sorted(batch_ids)}
    totals: dict[int, int] = {}
    batches = {}
    for student, batch, enrolment in rows:
        batches[batch.batch_id] = batch
        totals[batch.batch_id] = totals.get(batch.batch_id, 0) + 1
        found = by_seat.get((batch.batch_id, enrolment.enrolment_id))
        if found:
            per_batch.setdefault(batch.batch_id, []).append({
                "student": student.to_summary(), "enrolment_id": enrolment.enrolment_id, "reasons": found})
    for batch_id in per_batch:
        if batch_id not in batches:
            batches[batch_id] = batches_repo.get_batch(batch_id)
        per_batch[batch_id].sort(key=lambda r: (-len(r["reasons"]), r["student"]["full_name"]))
    result = [{"batch": batches[batch_id].to_summary(), "batch_state": batches[batch_id].state, "students": totals.get(batch_id, 0),
               "at_risk": len(per_batch[batch_id]), "rows": per_batch[batch_id]} for batch_id in sorted(per_batch, key=lambda b: batches[b].batch_code)]
    return {
        "as_of": datetime.now(timezone.utc),
        "date": today_ist(),
        "batches": result,
        "totals": {"students": sum(totals.values()), "at_risk": sum(b["at_risk"] for b in result)},
    }

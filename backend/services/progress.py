"""Progress: the four separate measures (Delivery, Attendance, Required learning, Engagement) per enrolment.

They are computed by the `enrolment_progress` SQL view (db/040) and never merged into one score; completion and
certificates are decided through Completion Review, not from a percentage. Other slices and the dashboards read the
same view through `progress_for_enrolments`.
"""
from datetime import datetime, timezone

from models import Enrolment, EnrolmentProgress
from repositories import batches as batches_repo
from repositories import progress as progress_repo
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories.rows import paginate_rows
from services import scope
from services.context import current_user
from services.errors import NotFound


def visible_enrolment_condition():
    """SQL condition on Enrolment columns: the enrolments the current user may see (branch, own batches, or own)."""
    return progress_repo.enrolment_scope_condition(scope.visible_branch_ids(), scope.trainer_batch_ids(), scope.student_enrolment_ids())


def get_visible_enrolment(enrolment_id: int) -> Enrolment:
    """The enrolment, or 404 when it does not exist or is outside the user's scope."""
    enrolment = students_repo.get_enrolment(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    scope.assert_can_view_enrolment(enrolment)
    return enrolment


def measures_of(progress: EnrolmentProgress) -> dict:
    """The four measures with the thresholds and windows they were judged against (from app_settings)."""
    return progress.to_measures(
        threshold=settings_repo.get_int("attendance_alert_threshold", 75),
        window_days=settings_repo.get_int("engagement_window_days", 14),
    )


def progress_for_enrolments(enrolment_ids: list[int]) -> dict[int, dict]:
    """enrolment id -> its four measures (for other slices and the dashboards)."""
    return {eid: measures_of(p) for eid, p in progress_repo.progress_by_enrolment(enrolment_ids).items()}


def _as_of() -> datetime:
    return datetime.now(timezone.utc)


def _block(enrolment: Enrolment, progress: EnrolmentProgress, batch: dict | None) -> dict:
    return {
        "enrolment": enrolment.to_summary(),
        "joining_date": enrolment.joining_date,
        "batch": batch,
        "certificate_status": enrolment.certificate_status,
        "as_of": _as_of(),
        **measures_of(progress),
    }


def get_enrolment_progress(enrolment_id: int) -> dict:
    enrolment = get_visible_enrolment(enrolment_id)
    allocation = batches_repo.active_allocation(enrolment_id)
    return _block(enrolment, progress_repo.get_progress(enrolment_id), allocation.batch.to_summary() if allocation else None)


def my_progress() -> list[dict]:
    """The signed-in student's progress, one block per enrolment being studied (never a combined score)."""
    blocks = []
    enrolments = [e for e in students_repo.enrolments_of_student(_student_id()) if e.status not in ("Withdrawn", "Provisioning Pending")]
    progress = progress_repo.progress_by_enrolment([e.enrolment_id for e in enrolments])
    allocations = batches_repo.active_allocations([e.enrolment_id for e in enrolments])
    for enrolment in enrolments:
        allocation = allocations.get(enrolment.enrolment_id)
        blocks.append(_block(enrolment, progress[enrolment.enrolment_id], allocation.batch.to_summary() if allocation else None))
    return blocks


def _student_id() -> int:
    student_id = current_user().student_id
    if student_id is None:
        raise NotFound("This login has no student record")
    return student_id


def list_progress(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Attendance & Progress table: one row per visible enrolment with its four measures, newest data live from the view."""
    rows, meta = paginate_rows(progress_repo.progress_stmt(filters, visible_enrolment_condition()), page, per_page)
    allocations = batches_repo.active_allocations([e.enrolment_id for _, e in rows])
    students = progress_repo.students_by_id({e.student_id for _, e in rows})
    items = []
    for progress, enrolment in rows:
        allocation = allocations.get(enrolment.enrolment_id)
        items.append({
            "student": students[enrolment.student_id].to_summary(),
            **_block(enrolment, progress, allocation.batch.to_summary() if allocation else None),
        })
    return items, meta


def branch_summary(branch_id: int | None) -> dict:
    """Branch report: per batch averages of each measure, enrolment counts by status and certificate register counts."""
    condition = visible_enrolment_condition()
    if branch_id is not None:
        scope.require_branch(branch_id)
    batches = progress_repo.batch_summaries(condition, branch_id)
    return {
        "batches": [
            {"batch": item["batch"].to_summary(), "branch": item["batch"].branch.to_summary(), "state": item["batch"].state,
             "students": item["students"], "avg_delivery": item["avg_delivery"], "avg_attendance": item["avg_attendance"],
             "avg_required_learning": item["avg_required"], "attendance_alerts": item["alerts"], "partial_data": item["partial_data"]}
            for item in batches
        ],
        "enrolments_by_status": progress_repo.enrolment_status_counts(condition, branch_id),
        "certificates_by_status": progress_repo.certificate_status_counts(scope.visible_branch_ids(), branch_id),
        "as_of": _as_of(),
    }

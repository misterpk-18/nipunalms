"""The Branch Manager's "My work" list (UX phase U14): what needs a decision or an action today, most pressing first.

The order is fixed by the product decisions: students waiting for a batch, reschedule and extra-class requests, results to
publish, content to review, recovery and correction requests, support near its deadline, classes at risk today. A row exists
only while something is waiting, carries the count, the oldest wait, the screen that holds it and the button's label. The
counts are the same ones the navigation badges show.
"""
from datetime import datetime, time, timedelta, timezone

from config.timezone import IST
from repositories import branch_work as work_repo
from repositories import nav as nav_repo
from repositories import progress as progress_repo
from services import progress as progress_service
from services import scope
from services.dashboards import scope_block
from services.nav import SUPPORT_WARNING, require_workspace


def _plural(count: int, one: str, many: str | None = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def _branches(branch_id: int | None) -> set[int] | None:
    """The chosen branch (404 outside the user's scope), else everything the user sees."""
    if branch_id is not None:
        scope.require_branch(branch_id)
        return {branch_id}
    return scope.visible_branch_ids()


def today_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    day = (now or datetime.now(timezone.utc)).astimezone(IST).date()
    start = datetime.combine(day, time.min, tzinfo=IST)
    return start, start + timedelta(days=1)


def decisions(branch_ids: set[int] | None) -> dict:
    """What waits on the Branch Manager in Schedule: trainers' reschedule requests and extra, remedial or replacement classes."""
    reschedules, oldest_reschedule = work_repo.open_reschedule_requests(branch_ids)
    classes, oldest_class = work_repo.classes_awaiting_approval(branch_ids)
    dates = [d for d in (oldest_reschedule, oldest_class) if d]
    return {"total": reschedules + classes, "reschedule_requests": reschedules, "extra_classes": classes, "oldest_at": min(dates) if dates else None}


def classes_at_risk_today(branch_ids: set[int] | None) -> list:
    start, end = today_bounds()
    return work_repo.classes_at_risk(branch_ids, start, end)


def _row(key: str, what: str, to: str, action: str, count: int, oldest_at: datetime | None = None, where: str | None = None,
         search: dict | None = None) -> dict:
    return {"key": key, "what": what, "where": where, "count": count, "oldest_at": oldest_at, "to": to, "search": search, "action": action}


def my_work(workspace_branch_id: int | None = None) -> dict:
    """The rows for the branches in view (one chosen branch, or all the user may see), in priority order."""
    require_workspace("branch")
    branch_ids = _branches(workspace_branch_id)
    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    waiting, waiting_since = work_repo.waiting_enrolments(branch_ids)
    if waiting:
        rows.append(_row("waiting", f"{_plural(waiting, 'student is', 'students are')} waiting for a batch", "/branch/waiting", "Allocate",
                         waiting, waiting_since))

    decide = decisions(branch_ids)
    if decide["total"]:
        parts = [text for count, text in ((decide["reschedule_requests"], _plural(decide["reschedule_requests"], "reschedule request")),
                                          (decide["extra_classes"], _plural(decide["extra_classes"], "extra class", "extra classes"))) if count]
        rows.append(_row("decisions", f"{' and '.join(parts)} to decide", "/branch/schedule", "Decide", decide["total"], decide["oldest_at"],
                         search={"decide": 1}))

    results, results_since = work_repo.results_to_publish(branch_ids)
    if results:
        rows.append(_row("results", f"{_plural(results, 'result')} to review and publish", "/branch/results", "Review results", results, results_since))

    content, content_since = work_repo.content_to_review(branch_ids)
    if content:
        rows.append(_row("content", f"{_plural(content, 'content item')} waiting for review", "/branch/content", "Review content", content,
                         content_since))

    recoveries, recovery_since = work_repo.recovery_requests(branch_ids)
    corrections, correction_since = work_repo.correction_requests(branch_ids)
    if recoveries + corrections:
        parts = [text for count, text in ((recoveries, _plural(recoveries, "recovery request")),
                                          (corrections, _plural(corrections, "attendance correction"))) if count]
        dates = [d for d in (recovery_since, correction_since) if d]
        rows.append(_row("attendance", f"{' and '.join(parts)} to decide", "/branch/progress", "Open requests", recoveries + corrections,
                         min(dates) if dates else None))

    support, support_due = work_repo.support_due(branch_ids, now + SUPPORT_WARNING)
    if support:
        rows.append(_row("support", f"{_plural(support, 'student request')} near or past the reply deadline", "/branch/support", "Reply", support,
                         support_due))

    at_risk = classes_at_risk_today(branch_ids)
    if at_risk:
        first = at_risk[0]
        rows.append(_row("class_day", f"{_plural(len(at_risk), 'class')} today may not run well", "/branch/class-day", "Open Class day", len(at_risk),
                         where=f"{first.batch.batch_code}: {first.title}" + (f" and {len(at_risk) - 1} more" if len(at_risk) > 1 else "")))

    return {"as_of": now, "scope": scope_block(branch_ids), "total": sum(r["count"] for r in rows), "rows": rows}


def attendance_summary(branch_id: int | None = None) -> dict:
    """The counts on the tabs of Attendance & progress: students below the attendance alert, recovery requests and corrections waiting.
    Super Admin and Founder read it across branches (with the branch filter)."""
    branch_ids = _branches(branch_id)
    filters = {"branch_id": branch_id} if branch_id else {}
    return {"students_at_risk": progress_repo.alert_count(filters, progress_service.visible_enrolment_condition()),
            "recoveries": nav_repo.pending_recoveries(branch_ids), "corrections": nav_repo.pending_corrections(branch_ids)}

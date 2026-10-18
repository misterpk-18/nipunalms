"""The Branch Manager's Reports (UX phase U15): figures for a period, each with a drill-down link to the records behind it,
a monthly trend over the last six months, and CSV exports of the same tables.

The period defaults to this month. Dates are business dates in IST. A figure that cannot be calculated honestly is None, never
zero (no marked attendance in the period means no attendance rate). The four progress measures are still never merged into one score.
"""
from datetime import date, datetime, time, timedelta, timezone

from config.timezone import IST, today_ist
from repositories import branch_reports as repo
from repositories import progress as progress_repo
from services import exceptions as exceptions_service
from services import progress, scope
from services.context import current_user
from services.errors import ValidationError

PERIODS = {"this_month": "This month", "last_month": "Last month", "last_90": "Last 90 days", "custom": "Custom dates"}
TREND_MONTHS = 6


def _first_of_month(day: date) -> date:
    return day.replace(day=1)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def resolve_period(period: str | None, start: date | None, end: date | None) -> tuple[str, date, date]:
    """(key, first day, last day inclusive)."""
    today = today_ist()
    key = period or "this_month"
    if key not in PERIODS:
        raise ValidationError("Invalid request data", {"period": [f"Must be one of: {', '.join(PERIODS)}"]})
    if key == "this_month":
        return key, _first_of_month(today), today
    if key == "last_month":
        first = _add_months(_first_of_month(today), -1)
        return key, first, _first_of_month(today) - timedelta(days=1)
    if key == "last_90":
        return key, today - timedelta(days=89), today
    if start is None or end is None:
        raise ValidationError("Choose both dates", {"from": ["Required for custom dates"], "to": ["Required for custom dates"]})
    if end < start:
        raise ValidationError("The end date is before the start", {"to": ["Must not be before the start date"]})
    if (end - start).days > 400:
        raise ValidationError("Choose a shorter period", {"to": ["At most about 13 months"]})
    return key, start, end


def _bounds(first: date, last: date) -> tuple[datetime, datetime]:
    return datetime.combine(first, time.min, tzinfo=IST), datetime.combine(last + timedelta(days=1), time.min, tzinfo=IST)


def _rate(marks: dict[str, int]) -> float | None:
    total = sum(marks.values())
    return round(100 * (marks.get("Present", 0) + marks.get("Late", 0)) / total, 1) if total else None


def _branches(branch_id: int | None) -> set[int] | None:
    if branch_id is not None:
        scope.require_branch(branch_id)
        return {branch_id}
    return scope.visible_branch_ids()


# Where a figure's records live for the Super Admin and Founder (read-only views under their own workspace). Branch work with no
# cross-branch screen (schedule, completion, results, content) has no link for them: they never get a /branch/* link.
CENTRAL_SCREENS = {"/branch/attendance": "/attendance", "/branch/support": "/support", "/branch/issues": "/issues"}


def _prefix() -> str | None:
    return {"SUPER_ADMIN": "/admin", "FOUNDER_CEO": "/founder"}.get(current_user().role_code)


def _drill(to: str, search: dict | None) -> dict | None:
    """`{to, search}` for the router in the session's workspace, or None when this role has no screen for it."""
    prefix = _prefix()
    if prefix is None:
        return {"to": to, "search": search or {}}
    if to.startswith("/branch/batches/"):
        return {"to": f"{prefix}/batches/{to.rsplit('/', 1)[1]}", "search": {}}
    target = CENTRAL_SCREENS.get(to)
    if target is None:
        return None
    keep = {k: v for k, v in (search or {}).items() if k in ("branch", "risk")} if target == "/attendance" else {}
    return {"to": f"{prefix}{target}", "search": keep}


def _figure(key: str, label: str, value, to: str, search: dict | None = None, *, unit: str = "", hint: str | None = None) -> dict:
    return {"key": key, "label": label, "value": value, "unit": unit, "hint": hint, "drill": _drill(to, search)}


def _measures(first: date, last: date, branch_ids) -> dict:
    start, end = _bounds(first, last)
    now = datetime.now(timezone.utc)
    classes = repo.classes_by_state(branch_ids, start, end)
    marks = repo.attendance_marks(branch_ids, start, end)
    recoveries = repo.recoveries_by_status(branch_ids, start, end)
    decisions = repo.decisions_by_outcome(branch_ids, start, end)
    support = repo.support_figures(branch_ids, start, end, now)
    issued = repo.certificates_issued(branch_ids, first, last + timedelta(days=1))
    return {"classes": classes, "marks": marks, "recoveries": recoveries, "decisions": decisions, "support": support, "issued": issued,
            "results": repo.results_published(branch_ids, start, end), "content": repo.content_released(branch_ids, start, end)}


def _figures(m: dict, branch_ids, branch_id: int | None, first: date, last: date) -> list[dict]:
    window = {"from": first.isoformat(), "to": last.isoformat()}
    branch = {"branch": branch_id} if branch_id else {}
    at_risk = progress_repo.alert_count({"branch_id": branch_id} if branch_id else {}, progress.visible_enrolment_condition())
    issues = exceptions_service.counts(branch_ids)["total"]
    complete = m["decisions"].get("Complete", 0)
    other = sum(n for d, n in m["decisions"].items() if d != "Complete")
    return [
        _figure("classes_held", "Classes held", m["classes"].get("Delivered", 0), "/branch/schedule", {"tab": "past", **window, **branch}),
        _figure("classes_cancelled", "Classes cancelled", m["classes"].get("Cancelled", 0), "/branch/schedule", {"tab": "past", **window, **branch}),
        _figure("attendance_rate", "Attendance rate", _rate(m["marks"]), "/branch/attendance", {"tab": "students", **branch}, unit="%",
                hint=None if m["marks"] else "No attendance was marked in this period"),
        _figure("at_risk", "Students below the attendance alert", at_risk, "/branch/attendance", {"tab": "students", "risk": 1, **branch},
                hint="Right now, not only in this period"),
        _figure("recoveries", "Recovery requests", sum(m["recoveries"].values()), "/branch/attendance", {"tab": "recoveries", **branch}),
        _figure("completed", "Courses marked complete", complete, "/branch/completion", {"stage": "completed", **branch}),
        _figure("not_yet", "Not yet complete or needs recovery", other, "/branch/completion", {"stage": "ready", **branch}),
        _figure("certificates", "Certificates issued", m["issued"], "/branch/completion", {"stage": "issued", **branch}),
        _figure("results", "Results published", m["results"], "/branch/results", {**branch}),
        _figure("content", "Content released", m["content"], "/branch/content", {"tab": "released", **branch}),
        _figure("support_opened", "Support requests opened", m["support"]["opened"], "/branch/support", {"view": "all", **branch}),
        _figure("support_resolved", "Support requests resolved", m["support"]["resolved"], "/branch/support", {"view": "done", **branch}),
        _figure("support_overdue", "Support replies overdue now", m["support"]["overdue_now"], "/branch/support", {"view": "needs_action", **branch},
                hint="Right now, not only in this period"),
        _figure("issues", "Open issues", issues, "/branch/issues", {**branch}, hint="Right now, not only in this period"),
    ]


def _batches(branch_id: int | None) -> list[dict]:
    rows = progress.branch_summary(branch_id)["batches"]
    return [{"batch": r["batch"], "state": r["state"], "students": r["students"], "avg_delivery": r["avg_delivery"],
             "avg_attendance": r["avg_attendance"], "avg_required_learning": r["avg_required_learning"], "alerts": r["attendance_alerts"],
             "drill": _drill(f"/branch/batches/{r['batch']['batch_id']}", None)} for r in rows]


def _trends(branch_ids) -> list[dict]:
    this_month = _first_of_month(today_ist())
    out = []
    for back in range(TREND_MONTHS - 1, -1, -1):
        first = _add_months(this_month, -back)
        last = _add_months(first, 1) - timedelta(days=1)
        m = _measures(first, last, branch_ids)
        out.append({"month": first.strftime("%Y-%m"), "label": first.strftime("%b %Y"), "classes_held": m["classes"].get("Delivered", 0),
                    "attendance_rate": _rate(m["marks"]), "completed": m["decisions"].get("Complete", 0), "certificates": m["issued"],
                    "support_opened": m["support"]["opened"]})
    return out


def report(period: str | None, start: date | None, end: date | None, branch_id: int | None) -> dict:
    key, first, last = resolve_period(period, start, end)
    branch_ids = _branches(branch_id)
    m = _measures(first, last, branch_ids)
    return {"period": {"key": key, "label": PERIODS[key], "from": first, "to": last}, "periods": PERIODS, "scope": {"branch_id": branch_id},
            "figures": _figures(m, branch_ids, branch_id, first, last), "batches": _batches(branch_id), "trends": _trends(branch_ids)}


SECTIONS = ("figures", "batches", "trends", "certificates")


def export(section: str, fmt: str, period: str | None, start: date | None, end: date | None, branch_id: int | None) -> tuple[str, bytes, str]:
    """(filename, bytes, mime type) of one table of the report."""
    from services import exports
    if fmt != "csv":
        raise ValidationError("Choose CSV", {"format": ["Only CSV is available; Excel opens it directly"]})
    if section not in SECTIONS:
        raise ValidationError("Invalid request data", {"section": [f"Must be one of: {', '.join(SECTIONS)}"]})
    data = report(period, start, end, branch_id)
    window = f"{data['period']['from']}_to_{data['period']['to']}"
    if section == "figures":
        headers, rows = ["Figure", "Value", "Unit", "Period"], [[f["label"], f["value"], f["unit"], window] for f in data["figures"]]
    elif section == "batches":
        headers = ["Batch", "Course", "State", "Students", "Curriculum delivered %", "Attendance %", "Required learning %", "Below attendance alert"]
        rows = [[b["batch"]["batch_code"], b["batch"].get("course_code"), b["state"], b["students"], b["avg_delivery"], b["avg_attendance"],
                 b["avg_required_learning"], b["alerts"]] for b in data["batches"]]
    elif section == "trends":
        headers = ["Month", "Classes held", "Attendance rate %", "Courses marked complete", "Certificates issued", "Support requests opened"]
        rows = [[t["label"], t["classes_held"], t["attendance_rate"], t["completed"], t["certificates"], t["support_opened"]] for t in data["trends"]]
    else:
        headers = ["Certificate number", "Version", "Student", "Student ID", "Course", "Branch", "Issue date"]
        rows = [[c.certificate_number, c.version, c.holder_name, c.student.student_code, c.course.title, c.branch.branch_name, c.issue_date]
                for c in repo.issued_list(_branches(branch_id), data["period"]["from"], data["period"]["to"] + timedelta(days=1))]
    return f"report-{section}-{window}.csv", exports.to_csv(headers, rows), "text/csv; charset=utf-8"

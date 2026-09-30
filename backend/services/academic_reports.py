"""Academic Reports (`GET /academic/reports`): one block per branch the user sees.

Reuses the S4 branch summary (per-batch averages of each measure, which stay separate) and adds the recovery, completion-review
and certificate register aggregates. A figure that cannot be computed honestly says so: no running batch is Empty, missing source
data is Partial Data, and a measure with no configured basis is Not Configured. Nothing is reported as zero by default.
"""
from collections import defaultdict
from datetime import datetime, timezone

from repositories import branches as branches_repo
from repositories import reports as reports_repo
from services import progress, scope
from services.cards import safe_card

RUNNING = "Running"


def _weighted(rows: list[dict], key: str) -> float | None:
    """Average of a per-batch average, weighted by each batch's students (None when no batch has a value)."""
    pairs = [(row[key], row["students"]) for row in rows if row[key] is not None and row["students"]]
    total = sum(weight for _, weight in pairs)
    return round(sum(value * weight for value, weight in pairs) / total, 1) if total else None


def _delivery(rows: list[dict]) -> dict:
    if not rows:
        return {"state": "Empty", "percent": None, "batches": 0, "message": "No batch is running at this branch."}
    value = _weighted(rows, "avg_delivery")
    incomplete = [r["batch"]["batch_code"] for r in rows if r["avg_delivery"] is None or not r["students"]]
    return {
        "state": "Partial Data" if incomplete or value is None else "Calculated", "percent": value, "batches": len(rows),
        "message": f"No delivery figure yet for {', '.join(incomplete)}." if incomplete else None,
    }


def _attendance(rows: list[dict], recoveries: dict[str, int]) -> dict:
    value = _weighted(rows, "avg_attendance")
    partial = sum(r["partial_data"] for r in rows)
    approved = recoveries.get("Approved", 0) + recoveries.get("Completed", 0)
    if not rows or value is None:
        state = "Empty"
    else:
        state = "Partial Data" if partial else "Calculated"
    return {
        "state": state, "percent": value, "partial_data_students": partial,
        "recovery": {"requested": recoveries.get("Requested", 0), "approved": recoveries.get("Approved", 0),
                     "completed": recoveries.get("Completed", 0), "rejected": recoveries.get("Rejected", 0), "approved_or_completed": approved},
        "alerts": sum(r["attendance_alerts"] for r in rows),
        "message": None if state in ("Calculated", "Partial Data") else "No attendance has been marked for the running batches yet.",
    }


def _completion(counts: dict[str, int]) -> dict:
    closed, open_, gap = counts.get("Decided", 0), counts.get("Open", 0), counts.get("completed_without_review", 0)
    if not (closed or open_ or gap):
        return {"state": "Empty", "closed": 0, "open": 0, "completed_without_review": 0, "message": "No completion review has been opened."}
    return {
        "state": "Partial Data" if gap else "Calculated", "closed": closed, "open": open_, "completed_without_review": gap,
        "message": f"{gap} completed enrolment(s) have no completion review record." if gap else None,
    }


def _lead_time(samples: list[tuple[datetime, object]]) -> dict:
    """Days from the completion decision to the certificate's issue date. Not Configured until an issued certificate traces back
    to a decided review."""
    if not samples:
        return {"state": "Not Configured", "average_days": None, "issued": 0,
                "message": "No issued certificate traces back to a decided completion review, so a lead time cannot be computed."}
    days = [(issued - decided.date()).days for decided, issued in samples]
    return {"state": "Calculated", "average_days": round(sum(days) / len(days), 1), "issued": len(days), "message": None}


def reports(branch_id: int | None) -> dict:
    if branch_id is not None:
        scope.require_branch(branch_id)
    visible = scope.visible_branch_ids()
    branch_ids = {branch_id} if branch_id is not None else visible
    branches = branches_repo.list_active(branch_ids)
    ids = {b.branch_id for b in branches}

    summary = progress.branch_summary(branch_id)["batches"]
    rows_by_branch: dict[int, list[dict]] = defaultdict(list)
    for row in summary:
        if row["state"] == RUNNING:
            rows_by_branch[row["branch"]["branch_id"]].append(row)

    recoveries = safe_card("academic_report_recoveries", lambda: {"data": reports_repo.recovery_counts(ids)})
    completion = safe_card("academic_report_completion", lambda: {"data": reports_repo.completion_review_counts(ids)})
    lead_samples = safe_card("academic_report_lead_time", lambda: {"data": reports_repo.certificate_lead_times(ids)})

    def block(branch) -> dict:
        rows = rows_by_branch.get(branch.branch_id, [])
        counts = recoveries["data"].get(branch.branch_id, {}) if "data" in recoveries else {}
        samples = [(decided, issued) for b, decided, issued in lead_samples["data"] if b == branch.branch_id] if "data" in lead_samples else []
        return {
            "branch": branch.to_summary(),
            "curriculum_delivered": _delivery(rows),
            "attendance": _attendance(rows, counts) if "data" in recoveries else recoveries,
            "completion_reviews": _completion(completion["data"].get(branch.branch_id, {})) if "data" in completion else completion,
            "certificate_lead_time": _lead_time(samples) if "data" in lead_samples else lead_samples,
        }

    return {"as_of": datetime.now(timezone.utc), "branches": [block(b) for b in branches]}

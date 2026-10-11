"""`GET /trainer/to-grade`: the trainer's one inbox of work to grade (UX plan U13).

Assignment submissions (the newest version, no review yet, for assignments the trainer reviews) and test attempts (submitted, with
written or coding answers still to mark, for tests the trainer grades) in one list: overdue first, then the oldest. Each row says
what it is, who handed it in, how long it has waited and where to open it. The same list is what "Save & next" walks through.
"""
from datetime import datetime, timezone

from services import attempts, review_clock, submissions

LIMIT = 200


def _submission_row(submission) -> dict:
    assignment = submission.assignment
    due = review_clock.review_due(assignment.kind, submission.submitted_at, assignment.batch.branch_id)
    return {
        "key": f"submission-{submission.submission_id}",
        "kind": "submission",
        "id": submission.submission_id,
        "title": assignment.title,
        "type": assignment.kind,
        "student": submission.student.to_summary(),
        "batch": assignment.batch.to_summary(),
        "submitted_at": submission.submitted_at,
        "is_late": submission.is_late,
        "review_due": due,
        "overdue": bool(due and due["overdue"]),
        "started": submission.review_started_at is not None,
        "max_marks": f"{assignment.max_marks:.2f}",
        "to_mark": None,
    }


def _attempt_row(row: dict) -> dict:
    due = row["review_due"]
    return {
        "key": f"attempt-{row['attempt_id']}",
        "kind": "attempt",
        "id": row["attempt_id"],
        "title": row["test"]["title"],
        "type": row["test"]["kind"],
        "student": row["student"],
        "batch": row["batch"],
        "submitted_at": row["submitted_at"],
        "is_late": False,
        "review_due": due,
        "overdue": bool(due and due["overdue"]),
        "started": True,
        "max_marks": row["total_marks"],
        "to_mark": row["manual_pending"],
    }


def _order(item: dict):
    # Overdue first, then the one that has waited longest; the key keeps the order stable
    return (not item["overdue"], item["submitted_at"] or datetime.max.replace(tzinfo=timezone.utc), item["key"])


def queue(batch_id: int | None = None) -> list[dict]:
    """Everything the signed-in trainer still has to grade, in the order to work through it."""
    filters = {"reviewer_me": True}
    if batch_id:
        filters["batch_id"] = batch_id
    rows, _ = submissions.list_submissions({**filters, "status": "Awaiting Review"}, 1, LIMIT)
    items = [_submission_row(s) for s in rows]
    marks, _ = attempts.list_attempts({**filters, "grading_status": "Awaiting Grading"}, 1, LIMIT)
    items += [_attempt_row(a) for a in marks]
    return sorted(items, key=_order)


def to_grade(batch_id: int | None = None) -> dict:
    """The inbox: the items plus the counts shown over it and the batches the trainer can filter by."""
    items = queue(batch_id)
    everything = items if not batch_id else queue(None)
    batches = {i["batch"]["batch_id"]: i["batch"] for i in everything}
    return {
        "as_of": datetime.now(timezone.utc),
        "items": items,
        "counts": {
            "total": len(items),
            "submissions": sum(1 for i in items if i["kind"] == "submission"),
            "attempts": sum(1 for i in items if i["kind"] == "attempt"),
            "overdue": sum(1 for i in items if i["overdue"]),
        },
        "batches": sorted(batches.values(), key=lambda b: b["batch_code"]),
    }

"""Tasks & Tests (`GET /me/work`, UX phase U9): the student's assignments and tests on one list, split into what they must do,
what is waiting for someone else, and what is finished. It reads the same rows the assignment and test screens read
(`assignments.list_assignments`, `tests.list_tests`), so the three always agree on a task's state.

  * To do: open work (due soon, overdue, to resubmit, a test that can be taken or booked), overdue first, then the nearest date.
  * Waiting for review: handed in, not yet reviewed, or marked but not yet published (a formal result waits for the Branch Manager).
  * Done: reviewed or marked work, and work whose window closed without a hand-in ("Missed"), newest first.

`state` is a code in the status dictionary of `state_domain` (work, test or slot), so the screen shows the plain label.
"""
from datetime import datetime, timezone

from repositories import results as results_repo
from repositories import tests as tests_repo
from services import assessment_scope as access
from services import assignments as assignments_service
from services import tests as tests_service
from services.errors import Forbidden

ALL = 500
SECTIONS = ("todo", "waiting", "done")
OPEN_ASSIGNMENT_STATES = ("Upcoming", "Due", "Overdue", "Resubmission Requested")
FAR_FUTURE = datetime.max.replace(tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _base(kind: str, row: dict) -> dict:
    return {
        "kind": kind,
        "id": row["assignment_id"] if kind == "assignment" else row["test_id"],
        "code": row["assignment_code"] if kind == "assignment" else row["test_code"],
        "title": row["title"],
        "type": row["kind"],  # the kind of assignment or test (Project, Practice quiz, Mock interview, ...)
        "is_required": row["is_required"],
        "batch": row["batch"],
        "module": row["module"],
        "topic": row["topic"],
        "enrolment_id": row["my"]["enrolment_id"],
    }


def _item(common: dict, section: str, state: str, domain: str, action: str, sort_at: datetime | None, **fields) -> dict:
    """One row: the defaults, then what the item has in common, then what this state sets."""
    return {"due_at": None, "opens_at": None, "overdue": False, "late": False, "marks": None, "max_marks": None, "duration_minutes": None,
            "attempts_remaining": None, "in_progress": False, **common,
            "section": section, "state": state, "state_domain": domain, "action": action, "sort_at": sort_at, **fields}


def _assignment(row: dict) -> dict:
    my, state = row["my"], row["my"]["state"]
    versions = my["versions"]
    submitted_at = versions[-1]["submitted_at"] if versions else None
    published = my["result"]["status"] == "Published"
    common = {**_base("assignment", row), "late": my["is_late"], "due_at": row["due_at"]}
    if state in OPEN_ASSIGNMENT_STATES:
        if state == "Overdue" and not my["window"]["allowed"]:
            return _item(common, "done", "Missed", "work", "View", row["due_at"])
        deadline = my["window"]["deadline"] or row["due_at"]
        action = "Resubmit" if state == "Resubmission Requested" else "Submit"
        return _item(common, "todo", state, "work", action, deadline, due_at=deadline, overdue=state == "Overdue")
    if state in ("Submitted", "Under Review"):
        return _item(common, "waiting", state, "work", "View", submitted_at)
    return _item(common, "done", state, "work", "View", submitted_at, marks=my["result"]["marks"] if published else None,
                 max_marks=my["result"]["max_marks"])


def _test(row: dict, results: dict, now: datetime) -> dict | None:
    status = row["status"]
    if status not in ("Scheduled", "Available", "Closed"):
        return None  # not released: nothing for the student to do yet
    my = row["my"]
    slot = my["slot"]
    attempt = my["latest_attempt"]
    common = {**_base("test", row), "due_at": row["closes_at"], "opens_at": row["opens_at"], "duration_minutes": row["duration_minutes"],
              "attempts_remaining": my["attempts_remaining"], "in_progress": my["in_progress_attempt_id"] is not None}

    if row["kind"] == "Mock interview":
        if slot is not None:
            if slot["status"] == "Completed":
                return _item(common, "done", "Completed", "slot", "View", slot["starts_at"])
            if slot["status"] == "Confirmed":
                return _item(common, "todo", "Confirmed", "slot", "View", slot["starts_at"], due_at=slot["starts_at"])
            return _item(common, "waiting", "Slot Confirmation Pending", "slot", "View", slot["starts_at"])
        if status == "Closed":
            return _item(common, "done", "Missed", "work", "View", row["closes_at"])
        if status == "Scheduled":
            return _item(common, "todo", "Scheduled", "test", "View", row["opens_at"])
        return _item(common, "todo", "Available", "test", "Book a slot", row["closes_at"])

    if my["in_progress_attempt_id"] is not None:
        return _item(common, "todo", "In progress", "test", "Resume test", row["closes_at"])
    if my["attempts_used"] > 0:
        submitted_at = attempt["submitted_at"] if attempt else None
        result = results.get(row["test_id"])
        graded = bool(attempt) and attempt["grading_status"] == "Graded"
        if row["is_formal"]:
            published = result is not None and result.status == "Published"
            marks = f"{result.final_marks:.2f}" if published else None
            if published:
                return _item(common, "done", "Graded", "test", "View", submitted_at, marks=marks, max_marks=f"{result.max_marks:.2f}")
            return _item(common, "waiting", "Under Review" if graded else "Submitted", "work", "View", submitted_at)
        if graded:
            marks = attempt.get("score")
            max_marks = f"{tests_repo.total_marks(row['test_id']):.2f}" if marks is not None else None
            action = "Try again" if my["can_start"] else "View"
            return _item(common, "done", "Graded", "test", action, submitted_at, marks=marks, max_marks=max_marks)
        return _item(common, "waiting", "Submitted", "work", "View", submitted_at)
    if status == "Closed":
        return _item(common, "done", "Missed", "work", "View", row["closes_at"])
    if status == "Scheduled":
        return _item(common, "todo", "Scheduled", "test", "View", row["opens_at"])
    return _item(common, "todo", "Available", "test", "Start test", row["closes_at"])


def _todo_order(item: dict):
    return (0 if item["overdue"] else 1, item["sort_at"] or FAR_FUTURE)


def _newest_first(item: dict):
    return item["sort_at"] or datetime.min.replace(tzinfo=timezone.utc)


def get_work() -> dict:
    """{counts: {todo, waiting, done, overdue}, todo: [...], waiting: [...], done: [...]}, items as described above."""
    if not access.is_student():
        raise Forbidden("This is a student view")
    now = _now()
    assignments, _ = assignments_service.list_assignments({}, 1, ALL)
    tests, _ = tests_service.list_tests({}, 1, ALL)
    enrolment_ids = {row["my"]["enrolment_id"] for row in tests}
    results = {r.test_id: r for r in results_repo.for_enrolments(enrolment_ids) if r.test_id is not None}

    items = [_assignment(a) for a in assignments]
    items += [item for item in (_test(t, results, now) for t in tests) if item is not None]
    grouped = {section: [i for i in items if i["section"] == section] for section in SECTIONS}
    grouped["todo"].sort(key=_todo_order)
    grouped["waiting"].sort(key=_newest_first, reverse=True)
    grouped["done"].sort(key=_newest_first, reverse=True)
    counts = {section: len(grouped[section]) for section in SECTIONS}
    counts["overdue"] = sum(i["overdue"] for i in grouped["todo"])
    return {"counts": counts, **grouped}


def todo_count() -> int:
    """How many things need the student: the badge on the Tasks & Tests item."""
    return get_work()["counts"]["todo"]

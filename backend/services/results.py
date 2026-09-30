"""Results: provisional marks (trainer review, test grading), moderation and publication by the Academic Coordinator.

A result moves Provisional -> Moderated (marks adjusted, reason kept) -> Published. Students only ever see Published results;
a provisional score is never shown as a score, and a published result cannot be changed (the database refuses it).
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from config.database import db
from models import Assignment, Enrolment, Result, Test, TestAttempt
from repositories import assignments as assignments_repo
from repositories import results as results_repo
from repositories import tests as tests_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import assessment_scope as access
from services import audit, notifications, scope
from services.assessment_rules import configuration_gaps, is_formal
from services.assignments import task_state
from services.context import current_user
from services.errors import BusinessRule, NotFound, ValidationError


def _marks(value: Decimal) -> str:
    return f"{value:.2f}"


def upsert_provisional(*, enrolment: Enrolment, batch_id: int, max_marks: Decimal, marks: Decimal,
                       assignment_id: int | None = None, test_id: int | None = None,
                       submission_id: int | None = None, attempt_id: int | None = None) -> Result:
    """Record the trainer's marks for an item as this student's provisional result (replacing an earlier provisional one)."""
    existing = (results_repo.for_assignment(assignment_id, enrolment.enrolment_id) if assignment_id
                else results_repo.for_test(test_id, enrolment.enrolment_id))
    if existing is not None:
        if existing.status == "Published":
            raise BusinessRule("The result is already published and cannot be replaced")
        existing.provisional_marks, existing.max_marks = marks, max_marks
        existing.submission_id, existing.attempt_id = submission_id, attempt_id
        # A new provisional score supersedes any earlier moderation
        existing.status, existing.moderated_marks, existing.moderation_reason = "Provisional", None, None
        existing.moderated_by = existing.moderated_at = None
        db.session.flush()
        return existing
    result = Result(enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id, batch_id=batch_id, assignment_id=assignment_id,
                    test_id=test_id, submission_id=submission_id, attempt_id=attempt_id, max_marks=max_marks, provisional_marks=marks)
    db.session.add(result)
    db.session.flush()
    return result


def _load_for_moderation(result_id: int) -> Result:
    result = results_repo.get_result(result_id)
    if result is None:
        raise NotFound("Result not found")
    scope.assert_can_view_batch(result.batch)
    access.assert_can_moderate(result.batch)
    return result


def moderate(result_id: int, marks: Decimal, reason: str) -> Result:
    """Adjust the marks that will be published; the trainer's provisional marks and the reason stay on record."""
    result = _load_for_moderation(result_id)
    if result.status == "Published":
        raise BusinessRule("A published result cannot be moderated")
    if marks > result.max_marks:
        raise ValidationError("Invalid request data", {"marks": [f"Must be {_marks(result.max_marks)} or less"]})
    if marks == result.counting_marks:
        raise ValidationError("Invalid request data", {"marks": ["These marks are unchanged; publish the result instead"]})
    old = {"marks": _marks(result.counting_marks), "status": result.status}
    user = current_user()
    result.moderated_marks, result.moderation_reason = marks, reason
    result.moderated_by, result.moderated_at = user.user_id, datetime.now(timezone.utc)
    result.status = "Moderated"
    db.session.flush()
    audit.record("moderate", "result", result_id, old=old, new={"marks": _marks(marks), "status": "Moderated"}, reason=reason,
                 branch_id=result.batch.branch_id)
    return result


def publish(filters: dict) -> list[Result]:
    """Publish results by id, or every unpublished result of an assignment / test (optionally one batch). Students are told."""
    if filters.get("result_ids"):
        found = [results_repo.get_result(i) for i in filters["result_ids"]]
        if any(r is None for r in found):
            raise NotFound("Result not found")
        candidates = found
    elif filters.get("assignment_id") or filters.get("test_id"):
        candidates = list(db.session.execute(results_repo.list_stmt(filters, access.visible_batch_clause)).scalars().unique())
    else:
        raise ValidationError("Invalid request data", {"result_ids": ["Give result_ids, an assignment_id or a test_id"]})

    for result in candidates:
        scope.assert_can_view_batch(result.batch)
        access.assert_can_moderate(result.batch)
    pending = [r for r in candidates if r.status != "Published"]
    if not pending:
        raise BusinessRule("Nothing to publish: every selected result is already published")

    user, now = current_user(), datetime.now(timezone.utc)
    for result in pending:
        old = {"status": result.status, "marks": _marks(result.counting_marks)}
        result.final_marks = result.counting_marks
        result.status = "Published"
        result.published_by, result.published_at = user.user_id, now
        db.session.flush()
        audit.record("publish", "result", result.result_id, old=old, new={"status": "Published", "marks": _marks(result.final_marks)},
                     branch_id=result.batch.branch_id)
        item = result.item()
        student_user = _student_user_id(result.student_id)
        if student_user:
            link = f"/assignments/{item['item_id']}" if item["kind"] == "Assignment" else "/results"
            notifications.notify(category="Results", title="Result published", body=f"Your result for {item['title']} is published.",
                                 link=link, event_key=f"result-published:{result.result_id}", recipient_user_ids=[student_user],
                                 branch_id=result.batch.branch_id)
    return pending


def _student_user_id(student_id: int) -> int | None:
    user = users_repo.get_by_student_id(student_id)
    return user.user_id if user else None


# ---------------------------------------------------------------- reads

def list_results(filters: dict, page: int, per_page: int) -> tuple[list[Result], dict]:
    """Staff: results of the batches they see, with every stage of the marks."""
    if filters.get("batch_id"):
        access.load_batch(filters["batch_id"])
    return paginate(results_repo.list_stmt(filters, access.visible_batch_clause), page, per_page)


def _assignment_row(assignment: Assignment, versions: list, result: Result | None, now: datetime) -> dict:
    state = task_state(assignment, versions, result, now)
    if result is not None and result.status == "Published":
        label, score = "Published", f"{_marks(result.final_marks)} / {_marks(result.max_marks)}"
    elif result is not None:
        label, score = "Provisional — pending moderation", None
    elif state == "Resubmission Requested":
        label, score = "Resubmission requested", None
    else:
        label, score = "Pending review", None
    return {"key": f"assignment-{assignment.assignment_id}", "kind": "Assignment", "item_id": assignment.assignment_id,
            "item": assignment.title, "type": assignment.kind, "score": score, "state": label, "pass_status": None,
            "published_at": result.published_at if result is not None and result.status == "Published" else None}


def _test_row(test: Test, result: Result | None, awaiting_grading: bool) -> dict:
    if result is not None and result.status == "Published":
        label, score = "Published", f"{_marks(result.final_marks)} / {_marks(result.max_marks)}"
        passed = None if test.pass_marks is None else ("Passed" if result.final_marks >= test.pass_marks else "Not Yet Passed")
    elif result is not None:
        label, score, passed = "Provisional — pending moderation", None, None
    else:
        label, score, passed = ("Pending review" if awaiting_grading else "Not attempted"), None, None
    return {"key": f"test-{test.test_id}", "kind": "Test", "item_id": test.test_id, "item": test.title, "type": test.kind, "score": score,
            "state": label, "pass_status": passed,
            "published_at": result.published_at if result is not None and result.status == "Published" else None}


def my_results() -> list[dict]:
    """A student's results screen: every assessed item they have work in, and only Published items carry a score."""
    now = datetime.now(timezone.utc)
    seats = access.student_enrolments_by_batch()
    enrolment_ids = {e.enrolment_id for e in seats.values()}
    results = results_repo.for_enrolments(enrolment_ids)
    by_assignment = {(r.assignment_id, r.enrolment_id): r for r in results if r.assignment_id is not None}
    by_test = {(r.test_id, r.enrolment_id): r for r in results if r.test_id is not None}

    rows = []
    assignments = assignments_repo.released_for_batches(set(seats), now)
    versions = assignments_repo.versions_for_enrolments(enrolment_ids, [a.assignment_id for a in assignments])
    for assignment in assignments:
        enrolment_id = seats[assignment.batch_id].enrolment_id
        submitted = versions.get((assignment.assignment_id, enrolment_id), [])
        if submitted:
            rows.append(_assignment_row(assignment, submitted, by_assignment.get((assignment.assignment_id, enrolment_id)), now))

    attempts = db.session.execute(
        select(TestAttempt).where(TestAttempt.enrolment_id.in_(enrolment_ids), TestAttempt.status == "Submitted")
    ).scalars().unique().all() if enrolment_ids else []
    attempted: dict[tuple[int, int], list[TestAttempt]] = {}
    for attempt in attempts:
        attempted.setdefault((attempt.test_id, attempt.enrolment_id), []).append(attempt)
    for (test_id, enrolment_id), tries in sorted(attempted.items()):
        test = tries[0].test
        if not is_formal(test):
            continue
        rows.append(_test_row(test, by_test.get((test_id, enrolment_id)), any(a.grading_status == "Awaiting Grading" for a in tries)))
    return rows


def review_queue(filters: dict) -> list[dict]:
    """The moderation screen: per assessment and batch, how many results are provisional, moderated, published, plus tests not ready."""
    clause = access.visible_batch_clause
    batch_id = filters.get("batch_id")
    if batch_id:
        access.load_batch(batch_id)
    counts = results_repo.status_counts(clause, batch_id)
    assignments = results_repo.assignments_by_ids({a for a, _, _, _, _ in counts if a})
    tests = results_repo.tests_by_ids({t for _, t, _, _, _ in counts if t})

    grouped: dict[tuple, dict] = {}
    for assignment_id, test_id, batch, status, count in counts:
        key = ("Assignment", assignment_id, batch) if assignment_id else ("Test", test_id, batch)
        entry = grouped.setdefault(key, {"Provisional": 0, "Moderated": 0, "Published": 0})
        entry[status] = count
    awaiting = _awaiting_grading_by_test()

    rows = []
    for (kind, item_id, batch), entry in grouped.items():
        item = assignments[item_id] if kind == "Assignment" else tests[item_id]
        counts_out = {"provisional": entry["Provisional"], "moderated": entry["Moderated"], "published": entry["Published"],
                      "awaiting_grading": awaiting.get(item_id, 0) if kind == "Test" else 0}
        if entry["Provisional"]:
            state = "Awaiting moderation"
        elif entry["Moderated"]:
            state = "Moderated — publish pending"
        else:
            state = "Published"
        rows.append({"kind": kind, "item_id": item_id, "code": item.assignment_code if kind == "Assignment" else item.test_code,
                     "title": item.title, "type": item.kind, "batch": item.batch.to_summary(), "counts": counts_out, "state": state,
                     "can_moderate": access.can_moderate_batch(item.batch)})
    rows.sort(key=lambda r: (r["state"] == "Published", r["batch"]["batch_code"], r["title"]))
    rows += _tests_not_ready(filters, clause)
    return rows


def _awaiting_grading_by_test() -> dict[int, int]:
    stmt = select(TestAttempt.test_id, func.count()).where(TestAttempt.grading_status == "Awaiting Grading").group_by(TestAttempt.test_id)
    return dict(db.session.execute(stmt).all())


def _tests_not_ready(filters: dict, clause) -> list[dict]:
    """Tests that cannot be released yet (with what is missing), so the coordinator sees them next to the results work."""
    stmt = tests_repo.list_stmt({"release_status": "Configuration Pending", **({"batch_id": filters["batch_id"]} if filters.get("batch_id") else {})}, clause)
    rows = []
    for test in db.session.execute(stmt).scalars().unique():
        gaps = configuration_gaps(test, tests_repo.question_count(test.test_id), tests_repo.slot_count(test.test_id))
        rows.append({"kind": "Test", "item_id": test.test_id, "code": test.test_code, "title": test.title, "type": test.kind,
                     "batch": test.batch.to_summary(), "counts": {"provisional": 0, "moderated": 0, "published": 0, "awaiting_grading": 0},
                     "state": "Configuration Pending", "gaps": gaps, "can_moderate": access.can_moderate_batch(test.batch)})
    return rows

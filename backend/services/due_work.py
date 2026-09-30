"""Ask Nipuna's due-work facts: the student's open assignments and tests (S3), read through the same rules the Tasks and Tests
screens use. Registered as the `due_work` fact provider in services.ask_nipuna; it shares nothing with another student.
"""
from datetime import datetime, timezone

from models import Student
from repositories import assignments as assignments_repo
from repositories import results as results_repo
from repositories import tests as tests_repo
from services import assessment_scope as access
from services.ai_facts import format_ist
from services.assessment_rules import effective_status
from services.assignments import task_state

# A task still needs the student's action in these states; Submitted / Under Review / Reviewed do not
OPEN_TASK_STATES = {"Upcoming", "Due", "Overdue", "Resubmission Requested"}
OPEN_TEST_STATUSES = {"Scheduled", "Available"}
LIMIT = 10


def open_items(student: Student) -> tuple[list[tuple], list[tuple]]:
    """The student's open work as raw records: [(Assignment, task state)] and [(Test, effective status)]. Student Home and
    Ask Nipuna both read through this, so the two always agree on what is due."""
    now = datetime.now(timezone.utc)
    seats = access.seats_of_student(student.student_id)
    enrolment_ids = {e.enrolment_id for e in seats.values()}

    released = assignments_repo.released_for_batches(set(seats), now)
    versions = assignments_repo.versions_for_enrolments(enrolment_ids, [a.assignment_id for a in released])
    results = {(r.assignment_id, r.enrolment_id): r for r in results_repo.for_enrolments(enrolment_ids) if r.assignment_id is not None}
    assignments = []
    for a in released:
        enrolment_id = seats[a.batch_id].enrolment_id
        state = task_state(a, versions.get((a.assignment_id, enrolment_id), []), results.get((a.assignment_id, enrolment_id)), now)
        if state in OPEN_TASK_STATES:
            assignments.append((a, state))

    tests = tests_repo.for_batches(set(seats))
    attempts = tests_repo.attempts_for_enrolments(enrolment_ids, [t.test_id for t in tests])
    open_tests = []
    for t in tests:
        status = effective_status(t, now)
        if status not in OPEN_TEST_STATUSES:
            continue
        used = sum(1 for x in attempts.get((t.test_id, seats[t.batch_id].enrolment_id), []) if x.status == "Submitted")
        if t.attempts_allowed is not None and used >= t.attempts_allowed:
            continue
        open_tests.append((t, status))
    return assignments, open_tests


def student_due_work(student: Student) -> tuple[dict, list[dict]]:
    assignment_items, test_items = open_items(student)
    sources: list[dict] = []
    assignments = []
    for a, state in assignment_items:
        assignments.append({"code": a.assignment_code, "title": a.title, "state": state, "due": format_ist(a.due_at), "batch": a.batch.batch_code})
        sources.append({"type": "assignment", "id": a.assignment_id, "code": a.assignment_code})
    test_facts = []
    for t, status in test_items:
        test_facts.append({
            "code": t.test_code, "title": t.title, "kind": t.kind, "status": status, "batch": t.batch.batch_code,
            "opens": format_ist(t.opens_at) if t.opens_at else None, "closes": format_ist(t.closes_at) if t.closes_at else None,
        })
        sources.append({"type": "test", "id": t.test_id, "code": t.test_code})

    return {"assignments": assignments[:LIMIT], "tests": test_facts[:LIMIT]}, sources[:2 * LIMIT]

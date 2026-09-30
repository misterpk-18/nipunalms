"""Tests (Module 20): definition, question selection, approval, release and the student's list.

A test moves Configuration Pending -> Not Released (everything set; formal tests also need the Academic Coordinator's approval)
-> Released (students see it as Scheduled / Available / Closed by its window) -> Closed. Selecting questions freezes their wording,
key and marks into the test, so an attempt is always scored against what the student was shown.
"""
from datetime import datetime, timezone

from config.database import db
from config.timezone import IST
from models import Test, TestQuestion
from repositories import batches as batches_repo
from repositories import questions as questions_repo
from repositories import tests as tests_repo
from repositories.common import paginate
from services import assessment_scope as access
from services import audit, notifications, scope
from services.assessment_rules import KIND_DEFAULTS, configuration_gaps, effective_status, is_formal, visible_score
from services.context import current_user
from services.errors import BusinessRule, NotFound, ValidationError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _invalid(field: str, message: str) -> ValidationError:
    return ValidationError("Invalid request data", {field: [message]})


# ---------------------------------------------------------------- status

def refresh_release_status(test: Test) -> None:
    """Configuration Pending <-> Not Released follows what is set; Released and Closed are only changed by release / close."""
    if test.release_status in ("Released", "Closed"):
        return
    gaps = configuration_gaps(test, tests_repo.question_count(test.test_id), tests_repo.slot_count(test.test_id))
    test.release_status = "Configuration Pending" if gaps else "Not Released"
    db.session.flush()


def _staff_extras(test: Test) -> dict:
    now = now_utc()
    gaps = configuration_gaps(test, tests_repo.question_count(test.test_id), tests_repo.slot_count(test.test_id))
    return {
        "status": effective_status(test, now),
        "is_formal": is_formal(test),
        "gaps": gaps,
        "question_count": tests_repo.question_count(test.test_id),
        "total_marks": f"{tests_repo.total_marks(test.test_id):.2f}",
        "attempt_count": tests_repo.attempt_count(test.test_id),
        "slot_count": tests_repo.slot_count(test.test_id),
        "can_manage": access.can_manage_batch(test.batch),
        "can_moderate": access.can_moderate_batch(test.batch),
    }


def student_view(test: Test, enrolment_id: int, attempts: list, slot, now: datetime) -> dict:
    """What a student needs to decide whether and how to start: status, attempts left, their latest attempt or booking."""
    status = effective_status(test, now)
    submitted = [a for a in attempts if a.status == "Submitted"]
    in_progress = next((a for a in attempts if a.status == "In Progress"), None)
    remaining = None if test.attempts_allowed is None else max(test.attempts_allowed - len(submitted), 0)
    if slot is not None:
        my_status = slot.status
    elif in_progress is not None:
        my_status = "In progress"
    elif submitted:
        my_status = f"Submitted — receipt {submitted[-1].receipt_code}"
    else:
        my_status = None
    latest = attempts[-1] if attempts else None
    return {
        "enrolment_id": enrolment_id,
        "my_status": my_status,
        "attempts_used": len(submitted),
        "attempts_remaining": remaining,
        "in_progress_attempt_id": in_progress.attempt_id if in_progress else None,
        "latest_attempt": ({**latest.to_summary(), "score": _score(test, latest)} if latest else None),
        "slot": slot.to_dict(viewer_is_student=True) if slot else None,
        "can_start": status == "Available" and test.kind != "Mock interview" and (remaining is None or remaining > 0 or in_progress is not None),
    }


def _score(test: Test, attempt) -> str | None:
    score = visible_score(test, attempt)
    return None if score is None else f"{score:.2f}"


# ---------------------------------------------------------------- reads

def list_tests(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Students: every test of the batches they sit in (with their own state). Staff: tests of the batches they see."""
    now = now_utc()
    if access.is_student():
        seats = access.student_enrolments_by_batch()
        tests = [t for t in tests_repo.for_batches(set(seats))
                 if (not filters.get("batch_id") or t.batch_id == filters["batch_id"]) and (not filters.get("kind") or t.kind == filters["kind"])]
        enrolment_ids = {e.enrolment_id for e in seats.values()}
        attempts = tests_repo.attempts_for_enrolments(enrolment_ids, [t.test_id for t in tests])
        slots = tests_repo.booked_slots_for(enrolment_ids, [t.test_id for t in tests])
        rows = []
        for test in tests:
            enrolment = seats[test.batch_id]
            view = student_view(test, enrolment.enrolment_id, attempts.get((test.test_id, enrolment.enrolment_id), []), slots.get(test.test_id), now)
            rows.append(test.to_dict(status=effective_status(test, now), is_formal=is_formal(test),
                                     question_count=tests_repo.question_count(test.test_id), my=view))
        start = (page - 1) * per_page
        return rows[start:start + per_page], {"page": page, "per_page": per_page, "total": len(rows), "pages": -(-len(rows) // per_page)}
    if filters.get("batch_id"):
        access.load_batch(filters["batch_id"])
    items, meta = paginate(tests_repo.list_stmt(filters, access.visible_batch_clause), page, per_page)
    return [t.to_dict(**_staff_extras(t)) for t in items], meta


def load_test(test_id: int) -> Test:
    test = tests_repo.get_test(test_id)
    if test is None:
        raise NotFound("Test not found")
    if access.is_student():
        access.student_seat(test.batch_id)
    else:
        scope.assert_can_view_batch(test.batch)
    return test


def get_test(test_id: int) -> dict:
    test = load_test(test_id)
    now = now_utc()
    if access.is_student():
        enrolment = access.student_seat(test.batch_id)
        attempts = tests_repo.attempts_of(test_id, enrolment.enrolment_id)
        slots = tests_repo.booked_slots_for({enrolment.enrolment_id}, [test_id])
        return test.to_dict(status=effective_status(test, now), is_formal=is_formal(test), question_count=tests_repo.question_count(test_id),
                            total_marks=f"{tests_repo.total_marks(test_id):.2f}", my=student_view(test, enrolment.enrolment_id, attempts, slots.get(test_id), now))
    extras = _staff_extras(test)
    # Answer keys go only to the people who build and approve the test, never to the Branch Manager or Founder
    if extras["can_manage"] or extras["can_moderate"]:
        extras["questions"] = [q.to_dict() for q in test.questions]
    return test.to_dict(**extras)


# ---------------------------------------------------------------- authoring

def _check_curriculum_links(batch, module_id: int | None, topic_id: int | None) -> None:
    if module_id and tests_repo.course_of_module(module_id) != batch.course_id:
        raise _invalid("module_id", "The module does not belong to the batch's course")
    if topic_id and tests_repo.course_of_topic(topic_id) != batch.course_id:
        raise _invalid("topic_id", "The topic does not belong to the batch's course")


def _check_settings(duration: int | None, opens_at, closes_at, pass_marks, total) -> None:
    if opens_at and closes_at and closes_at <= opens_at:
        raise _invalid("closes_at", "Must be after the opening time")
    if duration and opens_at and closes_at and (closes_at - opens_at).total_seconds() < duration * 60:
        raise _invalid("closes_at", "The window is shorter than the test duration")
    if pass_marks is not None and total and pass_marks > total:
        raise _invalid("pass_marks", f"Can't be more than the total marks ({total:.2f})")


def create_test(data: dict) -> Test:
    batch = access.manageable_batch(data["batch_id"])
    if batch.state in ("Completed", "Cancelled"):
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    _check_curriculum_links(batch, data.get("module_id"), data.get("topic_id"))
    kind = data["kind"]
    settings = {**KIND_DEFAULTS[kind], **{k: data[k] for k in ("duration_minutes", "attempts_allowed") if k in data}}
    _check_settings(settings["duration_minutes"], data.get("opens_at"), data.get("closes_at"), data.get("pass_marks"), None)
    reviewer_id = data.get("reviewer_user_id") or _default_grader(batch)
    if reviewer_id not in access.eligible_reviewers(batch):
        raise _invalid("reviewer_user_id", "Must be a trainer of this batch or the branch Academic Coordinator")

    fields = {k: data[k] for k in ("module_id", "topic_id", "title", "instructions", "is_required", "ai_use_rule", "opens_at", "closes_at",
                                   "pass_marks") if k in data}
    test = Test(batch_id=batch.batch_id, kind=kind, reviewer_user_id=reviewer_id, created_by=current_user().user_id, **settings, **fields)
    db.session.add(test)
    db.session.flush()
    db.session.refresh(test)
    refresh_release_status(test)
    audit.record("create", "test", test.test_id, new={"code": test.test_code, "kind": kind, "title": test.title}, branch_id=batch.branch_id)
    return test


def _default_grader(batch) -> int:
    user = current_user()
    trainers = access.batch_trainer_ids(batch)
    if user.user_id in trainers:
        return user.user_id
    return trainers[0] if trainers else user.user_id


def _editable(test_id: int) -> Test:
    test = tests_repo.get_test(test_id)
    if test is None:
        raise NotFound("Test not found")
    scope.assert_can_view_batch(test.batch)
    access.assert_can_manage(test.batch)
    return test


def update_test(test_id: int, data: dict) -> Test:
    """Change settings while the test is not released. A released test only takes new instructions and a later closing time
    (by the Academic Coordinator); any change to a formal test asks for approval again."""
    test = _editable(test_id)
    if test.release_status == "Closed":
        raise BusinessRule("A closed test cannot be changed")
    if test.release_status == "Released":
        locked = sorted(set(data) - {"instructions", "closes_at"})
        if locked:
            raise BusinessRule(f"A released test can only change its instructions and closing time (not {', '.join(locked)})")
        if "closes_at" in data:
            if not access.can_moderate_batch(test.batch):
                raise _invalid("closes_at", "Only the Academic Coordinator can change the window of a released test")
            if test.closes_at is not None and data["closes_at"] < test.closes_at:
                raise BusinessRule("The closing time can only be extended after release")

    _check_curriculum_links(test.batch, data.get("module_id"), data.get("topic_id"))
    _check_settings(data.get("duration_minutes", test.duration_minutes), data.get("opens_at", test.opens_at),
                    data.get("closes_at", test.closes_at), data.get("pass_marks", test.pass_marks), float(tests_repo.total_marks(test_id)) or None)
    if "reviewer_user_id" in data and data["reviewer_user_id"] not in access.eligible_reviewers(test.batch):
        raise _invalid("reviewer_user_id", "Must be a trainer of this batch or the branch Academic Coordinator")

    old = {k: getattr(test, k) for k in data}
    for key, value in data.items():
        setattr(test, key, value)
    if test.release_status != "Released" and test.approved_at is not None:
        test.approved_by = test.approved_at = None  # approval covered the settings as they were
    db.session.flush()
    refresh_release_status(test)
    audit.record("update", "test", test_id, old=old, new=data, branch_id=test.batch.branch_id)
    return test


def set_questions(test_id: int, items: list[dict]) -> Test:
    """Replace the test's question set with approved questions of the batch's course, freezing each one as it is now."""
    test = _editable(test_id)
    if test.kind == "Mock interview":
        raise BusinessRule("A mock interview has slots, not questions")
    if test.release_status in ("Released", "Closed") or tests_repo.attempt_count(test_id):
        raise BusinessRule("Questions can't change once the test is released or attempted")

    frozen = []
    for position, item in enumerate(items, 1):
        question = questions_repo.get_question(item["question_id"])
        if question is None or question.course_id != test.batch.course_id or question.branch_id != test.batch.branch_id:
            raise _invalid("questions", f"Question {item['question_id']} is not in this branch's bank for the batch's course")
        if question.status != "Approved":
            raise _invalid("questions", f"{question.question_code} is {question.status}; only approved questions can be used")
        frozen.append(TestQuestion(test_id=test_id, question_id=question.question_id, position=position, question_version=question.version,
                                   question_type=question.question_type, stem=question.stem, options=question.options,
                                   answer_key=question.answer_key, marks=item.get("marks", question.marks)))
    if len({f.question_id for f in frozen}) != len(frozen):
        raise _invalid("questions", "A question can only appear once")

    test.questions.clear()
    db.session.flush()
    test.questions.extend(frozen)
    if test.approved_at is not None:
        test.approved_by = test.approved_at = None
    db.session.flush()
    total = tests_repo.total_marks(test_id)
    if frozen and test.pass_marks is not None and test.pass_marks > total:
        raise _invalid("pass_marks", f"The pass marks ({test.pass_marks:.2f}) are more than the new total ({total:.2f}); lower them first")
    refresh_release_status(test)
    audit.record("set_questions", "test", test_id, new={"questions": [f.question_id for f in frozen], "total_marks": f"{total:.2f}"},
                 branch_id=test.batch.branch_id)
    return test


def approve_test(test_id: int) -> Test:
    """The Academic Coordinator signs off the questions and settings of a formal test."""
    test = tests_repo.get_test(test_id)
    if test is None:
        raise NotFound("Test not found")
    scope.assert_can_view_batch(test.batch)
    access.assert_can_moderate(test.batch)
    if test.release_status != "Configuration Pending" and test.release_status != "Not Released":
        raise BusinessRule(f"A {test.release_status.lower()} test can't be approved")
    if test.approved_at is not None:
        raise BusinessRule("This test is already approved")
    gaps = [g for g in configuration_gaps(test, tests_repo.question_count(test_id), tests_repo.slot_count(test_id))
            if g != "Academic Coordinator approval"]
    if gaps:
        raise BusinessRule(f"Finish the configuration first: {'; '.join(gaps)}")
    test.approved_by, test.approved_at = current_user().user_id, now_utc()
    db.session.flush()
    refresh_release_status(test)
    audit.record("approve", "test", test_id, new={"status": test.release_status}, branch_id=test.batch.branch_id)
    return test


def release_test(test_id: int, data: dict) -> Test:
    """Not Released -> Released. An opening time in the future makes it Scheduled for students."""
    test = _editable(test_id)
    if test.release_status != "Not Released":
        gaps = configuration_gaps(test, tests_repo.question_count(test_id), tests_repo.slot_count(test_id))
        detail = f": {'; '.join(gaps)}" if gaps else ""
        raise BusinessRule(f"A test that is {test.release_status} can't be released{detail}")
    if "opens_at" in data:
        test.opens_at = data["opens_at"]
    now = now_utc()
    if test.closes_at is not None and test.closes_at <= max(now, test.opens_at or now):
        raise BusinessRule("The closing time has passed or is not after the opening time; set a later window first")
    test.release_status, test.released_at = "Released", now
    db.session.flush()
    audit.record("release", "test", test_id, new={"opens_at": test.opens_at, "closes_at": test.closes_at}, branch_id=test.batch.branch_id)
    when = f"opens {test.opens_at.astimezone(IST).strftime('%d %b %Y %H:%M')} IST" if test.opens_at and test.opens_at > now else "is open now"
    notifications.notify(category="Assessments", title="Test released", body=f"{test.title} {when}.", link=f"/tests/{test_id}",
                         event_key=f"test-released:{test_id}", recipient_user_ids=batches_repo.student_user_ids_for_batch(test.batch_id),
                         branch_id=test.batch.branch_id)
    return test


def close_test(test_id: int) -> Test:
    test = _editable(test_id)
    if test.release_status != "Released":
        raise BusinessRule("Only a released test can be closed")
    test.release_status = "Closed"
    db.session.flush()
    audit.record("close", "test", test_id, branch_id=test.batch.branch_id)
    return test

"""Assignments (Module 19): authoring, release, withdrawal, and the student's task list with the state each task is in.

Rules kept here:
  * The due time is exact (IST when shown) with no automatic grace period; a first submission after it is accepted as Late until
    the initial window (7 calendar days) closes.
  * Before the deadline, and before review starts, a student may replace their submission (a new version, same attempt). After the
    deadline or once reviewed, only an instructed resubmission (its own deadline, up to `max_resubmissions`) is accepted.
  * Marks are provisional until the Academic Coordinator publishes the result: students see marks (and review feedback) only then,
    except the feedback that comes with a resubmission request.
"""
from datetime import datetime, timedelta, timezone

from config.database import db
from config.timezone import IST
from models import Assignment, AssignmentSubmission, Batch, Result
from repositories import assignments as assignments_repo
from repositories import batches as batches_repo
from repositories import results as results_repo
from repositories.common import paginate
from services import assessment_scope as access
from services import audit, notifications, scope
from services.context import current_user
from services.errors import BusinessRule, NotFound, ValidationError

DUE_SOON_DAYS = 3        # a task due within this many days is "Due", further away it is "Upcoming"
LATE_WINDOW_DAYS = 7     # calendar days after the due time during which a first submission is still accepted
STUDENT_STATES = ("Upcoming", "Due", "Overdue", "Submitted", "Under Review", "Reviewed", "Resubmission Requested")

# What can still change once an assignment is released (the rest is what students were promised)
RELEASED_EDITABLE = {"title", "brief", "attachments", "due_at", "late_policy", "reviewer_user_id", "closes_at"}
MATERIAL_FIELDS = {"brief", "attachments", "due_at", "closes_at"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- student state

def task_state(assignment: Assignment, versions: list[AssignmentSubmission], result: Result | None, now: datetime) -> str:
    """The one word a student sees for a task."""
    if versions:
        latest = versions[-1]
        review = latest.review
        if review is not None and review.outcome == "Resubmission Requested":
            return "Resubmission Requested"
        if review is not None:
            return "Reviewed" if result is not None and result.status == "Published" else "Under Review"
        return "Under Review" if latest.review_started_at is not None else "Submitted"
    if now > assignment.due_at:
        return "Overdue"
    return "Due" if assignment.due_at - now <= timedelta(days=DUE_SOON_DAYS) else "Upcoming"


def submission_window(assignment: Assignment, versions: list[AssignmentSubmission], now: datetime) -> dict:
    """Can the student submit right now, and as what? mode: initial | replacement | resubmission."""
    def closed(reason: str) -> dict:
        return {"allowed": False, "mode": None, "reason": reason, "deadline": None}

    if assignment.status != "Released" or assignment.release_at > now:
        return closed("This assignment is not open for submission")
    if not versions:
        if now > assignment.closes_at:
            return closed("The submission window has closed. Ask your Academic Coordinator to reopen it")
        return {"allowed": True, "mode": "initial", "reason": None, "deadline": assignment.due_at}

    latest = versions[-1]
    review = latest.review
    if review is None:
        if now <= assignment.due_at:
            return {"allowed": True, "mode": "replacement", "reason": None, "deadline": assignment.due_at}
        return closed("After the deadline, replacing your work needs a resubmission request from your trainer")
    if review.outcome == "Reviewed":
        return closed("Your work has been reviewed")
    if latest.attempt_no - 1 >= assignment.max_resubmissions:
        return closed("You have used every resubmission allowed for this assignment")
    if now > review.resubmission_due_at:
        return closed("The resubmission deadline has passed. Ask your trainer or Academic Coordinator")
    return {"allowed": True, "mode": "resubmission", "reason": None, "deadline": review.resubmission_due_at}


def student_submission(submission: AssignmentSubmission, result: Result | None) -> dict:
    """A version as its owner sees it: review marks and feedback only once the result is published, except a resubmission request."""
    published = result is not None and result.status == "Published" and result.submission_id == submission.submission_id
    data = submission.to_dict(with_marks=published, with_review=False)
    review = submission.review
    if review is not None and (review.outcome == "Resubmission Requested" or published):
        data["review"] = review.to_dict(with_marks=published)
    return data


def my_view(assignment: Assignment, enrolment_id: int, versions: list[AssignmentSubmission], result: Result | None, now: datetime) -> dict:
    published = result is not None and result.status == "Published"
    window = submission_window(assignment, versions, now)
    return {
        "enrolment_id": enrolment_id,
        "state": task_state(assignment, versions, result, now),
        "versions": [student_submission(v, result) for v in versions],
        "window": window,
        "is_late": bool(versions) and versions[0].is_late,
        "result": ({"status": "Published", "marks": f"{result.final_marks:.2f}", "max_marks": f"{result.max_marks:.2f}"}
                   if published else {"status": "Pending" if result is not None else None, "marks": None, "max_marks": f"{assignment.max_marks:.2f}"}),
    }


# ---------------------------------------------------------------- reads

def _student_rows(filters: dict, now: datetime) -> list[dict]:
    seats = access.student_enrolments_by_batch()
    assignments = assignments_repo.released_for_batches(set(seats), now)
    versions = assignments_repo.versions_for_enrolments({e.enrolment_id for e in seats.values()}, [a.assignment_id for a in assignments])
    results = {(r.assignment_id, r.enrolment_id): r for r in results_repo.for_enrolments({e.enrolment_id for e in seats.values()})
               if r.assignment_id is not None}
    rows = []
    for assignment in assignments:
        enrolment = seats[assignment.batch_id]
        view = my_view(assignment, enrolment.enrolment_id, versions.get((assignment.assignment_id, enrolment.enrolment_id), []),
                       results.get((assignment.assignment_id, enrolment.enrolment_id)), now)
        if filters.get("batch_id") and assignment.batch_id != filters["batch_id"]:
            continue
        if filters.get("state") and view["state"] != filters["state"]:
            continue
        if filters.get("is_required") is not None and assignment.is_required != filters["is_required"]:
            continue
        rows.append(assignment.to_dict(my=view))
    return rows


def list_assignments(filters: dict, page: int, per_page: int) -> tuple[list[dict], dict]:
    """Students: their released tasks with the state of each (filter `state`). Staff: assignments of the batches they see, with counts."""
    now = now_utc()
    if access.is_student():
        rows = _student_rows(filters, now)
        start = (page - 1) * per_page
        meta = {"page": page, "per_page": per_page, "total": len(rows), "pages": -(-len(rows) // per_page)}
        return rows[start:start + per_page], meta
    if filters.get("batch_id"):
        access.load_batch(filters["batch_id"])
    items, meta = paginate(assignments_repo.list_stmt(filters, access.visible_batch_clause), page, per_page)
    counts = assignments_repo.submission_counts([a.assignment_id for a in items])
    return [a.to_dict(counts=counts[a.assignment_id], can_manage=access.can_manage_batch(a.batch)) for a in items], meta


def load_assignment(assignment_id: int) -> Assignment:
    """The assignment if the user may see it: staff by batch scope, students only released work of a batch they sit in."""
    assignment = assignments_repo.get_assignment(assignment_id)
    if assignment is None:
        raise NotFound("Assignment not found")
    if access.is_student():
        access.student_seat(assignment.batch_id)
        if assignment.status != "Released" or assignment.release_at > now_utc():
            raise NotFound("Assignment not found")
    else:
        scope.assert_can_view_batch(assignment.batch)
    return assignment


def get_assignment(assignment_id: int) -> dict:
    assignment = load_assignment(assignment_id)
    now = now_utc()
    if access.is_student():
        enrolment = access.student_seat(assignment.batch_id)
        result = results_repo.for_assignment(assignment_id, enrolment.enrolment_id)
        return assignment.to_dict(my=my_view(assignment, enrolment.enrolment_id, assignments_repo.versions_of(assignment_id, enrolment.enrolment_id), result, now))
    counts = assignments_repo.submission_counts([assignment_id])[assignment_id]
    return assignment.to_dict(counts=counts, can_manage=access.can_manage_batch(assignment.batch))


# ---------------------------------------------------------------- authoring

def _default_reviewer(batch: Batch) -> int:
    user = current_user()
    trainers = access.batch_trainer_ids(batch)
    if user.user_id in trainers:
        return user.user_id
    return trainers[0] if trainers else user.user_id


def _check_reviewer(batch: Batch, reviewer_user_id: int) -> None:
    if reviewer_user_id not in access.eligible_reviewers(batch):
        raise ValidationError("Invalid request data", {"reviewer_user_id": ["Must be a trainer of this batch or the branch Academic Coordinator"]})


def create_assignment(data: dict) -> Assignment:
    batch = access.manageable_batch(data["batch_id"])
    if batch.state in ("Completed", "Cancelled"):
        raise BusinessRule(f"Batch {batch.batch_code} is {batch.state}")
    now = now_utc()
    release_at = data.get("release_at") or now
    if data["due_at"] <= release_at:
        raise ValidationError("Invalid request data", {"due_at": ["Must be after the release time"]})
    closes_at = data.get("closes_at") or data["due_at"] + timedelta(days=LATE_WINDOW_DAYS)
    if closes_at < data["due_at"]:
        raise ValidationError("Invalid request data", {"closes_at": ["Can't be before the due time"]})
    reviewer_id = data.get("reviewer_user_id") or _default_reviewer(batch)
    _check_reviewer(batch, reviewer_id)

    fields = {k: data[k] for k in ("topic_id", "title", "kind", "brief", "attachments", "is_required", "max_marks", "max_resubmissions",
                                   "late_policy", "ai_use_rule") if k in data}
    assignment = Assignment(batch_id=batch.batch_id, release_at=release_at, due_at=data["due_at"], closes_at=closes_at,
                            reviewer_user_id=reviewer_id, created_by=current_user().user_id, **fields)
    db.session.add(assignment)
    db.session.flush()
    db.session.refresh(assignment)
    audit.record("create", "assignment", assignment.assignment_id, new=assignment.to_dict(), branch_id=batch.branch_id)
    if data.get("release_now"):
        release_assignment(assignment.assignment_id, {})
    return assignment


def update_assignment(assignment_id: int, data: dict) -> Assignment:
    assignment = assignments_repo.get_assignment(assignment_id)
    if assignment is None:
        raise NotFound("Assignment not found")
    scope.assert_can_view_batch(assignment.batch)
    access.assert_can_manage(assignment.batch)
    if assignment.status == "Withdrawn":
        raise BusinessRule("A withdrawn assignment cannot be changed")
    if assignment.status == "Released":
        locked = sorted(set(data) - RELEASED_EDITABLE - {"reason"})
        if locked:
            raise BusinessRule(f"After release only the brief, attachments, due time, late policy and reviewer can change (not {', '.join(locked)})")
    reason = data.pop("reason", None)
    if "closes_at" in data and not access.can_moderate_batch(assignment.batch):
        raise ValidationError("Invalid request data", {"closes_at": ["Only the Academic Coordinator can reopen the submission window"]})
    if "closes_at" in data and not reason:
        raise ValidationError("Invalid request data", {"reason": ["Give the reason for changing the submission window"]})
    if "reviewer_user_id" in data:
        _check_reviewer(assignment.batch, data["reviewer_user_id"])

    due_at = data.get("due_at", assignment.due_at)
    release_at = data.get("release_at", assignment.release_at)
    if assignment.status == "Released" and due_at < assignment.due_at:
        raise BusinessRule("A due time can only be extended after release")
    if due_at <= release_at:
        raise ValidationError("Invalid request data", {"due_at": ["Must be after the release time"]})
    if "due_at" in data and "closes_at" not in data and assignment.closes_at < due_at:
        data["closes_at"] = due_at + timedelta(days=LATE_WINDOW_DAYS)

    old = assignment.to_dict()
    for key, value in data.items():
        setattr(assignment, key, value)
    db.session.flush()
    material = assignment.status == "Released" and bool(MATERIAL_FIELDS & set(data))
    audit.record("update", "assignment", assignment_id, old=old, new=assignment.to_dict(), reason=reason, branch_id=assignment.batch.branch_id)
    if material:
        _notify_students(assignment, "Assignment updated", f"{assignment.title} was changed. Check the brief and due time.",
                         f"assignment-updated:{assignment_id}:{int(now_utc().timestamp())}")
    return assignment


def release_assignment(assignment_id: int, data: dict) -> Assignment:
    """Draft -> Released. Students of the batch see it from `release_at` (now unless a later time is given)."""
    assignment = assignments_repo.get_assignment(assignment_id)
    if assignment is None:
        raise NotFound("Assignment not found")
    scope.assert_can_view_batch(assignment.batch)
    access.assert_can_manage(assignment.batch)
    if assignment.status != "Draft":
        raise BusinessRule(f"Only a draft can be released (this one is {assignment.status})")
    now = now_utc()
    release_at = data.get("release_at") or now
    if assignment.due_at <= max(release_at, now):
        raise BusinessRule("The due time has passed or is not after the release time; set a later due time first")
    assignment.release_at = release_at
    assignment.status = "Released"
    assignment.released_by = current_user().user_id
    db.session.flush()
    audit.record("release", "assignment", assignment_id, new={"release_at": release_at, "due_at": assignment.due_at},
                 branch_id=assignment.batch.branch_id)
    _notify_students(assignment, "New assignment", f"{assignment.title} is due {assignment.due_at.astimezone(IST).strftime('%d %b %Y %H:%M')} IST.",
                     f"assignment-released:{assignment_id}", action_required=True)
    return assignment


def withdraw_assignment(assignment_id: int, reason: str) -> Assignment:
    """Withdraw an assignment; versions, reviews and results already recorded are kept."""
    assignment = assignments_repo.get_assignment(assignment_id)
    if assignment is None:
        raise NotFound("Assignment not found")
    scope.assert_can_view_batch(assignment.batch)
    access.assert_can_manage(assignment.batch)
    if assignment.status == "Withdrawn":
        raise BusinessRule("This assignment is already withdrawn")
    was_released = assignment.status == "Released"
    assignment.status = "Withdrawn"
    assignment.withdrawn_reason = reason
    db.session.flush()
    audit.record("withdraw", "assignment", assignment_id, reason=reason, branch_id=assignment.batch.branch_id)
    if was_released:
        _notify_students(assignment, "Assignment withdrawn", f"{assignment.title} was withdrawn: {reason}", f"assignment-withdrawn:{assignment_id}")
    return assignment


def _notify_students(assignment: Assignment, title: str, body: str, event_key: str, *, action_required: bool = False) -> None:
    notifications.notify(category="Assignments", title=title, body=body, link=f"/assignments/{assignment.assignment_id}",
                         event_key=event_key, recipient_user_ids=batches_repo.student_user_ids_for_batch(assignment.batch_id),
                         branch_id=assignment.batch.branch_id, action_required=action_required)



def curriculum_options(batch_id: int) -> list[dict]:
    """Modules and topics an assignment or test of this batch can be linked to (staff)."""
    batch = access.load_batch(batch_id)
    return [{"module_id": m.module_id, "title": m.title, "version_label": m.version.version_label,
             "topics": [{"topic_id": t.topic_id, "title": t.title} for t in m.topics]}
            for m in assignments_repo.active_modules(batch.course_id)]

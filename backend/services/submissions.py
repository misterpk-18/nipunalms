"""Submissions and trainer reviews (Module 19 §6-§8).

A submission is a new version (v1, v2 ...) that is never edited. The student gets a submission code as receipt. A trainer reviews
the newest version: feedback + marks (provisional until the Academic Coordinator publishes), or a resubmission request with its
own deadline. Files are stored on disk under UPLOAD_DIR and are only ever served back to their owner and the batch's staff.
"""
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from config.database import db
from models import AssignmentSubmission, SubmissionReview
from repositories import assignments as assignments_repo
from repositories import results as results_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import assessment_scope as access
from services import assignments as assignments_service
from services import notifications, results, scope
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "md", "csv", "xlsx", "ipynb", "py", "sql", "java", "zip", "png", "jpg", "jpeg"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # the API's request limit (MAX_CONTENT_LENGTH); Module 19's 50 MB needs production storage


def _store_file(upload: FileStorage, assignment_id: int) -> dict:
    """Save an uploaded file (never executed) under UPLOAD_DIR/submissions/<assignment>/ with a random prefix."""
    name = secure_filename(upload.filename or "")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("File type not allowed", {"file": [f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"]})
    content = upload.read()
    if not content:
        raise ValidationError("The file is empty", {"file": ["Empty file"]})
    if len(content) > MAX_FILE_BYTES:
        raise ValidationError("The file is too large", {"file": [f"At most {MAX_FILE_BYTES // (1024 * 1024)} MB"]})
    relative = Path("submissions") / str(assignment_id) / f"{secrets.token_hex(8)}-{name}"
    target = Path(current_app.config["UPLOAD_DIR"]) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {"file_path": str(relative), "original_filename": upload.filename, "mime_type": upload.mimetype, "file_size_bytes": len(content)}


def submit(assignment_id: int, data: dict, upload: FileStorage | None) -> AssignmentSubmission:
    """A student submits a new version: text, a link, a file, or a mix. The window rules decide whether it is accepted, and as what."""
    if not access.is_student():
        raise Forbidden("Only students submit assignments")
    assignment = assignments_service.load_assignment(assignment_id)
    enrolment = access.student_seat(assignment.batch_id)
    versions = assignments_repo.versions_of(assignment_id, enrolment.enrolment_id)
    now = datetime.now(timezone.utc)
    window = assignments_service.submission_window(assignment, versions, now)
    if not window["allowed"]:
        raise BusinessRule(window["reason"])
    if not (data.get("body_text") or data.get("link_url") or upload):
        raise ValidationError("Invalid request data", {"body_text": ["Add your notes, a link or a file"]})

    file_fields = _store_file(upload, assignment_id) if upload else {}
    mode = window["mode"]
    attempt_no = 1 if not versions else versions[-1].attempt_no + (1 if mode == "resubmission" else 0)
    submission = AssignmentSubmission(
        assignment_id=assignment_id, enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id,
        version_no=len(versions) + 1, attempt_no=attempt_no, submitted_at=now, is_late=mode == "initial" and now > assignment.due_at,
        **{k: data[k] for k in ("body_text", "link_url", "ai_disclosure") if data.get(k)}, **file_fields,
    )
    db.session.add(submission)
    db.session.flush()
    db.session.refresh(submission)
    notifications.notify(
        category="Reviews", title="Submission awaiting review",
        body=f"{submission.student.full_name} submitted {assignment.title} (v{submission.version_no}).",
        link="/trainer/reviews", event_key=f"submission:{submission.submission_id}", recipient_user_ids=[assignment.reviewer_user_id],
        branch_id=assignment.batch.branch_id, action_required=True,
    )
    return submission


# ---------------------------------------------------------------- reads

def list_submissions(filters: dict, page: int, per_page: int) -> tuple[list[AssignmentSubmission], dict]:
    """Staff: the newest version per student, for the batches they see (review queue: status=Awaiting Review&reviewer_id=me)."""
    if filters.pop("reviewer_me", False):
        filters["reviewer_id"] = current_user().user_id
    if filters.get("batch_id"):
        access.load_batch(filters["batch_id"])
    if filters.get("assignment_id"):
        assignments_service.load_assignment(filters["assignment_id"])
    return paginate(assignments_repo.latest_submissions_stmt(filters, access.visible_batch_clause), page, per_page)


def load_submission(submission_id: int) -> AssignmentSubmission:
    """Staff by batch scope; a student only their own versions."""
    submission = assignments_repo.get_submission(submission_id)
    if submission is None:
        raise NotFound("Submission not found")
    if access.is_student():
        if submission.student_id != current_user().student_id:
            raise NotFound("Submission not found")
    else:
        scope.assert_can_view_batch(submission.assignment.batch)
    return submission


def submission_detail(submission_id: int) -> dict:
    """One version with the student's other versions (staff: full reviews; the student: reviews as published)."""
    submission = load_submission(submission_id)
    versions = assignments_repo.versions_of(submission.assignment_id, submission.enrolment_id)
    if access.is_student():
        result = results_repo.for_assignment(submission.assignment_id, submission.enrolment_id)
        return {**assignments_service.student_submission(submission, result),
                "versions": [assignments_service.student_submission(v, result) for v in versions]}
    return {**submission.to_dict(), "assignment": submission.assignment.to_dict(), "versions": [v.to_dict() for v in versions]}


def file_location(submission_id: int) -> tuple[Path, str, str | None]:
    """Where a submission's file is on disk (path, download name, mime type), after the scope check."""
    submission = load_submission(submission_id)
    if not submission.file_path:
        raise NotFound("This version has no file")
    path = Path(current_app.config["UPLOAD_DIR"]) / submission.file_path
    if not path.is_file():
        raise NotFound("The file is no longer available")
    return path, submission.original_filename or path.name, submission.mime_type


# ---------------------------------------------------------------- review

def _reviewable(submission_id: int) -> AssignmentSubmission:
    submission = assignments_repo.get_submission(submission_id)
    if submission is None:
        raise NotFound("Submission not found")
    scope.assert_can_view_batch(submission.assignment.batch)
    access.assert_can_manage(submission.assignment.batch)
    latest = assignments_repo.versions_of(submission.assignment_id, submission.enrolment_id)[-1]
    if latest.submission_id != submission.submission_id:
        raise BusinessRule(f"Only the newest version (v{latest.version_no}) can be reviewed")
    return submission


def start_review(submission_id: int) -> AssignmentSubmission:
    """Mark the version Under Review (the trainer opened it); safe to call again."""
    submission = _reviewable(submission_id)
    if submission.review is None and submission.review_started_at is None:
        submission.review_started_at = datetime.now(timezone.utc)
        submission.review_started_by = current_user().user_id
        db.session.flush()
    return submission


def review(submission_id: int, data: dict) -> SubmissionReview:
    """Record feedback and provisional marks, or ask for a resubmission. Marks reach the student only once published."""
    submission = _reviewable(submission_id)
    if submission.review is not None:
        raise Conflict("This version has already been reviewed")
    assignment = submission.assignment
    now = datetime.now(timezone.utc)
    outcome = data["outcome"]

    if outcome == "Reviewed":
        marks = data.get("marks")
        if marks is None:
            raise ValidationError("Invalid request data", {"marks": ["Required when the work is reviewed"]})
        if marks > assignment.max_marks:
            raise ValidationError("Invalid request data", {"marks": [f"Must be {assignment.max_marks:.2f} or less"]})
        due = None
    else:
        marks = None
        due = data.get("resubmission_due_at")
        if due is None or due <= now:
            raise ValidationError("Invalid request data", {"resubmission_due_at": ["Give a future deadline for the corrected work"]})
        if submission.attempt_no - 1 >= assignment.max_resubmissions:
            raise BusinessRule("The student has used every resubmission allowed; the Academic Coordinator can approve an extra attempt")

    review_row = SubmissionReview(submission_id=submission_id, reviewer_user_id=current_user().user_id, outcome=outcome,
                                  feedback=data["feedback"], marks=marks, resubmission_due_at=due)
    db.session.add(review_row)
    if submission.review_started_at is None:
        submission.review_started_at = now
        submission.review_started_by = current_user().user_id
    db.session.flush()
    db.session.refresh(submission)

    if outcome == "Reviewed":
        results.upsert_provisional(enrolment=submission.enrolment, batch_id=assignment.batch_id, max_marks=assignment.max_marks,
                                   marks=Decimal(marks), assignment_id=assignment.assignment_id, submission_id=submission_id)
    else:
        student_user = users_repo.get_by_student_id(submission.student_id)
        if student_user:
            notifications.notify(category="Assignments", title="Resubmission requested",
                                 body=f"Your trainer asked you to resubmit {assignment.title}: {data['feedback']}",
                                 link=f"/assignments/{assignment.assignment_id}", event_key=f"resubmission:{submission_id}",
                                 recipient_user_ids=[student_user.user_id], branch_id=assignment.batch.branch_id, action_required=True)
    return review_row

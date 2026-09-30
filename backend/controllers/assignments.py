"""Assignments, submissions and reviews."""
from flask import request, send_file

from controllers.common import Validator, created, get_page_params, json_body, ok, paginated, require_changes
from models.assessments import AI_USE_RULES, ASSIGNMENT_KINDS, ASSIGNMENT_STATUSES, REVIEW_OUTCOMES
from services import assignments as assignments_service
from services import submissions as submissions_service
from services.assignments import STUDENT_STATES


def _attachment(v: Validator) -> None:
    v.string("name", required=True, max_length=150)
    v.string("url", required=True, max_length=500, pattern=r"https?://\S+", pattern_message="Must be an http(s) link")


def _fields(v: Validator, *, creating: bool) -> None:
    v.integer("topic_id", nullable=True, min_value=1)
    v.string("title", required=creating, max_length=200)
    v.choice("kind", ASSIGNMENT_KINDS)
    v.string("brief", required=creating, max_length=10000)
    v.list_of("attachments", _attachment)
    v.boolean("is_required")
    v.decimal("max_marks", required=creating, min_value=1, max_value=1000)
    v.datetime("release_at")
    v.datetime("due_at", required=creating)
    v.datetime("closes_at")
    v.integer("max_resubmissions", min_value=0, max_value=5)
    v.string("late_policy", max_length=1000)
    v.choice("ai_use_rule", AI_USE_RULES)
    v.integer("reviewer_user_id", min_value=1)


def list_assignments():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    v.choice("state", STUDENT_STATES)
    v.choice("status", ASSIGNMENT_STATUSES)
    v.integer("reviewer_id", min_value=1)
    v.boolean("is_required")
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = assignments_service.list_assignments(filters, page, per_page)
    return paginated(rows, meta)


def get_assignment(assignment_id: int):
    return ok(assignments_service.get_assignment(assignment_id))


def create_assignment():
    v = Validator(json_body())
    v.integer("batch_id", required=True, min_value=1)
    _fields(v, creating=True)
    v.boolean("release_now", default=False)
    assignment = assignments_service.create_assignment(v.validate())
    return created(assignments_service.get_assignment(assignment.assignment_id))


def update_assignment(assignment_id: int):
    v = Validator(json_body())
    _fields(v, creating=False)
    v.string("reason", max_length=500)
    assignment = assignments_service.update_assignment(assignment_id, require_changes(v.validate()))
    return ok(assignments_service.get_assignment(assignment.assignment_id))


def release_assignment(assignment_id: int):
    v = Validator(json_body())
    v.datetime("release_at")
    assignment = assignments_service.release_assignment(assignment_id, v.validate())
    return ok(assignments_service.get_assignment(assignment.assignment_id))


def withdraw_assignment(assignment_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    assignment = assignments_service.withdraw_assignment(assignment_id, v.validate()["reason"])
    return ok(assignments_service.get_assignment(assignment.assignment_id))


# ---------------------------------------------------------------- submissions

def submit_assignment(assignment_id: int):
    """JSON {body_text, link_url, ai_disclosure} or multipart with the same fields plus `file`."""
    source = request.form.to_dict() if request.files else json_body()
    v = Validator(source)
    v.string("body_text", max_length=20000)
    v.string("link_url", max_length=500, pattern=r"https?://\S+", pattern_message="Must be an http(s) link")
    v.string("ai_disclosure", max_length=2000)
    submission = submissions_service.submit(assignment_id, v.validate(), request.files.get("file"))
    return created(submissions_service.submission_detail(submission.submission_id))


def list_submissions():
    v = Validator(request.args.to_dict())
    v.integer("assignment_id", min_value=1)
    v.integer("batch_id", min_value=1)
    v.integer("reviewer_id", min_value=1)
    v.boolean("reviewer_me")
    v.choice("status", ("Awaiting Review", *REVIEW_OUTCOMES))
    filters = v.validate()
    page, per_page = get_page_params()
    rows, meta = submissions_service.list_submissions(filters, page, per_page)
    return paginated([s.to_dict() | {"assignment": s.assignment.to_dict()} for s in rows], meta)


def get_submission(submission_id: int):
    return ok(submissions_service.submission_detail(submission_id))


def download_submission(submission_id: int):
    path, name, mime = submissions_service.file_location(submission_id)
    return send_file(path, as_attachment=True, download_name=name, mimetype=mime)


def start_review(submission_id: int):
    submission = submissions_service.start_review(submission_id)
    return ok(submissions_service.submission_detail(submission.submission_id))


def review_submission(submission_id: int):
    v = Validator(json_body())
    v.choice("outcome", REVIEW_OUTCOMES, required=True)
    v.string("feedback", required=True, max_length=5000)
    v.decimal("marks", min_value=0)
    v.datetime("resubmission_due_at")
    review = submissions_service.review(submission_id, v.validate())
    return created(submissions_service.submission_detail(review.submission_id))


def curriculum_options():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", required=True, min_value=1)
    return ok(assignments_service.curriculum_options(v.validate()["batch_id"]))

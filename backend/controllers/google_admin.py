from flask import request

from controllers.common import Validator, json_body, ok, require_changes
from services import google_admin as google_admin_service
from services.google_admin import EMAIL_STATES

JOB_STATES = ("Queued", "Running", "Failed", "Succeeded", "Dead")


def overview():
    return ok(google_admin_service.overview())


def list_jobs():
    v = Validator(request.args.to_dict())
    v.choice("state", JOB_STATES)
    v.integer("limit", min_value=1, max_value=200, default=100)
    args = v.validate()
    return ok(google_admin_service.list_jobs(args.get("state"), args["limit"]))


def retry_job(job_id: int):
    return ok(google_admin_service.retry_job(job_id))


def list_emails():
    v = Validator(request.args.to_dict())
    v.choice("status", EMAIL_STATES)
    v.integer("limit", min_value=1, max_value=200, default=50)
    args = v.validate()
    return ok(google_admin_service.list_emails(args.get("status"), args["limit"]))


def list_branches():
    return ok(google_admin_service.branch_configs())


def update_branch(branch_id: int):
    v = Validator(json_body())
    v.email("calendar_mailbox", nullable=True)
    v.email("gmail_sender", nullable=True)
    v.string("drive_root_folder_id", nullable=True, max_length=200)
    return ok(google_admin_service.update_branch_config(branch_id, require_changes(v.validate())))

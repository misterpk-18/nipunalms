from datetime import datetime, timezone

from flask import request

from controllers.common import Validator, get_page_params, json_body, ok, paginated
from models.enums import ACTIVATION_CHANNELS, ACTIVATION_STATUSES
from services import admin_students as students_service


def _row(account: students_service.StudentAccount) -> dict:
    """The Student Accounts row: identity, activation status, LMS login and an enrolment summary."""
    student, user = account.student, account.user
    return {
        **student.to_summary(),
        "name_te": student.name_te,
        "email": student.email,
        "lms_user_id": student.lms_user_id,
        "activation_status": student.activation_status,
        "service_branch": student.service_branch.to_summary(),
        "provisioned_at": student.provisioned_at,
        "user_id": user.user_id if user else None,
        "has_password": bool(user and user.password_hash),
        "is_login_active": bool(user and user.is_active),
        "last_login_at": user.last_login_at if user else None,
        "active_sessions": account.active_sessions,
        "enrolment_counts": account.enrolment_counts,
        "enrolment_total": sum(account.enrolment_counts.values()),
    }


def search():
    v = Validator(request.args.to_dict())
    v.string("q", max_length=100)
    v.choice("activation_status", ACTIVATION_STATUSES)
    v.choice("activation_channel", ACTIVATION_CHANNELS)
    v.integer("branch_id", min_value=1)
    filters = v.validate()

    page, per_page = get_page_params()
    accounts, meta = students_service.search(filters, page, per_page)
    return paginated([_row(a) for a in accounts], meta)


def get_student(student_id: int):
    detail = students_service.detail(student_id)
    activation = detail["activation"]
    suspension = detail["suspension"]
    return ok({
        **_row(detail["account"]),
        "enrolments": [
            {
                "enrolment_id": e.enrolment_id,
                "enrolment_code": e.enrolment_code,
                "course_code": c.course_code,
                "course_title": c.title,
                "kind": e.kind,
                "status": e.status,
                "service_branch_id": e.service_branch_id,
                "joining_date": e.joining_date,
            }
            for e, c in detail["enrolments"]
        ],
        "activation": {"status": activation.status(datetime.now(timezone.utc)), "expires_at": activation.expires_at, "issued_at": activation.created_at,
                       "channel": activation.channel} if activation else None,
        "suspension": {"suspended_at": suspension.occurred_at, "reason": suspension.reason} if suspension else None,
        "audit": [a.to_dict() for a in detail["audit"]],
    })


def suspend(student_id: int):
    v = Validator(json_body())
    v.string("reason", required=True, max_length=500)
    return ok(_row(students_service.suspend(student_id, v.validate()["reason"])))


def reactivate(student_id: int):
    v = Validator(json_body())
    v.string("reason", nullable=True, max_length=500)
    return ok(_row(students_service.reactivate(student_id, v.validate().get("reason"))))


def revoke_sessions(student_id: int):
    v = Validator(json_body())
    v.string("reason", nullable=True, max_length=500)
    return ok({"sessions_ended": students_service.revoke_sessions(student_id, v.validate().get("reason"))})

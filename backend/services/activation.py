"""Student activation: single-use, expiring tokens; the student sets their own password.

Tokens are issued when the LMS login is created from a CRM admission, and by staff (supervised activation).
Only the SHA-256 of a token is stored, so a raw token is shown exactly once, to whoever issued it.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.database import db
from models import Student, StudentActivation, UserRoleScope
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import audit
from services.auth import check_password_policy
from services.context import BRANCH_ROLES, current_user
from services.errors import BusinessRule, NotFound
from services.security import hash_password, hash_token, new_activation_token


@dataclass
class IssuedActivation:
    token: str  # raw; never stored
    activation: StudentActivation


def issue(student: Student, *, channel: str, issued_by: int | None) -> IssuedActivation:
    """Replace any outstanding token with a new one. The student moves to Activation Pending."""
    if student.activation_status == "Activated":
        raise BusinessRule("This student is already activated")
    if student.activation_status == "Suspended":
        raise BusinessRule("This student's account is suspended")

    now = datetime.now(timezone.utc)
    students_repo.revoke_outstanding_activation(student.student_id, now)

    token = new_activation_token()
    hours = settings_repo.get_int("activation_token_hours", 72)
    activation = StudentActivation(
        student_id=student.student_id,
        token_hash=hash_token(token),
        channel=channel,
        issued_by=issued_by,
        expires_at=now + timedelta(hours=hours),
    )
    db.session.add(activation)
    student.activation_status = "Activation Pending"
    db.session.flush()
    return IssuedActivation(token=token, activation=activation)


def issue_as_staff(student_id: int) -> IssuedActivation:
    """POST /students/{id}/activation: Super Admin, or Branch Manager / Academic Coordinator at the student's service branch."""
    actor = current_user()
    student = students_repo.get_student(student_id)
    if student is None:
        raise NotFound("Student not found")
    allowed = actor.has_role("SUPER_ADMIN") or actor.has_role(*BRANCH_ROLES, branch_id=student.service_branch_id)
    if not allowed:
        raise NotFound("Student not found")  # outside scope: same answer as a missing record

    reissued = students_repo.outstanding_activation(student.student_id) is not None
    issued = issue(student, channel="Staff issued", issued_by=actor.user_id)
    audit.record("ACTIVATION_REISSUED" if reissued else "ACTIVATION_ISSUED", "student", student.student_id,
                 new={"student_code": student.student_code, "expires_at": issued.activation.expires_at},
                 branch_id=student.service_branch_id)
    return issued


def describe(token: str) -> tuple[StudentActivation, str]:
    """Token status (valid / expired / used / revoked) and the masked Student ID."""
    activation = students_repo.find_activation(hash_token(token))
    if activation is None:
        raise NotFound("Activation link not found")
    return activation, activation.status(datetime.now(timezone.utc))


def mask_student_code(student_code: str) -> str:
    """NIT-STU-2026-004182 -> NIT-STU-2026-••••82"""
    head, tail = student_code[:-6], student_code[-6:]
    return f"{head}••••{tail[-2:]}"


def activate(token: str, password: str) -> Student:
    activation, status = describe(token)
    if status != "valid":
        raise BusinessRule(f"This activation link is {status}. Ask your coordinator for a new one.", {"status": status})
    check_password_policy(password, field="password")

    student = activation.student
    user = users_repo.get_by_student_id(student.student_id)
    if user is None:
        raise BusinessRule("This student has no LMS login yet. Contact your coordinator.")

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.password_changed_at = now
    user.is_active = True
    activation.used_at = now
    student.activation_status = "Activated"

    student_role = users_repo.get_role_by_code("STUDENT")
    if users_repo.find_unrevoked_scope(user.user_id, student_role.role_id, student.service_branch_id) is None:
        db.session.add(UserRoleScope(user_id=user.user_id, role_id=student_role.role_id, branch_id=student.service_branch_id))

    audit.record("ACCOUNT_ACTIVATED", "student", student.student_id, actor_user_id=user.user_id,
                 new={"student_code": student.student_code}, branch_id=student.service_branch_id)
    db.session.flush()
    return student

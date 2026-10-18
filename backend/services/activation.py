"""Activation: single-use, expiring tokens; the person sets their own password and is signed in.

Student tokens are issued when the LMS login is created from a CRM admission, and by staff ("Send new link"). Staff get an
invite token when a Super Admin creates their account or presses "Resend invite". Both go out by WhatsApp (templates 2 and 3)
and the raw token is also shown once to whoever issued it, as the copy-link fallback. Only the SHA-256 of a token is stored.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.database import db
from models import StaffInvite, Student, StudentActivation, User, UserRoleScope, WhatsappMessage
from repositories import settings as settings_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories import staff_invites as invites_repo
from services import audit, whatsapp_messages
from services.auth import LoginResult, check_password_policy, open_session
from services.context import ADMIN_ROLES, BRANCH_ROLES, current_user
from services.errors import BusinessRule, NotFound
from services.security import hash_password, hash_token, new_activation_token


@dataclass
class IssuedActivation:
    token: str  # raw; never stored
    activation: StudentActivation
    message: WhatsappMessage | None = None  # the WhatsApp message queued with the link (None: a repeat)


@dataclass
class IssuedInvite:
    token: str  # raw; never stored
    invite: StaffInvite
    message: WhatsappMessage | None = None


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
    message = whatsapp_messages.student_activation_link(student, token, activation)
    return IssuedActivation(token=token, activation=activation, message=message)


def issue_as_staff(student_id: int) -> IssuedActivation:
    """POST /students/{id}/activation: Super Admin, Founder / CEO, or Branch Manager at the student's service branch."""
    actor = current_user()
    student = students_repo.get_student(student_id)
    if student is None:
        raise NotFound("Student not found")
    allowed = actor.has_role(*ADMIN_ROLES) or actor.has_role(*BRANCH_ROLES, branch_id=student.service_branch_id)
    if not allowed:
        raise NotFound("Student not found")  # outside scope: same answer as a missing record

    reissued = students_repo.outstanding_activation(student.student_id) is not None
    issued = issue(student, channel="Staff issued", issued_by=actor.user_id)
    audit.record("ACTIVATION_REISSUED" if reissued else "ACTIVATION_ISSUED", "student", student.student_id,
                 new={"student_code": student.student_code, "expires_at": issued.activation.expires_at},
                 branch_id=student.service_branch_id)
    return issued


# ---------------------------------------------------------------- staff invites

def issue_invite(user: User, *, issued_by: int | None, role_name: str, branch_name: str) -> IssuedInvite:
    """Replace any outstanding invite with a new one and queue the WhatsApp message."""
    if not user.must_change_password:
        raise BusinessRule("This person has already chosen a password")
    if not user.is_active:
        raise BusinessRule("This account is deactivated")
    now = datetime.now(timezone.utc)
    invites_repo.revoke_outstanding(user.user_id, now)

    token = new_activation_token()
    hours = settings_repo.get_int("activation_token_hours", 72)
    invite = StaffInvite(user_id=user.user_id, token_hash=hash_token(token), issued_by=issued_by, expires_at=now + timedelta(hours=hours))
    db.session.add(invite)
    db.session.flush()
    message = whatsapp_messages.staff_invite(user, token, invite, role_name, branch_name)
    return IssuedInvite(token=token, invite=invite, message=message)


# ---------------------------------------------------------------- checking and using a token

@dataclass
class TokenInfo:
    kind: str  # "student" | "staff"
    status: str  # valid / expired / used / revoked
    full_name: str
    expires_at: datetime
    student_code: str | None = None  # masked
    email: str | None = None  # masked, staff only


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:1]}••••@{domain}"


def _find(token: str) -> tuple[StudentActivation | StaffInvite, str]:
    now = datetime.now(timezone.utc)
    record = students_repo.find_activation(hash_token(token)) or invites_repo.find(hash_token(token))
    if record is None:
        raise NotFound("Activation link not found")
    return record, record.status(now)


def describe(token: str) -> TokenInfo:
    """What the activation page shows: who the link is for and whether it still works. Student IDs and emails are masked."""
    record, status = _find(token)
    if isinstance(record, StudentActivation):
        return TokenInfo("student", status, record.student.full_name, record.expires_at,
                         student_code=mask_student_code(record.student.student_code))
    return TokenInfo("staff", status, record.user.full_name, record.expires_at, email=mask_email(record.user.email))


def mask_student_code(student_code: str) -> str:
    """NIT-STU-2026-004182 -> NIT-STU-2026-••••82"""
    head, tail = student_code[:-6], student_code[-6:]
    return f"{head}••••{tail[-2:]}"


@dataclass
class Activated:
    login: LoginResult
    student: Student | None  # set for a student: the success step shows their Student ID


def activate(token: str, password: str) -> Activated:
    """Set the password, mark the link used and sign the person in."""
    record, status = _find(token)
    if status != "valid":
        raise BusinessRule(f"This activation link is {status}. Ask for a new one.", {"status": status})
    check_password_policy(password, field="password")
    now = datetime.now(timezone.utc)

    if isinstance(record, StaffInvite):
        user = record.user
        if not user.is_active:
            raise BusinessRule("This account is deactivated. Contact a Super Admin.")
        _set_password(user, password, now)
        record.used_at = now
        audit.record("STAFF_INVITE_ACCEPTED", "user", user.user_id, actor_user_id=user.user_id)
        return Activated(open_session(user, now, record_activity=False), None)

    student = record.student
    user = users_repo.get_by_student_id(student.student_id)
    if user is None:
        raise BusinessRule("This student has no LMS login yet. Contact your branch.")
    _set_password(user, password, now)
    user.is_active = True
    record.used_at = now
    student.activation_status = "Activated"

    student_role = users_repo.get_role_by_code("STUDENT")
    if users_repo.find_unrevoked_scope(user.user_id, student_role.role_id, student.service_branch_id) is None:
        db.session.add(UserRoleScope(user_id=user.user_id, role_id=student_role.role_id, branch_id=student.service_branch_id))

    audit.record("ACCOUNT_ACTIVATED", "student", student.student_id, actor_user_id=user.user_id,
                 new={"student_code": student.student_code}, branch_id=student.service_branch_id)
    db.session.flush()
    return Activated(open_session(user, now, record_activity=False), student)


def _set_password(user: User, password: str, now: datetime) -> None:
    user.password_hash = hash_password(password)
    user.must_change_password = False
    user.password_changed_at = now

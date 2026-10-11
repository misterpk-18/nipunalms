"""A student adds or changes their email address (UX phase U11), confirmed with a code.

The email is what the student signs in with besides the Student ID and where a password reset is addressed, so a typo must not
take it over: the new address only replaces the old one after the student types the code. The LMS has no email sender, so the
code goes by WhatsApp to the mobile number the CRM holds (template 1, a generic "verification code" message), through the same
outbox and switch as every other message. When WhatsApp is switched off the answer says so (the email is not changed without the
code, so nothing can lock the student out). Only the code's hash is stored (it also covers the address, so a code cannot confirm a different one);
a code is single use, lasts 10 minutes, is burned after 5 wrong tries, and a person gets at most 5 codes an hour (like password_reset).
"""
import secrets
from datetime import datetime, timedelta, timezone

from config.database import db
from models import EmailChangeCode, Student, User
from repositories import email_change as email_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import audit, whatsapp_messages
from services.context import current_user
from services.errors import Forbidden, NotFound, TooManyAttempts, ValidationError
from services.security import hash_token

CODE_MINUTES = whatsapp_messages.RESET_CODE_MINUTES
MAX_CODES_PER_HOUR = 5
MAX_WRONG_TRIES = 5
BAD_CODE = "That code is wrong or has expired. Ask for a new one."
UNUSABLE = "That email address can't be used. Try a different one."


def _hash(user_id: int, email: str, code: str) -> str:
    return hash_token(f"{user_id}:{email}:{code}")


def new_code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def _me() -> tuple[User, Student]:
    current = current_user()
    if current.student_id is None:
        raise Forbidden("Only students change their email here")
    user = users_repo.get_by_id(current.user_id)
    student = students_repo.get_student(current.student_id)
    if user is None or student is None:
        raise NotFound("Student not found")
    return user, student


def request_code(email: str) -> dict:
    """Send a code to the student's WhatsApp number for the new address. Says whether a message will go out."""
    user, student = _me()
    email = email.strip().lower()
    if student.email and student.email.lower() == email:
        raise ValidationError("That is already your email address", {"email": ["That is already your email address"]})
    if users_repo.email_taken(email, exclude_user_id=user.user_id):
        raise ValidationError(UNUSABLE, {"email": [UNUSABLE]})
    now = datetime.now(timezone.utc)
    if email_repo.count_since(user.user_id, now - timedelta(hours=1)) >= MAX_CODES_PER_HOUR:
        raise TooManyAttempts("Too many codes requested. Try again in an hour.")

    code = new_code()
    row = EmailChangeCode(user_id=user.user_id, new_email=email, code_hash=_hash(user.user_id, email, code),
                          expires_at=now + timedelta(minutes=CODE_MINUTES))
    db.session.add(row)
    db.session.flush()
    message = whatsapp_messages.email_change_code(user, student, code, row.code_id)
    sent = bool(message and message.status == "Queued")
    audit.record("EMAIL_CHANGE_CODE_REQUESTED", "user", user.user_id, actor_user_id=user.user_id, new={"sent": sent},
                 branch_id=student.service_branch_id)
    return {"sent": sent, "channel": "WhatsApp", "expires_in_minutes": CODE_MINUTES,
            "reason": None if sent else (message.status_note if message else "This message was already queued")}


def confirm(code: str) -> Student:
    """Check the code and make the address the student's email (profile and sign-in)."""
    user, student = _me()
    now = datetime.now(timezone.utc)
    row = email_repo.latest_open(user.user_id, now)
    if row is None:
        raise ValidationError(BAD_CODE, {"code": [BAD_CODE]})
    if not secrets.compare_digest(row.code_hash, _hash(user.user_id, row.new_email, code.strip())):
        row.wrong_attempts += 1
        if row.wrong_attempts >= MAX_WRONG_TRIES:
            row.used_at = now  # burned: ask for a new code
        db.session.commit()  # the 422 response would otherwise roll the count back
        raise ValidationError(BAD_CODE, {"code": [BAD_CODE]})
    if users_repo.email_taken(row.new_email, exclude_user_id=user.user_id):
        raise ValidationError(UNUSABLE, {"email": [UNUSABLE]})

    old = student.email
    row.used_at = now
    student.email = user.email = row.new_email
    db.session.flush()
    audit.record("STUDENT_EMAIL_CHANGED", "student", student.student_code, actor_user_id=user.user_id,
                 old={"email": old}, new={"email": row.new_email}, branch_id=student.service_branch_id)
    return student

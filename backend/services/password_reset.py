"""Self-service password reset (UX phase U7): the person asks for a code on the sign-in page and sets a new password with it.

The code goes by WhatsApp (template 1) to the number on file. An email fallback is not built yet: the LMS has no email sender.
The answer to a request is always the same, so the page never shows whether an account exists. Only the code's hash is
stored; a code is single use, lasts 10 minutes, is burned after 5 wrong tries, and a person gets at most 5 codes an hour.
"""
import secrets
from datetime import datetime, timedelta, timezone

from config.database import db
from models import PasswordResetCode, User
from repositories import password_reset as reset_repo
from repositories import sessions as sessions_repo
from services import audit, whatsapp_messages
from services.auth import check_password_policy, find_login_user
from services.errors import ValidationError
from services.security import hash_password, hash_token

CODE_MINUTES = whatsapp_messages.RESET_CODE_MINUTES
MAX_CODES_PER_HOUR = 5
MAX_WRONG_TRIES = 5
BAD_CODE = "That code is wrong or has expired. Ask for a new one."


def _hash(user_id: int, code: str) -> str:
    return hash_token(f"{user_id}:{code}")


def new_code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def _can_reset(user: User | None) -> bool:
    """A real, active login that has a password of its own (a student who has not activated yet uses the activation link)."""
    return user is not None and user.is_active and bool(user.password_hash)


def request_code(login: str) -> None:
    """Send a code to the person, if there is a person. Never says which."""
    user = find_login_user(login.strip())
    if not _can_reset(user):
        return
    now = datetime.now(timezone.utc)
    if reset_repo.count_since(user.user_id, now - timedelta(hours=1)) >= MAX_CODES_PER_HOUR:
        return
    code = new_code()
    row = PasswordResetCode(user_id=user.user_id, code_hash=_hash(user.user_id, code), expires_at=now + timedelta(minutes=CODE_MINUTES))
    db.session.add(row)
    db.session.flush()
    message = whatsapp_messages.password_reset_code(user, code, row.code_id)
    audit.record("PASSWORD_RESET_CODE_REQUESTED", "user", user.user_id, actor_user_id=user.user_id,
                 new={"sent": bool(message and message.status == "Queued")})


def reset(login: str, code: str, new_password: str) -> None:
    user = find_login_user(login.strip())
    now = datetime.now(timezone.utc)
    row = reset_repo.latest_open(user.user_id, now) if _can_reset(user) else None
    if row is None:
        raise ValidationError(BAD_CODE, {"code": [BAD_CODE]})
    if not secrets.compare_digest(row.code_hash, _hash(user.user_id, code.strip())):
        row.wrong_attempts += 1
        if row.wrong_attempts >= MAX_WRONG_TRIES:
            row.used_at = now  # burned: ask for a new code
        db.session.commit()  # the 422 response would otherwise roll the count back
        raise ValidationError(BAD_CODE, {"code": [BAD_CODE]})
    check_password_policy(new_password, field="new_password")

    row.used_at = now
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = now
    user.failed_login_attempts, user.locked_until = 0, None
    signed_out = sessions_repo.revoke_all_for_user(user.user_id, "password reset with a code")
    audit.record("PASSWORD_RESET_WITH_CODE", "user", user.user_id, actor_user_id=user.user_id, new={"sessions_ended": signed_out})

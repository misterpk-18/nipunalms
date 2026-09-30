"""The signed-in user's own profile: identity, language, devices and sessions, password and recovery information.

A student's mobile number is shown masked and labelled as a shared family number: it is never identity proof.
"""
import re
from dataclasses import dataclass

from models import ActiveSession, Branch, Student, User, UserRoleScope
from repositories import branches as branches_repo
from repositories import sessions as sessions_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import audit
from services.context import current_user
from services.errors import Forbidden, NotFound

# (pattern, label): the first match wins, so Edge and Opera (which also say Chrome) come first
BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
SYSTEMS = (("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iOS"), ("Mac OS X", "macOS"), ("Linux", "Linux"))


@dataclass
class ProfileView:
    user: User
    student: Student | None
    scopes: list[UserRoleScope]
    branches: list[Branch]
    devices: list[ActiveSession]


def describe_device(user_agent: str | None) -> str:
    """'Chrome · Android' from a User-Agent string; 'Unknown device' when nothing is recognised."""
    agent = user_agent or ""
    browser = next((label for marker, label in BROWSERS if marker in agent), None)
    system = next((label for marker, label in SYSTEMS if marker in agent), None)
    return " · ".join(part for part in (browser, system) if part) or "Unknown device"


def mask_mobile(mobile: str | None) -> str | None:
    """'+91 ●●●●●●0417': only the last four digits."""
    if not mobile:
        return None
    digits = re.sub(r"\D", "", mobile)
    return f"{'+91 ' if mobile.startswith('+91') else ''}●●●●●●{digits[-4:]}"


def get_profile() -> ProfileView:
    current = current_user()
    user = users_repo.get_by_id(current.user_id)
    return ProfileView(
        user=user,
        student=students_repo.get_student(user.student_id) if user.student_id else None,
        scopes=users_repo.active_scopes(user.user_id),
        branches=branches_repo.list_active(current.branch_ids()),
        devices=sessions_repo.list_active_for_user(user.user_id),
    )


def set_language(language: str) -> Student:
    """Preferred language of a student (English / Telugu)."""
    current = current_user()
    if current.student_id is None:
        raise Forbidden("Only students have a preferred language")
    student = students_repo.get_student(current.student_id)
    if student is None:
        raise NotFound("Student not found")
    student.preferred_language = language
    return student


def sign_out_other_devices() -> int:
    """Revoke every session of the user except the one making the request."""
    current = current_user()
    signed_out = sessions_repo.revoke_all_for_user(current.user_id, "signed out other devices", except_session_id=current.session_id)
    audit.record("OTHER_SESSIONS_REVOKED", "user", current.user_id, new={"sessions": signed_out})
    return signed_out

"""Super Admin: student account administration (search, status, suspend / reactivate, end sessions).

Activation links are issued through `POST /students/{id}/activation` (services/activation.py), which a Super Admin,
Branch Manager or Academic Coordinator may use. Students themselves are created only by the CRM.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from models import Student, User
from repositories import admin_students as students_repo
from repositories import audit_log as audit_repo
from repositories import sessions as sessions_repo
from repositories import students as students_read_repo
from repositories.common import paginate_rows
from services import audit
from services.errors import BusinessRule, NotFound


@dataclass
class StudentAccount:
    student: Student
    user: User | None
    enrolment_counts: dict[str, int]
    active_sessions: int


def search(filters: dict, page: int, per_page: int) -> tuple[list[StudentAccount], dict]:
    rows, meta = paginate_rows(students_repo.search_stmt(filters), page, per_page)
    counts = students_repo.enrolment_status_counts([student.student_id for student, _ in rows])
    sessions = students_repo.active_session_counts([user.user_id for _, user in rows if user is not None])
    return [
        StudentAccount(student, user, counts.get(student.student_id, {}), sessions.get(user.user_id, 0) if user else 0)
        for student, user in rows
    ], meta


def get_account(student_id: int) -> StudentAccount:
    found = students_repo.get_with_user(student_id)
    if found is None:
        raise NotFound("Student not found")
    student, user = found
    sessions = students_repo.active_session_counts([user.user_id]) if user else {}
    return StudentAccount(student, user, students_repo.enrolment_status_counts([student_id]).get(student_id, {}),
                          sessions.get(user.user_id, 0) if user else 0)


def detail(student_id: int) -> dict:
    """The account plus enrolments, the outstanding activation link's state and recent audit entries."""
    account = get_account(student_id)
    activation = students_read_repo.outstanding_activation(student_id)
    suspension = (audit_repo.latest_for_entity("student", str(student_id), "STUDENT_SUSPENDED")
                  if account.student.activation_status == "Suspended" else None)
    return {
        "account": account,
        "enrolments": students_repo.enrolment_rows(student_id),
        "activation": activation,
        "suspension": suspension,
        "audit": audit_repo.recent_for_entity("student", str(student_id), 10),
    }


def suspend(student_id: int, reason: str) -> StudentAccount:
    """Block sign-in, end every session and cancel the outstanding activation link."""
    account = get_account(student_id)
    student, user = account.student, account.user
    if student.activation_status == "Suspended":
        raise BusinessRule("This account is already suspended")
    if user is None:
        raise BusinessRule("This student has no LMS login yet")

    previous = student.activation_status
    student.activation_status = "Suspended"
    user.is_active = False
    signed_out = sessions_repo.revoke_all_for_user(user.user_id, "account suspended")
    students_read_repo.revoke_outstanding_activation(student_id, datetime.now(timezone.utc))
    audit.record("STUDENT_SUSPENDED", "student", student_id, reason=reason, branch_id=student.service_branch_id,
                 old={"activation_status": previous}, new={"activation_status": "Suspended", "sessions_ended": signed_out})
    return get_account(student_id)


def reactivate(student_id: int, reason: str | None) -> StudentAccount:
    """Back to Activated when the student had set a password, else Account Created (staff issue a new activation link)."""
    account = get_account(student_id)
    student, user = account.student, account.user
    if student.activation_status != "Suspended":
        raise BusinessRule("This account is not suspended")

    student.activation_status = "Activated" if user is not None and user.password_hash else "Account Created"
    if user is not None:
        user.is_active = True
        user.failed_login_attempts, user.locked_until = 0, None
    audit.record("STUDENT_REACTIVATED", "student", student_id, reason=reason, branch_id=student.service_branch_id,
                 old={"activation_status": "Suspended"}, new={"activation_status": student.activation_status})
    return get_account(student_id)


def revoke_sessions(student_id: int, reason: str | None) -> int:
    """Sign the student out everywhere. Returns how many sessions ended."""
    account = get_account(student_id)
    if account.user is None:
        raise BusinessRule("This student has no LMS login yet")
    ended = sessions_repo.revoke_all_for_user(account.user.user_id, "sessions revoked by administrator")
    audit.record("STUDENT_SESSIONS_REVOKED", "student", student_id, reason=reason, branch_id=account.student.service_branch_id,
                 new={"sessions_ended": ended})
    return ended

"""Who may change delivery records. Viewing follows services/scope.py (404 outside scope); changing needs a management role
at the record's branch (403 when the record is visible but the user may not change it)."""
from services.context import ACADEMIC_ROLES, CurrentUser, current_user
from services.errors import Forbidden

# Branch Managers of their session's branch; Super Admin and Founder / CEO for every branch (full read and write)
MANAGE_ROLES = ACADEMIC_ROLES
ALLOCATE_ROLES = MANAGE_ROLES

def is_student_only(user: CurrentUser | None = None) -> bool:
    """A learner: the session's role is Student."""
    user = user or current_user()
    return user.role_code == "STUDENT"


def can_manage_branch(branch_id: int, user: CurrentUser | None = None) -> bool:
    user = user or current_user()
    return user.has_role(*MANAGE_ROLES, branch_id=branch_id)


def assert_can_manage_branch(branch_id: int, user: CurrentUser | None = None) -> None:
    if not can_manage_branch(branch_id, user):
        raise Forbidden("You don't have access to this action")


def assert_can_allocate_branch(branch_id: int, user: CurrentUser | None = None) -> None:
    user = user or current_user()
    if not user.has_role(*ALLOCATE_ROLES, branch_id=branch_id):
        raise Forbidden("You don't have access to this action")

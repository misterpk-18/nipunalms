"""Who may change delivery records. Viewing follows services/scope.py (404 outside scope); changing needs a management role
at the record's branch (403 when the record is visible but the user may not change it)."""
from services.context import CurrentUser, current_user
from services.errors import Forbidden

# Branch Managers of the branch, and Super Admin (all branches). The Founder / CEO reads only.
MANAGE_ROLES = ("BRANCH_MANAGER", "SUPER_ADMIN")
# Curriculum is global (not per branch): Branch Managers and Super Admin draft, submit and review it
CURRICULUM_ROLES = ("BRANCH_MANAGER", "SUPER_ADMIN")
# ... and the Founder / CEO or Super Admin approve, activate and retire it (Module 14 §5, §11)
CURRICULUM_APPROVER_ROLES = ("FOUNDER_CEO", "SUPER_ADMIN")


def is_student_only(user: CurrentUser | None = None) -> bool:
    """A learner: the login has the Student role and nothing else."""
    user = user or current_user()
    return user.role_codes == {"STUDENT"}


def can_manage_branch(branch_id: int, user: CurrentUser | None = None) -> bool:
    user = user or current_user()
    return user.has_role(*MANAGE_ROLES, branch_id=branch_id)


def assert_can_manage_branch(branch_id: int, user: CurrentUser | None = None) -> None:
    if not can_manage_branch(branch_id, user):
        raise Forbidden("You don't have access to this action")

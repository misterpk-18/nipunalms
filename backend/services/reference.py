"""Reference lists for dropdowns (staff only)."""
from models import Branch, Course, Role, UserRoleScope
from repositories import branches as branches_repo
from repositories import catalog as catalog_repo
from repositories import users as users_repo
from services.context import current_user
from services.errors import NotFound


def list_branches() -> list[Branch]:
    return branches_repo.list_active(current_user().branch_ids())


def list_roles() -> list[Role]:
    return users_repo.list_roles()


def list_courses() -> list[Course]:
    return catalog_repo.list_courses()


def list_staff(role_code: str | None, branch_id: int | None) -> list[UserRoleScope]:
    """Staff with an active scope, at the branches the user works in (narrowed to one branch if given)."""
    branch_ids = current_user().branch_ids()
    if branch_id is not None:
        if branch_ids is not None and branch_id not in branch_ids:
            raise NotFound("Branch not found")  # not one of the user's branches
        branch_ids = {branch_id}
    return users_repo.staff_scopes([role_code] if role_code else None, branch_ids)

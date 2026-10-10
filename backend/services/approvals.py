"""Independent decisions (Modules 14, 21, 22): a sensitive request is decided by someone other than the people who raised or
produced it. Every service that needs this calls require_independent, so the rule and its 422 read the same everywhere.

A Branch Manager reviews the requests and corrections of trainers and other staff and decides most things alone. When the
requester is a Branch Manager, nobody at the branch can review the request independently, so the Founder / CEO or a Super
Admin decides it (UX plan: Branch Manager merged with the Academic Coordinator)."""
from repositories import users as users_repo
from services.context import ADMIN_ROLES, current_user
from services.errors import BusinessRule

BRANCH_MANAGER_OWN_REQUEST = "A Branch Manager's own request is decided by the Founder / CEO or a Super Admin"


def requester_needs_admin(requester_user_id: int | None) -> bool:
    """True when the request was raised by a Branch Manager: only the Founder / CEO or a Super Admin may decide it."""
    return requester_user_id is not None and users_repo.holds_role(requester_user_id, "BRANCH_MANAGER")


def can_decide(requester_user_id: int | None) -> bool:
    """Whether the current user may decide a request raised by this person (not their own; a Branch Manager's goes to an admin)."""
    user = current_user()
    if requester_user_id is not None and user.user_id == requester_user_id:
        return False
    return not requester_needs_admin(requester_user_id) or user.has_role(*ADMIN_ROLES)


def require_independent(*involved_user_ids: int | None, message: str, requester: int | None = None) -> None:
    """422 when the current user is one of the people involved (requester, submitter, recommender, marker). With `requester`,
    also 422 when that person is a Branch Manager and the current user is not the Founder / CEO or a Super Admin."""
    if current_user().user_id in {u for u in involved_user_ids if u is not None}:
        raise BusinessRule(message)
    if requester is not None and requester_needs_admin(requester) and not current_user().has_role(*ADMIN_ROLES):
        raise BusinessRule(BRANCH_MANAGER_OWN_REQUEST)

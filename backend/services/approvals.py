"""Independent decisions (Modules 14, 21, 22): a sensitive request is decided by someone other than the people who raised or
produced it. Every service that needs this calls require_independent, so the rule and its 422 read the same everywhere."""
from services.context import current_user
from services.errors import BusinessRule


def require_independent(*involved_user_ids: int | None, message: str) -> None:
    """422 when the current user is one of the people involved (requester, submitter, recommender, marker)."""
    if current_user().user_id in {u for u in involved_user_ids if u is not None}:
        raise BusinessRule(message)

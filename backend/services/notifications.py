"""Internal notification sending for other slices (the Notification Centre API comes with the student-services slice).

A notification goes to explicit recipients, or to everyone holding a role at a branch. Sending is deduplicated:
one notification per (event_key, recipient), however many times the same event is processed.
"""
from sqlalchemy.dialects.postgresql import insert

from config.database import db
from models import Notification
from repositories import users as users_repo


def notify(
    *,
    category: str,
    title: str,
    event_key: str,
    body: str | None = None,
    link: str | None = None,
    recipient_user_ids: list[int] | None = None,
    role_code: str | None = None,
    branch_id: int | None = None,
    action_required: bool = False,
) -> int:
    """Send a notification; returns how many recipients newly received it.

    Give either recipient_user_ids, or role_code (+ branch_id: holders at that branch and company-wide holders).
    """
    if recipient_user_ids is None:
        if role_code is None:
            raise ValueError("notify needs recipient_user_ids or role_code")
        recipient_user_ids = users_repo.user_ids_with_role(role_code, branch_id)

    created = 0
    for user_id in recipient_user_ids:
        result = db.session.execute(
            insert(Notification)
            .values(recipient_user_id=user_id, branch_id=branch_id, category=category, title=title, body=body,
                    link=link, event_key=event_key, action_status="Open" if action_required else "None")
            .on_conflict_do_nothing(index_elements=["event_key", "recipient_user_id"])
        )
        created += result.rowcount
    return created

"""The notification centre: a user's own notifications, counts and preferences."""
from sqlalchemy import Select, exists, func, or_, select, update

from config.database import db
from models import Integration, Notification, NotificationPreference, Role, UserRoleScope
from repositories.users import active_scope_condition

# Channel -> the integrations register entry that says whether it can deliver
CHANNEL_INTEGRATIONS = {"WhatsApp": "WHATSAPP", "Email": "EMAIL"}


def _mine(user_id: int, scoped: bool):
    """Sent to this user and, for staff (scoped), still within their access (Module 26 §8): a notice about a branch stays
    visible only while the user holds its role (any role, for notices sent to named people) at that branch or company-wide.
    A transfer or a removed role hides the old branch's notices; students always keep their own."""
    condition = Notification.recipient_user_id == user_id
    if not scoped:
        return condition
    in_scope = exists(
        select(UserRoleScope.scope_id).join(Role, Role.role_id == UserRoleScope.role_id).where(
            UserRoleScope.user_id == user_id, active_scope_condition(),
            or_(UserRoleScope.branch_id.is_(None), UserRoleScope.branch_id == Notification.branch_id),
            or_(Notification.role_code.is_(None), Role.role_code == Notification.role_code),
        )
    )
    scoped_to = condition & (Notification.branch_id.is_(None) | in_scope)
    branch_id = _session_branch(user_id)
    if branch_id is not None:  # a Branch Manager with several branches sees only the session's branch
        scoped_to &= Notification.branch_id.is_(None) | (Notification.branch_id == branch_id)
    return scoped_to


def _session_branch(user_id: int) -> int | None:
    from services.context import current_user  # the one place a repository reads the signed-in session: notices follow its branch

    user = current_user()
    return user.active_branch_id if user is not None and user.user_id == user_id else None


def get_for_recipient(notification_id: int, user_id: int, scoped: bool) -> Notification | None:
    """The notification, only when it was sent to this user and is still within their access."""
    return db.session.execute(select(Notification).where(Notification.notification_id == notification_id, _mine(user_id, scoped))).scalar_one_or_none()


def list_stmt(user_id: int, scoped: bool, filters: dict) -> Select:
    stmt = select(Notification).where(_mine(user_id, scoped)).order_by(
        Notification.created_at.desc(), Notification.notification_id.desc()
    )
    view = filters.get("view", "my")
    if not filters.get("show_failures"):
        # a channel that could not deliver is a system matter, shown only to the people who run the system
        stmt = stmt.where(Notification.delivery_status == "Delivered")
    if view == "needs_action":
        stmt = stmt.where(Notification.action_status == "Open")
    elif view == "new":
        stmt = stmt.where(Notification.read_at.is_(None), Notification.acknowledged_at.is_(None), Notification.action_status != "Open")
    elif view == "done":
        stmt = stmt.where(Notification.action_status != "Open",
                          or_(Notification.action_status == "Completed", Notification.read_at.is_not(None), Notification.acknowledged_at.is_not(None)))
    elif view == "action":
        stmt = stmt.where(Notification.action_status == "Open")
    elif view == "unread":
        stmt = stmt.where(Notification.read_at.is_(None), Notification.delivery_status == "Delivered")
    elif view == "completed":
        stmt = stmt.where(Notification.action_status == "Completed")
    elif view == "system":
        stmt = stmt.where(Notification.delivery_status == "Failed")
    if filters.get("category"):
        stmt = stmt.where(Notification.category == filters["category"])
    if filters.get("q"):
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(or_(Notification.title.ilike(pattern), Notification.body.ilike(pattern)))
    return stmt


def categories(user_id: int, scoped: bool) -> list[str]:
    stmt = select(Notification.category).where(_mine(user_id, scoped)).distinct().order_by(Notification.category)
    return list(db.session.execute(stmt).scalars())


def counts(user_id: int, scoped: bool) -> dict[str, int]:
    """Unread (delivered, not yet read) and action-required (open action) notifications."""
    base = select(func.count()).select_from(Notification).where(_mine(user_id, scoped))
    unread = db.session.execute(base.where(Notification.read_at.is_(None), Notification.delivery_status == "Delivered")).scalar_one()
    action = db.session.execute(base.where(Notification.action_status == "Open")).scalar_one()
    new = db.session.execute(base.where(Notification.read_at.is_(None), Notification.acknowledged_at.is_(None), Notification.action_status != "Open",
                                        Notification.delivery_status == "Delivered")).scalar_one()
    return {"unread": unread, "action_required": action, "needs_action": action, "new": new}


def mark_all_read(user_id: int, scoped: bool) -> int:
    result = db.session.execute(
        update(Notification)
        .where(_mine(user_id, scoped), Notification.read_at.is_(None), Notification.delivery_status == "Delivered")
        .values(read_at=func.now())
    )
    return result.rowcount


def preferences(user_id: int) -> dict[tuple[str, str], bool]:
    rows = db.session.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id)).scalars()
    return {(p.preference_group, p.channel): p.enabled for p in rows}


def set_preference(user_id: int, group: str, channel: str, enabled: bool) -> None:
    row = db.session.get(NotificationPreference, (user_id, group, channel))
    if row is None:
        db.session.add(NotificationPreference(user_id=user_id, preference_group=group, channel=channel, enabled=enabled))
    else:
        row.enabled = enabled


def channel_integrations() -> dict[str, Integration]:
    rows = db.session.execute(select(Integration).where(Integration.integration_code.in_(CHANNEL_INTEGRATIONS.values()))).scalars()
    by_code = {i.integration_code: i for i in rows}
    return {channel: by_code[code] for channel, code in CHANNEL_INTEGRATIONS.items() if code in by_code}

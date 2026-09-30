"""The notification centre: a user's own notifications, counts and preferences."""
from sqlalchemy import Select, func, or_, select, update

from config.database import db
from models import Integration, Notification, NotificationPreference

# Channel -> the integrations register entry that says whether it can deliver
CHANNEL_INTEGRATIONS = {"WhatsApp": "WHATSAPP", "Email": "EMAIL"}


def get_for_recipient(notification_id: int, user_id: int) -> Notification | None:
    """The notification, only when it was sent to this user."""
    notification = db.session.get(Notification, notification_id)
    return notification if notification is not None and notification.recipient_user_id == user_id else None


def list_stmt(user_id: int, filters: dict) -> Select:
    stmt = select(Notification).where(Notification.recipient_user_id == user_id).order_by(
        Notification.created_at.desc(), Notification.notification_id.desc()
    )
    view = filters.get("view", "my")
    if view == "action":
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


def categories(user_id: int) -> list[str]:
    stmt = select(Notification.category).where(Notification.recipient_user_id == user_id).distinct().order_by(Notification.category)
    return list(db.session.execute(stmt).scalars())


def counts(user_id: int) -> dict[str, int]:
    """Unread (delivered, not yet read) and action-required (open action) notifications."""
    base = select(func.count()).select_from(Notification).where(Notification.recipient_user_id == user_id)
    unread = db.session.execute(base.where(Notification.read_at.is_(None), Notification.delivery_status == "Delivered")).scalar_one()
    action = db.session.execute(base.where(Notification.action_status == "Open")).scalar_one()
    return {"unread": unread, "action_required": action}


def mark_all_read(user_id: int) -> int:
    result = db.session.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None), Notification.delivery_status == "Delivered")
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

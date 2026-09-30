"""The notification centre (Module 26): a user's own notifications with separate delivery, read, acknowledged and
action states, the header unread count, and per-group channel preferences. In-app is always on; WhatsApp and email are
listed with the state of their integration (nothing is sent through them until they are verified)."""
from datetime import datetime, timezone

from config.database import db
from models import Notification
from models.notification_preferences import CHANNELS, PREFERENCE_GROUPS
from repositories import notifications as notifications_repo
from repositories.common import paginate
from services.context import current_user
from services.errors import BusinessRule, NotFound, ValidationError

# Groups whose external channels start enabled (essential service messages); the others start muted
DEFAULT_EXTERNAL_ON = {"Service"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def delivery_label(notification: Notification) -> str:
    """'Delivered in-app', or why an external message was not sent."""
    if notification.delivery_status == "Delivered" and notification.channel == "In-app":
        return "Delivered in-app"
    if notification.delivery_status == "Delivered":
        return f"Delivered by {notification.channel}"
    return f"{notification.channel} — {notification.delivery_note} (not sent)"


def list_notifications(filters: dict, page: int, per_page: int) -> tuple[list[Notification], dict]:
    return paginate(notifications_repo.list_stmt(current_user().user_id, filters), page, per_page)


def overview() -> dict:
    """Counts for the header bell and the categories the user can filter by."""
    user_id = current_user().user_id
    return {**notifications_repo.counts(user_id), "categories": notifications_repo.categories(user_id)}


def _own(notification_id: int) -> Notification:
    notification = notifications_repo.get_for_recipient(notification_id, current_user().user_id)
    if notification is None:
        raise NotFound("Notification not found")
    return notification


def mark_read(notification_id: int) -> Notification:
    notification = _own(notification_id)
    if notification.read_at is None:
        notification.read_at = _now()
    return notification


def mark_all_read() -> int:
    return notifications_repo.mark_all_read(current_user().user_id)


def acknowledge(notification_id: int) -> Notification:
    """Acknowledging also counts as reading it; it does not complete the action behind it."""
    notification = _own(notification_id)
    now = _now()
    notification.read_at = notification.read_at or now
    notification.acknowledged_at = notification.acknowledged_at or now
    return notification


def mark_action_done(notification_id: int) -> Notification:
    notification = _own(notification_id)
    if notification.action_status != "Open":
        raise BusinessRule("This notification has no open action")
    notification.action_status = "Completed"
    notification.read_at = notification.read_at or _now()
    return notification


# ---------------------------------------------------------------- preferences

def get_preferences() -> dict:
    """Every group x channel with its current setting, and the state of each external channel's integration."""
    stored = notifications_repo.preferences(current_user().user_id)
    integrations = notifications_repo.channel_integrations()
    return {
        "channels": [
            {
                "channel": channel,
                "always_on": channel == "In-app",
                "configuration_status": integrations[channel].configuration_status if channel in integrations else None,
                "verification_status": integrations[channel].verification_status if channel in integrations else None,
            }
            for channel in CHANNELS
        ],
        "groups": [
            {
                "group": group,
                "settings": {
                    channel: True if channel == "In-app" else stored.get((group, channel), group in DEFAULT_EXTERNAL_ON)
                    for channel in CHANNELS
                },
            }
            for group in PREFERENCE_GROUPS
        ],
    }


def set_preferences(changes: list[dict]) -> dict:
    user_id = current_user().user_id
    for change in changes:
        if change["channel"] == "In-app" and not change["enabled"]:
            raise ValidationError("In-app notifications cannot be turned off", {"channel": ["In-app is always on"]})
        notifications_repo.set_preference(user_id, change["group"], change["channel"], change["enabled"])
    db.session.flush()
    return get_preferences()

from flask import request

from controllers.common import Validator, get_page_params, json_body, ok, paginated
from models.notification_preferences import CHANNELS, PREFERENCE_GROUPS
from services import notification_centre as centre

VIEWS = ("my", "action", "unread", "completed", "system")


def _item(notification) -> dict:
    return {**notification.to_dict(), "delivery_label": centre.delivery_label(notification)}


def list_notifications():
    v = Validator(request.args.to_dict())
    v.choice("view", VIEWS, default="my")
    v.string("category", max_length=50)
    v.string("q", max_length=100)
    page, per_page = get_page_params()
    items, meta = centre.list_notifications(v.validate(), page, per_page)
    return paginated([_item(n) for n in items], meta)


def overview():
    return ok(centre.overview())


def mark_read(notification_id: int):
    return ok(_item(centre.mark_read(notification_id)))


def mark_all_read():
    return ok({"marked": centre.mark_all_read()})


def acknowledge(notification_id: int):
    return ok(_item(centre.acknowledge(notification_id)))


def mark_action_done(notification_id: int):
    return ok(_item(centre.mark_action_done(notification_id)))


def get_preferences():
    return ok(centre.get_preferences())


def set_preferences():
    v = Validator(json_body())

    def setting(item: Validator) -> None:
        item.choice("group", PREFERENCE_GROUPS, required=True)
        item.choice("channel", CHANNELS, required=True)
        item.boolean("enabled", required=True)

    v.list_of("preferences", setting, required=True, min_items=1)
    return ok(centre.set_preferences(v.validate()["preferences"]))

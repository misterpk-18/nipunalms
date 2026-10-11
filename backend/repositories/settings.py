"""Admin-editable values in app_settings."""
from typing import Any

from sqlalchemy import select

from config.database import db
from models import AppSetting


def get(key: str, default: Any = None) -> Any:
    value = db.session.execute(select(AppSetting.setting_value).where(AppSetting.setting_key == key)).scalar()
    return default if value is None else value


def get_int(key: str, default: int) -> int:
    return int(get(key, default))


def set_value(key: str, value: Any, user_id: int | None, description: str | None = None) -> None:
    """Create or change a setting; the description is kept when the row already has one."""
    row = db.session.get(AppSetting, key)
    if row is None:
        db.session.add(AppSetting(setting_key=key, setting_value=value, description=description, updated_by=user_id))
    else:
        row.setting_value, row.updated_by = value, user_id
    db.session.flush()

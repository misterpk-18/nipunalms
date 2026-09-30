"""The integrations register."""
from sqlalchemy import select

from config.database import db
from models import Integration


def list_all() -> list[Integration]:
    return list(db.session.execute(select(Integration).order_by(Integration.integration_id)).scalars())


def get(integration_id: int) -> Integration | None:
    return db.session.get(Integration, integration_id)


def get_by_code(integration_code: str) -> Integration | None:
    return db.session.execute(
        select(Integration).where(Integration.integration_code == integration_code)
    ).scalar_one_or_none()

"""The security controls register."""
from sqlalchemy import select

from config.database import db
from models import SecurityControl


def list_all() -> list[SecurityControl]:
    return list(db.session.execute(select(SecurityControl).order_by(SecurityControl.control_id)).scalars())


def get(control_id: int) -> SecurityControl | None:
    return db.session.get(SecurityControl, control_id)

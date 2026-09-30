"""Dashboard cards: one source failing must not take a whole dashboard down."""
import logging
from collections.abc import Callable

from config.database import db

logger = logging.getLogger(__name__)


def safe_card(name: str, build: Callable[[], dict]) -> dict:
    """Run one card's source inside a savepoint. A failure marks only that card Unavailable (and is logged)."""
    try:
        with db.session.begin_nested():
            return build()
    except Exception:  # noqa: BLE001 - a dashboard card must degrade, never raise
        logger.exception("Dashboard card %s failed", name)
        return {"state": "Unavailable", "message": "This information could not be loaded right now."}

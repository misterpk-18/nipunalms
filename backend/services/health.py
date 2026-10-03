"""Health check: is the app up and can it reach the database?

The CRM's worker polls GET /api/v1/health every 10 s while events wait because the LMS was unreachable, and releases
them as soon as it answers 200 (CRM_ROUND3_JOINT_TESTS_RESULTS.md §3). Keep it unauthenticated and to one cheap query."""
import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config.database import db

logger = logging.getLogger(__name__)


def get_status() -> dict:
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        db.session.rollback()
        database = "unavailable"

    return {"status": "ok" if database == "ok" else "degraded", "database": database}

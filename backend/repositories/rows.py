"""Pagination for statements that select several columns or entities (common.paginate returns only the first one)."""
from sqlalchemy import Select, func, select

from config.database import db


def paginate_rows(stmt: Select, page: int, per_page: int) -> tuple[list, dict]:
    """Rows of the statement for one page, as tuples, with the same meta as common.paginate."""
    total = db.session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.session.execute(stmt.limit(per_page).offset((page - 1) * per_page)).unique().all()
    return [tuple(row) for row in rows], {"page": page, "per_page": per_page, "total": total, "pages": -(-total // per_page)}

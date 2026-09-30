"""Class sessions: scoped list."""
from models import ClassSession
from repositories import batches as batches_repo
from repositories.common import paginate
from services import scope
from services.errors import NotFound


def list_sessions(filters: dict, page: int, per_page: int) -> tuple[list[ClassSession], dict]:
    """Sessions of the batches the user may see, in start order."""
    if filters.get("batch_id"):
        batch = batches_repo.get_batch(filters["batch_id"])
        if batch is None:
            raise NotFound("Batch not found")
        scope.assert_can_view_batch(batch)
    stmt = batches_repo.sessions_stmt(filters, scope.visible_branch_ids(), scope.visible_batch_ids())
    return paginate(stmt, page, per_page)

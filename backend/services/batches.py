"""Batches: scoped list and detail."""
from models import Batch
from repositories import batches as batches_repo
from repositories.common import paginate
from services import scope
from services.errors import NotFound


def list_batches(filters: dict, page: int, per_page: int) -> tuple[list[tuple[Batch, int]], dict]:
    """Batches the user may see, each with its allocated-student count."""
    stmt = batches_repo.list_stmt(filters, scope.visible_branch_ids(), scope.visible_batch_ids())
    batches, meta = paginate(stmt, page, per_page)
    counts = batches_repo.allocated_counts([b.batch_id for b in batches])
    return [(b, counts.get(b.batch_id, 0)) for b in batches], meta


def get_batch(batch_id: int) -> tuple[Batch, int]:
    batch = batches_repo.get_batch(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    return batch, batches_repo.allocated_counts([batch_id]).get(batch_id, 0)

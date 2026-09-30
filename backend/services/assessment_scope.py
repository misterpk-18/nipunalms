"""Who may see and change assessment records of a batch. Shared by the assignment, test, question and result services.

Reading a batch's assessments follows services/scope.py (branch roles, assigned trainer, allocated student). Changing them
is narrower: the trainers assigned to the batch, the branch Academic Coordinator and Super Admin. The Branch Manager and the
Founder read; moderation and publication belong to the Academic Coordinator and Super Admin.
"""
from sqlalchemy import select

from config.database import db
from models import Batch, BatchTrainer, Enrolment
from repositories import batches as batches_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import scope
from services.context import MODERATOR_ROLES, CurrentUser, current_user
from services.errors import Forbidden, NotFound


def is_student(user: CurrentUser | None = None) -> bool:
    return (user or current_user()).student_id is not None


def can_manage_batch(batch: Batch, user: CurrentUser | None = None) -> bool:
    """Author, release and review work for this batch: an assigned trainer, the branch Academic Coordinator, Super Admin."""
    user = user or current_user()
    if user.has_role("SUPER_ADMIN") or user.has_role("ACADEMIC_COORDINATOR", branch_id=batch.branch_id):
        return True
    return user.has_role("TRAINER") and batch.batch_id in scope.trainer_batch_ids(user)


def can_moderate_batch(batch: Batch, user: CurrentUser | None = None) -> bool:
    user = user or current_user()
    return user.has_role(*MODERATOR_ROLES, branch_id=batch.branch_id)


def load_batch(batch_id: int) -> Batch:
    """The batch, or 404 when it does not exist or the user cannot see it."""
    batch = batches_repo.get_batch(batch_id)
    if batch is None:
        raise NotFound("Batch not found")
    scope.assert_can_view_batch(batch)
    return batch


def assert_can_manage(batch: Batch) -> None:
    if not can_manage_batch(batch):
        raise Forbidden("You can't change assessments for this batch")


def manageable_batch(batch_id: int) -> Batch:
    """The batch for a change: 404 outside the user's scope, 403 when they can see it but may not change its assessments."""
    batch = load_batch(batch_id)
    assert_can_manage(batch)
    return batch


def assert_can_moderate(batch: Batch) -> None:
    if not can_moderate_batch(batch):
        raise Forbidden("Only the Academic Coordinator can moderate and publish results")


def visible_batch_clause(batch_id_column):
    """SQL condition for staff lists: batches in the user's branches or that they teach (None = no restriction)."""
    branch_ids = scope.visible_branch_ids()
    if branch_ids is None:
        return None
    clause = batch_id_column.in_(select(Batch.batch_id).where(Batch.branch_id.in_(branch_ids or {0})))
    taught = scope.trainer_batch_ids()
    return clause | batch_id_column.in_(taught) if taught else clause


def seats_of_student(student_id: int) -> dict[int, Enrolment]:
    """A student's seat per batch: batch id -> the enrolment allocated there."""
    enrolments = {e.enrolment_id: e for e in students_repo.enrolments_of_student(student_id)}
    allocations = batches_repo.active_allocations(list(enrolments))
    seats: dict[int, Enrolment] = {}
    for enrolment_id, allocation in allocations.items():
        seats.setdefault(allocation.batch_id, enrolments[enrolment_id])
    return seats


def student_enrolments_by_batch(user: CurrentUser | None = None) -> dict[int, Enrolment]:
    """The current student's seat per batch: batch id -> the enrolment allocated there."""
    user = user or current_user()
    return seats_of_student(user.student_id) if user.student_id is not None else {}


def student_seat(batch_id: int, user: CurrentUser | None = None) -> Enrolment:
    """The student's enrolment in this batch; 404 for a batch they are not allocated to."""
    enrolment = student_enrolments_by_batch(user).get(batch_id)
    if enrolment is None:
        raise NotFound("Not found")
    return enrolment


def batch_trainer_ids(batch: Batch) -> list[int]:
    """Users currently assigned to teach the batch."""
    rows = db.session.execute(
        select(BatchTrainer.trainer_user_id).where(BatchTrainer.batch_id == batch.batch_id, BatchTrainer.to_date.is_(None))
    )
    return list(rows.scalars())


def eligible_reviewers(batch: Batch) -> set[int]:
    """Users who can be named as reviewer or grader: the batch's trainers and the branch Academic Coordinators."""
    return set(batch_trainer_ids(batch)) | set(users_repo.user_ids_with_role("ACADEMIC_COORDINATOR", batch.branch_id))

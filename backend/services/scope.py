"""Record-scope helpers: what the current user may see. Every slice's lists and details go through these.

Scope rules (API_PLAN §2):
  STUDENT               own student record, own enrolments, batches they are allocated to
  TRAINER               batches they are assigned to and the students allocated to those batches
  ACADEMIC_COORDINATOR  everything academic at their branch
  BRANCH_MANAGER        everything at their branch
  SUPER_ADMIN / FOUNDER_CEO  all branches
A user holding several roles gets the union. A record outside scope is a 404, never a 403.
"""
from config.timezone import today_ist
from models import Batch, Enrolment, Student
from repositories import batches as batches_repo
from repositories import students as students_repo
from services.context import ADMIN_ROLES, BRANCH_ROLES, CurrentUser, current_user
from services.errors import NotFound


def _resolve(user: CurrentUser | None) -> CurrentUser:
    return user or current_user()


def visible_branch_ids(user: CurrentUser | None = None) -> set[int] | None:
    """Branches whose records the user sees in full: None = all branches, else the branches where they are
    Branch Manager / Academic Coordinator (empty for a trainer or student, who see specific records instead)."""
    user = _resolve(user)
    if user.has_role(*ADMIN_ROLES):
        return None
    return {s.branch_id for s in user.scopes if s.role_code in BRANCH_ROLES}


def require_branch(branch_id: int, user: CurrentUser | None = None) -> None:
    """404 unless the user sees this branch in full."""
    branch_ids = visible_branch_ids(user)
    if branch_ids is not None and branch_id not in branch_ids:
        raise NotFound("Branch not found")


def trainer_batch_ids(user: CurrentUser | None = None) -> set[int]:
    """Batches the user is currently assigned to as a trainer."""
    user = _resolve(user)
    if not user.has_role("TRAINER"):
        return set()
    return batches_repo.batch_ids_for_trainer(user.user_id, today_ist())


def student_enrolment_ids(user: CurrentUser | None = None) -> set[int]:
    """The user's own enrolments (empty unless the login belongs to a student)."""
    user = _resolve(user)
    if user.student_id is None:
        return set()
    return {e.enrolment_id for e in students_repo.enrolments_of_student(user.student_id)}


def student_batch_ids(user: CurrentUser | None = None) -> set[int]:
    """Batches the user's own enrolments are allocated to."""
    return batches_repo.batch_ids_for_enrolments(student_enrolment_ids(user))


def visible_batch_ids(user: CurrentUser | None = None) -> set[int]:
    """Batches visible through a person-level tie (assigned trainer, allocated student), on top of branch scope."""
    return trainer_batch_ids(user) | student_batch_ids(user)


def assert_can_view_batch(batch: Batch, user: CurrentUser | None = None) -> None:
    branch_ids = visible_branch_ids(user)
    if branch_ids is None or batch.branch_id in branch_ids:
        return
    if batch.batch_id in visible_batch_ids(user):
        return
    raise NotFound("Batch not found")


def assert_can_view_enrolment(enrolment: Enrolment, user: CurrentUser | None = None) -> None:
    user = _resolve(user)
    branch_ids = visible_branch_ids(user)
    if branch_ids is None or enrolment.service_branch_id in branch_ids:
        return
    if enrolment.student_id == user.student_id:
        return
    if enrolment.enrolment_id in batches_repo.enrolment_ids_in_batches(trainer_batch_ids(user)):
        return
    raise NotFound("Enrolment not found")


def assert_can_view_student(student: Student, user: CurrentUser | None = None) -> None:
    """Own record; the student's service branch or a branch that services one of their enrolments; a trainer of their batch."""
    user = _resolve(user)
    if student.student_id == user.student_id:
        return
    branch_ids = visible_branch_ids(user)
    enrolments = students_repo.enrolments_of_student(student.student_id)
    if branch_ids is None or student.service_branch_id in branch_ids:
        return
    if any(e.service_branch_id in branch_ids for e in enrolments):
        return
    trainer_enrolments = batches_repo.enrolment_ids_in_batches(trainer_batch_ids(user))
    if any(e.enrolment_id in trainer_enrolments for e in enrolments):
        return
    raise NotFound("Student not found")

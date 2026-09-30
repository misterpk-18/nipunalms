"""Who is told when delivery changes: the students of a batch, one student, the branch's managers, a trainer.

Every notice goes through notifications.notify(), so repeating the same event never sends it twice.
"""
from repositories import batches as batches_repo
from repositories import users as users_repo
from services import notifications
from services.context import actor_id


def _without_actor(user_ids: list[int]) -> list[int]:
    """The person who made the change already knows about it."""
    me = actor_id()
    return [user_id for user_id in user_ids if user_id != me]


def notify_batch_students(batch_id: int, *, title: str, body: str, event_key: str, link: str, branch_id: int,
                          category: str = "Session") -> None:
    notifications.notify(category=category, title=title, body=body, event_key=event_key, link=link, branch_id=branch_id,
                         recipient_user_ids=batches_repo.student_user_ids_for_batch(batch_id))


def notify_student(student_id: int, *, title: str, body: str, event_key: str, link: str, branch_id: int,
                   category: str = "Enrolment") -> None:
    user = users_repo.get_by_student_id(student_id)
    if user is not None:
        notifications.notify(category=category, title=title, body=body, event_key=event_key, link=link, branch_id=branch_id,
                             recipient_user_ids=[user.user_id])


def notify_users(user_ids: list[int], *, title: str, body: str, event_key: str, link: str, branch_id: int | None,
                 category: str = "Session", action_required: bool = False) -> None:
    recipients = _without_actor(list(dict.fromkeys(user_ids)))
    if recipients:
        notifications.notify(category=category, title=title, body=body, event_key=event_key, link=link, branch_id=branch_id,
                             recipient_user_ids=recipients, action_required=action_required)


def notify_branch_managers(branch_id: int, *, title: str, body: str, event_key: str, link: str, category: str = "Batch",
                           action_required: bool = False) -> None:
    """The Academic Coordinators and Branch Managers of the branch."""
    holders = users_repo.user_ids_with_role("ACADEMIC_COORDINATOR", branch_id) + users_repo.user_ids_with_role("BRANCH_MANAGER", branch_id)
    notify_users(holders, title=title, body=body, event_key=event_key, link=link, branch_id=branch_id, category=category,
                 action_required=action_required)

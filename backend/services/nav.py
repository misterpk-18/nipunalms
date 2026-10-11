"""What the shell shows around every screen: the count badges on navigation items (`GET /me/nav-counts`) and the "Getting
started" steps of each workspace (`GET /me/getting-started`).

Badges are cheap counts of what waits for the person, read from the slice that owns the record and limited to what they see.
A workspace the user does not hold is a 403; a branch outside their scope is a 404. The dismissed state of a Getting started
card lives in the browser, not here.
"""
from datetime import datetime, timedelta, timezone

from repositories import dashboards as dash_repo
from repositories import nav as nav_repo
from services import scope, student_work, trainer_todo
from services import exceptions as exceptions_service
from services import crm_sync
from services.auth import workspaces_for
from services.context import current_user
from services.errors import Forbidden

# Certificate register states that wait for a person to decide
CERTIFICATE_REVIEW = ("Eligibility Review", "Awaiting Approval")
# A support reply counts as "near its deadline" this long before it is due
SUPPORT_WARNING = timedelta(hours=4)


def _require_workspace(workspace: str) -> None:
    if workspace not in workspaces_for(current_user().role_codes):
        raise Forbidden("You don't have access to this workspace")


def _branches(branch_id: int | None) -> set[int] | None:
    """The branches to count: the chosen one (404 outside the user's scope), else everything the user sees."""
    if branch_id is not None:
        scope.require_branch(branch_id)
        return {branch_id}
    return scope.visible_branch_ids()


# ---------------------------------------------------------------- badges

def _student_counts() -> dict[str, int]:
    user = current_user()
    return {"tasks": student_work.todo_count(), "support": nav_repo.support_waiting_on_student(user.student_id)}


def _trainer_counts() -> dict[str, int]:
    user = current_user()
    return {
        "to_grade": trainer_todo.assignments_to_review() + trainer_todo.attempts_to_mark(),
        "support": nav_repo.support_open_for_owner(user.user_id),
        "attendance": trainer_todo.attendance_work()["total"],
        "class_logs": trainer_todo.class_logs_missing(datetime.now(timezone.utc), 1)[0],
    }


def _branch_counts(branch_id: int | None) -> dict[str, int]:
    branch_ids = _branches(branch_id)
    now = datetime.now(timezone.utc)
    enrolments = dash_repo.enrolment_counts(branch_ids)
    certificates = sum(dash_repo.certificates_in_status(CERTIFICATE_REVIEW, branch_ids).values())
    return {
        "waiting": enrolments.get("Allocation Pending", 0),
        "requests": (dash_repo.open_reschedule_requests(branch_ids) + dash_repo.escalated_support_requests(branch_ids)
                     + dash_repo.pending_extension_requests(branch_ids)),
        "content_review": dash_repo.content_awaiting_review(branch_ids),
        "marks": dash_repo.results_awaiting_publication(branch_ids),
        "completion": dash_repo.open_completion_reviews(branch_ids),
        "certificates": certificates,
        "issues": exceptions_service.counts(branch_ids)["total"],
        "recording_issues": dash_repo.unresolved_recording_exceptions(branch_ids),
        "support": nav_repo.support_due_by(branch_ids, now + SUPPORT_WARNING),
        "attendance": nav_repo.pending_recoveries(branch_ids) + nav_repo.pending_corrections(branch_ids),
    }


def _admin_counts() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    return {
        "crm_sync": crm_sync.summary()["failed_events"],
        "issues": exceptions_service.counts(None)["awaiting_owner"],
        "users": nav_repo.locked_users(now),
    }


def _founder_counts() -> dict[str, int]:
    certificates = dash_repo.certificates_in_status(("Awaiting Approval",), None)
    return {
        "curriculum": nav_repo.curriculum_awaiting_approval(),
        "certificates": sum(certificates.values()),
        "access": len(dash_repo.pending_exception_requests()),
    }


def nav_counts(workspace: str, branch_id: int | None = None) -> dict[str, int]:
    """`{key: n}` for one workspace; the keys are the `badgeKey`s of that workspace's navigation items."""
    _require_workspace(workspace)
    if workspace == "student":
        return _student_counts()
    if workspace == "trainer":
        return _trainer_counts()
    if workspace == "branch":
        return _branch_counts(branch_id)
    if workspace == "admin":
        return _admin_counts()
    return _founder_counts()


# ---------------------------------------------------------------- getting started

def _step(key: str, label: str, done: bool, to: str) -> dict:
    return {"key": key, "label": label, "done": done, "to": to}


def _student_steps() -> list[dict]:
    student_id = current_user().student_id
    return [
        _step("activate", "Activate your account", True, "/dashboard"),
        _step("batch", "Check your batch", nav_repo.student_has_batch(student_id), "/my-courses"),
        _step("class", "Join your first class", nav_repo.student_joined_a_class(student_id), "/schedule"),
        _step("task", "Submit your first task", nav_repo.student_submitted_a_task(student_id), "/tasks"),
    ]


def _trainer_steps() -> list[dict]:
    user_id = current_user().user_id
    return [
        _step("class", "Open your first class", nav_repo.trainer_opened_a_class(user_id), "/trainer"),
        _step("attendance", "Mark attendance", nav_repo.trainer_marked_attendance(user_id), "/trainer/attendance"),
        _step("grade", "Grade a submission", nav_repo.trainer_graded_a_submission(user_id), "/trainer/to-grade"),
    ]


def _branch_steps(branch_id: int | None) -> list[dict]:
    branch_ids = _branches(branch_id)
    return [
        _step("batch", "Create a batch", nav_repo.branch_has_batches(branch_ids), "/branch/batches"),
        _step("allocate", "Allocate students", nav_repo.branch_has_allocations(branch_ids), "/branch/operations"),
        _step("classes", "Create classes", nav_repo.branch_has_classes(branch_ids), "/branch/schedule"),
    ]


def _admin_steps() -> list[dict]:
    return [
        _step("staff", "Add a staff user", nav_repo.user_added_staff(current_user().user_id), "/admin/users"),
        _step("setup", "Review setup and health", nav_repo.setup_reviewed(), "/admin/integrations"),
    ]


def getting_started(workspace: str, branch_id: int | None = None) -> dict:
    """The first steps for a workspace and whether each is done. The Founder has none."""
    _require_workspace(workspace)
    steps = {"student": _student_steps, "trainer": _trainer_steps, "admin": _admin_steps}.get(workspace)
    if workspace == "branch":
        items = _branch_steps(branch_id)
    elif steps is not None:
        items = steps()
    else:
        items = []
    return {"workspace": workspace, "steps": items, "complete": bool(items) and all(s["done"] for s in items)}

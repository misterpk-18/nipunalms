"""What the shell shows around every screen: the count badges on navigation items (`GET /me/nav-counts`) and the "Getting
started" steps of each workspace (`GET /me/getting-started`).

Badges are cheap counts of what waits for the person, read from the slice that owns the record and limited to what they see.
A workspace the user does not hold is a 403; a branch outside their scope is a 404. The dismissed state of a Getting started
card lives in the browser, not here.
"""
from datetime import datetime, timedelta, timezone

from config.timezone import today_ist
from repositories import admin_students as admin_students_repo
from repositories import dashboards as dash_repo
from repositories import access_extensions as extensions_repo
from repositories import nav as nav_repo
from repositories import questions as questions_repo
from services import founder_inbox, scope, setup_health, student_work, trainer_todo
from services import exceptions as exceptions_service
from services import crm_sync
from services.auth import workspaces_for
from services.context import current_user
from services.errors import Forbidden

# Certificate register states that wait for a person to decide
CERTIFICATE_REVIEW = ("Eligibility Review", "Awaiting Approval")
# ... and the ones that wait for the Branch Manager to issue them (Completion & certificates counts all of these)
CERTIFICATE_TO_ACT_ON = CERTIFICATE_REVIEW + ("Approved for Issue",)
# A support reply counts as "near its deadline" this long before it is due
SUPPORT_WARNING = timedelta(hours=4)


def _require_workspace(workspace: str) -> None:
    if workspace not in workspaces_for(current_user().role_codes):
        raise Forbidden("You don't have access to this workspace")


require_workspace = _require_workspace


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
    from services import branch_work  # it reads this module's helpers

    branch_ids = _branches(branch_id)
    work = branch_work.my_work(branch_id)
    by_key = {row["key"]: row["count"] for row in work["rows"]}
    now = datetime.now(timezone.utc)
    enrolments = dash_repo.enrolment_counts(branch_ids)
    certificates = sum(dash_repo.certificates_in_status(CERTIFICATE_TO_ACT_ON, branch_ids).values())
    extensions = extensions_repo.counts(branch_ids)
    return {
        "waiting": enrolments.get("Allocation Pending", 0),
        "requests": (dash_repo.open_reschedule_requests(branch_ids) + dash_repo.escalated_support_requests(branch_ids)
                     + dash_repo.pending_extension_requests(branch_ids)),
        # Content & questions: uploads waiting for review plus questions waiting for approval
        "content_review": dash_repo.content_awaiting_review(branch_ids) + questions_repo.count_drafts(branch_ids),
        "marks": dash_repo.results_awaiting_publication(branch_ids),
        # Completion & certificates: reviews to decide plus certificates to approve or issue
        "completion": dash_repo.open_completion_reviews(branch_ids) + certificates,
        "issues": exceptions_service.counts(branch_ids)["total"],
        # Student support: replies near or past their deadline, new student replies, and access extensions the Branch Manager decides
        "support": nav_repo.support_needing_attention(branch_ids, now + SUPPORT_WARNING) + extensions["decide"] + extensions["recommend"],
        "attendance": nav_repo.pending_recoveries(branch_ids) + nav_repo.pending_corrections(branch_ids),
        "my_work": work["total"],
        "schedule": by_key.get("decisions", 0),
        "class_day": by_key.get("class_day", 0),
    }


def _admin_counts() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    counts = {
        "crm_sync": crm_sync.summary()["needs_attention"],
        "issues": exceptions_service.counts(None)["awaiting_owner"],
        "users": nav_repo.locked_users(now),
        "student_accounts": admin_students_repo.needs_attention_count(),
        "calendar": nav_repo.pending_closures(today_ist()),
        "setup": setup_health.broken_count(),
    }
    return {**counts, "home": sum(counts.values())}  # Home: everything the other items count


def _founder_counts() -> dict[str, int]:
    """The Founder's inbox as a whole and its three pages (curriculum, certificate decisions, access extensions)."""
    return founder_inbox.counts()


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
        _step("allocate", "Allocate students", nav_repo.branch_has_allocations(branch_ids), "/branch/waiting"),
        _step("classes", "Create classes", nav_repo.branch_has_classes(branch_ids), "/branch/schedule"),
    ]


def _admin_steps() -> list[dict]:
    return [
        _step("staff", "Add a staff user", nav_repo.user_added_staff(current_user().user_id), "/admin/users"),
        _step("setup", "Review setup and health", nav_repo.setup_reviewed(), "/admin/setup"),
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

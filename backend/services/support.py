"""Support requests: raising, routing to a named owner, the message thread, status, escalation and reopening.

Routing (by category, in the student's service branch): Academic goes to the trainer of the student's batch and then the
Academic Coordinator; Recording access and Other go to the Academic Coordinator; LMS, Account and Device access go to
Super Admin (shown as "LMS Support"). A missing owner falls back to the next role, so a request always has a named owner.
Escalation: a trainer-owned request moves up to the Academic Coordinator; anything else, and any request past its SLA
(app_settings.support_sla_hours), goes to the Branch Manager.
"""
import logging
from datetime import datetime, timezone

from config.database import db
from config.timezone import today_ist
from models import Enrolment, Student, SupportRequest
from models.support import SUPPORT_OPEN_STATUSES
from repositories import batches as batches_repo
from repositories import students as students_repo
from repositories import support as support_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import audit, scope
from services.context import ADMIN_ROLES, BRANCH_ROLES, CurrentUser, current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.notifications import notify

logger = logging.getLogger(__name__)

# Roles that may own a request, in the order tried for a category
ROUTING = {
    "Academic": ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN"),
    "Recording access": ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN"),
    "Other": ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN"),
    "LMS": ("SUPER_ADMIN", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER"),
    "Account": ("SUPER_ADMIN", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER"),
    "Device access": ("SUPER_ADMIN", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER"),
}
# Where each owner role works on requests
OWNER_LINKS = {
    "TRAINER": "/trainer/support",
    "ACADEMIC_COORDINATOR": "/academic/support",
    "BRANCH_MANAGER": "/branch/requests",
    "SUPER_ADMIN": "/academic/support",
}
# Roles tried, in this order, when assigning a request to a chosen colleague
ASSIGNABLE_ROLES = ("TRAINER", "ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN")
STAFF_STATUS_TARGETS = ("In Progress", "Waiting on Student", "Resolved", "Closed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_student(user: CurrentUser) -> bool:
    return user.student_id is not None and user.has_role("STUDENT")


# ---------------------------------------------------------------- scope

def _can_manage(request: SupportRequest, user: CurrentUser) -> bool:
    """Owner, a Branch Manager / Academic Coordinator of the request's branch, or an admin: may change status and assign."""
    return user.has_role(*ADMIN_ROLES) or request.owner_user_id == user.user_id or user.has_role(*BRANCH_ROLES, branch_id=request.branch_id)


def _can_view(request: SupportRequest, user: CurrentUser) -> bool:
    if _is_student(user):
        return request.student_id == user.student_id
    if _can_manage(request, user):
        return True
    return user.has_role("TRAINER") and request.raised_by_user_id == user.user_id


def get_request(support_request_id: int) -> SupportRequest:
    """The request, or 404 when it is outside the user's scope."""
    request = support_repo.get_request(support_request_id)
    if request is None or not _can_view(request, current_user()):
        raise NotFound("Support request not found")
    return request


def _get_managed(support_request_id: int) -> SupportRequest:
    request = get_request(support_request_id)
    if _is_student(current_user()):
        raise Forbidden("Only staff can do this")
    if not _can_manage(request, current_user()):
        raise Forbidden("Only the owner, the branch coordinators or an admin can change this request")
    return request


def _flush_and_reload(request: SupportRequest) -> None:
    """Write the change, then re-read the row: triggers fill in resolved_at, the SLA clock and the reopen count."""
    db.session.flush()
    db.session.refresh(request)


# ---------------------------------------------------------------- presentation

def to_detail(request: SupportRequest) -> dict:
    """The request with its thread; internal staff remarks are left out for a student."""
    student_user = users_repo.get_by_student_id(request.student_id)
    return request.to_dict(_now(), include_internal=not _is_student(current_user()),
                           student_user_id=student_user.user_id if student_user else None)


def to_summaries(requests: list[SupportRequest]) -> list[dict]:
    now = _now()
    return [r.to_summary(now) for r in requests]


# ---------------------------------------------------------------- listing

def list_requests(filters: dict, page: int, per_page: int) -> tuple[list[SupportRequest], dict]:
    user = current_user()
    branch_ids = scope.visible_branch_ids(user)
    stmt = support_repo.list_stmt(
        filters,
        student_id=user.student_id if _is_student(user) else None,
        branch_ids=branch_ids,
        user_id=user.user_id,
        all_branches=branch_ids is None and not _is_student(user),
        trainer=user.has_role("TRAINER"),
    )
    return paginate(stmt, page, per_page)


def assigned_students() -> list[dict]:
    """The trainer's students (active seats in their batches) with any open support request as the flag."""
    rows = support_repo.assigned_students(scope.trainer_batch_ids())
    open_requests = support_repo.open_requests_by_student([student.student_id for student, _, _ in rows])
    now = _now()
    result = []
    for student, batch, enrolment in rows:
        flags = open_requests.get(student.student_id, [])
        result.append({
            "student": student.to_summary(),
            "batch": batch.to_summary(),
            "enrolment": enrolment.to_summary(),
            "open_requests": [r.to_summary(now) for r in flags],
            "flag": f"Open — {flags[0].category}" if flags else "None",
        })
    return result


# ---------------------------------------------------------------- raising

def _lead_trainer(student: Student, enrolment: Enrolment | None, branch_id: int) -> int | None:
    """The current trainer (Lead first) of the batch the enrolment - or the student's first seated enrolment - sits in."""
    enrolments = [enrolment] if enrolment else students_repo.enrolments_of_student(student.student_id)
    for candidate in enrolments:
        allocation = batches_repo.active_allocation(candidate.enrolment_id)
        if allocation is None or allocation.batch.branch_id != branch_id:
            continue
        for user_id in support_repo.trainers_of_batch(allocation.batch, today_ist()):
            trainer = users_repo.get_by_id(user_id)
            if trainer is not None and trainer.is_active:
                return user_id
    return None


def _owner_holding(role: str, branch_id: int) -> int | None:
    holders = users_repo.user_ids_with_role(role, None if role == "SUPER_ADMIN" else branch_id)
    return min(holders) if holders else None


def _route(category: str, student: Student, enrolment: Enrolment | None, branch_id: int) -> tuple[int, str]:
    """(owner user id, owner role) for the category at the branch."""
    for role in ROUTING[category]:
        user_id = _lead_trainer(student, enrolment, branch_id) if role == "TRAINER" else _owner_holding(role, branch_id)
        if user_id is not None:
            return user_id, role
    raise BusinessRule("No owner is configured for this kind of request at the branch. Ask a Super Admin to add a coordinator.")


def _student_for(user: CurrentUser, student_id: int | None) -> tuple[Student, str]:
    """Who the request is about and how it was raised: a student raises for themselves; staff flag on a student's behalf."""
    if _is_student(user):
        if student_id not in (None, user.student_id):
            raise ValidationError("You can only raise requests for yourself", {"student_id": ["Not allowed"]})
        return students_repo.get_student(user.student_id), "Student"
    if student_id is None:
        raise ValidationError("Choose the student", {"student_id": ["Required"]})
    student = students_repo.get_student(student_id)
    if student is None:
        raise NotFound("Student not found")
    if user.has_role(*ADMIN_ROLES, *BRANCH_ROLES):
        scope.assert_can_view_student(student, user)
    else:
        taught = batches_repo.enrolment_ids_in_batches(scope.trainer_batch_ids(user))
        if not any(e.enrolment_id in taught for e in students_repo.enrolments_of_student(student_id)):
            raise NotFound("Student not found")
    return student, "Staff flag"


def raise_request(data: dict) -> SupportRequest:
    user = current_user()
    student, raised_via = _student_for(user, data.get("student_id"))

    enrolment = None
    if data.get("enrolment_id") is not None:
        enrolment = students_repo.get_enrolment(data["enrolment_id"])
        if enrolment is None or enrolment.student_id != student.student_id:
            raise ValidationError("Not one of this student's enrolments", {"enrolment_id": ["Choose one of the student's courses"]})
    branch_id = enrolment.service_branch_id if enrolment else student.service_branch_id
    owner_id, owner_role = _route(data["category"], student, enrolment, branch_id)

    details = data["details"]
    request = SupportRequest(
        student_id=student.student_id, enrolment_id=enrolment.enrolment_id if enrolment else None, branch_id=branch_id,
        category=data["category"], subject=data.get("subject") or details.splitlines()[0][:120], priority=data.get("priority", "Normal"),
        raised_by_user_id=user.user_id, raised_via=raised_via, owner_user_id=owner_id, owner_role=owner_role,
    )
    db.session.add(request)
    db.session.flush()
    support_repo.add_message(request, user.user_id, details)

    _notify_owner(request, f"New support request {request.request_code}", f"{student.full_name}: {request.subject}", "raised")
    if raised_via == "Staff flag":
        _notify_student(request, f"{user.full_name} raised support request {request.request_code} for you", request.subject, "raised")
    return request


# ---------------------------------------------------------------- thread

def add_message(support_request_id: int, body: str, *, internal: bool = False) -> SupportRequest:
    user = current_user()
    request = get_request(support_request_id)
    if request.status in ("Resolved", "Closed"):
        raise BusinessRule(f"This request is {request.status.lower()}. Reopen it to add a message.")
    if internal and _is_student(user):
        raise Forbidden("Students cannot add internal remarks")

    if _is_student(user):
        if request.status == "Waiting on Student":
            request.status = "In Progress"
    elif request.status == "Open" and not internal:
        request.status = "In Progress"
    message = support_repo.add_message(request, user.user_id, body, is_internal=internal)

    if _is_student(user):
        _notify_owner(request, f"Reply on {request.request_code}", f"{request.student.full_name}: {body[:120]}", f"message:{message.support_message_id}")
    elif not internal:
        _notify_student(request, f"New reply on {request.request_code}", body[:160], f"message:{message.support_message_id}")
    return request


# ---------------------------------------------------------------- status

def change_status(support_request_id: int, status: str, note: str | None) -> SupportRequest:
    request = _get_managed(support_request_id)
    if status == "Resolved" and not note:
        raise ValidationError("Say how it was resolved", {"note": ["Required to resolve a request"]})
    old_status = request.status
    request.status = status
    if status == "Resolved":
        request.resolution_note = note
    _flush_and_reload(request)

    text = f"Status: {old_status} → {status}" + (f". {note}" if note else "")
    message = support_repo.add_message(request, current_user().user_id, text, kind="Status")
    if status in ("Resolved", "Closed"):
        audit.record(f"SUPPORT_{status.upper()}", "support_request", request.request_code, old={"status": old_status},
                     new={"status": status, "resolution_note": request.resolution_note}, branch_id=request.branch_id)
    _notify_student(request, f"Support request {request.request_code} {status.lower()}", note or request.subject,
                    f"status:{message.support_message_id}")
    return request


def close(support_request_id: int) -> SupportRequest:
    """The student confirms a resolved request is done."""
    user = current_user()
    request = get_request(support_request_id)
    if not _is_student(user):
        raise Forbidden("Only the student closes their own request; staff use the status action")
    if request.status != "Resolved":
        raise BusinessRule("Only a resolved request can be closed")
    request.status = "Closed"
    _flush_and_reload(request)
    support_repo.add_message(request, user.user_id, "Status: Resolved → Closed. Confirmed by the student.", kind="Status")
    return request


def reopen(support_request_id: int, reason: str) -> SupportRequest:
    user = current_user()
    request = get_request(support_request_id)
    if request.status not in ("Resolved", "Closed"):
        raise BusinessRule("Only a resolved or closed request can be reopened")
    if not _is_student(user) and not _can_manage(request, user):
        raise Forbidden("Only the owner, the branch coordinators or an admin can reopen this request")
    old_status = request.status
    request.status = "Open"
    _flush_and_reload(request)
    message = support_repo.add_message(request, user.user_id, reason, kind="Reopened")
    audit.record("SUPPORT_REOPENED", "support_request", request.request_code, old={"status": old_status}, new={"status": "Open"},
                 reason=reason, branch_id=request.branch_id)
    _notify_owner(request, f"Support request {request.request_code} reopened", reason[:160], f"reopened:{message.support_message_id}")
    return request


# ---------------------------------------------------------------- escalation and assignment

def escalate(support_request_id: int, reason: str) -> SupportRequest:
    """A trainer-owned request goes up to the Academic Coordinator; anything else to the Branch Manager."""
    request = get_request(support_request_id)
    if _is_student(current_user()):
        raise Forbidden("Only staff can escalate a request")
    return _escalate(request, reason, actor_user_id=current_user().user_id)


def _escalate(request: SupportRequest, reason: str, *, actor_user_id: int | None) -> SupportRequest:
    if request.status not in SUPPORT_OPEN_STATUSES:
        raise BusinessRule("Only an open request can be escalated")
    if request.escalation_level == "Branch Manager":
        raise BusinessRule("This request is already escalated to the Branch Manager")

    old = {"owner_user_id": request.owner_user_id, "escalation_level": request.escalation_level}
    if request.owner_role == "TRAINER" and actor_user_id is not None:
        coordinator = _owner_holding("ACADEMIC_COORDINATOR", request.branch_id)
        if coordinator is None:
            raise BusinessRule("There is no Academic Coordinator at this branch to escalate to")
        request.owner_user_id, request.owner_role, request.escalation_level = coordinator, "ACADEMIC_COORDINATOR", "Academic Coordinator"
    else:
        request.escalation_level = "Branch Manager"
    request.escalated_at, request.escalation_reason = _now(), reason
    _flush_and_reload(request)

    support_repo.add_message(request, actor_user_id, f"Escalated to the {request.escalation_level}. {reason}", kind="Escalation")
    audit.record("SUPPORT_ESCALATED", "support_request", request.request_code, old=old,
                 new={"owner_user_id": request.owner_user_id, "escalation_level": request.escalation_level}, reason=reason,
                 branch_id=request.branch_id, actor_user_id=actor_user_id)
    key = f"escalated:{request.escalation_level}"
    if request.escalation_level == "Branch Manager":
        notify(category="Support", title=f"Escalated: {request.request_code} needs the Branch Manager",
               body=f"{request.subject}. {reason}", link="/branch/requests", event_key=f"support:{request.support_request_id}:{key}",
               role_code="BRANCH_MANAGER", branch_id=request.branch_id, action_required=True)
    else:
        _notify_owner(request, f"Escalated to you: {request.request_code}", f"{request.subject}. {reason}", key)
    return request


def escalate_overdue() -> int:
    """Job: escalate every open request past its SLA to the Branch Manager. Returns how many were escalated."""
    count = 0
    for request in support_repo.overdue_requests(_now()):
        _escalate(request, f"SLA breached: no resolution by {request.sla_due_at.isoformat()}", actor_user_id=None)
        count += 1
    return count


def assign(support_request_id: int, owner_user_id: int) -> SupportRequest:
    """Give the request to a named colleague who works at the request's branch (or a Super Admin)."""
    request = _get_managed(support_request_id)
    if request.status not in SUPPORT_OPEN_STATUSES:
        raise BusinessRule("Only an open request can be reassigned")
    role = next((r for r in ASSIGNABLE_ROLES if owner_user_id in users_repo.user_ids_with_role(r, request.branch_id)), None)
    if role is None:
        raise ValidationError("That person does not work at this branch", {"owner_user_id": ["Choose a trainer, coordinator or manager of the branch"]})

    old = {"owner_user_id": request.owner_user_id, "owner_role": request.owner_role}
    request.owner_user_id, request.owner_role = owner_user_id, role
    _flush_and_reload(request)
    message = support_repo.add_message(request, current_user().user_id, f"Assigned to {request.owner.full_name} ({request.owner_label()})",
                                       kind="Assignment")
    audit.record("SUPPORT_ASSIGNED", "support_request", request.request_code, old=old,
                 new={"owner_user_id": owner_user_id, "owner_role": role}, branch_id=request.branch_id)
    _notify_owner(request, f"Support request {request.request_code} assigned to you", request.subject, f"assigned:{message.support_message_id}")
    return request


# ---------------------------------------------------------------- notifications

def _notify_owner(request: SupportRequest, title: str, body: str, event: str) -> None:
    notify(category="Support", title=title, body=body, link=OWNER_LINKS[request.owner_role],
           event_key=f"support:{request.support_request_id}:{event}", recipient_user_ids=[request.owner_user_id],
           branch_id=request.branch_id, action_required=True)


def _notify_student(request: SupportRequest, title: str, body: str, event: str) -> None:
    student_user = users_repo.get_by_student_id(request.student_id)
    if student_user is None:
        return
    notify(category="Support", title=title, body=body, link="/support", event_key=f"support:{request.support_request_id}:{event}",
           recipient_user_ids=[student_user.user_id], branch_id=request.branch_id)

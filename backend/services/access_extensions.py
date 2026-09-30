"""Access extension requests: one extra year for recordings and / or materials (Modules 17 §8 and 18 §5).

A student asks with a reason. The Academic Coordinator or Branch Manager of the enrolment's service branch (Super Admin
as cover) approves the routine extension, which always ends on the second anniversary of the Joining Date; repeated
requests do not stack years. A request made after the second anniversary is a further exception only a Founder / CEO or
Super Admin may grant, with the new expiry stated. The student is told; every decision is audited.
"""
from datetime import datetime, timezone

from config.database import db
from config.timezone import today_ist
from models import AccessExtensionRequest
from repositories import access_extensions as extensions_repo
from repositories import students as students_repo
from repositories import users as users_repo
from repositories.common import paginate
from services import access, audit, scope, student_library
from services.context import current_user
from services.errors import BusinessRule, Conflict, Forbidden, NotFound, ValidationError
from services.notifications import notify

DECIDERS = ("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", "SUPER_ADMIN")
EXCEPTION_DECIDERS = ("SUPER_ADMIN", "FOUNDER_CEO")


def _kinds(scope_value: str) -> tuple[str, ...]:
    return access.KINDS if scope_value == "Both" else (scope_value,)


def create_request(enrolment_id: int, scope_value: str, reason: str) -> AccessExtensionRequest:
    """The student asks for the routine extra year (or, after the second anniversary, an exception)."""
    ctx = student_library.student_context()
    enrolment = ctx.enrolment(enrolment_id)
    if enrolment is None:
        raise NotFound("Enrolment not found")
    window = ctx.windows[enrolment_id]
    if window.joining_date is None:
        raise BusinessRule("Access dates start from your confirmed Joining Date. You can ask for an extension once you have joined a class.")
    for kind in _kinds(scope_value):
        if window.extended(kind):
            raise BusinessRule(f"Your {kind.lower()} access was already extended to {window.expiry[kind]:%d %b %Y}. "
                               "Repeated requests do not add further years.")
    pending = extensions_repo.pending_for_enrolment(enrolment_id)
    if any(set(_kinds(r.scope)) & set(_kinds(scope_value)) for r in pending):
        raise Conflict("A request for this enrolment is already waiting for a decision")

    request = AccessExtensionRequest(
        enrolment_id=enrolment_id, student_id=ctx.student_id, branch_id=enrolment.service_branch_id, scope=scope_value, reason=reason,
        needs_exception=ctx.today > window.second_expiry, original_expiry=window.first_expiry)
    db.session.add(request)
    db.session.flush()
    db.session.refresh(request)
    audit.record("ACCESS_EXTENSION_REQUESTED", "access_extension_request", request.request_code,
                 new={"enrolment": enrolment.enrolment_code, "scope": scope_value, "needs_exception": request.needs_exception},
                 reason=reason, branch_id=request.branch_id)
    if request.needs_exception:
        recipients = dict(role_code="SUPER_ADMIN", branch_id=request.branch_id)
        headline = "needs a Founder / CEO or Super Admin exception"
    else:
        recipients = dict(role_code="ACADEMIC_COORDINATOR", branch_id=request.branch_id)
        headline = "is waiting for approval"
    notify(category="Access", title=f"{request.request_code}: access extension request {headline}",
           body=f"{request.student.full_name} · {enrolment.course.title} · {scope_value}", link="/branch/requests",
           event_key=f"ext-requested-{request.request_code}", action_required=True, **recipients)
    if not request.needs_exception:
        notify(category="Access", title=f"{request.request_code}: access extension request is waiting for approval",
               body=f"{request.student.full_name} · {enrolment.course.title} · {scope_value}", link="/branch/requests",
               role_code="BRANCH_MANAGER", branch_id=request.branch_id, event_key=f"ext-requested-{request.request_code}", action_required=True)
    return request


def list_requests(filters: dict, page: int, per_page: int) -> tuple[list[AccessExtensionRequest], dict]:
    """A student's own requests, or the requests of the staff member's branches (all branches for Super Admin / Founder)."""
    user = current_user()
    if user.student_id is not None:
        stmt = extensions_repo.list_stmt(filters, None, user.student_id)
    elif user.has_role(*DECIDERS, "FOUNDER_CEO"):
        stmt = extensions_repo.list_stmt(filters, scope.visible_branch_ids(user), None)
    else:
        raise Forbidden("You don't have access to access-extension requests")
    return paginate(stmt, page, per_page)


def get_request(request_id: int) -> AccessExtensionRequest:
    request = extensions_repo.get(request_id)
    user = current_user()
    if request is not None:
        branch_ids = scope.visible_branch_ids(user)
        if request.student_id == user.student_id or (user.has_role(*DECIDERS, "FOUNDER_CEO") and (branch_ids is None or request.branch_id in branch_ids)):
            return request
    raise NotFound("Access extension request not found")


def decide(request_id: int, decision: str, note: str | None, new_expiry=None) -> AccessExtensionRequest:
    """Approve or reject. Routine approval grants the second anniversary; an exception needs the new expiry stated."""
    request = get_request(request_id)
    user = current_user()
    if user.student_id is not None:
        raise Forbidden("Only staff decide access extensions")
    if request.status != "Pending":
        raise BusinessRule(f"{request.request_code} was already {request.status.lower()}")
    if request.needs_exception:
        if not user.has_role(*EXCEPTION_DECIDERS):
            raise Forbidden("Requests after the second anniversary need a Founder / CEO or Super Admin exception")
    elif not (user.has_role("SUPER_ADMIN") or user.has_role("ACADEMIC_COORDINATOR", "BRANCH_MANAGER", branch_id=request.branch_id)):
        raise Forbidden("Only the Academic Coordinator or Branch Manager of the service branch decides this")

    old = {"status": "Pending", "expiry": {k: str(v) for k, v in _current_expiry(request).items()}}
    if decision == "reject":
        if not (note or "").strip():
            raise ValidationError("Give the student a reason", {"note": ["Required when rejecting"]})
        request.status = "Rejected"
        approved = None
    else:
        approved = _granted_expiry(request, new_expiry)
        request.status = "Approved"
        request.approved_expiry = approved
    request.decided_by = user.user_id
    request.decided_at = datetime.now(timezone.utc)
    request.decision_note = note
    db.session.flush()
    db.session.refresh(request)
    audit.record("ACCESS_EXTENSION_DECIDED", "access_extension_request", request.request_code, old=old,
                 new={"status": request.status, "approved_expiry": str(approved) if approved else None, "scope": request.scope},
                 reason=note, branch_id=request.branch_id)

    student_user = users_repo.get_by_student_id(request.student_id)
    if student_user is not None:
        body = (f"Your {request.scope.lower()} access now runs until {approved:%d %b %Y}." if approved
                else f"Your request was not approved: {note}")
        notify(category="Access", title=f"Access extension {request.request_code} {request.status.lower()}", body=body,
               link="/recordings", recipient_user_ids=[student_user.user_id], branch_id=request.branch_id,
               event_key=f"ext-decided-{request.request_code}")
    return request


def _current_expiry(request: AccessExtensionRequest) -> dict:
    enrolment = students_repo.get_enrolment(request.enrolment_id)
    window = access.window_for(enrolment)
    return {kind: window.expiry[kind] for kind in _kinds(request.scope)}


def _granted_expiry(request: AccessExtensionRequest, new_expiry):
    """The expiry an approval grants: the second anniversary, or for an exception the date the approver states."""
    enrolment = students_repo.get_enrolment(request.enrolment_id)
    window = access.window_for(enrolment)
    if window.second_expiry is None:
        raise BusinessRule("The enrolment has no Joining Date")
    if request.needs_exception:
        if new_expiry is None:
            raise ValidationError("State the new expiry", {"new_expiry": ["Required for an exception"]})
        if new_expiry <= today_ist():
            raise ValidationError("State the new expiry", {"new_expiry": ["Must be a future date"]})
        return new_expiry
    return window.second_expiry

"""Access extension requests: one extra year for recordings and / or materials (Modules 17 §8 and 18 §5).

A student asks with a reason. The Branch Manager of the enrolment's service branch (Super Admin
as cover) approves the routine extension, which always ends on the second anniversary of the Joining Date; repeated
requests do not stack years. A request made after the second anniversary is a further exception only a Founder / CEO or
Super Admin may grant, with the new expiry stated. The Branch Manager of the branch does not decide it but adds a recommendation
(UX phase U15, db/113); saving it routes the request to the Founder's inbox. The student is told; every decision is audited.
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

DECIDERS = ("BRANCH_MANAGER", "SUPER_ADMIN")
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
    link = "/branch/support?tab=extensions"
    if request.needs_exception:
        # Beyond the Branch Manager's limit: the Branch Manager adds a recommendation, which sends it on to the Founder
        notify(category="Access", title=f"{request.request_code}: access extension request needs your recommendation",
               body=f"{request.student.full_name} · {enrolment.course.title} · {scope_value}. It is beyond your limit: add a recommendation "
                    "and it goes to the Founder / CEO.", link=link, role_code="BRANCH_MANAGER", branch_id=request.branch_id,
               event_key=f"ext-requested-{request.request_code}", action_required=True)
    else:
        notify(category="Access", title=f"{request.request_code}: access extension request is waiting for approval",
               body=f"{request.student.full_name} · {enrolment.course.title} · {scope_value}", link=link,
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
    elif not (user.has_role("SUPER_ADMIN") or user.has_role("BRANCH_MANAGER", branch_id=request.branch_id)):
        raise Forbidden("Only the Branch Manager of the service branch decides this")

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
               link="/materials", recipient_user_ids=[student_user.user_id], branch_id=request.branch_id,
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


# ---------------------------------------------------------------- recommendation (beyond the Branch Manager's limit)

def recommend(request_id: int, decision: str, note: str, expiry=None) -> AccessExtensionRequest:
    """The Branch Manager's view on a request made after the second anniversary: approve or reject, why, and (for approve) the
    end date they suggest. It does not decide the request; saving it sends the request to the Founder's inbox. It may be revised
    until the request is decided."""
    request = get_request(request_id)
    user = current_user()
    if not user.has_role("BRANCH_MANAGER", branch_id=request.branch_id):
        raise Forbidden("Only the Branch Manager of the service branch recommends on this request")
    if not request.needs_exception:
        raise BusinessRule("This request is within your limit: approve or reject it yourself")
    if request.status != "Pending":
        raise BusinessRule(f"{request.request_code} was already {request.status.lower()}")
    if not (note or "").strip():
        raise ValidationError("Say why", {"note": ["Required"]})
    if expiry is not None:
        if decision != "approve":
            raise ValidationError("An end date goes with an approval", {"expiry": ["Only when you recommend approving"]})
        if expiry <= max(today_ist(), request.original_expiry):
            raise ValidationError("Suggest a later end date", {"expiry": ["Must be after today and after the current end date"]})
    first_time = request.recommended_at is None
    old = {"recommended_decision": request.recommended_decision, "recommended_expiry": str(request.recommended_expiry) if request.recommended_expiry else None}
    request.recommended_decision, request.recommendation, request.recommended_expiry = decision, note.strip(), expiry
    request.recommended_by, request.recommended_at = user.user_id, datetime.now(timezone.utc)
    db.session.flush()
    db.session.refresh(request)
    audit.record("ACCESS_EXTENSION_RECOMMENDED", "access_extension_request", request.request_code, old=old,
                 new={"recommended_decision": decision, "recommended_expiry": str(expiry) if expiry else None}, reason=note.strip(),
                 branch_id=request.branch_id)
    suggestion = f", suggesting access until {expiry:%d %b %Y}" if expiry else ""
    notify(category="Access", title=f"{request.request_code}: access extension waiting for your decision",
           body=f"{request.student.full_name} · {request.enrolment.course.title}. The Branch Manager recommends to {decision}{suggestion}: {note.strip()[:160]}",
           link="/founder", role_code="FOUNDER_CEO", branch_id=None,
           event_key=f"ext-recommended-{request.request_code}-{int(request.recommended_at.timestamp())}", action_required=True)
    if not first_time:
        audit.record("ACCESS_EXTENSION_RECOMMENDATION_REVISED", "access_extension_request", request.request_code, branch_id=request.branch_id)
    return request


def awaiting_founder(limit: int | None = None) -> list[AccessExtensionRequest]:
    """The requests in the Founder's inbox: made after the second anniversary, still pending, with a Branch Manager's
    recommendation (what U16's GET /founder/inbox reads)."""
    return extensions_repo.with_founder(limit)


def present(request: AccessExtensionRequest) -> dict:
    """The request as a screen needs it: what it would change, who may act, and (for staff) the recommendation."""
    user = current_user()
    data = request.to_dict()
    window = access.window_for(students_repo.get_enrolment(request.enrolment_id))
    kinds = _kinds(request.scope)
    current = max((window.expiry[k] for k in kinds), default=None)
    is_student = user.student_id is not None
    routine = not request.needs_exception
    data.update({
        "limit": "beyond" if request.needs_exception else "within",
        "current_end_date": current if request.status != "Approved" else request.original_expiry,
        # What approval grants without the approver stating a date: the second anniversary of the Joining Date
        "new_end_date": window.second_expiry if routine and request.status == "Pending" else request.approved_expiry,
        "can_decide": request.status == "Pending" and not is_student and (
            user.has_role(*EXCEPTION_DECIDERS) if request.needs_exception
            else user.has_role("SUPER_ADMIN") or user.has_role("BRANCH_MANAGER", branch_id=request.branch_id)),
        "can_recommend": request.status == "Pending" and request.needs_exception and not is_student
                         and user.has_role("BRANCH_MANAGER", branch_id=request.branch_id),
    })
    if not is_student:
        data["recommendation"] = request.recommendation_dict()
        data["with_founder"] = request.status == "Pending" and request.needs_exception and request.recommended_at is not None
    return data

"""The Founder's inbox (UX phase U16): everything waiting for the Founder / CEO in one list, oldest first.

Curriculum versions to approve or activate, certificate change requests (correction, revocation, reinstatement), certificate
release exceptions for an unpaid fee, access extensions beyond the Branch Manager's limit that carry the Branch Manager's
recommendation, the monthly AI budget while nobody has approved it, and the Branch Managers' own requests (a Branch Manager's
request cannot be reviewed at the branch, so it comes here). Only what the signed-in person can decide appears. Each item carries
the record as its own screen shows it (`detail`), so the side panel needs no second read. The same builders feed the nav badges.

A Super Admin opens the same list: they hold the Founder's powers too, and the same independence rules apply to them.

One inbox for every role that decides (role separation 7.8): the Founder and Super Admin see every kind; a Branch Manager sees only the
certificate change requests of their branch that they may decide (the section in Completion). Certificate requests and fee exceptions
that the signed-in person could decide but may not because they raised them are listed too, with `can_decide: false`, so the screen can
say why (nobody decides their own request); the counts and nav badges include only what the person can decide.
"""
from datetime import datetime, timezone

from repositories import catalog as catalog_repo
from repositories import dashboards as dash_repo
from repositories import founder_inbox as inbox_repo
from repositories import students as students_repo
from repositories import users as users_repo
from services import access_extensions, ai_budget, approvals, attendance, certificate_requests
from services.context import current_user

# The pages of the Founder workspace ("other" is the home page itself: the AI budget and the Branch Managers' own requests)
GROUPS = ("curriculum", "certificates", "access", "other")
KINDS = ("curriculum", "certificate", "fee_exception", "access_extension", "ai_budget", "bm_reschedule", "bm_correction")
# The Founder workspace page that lists each kind
PAGES = {"curriculum": "/founder/curriculum", "certificate": "/founder/certificates", "fee_exception": "/founder/certificates",
         "access_extension": "/founder/access", "ai_budget": "/founder", "bm_reschedule": "/founder", "bm_correction": "/founder"}
CHANGE_TITLES = {"Correction": "Correction to certificate", "Revocation": "Revocation of certificate", "Reinstatement": "Reinstatement of certificate"}


def _item(kind: str, ident, title: str, since, action: str, detail: dict, *, where: str | None = None, from_bm: bool = False,
          can_decide: bool = True) -> dict:
    return {"key": f"{kind}-{ident}", "kind": kind, "id": ident, "title": title, "where": where, "since": since, "action": action,
            "to": PAGES[kind], "from_branch_manager": from_bm, "can_decide": can_decide, "detail": detail}


def _curriculum_items() -> list[dict]:
    items = []
    me = current_user().user_id
    for version in inbox_repo.curriculum_waiting():
        course = catalog_repo.get_course(version.course_id)
        component = catalog_repo.get_component(version.component_id) if version.component_id else None
        submitted = catalog_repo.last_event(version.curriculum_version_id, "Submitted")
        if version.status == "Under Review" and submitted is not None and submitted.actor_user_id == me:
            continue  # someone else approves what you submitted
        name = course.title + (f" ({component.track_name})" if component else "")
        waiting = version.status == "Under Review"
        detail = {"curriculum_version_id": version.curriculum_version_id, "version_label": version.version_label, "status": version.status,
                  "course": course.to_summary(), "component": component.to_dict() if component else None,
                  "submitted_by": submitted.actor.to_summary() if submitted and submitted.actor else None,
                  "submitted_at": submitted.created_at if submitted else None, "approved_at": version.approved_at}
        since = (submitted.created_at if submitted else None) if waiting else version.approved_at
        items.append(_item("curriculum", version.curriculum_version_id,
                           f"{'Approve' if waiting else 'Activate'} curriculum {version.version_label} for {name}", since,
                           "Review" if waiting else "Activate", detail))
    return items


def _certificate_items() -> list[dict]:
    items = []
    user = current_user()
    for request in inbox_repo.pending_certificate_requests():
        certificate = request.certificate
        actions = certificate_requests.actions_for_request(request)
        # Listed when the role decides or asks for this kind at this branch; what a Branch Manager asked for is decided by an admin,
        # so a Branch Manager sees it as waiting (`can_decide: false`), the Founder and Super Admin decide it
        could = user.has_role(*certificate_requests.DECIDERS[request.kind], *certificate_requests.REQUESTERS[request.kind],
                              branch_id=certificate.branch_id)
        if "decide" not in actions and not could:
            continue
        items.append(_item("certificate", request.request_id,
                           f"{CHANGE_TITLES[request.kind]} {certificate.certificate_number} ({certificate.holder_name})", request.requested_at,
                           "Review", request.to_dict(actions), where=certificate.branch.branch_name,
                           from_bm=approvals.requester_needs_admin(request.requested_by), can_decide="decide" in actions))
    for exception in inbox_repo.pending_fee_exceptions():
        actions = certificate_requests.actions_for_exception(exception)
        could = user.has_role(*certificate_requests.EXCEPTION_DECIDERS, *certificate_requests.EXCEPTION_REQUESTERS,
                              branch_id=exception.admission.service_branch_id)
        if "decide" not in actions and not could:
            continue
        items.append(_item("fee_exception", exception.exception_id,
                           f"Release certificates with a fee unpaid: {exception.admission.admission_code} (₹{exception.outstanding_amount:,.0f} outstanding)",
                           exception.requested_at, "Review", {**exception.to_dict(), "actions": actions},
                           where=exception.admission.service_branch.branch_name, from_bm=approvals.requester_needs_admin(exception.requested_by),
                           can_decide="decide" in actions))
    return items


def _access_items() -> list[dict]:
    return [_item("access_extension", r.request_id, f"Access beyond two years for {r.student.full_name}", r.recommended_at, "Review",
                  access_extensions.present(r), where=r.branch.branch_name) for r in access_extensions.awaiting_founder()]


def _ai_items() -> list[dict]:
    state = ai_budget.state()
    if state["state"] == "Configured":
        return []
    return [_item("ai_budget", "monthly", "Approve the monthly AI budget", None, "Set budget", state)]


def _branch_manager_items() -> list[dict]:
    managers = users_repo.user_ids_with_role("BRANCH_MANAGER", None)
    items = []
    for request in inbox_repo.reschedule_requests_by(managers):
        if not approvals.can_decide(request.requested_by):
            continue
        session = request.session
        items.append(_item("bm_reschedule", request.request_id, f"{request.requester.full_name} asks to move {session.title}", request.created_at,
                           "Review", {**request.to_dict(), "can_decide": True}, where=session.batch.branch.branch_name, from_bm=True))
    for correction in inbox_repo.corrections_by(managers):
        if not attendance.can_decide_correction(correction):
            continue
        items.append(_item("bm_correction", correction.correction_id,
                           f"{correction.requester.full_name} asks to change attendance for {students_repo.get_student(correction.enrolment.student_id).full_name}",
                           correction.requested_at, "Review", {**correction.to_dict(), "can_decide": True},
                           where=correction.enrolment.service_branch.branch_name, from_bm=True))
    return items


def _sort_key(item: dict):
    since = item["since"]
    return (since is None, since or datetime.max.replace(tzinfo=timezone.utc))


def inbox(group: str | None = None) -> dict:
    """Items oldest first (the AI budget, which has no date, last), the count per kind, the scheduled activations and whether the
    CRM has sent its finance figures yet. `group` narrows it to one page of the workspace."""
    builders = {"curriculum": (_curriculum_items,), "certificates": (_certificate_items,), "access": (_access_items,),
                "other": (_ai_items, _branch_manager_items)}
    if current_user().role_code == "BRANCH_MANAGER":
        builders = {"certificates": builders["certificates"]}  # the Branch Manager's section in Completion: certificate requests only
    items = [item for name, build in builders.items() if group in (None, name) for fn in build for item in fn()]
    items.sort(key=_sort_key)
    decidable = [i for i in items if i["can_decide"]]
    scheduled = []
    if "curriculum" in builders and group in (None, "curriculum"):
        scheduled = [{"curriculum_version_id": v.curriculum_version_id, "version_label": v.version_label, "activate_on": v.activate_on,
                      "course": catalog_repo.get_course(v.course_id).to_summary()} for v in inbox_repo.curriculum_scheduled()]
    return {"as_of": datetime.now(timezone.utc), "total": len(decidable), "counts": {k: sum(1 for i in decidable if i["kind"] == k) for k in KINDS},
            "items": items, "scheduled": scheduled, "crm_connected": crm_connected()}


def crm_connected() -> bool:
    """True once the CRM has sent finance figures for at least one branch (what the CRM tiles show)."""
    return bool(dash_repo.finance_snapshots(None))


def counts() -> dict[str, int]:
    """The nav badges: the whole inbox, and the three pages."""
    everything = inbox()
    by_kind = everything["counts"]
    return {"inbox": everything["total"], "curriculum": by_kind["curriculum"], "certificates": by_kind["certificate"] + by_kind["fee_exception"],
            "access": by_kind["access_extension"]}

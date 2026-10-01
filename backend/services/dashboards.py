"""Dashboard summaries: one read per workspace (Academic, Branch, Super Admin, Founder).

Nothing here decides anything. Every figure is a count read from the slice that owns the record (repositories/dashboards,
the exception queue, the integrations register, CRM sync, Ask Nipuna status), restricted to the branches the user sees.

CRM-authoritative figures (verified collections and paid Admissions against a target, overdue amounts, overdue payment
verifications and follow-ups) come from the CRM's per-branch `BranchFinanceSnapshot` (db 096), summed over the branches
in view. A figure is "Configured" when every branch in view has a snapshot, "Partial Data" (naming the missing branches)
when only some do, and `{"state": "Not Configured"}` when none do: never 0. `stale` flags a snapshot older than the CRM's
15-minute push allows.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from repositories import branches as branches_repo
from repositories import dashboards as dash_repo
from repositories import settings as settings_repo
from services import ask_nipuna, crm_sync, scope
from services import exceptions as exceptions_service
from services import integrations as integrations_service

# Enrolment statuses that are waiting for a seat (Curriculum Mapping Pending is included, as in the prototype)
AWAITING_ALLOCATION = ("Curriculum Mapping Pending", "Allocation Pending")
# Certificate register states that wait for a person to decide
CERTIFICATE_REVIEW = ("Eligibility Review", "Awaiting Approval")
AI_CEILING_SETTING = "ai_monthly_ceiling_inr"
# The CRM pushes a snapshot every 15 minutes; older than this, the figure is shown as stale
FINANCE_STALE_AFTER = timedelta(minutes=60)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _branches(branch_id: int | None) -> set[int] | None:
    """The branches to aggregate: the requested one (404 when outside the user's scope), else everything the user sees."""
    if branch_id is not None:
        scope.require_branch(branch_id)
        return {branch_id}
    return scope.visible_branch_ids()


def _scope_block(branch_ids: set[int] | None) -> dict:
    branches = branches_repo.list_active(branch_ids)
    return {"branches": [b.to_summary() for b in branches], "all_branches": branch_ids is None,
            "label": " · ".join(b.branch_name for b in branches) if branch_ids is not None else "All branches"}


def not_configured(reason: str) -> dict:
    """A CRM-authoritative figure the LMS does not hold. Never a number, never 0."""
    return {"state": "Not Configured", "reason": reason, "refreshed_at": dash_repo.latest_finance_refresh()}


CRM_REASON = "CRM-authoritative; the source is not connected"


def _sum(values) -> Decimal | int:
    return sum(values, start=0)


def _all_or_none(values: list):
    """The total when every branch has a value (e.g. a target), else None: a partial target is no target."""
    return None if any(v is None for v in values) else _sum(values)


def _period(snapshots: list) -> dict | None:
    periods = {(s.period_label, s.period_start, s.period_end) for s in snapshots}
    if len(periods) != 1 or None in next(iter(periods)):
        return None  # no approved target, or branches on different periods
    label, start, end = periods.pop()
    return {"label": label, "start": start, "end": end}


def _merged_age_bands(snapshots: list) -> list[dict]:
    bands: dict[str, dict] = {}
    for snapshot in snapshots:
        for band in snapshot.overdue_by_age_band:
            total = bands.setdefault(band["band"], {"band": band["band"], "amount": Decimal("0.00"), "count": 0})
            total["amount"] += Decimal(band["amount"])
            total["count"] += band["count"]
    return list(bands.values())


FIGURES = {
    "verified_collections": lambda s: {"unit": "INR", "value": _sum(x.collections_verified for x in s),
                                       "target": _all_or_none([x.collections_target for x in s]), "period": _period(s)},
    "new_paid_admissions": lambda s: {"unit": "count", "value": _sum(x.paid_admissions for x in s),
                                      "target": _all_or_none([x.paid_admissions_target for x in s]), "period": _period(s)},
    "overdue_amount": lambda s: {"unit": "INR", "value": _sum(x.overdue_amount for x in s),
                                 "detail": {"count": _sum(x.overdue_count for x in s), "by_age_band": _merged_age_bands(s)}},
    "overdue_followups": lambda s: {"unit": "count", "value": _sum(x.followups_overdue + x.broken_promises for x in s),
                                    "detail": {"followups_overdue": _sum(x.followups_overdue for x in s),
                                               "broken_promises": _sum(x.broken_promises for x in s)}},
    "overdue_payment_verifications": lambda s: {
        "unit": "count", "value": _sum(x.verifications_overdue for x in s),
        "detail": {"pending_count": _sum(x.verifications_pending for x in s),
                   "pending_amount": _sum(x.verifications_pending_amount for x in s),
                   "oldest_at": min((x.verifications_oldest_at for x in s if x.verifications_oldest_at), default=None)}},
}


def _crm_figures(branch_ids: set[int] | None, *names: str) -> dict:
    """The CRM's finance figures for the branches in view, from their latest BranchFinanceSnapshot."""
    branches = branches_repo.list_active(branch_ids)
    snapshots = dash_repo.finance_snapshots({b.branch_id for b in branches})
    reported = [snapshots[b.branch_id] for b in branches if b.branch_id in snapshots]
    if not reported:
        return {name: not_configured(CRM_REASON) for name in names}
    missing = [b.to_summary() for b in branches if b.branch_id not in snapshots]
    as_of = min(x.as_of for x in reported)
    common = {"state": "Partial Data" if missing else "Configured", "as_of": as_of,
              "stale": _now() - as_of > FINANCE_STALE_AFTER, "missing_branches": missing,
              "target": None, "period": None, "detail": None}
    return {name: {**common, **FIGURES[name](reported)} for name in names}


def _batch_risks(batches) -> list[dict]:
    return [{"batch_id": b.batch_id, "batch_code": b.batch_code, "branch": b.branch.to_summary(), "state": b.state, "readiness": b.readiness,
             "reason": b.readiness_reason, "recovery_owner": b.recovery_owner} for b in batches if b.readiness != "Ready"]


def academic_summary(branch_id: int | None = None) -> dict:
    branch_ids = _branches(branch_id)
    enrolments = dash_repo.enrolment_counts(branch_ids)
    batches = dash_repo.open_batches(branch_ids)
    content, completion = dash_repo.content_awaiting_review(branch_ids), dash_repo.open_completion_reviews(branch_ids)
    certificates = sum(dash_repo.certificates_in_status(CERTIFICATE_REVIEW, branch_ids).values())
    exceptions = exceptions_service.counts(branch_ids)
    return {
        "as_of": _now(),
        "scope": _scope_block(branch_ids),
        "allocation_queue": {
            "count": sum(enrolments.get(s, 0) for s in AWAITING_ALLOCATION),
            "curriculum_mapping_pending": enrolments.get("Curriculum Mapping Pending", 0),
            "allocation_pending": enrolments.get("Allocation Pending", 0),
        },
        "results_awaiting_publication": {"count": dash_repo.results_awaiting_publication(branch_ids)},
        "recording_exceptions": {"count": dash_repo.unresolved_recording_exceptions(branch_ids)},
        "batches_ready": {"ready": sum(1 for b in batches if b.readiness == "Ready"), "total": len(batches)},
        "reviews_awaiting": {"count": content + completion + certificates, "content": content, "completion": completion,
                             "certificates": certificates},
        "open_exceptions": {"count": exceptions["total"], "awaiting_owner": exceptions["awaiting_owner"]},
        "batch_risks": _batch_risks(batches),
    }


def branch_summary(branch_id: int | None = None) -> dict:
    branch_ids = _branches(branch_id)
    batches = dash_repo.open_batches(branch_ids)
    running = [b for b in batches if b.state in ("Starting", "Running", "Full")]
    recording = dash_repo.unresolved_recording_exceptions(branch_ids)
    reschedule = dash_repo.open_reschedule_requests(branch_ids)
    escalations = dash_repo.escalated_support_requests(branch_ids)
    extensions = dash_repo.pending_extension_requests(branch_ids)
    return {
        "as_of": _now(),
        "scope": _scope_block(branch_ids),
        "crm": _crm_figures(branch_ids, "verified_collections", "new_paid_admissions", "overdue_followups"),
        "batches_running": {"count": len(running), "total_open": len(batches)},
        "schedule_and_recording_exceptions": {"count": recording + reschedule, "recording_exceptions": recording, "reschedule_requests": reschedule},
        "requests_open": {"count": escalations + extensions, "escalations": escalations, "extension_requests": extensions},
        "batch_risks": _batch_risks(batches),
    }


def _sync_flows(summary: dict, crm_state: str) -> list[dict]:
    """The two CRM/LMS flows with the honest state: nothing is 'Verified' unless the CRM integration is."""
    received, delivered = summary["last_event_received_at"], summary["last_outbox_delivered_at"]
    working = "Verified" if crm_state == "Verified" else "Pending Verification"
    return [
        {"flow": "CRM → LMS events", "last_successful_at": received, "state": working if received else crm_state,
         "detail": f"{summary['failed_events']} failed event(s)" if summary["failed_events"] else None},
        {"flow": "LMS → CRM status outbox", "last_successful_at": delivered, "state": working if delivered else "Integration Unavailable",
         "detail": f"{summary['pending_outbox']} value(s) queued; no delivery worker yet" if summary["pending_outbox"] and not delivered else None},
    ]


def _ai_status() -> dict:
    status = ask_nipuna.status()
    ceiling = settings_repo.get(AI_CEILING_SETTING)
    return {
        "state": status.status,
        "student_daily_limit": settings_repo.get_int("ai_daily_limit", 50),
        "staff_daily_limit": settings_repo.get_int("ai_daily_limit_staff", 100),
        "monthly_ceiling": {"state": "Configuration Pending"} if ceiling is None else {"state": "Configured", "amount_inr": ceiling},
    }


def admin_summary() -> dict:
    integrations = dash_repo.integration_counts()
    exceptions = exceptions_service.counts(None)
    sync = crm_sync.summary()
    crm_state = integrations_service.integration_status("CRM").state
    provisioning, _ = exceptions_service.list_exceptions({"source": "PROVISIONING"}, 1, 10)
    failed_events, _ = exceptions_service.list_exceptions({"source": "CRM_EVENT"}, 1, 10)
    return {
        "as_of": _now(),
        "scope": _scope_block(None),
        "crm": _crm_figures(None, "overdue_payment_verifications"),
        "integration_failures": {"count": len(integrations["failing"]), "codes": integrations["failing"],
                                 "source": "Readiness register; live monitoring is Configuration Pending"},
        "awaiting_owner": {"count": exceptions["awaiting_owner"]},
        "integrations_verified": {"verified": integrations["verified"], "total": integrations["total"]},
        "provisioning": {"count": exceptions["by_source"].get("PROVISIONING", {}).get("count", 0), "items": provisioning},
        "open_exceptions": {"count": exceptions["total"], "by_source": exceptions["by_source"]},
        "sync": {"flows": _sync_flows(sync, crm_state), "failed_events": sync["failed_events"], "pending_outbox": sync["pending_outbox"],
                 "failed_event_items": failed_events},
        "ai": _ai_status(),
    }


def founder_summary() -> dict:
    by_branch = dash_repo.active_enrolments_by_branch()
    branches = branches_repo.list_active()
    batches = dash_repo.open_batches(None)
    risks = _batch_risks(batches)
    certificates = dash_repo.certificates_in_status(("Awaiting Approval",), None)
    ceiling = settings_repo.get(AI_CEILING_SETTING)
    access = dash_repo.pending_exception_requests()
    return {
        "as_of": _now(),
        "scope": _scope_block(None),
        "crm": _crm_figures(None, "verified_collections", "new_paid_admissions", "overdue_amount"),
        "active_enrolments": {"count": sum(by_branch.values()),
                              "by_branch": [{"branch": b.to_summary(), "count": by_branch.get(b.branch_id, 0)} for b in branches]},
        "batches_at_risk": {"count": len(risks), "items": risks},
        "certificates_awaiting_approval": {"count": sum(certificates.values()),
                                           "by_branch": [{"branch": b.to_summary(), "count": certificates.get(b.branch_id, 0)} for b in branches]},
        "decisions": {
            "ai_ceiling": {"state": "Configuration Pending"} if ceiling is None else {"state": "Configured", "amount_inr": ceiling},
            "access_exceptions": {"count": len(access), "state": "Awaiting Approval", "items": access},
        },
    }

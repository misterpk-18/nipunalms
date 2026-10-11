"""The Super Admin's home (UX phase U17): "Needs action" and the Setup checklist.

Needs action lists what is waiting, with one button each: failed CRM updates (each with Retry, up to three; the rest are one row),
issues nobody owns, locked accounts, branch closures waiting for a decision, student accounts that need attention and setup items
that are broken. A row exists only while something waits. The Setup checklist is the Setup & health list shortened to what is not
Working yet; once everything is Working `setup.done` is true and the card goes away.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from config.database import db
from config.timezone import today_ist
from models import CrmEvent
from repositories import admin_students as students_repo
from repositories import crm_sync as sync_repo
from repositories import exceptions as exceptions_repo
from repositories import nav as nav_repo
from services import crm_causes, setup_health

SHOWN_FAILURES = 3


def _age(opened_at: datetime | None) -> int | None:
    return None if opened_at is None else max(0, (datetime.now(timezone.utc) - opened_at).days)


def _failed_events() -> list[dict]:
    events = list(db.session.execute(select(CrmEvent).where(CrmEvent.status == "Failed").order_by(CrmEvent.crm_event_id.desc())
                                     .limit(SHOWN_FAILURES)).scalars())
    total = sync_repo.event_counts().get("Failed", 0)
    rows = []
    for event in events:
        info = crm_causes.describe(event)
        rows.append({"key": f"crm_event:{event.crm_event_id}", "kind": "crm_event", "count": 1, "what": f"CRM update failed: {info['summary']}",
                     "where": info["plain_cause"], "age_days": _age(event.received_at), "to": "/admin/crm-sync", "search": {"event": event.crm_event_id},
                     "action": "Look at it", "retry": {"crm_event_id": event.crm_event_id} if info["can_retry"] else None})
    if total > len(events):
        rows.append({"key": "crm_events_more", "kind": "crm_events", "count": total - len(events), "what": f"{total - len(events)} more CRM updates failed",
                     "where": None, "age_days": None, "to": "/admin/crm-sync", "search": {}, "action": "See all", "retry": None})
    return rows


def needs_action() -> dict:
    rows = _failed_events()
    unowned = exceptions_repo.list_stmt({"awaiting_owner": True}, None).limit(1)
    oldest = db.session.execute(unowned).scalars().first()
    counts = exceptions_repo.counts(None)
    if counts["awaiting_owner"]:
        rows.append({"key": "issues", "kind": "issues", "count": counts["awaiting_owner"],
                     "what": f"{counts['awaiting_owner']} issue{'s' if counts['awaiting_owner'] != 1 else ''} nobody owns yet", "where": None,
                     "age_days": _age(oldest.opened_at) if oldest else None, "to": "/admin/issues", "search": {"owner": "none"}, "action": "Assign"})
    locked = nav_repo.locked_users(datetime.now(timezone.utc))
    if locked:
        rows.append({"key": "locked_users", "kind": "locked_users", "count": locked, "what": f"{locked} staff account{'s are' if locked != 1 else ' is'} locked",
                     "where": "Locked after too many wrong passwords", "age_days": None, "to": "/admin/users", "search": {"locked": "true"}, "action": "Unlock"})
    closures = nav_repo.pending_closures(today_ist())
    if closures:
        rows.append({"key": "closures", "kind": "closures", "count": closures,
                     "what": f"{closures} branch closure{'s' if closures != 1 else ''} waiting for a decision", "where": None, "age_days": None,
                     "to": "/admin/calendar", "search": {"view": "list"}, "action": "Decide"})
    attention = students_repo.needs_attention_count()
    if attention:
        rows.append({"key": "student_accounts", "kind": "student_accounts", "count": attention,
                     "what": f"{attention} student account{'s need' if attention != 1 else ' needs'} attention", "where": "For example a link that expired",
                     "age_days": None, "to": "/admin/students", "search": {"attention": "true"}, "action": "Open"})
    checklist = setup_health.checklist()
    broken = checklist["summary"]["counts"]["Broken"]
    if broken:
        rows.append({"key": "setup_broken", "kind": "setup", "count": broken, "what": f"{broken} connection{'s' if broken != 1 else ''} or setting{'s are' if broken != 1 else ' is'} broken",
                     "where": None, "age_days": None, "to": "/admin/setup", "search": {}, "action": "Fix"})
    open_items = [i for i in checklist["items"] if i["state"] != "Working"]
    return {"rows": rows, "total": sum(r["count"] for r in rows),
            "setup": {**checklist["summary"], "items": [{k: i[k] for k in ("key", "name", "group", "state")} | {"owner": i["owner"]["full_name"] or i["owner"]["label"]}
                                                          for i in open_items]}}

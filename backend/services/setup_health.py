"""Setup & health (UX phase U17): the integrations register and the security register as one checklist.

Each row says in plain words where it stands (Not set up / Set up / Working / Broken, from the two registers' statuses, see
`services/readiness.setup_state`), who owns it (picked from staff) and the evidence. The two registers keep their own tables
and their own update rules; this module only reads them side by side. The Setup checklist card on the Super Admin's home
counts the rows that are not Working yet and disappears when none is left.
"""
from services import integrations as integrations_service
from services import security_controls as controls_service
from services.readiness import SETUP_STATES, setup_state

HELP = {
    "Not set up": "Nothing is connected yet. Set it up, then record that it works.",
    "Set up": "It is set up but nobody has seen it working yet. Check it and mark it Working with a note of how.",
    "Working": "Someone saw it working and wrote down how.",
    "Broken": "A check failed or it is set up wrongly. Fix it, then check it again.",
}


def _owner(record) -> dict:
    return {"user_id": record.owner_user_id, "full_name": record.owner if record.owner_user_id else None, "label": record.owner}


def _row(kind: str, record, *, rid: int, key: str, name: str, group: str) -> dict:
    return {
        "key": f"{kind}:{key}", "kind": kind, "id": rid,
        "code": key, "name": name, "group": group, "requirement": record.requirement,
        "state": setup_state(record.configuration_status, record.verification_status),
        "configuration_status": record.configuration_status, "verification_status": record.verification_status,
        "owner": _owner(record), "evidence": record.evidence, "notes": record.notes,
        "verified_at": record.verified_at, "last_checked_at": record.last_checked_at,
    }


def items() -> list[dict]:
    connections = [_row("integration", i, rid=i.integration_id, key=i.integration_code, name=i.integration_name, group="Connections")
                   for i in integrations_service.list_integrations()]
    security = [_row("security", c, rid=c.control_id, key=c.control_code, name=c.title, group=f"Security · {c.category}")
                for c in controls_service.list_controls()]
    return connections + security


def summary(rows: list[dict] | None = None) -> dict:
    rows = items() if rows is None else rows
    counts = {state: sum(1 for r in rows if r["state"] == state) for state in SETUP_STATES}
    open_rows = [r for r in rows if r["state"] != "Working"]
    return {"counts": counts, "total": len(rows), "open": len(open_rows), "done": not open_rows}


def checklist() -> dict:
    rows = items()
    return {"items": rows, "summary": summary(rows), "help": HELP}


def broken_count() -> int:
    """Rows whose last check failed (the nav badge of Setup & health: a count of everything not yet set up would never go away)."""
    return summary()["counts"]["Broken"]

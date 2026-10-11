"""Audit log viewer (Super Admin / Founder): filter the append-only history by actor, entity, action, branch and date.

Entries are written by services/audit.py; nothing here changes them.
"""
from datetime import date, datetime, time, timedelta

from config.timezone import IST
from repositories import audit_log as audit_repo
from repositories.common import paginate_rows
from services import audit_sentences, exports
from services.errors import ValidationError


def ist_day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def _prepare(filters: dict) -> dict:
    """Filters `from` / `to` are IST dates, both inclusive; `preset` is Accounts, Roles or Integrations (an action filter)."""
    filters = dict(filters)
    if filters.get("from"):
        filters["occurred_from"] = ist_day_start(filters["from"])
    if filters.get("to"):
        filters["occurred_before"] = ist_day_start(filters["to"] + timedelta(days=1))
    if filters.get("preset"):
        if filters["preset"] not in audit_sentences.PRESETS:
            raise ValidationError("Invalid request data", {"preset": ["Not a preset filter"]})
        filters["actions"] = audit_sentences.PRESETS[filters["preset"]]
    return filters


def list_entries(filters: dict, page: int, per_page: int):
    """The page of entries as `(entry dict, actor)` rows: the stored entry plus a plain sentence, the record's name and a link."""
    rows, meta = paginate_rows(audit_repo.list_stmt(_prepare(filters)), page, per_page)
    names = {entry.actor_user_id: name for entry, name, _ in rows if entry.actor_user_id}
    annotated = audit_sentences.annotate([entry for entry, _, _ in rows], names)
    return [{**item, "actor": {"user_id": entry.actor_user_id, "full_name": name, "email": email} if entry.actor_user_id else None}
            for item, (entry, name, email) in zip(annotated, rows)], meta


def facets() -> dict:
    return {**audit_repo.facets(), "actors": [{"user_id": i, "full_name": name, "email": email} for i, name, email in audit_repo.actors()],
            "presets": [{"key": key, "label": label} for key, label in audit_sentences.PRESET_LABELS.items()]}


EXPORT_LIMIT = 5000


def export_csv(filters: dict) -> tuple[str, bytes]:
    """The filtered entries (newest first, at most EXPORT_LIMIT) as a CSV the Super Admin can open in Excel."""
    stmt = audit_repo.list_stmt(_prepare(filters)).limit(EXPORT_LIMIT)
    from config.database import db

    rows = db.session.execute(stmt).all()
    names = {entry.actor_user_id: name for entry, name, _ in rows if entry.actor_user_id}
    annotated = audit_sentences.annotate([entry for entry, _, _ in rows], names)
    body = [[a["occurred_at"].astimezone(IST).strftime("%Y-%m-%d %H:%M"), a["sentence"], (names.get(a["actor_user_id"]) or "System"), a["action"],
             a["entity_type"], a["entity_id"], a["reason"] or ""] for a in annotated]
    return "audit-log.csv", exports.to_csv(["When (IST)", "What happened", "Who", "Action", "Record type", "Record", "Reason"], body)

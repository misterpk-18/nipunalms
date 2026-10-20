"""A first-day check of the Google connection (`flask google check`): is the key there, is the service account authorised for
each scope and mailbox, and can it read the mailbox's calendar and Drive. Everything here only reads; nothing is created or sent."""
from dataclasses import dataclass

from flask import current_app

from services.google import client
from services.google.client import GoogleError

CALENDAR_LIST = "https://www.googleapis.com/calendar/v3/calendars/{mailbox}/events"
DRIVE_LIST = "https://www.googleapis.com/drive/v3/files"
GROUP_LIST = "https://admin.googleapis.com/admin/directory/v1/groups"
SCOPES = (("Calendar events", client.CALENDAR_SCOPE), ("Drive files", client.DRIVE_SCOPE), ("Gmail send", client.GMAIL_SEND_SCOPE))


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    hint: str | None = None


def _step(name: str, action, hint: str | None = None) -> Check:
    try:
        return Check(name, True, action() or "ok")
    except GoogleError as exc:
        return Check(name, False, str(exc), hint)


def run(mailbox: str | None = None) -> list[Check]:
    """The checks in order; later ones are skipped when an earlier one they depend on fails."""
    config = current_app.config
    mailbox = mailbox or config.get("GOOGLE_DELEGATED_ADMIN")
    checks = [Check("Mailbox to act as", bool(mailbox), mailbox or "none set",
                    None if mailbox else "Set GOOGLE_DELEGATED_ADMIN in backend/.env, or pass --mailbox")]
    key_ok = bool(config.get("GOOGLE_SA_SECRET_NAME")) or bool(client._key_file() and client._key_file().is_file())
    checks.append(Check("Service-account key", key_ok, config.get("GOOGLE_SA_SECRET_NAME") or str(client._key_file() or "not set"),
                        None if key_ok else "Put the key file at GOOGLE_SA_KEY_FILE or set GOOGLE_SA_SECRET_NAME"))
    if not (mailbox and key_ok):
        return checks

    key = _step("Key is a service account", _key_check, "Download a JSON key for the service account")
    checks.append(key)
    if not key.ok:
        return checks

    delegated = []
    for label, scope in SCOPES:
        check = _step(f"Delegation: {label}", lambda scope=scope: client.mint_token(mailbox, [scope]) or f"authorised for {mailbox}",
                      "Admin console > Security > API controls > Domain-wide delegation: add the client ID above with this scope, and check the mailbox exists")
        checks.append(check)
        delegated.append(check.ok)
    if delegated[0]:
        checks.append(_step("Read the mailbox's calendar", lambda: _count(client.request(
            "GET", CALENDAR_LIST.format(mailbox=mailbox), subject=mailbox, scopes=[client.CALENDAR_SCOPE], params={"maxResults": 1}), "items", "event"),
            "Enable the Google Calendar API in the Cloud project"))
    if delegated[1]:
        checks.append(_step("Read Drive", lambda: _count(client.request(
            "GET", DRIVE_LIST, subject=mailbox, scopes=[client.DRIVE_SCOPE], params={"pageSize": 1, "fields": "files(id)"}), "files", "file"),
            "Enable the Google Drive API in the Cloud project"))

    # Batch groups: the Directory API acts as the delegated admin, who must be allowed to manage groups
    admin, domain = config.get("GOOGLE_DELEGATED_ADMIN"), config.get("GOOGLE_WORKSPACE_DOMAIN")
    groups = _step("Delegation: Groups (as the delegated admin)", lambda: client.mint_token(admin, [client.ADMIN_GROUP_SCOPE]) or f"authorised for {admin}",
                   "Add the scope https://www.googleapis.com/auth/admin.directory.group to the client ID's delegation, and use a Workspace admin as GOOGLE_DELEGATED_ADMIN")
    checks.append(groups)
    if groups.ok and domain:
        checks.append(_step("List the domain's groups", lambda: _count(client.request(
            "GET", GROUP_LIST, subject=admin, scopes=[client.ADMIN_GROUP_SCOPE], params={"domain": domain, "maxResults": 1}), "groups", "group"),
            "Enable the Admin SDK API in the Cloud project, and give the delegated admin a role that can manage groups"))
    elif groups.ok:
        checks.append(Check("Workspace domain", False, "GOOGLE_WORKSPACE_DOMAIN is not set", "Set it in backend/.env: batch groups are made at <batch code>@<domain>"))
    return checks


def _key_check() -> str:
    summary = client.key_summary()
    if summary.get("type") != "service_account":
        raise GoogleError("The key file is not a service-account key")
    return f"{summary['client_email']} · client ID {summary['client_id']} · project {summary['project_id']}"


def _count(reply: dict, key: str, noun: str) -> str:
    return f"reachable ({len(reply.get(key, []))} {noun} seen in the first page)"

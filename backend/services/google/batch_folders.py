"""A batch's Google Drive folder, its Google Group, and who has access (docs/GOOGLE_WORKSPACE.md §5.2).

Folders: `Nipuna LMS / <course> / <batch code>`, owned by the branch's mailbox and made on demand. The students holding a seat are
members of one Google Group per batch (`<batch code>@<workspace domain>`), and the folder is shared once with that group as viewers;
trainers assigned to the batch are shared with individually as editors. A student loses access when their seat ends or the batch is
Completed, Cancelled or Archived (they leave the group); trainers lose it when their assignment ends or the batch is Cancelled or
Archived.

Nothing here runs inside a user's request. Every change that could alter who has access (a seat taken or ended, a trainer
assigned or ended, a batch state change) calls `enqueue_sync(batch_id)`, and the `google-sync` job compares who should have
access with the group's members and the shares it recorded, and adds or removes the difference. One job per batch, so any number
of changes is one pass, and a retry after a failure picks up where the last pass stopped.

The switch is the `GOOGLE_DRIVE` entry of the integrations register plus a service-account key. The group calls act as
`GOOGLE_DELEGATED_ADMIN`, which must be a Workspace admin allowed to manage groups.
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

from flask import current_app

from config.database import db
from config.timezone import today_ist
from models import Batch, GoogleDriveGrant, GoogleDriveItem
from repositories import google as google_repo
from repositories import users as users_repo
from repositories import whatsapp as whatsapp_repo
from services import delivery_notices, integrations
from services.google import client
from services.google.client import GoogleError

logger = logging.getLogger(__name__)

DRIVE_INTEGRATION = "GOOGLE_DRIVE"
KIND_SYNC = "DRIVE_SYNC"
ENTITY = "batch"
FILES = "https://www.googleapis.com/drive/v3/files"
GROUPS = "https://admin.googleapis.com/admin/directory/v1/groups"
FOLDER = "application/vnd.google-apps.folder"
ROOT_NAME = "Nipuna LMS"
STUDENTS_LOSE_ACCESS = ("Completed", "Cancelled", "Archived")
TRAINERS_LOSE_ACCESS = ("Cancelled", "Archived")


def is_enabled() -> bool:
    return client.is_configured() and integrations.is_verified(DRIVE_INTEGRATION)


def enqueue_sync(batch_id: int) -> None:
    """Who should have this batch's folder may have changed; the job works it out when it runs."""
    if is_enabled():
        google_repo.enqueue(KIND_SYNC, ENTITY, batch_id)


# ---------------------------------------------------------------- who should have access

def _address(student_or_user_email: str | None) -> str:
    return (student_or_user_email or "").strip()


def _wanted_students(batch: Batch) -> dict[str, int | None]:
    """{lower-case email: user id} for every student who should be in the batch's group right now."""
    wanted: dict[str, int | None] = {}
    if batch.state in STUDENTS_LOSE_ACCESS:
        return wanted
    for student in whatsapp_repo.batch_roster(batch.batch_id):
        user = users_repo.get_by_student_id(student.student_id)
        address = _address(student.email or (user.email if user else None))
        if address:
            wanted[address.lower()] = user.user_id if user else None
    return wanted


def _wanted_trainers(batch: Batch) -> dict[str, int]:
    """{lower-case email: user id} for every trainer who should be able to edit the folder right now."""
    wanted: dict[str, int] = {}
    if batch.state in TRAINERS_LOSE_ACCESS:
        return wanted
    today = today_ist()
    for assignment in batch.trainers:
        address = _address(assignment.trainer.email)
        if address and (assignment.to_date is None or assignment.to_date >= today):
            wanted[address.lower()] = assignment.trainer_user_id
    return wanted


# ---------------------------------------------------------------- Drive calls

def _call(method: str, mailbox: str, path: str = "", *, body: dict | None = None, params: dict | None = None) -> dict:
    return client.request(method, FILES + path, subject=mailbox, scopes=[client.DRIVE_SCOPE], body=body, params=params)


def _find_or_create_folder(mailbox: str, key: str, name: str, parent_id: str | None) -> str:
    """The folder tagged with our key, made when it is not there yet. The tag is how a retry after a lost reply finds it again."""
    found = _call("GET", mailbox, params={"q": f"appProperties has {{ key='lms_key' and value='{key}' }} and trashed=false and mimeType='{FOLDER}'",
                                          "fields": "files(id)", "spaces": "drive"})
    if found.get("files"):
        return found["files"][0]["id"]
    body = {"name": name, "mimeType": FOLDER, "appProperties": {"lms_key": key}}
    if parent_id:
        body["parents"] = [parent_id]
    return _call("POST", mailbox, body=body, params={"fields": "id"})["id"]


def _ensure_item(mailbox: str, entity_type: str, entity_id: int, branch_id: int, name: str, parent: GoogleDriveItem | None) -> GoogleDriveItem:
    item = google_repo.drive_item(entity_type, entity_id, branch_id)
    if item is not None:
        return item
    folder_id = None
    if entity_type == "branch":
        config = google_repo.branch_config(branch_id)
        folder_id = config.drive_root_folder_id if config else None  # a folder the branch's admin chose
    if folder_id is None:
        folder_id = _find_or_create_folder(mailbox, f"nipuna-lms:{entity_type}:{branch_id}:{entity_id}", name, parent.folder_id if parent else None)
    if entity_type == "branch":
        google_repo.set_drive_root(branch_id, folder_id)
    return google_repo.add_drive_item(entity_type, entity_id, branch_id, parent, folder_id, name)


def _batch_item(mailbox: str, batch: Batch) -> GoogleDriveItem:
    root = _ensure_item(mailbox, "branch", batch.branch_id, batch.branch_id, ROOT_NAME, None)
    course = _ensure_item(mailbox, "course", batch.course_id, batch.branch_id, batch.course.title, root)
    return _ensure_item(mailbox, "batch", batch.batch_id, batch.branch_id, batch.batch_code, course)


def _share(mailbox: str, folder_id: str, email: str, role: str, kind: str = "user") -> str:
    """Share the folder with one person or group. An address with no Google account can only be invited, which Google emails."""
    path, body = f"/{folder_id}/permissions", {"type": kind, "role": role, "emailAddress": email}
    try:
        return _call("POST", mailbox, path, body=body, params={"sendNotificationEmail": "false", "fields": "id"})["id"]
    except GoogleError as exc:
        if exc.status != 400 or "google account" not in str(exc).lower():
            raise
    return _call("POST", mailbox, path, body=body, params={"sendNotificationEmail": "true", "fields": "id"})["id"]


# ---------------------------------------------------------------- the batch's Google Group

def _directory(method: str, path: str = "", *, body: dict | None = None, params: dict | None = None) -> dict:
    admin = current_app.config.get("GOOGLE_DELEGATED_ADMIN")
    return client.request(method, GROUPS + path, subject=admin, scopes=[client.ADMIN_GROUP_SCOPE], body=body, params=params)


def _group_address(batch: Batch) -> str:
    domain = current_app.config.get("GOOGLE_WORKSPACE_DOMAIN")
    if not domain:
        raise GoogleError("GOOGLE_WORKSPACE_DOMAIN is not set, so a batch group has no address")
    return f"{re.sub(r'[^a-z0-9-]+', '-', batch.batch_code.lower()).strip('-')}@{domain}"


def _ensure_group(batch: Batch, item: GoogleDriveItem) -> str:
    if item.group_email:
        return item.group_email
    address = _group_address(batch)
    try:
        _directory("POST", body={"email": address, "name": f"Batch {batch.batch_code}",
                                 "description": f"Students of batch {batch.batch_code}, {batch.course.title}"})
    except GoogleError as exc:
        if exc.status != 409:  # 409: the group is already there (a retry after a lost reply)
            raise
    google_repo.set_item_group(item, address)
    return address


def _group_members(address: str) -> dict[str, str]:
    """{lower-case email: role} for everyone in the group."""
    members, token = {}, None
    while True:
        page = _directory("GET", f"/{quote(address, safe='@')}/members", params={"maxResults": 200, **({"pageToken": token} if token else {})})
        members.update({m["email"].lower(): m.get("role", "MEMBER") for m in page.get("members", [])})
        token = page.get("nextPageToken")
        if not token:
            return members


def _sync_group(address: str, wanted: dict[str, int | None]) -> tuple[int, int, list[GoogleError]]:
    """Make the group's plain members exactly the wanted students (owners and managers are never touched)."""
    base, failures, added, removed = f"/{quote(address, safe='@')}/members", [], 0, 0
    current = _group_members(address)
    for email in wanted:
        if email in current:
            continue
        try:
            _directory("POST", base, body={"email": email, "role": "MEMBER"})
            added += 1
        except GoogleError as exc:
            if exc.status == 409:  # already a member
                continue
            failures.append(exc)
    for email, role in current.items():
        if role == "MEMBER" and email not in wanted:
            try:
                _directory("DELETE", f"{base}/{quote(email, safe='@')}")
                removed += 1
            except GoogleError as exc:
                if exc.status not in (404, 410):
                    failures.append(exc)
    return added, removed, failures


# ---------------------------------------------------------------- called from the google-sync job

def handle_sync(batch_id: int) -> str:
    batch = db.session.get(Batch, batch_id)
    if batch is None:
        return "batch no longer exists"
    students, trainers = _wanted_students(batch), _wanted_trainers(batch)
    item = google_repo.drive_item("batch", batch.batch_id, batch.branch_id)
    if item is None and not students and not trainers:
        return "nobody to share with yet"
    mailbox = google_repo.branch_mailbox(batch.branch_id)
    if not mailbox:
        raise GoogleError(f"Branch {batch.branch_id} has no mailbox that owns its Drive folders")
    if item is None:
        item = _batch_item(mailbox, batch)

    failures: list[GoogleError] = []
    joined = left = 0
    if students or item.group_email:  # a batch that has never had a student needs no group
        address = _ensure_group(batch, item)
        joined, left, group_failures = _sync_group(address, students)
        failures += group_failures

    wanted: dict[str, tuple[str, int | None, str]] = {email: ("writer", user_id, "user") for email, user_id in trainers.items()}
    if item.group_email:
        wanted[item.group_email.lower()] = ("reader", None, "group")

    live = {grant.grantee_email.lower(): grant for grant in google_repo.live_grants(item.item_id)}
    now, added, removed = datetime.now(timezone.utc), 0, 0
    for email, grant in live.items():
        if email not in wanted or wanted[email][0] != grant.role:
            try:
                _call("DELETE", mailbox, f"/{item.folder_id}/permissions/{grant.permission_id}")
            except GoogleError as exc:
                if exc.status not in (404, 410):  # already gone is the same as removed
                    failures.append(exc)
                    continue
            grant.revoked_at = now
            removed += 1
            live[email] = None
    db.session.flush()
    for email, (role, user_id, kind) in wanted.items():
        if live.get(email) is not None:
            continue
        try:
            permission_id = _share(mailbox, item.folder_id, email, role, kind)
        except GoogleError as exc:
            failures.append(exc)
            continue
        db.session.add(GoogleDriveGrant(item_id=item.item_id, grantee_email=email, grantee_user_id=user_id, role=role, permission_id=permission_id))
        added += 1
    db.session.flush()
    if failures:
        raise GoogleError(f"{len(failures)} share change(s) failed; first: {failures[0]}", retryable=any(f.retryable for f in failures))
    return f"{joined} joined and {left} left the group, {added} shared, {removed} unshared, {len(students)} students and {len(trainers)} trainers with access"


def on_dead(job_kind: str, batch_id: int, error: str) -> None:
    """The retries are used up: tell the branch's managers that sharing for this batch needs a person to look at it."""
    batch = db.session.get(Batch, batch_id)
    if batch is None:
        return
    delivery_notices.notify_branch_managers(
        batch.branch_id, title=f"Drive sharing failed: batch {batch.batch_code}", category="Batch", action_required=True,
        body=f"The batch folder or its group could not be updated. {error}",
        event_key=f"drive-failed-{batch.batch_id}-{datetime.now(timezone.utc):%Y%m%d%H%M}", link="/branch/batches")

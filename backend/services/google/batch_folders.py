"""A batch's Google Drive folder and who it is shared with (docs/GOOGLE_WORKSPACE.md §5.2).

Folders: `Nipuna LMS / <course> / <batch code>`, owned by the branch's mailbox and made on demand. Trainers assigned to the batch
are editors; students holding a seat are viewers while the batch runs, and lose access when their seat ends or the batch is
Completed, Cancelled or Archived. Trainers lose it when the batch is Cancelled or Archived, or their assignment ends.

Nothing here runs inside a user's request. Every change that could alter who has access (a seat taken or ended, a trainer
assigned or ended, a batch state change) calls `enqueue_sync(batch_id)`, and the `google-sync` job compares who should have
access with the shares it recorded and adds or removes the difference. One job per batch, so any number of changes is one pass,
and a retry after a failure picks up where the last pass stopped.

The switch is the `GOOGLE_DRIVE` entry of the integrations register plus a service-account key.
"""
import logging
from datetime import datetime, timezone

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

def _wanted(batch: Batch) -> dict[str, tuple[str, int | None]]:
    """{lower-case email: (role, user id)} for everyone who should hold a share of the batch's folder right now."""
    wanted: dict[str, tuple[str, int | None]] = {}
    today = today_ist()
    if batch.state not in STUDENTS_LOSE_ACCESS:
        for student in whatsapp_repo.batch_roster(batch.batch_id):
            user = users_repo.get_by_student_id(student.student_id)
            address = (student.email or (user.email if user else None) or "").strip()
            if address:
                wanted[address.lower()] = ("reader", user.user_id if user else None)
    if batch.state not in TRAINERS_LOSE_ACCESS:
        for assignment in batch.trainers:
            if assignment.to_date is None or assignment.to_date >= today:
                address = (assignment.trainer.email or "").strip()
                if address:
                    wanted[address.lower()] = ("writer", assignment.trainer_user_id)  # an editor wins over a viewer
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


def _share(mailbox: str, folder_id: str, email: str, role: str) -> str:
    """Share the folder with one person. An address with no Google account can only be invited, which Google emails."""
    path, body = f"/{folder_id}/permissions", {"type": "user", "role": role, "emailAddress": email}
    try:
        return _call("POST", mailbox, path, body=body, params={"sendNotificationEmail": "false", "fields": "id"})["id"]
    except GoogleError as exc:
        if exc.status != 400 or "google account" not in str(exc).lower():
            raise
    return _call("POST", mailbox, path, body=body, params={"sendNotificationEmail": "true", "fields": "id"})["id"]


# ---------------------------------------------------------------- called from the google-sync job

def handle_sync(batch_id: int) -> str:
    batch = db.session.get(Batch, batch_id)
    if batch is None:
        return "batch no longer exists"
    wanted = _wanted(batch)
    item = google_repo.drive_item("batch", batch.batch_id, batch.branch_id)
    if item is None and not wanted:
        return "nobody to share with yet"
    mailbox = google_repo.branch_mailbox(batch.branch_id)
    if not mailbox:
        raise GoogleError(f"Branch {batch.branch_id} has no mailbox that owns its Drive folders")
    if item is None:
        item = _batch_item(mailbox, batch)

    live = {grant.grantee_email.lower(): grant for grant in google_repo.live_grants(item.item_id)}
    now, failures, added, removed = datetime.now(timezone.utc), [], 0, 0
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
    for email, (role, user_id) in wanted.items():
        if live.get(email) is not None:
            continue
        try:
            permission_id = _share(mailbox, item.folder_id, email, role)
        except GoogleError as exc:
            failures.append(exc)
            continue
        db.session.add(GoogleDriveGrant(item_id=item.item_id, grantee_email=email, grantee_user_id=user_id, role=role,
                                        permission_id=permission_id))
        added += 1
    db.session.flush()
    if failures:
        raise GoogleError(f"{len(failures)} share change(s) failed; first: {failures[0]}", retryable=any(f.retryable for f in failures))
    return f"{added} shared, {removed} removed, {len(wanted)} with access"


def on_dead(job_kind: str, batch_id: int, error: str) -> None:
    """The retries are used up: tell the branch's managers that sharing for this batch needs a person to look at it."""
    batch = db.session.get(Batch, batch_id)
    if batch is None:
        return
    delivery_notices.notify_branch_managers(
        batch.branch_id, title=f"Drive sharing failed: batch {batch.batch_code}", category="Batch", action_required=True,
        body=f"The batch folder could not be shared or unshared. {error}",
        event_key=f"drive-failed-{batch.batch_id}-{datetime.now(timezone.utc):%Y%m%d%H%M}", link="/branch/batches")

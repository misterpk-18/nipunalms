"""Google Workspace slice 3 (docs/GOOGLE_WORKSPACE.md §5.2): a batch's Drive folder shared with its trainers, and with one Google
Group per batch whose members are the students holding a seat. Drive and the Directory are faked: no test reaches Google."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import GoogleDriveGrant, GoogleDriveItem, GoogleJob, Notification
from services import allocations, batches as batches_service, integrations
from services.google import batch_folders
from services.google import client as google_client
from services.google import jobs
from services.google.client import GoogleError
from tests.test_delivery import world  # noqa: F401

DOMAIN = "example.test"


class FakeDrive:
    """Stands in for client.request, answering like Drive and the Directory and remembering every call."""

    def __init__(self):
        self.calls, self.folders, self.permissions = [], {}, {}  # folders: lms_key -> id; permissions: id -> (folder, email, role, type)
        self.groups = {}  # group address -> {member email: role}
        self.no_google = set()  # addresses Drive can only invite
        self.fail = []  # errors to raise on the next calls, first in first out
        self.counter = 0

    def of(self, method, contains=None):
        return [c for c in self.calls if c["method"] == method and (contains is None or contains in c["url"])]

    def __call__(self, method, url, *, subject, scopes, body=None, params=None):
        self.calls.append({"method": method, "url": url, "subject": subject, "scopes": scopes, "body": body, "params": params})
        if self.fail:
            error = self.fail.pop(0)
            if error is not None:
                raise error
        self.counter += 1
        if "/admin/directory/v1/groups" in url:
            return self.directory(method, url.split("/groups", 1)[1], body)
        if method == "GET":
            key = re.search(r"value='([^']+)'", params["q"]).group(1)
            return {"files": [{"id": self.folders[key]}] if key in self.folders else []}
        if method == "POST" and url.endswith("/files"):
            self.folders[body["appProperties"]["lms_key"]] = f"folder-{self.counter}"
            return {"id": f"folder-{self.counter}"}
        if method == "POST":
            folder = url.split("/files/")[1].split("/")[0]
            if body["emailAddress"] in self.no_google and params["sendNotificationEmail"] == "false":
                raise GoogleError("Google returned 400: Since there is no Google account associated with this email address, "
                                  "you must set sendNotificationEmail to true.", status=400)
            self.permissions[f"perm-{self.counter}"] = (folder, body["emailAddress"], body["role"], body["type"])
            return {"id": f"perm-{self.counter}"}
        if method == "DELETE":
            self.permissions.pop(url.rsplit("/", 1)[1], None)
            return {}
        raise AssertionError(f"unexpected {method} {url}")

    def directory(self, method, path, body):
        if method == "POST" and path == "":
            if body["email"] in self.groups:
                raise GoogleError("Google returned 409: Entity already exists.", status=409)
            self.groups[body["email"]] = {}
            return {"email": body["email"]}
        address, _, rest = path.lstrip("/").partition("/members")
        address = address.replace("%40", "@")
        members = self.groups[address]
        if method == "GET":
            return {"members": [{"email": e, "role": r} for e, r in members.items()]}
        if method == "POST":
            if body["email"] in members:
                raise GoogleError("Google returned 409: Member already exists.", status=409)
            members[body["email"]] = body["role"]
            return {}
        if method == "DELETE":
            members.pop(rest.lstrip("/").replace("%40", "@"), None)
            return {}
        raise AssertionError(f"unexpected directory {method} {path}")


def verify_drive(verifier):
    integration = integrations.integrations_repo.get_by_code("GOOGLE_DRIVE")
    integration.configuration_status, integration.verification_status = "Configured", "Verified"
    integration.verified_by, integration.verified_at, integration.evidence = verifier.user_id, datetime.now(timezone.utc), "Test folder"
    db.session.commit()


@pytest.fixture
def drive(app, monkeypatch, make_user):
    fake = FakeDrive()
    monkeypatch.setattr(google_client, "request", fake)
    monkeypatch.setattr(google_client, "is_configured", lambda: True)
    app.config.update(GOOGLE_WORKSPACE_DOMAIN=DOMAIN, GOOGLE_DELEGATED_ADMIN="admin@example.test")
    verify_drive(make_user(roles=[("SUPER_ADMIN", None)]))
    return fake


def seat(student, batch, allocate):
    return allocate(student, batch)


def sync_jobs(batch):
    db.session.expire_all()
    return list(db.session.execute(select(GoogleJob).where(GoogleJob.kind == "DRIVE_SYNC", GoogleJob.entity_id == batch.batch_id)
                                   .order_by(GoogleJob.job_id)).scalars())


def live():
    """Who holds a live share of any folder: {(email, role)}."""
    db.session.expire_all()
    return {(g.grantee_email, g.role) for g in db.session.execute(select(GoogleDriveGrant).where(GoogleDriveGrant.revoked_at.is_(None))).scalars()}


def group_of(batch):
    return f"{re.sub('[^a-z0-9-]+', '-', batch.batch_code.lower())}@{DOMAIN}"


def email_of(student):
    return student.email.lower()


def run():
    return jobs.run_due()


def end_seat(student, batch):
    from repositories import students as students_repo
    allocations.end(next(e for e in students_repo.enrolments_of_student(student.student_id) if e.course_id == batch.course_id), reason="Left")
    db.session.commit()


# ---------------------------------------------------------------- the switch

def test_nothing_is_queued_while_drive_is_off(world, allocate):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    assert sync_jobs(batch) == []


# ---------------------------------------------------------------- folders, group and shares

def test_a_seat_makes_the_folders_the_group_and_shares_once_with_the_group(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    assert [j.state for j in sync_jobs(batch)] == ["Queued"]
    assert run() == {"done": 1, "retry": 0, "dead": 0}

    made = [c["body"]["name"] for c in drive.of("POST", "/drive/v3/files") if c["url"].endswith("/files")]
    assert made == ["Nipuna LMS", batch.course.title, batch.batch_code]  # branch, course, batch, top down
    assert group_of(batch) in drive.groups and drive.groups[group_of(batch)] == {email_of(student): "MEMBER"}
    # the folder is shared with the group (viewers) and the trainer (editor); the student is not shared with directly
    assert live() == {(group_of(batch), "reader"), (people["g1"].email.lower(), "writer")}
    assert {p[3] for p in drive.permissions.values()} == {"group", "user"}
    item = db.session.execute(select(GoogleDriveItem).where(GoogleDriveItem.entity_type == "batch")).scalar_one()
    assert item.group_email == group_of(batch)
    # Drive calls act as the branch mailbox, group calls as the delegated admin
    from models import Branch
    assert {c["subject"] for c in drive.calls if "/drive/" in c["url"]} == {db.session.get(Branch, batch.branch_id).mailbox}
    assert {c["subject"] for c in drive.calls if "/directory/" in c["url"]} == {"admin@example.test"}
    assert all(c["scopes"] == [google_client.ADMIN_GROUP_SCOPE] for c in drive.calls if "/directory/" in c["url"])
    from repositories import google as google_repo
    assert google_repo.branch_config(batch.branch_id).drive_root_folder_id == drive.folders[f"nipuna-lms:branch:{batch.branch_id}:{batch.branch_id}"]


def test_a_second_pass_changes_nothing(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    writes = [c for c in drive.calls if c["method"] in ("POST", "DELETE")]
    batch_folders.enqueue_sync(batch.batch_id)
    assert run()["done"] == 1
    assert [c for c in drive.calls if c["method"] in ("POST", "DELETE")] == writes


def test_another_student_joins_the_group_and_a_leaver_is_removed(world, allocate, make_student, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    other = make_student()
    seat(other, batch, allocate)
    run()
    assert set(drive.groups[group_of(batch)]) == {email_of(student), email_of(other)}
    assert len(drive.permissions) == 2  # the folder is not shared again: the group already has it

    end_seat(student, batch)
    run()
    assert set(drive.groups[group_of(batch)]) == {email_of(other)}
    assert live() == {(group_of(batch), "reader"), (people["g1"].email.lower(), "writer")}


def test_a_group_owner_is_never_removed(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    drive.groups[group_of(batch)]["admin@example.test"] = "OWNER"
    batch_folders.enqueue_sync(batch.batch_id)
    run()
    assert drive.groups[group_of(batch)]["admin@example.test"] == "OWNER" and email_of(student) in drive.groups[group_of(batch)]


def test_a_transfer_moves_the_student_to_the_new_batchs_group(world, allocate, make_batch, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    other = make_batch(1, trainers=[people["g2"]], state="Running")
    seat(student, other, allocate)  # the old seat ends as Transferred
    assert {j.entity_id for j in db.session.execute(select(GoogleJob).where(GoogleJob.state == "Queued")).scalars() if j.kind == "DRIVE_SYNC"} == {batch.batch_id, other.batch_id}
    run()
    assert email_of(student) not in drive.groups[group_of(batch)] and email_of(student) in drive.groups[group_of(other)]


def test_completing_the_batch_empties_the_group_but_the_trainer_keeps_the_folder(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    batches_service._set_state(batch, "Completed", "Finished")
    db.session.commit()
    run()
    assert drive.groups[group_of(batch)] == {}
    assert (people["g1"].email.lower(), "writer") in live()


def test_a_cancelled_batch_loses_everyone(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    end_seat(student, batch)
    batches_service._set_state(batch, "Cancelled", "Not viable")
    db.session.commit()
    run()
    assert drive.groups[group_of(batch)] == {}
    assert (people["g1"].email.lower(), "writer") not in live()


def test_a_trainer_assigned_later_gets_editor_access(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    from models import BatchTrainer
    db.session.add(BatchTrainer(batch_id=batch.batch_id, trainer_user_id=people["g2"].user_id, role="Co-trainer"))
    db.session.commit()
    batch_folders.enqueue_sync(batch.batch_id)
    run()
    assert (people["g2"].email.lower(), "writer") in live()


def test_a_batch_that_only_has_trainers_gets_a_folder_but_no_group(world, drive):  # noqa: F811
    people, batch, student = world
    batch_folders.enqueue_sync(batch.batch_id)
    run()
    assert drive.groups == {} and live() == {(people["g1"].email.lower(), "writer")}


# ---------------------------------------------------------------- Google's quirks and failures

def test_the_group_needs_the_workspace_domain(world, allocate, drive, app):  # noqa: F811
    people, batch, student = world
    app.config["GOOGLE_WORKSPACE_DOMAIN"] = None
    seat(student, batch, allocate)
    assert run() == {"done": 0, "retry": 0, "dead": 1}
    [job] = sync_jobs(batch)
    assert "GOOGLE_WORKSPACE_DOMAIN" in job.last_error


def test_a_group_made_before_a_lost_reply_is_reused(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    drive.groups[group_of(batch)] = {}
    seat(student, batch, allocate)
    run()
    assert email_of(student) in drive.groups[group_of(batch)]
    assert sync_jobs(batch)[0].state == "Succeeded"


def test_a_trainer_without_a_google_account_is_invited(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    drive.no_google.add(people["g1"].email.lower())
    seat(student, batch, allocate)
    run()
    mine = [c for c in drive.calls if c["body"] and c["body"].get("emailAddress") == people["g1"].email.lower()]
    assert [c["params"]["sendNotificationEmail"] for c in mine] == ["false", "true"]
    assert (people["g1"].email.lower(), "writer") in live()


def test_a_folder_made_before_a_lost_reply_is_found_not_duplicated(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    drive.folders[f"nipuna-lms:batch:{batch.branch_id}:{batch.batch_id}"] = "folder-existing"
    seat(student, batch, allocate)
    run()
    assert batch.batch_code not in [c["body"]["name"] for c in drive.of("POST") if c["body"] and "name" in c["body"] and "appProperties" in c["body"]]
    item = db.session.execute(select(GoogleDriveItem).where(GoogleDriveItem.entity_type == "batch")).scalar_one()
    assert item.folder_id == "folder-existing"


def test_one_failed_group_change_is_retried_and_the_rest_is_kept(world, allocate, make_student, drive):  # noqa: F811
    people, batch, student = world
    other = make_student()
    seat(student, batch, allocate)
    seat(other, batch, allocate)
    # folders: 3 lookups + 3 creates, the group, listing its members, then the first member fails
    drive.fail = [None] * 8 + [GoogleError("Google returned 503", status=503, retryable=True)]
    assert run() == {"done": 0, "retry": 1, "dead": 0}
    assert len(drive.groups[group_of(batch)]) == 1  # the second student went in
    [job] = sync_jobs(batch)
    assert job.state == "Failed" and "1 share change(s) failed" in job.last_error
    assert (group_of(batch), "reader") in live()  # the share with the group was still made
    job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert run()["done"] == 1
    assert set(drive.groups[group_of(batch)]) == {email_of(student), email_of(other)}


def test_when_the_retries_run_out_the_branch_managers_are_told(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    drive.fail = [GoogleError("Google refused the service account")]
    assert run() == {"done": 0, "retry": 0, "dead": 1}
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert any(t.startswith("Drive sharing failed") for t in titles)

"""Google Workspace slice 3 (docs/GOOGLE_WORKSPACE.md §5.2): a batch's Drive folder, shared with its trainers and the students
holding a seat. Drive is faked: no test reaches Google."""
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import GoogleDriveGrant, GoogleDriveItem, GoogleJob, Notification
from services import allocations, batches as batches_service, integrations
from services.google import client as google_client
from services.google import jobs
from services.google.client import GoogleError
from tests.test_delivery import world  # noqa: F401


class FakeDrive:
    """Stands in for client.request, answering like Drive and remembering every call."""

    def __init__(self):
        self.calls, self.folders, self.permissions = [], {}, {}  # folders: lms_key -> id; permissions: id -> (folder, email, role)
        self.no_google = set()  # addresses Drive can only invite
        self.fail = []  # errors to raise on the next calls, first in first out
        self.counter = 0

    def of(self, method, suffix=None):
        return [c for c in self.calls if c["method"] == method and (suffix is None or c["url"].endswith(suffix))]

    def __call__(self, method, url, *, subject, scopes, body=None, params=None):
        self.calls.append({"method": method, "url": url, "subject": subject, "scopes": scopes, "body": body, "params": params})
        if self.fail:
            error = self.fail.pop(0)
            if error is not None:
                raise error
        self.counter += 1
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
            self.permissions[f"perm-{self.counter}"] = (folder, body["emailAddress"], body["role"])
            return {"id": f"perm-{self.counter}"}
        if method == "DELETE":
            self.permissions.pop(url.rsplit("/", 1)[1], None)
            return {}
        raise AssertionError(f"unexpected {method} {url}")


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
    verify_drive(make_user(roles=[("SUPER_ADMIN", None)]))
    return fake


def seat(student, batch, allocate):
    return allocate(student, batch)


def sync_jobs(batch):
    db.session.expire_all()
    return list(db.session.execute(select(GoogleJob).where(GoogleJob.kind == "DRIVE_SYNC", GoogleJob.entity_id == batch.batch_id)
                                   .order_by(GoogleJob.job_id)).scalars())


def live():
    db.session.expire_all()
    return {(g.grantee_email, g.role) for g in db.session.execute(select(GoogleDriveGrant).where(GoogleDriveGrant.revoked_at.is_(None))).scalars()}


def run():
    return jobs.run_due()


# ---------------------------------------------------------------- the switch

def test_nothing_is_queued_while_drive_is_off(world, allocate):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    assert sync_jobs(batch) == []


# ---------------------------------------------------------------- folders and shares

def test_a_seat_makes_the_folders_and_shares_the_batch(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    assert [j.state for j in sync_jobs(batch)] == ["Queued"]
    assert run() == {"done": 1, "retry": 0, "dead": 0}

    made = [c["body"]["name"] for c in drive.of("POST", "/files")]
    assert made == ["Nipuna LMS", batch.course.title, batch.batch_code]  # branch, course, batch, top down
    assert all(c["scopes"] == [google_client.DRIVE_SCOPE] for c in drive.calls)
    parents = [c["body"].get("parents") for c in drive.of("POST", "/files")]
    assert parents[0] is None and parents[1] == [drive.folders[f"nipuna-lms:branch:{batch.branch_id}:{batch.branch_id}"]]
    assert live() == {(people["g1"].email.lower(), "writer"), (student_email(student), "reader")}
    assert {c["body"]["role"] for c in drive.of("POST", None) if "emailAddress" in (c["body"] or {})} == {"writer", "reader"}
    assert all(c["params"]["sendNotificationEmail"] == "false" for c in drive.calls if c["body"] and "emailAddress" in c["body"])
    items = db.session.execute(select(GoogleDriveItem.entity_type)).scalars().all()
    assert sorted(items) == ["batch", "branch", "course"]
    from repositories import google as google_repo
    assert google_repo.branch_config(batch.branch_id).drive_root_folder_id == drive.folders[f"nipuna-lms:branch:{batch.branch_id}:{batch.branch_id}"]


def student_email(student):
    return student.email.lower()


def test_a_second_pass_changes_nothing(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    before = len(drive.calls)
    from services.google import batch_folders
    batch_folders.enqueue_sync(batch.batch_id)
    assert run()["done"] == 1
    assert len(drive.calls) == before


def test_another_student_is_added_and_a_leaver_is_removed(world, allocate, make_student, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    other = make_student()
    seat(other, batch, allocate)
    run()
    assert (other.email.lower(), "reader") in live()

    from repositories import students as students_repo
    enrolment = next(e for e in students_repo.enrolments_of_student(student.student_id) if e.course_id == batch.course_id)
    allocations.end(enrolment, reason="Left")
    db.session.commit()
    run()
    assert (student_email(student), "reader") not in live() and (other.email.lower(), "reader") in live()
    assert len(drive.of("DELETE")) == 1
    revoked = db.session.execute(select(GoogleDriveGrant).where(GoogleDriveGrant.revoked_at.is_not(None))).scalars().all()
    assert [g.grantee_email for g in revoked] == [student_email(student)]


def test_a_transfer_moves_the_share_to_the_new_batch(world, allocate, make_batch, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    other = make_batch(1, trainers=[people["g2"]], state="Running")
    seat(student, other, allocate)  # the old seat ends as Transferred
    assert {j.entity_id for j in db.session.execute(select(GoogleJob).where(GoogleJob.state == "Queued")).scalars()} == {batch.batch_id, other.batch_id}
    run()
    folders = {i.entity_id: i.item_id for i in db.session.execute(select(GoogleDriveItem).where(GoogleDriveItem.entity_type == "batch")).scalars()}
    shares = {(g.item_id, g.grantee_email) for g in db.session.execute(select(GoogleDriveGrant).where(GoogleDriveGrant.revoked_at.is_(None))).scalars()}
    assert (folders[other.batch_id], student_email(student)) in shares
    assert (folders[batch.batch_id], student_email(student)) not in shares


def test_completing_the_batch_removes_the_students_but_not_the_trainer(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    batches_service._set_state(batch, "Completed", "Finished")
    db.session.commit()
    run()
    assert live() == {(people["g1"].email.lower(), "writer")}


def test_a_cancelled_batch_loses_everyone(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    from repositories import students as students_repo
    allocations.end(next(e for e in students_repo.enrolments_of_student(student.student_id) if e.course_id == batch.course_id))
    batches_service._set_state(batch, "Cancelled", "Not viable")
    db.session.commit()
    run()
    assert live() == set()


def test_a_trainer_assigned_later_gets_editor_access(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    run()
    from models import BatchTrainer
    db.session.add(BatchTrainer(batch_id=batch.batch_id, trainer_user_id=people["g2"].user_id, role="Co-trainer"))
    db.session.commit()
    from services.google import batch_folders
    batch_folders.enqueue_sync(batch.batch_id)
    run()
    assert (people["g2"].email.lower(), "writer") in live()


# ---------------------------------------------------------------- Google's quirks and failures

def test_an_address_without_a_google_account_is_invited(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    drive.no_google.add(student_email(student))
    seat(student, batch, allocate)
    run()
    mine = [c for c in drive.calls if c["body"] and c["body"].get("emailAddress") == student_email(student)]
    assert [c["params"]["sendNotificationEmail"] for c in mine] == ["false", "true"]
    assert (student_email(student), "reader") in live()


def test_a_folder_made_before_a_lost_reply_is_found_not_duplicated(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    drive.folders[f"nipuna-lms:batch:{batch.branch_id}:{batch.batch_id}"] = "folder-existing"
    seat(student, batch, allocate)
    run()
    assert batch.batch_code not in [c["body"]["name"] for c in drive.of("POST", "/files")]
    item = db.session.execute(select(GoogleDriveItem).where(GoogleDriveItem.entity_type == "batch")).scalar_one()
    assert item.folder_id == "folder-existing"


def test_one_failed_share_is_retried_and_the_others_are_kept(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    # folders: 3 lookups + 3 creates; then the shares
    drive.fail = [None] * 6 + [GoogleError("Google returned 503", status=503, retryable=True)]
    assert run() == {"done": 0, "retry": 1, "dead": 0}
    assert len(live()) == 1  # the second share went through
    [job] = sync_jobs(batch)
    assert job.state == "Failed" and "1 share change(s) failed" in job.last_error
    job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    before = len(drive.of("POST", None))
    assert run()["done"] == 1
    assert len(live()) == 2 and len(drive.of("POST", None)) == before + 1  # only the missing share was made


def test_when_the_retries_run_out_the_branch_managers_are_told(world, allocate, drive):  # noqa: F811
    people, batch, student = world
    seat(student, batch, allocate)
    drive.fail = [GoogleError("Google refused the service account")]
    assert run() == {"done": 0, "retry": 0, "dead": 1}
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert any(t.startswith("Drive sharing failed") for t in titles)

"""Content library: authoring, upload checks, review and release, versions, audience and access expiry, download policy."""
import io
import zipfile

import pytest
from sqlalchemy import select

from config.database import db
from models import ActivityEvent, AuditLog, Notification
from repositories import users as users_repo
from tests import library_helpers as h
from tests.library_helpers import API, auth, create_item, get, post, release_item, upload_data


@pytest.fixture
def world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql):
    return h.build_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql)


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def audit_actions(entity_id: str) -> list[str]:
    return list(db.session.execute(select(AuditLog.action).where(AuditLog.entity_id == entity_id).order_by(AuditLog.audit_id)).scalars())


# ---------------------------------------------------------------- authoring

def test_trainer_creates_a_draft_item_with_its_first_version(client, login, world):
    item = create_item(client, auth(login, world.people.t1), world, fields={"description": "Week 1"})
    assert item["item_code"].startswith("CNT-") and item["status"] == "Draft" and item["version_no"] == 1
    assert item["course"]["course_code"] == "NIT-CRS-047" and item["branch"]["branch_code"] == "NIT-GNT"
    assert item["topic"]["title"] == "OOP & Collections" and item["module"]["title"] == "Core Java"
    assert item["batch"]["batch_code"] == world.g1.batch_code
    assert item["owner"]["full_name"] == "Trainer One" and item["download_allowed"] is True
    assert item["versions"][0]["original_filename"] == "notes.pdf" and item["versions"][0]["file_size_bytes"] > 0
    assert audit_actions(item["item_code"]) == ["CONTENT_CREATED"]


def test_a_trainer_only_adds_content_for_batches_they_teach(client, login, world):
    other = auth(login, world.people.t2)
    body = create_item(client, other, world, expect=403)
    assert body["error"]["code"] == "FORBIDDEN"
    vij = create_item(client, auth(login, world.people.tv), world, expect=403)  # G1 belongs to Guntur
    assert vij["error"]["code"] == "FORBIDDEN"
    # Without a batch a trainer may still author for the course they teach (branch worked out from their batches)
    item = create_item(client, auth(login, world.people.t1), world, fields={"batch_id": ""})
    assert item["batch"] is None and item["branch"]["branch_code"] == "NIT-GNT"
    assert create_item(client, other, world, fields={"batch_id": ""}, expect=403)["error"]["code"] == "FORBIDDEN"


def test_students_and_branch_managers_cannot_author(client, login, world):
    assert create_item(client, auth(login, world.students.s1), world, expect=403)["error"]["code"] == "FORBIDDEN"
    assert create_item(client, auth(login, world.people.bm), world, expect=403)["error"]["code"] == "FORBIDDEN"


def test_super_admin_names_the_branch_when_there_is_no_batch(client, login, world):
    headers = auth(login, world.people.admin)
    body = create_item(client, headers, world, fields={"batch_id": ""}, expect=400)
    assert "branch_id" in body["error"]["details"]
    item = create_item(client, headers, world, fields={"batch_id": "", "branch_id": 1})
    assert item["branch"]["branch_id"] == 1


def test_placement_must_be_consistent(client, login, world):
    headers = auth(login, world.people.ac)
    assert create_item(client, headers, world, fields={"topic_id": 999999}, expect=400)["error"]["details"]["topic_id"]
    vij = create_item(client, headers, world, fields={"batch_id": world.v1.batch_id}, expect=403)  # AC Guntur, Vijayawada batch
    assert vij["error"]["code"] == "FORBIDDEN"
    assert create_item(client, headers, world, fields={"topic_id": "", "course_id": ""}, expect=400)["error"]["details"]["topic_id"]


def test_validation_of_title_type_and_source(client, login, world):
    headers = auth(login, world.people.t1)
    assert create_item(client, headers, world, title="", expect=400)["error"]["details"]["title"]
    assert create_item(client, headers, world, content_type="Video", expect=400)["error"]["details"]["content_type"]
    assert create_item(client, headers, world, filename=None, expect=400)["error"]["details"]["file"]
    link_with_file = create_item(client, headers, world, content_type="Link", url="https://example.test/a", expect=400)
    assert "file" in link_with_file["error"]["details"]
    no_url = create_item(client, headers, world, content_type="Link", filename=None, expect=400)
    assert no_url["error"]["details"]["url"] == ["Required"]
    ftp = create_item(client, headers, world, content_type="Link", filename=None, url="ftp://example.test/a", expect=400)
    assert "url" in ftp["error"]["details"]
    url_for_file = create_item(client, headers, world, url="https://example.test/a", expect=400)
    assert "url" in url_for_file["error"]["details"]


def test_a_link_is_added_by_address(client, login, world):
    item = create_item(client, auth(login, world.people.t1), world, title="scikit-learn docs", content_type="Video link",
                       filename=None, url="https://scikit-learn.org/stable/", fields={})
    assert item["storage_kind"] == "Link" and item["url"] == "https://scikit-learn.org/stable/"
    assert item["download_allowed"] is False and item["versions"][0]["file_size_bytes"] is None


@pytest.mark.parametrize("filename,content,message", [
    ("virus.exe", b"MZ....", "File type not allowed"),
    ("fake.pdf", b"this is not a pdf", "does not look like a real .pdf"),
    ("empty.txt", b"", "The file is empty"),
    ("nb.ipynb", b"not json", "not valid JSON"),
    ("nb2.ipynb", b'{"metadata": {}}', "no cells"),
    ("bad.zip", b"PK\x03\x04garbage", "damaged"),
])
def test_uploads_are_checked_before_they_are_kept(client, login, world, filename, content, message):
    body = create_item(client, auth(login, world.people.t1), world, filename=filename, content=content, expect=400)
    assert message in body["error"]["details"]["file"][0]


def test_oversized_and_unsafe_uploads_are_rejected(client, login, world, run_sql):
    headers = auth(login, world.people.t1)
    run_sql("UPDATE app_settings SET setting_value = '1' WHERE setting_key = 'content_max_upload_mb'")
    big = create_item(client, headers, world, filename="big.pdf", content=b"%PDF-" + b"0" * (1024 * 1024 + 10), expect=400)
    assert "1 MB limit" in big["error"]["details"]["file"][0]
    dataset = create_item(client, headers, world, content_type="Dataset", filename="rows.csv", content=b"a,b\n" + b"1,2\n" * 400000)
    assert dataset["status"] == "Draft"  # datasets have their own, larger limit

    traversal = create_item(client, headers, world, filename="a.zip", content=zip_bytes({"../evil.txt": b"x"}), expect=400)
    assert "unsafe file path" in traversal["error"]["details"]["file"][0]
    nested = create_item(client, headers, world, filename="b.zip", content=zip_bytes({"inner.zip": b"PK"}), expect=400)
    assert "inside archives" in nested["error"]["details"]["file"][0]
    executable = create_item(client, headers, world, filename="c.zip", content=zip_bytes({"run.exe": b"MZ"}), expect=400)
    assert "not allowed" in executable["error"]["details"]["file"][0]
    bomb = create_item(client, headers, world, filename="d.zip", content=zip_bytes({"zeros.txt": b"0" * 5_000_000}), expect=400)
    assert "expands far more" in bomb["error"]["details"]["file"][0]
    fine = create_item(client, headers, world, content_type="Dataset", filename="e.zip", content=zip_bytes({"data/rows.csv": b"a,b\n1,2\n"}))
    assert fine["versions"][0]["original_filename"] == "e.zip"


def test_a_trainer_edits_a_draft_but_not_after_submitting(client, login, world):
    trainer = auth(login, world.people.t1)
    item = create_item(client, trainer, world)
    edited = client.patch(f"{API}/content-items/{item['content_item_id']}", headers=trainer,
                          json={"title": "Regression notes v0", "topic_id": world.topics.streams.topic_id, "download_allowed": False})
    assert edited.status_code == 200 and edited.get_json()["data"]["topic"]["title"] == "Streams & Lambdas"
    assert edited.get_json()["data"]["download_allowed"] is False
    post(client, f"/content-items/{item['content_item_id']}/submit", trainer)
    locked = client.patch(f"{API}/content-items/{item['content_item_id']}", headers=trainer, json={"title": "Sneaky"})
    assert locked.status_code == 422
    assert client.patch(f"{API}/content-items/{item['content_item_id']}", headers=trainer, json={}).status_code == 400
    other = client.patch(f"{API}/content-items/{item['content_item_id']}", headers=auth(login, world.people.t2), json={"title": "Mine"})
    assert other.status_code == 404  # not their item or batch: invisible


def test_a_reviewer_edit_is_audited_with_old_and_new_values(client, login, world):
    item = create_item(client, auth(login, world.people.t1), world)
    release_item(client, world, login, item["content_item_id"])
    response = client.patch(f"{API}/content-items/{item['content_item_id']}", headers=auth(login, world.people.ac),
                            json={"download_allowed": False})
    assert response.status_code == 200
    entry = db.session.execute(select(AuditLog).where(AuditLog.entity_id == item["item_code"], AuditLog.action == "CONTENT_UPDATED")).scalar_one()
    assert entry.old_values["download_allowed"] is True and entry.new_values["download_allowed"] is False


# ---------------------------------------------------------------- review and release

def test_review_flow_from_submission_to_release(client, login, world):
    trainer, coordinator = auth(login, world.people.t1), auth(login, world.people.ac)
    item = create_item(client, trainer, world, title="Decision trees slides")
    item_id = item["content_item_id"]

    submitted = post(client, f"/content-items/{item_id}/submit", trainer)
    assert submitted["status"] == "Submitted" and submitted["submitted_at"]
    assert client.post(f"{API}/content-items/{item_id}/submit", headers=trainer).status_code == 422  # already submitted
    queue = get(client, "/content-items?status=Submitted,Under%20Review", coordinator)
    assert [i["content_item_id"] for i in queue] == [item_id]
    # the coordinator was told and the notice needs action
    notice = db.session.execute(select(Notification).where(Notification.recipient_user_id == world.people.ac.user_id,
                                                           Notification.category == "Content")).scalar_one()
    assert notice.category == "Content" and notice.action_status == "Open" and notice.link == "/academic/content-review"

    assert post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "start"})["status"] == "Under Review"
    approved = post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "approve", "comment": "Good"})
    assert approved["status"] == "Approved" and approved["released_version_no"] is None
    released = post(client, f"/content-items/{item_id}/release", coordinator)
    assert released["status"] == "Released" and released["released_version_no"] == 1
    detail = get(client, f"/content-items/{item_id}", coordinator)
    assert [r["action"] for r in detail["reviews"]] == ["Submitted", "Review Started", "Approved", "Released"]
    assert audit_actions(item["item_code"]) == ["CONTENT_CREATED", "CONTENT_SUBMITTED", "CONTENT_REVIEWED", "CONTENT_REVIEWED", "CONTENT_RELEASED"]
    # the trainer was told about the decision
    titles = [n.title for n in db.session.execute(select(Notification).where(Notification.recipient_user_id == world.people.t1.user_id)).scalars()]
    assert "Decision trees slides: approved" in titles


def test_changes_requested_needs_a_comment_and_lets_the_trainer_resubmit(client, login, world):
    trainer, coordinator = auth(login, world.people.t1), auth(login, world.people.ac)
    item_id = create_item(client, trainer, world)["content_item_id"]
    post(client, f"/content-items/{item_id}/submit", trainer)
    missing = client.post(f"{API}/content-items/{item_id}/review", headers=coordinator, json={"decision": "request_changes"})
    assert missing.status_code == 400 and "comment" in missing.get_json()["error"]["details"]
    changed = post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "request_changes", "comment": "Add examples"})
    assert changed["status"] == "Changes Requested"
    assert [r["comment"] for r in get(client, f"/content-items/{item_id}", trainer)["reviews"]][-1] == "Add examples"
    # the trainer uploads a corrected version and resubmits it
    version = client.post(f"{API}/content-items/{item_id}/versions", headers=trainer, content_type="multipart/form-data",
                          data=upload_data(filename="notes-v2.pdf", change_summary="Examples added"))
    assert version.status_code == 201 and version.get_json()["data"]["version_no"] == 2
    assert post(client, f"/content-items/{item_id}/submit", trainer)["status"] == "Submitted"
    rejected = post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "reject", "comment": "Not aligned"})
    assert rejected["status"] == "Rejected"
    assert client.post(f"{API}/content-items/{item_id}/release", headers=coordinator).status_code == 422


def test_reviewers_cannot_review_their_own_upload_or_other_branches(client, login, world):
    coordinator = auth(login, world.people.ac)
    own = create_item(client, coordinator, world)
    post(client, f"/content-items/{own['content_item_id']}/submit", coordinator)
    refused = client.post(f"{API}/content-items/{own['content_item_id']}/review", headers=coordinator, json={"decision": "approve"})
    assert refused.status_code == 422 and "uploaded" in refused.get_json()["error"]["message"]
    # a second coordinator (or the Super Admin) can
    assert post(client, f"/content-items/{own['content_item_id']}/review", auth(login, world.people.ac2), json={"decision": "approve"})["status"] == "Approved"

    theirs = create_item(client, auth(login, world.people.t1), world)
    post(client, f"/content-items/{theirs['content_item_id']}/submit", auth(login, world.people.t1))
    assert client.post(f"{API}/content-items/{theirs['content_item_id']}/review", headers=auth(login, world.people.ac_vij),
                       json={"decision": "approve"}).status_code == 404
    assert client.post(f"{API}/content-items/{theirs['content_item_id']}/review", headers=auth(login, world.people.t1),
                       json={"decision": "approve"}).status_code == 403
    assert client.post(f"{API}/content-items/{theirs['content_item_id']}/review", headers=auth(login, world.people.bm),
                       json={"decision": "approve"}).status_code == 403
    assert post(client, f"/content-items/{theirs['content_item_id']}/review", auth(login, world.people.admin), json={"decision": "approve"})["status"] == "Approved"


def test_only_submitted_content_can_be_reviewed_and_only_approved_can_be_released(client, login, world):
    trainer, coordinator = auth(login, world.people.t1), auth(login, world.people.ac)
    item_id = create_item(client, trainer, world)["content_item_id"]
    assert client.post(f"{API}/content-items/{item_id}/review", headers=coordinator, json={"decision": "approve"}).status_code == 422
    assert client.post(f"{API}/content-items/{item_id}/release", headers=coordinator).status_code == 422
    assert client.post(f"{API}/content-items/{item_id}/review", headers=coordinator, json={"decision": "sign-off"}).status_code == 400
    post(client, f"/content-items/{item_id}/submit", trainer)
    post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "start"})
    assert client.post(f"{API}/content-items/{item_id}/review", headers=coordinator, json={"decision": "start"}).status_code == 422


# ---------------------------------------------------------------- versions

def test_a_new_version_keeps_the_released_one_until_it_is_released(client, login, world):
    trainer, coordinator, student = auth(login, world.people.t1), auth(login, world.people.ac), auth(login, world.students.s1)
    item = create_item(client, trainer, world, title="SQL cheatsheet")
    item_id = item["content_item_id"]
    release_item(client, world, login, item_id)

    v2 = client.post(f"{API}/content-items/{item_id}/versions", headers=trainer, content_type="multipart/form-data",
                     data=upload_data(filename="cheatsheet-v2.pdf", change_summary="More window functions")).get_json()["data"]
    assert v2["version_no"] == 2 and v2["status"] == "Draft" and v2["released_version_no"] == 1
    assert [v["status"] for v in v2["versions"]] == ["Released", "Draft"]
    seen = get(client, "/me/resources", student)
    assert [(r["title"], r["version_no"]) for r in seen] == [("SQL cheatsheet", 1)]  # still v1 for students

    post(client, f"/content-items/{item_id}/submit", trainer)
    blocked = client.post(f"{API}/content-items/{item_id}/versions", headers=trainer, content_type="multipart/form-data",
                          data=upload_data(filename="x.pdf"))
    assert blocked.status_code == 422  # waiting for review
    post(client, f"/content-items/{item_id}/review", coordinator, json={"decision": "approve", "release": True})
    detail = get(client, f"/content-items/{item_id}", trainer)
    assert [v["status"] for v in detail["versions"]] == ["Retired", "Released"]  # v1 kept, retired
    assert get(client, "/me/resources", student)[0]["version_no"] == 2
    assert detail["versions"][0]["original_filename"] == "notes.pdf"
    student_user = users_repo.get_by_student_id(world.students.s1.student_id)
    notices = [n.title for n in db.session.execute(select(Notification).where(Notification.recipient_user_id == student_user.user_id,
                                                                                                  Notification.category == "Content")).scalars()]
    assert notices.count("New material: SQL cheatsheet") == 2  # once per released version


def test_a_version_must_match_the_item_source(client, login, world):
    trainer = auth(login, world.people.t1)
    link = create_item(client, trainer, world, content_type="Link", filename=None, url="https://example.test/a", fields={})
    response = client.post(f"{API}/content-items/{link['content_item_id']}/versions", headers=trainer, content_type="multipart/form-data",
                           data=upload_data(filename="a.pdf"))
    assert response.status_code == 400  # a link is replaced by an address, not a file
    updated = client.post(f"{API}/content-items/{link['content_item_id']}/versions", headers=trainer, json={"url": "https://example.test/b"})
    assert updated.status_code == 201 and updated.get_json()["data"]["url"] == "https://example.test/b"


# ---------------------------------------------------------------- student audience

def test_students_see_only_released_items_of_their_own_enrolments(client, login, world):
    trainer = auth(login, world.people.t1)
    draft = create_item(client, trainer, world, title="Draft only")
    batch_item = create_item(client, trainer, world, title="For batch G1")
    course_wide = create_item(client, trainer, world, title="For the course", fields={"batch_id": ""})
    vij_item = create_item(client, auth(login, world.people.tv), world, title="Vijayawada notes", fields={"batch_id": world.v1.batch_id})
    for item in (batch_item, course_wide):
        release_item(client, world, login, item["content_item_id"])
    release_item(client, world, login, vij_item["content_item_id"], trainer=world.people.tv, coordinator=world.people.ac_vij)

    def titles(who):
        return sorted(r["title"] for r in get(client, "/me/resources", auth(login, who)))

    assert titles(world.students.s1) == ["For batch G1", "For the course"]
    assert titles(world.students.s2) == ["For the course"]  # enrolled but not allocated to G1
    assert titles(world.students.s3) == ["Vijayawada notes"]  # Vijayawada branch, its own batch
    for student in (world.students.s2, world.students.s3):
        assert client.post(f"{API}/content-items/{batch_item['content_item_id']}/open", headers=auth(login, student)).status_code == 404
    assert client.post(f"{API}/content-items/{draft['content_item_id']}/open", headers=auth(login, world.students.s1)).status_code == 404
    assert client.get(f"{API}/content-items/{batch_item['content_item_id']}/file", headers=auth(login, world.students.s2)).status_code == 404


def test_student_resources_filters_and_entry_shape(client, login, world):
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    pdf = create_item(client, trainer, world, title="Regression notes")
    sheet = create_item(client, trainer, world, title="Streams cheatsheet", content_type="Notes", filename="sheet.md", content=b"# hi",
                        fields={"topic_id": world.topics.streams.topic_id})
    for item in (pdf, sheet):
        release_item(client, world, login, item["content_item_id"])

    entries = get(client, "/me/resources", student)
    assert len(entries) == 2
    entry = next(e for e in entries if e["title"] == "Regression notes")
    assert entry["course"]["course_code"] == "NIT-CRS-047" and entry["topic"]["title"] == "OOP & Collections"
    assert entry["access"] == {"state": "Available", "expiry": "2027-03-02", "extended": False}
    assert entry["enrolment"]["enrolment_code"] and entry["download_allowed"] is True and "url" not in entry
    assert [e["title"] for e in get(client, f"/me/resources?content_type=Notes", student)] == ["Streams cheatsheet"]
    assert [e["title"] for e in get(client, f"/me/resources?topic_id={world.topics.streams.topic_id}", student)] == ["Streams cheatsheet"]
    assert [e["title"] for e in get(client, "/me/resources?q=regress", student)] == ["Regression notes"]
    assert get(client, f"/me/resources?module_id={world.module.module_id}", student)
    assert client.get(f"{API}/me/resources?content_type=Video", headers=student).status_code == 400
    assert client.get(f"{API}/me/resources", headers=trainer).status_code == 403


def test_retiring_withdraws_the_item_from_students_and_keeps_the_files(client, login, world):
    trainer, coordinator, student = auth(login, world.people.t1), auth(login, world.people.ac), auth(login, world.students.s1)
    item = create_item(client, trainer, world)
    item_id = item["content_item_id"]
    release_item(client, world, login, item_id)
    assert len(get(client, "/me/resources", student)) == 1

    assert client.post(f"{API}/content-items/{item_id}/retire", headers=coordinator, json={}).status_code == 400
    retired = post(client, f"/content-items/{item_id}/retire", coordinator, json={"reason": "Superseded by the new syllabus"})
    assert retired["status"] == "Retired" and retired["retire_reason"] and retired["versions"][0]["original_filename"] == "notes.pdf"
    assert get(client, "/me/resources", student) == []
    assert client.post(f"{API}/content-items/{item_id}/open", headers=student).status_code == 404
    assert client.post(f"{API}/content-items/{item_id}/submit", headers=trainer).status_code == 422
    assert audit_actions(item["item_code"])[-1] == "CONTENT_RETIRED"
    assert client.post(f"{API}/content-items/{item_id}/retire", headers=coordinator, json={"reason": "again"}).status_code == 422


# ---------------------------------------------------------------- open, files, download policy, expiry

def test_opening_a_resource_records_learning_activity(client, login, world):
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    item = create_item(client, trainer, world, title="Docs", content_type="Link", filename=None, url="https://example.test/docs", fields={})
    release_item(client, world, login, item["content_item_id"])
    opened = post(client, f"/content-items/{item['content_item_id']}/open", student)
    assert opened["url"] == "https://example.test/docs" and opened["storage_kind"] == "Link"
    event = db.session.execute(select(ActivityEvent).where(ActivityEvent.kind == "resource_view")).scalar_one()
    assert event.student_id == world.students.s1.student_id and event.detail["content_item_id"] == item["content_item_id"]
    assert event.enrolment_id is not None
    # staff previews do not count as student activity
    post(client, f"/content-items/{item['content_item_id']}/open", trainer)
    assert len(list(db.session.execute(select(ActivityEvent).where(ActivityEvent.kind == "resource_view")).scalars())) == 1
    # a link has no file
    assert client.get(f"{API}/content-items/{item['content_item_id']}/file", headers=student).status_code == 422


def test_file_retrieval_respects_the_download_policy(client, login, world):
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    allowed = create_item(client, trainer, world, title="Handout")
    locked = create_item(client, trainer, world, title="View only", fields={"download_allowed": "false"})
    for item in (allowed, locked):
        release_item(client, world, login, item["content_item_id"])

    inline = client.get(f"{API}/content-items/{allowed['content_item_id']}/file", headers=student)
    assert inline.status_code == 200 and inline.data.startswith(b"%PDF") and inline.headers["Content-Type"].startswith("application/pdf")
    assert "attachment" not in inline.headers.get("Content-Disposition", "") and inline.headers["X-Content-Type-Options"] == "nosniff"
    download = client.get(f"{API}/content-items/{allowed['content_item_id']}/file?download=true", headers=student)
    assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]

    assert client.get(f"{API}/content-items/{locked['content_item_id']}/file", headers=student).status_code == 200  # view in browser
    refused = client.get(f"{API}/content-items/{locked['content_item_id']}/file?download=true", headers=student)
    assert refused.status_code == 403
    assert client.get(f"{API}/content-items/{locked['content_item_id']}/file?download=true", headers=trainer).status_code == 200  # staff


def test_only_safe_types_are_shown_in_the_browser(client, login, world):
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    item = create_item(client, trainer, world, title="Starter", content_type="Code", filename="starter.py", content=b"print('hi')\n")
    release_item(client, world, login, item["content_item_id"])
    response = client.get(f"{API}/content-items/{item['content_item_id']}/file", headers=student)
    assert response.status_code == 200 and "attachment" in response.headers["Content-Disposition"]
    assert response.headers["Content-Type"] == "application/octet-stream"  # uploaded code is only ever downloaded, never run or rendered


def test_access_window_pending_available_and_expired(client, login, world, run_sql):
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    item = create_item(client, trainer, world)
    release_item(client, world, login, item["content_item_id"])
    item_id = item["content_item_id"]

    assert get(client, "/me/resources", student)[0]["access"]["expiry"] == "2027-03-02"
    # 29 February joining date: anniversary falls on 1 March in a non-leap year
    run_sql("UPDATE enrolments SET joining_date = '2028-02-29' WHERE student_id = :s", s=world.students.s1.student_id)
    assert get(client, "/me/resources", student)[0]["access"]["expiry"] == "2029-03-01"

    # No Joining Date yet: pending, but the material can still be opened
    run_sql("UPDATE enrolments SET status = 'Allocated — awaiting first regular class', joining_date = NULL WHERE student_id = :s",
            s=world.students.s1.student_id)
    entry = get(client, "/me/resources", student)[0]
    assert entry["access"] == {"state": "Pending", "expiry": None, "extended": False}
    assert client.post(f"{API}/content-items/{item_id}/open", headers=student).status_code == 200

    # After the first anniversary the material is listed as Expired and cannot be opened or downloaded
    run_sql("UPDATE enrolments SET status = 'Active', joining_date = :d WHERE student_id = :s", d=h.days_ago(400), s=world.students.s1.student_id)
    assert get(client, "/me/resources", student)[0]["access"]["state"] == "Expired"
    expired = client.post(f"{API}/content-items/{item_id}/open", headers=student)
    assert expired.status_code == 422 and "ended on" in expired.get_json()["error"]["message"]
    assert client.get(f"{API}/content-items/{item_id}/file", headers=student).status_code == 422


def test_withdrawn_enrolments_grant_nothing(client, login, world, run_sql):
    item = create_item(client, auth(login, world.people.t1), world)
    release_item(client, world, login, item["content_item_id"])
    run_sql("UPDATE enrolments SET status = 'Withdrawn' WHERE student_id = :s", s=world.students.s1.student_id)
    assert get(client, "/me/resources", auth(login, world.students.s1)) == []


# ---------------------------------------------------------------- staff scope

def test_staff_see_content_by_branch_authorship_and_batch(client, login, world):
    item = create_item(client, auth(login, world.people.t1), world, title="Guntur item")
    other = create_item(client, auth(login, world.people.tv), world, title="Vijayawada item", fields={"batch_id": world.v1.batch_id})

    def titles(who):
        return sorted(i["title"] for i in get(client, "/content-items", auth(login, who)))

    assert titles(world.people.t1) == ["Guntur item"]
    assert titles(world.people.t2) == []  # neither author nor teaching the batch
    assert titles(world.people.tv) == ["Vijayawada item"]
    assert titles(world.people.ac) == ["Guntur item"] and titles(world.people.bm) == ["Guntur item"]
    assert titles(world.people.ac_vij) == ["Vijayawada item"]
    assert titles(world.people.admin) == ["Guntur item", "Vijayawada item"] == titles(world.people.founder)
    for who, expected in ((world.people.t2, 404), (world.people.ac_vij, 404), (world.people.bm, 200), (world.people.founder, 200)):
        assert client.get(f"{API}/content-items/{item['content_item_id']}", headers=auth(login, who)).status_code == expected
    assert client.get(f"{API}/content-items", headers=auth(login, world.students.s1)).status_code == 403
    assert client.get(f"{API}/content-items/{other['content_item_id']}/file", headers=auth(login, world.people.t1)).status_code == 404


def test_list_filters_and_pagination(client, login, world):
    trainer = auth(login, world.people.t1)
    for index in range(3):
        create_item(client, trainer, world, title=f"Item {index}")
    create_item(client, trainer, world, title="A dataset", content_type="Dataset", filename="rows.csv", content=b"a,b\n1,2\n")
    everything = client.get(f"{API}/content-items?per_page=2", headers=trainer).get_json()
    assert everything["meta"]["total"] == 4 and len(everything["data"]) == 2
    assert [i["title"] for i in get(client, "/content-items?content_type=Dataset", trainer)] == ["A dataset"]
    assert len(get(client, f"/content-items?batch_id={world.g1.batch_id}&status=Draft", trainer)) == 4
    assert get(client, "/content-items?status=Released", trainer) == []
    assert len(get(client, "/content-items?q=item", trainer)) == 3
    assert client.get(f"{API}/content-items?status=Live", headers=trainer).status_code == 400


def test_placement_options_list_batches_versions_and_topics(client, login, world):
    options = get(client, "/content-items/options", auth(login, world.people.t1))
    assert [o["batch"]["batch_code"] for o in options] == [world.g1.batch_code]
    versions = options[0]["versions"]
    assert versions[0]["version_label"] == "CV 5.1"
    assert [t["title"] for t in versions[0]["modules"][0]["topics"]] == ["OOP & Collections", "Streams & Lambdas"]
    assert len(get(client, "/content-items/options", auth(login, world.people.admin))) == 2
    assert client.get(f"{API}/content-items/options", headers=auth(login, world.students.s1)).status_code == 403

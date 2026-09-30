"""Assignments: authoring and scope, the student's states, versioned submissions and the review flow."""
import io

from sqlalchemy import select

from config.database import db
from models import AuditLog, Notification, Result
from tests.assessment_world import API, assignment_body, hours, iso, released_assignment, world  # noqa: F401 (fixtures)


def move_deadline(run_sql, assignment_id, due_hours, closes_hours=None):
    """Put the due time (and the end of the late window) relative to now, keeping the release well in the past."""
    run_sql("UPDATE assignments SET release_at = now() - interval '1000 hours', due_at = now() + make_interval(hours => :d), "
            "closes_at = now() + make_interval(hours => :c) WHERE assignment_id = :id",
            d=due_hours, c=closes_hours if closes_hours is not None else due_hours + 168, id=assignment_id)


def submit(client, world, who, assignment_id, **body):
    return client.post(f"{API}/assignments/{assignment_id}/submissions", json=body or {"body_text": "My work"}, headers=world.h[who])


def review(client, world, submission_id, who="g1", **body):
    return client.post(f"{API}/submissions/{submission_id}/review", json=body, headers=world.h[who])


# ---------------------------------------------------------------- authoring and scope

def test_trainer_creates_a_draft_that_students_cannot_see_until_it_is_released(client, world):
    created = client.post(f"{API}/assignments", json=assignment_body(world), headers=world.h["g1"])
    assert created.status_code == 201, created.get_json()
    assignment = created.get_json()["data"]
    assert assignment["status"] == "Draft" and assignment["assignment_code"].startswith("ASG-")
    assert assignment["topic"]["title"] == "OOP & Collections" and assignment["module"]["title"] == "Core Java"
    assert assignment["reviewer"]["full_name"] == "Trainer G1"
    assert assignment["closes_at"] > assignment["due_at"]  # the seven-day late window

    assert client.get(f"{API}/assignments", headers=world.h["s1"]).get_json()["data"] == []
    assert client.get(f"{API}/assignments/{assignment['assignment_id']}", headers=world.h["s1"]).status_code == 404

    released = client.post(f"{API}/assignments/{assignment['assignment_id']}/release", json={}, headers=world.h["g1"])
    assert released.status_code == 200 and released.get_json()["data"]["status"] == "Released"
    visible = client.get(f"{API}/assignments", headers=world.h["s1"]).get_json()["data"]
    assert [a["title"] for a in visible] == ["Regression on housing dataset"] and visible[0]["my"]["state"] == "Due"
    # Only the students of the batch: the other batch's student and the other branch see nothing
    assert client.get(f"{API}/assignments", headers=world.h["s3"]).get_json()["data"] == []
    assert client.get(f"{API}/assignments", headers=world.h["s4"]).get_json()["data"] == []

    notice = db.session.execute(select(Notification).where(Notification.event_key == f"assignment-released:{assignment['assignment_id']}")).scalars().all()
    assert len(notice) == 2  # s1 and s2, not s3 or s4
    assert db.session.execute(select(AuditLog).where(AuditLog.entity_type == "assignment", AuditLog.action == "release")).scalars().all()


def test_only_people_who_run_the_batch_can_create_assignments(client, world):
    body = assignment_body(world)
    assert client.post(f"{API}/assignments", json=body, headers=world.h["s1"]).status_code == 403
    assert client.post(f"{API}/assignments", json=body, headers=world.h["bm"]).status_code == 403  # the Branch Manager reads
    assert client.post(f"{API}/assignments", json=body, headers=world.h["g2"]).status_code == 404  # another batch's trainer
    assert client.post(f"{API}/assignments", json=body, headers=world.h["ac_vij"]).status_code == 404  # another branch
    assert client.post(f"{API}/assignments", json=body, headers=world.h["ac"]).status_code == 201
    assert client.post(f"{API}/assignments", json=body, headers=world.h["admin"]).status_code == 201
    assert client.post(f"{API}/assignments", json=body).status_code == 401


def test_assignment_validation(client, world):
    def create(**overrides):
        return client.post(f"{API}/assignments", json=assignment_body(world, **overrides), headers=world.h["g1"])

    assert create(due_at=iso(hours(-5))).status_code == 400  # before the (default now) release time
    assert create(max_marks=0).status_code == 400
    assert create(title="").status_code == 400
    assert create(closes_at=iso(hours(1))).status_code == 400  # before the due time
    assert create(reviewer_user_id=world.people["g2"].user_id).status_code == 400  # not a trainer of this batch
    assert create(topic_id=999999).status_code == 422  # the database rejects a topic of no course
    assert create(attachments=[{"name": "data", "url": "not a link"}]).status_code == 400
    assert client.post(f"{API}/assignments", json={"batch_id": world.batches["G1"].batch_id}, headers=world.h["g1"]).status_code == 400


def test_release_needs_a_due_time_in_the_future(client, world, run_sql):
    assignment = client.post(f"{API}/assignments", json=assignment_body(world), headers=world.h["g1"]).get_json()["data"]
    run_sql("UPDATE assignments SET release_at = now() - interval '10 hours', due_at = now() - interval '1 hour', closes_at = now() WHERE assignment_id = :id",
            id=assignment["assignment_id"])
    response = client.post(f"{API}/assignments/{assignment['assignment_id']}/release", json={}, headers=world.h["g1"])
    assert response.status_code == 422 and "due time" in response.get_json()["error"]["message"]


def test_a_released_assignment_only_takes_limited_changes_and_notifies_students(client, world, released_assignment):
    url = f"{API}/assignments/{released_assignment['assignment_id']}"
    assert client.patch(url, json={"max_marks": 50}, headers=world.h["g1"]).status_code == 422
    assert client.patch(url, json={"due_at": iso(hours(1))}, headers=world.h["g1"]).status_code == 422  # only later
    extended = client.patch(url, json={"due_at": iso(hours(96)), "brief": "Updated brief"}, headers=world.h["g1"])
    assert extended.status_code == 200 and extended.get_json()["data"]["brief"] == "Updated brief"
    assert db.session.execute(select(Notification).where(Notification.event_key.like("assignment-updated:%"))).scalars().first()
    old_new = db.session.execute(select(AuditLog).where(AuditLog.entity_type == "assignment", AuditLog.action == "update")).scalars().one()
    assert old_new.old_values["brief"] == "Build and evaluate a model." and old_new.new_values["brief"] == "Updated brief"
    # Reopening the submission window is the Academic Coordinator's call, with a reason
    reopen = {"closes_at": iso(hours(400))}
    assert client.patch(url, json={**reopen, "reason": "Outage"}, headers=world.h["g1"]).status_code == 400
    assert client.patch(url, json=reopen, headers=world.h["ac"]).status_code == 400
    assert client.patch(url, json={**reopen, "reason": "Platform outage on 30 Sep"}, headers=world.h["ac"]).status_code == 200


def test_withdrawing_needs_a_reason_and_hides_the_assignment(client, world, released_assignment):
    url = f"{API}/assignments/{released_assignment['assignment_id']}"
    assert client.post(f"{url}/withdraw", json={}, headers=world.h["g1"]).status_code == 400
    assert client.post(f"{url}/withdraw", json={"reason": "Wrong dataset"}, headers=world.h["g1"]).status_code == 200
    assert client.get(url, headers=world.h["s1"]).status_code == 404
    assert client.get(f"{API}/assignments", headers=world.h["s1"]).get_json()["data"] == []
    assert client.post(f"{url}/withdraw", json={"reason": "again"}, headers=world.h["g1"]).status_code == 422
    assert submit(client, world, "s1", released_assignment["assignment_id"]).status_code == 404


def test_staff_lists_are_scoped_and_carry_counts(client, world, released_assignment):
    listed = client.get(f"{API}/assignments", headers=world.h["g1"]).get_json()["data"]
    assert [a["assignment_id"] for a in listed] == [released_assignment["assignment_id"]]
    assert listed[0]["counts"] == {"submitted": 0, "awaiting_review": 0, "reviewed": 0, "resubmission_requested": 0}
    assert listed[0]["can_manage"] is True
    assert client.get(f"{API}/assignments", headers=world.h["g2"]).get_json()["data"] == []
    assert len(client.get(f"{API}/assignments", headers=world.h["bm"]).get_json()["data"]) == 1
    bm_view = client.get(f"{API}/assignments", headers=world.h["bm"]).get_json()["data"][0]
    assert bm_view["can_manage"] is False
    assert client.get(f"{API}/assignments/{released_assignment['assignment_id']}", headers=world.h["g2"]).status_code == 404
    assert client.get(f"{API}/assignments/{released_assignment['assignment_id']}", headers=world.h["ac_vij"]).status_code == 404
    assert client.get(f"{API}/assignments?batch_id={world.batches['G1'].batch_id}", headers=world.h["g2"]).status_code == 404


# ---------------------------------------------------------------- student states

def test_task_states_follow_the_due_time(client, world, released_assignment, run_sql):
    assignment_id = released_assignment["assignment_id"]

    def state():
        return client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]["state"]

    move_deadline(run_sql, assignment_id, 24 * 10)
    assert state() == "Upcoming"
    move_deadline(run_sql, assignment_id, 24)
    assert state() == "Due"
    move_deadline(run_sql, assignment_id, -2)
    assert state() == "Overdue"
    filtered = client.get(f"{API}/assignments?state=Overdue", headers=world.h["s1"]).get_json()["data"]
    assert [a["assignment_id"] for a in filtered] == [assignment_id]
    assert client.get(f"{API}/assignments?state=Due", headers=world.h["s1"]).get_json()["data"] == []
    assert client.get(f"{API}/assignments?state=Nonsense", headers=world.h["s1"]).status_code == 400


# ---------------------------------------------------------------- submissions

def test_submissions_are_versioned_and_replacement_stops_at_the_deadline(client, world, released_assignment, run_sql):
    assignment_id = released_assignment["assignment_id"]
    first = submit(client, world, "s1", assignment_id, body_text="v1 notes", link_url="https://github.com/s1/housing")
    assert first.status_code == 201, first.get_json()
    v1 = first.get_json()["data"]
    assert v1["version_no"] == 1 and v1["attempt_no"] == 1 and v1["submission_code"].startswith("SUB-") and v1["is_late"] is False

    second = submit(client, world, "s1", assignment_id, body_text="v2 notes").get_json()["data"]
    assert second["version_no"] == 2 and second["attempt_no"] == 1  # a pre-review replacement is the same attempt
    assert [v["version_no"] for v in second["versions"]] == [1, 2]
    detail = client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]
    assert detail["state"] == "Submitted" and len(detail["versions"]) == 2

    move_deadline(run_sql, assignment_id, -1)  # the deadline passes
    late = submit(client, world, "s1", assignment_id, body_text="too late to replace")
    assert late.status_code == 422 and "resubmission" in late.get_json()["error"]["message"]
    assert client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]["state"] == "Submitted"


def test_a_first_submission_after_the_due_time_is_late_until_the_window_closes(client, world, released_assignment, run_sql):
    assignment_id = released_assignment["assignment_id"]
    move_deadline(run_sql, assignment_id, -5, 100)
    late = submit(client, world, "s1", assignment_id)
    assert late.status_code == 201 and late.get_json()["data"]["is_late"] is True

    move_deadline(run_sql, assignment_id, -200, -20)
    closed = submit(client, world, "s2", assignment_id)
    assert closed.status_code == 422 and "reopen" in closed.get_json()["error"]["message"]
    window = client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s2"]).get_json()["data"]["my"]["window"]
    assert window["allowed"] is False and window["mode"] is None


def test_submission_content_and_scope_rules(client, world, released_assignment):
    assignment_id = released_assignment["assignment_id"]
    assert client.post(f"{API}/assignments/{assignment_id}/submissions", json={}, headers=world.h["s1"]).status_code == 400
    assert submit(client, world, "s1", assignment_id, link_url="ftp://nope").status_code == 400
    assert submit(client, world, "s3", assignment_id).status_code == 404  # a student of another batch
    assert submit(client, world, "s4", assignment_id).status_code == 404
    assert submit(client, world, "g1", assignment_id).status_code == 403  # staff do not submit
    assert client.post(f"{API}/assignments/{assignment_id}/submissions", json={"body_text": "x"}).status_code == 401

    mine = submit(client, world, "s1", assignment_id, body_text="private work").get_json()["data"]
    assert client.get(f"{API}/submissions/{mine['submission_id']}", headers=world.h["s2"]).status_code == 404  # another student
    assert client.get(f"{API}/submissions/{mine['submission_id']}", headers=world.h["g2"]).status_code == 404  # another batch's trainer
    assert client.get(f"{API}/submissions/{mine['submission_id']}", headers=world.h["g1"]).status_code == 200
    assert client.get(f"{API}/submissions/{mine['submission_id']}", headers=world.h["bm"]).status_code == 200
    assert client.get(f"{API}/submissions", headers=world.h["s1"]).status_code == 403


def test_file_submission_is_stored_and_only_its_owner_and_the_batch_staff_can_download_it(client, world, released_assignment):
    assignment_id = released_assignment["assignment_id"]
    upload = client.post(f"{API}/assignments/{assignment_id}/submissions", headers=world.h["s1"], content_type="multipart/form-data",
                         data={"file": (io.BytesIO(b"select 1;"), "answers.sql"), "body_text": "see file"})
    assert upload.status_code == 201, upload.get_json()
    submission = upload.get_json()["data"]
    assert submission["file"]["filename"] == "answers.sql" and submission["file"]["size_bytes"] == 9

    url = f"{API}/submissions/{submission['submission_id']}/file"
    assert client.get(url, headers=world.h["s1"]).data == b"select 1;"
    assert client.get(url, headers=world.h["g1"]).status_code == 200
    assert client.get(url, headers=world.h["s2"]).status_code == 404
    assert client.get(url, headers=world.h["g2"]).status_code == 404

    bad = client.post(f"{API}/assignments/{assignment_id}/submissions", headers=world.h["s1"], content_type="multipart/form-data",
                      data={"file": (io.BytesIO(b"MZ"), "run.exe")})
    assert bad.status_code == 400
    empty = client.post(f"{API}/assignments/{assignment_id}/submissions", headers=world.h["s1"], content_type="multipart/form-data",
                        data={"file": (io.BytesIO(b""), "empty.txt")})
    assert empty.status_code == 400


# ---------------------------------------------------------------- review

def test_review_gives_provisional_marks_that_students_only_see_once_published(client, world, released_assignment):
    assignment_id = released_assignment["assignment_id"]
    sub = submit(client, world, "s1", assignment_id, body_text="analysis").get_json()["data"]
    submission_id = sub["submission_id"]

    queue = client.get(f"{API}/submissions?status=Awaiting Review&reviewer_me=true", headers=world.h["g1"]).get_json()["data"]
    assert [s["submission_id"] for s in queue] == [submission_id]
    assert client.get(f"{API}/submissions?status=Awaiting Review&reviewer_me=true", headers=world.h["g2"]).get_json()["data"] == []
    assert db.session.execute(select(Notification).where(Notification.event_key == f"submission:{submission_id}")).scalars().one().recipient_user_id \
        == world.people["g1"].user_id

    started = client.post(f"{API}/submissions/{submission_id}/start-review", headers=world.h["g1"])
    assert started.status_code == 200
    assert client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]["state"] == "Under Review"

    assert review(client, world, submission_id, outcome="Reviewed", feedback="Good work").status_code == 400  # no marks
    assert review(client, world, submission_id, outcome="Reviewed", feedback="Good work", marks=25).status_code == 400  # over the maximum
    assert review(client, world, submission_id, who="g2", outcome="Reviewed", feedback="x", marks=10).status_code == 404
    assert review(client, world, submission_id, who="s1", outcome="Reviewed", feedback="x", marks=10).status_code == 403
    assert review(client, world, submission_id, who="bm", outcome="Reviewed", feedback="x", marks=10).status_code == 403

    reviewed = review(client, world, submission_id, outcome="Reviewed", feedback="Good partitioning", marks=18)
    assert reviewed.status_code == 201, reviewed.get_json()
    assert review(client, world, submission_id, outcome="Reviewed", feedback="again", marks=19).status_code == 409

    result = db.session.execute(select(Result).where(Result.assignment_id == assignment_id)).scalars().one()
    assert result.status == "Provisional" and float(result.provisional_marks) == 18.0

    # Still provisional: the student sees neither the marks nor the feedback, only that it is under review
    mine = client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]
    assert mine["state"] == "Under Review" and mine["result"]["marks"] is None
    assert mine["versions"][0]["review"] is None
    staff = client.get(f"{API}/submissions/{submission_id}", headers=world.h["g1"]).get_json()["data"]
    assert staff["review"]["marks"] == "18.00" and staff["review"]["feedback"] == "Good partitioning"

    # After the coordinator publishes, the student gets both
    published = client.post(f"{API}/results/publish", json={"assignment_id": assignment_id}, headers=world.h["ac"])
    assert published.status_code == 200 and published.get_json()["data"]["published"] == 1
    mine = client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]
    assert mine["state"] == "Reviewed" and mine["result"] == {"status": "Published", "marks": "18.00", "max_marks": "20.00"}
    assert mine["versions"][0]["review"]["feedback"] == "Good partitioning" and mine["versions"][0]["review"]["marks"] == "18.00"


def test_resubmission_request_keeps_history_and_is_limited(client, world, released_assignment):
    assignment_id = released_assignment["assignment_id"]
    v1 = submit(client, world, "s1", assignment_id, body_text="first try").get_json()["data"]
    no_deadline = review(client, world, v1["submission_id"], outcome="Resubmission Requested", feedback="Redo the split")
    assert no_deadline.status_code == 400
    past = review(client, world, v1["submission_id"], outcome="Resubmission Requested", feedback="Redo", resubmission_due_at=iso(hours(-1)))
    assert past.status_code == 400
    asked = review(client, world, v1["submission_id"], outcome="Resubmission Requested", feedback="Redo the split", resubmission_due_at=iso(hours(72)))
    assert asked.status_code == 201

    mine = client.get(f"{API}/assignments/{assignment_id}", headers=world.h["s1"]).get_json()["data"]["my"]
    assert mine["state"] == "Resubmission Requested" and mine["window"]["mode"] == "resubmission"
    assert mine["versions"][0]["review"]["feedback"] == "Redo the split"  # the request's feedback is shown at once
    assert db.session.execute(select(Notification).where(Notification.event_key == f"resubmission:{v1['submission_id']}")).scalars().one()
    assert db.session.execute(select(Result).where(Result.assignment_id == assignment_id)).first() is None  # no marks yet

    v2 = submit(client, world, "s1", assignment_id, body_text="second try").get_json()["data"]
    assert v2["version_no"] == 2 and v2["attempt_no"] == 2 and v2["is_late"] is False
    v2_review = review(client, world, v2["submission_id"], outcome="Resubmission Requested", feedback="Almost", resubmission_due_at=iso(hours(72)))
    assert v2_review.status_code == 201
    v3 = submit(client, world, "s1", assignment_id, body_text="third try").get_json()["data"]
    assert v3["attempt_no"] == 3  # the second (and last) authorised resubmission
    limit = review(client, world, v3["submission_id"], outcome="Resubmission Requested", feedback="Again?", resubmission_due_at=iso(hours(72)))
    assert limit.status_code == 422 and "resubmission" in limit.get_json()["error"]["message"]
    assert review(client, world, v3["submission_id"], outcome="Reviewed", feedback="Fine", marks=15).status_code == 201

    old_version = client.get(f"{API}/submissions/{v1['submission_id']}", headers=world.h["g1"]).get_json()["data"]
    assert old_version["body_text"] == "first try" and len(old_version["versions"]) == 3


def test_only_the_newest_version_can_be_reviewed_and_a_resubmission_needs_its_deadline(client, world, released_assignment, run_sql):
    assignment_id = released_assignment["assignment_id"]
    v1 = submit(client, world, "s1", assignment_id, body_text="v1").get_json()["data"]
    v2 = submit(client, world, "s1", assignment_id, body_text="v2").get_json()["data"]
    older = review(client, world, v1["submission_id"], outcome="Reviewed", feedback="x", marks=5)
    assert older.status_code == 422 and "newest" in older.get_json()["error"]["message"]

    review(client, world, v2["submission_id"], outcome="Resubmission Requested", feedback="Redo", resubmission_due_at=iso(hours(24)))
    run_sql("UPDATE submission_reviews SET resubmission_due_at = now() - interval '1 hour' WHERE submission_id = :id", id=v2["submission_id"])
    expired = submit(client, world, "s1", assignment_id, body_text="late redo")
    assert expired.status_code == 422 and "deadline" in expired.get_json()["error"]["message"]


def test_database_refuses_marks_over_the_maximum_and_edits_to_a_submitted_version(client, world, released_assignment, run_sql):
    from sqlalchemy.exc import DBAPIError
    import pytest

    submission = submit(client, world, "s1", released_assignment["assignment_id"]).get_json()["data"]
    with pytest.raises(DBAPIError, match="cannot exceed"):
        run_sql("INSERT INTO submission_reviews (submission_id, reviewer_user_id, outcome, feedback, marks) VALUES (:s, :u, 'Reviewed', 'x', 99)",
                s=submission["submission_id"], u=world.people["g1"].user_id)
    db.session.rollback()
    with pytest.raises(DBAPIError, match="cannot be changed"):
        run_sql("UPDATE assignment_submissions SET body_text = 'edited' WHERE submission_id = :s", s=submission["submission_id"])
    db.session.rollback()


def test_curriculum_options_list_the_modules_a_batch_can_link_to(client, world):
    url = f"{API}/assessments/curriculum?batch_id={world.batches['G1'].batch_id}"
    options = client.get(url, headers=world.h["g1"]).get_json()["data"]
    assert [m["title"] for m in options] == ["Core Java"] and [t["title"] for t in options[0]["topics"]] == ["OOP & Collections", "Streams"]
    assert client.get(url, headers=world.h["g2"]).status_code == 404
    assert client.get(url, headers=world.h["s1"]).status_code == 403

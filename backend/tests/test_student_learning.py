"""UX phase U8: topic progress (Done rules), My Learning cards, module percentages, the topic hub, Home's "Up next", the
batch-change banner and the preferred-slot rule."""
from datetime import datetime, timedelta, timezone

from config.database import db
from models import ActivityEvent, AssignmentSubmission, AttendanceRecord, MaterialChange
from tests.assessment_world import API, released_assignment, world  # noqa: F401 (fixtures)
from tests.conftest import _commit
from tests.test_batches_delivery import confirmed_batch, seat
from tests.test_delivery import call, data, world as delivery_world  # noqa: F401


def enrolment_id(student) -> int:
    return student.enrolments[0]["enrolment_id"]


def taught(make_session, world, topic, *, student="s1", status="Present", days_ago=1, title="Taught class"):
    """A delivered class of G1 on `topic`, with the student's attendance marked."""
    start = datetime.now(timezone.utc) - timedelta(days=days_ago)
    session = make_session(world.batches["G1"], world.people["g1"], start, state="Delivered", delivered_at=start + timedelta(hours=2),
                           topic_id=topic.topic_id, title=title)
    if status:
        db.session.add(AttendanceRecord(session_id=session.session_id, enrolment_id=enrolment_id(world.students[student]), status=status,
                                        marked_by=world.people["g1"].user_id))
        _commit()
    return session


def progress_of(client, world, who="s1"):
    response = client.get(f"{API}/me/enrolments", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"][0]


def hub(client, world, topic, who="s1"):
    response = client.get(f"{API}/me/topics/{topic.topic_id}", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def home(client, world, who="s1"):
    response = client.get(f"{API}/me/home", headers=world.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def hand_in(world, assignment_id, student="s1"):
    s = world.students[student]
    db.session.add(AssignmentSubmission(assignment_id=assignment_id, enrolment_id=enrolment_id(s), student_id=s.student_id, version_no=1,
                                        body_text="My answer"))
    _commit()


# ---------------------------------------------------------------- when a topic is Done

def test_a_topic_nobody_has_taught_is_not_started(client, world):
    card = progress_of(client, world)
    assert card["topics"] == {"done": 0, "total": 2, "percent": 0}
    assert card["continue_topic"]["title"] == "OOP & Collections" and card["continue_topic"]["status"] == "Not started"


def test_attending_the_class_finishes_a_topic_with_no_required_work(client, world, make_session):
    taught(make_session, world, world.topics[0])

    card = progress_of(client, world)

    assert card["topics"] == {"done": 1, "total": 2, "percent": 50}
    assert card["continue_topic"]["title"] == "Streams"  # on to the next topic


def test_an_absence_does_not_finish_the_topic(client, world, make_session):
    taught(make_session, world, world.topics[0], status="Absent")

    assert progress_of(client, world)["topics"]["done"] == 0


def test_required_work_must_be_handed_in_before_the_topic_is_done(client, world, make_session, released_assignment):
    taught(make_session, world, world.topics[0])
    assert hub(client, world, world.topics[0])["progress"]["status"] == "Work to hand in"
    assert progress_of(client, world)["topics"]["done"] == 0

    hand_in(world, released_assignment["assignment_id"])

    assert hub(client, world, world.topics[0])["progress"]["status"] == "Done"
    assert progress_of(client, world)["topics"]["done"] == 1


def test_work_for_one_student_does_not_finish_a_topic_for_another(client, world, make_session, released_assignment):
    taught(make_session, world, world.topics[0], student="s1")
    taught(make_session, world, world.topics[0], student="s2", title="Same class, s2")
    hand_in(world, released_assignment["assignment_id"], "s1")

    assert hub(client, world, world.topics[0], "s1")["progress"]["status"] == "Done"
    assert hub(client, world, world.topics[0], "s2")["progress"]["status"] == "Work to hand in"


def test_watching_the_recording_finishes_a_topic_without_the_class(client, world, make_session, run_sql):
    session = taught(make_session, world, world.topics[0], status=None)  # delivered, attendance never marked
    run_sql("INSERT INTO recordings (session_id, status, media_ref, released_at) VALUES (:s, 'Released', 'drive-file-1', now())", s=session.session_id)
    recording_id = db.session.execute(db.text("SELECT recording_id FROM recordings WHERE session_id = :s"), {"s": session.session_id}).scalar_one()
    assert progress_of(client, world)["topics"]["done"] == 0

    db.session.add(ActivityEvent(student_id=world.students["s1"].student_id, enrolment_id=enrolment_id(world.students["s1"]),
                                 kind="recording_view", detail={"recording_id": recording_id}))
    _commit()

    assert progress_of(client, world)["topics"]["done"] == 1


# ---------------------------------------------------------------- My Learning

def test_the_course_page_lists_modules_with_their_percent_and_topics_done(client, world, make_session):
    taught(make_session, world, world.topics[0])
    card = progress_of(client, world)

    detail = client.get(f"{API}/me/enrolments/{card['enrolment_id']}", headers=world.h["s1"]).get_json()["data"]

    (module,) = [m for m in detail["modules"] if m["module_id"] == world.module.module_id]
    assert (module["topic_count"], module["topics_done"], module["percent"]) == (2, 1, 50)
    assert detail["topics"]["percent"] == 50 and detail["continue_topic"]["title"] == "Streams"


def test_the_module_page_shows_each_topics_status_to_the_learner_only(client, world, make_session):
    taught(make_session, world, world.topics[0])

    page = client.get(f"{API}/modules/{world.module.module_id}", headers=world.h["s1"]).get_json()["data"]
    staff = client.get(f"{API}/modules/{world.module.module_id}", headers=world.h["g1"]).get_json()["data"]

    assert [t["progress"]["status"] for t in page["topics"]] == ["Done", "Not started"]
    assert all(t["progress"] is None for t in staff["topics"])


# ---------------------------------------------------------------- the topic hub

def test_the_hub_gathers_class_work_and_the_next_topic(client, world, make_session, released_assignment):
    taught(make_session, world, world.topics[0])

    page = hub(client, world, world.topics[0])

    assert page["topic"]["title"] == "OOP & Collections" and page["module"]["title"] == "Core Java"
    assert [s["title"] for s in page["sessions"]] == ["Taught class"] and page["sessions"][0]["attendance"] == "Present"
    assert [a["assignment_id"] for a in page["assignments"]] == [released_assignment["assignment_id"]]
    assert page["assignments"][0]["my"]["state"] in ("Due", "Upcoming")
    assert page["next_topic"]["title"] == "Streams" and page["recordings"] == [] and page["materials"] == [] and page["tests"] == []
    assert hub(client, world, world.topics[1])["next_topic"] is None  # the last topic


def test_the_hub_is_for_students_of_that_course_only(client, world):
    topic = world.topics[0]
    assert client.get(f"{API}/me/topics/{topic.topic_id}", headers=world.h["g1"]).status_code == 403
    assert client.get(f"{API}/me/topics/{topic.topic_id}").status_code == 401
    assert client.get(f"{API}/me/topics/999999", headers=world.h["s1"]).status_code == 404


# ---------------------------------------------------------------- Home: Up next

def test_up_next_starts_with_the_next_topic(client, world):
    up = home(client, world)["up_next"]

    assert up["kind"] == "continue_topic" and up["title"] == "OOP & Collections" and up["topic_id"] == world.topics[0].topic_id


def test_up_next_prefers_work_due_today_over_the_next_topic(client, world, released_assignment, run_sql):
    run_sql("UPDATE assignments SET release_at = now() - interval '3 days', due_at = now() - interval '1 hour' WHERE assignment_id = :a",
            a=released_assignment["assignment_id"])

    up = home(client, world)["up_next"]

    assert up["kind"] == "work_due" and up["work"]["kind"] == "assignment" and up["work"]["id"] == released_assignment["assignment_id"]
    assert up["count"] == 1


def test_up_next_prefers_a_live_class_over_everything(client, world, make_session, released_assignment):
    now = datetime.now(timezone.utc)
    session = make_session(world.batches["G1"], world.people["g1"], now - timedelta(minutes=10), state="Live", title="Streams, live")

    up = home(client, world)["up_next"]

    assert up["kind"] == "live_class" and up["live"] is True and up["session_id"] == session.session_id and "join" in up


def test_up_next_falls_back_to_the_next_class_then_to_nothing(client, world, make_session, run_sql):
    # every topic Done: no topic to continue; a class in a week is the next thing
    for topic in world.topics:
        taught(make_session, world, topic, title=f"Taught {topic.title}")
    assert home(client, world)["up_next"] == {"kind": "nothing"}

    make_session(world.batches["G1"], world.people["g1"], datetime.now(timezone.utc) + timedelta(days=5), title="Revision")
    up = home(client, world)["up_next"]
    assert up["kind"] == "next_class" and up["title"] == "Revision"


def test_home_course_progress_counts_topics_and_keeps_delivery_separate(client, world, make_session):
    taught(make_session, world, world.topics[0])

    card = home(client, world)["course_progress"]

    assert card["topics"] == {"done": 1, "total": 2, "percent": 50}
    assert card["percent"] == 100  # curriculum delivery (one of one planned class) is its own measure


def test_continue_learning_points_at_the_next_topic_not_done(client, world, make_session):
    taught(make_session, world, world.topics[0])

    card = home(client, world)["continue_learning"]

    assert card["state"] == "Ready" and card["topic"]["title"] == "Streams" and card["basis"] == "Next topic"


# ---------------------------------------------------------------- Home: batch change banner and preferred slot

def test_a_batch_change_waiting_for_the_student_shows_with_a_reply_by_date(client, login, delivery_world, make_batch, make_student):  # noqa: F811
    people, _, student = delivery_world
    other = make_student()
    batch = confirmed_batch(client, login, people, make_batch)
    seat(client, login, people, batch, student)
    seat(client, login, people, batch, other)
    change = data(call(client, login, people["ac"], "post", f"/batches/{batch.batch_id}/material-changes", json={
        "kind": "Teaching days / times", "proposed_plan": "Tue, Thu 16:00–18:00", "reason": "Lab is booked at 15:00",
        "changes": {"start_time": "16:00", "end_time": "18:00"}}), 201)
    mine = lambda: data(call(client, login, student.student_code, "get", "/me/home"), 200)["batch_changes"]  # noqa: E731
    assert mine() == {"state": "Empty", "items": []}  # not approved yet: the student is not asked

    data(call(client, login, people["admin"], "post", f"/material-changes/{change['change_id']}/decision", json={"decision": "Approved"}), 200)

    (item,) = mine()["items"]
    assert item["change_id"] == change["change_id"] and item["proposed_plan"] == "Tue, Thu 16:00–18:00"
    reply_by = datetime.fromisoformat(item["reply_by"])
    assert timedelta(days=6, hours=23) < reply_by - datetime.now(timezone.utc) <= timedelta(days=7)
    assert db.session.get(MaterialChange, change["change_id"]).reply_by is not None

    data(call(client, login, student.student_code, "post", f"/me/material-changes/{change['change_id']}/response", json={"response": "Agreed"}), 200)
    assert mine() == {"state": "Empty", "items": []}  # answered: the banner goes


def test_the_preferred_slot_is_offered_only_to_a_student_waiting_for_a_batch(client, world, make_student, login):
    assert home(client, world)["needs_batch"] is False  # s1 holds a seat
    waiting = make_student()
    headers = {"Authorization": login(waiting.student_code)["Authorization"]}

    data_ = client.get(f"{API}/me/home", headers=headers).get_json()["data"]

    assert data_["needs_batch"] is True

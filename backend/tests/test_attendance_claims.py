"""A student says "I attended" an online class; the trainer's register stays the record and shows who said so."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from config.database import db
from config.timezone import IST
from models import AttendanceClaim, AttendanceRecord, AuditLog
from tests import attendance_world

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    world = attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)
    world.online = make_session(world.b1, world.t1, world.recent_start, state="Delivered", mode="Live Online", title="Online recap",
                                delivered_at=world.recent_start + timedelta(hours=2))
    world.older_online = make_session(world.b1, world.t1, world.older_start, state="Delivered", mode="Live Online", title="Old online",
                                      delivered_at=world.older_start + timedelta(hours=2))
    world.live_online = make_session(world.b1, world.t1, datetime.now(IST) - timedelta(minutes=20), state="Live", mode="Live Online", title="Live now")
    world.future_online = make_session(world.b1, world.t1, datetime.now(IST) + timedelta(days=2), mode="Live Online", title="Next week")
    return world


def confirm(client, w, who, session):
    return client.post(f"{API}/me/class-sessions/{session.session_id}/attendance-confirmation", headers=w.h[who])


def register(client, w, session, who="t1"):
    response = client.get(f"{API}/attendance/sessions/{session.session_id}", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


# ---------------------------------------------------------------- the student

def test_a_student_confirms_an_online_class_once(client, w):
    first = confirm(client, w, "s1", w.online)
    assert first.status_code == 200, first.get_json()
    again = confirm(client, w, "s1", w.online)
    assert again.status_code == 200 and again.get_json()["data"]["claimed_at"] == first.get_json()["data"]["claimed_at"]
    assert db.session.query(AttendanceClaim).count() == 1
    assert len(db.session.execute(select(AuditLog).where(AuditLog.action == "ATTENDANCE_CLAIMED")).scalars().all()) == 1
    assert db.session.query(AttendanceRecord).count() == 0  # a claim is never attendance


def test_a_class_in_progress_can_be_confirmed(client, w):
    assert confirm(client, w, "s1", w.live_online).status_code == 200


@pytest.mark.parametrize("which, fragment", [("future_online", "once the class has started"), ("older_online", "locked"),
                                             ("future", "marks the register in the room")])
def test_a_class_that_cannot_be_confirmed_says_why(client, w, which, fragment):
    response = confirm(client, w, "s1", getattr(w, which))
    assert response.status_code == 422 and fragment in response.get_json()["error"]["message"]


def test_a_classroom_class_cannot_be_confirmed(client, w):
    response = confirm(client, w, "s1", w.recent)  # delivered in the room
    assert response.status_code == 422 and "in the room" in response.get_json()["error"]["message"]


def test_a_student_already_marked_by_the_trainer_cannot_confirm(client, w):
    client.put(f"{API}/attendance/sessions/{w.online.session_id}", headers=w.h["t1"], json={"entries": [{"enrolment_id": w.e1, "status": "Absent"}]})
    response = confirm(client, w, "s1", w.online)
    assert response.status_code == 422 and "already marked you absent" in response.get_json()["error"]["message"]


def test_only_a_student_with_a_seat_can_confirm(client, w):
    assert confirm(client, w, "s3", w.online).status_code == 404  # seated in another batch
    assert client.post(f"{API}/me/class-sessions/{w.online.session_id}/attendance-confirmation", headers=w.h["t1"]).status_code == 403
    assert client.post(f"{API}/me/class-sessions/{w.online.session_id}/attendance-confirmation").status_code == 401
    assert confirm(client, w, "s1", type("S", (), {"session_id": 999999})).status_code == 404


def test_the_class_page_tells_the_student_what_they_can_do(client, w):
    def state(session):
        return client.get(f"{API}/class-sessions/{session.session_id}", headers=w.h["s1"]).get_json()["data"]["attendance_claim"]

    assert state(w.online) == {"can_confirm": True, "reason": None, "claimed_at": None}
    assert state(w.recent) is None  # a classroom class has nothing to confirm
    assert "started" in state(w.future_online)["reason"] and state(w.future_online)["can_confirm"] is False
    confirm(client, w, "s1", w.online)
    after = state(w.online)
    assert after["can_confirm"] is False and after["claimed_at"] and after["reason"] is None
    staff = client.get(f"{API}/class-sessions/{w.online.session_id}", headers=w.h["t1"]).get_json()["data"]
    assert "attendance_claim" not in staff


# ---------------------------------------------------------------- the trainer

def test_the_register_shows_who_confirmed(client, w):
    confirm(client, w, "s1", w.online)
    data = register(client, w, w.online)
    rows = {r["enrolment"]["enrolment_id"]: r for r in data["rows"]}
    assert rows[w.e1]["student_confirmed_at"] and rows[w.e2]["student_confirmed_at"] is None
    assert rows[w.e1]["attendance"] is None  # still not marked: the trainer decides
    assert data["summary"]["confirmed_by_student"] == 1


def test_the_trainer_confirms_the_claims_in_one_step_and_corrects_the_rest(client, w):
    confirm(client, w, "s1", w.online)
    done = client.put(f"{API}/attendance/sessions/{w.online.session_id}", headers=w.h["t1"], json={"from_confirmations": True})
    assert done.status_code == 200, done.get_json()
    rows = {r["enrolment"]["enrolment_id"]: r for r in done.get_json()["data"]["rows"]}
    assert rows[w.e1]["attendance"]["status"] == "Present" and rows[w.e1]["attendance"]["remarks"] == "Confirmed by the student"
    assert rows[w.e2]["attendance"] is None  # the student who did not say so is left for the trainer
    assert done.get_json()["data"]["summary"]["confirmed_by_student"] == 0  # nothing waiting any more

    # an explicit entry beats the claim
    confirm(client, w, "s2", w.online)
    mixed = client.put(f"{API}/attendance/sessions/{w.online.session_id}", headers=w.h["t1"],
                       json={"from_confirmations": True, "entries": [{"enrolment_id": w.e2, "status": "Absent", "remarks": "Not in the Meet"}]})
    rows = {r["enrolment"]["enrolment_id"]: r for r in mixed.get_json()["data"]["rows"]}
    assert rows[w.e2]["attendance"]["status"] == "Absent"


def test_with_no_claims_there_is_nothing_to_mark(client, w):
    nothing = client.put(f"{API}/attendance/sessions/{w.online.session_id}", headers=w.h["t1"], json={"from_confirmations": True})
    assert nothing.status_code == 400

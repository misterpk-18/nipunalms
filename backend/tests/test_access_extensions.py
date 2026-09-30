"""Access extension requests: the one extra year, timing rules, who decides, and the effect on materials and recordings."""
from datetime import date

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, Notification
from repositories import users as users_repo
from services import access
from tests import library_helpers as h
from tests.library_helpers import API, auth, create_item, get, post, release_item


@pytest.fixture
def world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql):
    return h.build_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql)


def request_extension(client, login, world, *, expect=201, scope="Both", reason="Need to revise for interviews", who=None):
    response = client.post(f"{API}/access-extension-requests", headers=auth(login, who or world.students.s1), json={
        "enrolment_id": world.students.s1.enrolments[0]["enrolment_id"], "scope": scope, "reason": reason})
    assert response.status_code == expect, response.get_json()
    return response.get_json()["data"] if expect == 201 else response.get_json()


def set_joining(run_sql, world, joining: str):
    run_sql("UPDATE enrolments SET joining_date = :d WHERE student_id = :s", d=joining, s=world.students.s1.student_id)


def test_anniversary_uses_first_march_for_a_leap_day():
    assert access.anniversary(date(2024, 2, 29), 1) == date(2025, 3, 1)
    assert access.anniversary(date(2024, 2, 29), 2) == date(2026, 3, 1)
    assert access.anniversary(date(2024, 2, 29), 4) == date(2028, 2, 29)
    assert access.anniversary(date(2026, 1, 12), 1) == date(2027, 1, 12)


def test_access_overview_shows_dates_and_what_can_be_requested(client, login, world):
    overview = get(client, "/me/access", auth(login, world.students.s1))
    assert len(overview) == 1
    row = overview[0]
    assert row["joining_date"] == "2026-03-02" and row["first_expiry"] == "2027-03-02" and row["second_expiry"] == "2028-03-02"
    assert row["recording"] == {"state": "Available", "expiry": "2027-03-02", "extended": False}
    assert row["can_request"] == {"Recording": True, "Material": True}
    assert get(client, "/me/access", auth(login, world.students.s2))[0]["can_request"] == {"Recording": False, "Material": False}  # not joined
    assert client.get(f"{API}/me/access", headers=auth(login, world.people.ac)).status_code == 403


def test_a_request_before_the_first_expiry_extends_to_the_second_anniversary(client, login, world):
    request = request_extension(client, login, world)
    assert request["request_code"].startswith("EXT-") and request["status"] == "Pending" and request["needs_exception"] is False
    assert request["original_expiry"] == "2027-03-02" and request["approved_expiry"] is None
    # the coordinator and the branch manager are told, with an action to take
    for who in (world.people.ac, world.people.bm):
        notice = db.session.execute(select(Notification).where(Notification.recipient_user_id == who.user_id,
                                                               Notification.category == "Access")).scalar_one()
        assert notice.action_status == "Open" and notice.link == "/branch/requests"

    decided = post(client, f"/access-extension-requests/{request['request_id']}/decision", auth(login, world.people.ac),
                   json={"decision": "approve", "note": "Verified"})
    assert decided["status"] == "Approved" and decided["approved_expiry"] == "2028-03-02" and decided["decided_by"]["full_name"] == "AC Guntur"
    row = get(client, "/me/access", auth(login, world.students.s1))[0]
    assert row["recording"] == {"state": "Available", "expiry": "2028-03-02", "extended": True} == row["material"]
    assert row["can_request"] == {"Recording": False, "Material": False}
    # the student is told and it is audited with old and new expiry
    student_user = users_repo.get_by_student_id(world.students.s1.student_id)
    notice = db.session.execute(select(Notification).where(Notification.recipient_user_id == student_user.user_id,
                                                           Notification.category == "Access")).scalar_one()
    assert "2028" in notice.body
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "ACCESS_EXTENSION_DECIDED")).scalar_one()
    assert entry.new_values["approved_expiry"] == "2028-03-02" and entry.old_values["expiry"]["Recording"] == "2027-03-02"


def test_repeated_requests_do_not_stack_years(client, login, world):
    first = request_extension(client, login, world)
    post(client, f"/access-extension-requests/{first['request_id']}/decision", auth(login, world.people.bm), json={"decision": "approve"})
    again = request_extension(client, login, world, expect=422)
    assert "Repeated requests do not add further years" in again["error"]["message"]


def test_scope_limits_the_extension_and_one_request_waits_at_a_time(client, login, world):
    recording = request_extension(client, login, world, scope="Recording")
    assert request_extension(client, login, world, scope="Both", expect=409)["error"]["code"] == "CONFLICT"  # overlaps the waiting one
    material = request_extension(client, login, world, scope="Material")  # a different kind is fine
    post(client, f"/access-extension-requests/{recording['request_id']}/decision", auth(login, world.people.ac), json={"decision": "approve"})
    row = get(client, "/me/access", auth(login, world.students.s1))[0]
    assert row["recording"]["extended"] is True and row["material"]["extended"] is False
    assert row["pending_requests"][0]["request_id"] == material["request_id"]
    assert request_extension(client, login, world, scope="Both", expect=422)  # recording already extended


def test_no_request_before_a_joining_date(client, login, world, run_sql):
    run_sql("UPDATE enrolments SET status = 'Allocated — awaiting first regular class', joining_date = NULL WHERE student_id = :s",
            s=world.students.s1.student_id)
    body = request_extension(client, login, world, expect=422)
    assert "Joining Date" in body["error"]["message"]


def test_a_request_after_the_first_expiry_restores_the_remaining_time(client, login, world, run_sql):
    set_joining(run_sql, world, h.days_ago(500))  # first anniversary passed, second still ahead
    trainer, student = auth(login, world.people.t1), auth(login, world.students.s1)
    item = create_item(client, trainer, world)
    release_item(client, world, login, item["content_item_id"])
    assert get(client, "/me/resources", student)[0]["access"]["state"] == "Expired"

    request = request_extension(client, login, world)
    assert request["needs_exception"] is False
    decided = post(client, f"/access-extension-requests/{request['request_id']}/decision", auth(login, world.people.ac), json={"decision": "approve"})
    joining = date.fromisoformat(h.days_ago(500))
    assert decided["approved_expiry"] == access.anniversary(joining, 2).isoformat()
    entry = get(client, "/me/resources", student)[0]
    assert entry["access"]["state"] == "Available" and entry["access"]["extended"] is True  # access is back
    assert client.post(f"{API}/content-items/{item['content_item_id']}/open", headers=student).status_code == 200


def test_after_the_second_anniversary_only_a_founder_or_super_admin_decides(client, login, world, run_sql):
    set_joining(run_sql, world, h.days_ago(900))
    request = request_extension(client, login, world)
    assert request["needs_exception"] is True
    path = f"/access-extension-requests/{request['request_id']}/decision"
    for who in (world.people.ac, world.people.bm):
        assert client.post(f"{API}{path}", headers=auth(login, who), json={"decision": "approve"}).status_code == 403
    admin = auth(login, world.people.admin)
    assert client.post(f"{API}{path}", headers=admin, json={"decision": "approve"}).status_code == 400  # new expiry needed
    assert client.post(f"{API}{path}", headers=admin, json={"decision": "approve", "new_expiry": h.days_ago(1)}).status_code == 400
    future = date.today().replace(year=date.today().year + 1).isoformat()
    granted = post(client, path, auth(login, world.people.founder), json={"decision": "approve", "new_expiry": future})
    assert granted["approved_expiry"] == future
    assert get(client, "/me/access", auth(login, world.students.s1))[0]["recording"]["expiry"] == future


def test_rejection_needs_a_reason_and_frees_the_student_to_ask_again(client, login, world):
    request = request_extension(client, login, world)
    path = f"/access-extension-requests/{request['request_id']}/decision"
    coordinator = auth(login, world.people.ac)
    assert client.post(f"{API}{path}", headers=coordinator, json={"decision": "reject"}).status_code == 400
    rejected = post(client, path, coordinator, json={"decision": "reject", "note": "Course still running"})
    assert rejected["status"] == "Rejected" and rejected["approved_expiry"] is None
    assert client.post(f"{API}{path}", headers=coordinator, json={"decision": "approve"}).status_code == 422  # already decided
    student_user = users_repo.get_by_student_id(world.students.s1.student_id)
    notice = db.session.execute(select(Notification).where(Notification.recipient_user_id == student_user.user_id,
                                                           Notification.category == "Access")).scalar_one()
    assert "Course still running" in notice.body
    assert request_extension(client, login, world)["status"] == "Pending"


def test_who_can_see_and_decide(client, login, world):
    request = request_extension(client, login, world)
    rid = request["request_id"]
    for who in (world.people.ac, world.people.bm, world.people.admin, world.people.founder):
        assert [r["request_id"] for r in get(client, "/access-extension-requests", auth(login, who))] == [rid]
        assert get(client, f"/access-extension-requests/{rid}", auth(login, who))["student"]["student_code"]
    for who in (world.people.ac_vij, world.people.bm_vij):  # another branch
        assert get(client, "/access-extension-requests", auth(login, who)) == []
        assert client.get(f"{API}/access-extension-requests/{rid}", headers=auth(login, who)).status_code == 404
        assert client.post(f"{API}/access-extension-requests/{rid}/decision", headers=auth(login, who), json={"decision": "approve"}).status_code == 404
    assert client.get(f"{API}/access-extension-requests", headers=auth(login, world.people.t1)).status_code == 403
    student = auth(login, world.students.s1)
    assert [r["request_id"] for r in get(client, "/access-extension-requests", student)] == [rid]
    assert client.post(f"{API}/access-extension-requests/{rid}/decision", headers=student, json={"decision": "approve"}).status_code == 403
    assert get(client, "/access-extension-requests", auth(login, world.students.s2)) == []  # only their own
    assert client.get(f"{API}/access-extension-requests/{rid}", headers=auth(login, world.students.s2)).status_code == 404
    assert len(get(client, "/access-extension-requests?status=Pending&scope=Both", auth(login, world.people.ac))) == 1
    assert get(client, "/access-extension-requests?status=Approved", auth(login, world.people.ac)) == []
    assert get(client, "/access-extension-requests?needs_exception=true", auth(login, world.people.ac)) == []


def test_request_validation(client, login, world):
    student = auth(login, world.students.s1)
    enrolment_id = world.students.s1.enrolments[0]["enrolment_id"]
    for body in ({}, {"enrolment_id": enrolment_id, "scope": "Video", "reason": "x"}, {"enrolment_id": enrolment_id, "scope": "Both", "reason": " "}):
        assert client.post(f"{API}/access-extension-requests", headers=student, json=body).status_code == 400
    other = world.students.s2.enrolments[0]["enrolment_id"]
    assert client.post(f"{API}/access-extension-requests", headers=student,
                       json={"enrolment_id": other, "scope": "Both", "reason": "x"}).status_code == 404  # not their enrolment
    assert client.post(f"{API}/access-extension-requests", headers=auth(login, world.people.ac),
                       json={"enrolment_id": enrolment_id, "scope": "Both", "reason": "x"}).status_code == 403

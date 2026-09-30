"""The notification centre: own notifications only, separate read / acknowledged / action states, counts and preferences."""
import pytest

from config.database import db
from models import Notification
from repositories import users as users_repo
from services.notifications import notify
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1/notifications"


@pytest.fixture
def inbox(world, run_sql):
    """Four notifications for student one (one needing action, one already completed, one WhatsApp message that was not
    sent) and one for student two."""
    s1 = users_repo.get_by_student_id(world.students.s1.student_id).user_id
    s2 = users_repo.get_by_student_id(world.students.s2.student_id).user_id
    notify(category="Assignment", title="Regression on housing dataset due 29 Sep", event_key="a1", recipient_user_ids=[s1],
           link="/assignments", action_required=True)
    notify(category="Recording", title="Recording for 24 Sep held for review", event_key="a2", recipient_user_ids=[s1])
    notify(category="Support", title="Support request SR-1019 resolved", event_key="a3", recipient_user_ids=[s1])
    notify(category="Session", title="Module test scheduled 03 Oct", event_key="a4", recipient_user_ids=[s2])
    run_sql("UPDATE notifications SET action_status = 'Completed', read_at = now(), acknowledged_at = now() WHERE event_key = 'a3'")
    run_sql("INSERT INTO notifications (recipient_user_id, category, title, event_key, channel, delivery_status, delivery_note) "
            "VALUES (:u, 'Session', 'WhatsApp reminder for class 28 Sep', 'a5', 'WhatsApp', 'Failed', 'Integration Pending Verification')",
            u=s1)
    return {"s1": s1, "s2": s2}


def titles(response):
    assert response.status_code == 200, response.get_json()
    return [n["title"] for n in response.get_json()["data"]]


def test_a_user_sees_only_their_own_notifications(client, world, inbox):
    mine = titles(client.get(API, headers=world.h(world.students.s1)))
    assert len(mine) == 4 and "Module test scheduled 03 Oct" not in mine
    assert titles(client.get(API, headers=world.h(world.students.s2))) == ["Module test scheduled 03 Oct"]
    assert titles(client.get(API, headers=world.h(world.people.t1))) == []


def test_views_split_by_state(client, world, inbox):
    h = world.h(world.students.s1)
    assert titles(client.get(f"{API}?view=action", headers=h)) == ["Regression on housing dataset due 29 Sep"]
    assert titles(client.get(f"{API}?view=completed", headers=h)) == ["Support request SR-1019 resolved"]
    assert titles(client.get(f"{API}?view=system", headers=h)) == ["WhatsApp reminder for class 28 Sep"]
    unread = titles(client.get(f"{API}?view=unread", headers=h))
    assert sorted(unread) == ["Recording for 24 Sep held for review", "Regression on housing dataset due 29 Sep"]
    assert titles(client.get(f"{API}?category=Recording", headers=h)) == ["Recording for 24 Sep held for review"]
    assert titles(client.get(f"{API}?q=housing", headers=h)) == ["Regression on housing dataset due 29 Sep"]
    assert client.get(f"{API}?view=nonsense", headers=h).status_code == 400


def test_each_notification_shows_its_delivery_state(client, world, inbox):
    rows = {n["title"]: n for n in client.get(API, headers=world.h(world.students.s1)).get_json()["data"]}
    assert rows["Regression on housing dataset due 29 Sep"]["delivery_label"] == "Delivered in-app"
    assert rows["WhatsApp reminder for class 28 Sep"]["delivery_label"] == "WhatsApp — Integration Pending Verification (not sent)"
    assert rows["WhatsApp reminder for class 28 Sep"]["delivery_status"] == "Failed"


def test_overview_counts_unread_and_open_actions(client, world, inbox):
    h = world.h(world.students.s1)
    assert client.get(f"{API}/overview", headers=h).get_json()["data"] == {
        "unread": 2, "action_required": 1, "categories": ["Assignment", "Recording", "Session", "Support"]}
    assert client.get(f"{API}/overview", headers=world.h(world.people.t1)).get_json()["data"]["unread"] == 0


def test_read_acknowledge_and_action_are_separate_states(client, world, inbox):
    h = world.h(world.students.s1)
    action = client.get(f"{API}?view=action", headers=h).get_json()["data"][0]
    url = f"{API}/{action['notification_id']}"

    read = client.post(f"{url}/read", headers=h).get_json()["data"]
    assert read["read_at"] and read["acknowledged_at"] is None and read["action_status"] == "Open"

    acknowledged = client.post(f"{url}/acknowledge", headers=h).get_json()["data"]
    assert acknowledged["acknowledged_at"] and acknowledged["action_status"] == "Open"    # acknowledging does not finish the task

    done = client.post(f"{url}/action-done", headers=h).get_json()["data"]
    assert done["action_status"] == "Completed"
    assert client.post(f"{url}/action-done", headers=h).status_code == 422                 # nothing left to complete
    assert client.get(f"{API}/overview", headers=h).get_json()["data"]["action_required"] == 0


def test_acknowledging_marks_it_read(client, world, inbox):
    h = world.h(world.students.s1)
    note = next(n for n in client.get(API, headers=h).get_json()["data"] if n["title"].startswith("Recording"))
    result = client.post(f"{API}/{note['notification_id']}/acknowledge", headers=h).get_json()["data"]
    assert result["read_at"] and result["acknowledged_at"]


def test_an_action_needs_an_open_action(client, world, inbox):
    h = world.h(world.students.s1)
    note = next(n for n in client.get(API, headers=h).get_json()["data"] if n["title"].startswith("Recording"))
    assert client.post(f"{API}/{note['notification_id']}/action-done", headers=h).status_code == 422


def test_someone_elses_notification_is_a_404(client, world, inbox):
    theirs = db.session.query(Notification).filter_by(event_key="a4").one().notification_id
    for action in ("read", "acknowledge", "action-done"):
        assert client.post(f"{API}/{theirs}/{action}", headers=world.h(world.students.s1)).status_code == 404


def test_mark_all_read(client, world, inbox):
    h = world.h(world.students.s1)
    assert client.post(f"{API}/read-all", headers=h).get_json()["data"] == {"marked": 2}    # the failed WhatsApp one is not "unread"
    assert client.get(f"{API}/overview", headers=h).get_json()["data"]["unread"] == 0
    assert client.get(f"{API}/overview", headers=world.h(world.students.s2)).get_json()["data"]["unread"] == 1


def test_the_bell_works_for_staff_too(client, world):
    notify(category="Support", title="New support request SR-1", event_key="s1", recipient_user_ids=[world.people.t1.user_id], action_required=True)
    db.session.commit()
    assert client.get(f"{API}/overview", headers=world.h(world.people.t1)).get_json()["data"]["action_required"] == 1


class TestPreferences:
    def test_defaults_show_in_app_on_and_external_channels_not_configured(self, client, world):
        data = client.get(f"{API}/preferences", headers=world.h(world.students.s1)).get_json()["data"]
        channels = {c["channel"]: c for c in data["channels"]}
        assert channels["In-app"]["always_on"] is True
        assert channels["WhatsApp"]["configuration_status"] == "Not Configured" and channels["WhatsApp"]["verification_status"] == "Not Verified"
        assert channels["Email"]["configuration_status"] == "Configuration Pending"
        groups = {g["group"]: g["settings"] for g in data["groups"]}
        assert set(groups) == {"Service", "Learning reminders", "Placement", "Promotions & alumni"}
        assert groups["Service"] == {"In-app": True, "WhatsApp": True, "Email": True}
        assert groups["Promotions & alumni"] == {"In-app": True, "WhatsApp": False, "Email": False}

    def test_preferences_are_saved_per_user(self, client, world):
        h = world.h(world.students.s1)
        response = client.put(f"{API}/preferences", headers=h, json={"preferences": [
            {"group": "Learning reminders", "channel": "WhatsApp", "enabled": True},
            {"group": "Service", "channel": "Email", "enabled": False}]})
        assert response.status_code == 200
        groups = {g["group"]: g["settings"] for g in response.get_json()["data"]["groups"]}
        assert groups["Learning reminders"]["WhatsApp"] is True and groups["Service"]["Email"] is False
        other = client.get(f"{API}/preferences", headers=world.h(world.students.s2)).get_json()["data"]["groups"]
        assert {g["group"]: g["settings"] for g in other}["Service"]["Email"] is True

    def test_in_app_cannot_be_turned_off(self, client, world):
        response = client.put(f"{API}/preferences", headers=world.h(world.students.s1),
                              json={"preferences": [{"group": "Placement", "channel": "In-app", "enabled": False}]})
        assert response.status_code == 400

    @pytest.mark.parametrize("body", [{}, {"preferences": []}, {"preferences": [{"group": "Nope", "channel": "Email", "enabled": True}]}])
    def test_invalid_input_is_rejected(self, client, world, body):
        assert client.put(f"{API}/preferences", headers=world.h(world.students.s1), json=body).status_code == 400


def test_the_database_keeps_failed_notifications_explained(run_sql, world):
    s1 = users_repo.get_by_student_id(world.students.s1.student_id).user_id
    with pytest.raises(Exception, match="notifications_failed_has_note"):
        run_sql("INSERT INTO notifications (recipient_user_id, category, title, event_key, delivery_status) "
                "VALUES (:u, 'x', 'x', 'k', 'Failed')", u=s1)


def test_login_is_required(client):
    assert client.get(API).status_code == 401


@pytest.mark.parametrize("who", ["ac", "bm", "admin", "founder"])
def test_every_staff_role_lists_and_acknowledges_only_its_own_notifications(client, world, who):
    me = getattr(world.people, who)
    other = world.people.bm_vij if who == "bm" else world.people.bm
    notify(category="Review", title="Mine", event_key=f"staff-mine-{who}", recipient_user_ids=[me.user_id], action_required=True)
    notify(category="Review", title="Theirs", event_key=f"staff-theirs-{who}", recipient_user_ids=[other.user_id])
    db.session.commit()
    h = world.h(me)

    seen = titles(client.get(API, headers=h))
    assert "Mine" in seen and "Theirs" not in seen
    mine = next(n for n in client.get(API, headers=h).get_json()["data"] if n["title"] == "Mine")
    assert client.get(f"{API}/overview", headers=h).get_json()["data"]["action_required"] >= 1
    assert client.post(f"{API}/{mine['notification_id']}/acknowledge", headers=h).get_json()["data"]["acknowledged_at"]

    theirs = db.session.query(Notification).filter_by(event_key=f"staff-theirs-{who}").one().notification_id
    for action in ("read", "acknowledge", "action-done"):
        assert client.post(f"{API}/{theirs}/{action}", headers=h).status_code == 404


def test_staff_profile_lists_roles_and_branch(client, world):
    data = client.get("/api/v1/me/profile", headers=world.h(world.people.bm)).get_json()["data"]
    assert data["student"] is None and [s["role_name"] for s in data["scopes"]] == ["Branch Manager"]

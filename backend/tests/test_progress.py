"""The four progress measures: Delivery, Attendance, Required learning, Engagement (never one blended score)."""
from datetime import datetime, timedelta, timezone

import pytest

from config.database import db
from config.timezone import IST
from models import ActivityEvent
from tests import attendance_world

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    return attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)


def measures(client, w, who="s1", enrolment_id=None):
    response = client.get(f"{API}/progress/enrolments/{enrolment_id or w.e1}", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def mark(client, w, session, entries=None, default_status=None, who="t1"):
    body = {"entries": entries or []}
    if default_status:
        body["default_status"] = default_status
    response = client.put(f"{API}/attendance/sessions/{session.session_id}", json=body, headers=w.h[who])
    assert response.status_code == 200, response.get_json()


def days_ago(n):
    return (datetime.now(IST) - timedelta(days=n)).replace(hour=10, minute=0, second=0, microsecond=0)


def add_activity(student, count, days_back=1, enrolment_id=None):
    for i in range(count):
        db.session.add(ActivityEvent(student_id=student.student_id, enrolment_id=enrolment_id, kind="login",
                                     occurred_at=datetime.now(timezone.utc) - timedelta(days=days_back, minutes=i)))
    db.session.commit()


def test_the_four_measures_are_separate_and_there_is_no_combined_score(client, w):
    data = measures(client, w)
    assert {"delivery", "attendance", "required_learning", "engagement"} <= set(data)
    assert not {"score", "overall", "overall_percent", "completion_percent"} & set(data)


def test_delivery_is_delivered_over_planned_sessions_of_the_batch(client, w):
    delivery = measures(client, w)["delivery"]
    assert (delivery["delivered_sessions"], delivery["planned_sessions"], delivery["percent"]) == (2, 3, 66.7)
    assert measures(client, w, "s3", w.e3)["delivery"]["planned_sessions"] == 0
    assert measures(client, w, "s3", w.e3)["delivery"]["percent"] is None  # not 0: nothing planned yet


def test_attendance_is_not_started_before_joining(client, w):
    attendance = measures(client, w)["attendance"]
    assert attendance["state"] == "Not started" and attendance["percent"] is None
    assert measures(client, w)["joining_date"] is None


def test_attendance_counts_present_and_late_since_joining_and_flags_partial_data(client, w):
    d1, d2, d4 = w.delivered(days_ago(3)), w.delivered(days_ago(2)), w.delivered(days_ago(1) + timedelta(hours=-2))
    mark(client, w, d1, [{"enrolment_id": w.e1, "status": "Present"}])
    mark(client, w, d2, [{"enrolment_id": w.e1, "status": "Absent"}])
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Late"}])

    attendance = measures(client, w)["attendance"]
    # w.older (20 days ago) is before the joining date, so it is neither a present nor an absent
    assert attendance["state"] == "Partial Data" and attendance["provisional"] is True
    assert (attendance["delivered_since_joining"], attendance["marked"], attendance["unmarked"]) == (4, 3, 1)
    assert (attendance["present"], attendance["late"], attendance["absent"]) == (1, 1, 1)
    assert attendance["percent"] == 66.7 and attendance["alert"] is True

    mark(client, w, d4, [{"enrolment_id": w.e1, "status": "Present"}])
    attendance = measures(client, w)["attendance"]
    assert attendance["state"] == "Calculated" and attendance["provisional"] is False
    assert attendance["percent"] == 75.0 and attendance["alert"] is False   # exactly at the threshold is not an alert
    assert attendance["alert_threshold"] == 75


def test_excused_counts_against_the_percentage_but_is_recorded_separately(client, w):
    sessions = [w.delivered(days_ago(n)) for n in (5, 4, 3)]
    mark(client, w, sessions[0], [{"enrolment_id": w.e1, "status": "Present"}])
    mark(client, w, sessions[1], [{"enrolment_id": w.e1, "status": "Excused", "remarks": "Medical certificate"}])
    mark(client, w, sessions[2], [{"enrolment_id": w.e1, "status": "Present"}])
    attendance = measures(client, w)["attendance"]
    assert attendance["excused"] == 1 and attendance["percent"] == 66.7


def test_alert_needs_three_marked_sessions_and_follows_the_threshold_setting(client, w, run_sql):
    a, b = w.delivered(days_ago(3)), w.delivered(days_ago(2))
    mark(client, w, a, [{"enrolment_id": w.e1, "status": "Present"}])
    mark(client, w, b, [{"enrolment_id": w.e1, "status": "Absent"}])
    assert measures(client, w)["attendance"]["alert"] is False               # only two marked so far
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Absent"}])
    assert measures(client, w)["attendance"]["alert"] is True                # 33% of three
    run_sql("UPDATE app_settings SET setting_value = '30' WHERE setting_key = 'attendance_alert_threshold'")
    assert measures(client, w)["attendance"]["alert"] is False


def test_required_learning_counts_topics_covered_by_attended_or_recovered_sessions(client, w):
    assert measures(client, w)["required_learning"] == {"required_topics": 3, "covered_topics": 0, "percent": 0.0}
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Present"}])          # topic 1 taught
    assert measures(client, w)["required_learning"]["covered_topics"] == 1

    third = w.delivered(days_ago(1) + timedelta(hours=-3), w.topics[2], "REST class")
    mark(client, w, third, [{"enrolment_id": w.e1, "status": "Absent"}])
    assert measures(client, w)["required_learning"]["covered_topics"] == 1         # absent: not covered
    rows = client.get(f"{API}/attendance/enrolments/{w.e1}", headers=w.h["s1"]).get_json()["data"]["rows"]
    absent = next(r for r in rows if r["session"]["session_code"] == third.session_code)["attendance_id"]
    rid = client.post(f"{API}/attendance/recoveries", json={"attendance_id": absent, "method": "Assignment", "reason": "Unwell"},
                      headers=w.h["s1"]).get_json()["data"]["recovery_id"]
    assert measures(client, w)["required_learning"]["covered_topics"] == 1         # a requested recovery is not enough
    client.post(f"{API}/attendance/recoveries/{rid}/decision", json={"decision": "Approved"}, headers=w.h["ac"])
    learning = measures(client, w)["required_learning"]
    assert learning["covered_topics"] == 2 and learning["percent"] == 66.7
    assert measures(client, w)["attendance"]["recovered"] == 1


@pytest.mark.parametrize("events, days_back, level, in_window", [
    (0, 1, "Not started", 0), (2, 1, "Low", 2), (3, 1, "Medium", 3), (8, 1, "High", 8), (5, 20, "Low", 0),
])
def test_engagement_levels_from_recent_activity(client, w, run_sql, events, days_back, level, in_window):
    run_sql("DELETE FROM activity_events")  # signing in during setup already logged some activity
    add_activity(w.s1, events, days_back)
    engagement = measures(client, w)["engagement"]
    assert engagement["level"] == level and engagement["events_in_window"] == in_window and engagement["window_days"] == 14
    assert (engagement["last_activity_at"] is None) == (events == 0)


def test_student_sees_only_their_own_progress(client, w):
    mine = client.get(f"{API}/me/progress", headers=w.h["s1"]).get_json()["data"]
    assert [b["enrolment"]["enrolment_id"] for b in mine] == [w.e1]
    assert mine[0]["batch"]["batch_code"] == w.b1.batch_code
    assert client.get(f"{API}/progress/enrolments/{w.e1}", headers=w.h["s2"]).status_code == 404
    assert client.get(f"{API}/progress/enrolments/{w.e1}", headers=w.h["t2"]).status_code == 404
    assert client.get(f"{API}/progress/enrolments/{w.e1}", headers=w.h["ac_v"]).status_code == 404
    assert client.get(f"{API}/progress/enrolments/999999", headers=w.h["ac"]).status_code == 404
    assert client.get(f"{API}/me/progress", headers=w.h["t1"]).status_code == 403
    assert client.get(f"{API}/progress/students", headers=w.h["s1"]).status_code == 403


def names(response):
    assert response.status_code == 200, response.get_json()
    return sorted(row["student"]["full_name"] for row in response.get_json()["data"])


def test_progress_table_is_scoped_and_filterable(client, w):
    mark(client, w, w.recent, default_status="Present")
    listing = f"{API}/progress/students"
    assert names(client.get(listing, headers=w.h["t1"])) == ["Anvitha K.", "Learner Two"]
    assert names(client.get(listing, headers=w.h["t2"])) == ["Other Batch Learner"]
    everyone = ["Anvitha K.", "Learner Two", "Other Batch Learner"]
    assert names(client.get(listing, headers=w.h["ac"])) == everyone
    assert names(client.get(listing, headers=w.h["admin"])) == everyone
    assert names(client.get(listing, headers=w.h["ac_v"])) == []
    assert names(client.get(f"{listing}?q=anvitha", headers=w.h["ac"])) == ["Anvitha K."]
    assert names(client.get(f"{listing}?batch_id={w.b1.batch_id}", headers=w.h["ac"])) == ["Anvitha K.", "Learner Two"]
    assert names(client.get(f"{listing}?alert=true", headers=w.h["ac"])) == []
    row = client.get(listing, headers=w.h["ac"]).get_json()["data"][0]
    assert {"student", "enrolment", "batch", "delivery", "attendance", "required_learning", "engagement"} <= set(row)


def test_progress_table_lists_alerts(client, w):
    first, *others = [w.delivered(days_ago(n)) for n in (4, 3, 2)]
    mark(client, w, first, default_status="Present")
    for session in others:
        mark(client, w, session, [{"enrolment_id": w.e1, "status": "Present"}, {"enrolment_id": w.e2, "status": "Absent"}])
    assert names(client.get(f"{API}/progress/students?alert=true", headers=w.h["ac"])) == ["Learner Two"]
    assert names(client.get(f"{API}/progress/students?alert=true", headers=w.h["t1"])) == ["Learner Two"]


def test_branch_summary_averages_each_measure_separately(client, w):
    mark(client, w, w.delivered(days_ago(3)), default_status="Present")
    mark(client, w, w.recent, [{"enrolment_id": w.e1, "status": "Present"}, {"enrolment_id": w.e2, "status": "Absent"}])
    summary = client.get(f"{API}/progress/summary", headers=w.h["bm"]).get_json()["data"]
    batch = next(b for b in summary["batches"] if b["batch"]["batch_code"] == w.b1.batch_code)
    assert batch["students"] == 2 and batch["avg_attendance"] == 75.0 and batch["avg_delivery"] == 75.0
    assert "certificates_by_status" in summary and "enrolments_by_status" in summary
    assert client.get(f"{API}/progress/summary?branch_id=2", headers=w.h["bm"]).status_code == 404
    assert client.get(f"{API}/progress/summary", headers=w.h["t1"]).status_code == 403
    assert client.get(f"{API}/progress/summary?branch_id=2", headers=w.h["admin"]).get_json()["data"]["batches"] == []
    assert client.get(f"{API}/progress/summary", headers=w.h["bm_v"]).get_json()["data"]["batches"] == []

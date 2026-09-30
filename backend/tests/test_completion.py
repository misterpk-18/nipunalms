"""Completion review: evidence, trainer recommendation, Academic Coordinator decision, effect on the enrolment."""
import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, Certificate, CompletionReview, Enrolment, Notification
from tests import attendance_world, helpers

API = attendance_world.API


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    return attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)


def start(client, w, enrolment_ids=None):
    """Mark the recent session Present for everyone, so the enrolments are Active."""
    response = client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    assert response.status_code == 200, response.get_json()


def open_review(client, w, who="t1", enrolment_id=None):
    return client.post(f"{API}/completion-reviews", json={"enrolment_id": enrolment_id or w.e1}, headers=w.h[who])


def decide(client, w, review_id, decision="Complete", reason=None, who="ac"):
    return client.post(f"{API}/completion-reviews/{review_id}/decision", json={"decision": decision, "reason": reason}, headers=w.h[who])


def enrolment(enrolment_id) -> Enrolment:
    db.session.expire_all()
    return db.session.get(Enrolment, enrolment_id)


def test_candidates_are_the_running_enrolments_with_their_evidence(client, w):
    listing = f"{API}/completion-reviews"
    assert client.get(listing, headers=w.h["ac"]).get_json()["data"] == []        # nobody has started yet
    start(client, w)
    rows = client.get(listing, headers=w.h["ac"]).get_json()["data"]
    assert [r["student"]["full_name"] for r in rows] == ["Anvitha K.", "Learner Two"]
    row = rows[0]
    assert {"delivery", "attendance", "required_learning", "engagement"} <= set(row["evidence"])
    assert row["review"] is None and row["can_open"] is True and row["can_decide"] is False
    assert row["certificate_status"] == "Not Yet Eligible" and row["batch"]["batch_code"] == w.b1.batch_code

    assert [r["student"]["full_name"] for r in client.get(listing, headers=w.h["t1"]).get_json()["data"]] == ["Anvitha K.", "Learner Two"]
    assert client.get(listing, headers=w.h["t2"]).get_json()["data"] == []
    assert client.get(listing, headers=w.h["ac_v"]).get_json()["data"] == []
    assert client.get(listing, headers=w.h["s1"]).status_code == 403
    assert len(client.get(f"{listing}?q=learner", headers=w.h["bm"]).get_json()["data"]) == 1


def test_opening_a_review_needs_a_running_enrolment_and_the_right_person(client, w):
    assert open_review(client, w).status_code == 422                            # still awaiting its first class
    start(client, w)
    assert open_review(client, w, "s1").status_code == 403
    assert open_review(client, w, "bm").status_code == 403
    assert open_review(client, w, "t2").status_code == 404
    assert open_review(client, w, "ac_v").status_code == 404
    created = open_review(client, w)
    assert created.status_code == 201 and created.get_json()["data"]["status"] == "Open"
    again = open_review(client, w, "ac")
    assert again.status_code == 200 and again.get_json()["data"]["review_id"] == created.get_json()["data"]["review_id"]


def test_trainer_recommendation_informs_but_does_not_decide(client, w):
    start(client, w)
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    url = f"{API}/completion-reviews/{review_id}/recommendation"
    assert client.post(url, json={"recommendation": "Not Yet"}, headers=w.h["t1"]).status_code == 400   # say what is missing
    ok = client.post(url, json={"recommendation": "Not Yet", "comment": "Capstone not submitted"}, headers=w.h["t1"])
    assert ok.status_code == 200 and ok.get_json()["data"]["trainer_recommendation"] == "Not Yet"
    assert client.post(url, json={"recommendation": "Complete"}, headers=w.h["t2"]).status_code == 404
    assert client.post(url, json={"recommendation": "Complete"}, headers=w.h["s1"]).status_code == 403
    assert enrolment(w.e1).status == "Active"
    told = db.session.execute(select(Notification).where(Notification.category == "Completion")).scalars().all()
    assert len(told) == 2 and all("Not Yet" in n.body for n in told)  # both Guntur coordinators


def test_only_the_coordinator_decides_and_reasons_are_required(client, w):
    start(client, w)
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    assert decide(client, w, review_id, who="t1").status_code == 403
    assert decide(client, w, review_id, who="bm").status_code == 403
    assert decide(client, w, review_id, who="ac_v").status_code == 404
    assert decide(client, w, review_id, "Not Yet").status_code == 400
    assert decide(client, w, review_id, "Needs Recovery", "").status_code == 400


def test_not_yet_keeps_the_enrolment_running_and_a_new_review_can_follow(client, w):
    start(client, w)
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    decided = decide(client, w, review_id, "Not Yet", "Two required topics still open")
    assert decided.status_code == 200
    data = decided.get_json()["data"]
    assert data["status"] == "Decided" and data["decision"] == "Not Yet" and data["evidence"]["attendance"]["percent"] == 100.0
    assert enrolment(w.e1).status == "Active"
    assert decide(client, w, review_id, "Complete").status_code == 409             # a decided review is final
    assert open_review(client, w).status_code == 201
    row = client.get(f"{API}/completion-reviews", headers=w.h["ac"]).get_json()["data"][0]
    assert row["review"]["status"] == "Open"


def test_complete_is_blocked_while_a_recovery_is_open(client, w):
    session = w.delivered(w.recent_start.replace(hour=15))
    start(client, w)
    client.put(f"{API}/attendance/sessions/{session.session_id}", json={"entries": [{"enrolment_id": w.e1, "status": "Absent"}]}, headers=w.h["t1"])
    attendance_id = next(r["attendance_id"] for r in client.get(f"{API}/attendance/enrolments/{w.e1}", headers=w.h["s1"]).get_json()["data"]["rows"]
                         if r["status"] == "Absent")
    rid = client.post(f"{API}/attendance/recoveries", json={"attendance_id": attendance_id, "method": "Extra session", "reason": "Unwell"},
                      headers=w.h["s1"]).get_json()["data"]["recovery_id"]
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    blocked = decide(client, w, review_id, "Complete")
    assert blocked.status_code == 422 and "recovery" in blocked.get_json()["error"]["message"]

    client.post(f"{API}/attendance/recoveries/{rid}/decision", json={"decision": "Approved"}, headers=w.h["ac"])
    assert decide(client, w, review_id, "Complete").status_code == 422              # approved but not yet completed
    client.post(f"{API}/attendance/recoveries/{rid}/completion", json={"evidence_note": "Task reviewed"}, headers=w.h["t1"])
    assert decide(client, w, review_id, "Complete").status_code == 200


def test_complete_finishes_the_enrolment_and_opens_certificate_eligibility(client, w):
    start(client, w)
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    client.post(f"{API}/completion-reviews/{review_id}/recommendation", json={"recommendation": "Complete"}, headers=w.h["t1"])
    response = decide(client, w, review_id, "Complete")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["evidence"]["trainer_recommendation"] == "Complete"

    e1 = enrolment(w.e1)
    assert e1.status == "Completed" and e1.certificate_status == "Eligibility Review"
    certificate = db.session.execute(select(Certificate).where(Certificate.enrolment_id == w.e1)).scalar_one()
    assert certificate.status == "Eligibility Review" and certificate.completion_review_id == review_id
    assert certificate.holder_name == "Anvitha K." and certificate.branch_id == 1
    assert enrolment(w.e2).status == "Active"

    actions = db.session.execute(select(AuditLog.action).where(AuditLog.entity_type.in_(["completion_review", "certificate"]))).scalars().all()
    assert {"COMPLETION_DECIDED", "CERTIFICATE_ELIGIBILITY_OPENED"} <= set(actions)
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert any(t.startswith("Course completion confirmed") for t in titles)
    assert any(t.startswith("Certificate eligibility to review") for t in titles)
    assert open_review(client, w).status_code == 422                                # a Completed enrolment cannot be reviewed again


def test_decisions_need_fresh_authentication(client, w, run_sql):
    start(client, w)
    review_id = open_review(client, w).get_json()["data"]["review_id"]
    run_sql("UPDATE user_sessions SET reauthenticated_at = NULL")
    stale = decide(client, w, review_id, "Complete")
    assert stale.status_code == 401 and stale.get_json()["error"]["code"] == "FRESH_AUTH_REQUIRED"


def complimentary_enrolment(crm_event, run_sql):
    """A combo student whose complimentary Python Full Stack enrolment is made Active."""
    result = crm_event("AdmissionQualified", helpers.combo_admission_data(person_id="P-COMBO", admission_id="A-COMBO")).get_json()["data"]["result"]
    enrolment_id = next(e["enrolment_id"] for e in result["enrolments"] if e["kind"] == "Complimentary")
    run_sql("UPDATE enrolments SET status = 'Active', joining_date = CURRENT_DATE WHERE enrolment_id = :id", id=enrolment_id)
    return enrolment_id


def test_a_complimentary_offer_without_a_completion_rule_stays_configuration_pending(client, w, crm_event, run_sql):
    enrolment_id = complimentary_enrolment(crm_event, run_sql)
    blocked = open_review(client, w, "ac", enrolment_id)
    assert blocked.status_code == 422 and "Configuration Pending" in blocked.get_json()["error"]["message"]
    assert db.session.execute(select(CompletionReview)).first() is None

    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'complimentary_completion_rule_configured'")
    assert open_review(client, w, "ac", enrolment_id).status_code == 201

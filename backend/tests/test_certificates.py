"""Certificate Register: workflow, numbering, reissue, revoke, scope, public verification and database invariants."""
import re
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from config.timezone import IST
from models import AuditLog, Certificate, Enrolment, Notification
from tests import attendance_world, helpers

API = attendance_world.API
NUMBER = re.compile(rf"^NIT-CERT-{datetime.now(IST).year}-\d{{6}}$")


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login):
    world = attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)
    world.founder = make_user(roles=[("FOUNDER_CEO", None)])
    world.h["founder"] = login(world.founder.email)
    return world


def post(client, w, who, path, body=None):
    return client.post(f"{API}{path}", json=body or {}, headers=w.h[who])


def complete(client, w, enrolment_id=None):
    """Mark the class, review and complete the enrolment; returns its certificate id (status Eligibility Review)."""
    enrolment_id = enrolment_id or w.e1
    client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    review_id = post(client, w, "t1", "/completion-reviews", {"enrolment_id": enrolment_id}).get_json()["data"]["review_id"]
    assert post(client, w, "ac", f"/completion-reviews/{review_id}/decision", {"decision": "Complete"}).status_code == 200
    return db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == enrolment_id)).scalar_one()


def issued(client, w, enrolment_id=None):
    cid = complete(client, w, enrolment_id)
    assert post(client, w, "ac", f"/certificates/{cid}/recommendation").status_code == 200
    assert post(client, w, "bm", f"/certificates/{cid}/approval").status_code == 200
    response = post(client, w, "bm", f"/certificates/{cid}/issue")
    assert response.status_code == 200, response.get_json()
    return cid, response.get_json()["data"]


def get(client, w, who, cid):
    return client.get(f"{API}/certificates/{cid}", headers=w.h[who])


def test_register_entry_appears_when_the_enrolment_starts(client, w):
    assert client.get(f"{API}/certificates", headers=w.h["ac"]).get_json()["data"] == []
    client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    rows = client.get(f"{API}/certificates", headers=w.h["ac"]).get_json()["data"]
    assert sorted(r["holder_name"] for r in rows) == ["Anvitha K.", "Learner Two"]
    assert {r["status"] for r in rows} == {"Not Yet Eligible"} and {r["certificate_number"] for r in rows} == {None}
    assert rows[0]["certificate_type"] == "Course Completion Certificate" and rows[0]["actions"] == []


def test_full_workflow_allocates_the_number_only_at_issue(client, w):
    cid = complete(client, w)
    assert get(client, w, "ac", cid).get_json()["data"]["actions"] == ["recommend"]
    assert get(client, w, "bm", cid).get_json()["data"]["actions"] == []

    assert post(client, w, "bm", f"/certificates/{cid}/approval").status_code == 422        # not recommended yet
    assert post(client, w, "ac", f"/certificates/{cid}/recommendation").status_code == 200
    assert get(client, w, "bm", cid).get_json()["data"]["actions"] == ["approve", "return"]
    assert post(client, w, "ac", f"/certificates/{cid}/approval").status_code == 403         # the coordinator recommends, cannot approve
    assert post(client, w, "ac", f"/certificates/{cid}/issue").status_code == 422
    approved = post(client, w, "bm", f"/certificates/{cid}/approval").get_json()["data"]
    assert approved["status"] == "Approved for Issue" and approved["certificate_number"] is None
    assert get(client, w, "ac", cid).get_json()["data"]["actions"] == ["issue"]

    done = post(client, w, "ac", f"/certificates/{cid}/issue").get_json()["data"]
    assert done["status"] == "Issued" and NUMBER.match(done["certificate_number"]) and done["version"] == 1
    assert done["issue_date"] == datetime.now(IST).date().isoformat()
    db.session.expire_all()
    e1 = db.session.get(Enrolment, w.e1)
    assert e1.certificate_status == "Issued"
    actions = set(db.session.execute(select(AuditLog.action).where(AuditLog.entity_type == "certificate")).scalars())
    assert {"CERTIFICATE_RECOMMENDED", "CERTIFICATE_APPROVED", "CERTIFICATE_ISSUED"} <= actions
    titles = db.session.execute(select(Notification.title)).scalars().all()
    assert any(t.startswith("Certificate awaiting your approval") for t in titles)
    assert any(t.startswith("Your certificate was issued") for t in titles)


def test_numbers_are_sequential_across_students(client, w):
    _, first = issued(client, w, w.e1)
    review = post(client, w, "t1", "/completion-reviews", {"enrolment_id": w.e2}).get_json()["data"]["review_id"]
    post(client, w, "ac", f"/completion-reviews/{review}/decision", {"decision": "Complete"})
    cid = db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == w.e2)).scalar_one()
    post(client, w, "ac", f"/certificates/{cid}/recommendation")
    post(client, w, "bm", f"/certificates/{cid}/approval")
    second = post(client, w, "bm", f"/certificates/{cid}/issue").get_json()["data"]
    assert int(second["certificate_number"][-6:]) == int(first["certificate_number"][-6:]) + 1


def test_approval_needs_someone_other_than_the_recommender(client, w):
    cid = complete(client, w)
    post(client, w, "admin", f"/certificates/{cid}/recommendation")
    own = post(client, w, "admin", f"/certificates/{cid}/approval")
    assert own.status_code == 422 and "different person" in own.get_json()["error"]["message"]
    assert post(client, w, "bm", f"/certificates/{cid}/approval").status_code == 200


def test_manager_can_return_a_recommendation_for_review(client, w):
    cid = complete(client, w)
    post(client, w, "ac", f"/certificates/{cid}/recommendation")
    assert post(client, w, "bm", f"/certificates/{cid}/return").status_code == 400
    back = post(client, w, "bm", f"/certificates/{cid}/return", {"reason": "Name spelling to confirm"})
    assert back.status_code == 200 and back.get_json()["data"]["status"] == "Eligibility Review"


def test_reissue_keeps_the_number_and_supersedes_the_earlier_version(client, w):
    cid, done = issued(client, w)
    assert post(client, w, "ac", f"/certificates/{cid}/reissue", {"reason": "Name correction"}).status_code == 403
    assert post(client, w, "bm", f"/certificates/{cid}/reissue", {}).status_code == 400
    response = post(client, w, "bm", f"/certificates/{cid}/reissue", {"reason": "Name correction", "holder_name": "Anvitha Kolli"})
    assert response.status_code == 201, response.get_json()
    v2 = response.get_json()["data"]
    assert v2["version"] == 2 and v2["status"] == "Issued" and v2["certificate_number"] == done["certificate_number"]
    assert v2["holder_name"] == "Anvitha Kolli" and v2["version_label"] == "v2 (reissue)"

    old = get(client, w, "bm", cid).get_json()["data"]
    assert old["status"] == "Superseded" and old["actions"] == []
    assert [h["version"] for h in get(client, w, "bm", v2["certificate_id"]).get_json()["data"]["history"]] == [1, 2]

    register = client.get(f"{API}/certificates?q=anvitha", headers=w.h["bm"]).get_json()["data"]
    assert sorted(r["status"] for r in register) == ["Issued", "Superseded"]
    mine = client.get(f"{API}/me/certificates", headers=w.h["s1"]).get_json()["data"]["certificates"]
    assert [c["status"] for c in mine] == ["Issued"]
    verified = client.get(f"{API}/certificates/verify/{done['certificate_number']}").get_json()["data"]
    assert verified["version"] == 2 and verified["holder_name"] == "Anvitha Kolli" and verified["status"] == "Issued"
    assert post(client, w, "bm", f"/certificates/{cid}/reissue", {"reason": "again"}).status_code == 422  # v1 is Superseded


def test_only_the_super_admin_revokes_and_a_revoked_certificate_is_final(client, w):
    cid, done = issued(client, w)
    for who in ("ac", "bm", "s1", "t1"):
        assert post(client, w, who, f"/certificates/{cid}/revocation", {"reason": "Record error"}).status_code in (403, 404)
    assert post(client, w, "admin", f"/certificates/{cid}/revocation", {}).status_code == 400
    revoked = post(client, w, "admin", f"/certificates/{cid}/revocation", {"reason": "Record error"})
    assert revoked.status_code == 200 and revoked.get_json()["data"]["status"] == "Revoked"
    assert revoked.get_json()["data"]["reason"] == "Record error"
    assert post(client, w, "admin", f"/certificates/{cid}/revocation", {"reason": "twice"}).status_code == 422
    assert post(client, w, "bm", f"/certificates/{cid}/reissue", {"reason": "x"}).status_code == 422
    verified = client.get(f"{API}/certificates/verify/{done['certificate_number']}").get_json()["data"]
    assert verified["status"] == "Revoked"
    assert db.session.execute(select(AuditLog).where(AuditLog.action == "CERTIFICATE_REVOKED")).scalar_one().reason == "Record error"


def test_public_verification_returns_only_the_public_facts(client, w):
    _, done = issued(client, w)
    number = done["certificate_number"]
    data = client.get(f"{API}/certificates/verify/{number.lower()}").get_json()["data"]
    assert set(data) == {"certificate_number", "holder_name", "course", "certificate_type", "issue_date", "status", "version"}
    assert data["holder_name"] == "Anvitha K." and data["course"]["course_code"] == "NIT-CRS-047"
    assert client.get(f"{API}/certificates/verify/NIT-CERT-2026-999999").status_code == 404


def test_scope_of_the_register(client, w):
    cid = complete(client, w)
    assert get(client, w, "ac", cid).status_code == 200
    assert get(client, w, "ac_v", cid).status_code == 404
    assert get(client, w, "bm_v", cid).status_code == 404
    assert get(client, w, "s1", cid).status_code == 200
    assert get(client, w, "s2", cid).status_code == 404
    assert get(client, w, "t1", cid).status_code == 403
    assert client.get(f"{API}/certificates", headers=w.h["t1"]).status_code == 403
    assert client.get(f"{API}/certificates", headers=w.h["s1"]).status_code == 403
    assert client.get(f"{API}/certificates", headers=w.h["ac_v"]).get_json()["data"] == []
    assert post(client, w, "ac_v", f"/certificates/{cid}/recommendation").status_code == 404
    assert client.get(f"{API}/certificates", headers=w.h["founder"]).status_code == 200
    assert get(client, w, "founder", cid).get_json()["data"]["actions"] == []
    assert get(client, w, "s1", cid).get_json()["data"]["actions"] == []


def test_register_filters(client, w):
    complete(client, w)
    base = f"{API}/certificates"
    assert len(client.get(f"{base}?status=Eligibility Review", headers=w.h["ac"]).get_json()["data"]) == 1
    assert client.get(f"{base}?status=Issued", headers=w.h["ac"]).get_json()["data"] == []
    assert len(client.get(f"{base}?q=anvitha", headers=w.h["ac"]).get_json()["data"]) == 1
    assert client.get(f"{base}?certificate_type=Internship Certificate", headers=w.h["ac"]).get_json()["data"] == []
    assert client.get(f"{base}?status=Nope", headers=w.h["ac"]).status_code == 400


def test_coordinator_can_add_an_internship_entry(client, w):
    complete(client, w)
    made = post(client, w, "ac", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"})
    assert made.status_code == 201 and made.get_json()["data"]["status"] == "Eligibility Review"
    assert post(client, w, "ac", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 409
    assert post(client, w, "bm", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 403
    assert post(client, w, "ac_v", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 404
    assert post(client, w, "ac", "/certificates", {"enrolment_id": w.e3, "certificate_type": "Internship Certificate"}).status_code == 422


def test_a_complimentary_offer_shows_configuration_pending_on_the_student_screen(client, w, crm_event, login, run_sql):
    data = crm_event("AdmissionQualified", helpers.combo_admission_data(person_id="P-COMBO", admission_id="A-COMBO", email="combo@example.test")).get_json()["data"]
    client.post(f"{API}/auth/activate", json={"token": data["activation_token"], "password": "Correct-horse-1"})
    headers = {"Authorization": login("combo@example.test")["Authorization"]}
    mine = client.get(f"{API}/me/certificates", headers=headers).get_json()["data"]
    assert mine["certificates"] == []
    assert len(mine["configuration_pending"]) == 1
    assert mine["configuration_pending"][0]["message"] == "Completion rule not configured for complimentary offer"
    assert mine["configuration_pending"][0]["enrolment"]["kind"] == "Complimentary"
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'complimentary_completion_rule_configured'")
    assert client.get(f"{API}/me/certificates", headers=headers).get_json()["data"]["configuration_pending"] == []


def test_sensitive_steps_need_fresh_authentication(client, w, run_sql):
    cid = complete(client, w)
    post(client, w, "ac", f"/certificates/{cid}/recommendation")
    run_sql("UPDATE user_sessions SET reauthenticated_at = NULL")
    response = post(client, w, "bm", f"/certificates/{cid}/approval")
    assert response.status_code == 401 and response.get_json()["error"]["code"] == "FRESH_AUTH_REQUIRED"


# ---------------------------------------------------------------- database invariants

def certificate_row(cid) -> Certificate:
    db.session.expire_all()
    return db.session.get(Certificate, cid)


def test_database_rejects_invalid_transitions_and_number_changes(client, w, run_sql):
    cid, _ = issued(client, w)
    waiting = db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == w.e2)).scalar_one()
    for target in ("Approved for Issue", "Issued", "Revoked"):
        with pytest.raises(DBAPIError, match="cannot move"):
            run_sql(f"UPDATE certificates SET status = '{target}' WHERE certificate_id = {waiting}")
        db.session.rollback()
    with pytest.raises(DBAPIError, match="never changes"):
        run_sql("UPDATE certificates SET certificate_number = 'NIT-CERT-2026-000999' WHERE certificate_id = :c", c=cid)
    db.session.rollback()
    with pytest.raises(DBAPIError, match="cannot move"):
        run_sql("UPDATE certificates SET status = 'Approved for Issue' WHERE certificate_id = :c", c=cid)
    db.session.rollback()


def test_database_needs_a_completed_enrolment_for_eligibility(client, w, run_sql):
    client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    cid = db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == w.e1)).scalar_one()
    with pytest.raises(DBAPIError, match="only after a Complete completion decision"):
        run_sql("UPDATE certificates SET status = 'Eligibility Review' WHERE certificate_id = :c", c=cid)
    db.session.rollback()

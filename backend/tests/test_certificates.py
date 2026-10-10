"""Certificate Register: workflow, numbering, reissue, revoke, scope, public verification and database invariants."""
import re
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from config.database import db
from config.timezone import IST
from models import AuditLog, Certificate, Enrolment, Notification, WhatsappMessage
from tests import attendance_world, helpers

API = attendance_world.API
NUMBER = re.compile(rf"^NIT-CERT-{datetime.now(IST).year}-\d{{6}}$")


@pytest.fixture
def w(make_user, make_student, make_batch, make_session, allocate, login, run_sql):
    world = attendance_world.build(make_user, make_student, make_batch, make_session, allocate, login)
    world.founder = make_user(roles=[("FOUNDER_CEO", None)])
    world.h["founder"] = login(world.founder.email)
    for enrolment_id in (world.e1, world.e2, world.e3):  # fees cleared unless a test says otherwise
        attendance_world.set_fee(run_sql, enrolment_id)
    return world


def post(client, w, who, path, body=None):
    return client.post(f"{API}{path}", json=body or {}, headers=w.h[who])


def complete(client, w, enrolment_id=None):
    """Mark the class, review and complete the enrolment; returns its certificate id (status Eligibility Review)."""
    enrolment_id = enrolment_id or w.e1
    client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    review_id = post(client, w, "t1", "/completion-reviews", {"enrolment_id": enrolment_id}).get_json()["data"]["review_id"]
    post(client, w, "t1", f"/completion-reviews/{review_id}/recommendation", {"recommendation": "Complete"})  # trainer confirms
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
    assert get(client, w, "ac", cid).get_json()["data"]["actions"] == ["recommend", "approve"]
    assert get(client, w, "founder", cid).get_json()["data"]["actions"] == []

    assert post(client, w, "ac", f"/certificates/{cid}/recommendation").status_code == 200
    assert get(client, w, "bm", cid).get_json()["data"]["actions"] == ["approve", "return"]
    assert post(client, w, "ac", f"/certificates/{cid}/issue").status_code == 422
    approved = post(client, w, "ac", f"/certificates/{cid}/approval").get_json()["data"]        # the recommender may approve too
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
    post(client, w, "t1", f"/completion-reviews/{review}/recommendation", {"recommendation": "Complete"})
    post(client, w, "ac", f"/completion-reviews/{review}/decision", {"decision": "Complete"})
    cid = db.session.execute(select(Certificate.certificate_id).where(Certificate.enrolment_id == w.e2)).scalar_one()
    post(client, w, "ac", f"/certificates/{cid}/recommendation")
    post(client, w, "bm", f"/certificates/{cid}/approval")
    second = post(client, w, "bm", f"/certificates/{cid}/issue").get_json()["data"]
    assert int(second["certificate_number"][-6:]) == int(first["certificate_number"][-6:]) + 1


def test_a_branch_manager_approves_straight_from_eligibility_review(client, w):
    """Recommending and approving are one Branch Manager step: the recommendation is recorded with the approval."""
    cid = complete(client, w)
    approved = post(client, w, "bm", f"/certificates/{cid}/approval")
    assert approved.status_code == 200 and approved.get_json()["data"]["status"] == "Approved for Issue"
    db.session.expire_all()
    certificate = db.session.get(Certificate, cid)
    assert certificate.recommended_by == certificate.approved_by and certificate.recommended_at is not None


def test_manager_can_return_a_recommendation_for_review(client, w):
    cid = complete(client, w)
    post(client, w, "ac", f"/certificates/{cid}/recommendation")
    assert post(client, w, "bm", f"/certificates/{cid}/return").status_code == 400
    back = post(client, w, "bm", f"/certificates/{cid}/return", {"reason": "Name spelling to confirm"})
    assert back.status_code == 200 and back.get_json()["data"]["status"] == "Eligibility Review"


def change(client, w, who, cid, kind, **body):
    return post(client, w, who, f"/certificates/{cid}/change-requests", {"kind": kind, **body})


def decide(client, w, who, request_id, decision="Approved", note=None):
    return post(client, w, who, f"/certificate-requests/{request_id}/decision", {"decision": decision, "note": note})


def test_a_correction_is_requested_and_an_independent_approver_reissues_it(client, w):
    """Module 22 §7: a Branch Manager asks, so a Super Admin approves; the current copy stays valid until then."""
    cid, done = issued(client, w)
    assert change(client, w, "t1", cid, "Correction", reason="Name correction").status_code == 403
    assert change(client, w, "ac", cid, "Correction").status_code == 400
    asked = change(client, w, "ac", cid, "Correction", reason="Name correction", holder_name="Anvitha Kolli")
    assert asked.status_code == 201, asked.get_json()
    request = asked.get_json()["data"]
    assert request["status"] == "Pending" and request["changes"] == {"holder_name": {"from": "Anvitha K.", "to": "Anvitha Kolli"}}
    assert get(client, w, "ac", cid).get_json()["data"]["status"] == "Issued"                  # still valid while pending
    assert get(client, w, "ac", cid).get_json()["data"]["pending_request"]["kind"] == "Correction"
    assert change(client, w, "bm", cid, "Revocation", reason="x", evidence="y").status_code == 409  # one request at a time

    listed = client.get(f"{API}/certificate-requests?status=Pending", headers=w.h["admin"]).get_json()["data"]
    assert [r["actions"] for r in listed] == [["decide"]]
    assert [r["actions"] for r in client.get(f"{API}/certificate-requests?status=Pending", headers=w.h["bm"]).get_json()["data"]] == [[]]
    assert decide(client, w, "ac", request["request_id"]).status_code == 422                  # never the person who asked
    assert decide(client, w, "bm", request["request_id"]).status_code == 422                  # a Branch Manager's own request goes up
    assert decide(client, w, "admin", request["request_id"], "Rejected").status_code == 400   # a rejection needs a note
    approved = decide(client, w, "admin", request["request_id"])
    assert approved.status_code == 200, approved.get_json()
    v2_id = approved.get_json()["data"]["resulting_certificate_id"]
    v2 = get(client, w, "bm", v2_id).get_json()["data"]
    assert v2["version"] == 2 and v2["status"] == "Issued" and v2["certificate_number"] == done["certificate_number"]
    assert v2["holder_name"] == "Anvitha Kolli" and v2["version_label"] == "v2 (reissue)"
    assert get(client, w, "bm", cid).get_json()["data"]["status"] == "Superseded"
    assert [h["version"] for h in v2["history"]] == [1, 2]
    mine = client.get(f"{API}/me/certificates", headers=w.h["s1"]).get_json()["data"]["certificates"]
    assert [c["status"] for c in mine] == ["Issued"]


def test_the_person_who_asked_never_decides(client, w):
    cid, _ = issued(client, w)
    request_id = change(client, w, "bm", cid, "Correction", reason="Typo").get_json()["data"]["request_id"]
    own = decide(client, w, "bm", request_id)
    assert own.status_code == 422 and "independent" in own.get_json()["error"]["message"]
    assert decide(client, w, "admin", request_id).status_code == 200


def test_revocation_and_reinstatement_need_evidence_and_the_founder_or_super_admin(client, w):
    """Module 22 §8: revocation and a later reinstatement are separate, recorded, independent decisions."""
    cid, done = issued(client, w)
    assert change(client, w, "ac", cid, "Revocation", reason="Record error").status_code == 400   # evidence is required
    request_id = change(client, w, "ac", cid, "Revocation", reason="Record error", evidence="Issued against the wrong enrolment"
                        ).get_json()["data"]["request_id"]
    assert decide(client, w, "bm", request_id).status_code == 403
    revoked = decide(client, w, "founder", request_id)
    assert revoked.status_code == 200, revoked.get_json()
    certificate = get(client, w, "ac", cid).get_json()["data"]
    assert certificate["status"] == "Revoked" and certificate["reason"] == "Record error" and certificate["actions"] == ["request_reinstatement"]
    assert client.get(f"{API}/certificates/verify/{done['certificate_number']}").get_json()["data"]["state"] == "Revoked"

    request_id = change(client, w, "bm", cid, "Reinstatement", reason="The revocation was a mistake",
                        evidence="Enrolment confirmed by the coordinator").get_json()["data"]["request_id"]
    reinstated = decide(client, w, "admin", request_id)
    assert reinstated.status_code == 200, reinstated.get_json()
    certificate = get(client, w, "ac", cid).get_json()["data"]
    assert certificate["status"] == "Issued" and certificate["certificate_number"] == done["certificate_number"]
    assert certificate["issue_date"] == done["issue_date"]                                     # the original issue date stays
    assert [h["to_status"] for h in certificate["status_history"]][-2:] == ["Revoked", "Issued"]  # the revoked interval is kept
    actions = set(db.session.execute(select(AuditLog.action).where(AuditLog.entity_type == "certificate")).scalars())
    assert {"CERTIFICATE_REVOKED", "CERTIFICATE_REINSTATED", "CERTIFICATE_REVOCATION_APPROVED"} <= actions


def test_public_verification_shows_the_presented_version_state(client, w):
    """Module 22 §9: Valid — Current Version, Superseded (with the current version) or Revoked; branch and original issue date."""
    cid, done = issued(client, w)
    number = done["certificate_number"]
    data = client.get(f"{API}/certificates/verify/{number.lower()}").get_json()["data"]
    assert set(data) == {"certificate_number", "version", "state", "holder_name", "course", "certificate_type", "branch",
                         "issue_date", "original_issue_date", "current_version"}
    assert data["state"] == "Valid — Current Version" and data["current_version"] is None and data["branch"]["branch_code"] == "NIT-GNT"
    request_id = change(client, w, "ac", cid, "Correction", reason="Name correction", holder_name="Anvitha Kolli").get_json()["data"]["request_id"]
    decide(client, w, "admin", request_id)
    old = client.get(f"{API}/certificates/verify/{number}?version=1").get_json()["data"]
    assert old["state"] == "Superseded" and old["holder_name"] == "Anvitha K." and old["current_version"] == {"version": 2, "state": "Valid — Current Version"}
    assert client.get(f"{API}/certificates/verify/{number}").get_json()["data"]["version"] == 2
    assert client.get(f"{API}/certificates/verify/{number}?version=9").status_code == 404
    assert client.get(f"{API}/certificates/verify/NIT-CERT-2026-999999").status_code == 404


def test_an_unpaid_fee_holds_the_certificate_until_paid_or_released_by_exception(client, w, run_sql):
    """Module 22 §5: the final fee is cleared before eligibility; a Founder / CEO or Super Admin exception lets it go ahead."""
    attendance_world.set_fee(run_sql, w.e1, balance=5000)
    cid = complete(client, w)
    entry = get(client, w, "ac", cid).get_json()["data"]
    assert entry["fee_clearance"]["state"] == "Outstanding" and entry["fee_clearance"]["balance"] == "5000.00"
    held = post(client, w, "ac", f"/certificates/{cid}/recommendation")
    assert held.status_code == 422 and "Fee not cleared" in held.get_json()["error"]["message"]

    asked = post(client, w, "ac", f"/certificates/{cid}/financial-exception", {"reason": "Scholarship letter pending in the CRM"})
    assert asked.status_code == 201, asked.get_json()
    exception_id = asked.get_json()["data"]["exception_id"]
    assert post(client, w, "ac", f"/certificates/{cid}/financial-exception", {"reason": "again"}).status_code == 409
    assert post(client, w, "bm", f"/certificate-financial-exceptions/{exception_id}/decision", {"decision": "Approved", "note": "ok"}).status_code == 403
    assert post(client, w, "founder", f"/certificate-financial-exceptions/{exception_id}/decision", {"decision": "Approved"}).status_code == 400
    approved = post(client, w, "founder", f"/certificate-financial-exceptions/{exception_id}/decision",
                    {"decision": "Approved", "note": "Released; the balance stays due in the CRM"})
    assert approved.status_code == 200 and approved.get_json()["data"]["status"] == "Approved"
    assert get(client, w, "ac", cid).get_json()["data"]["fee_clearance"]["state"] == "Released by exception"
    assert post(client, w, "ac", f"/certificates/{cid}/recommendation").status_code == 200


def test_a_missing_fee_summary_holds_the_certificate(client, w, run_sql):
    run_sql("DELETE FROM finance_summaries")
    cid = complete(client, w)
    held = post(client, w, "ac", f"/certificates/{cid}/recommendation")
    assert held.status_code == 422 and "not been received" in held.get_json()["error"]["message"]


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


def test_branch_manager_can_add_an_internship_entry(client, w):
    complete(client, w)
    made = post(client, w, "ac", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"})
    assert made.status_code == 201 and made.get_json()["data"]["status"] == "Not Yet Eligible"  # course completion is not an internship
    assert post(client, w, "ac", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 409
    assert post(client, w, "founder", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 403
    assert post(client, w, "ac_v", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 404
    assert post(client, w, "ac", "/certificates", {"enrolment_id": w.e3, "certificate_type": "Internship Certificate"}).status_code == 422


def test_course_completion_does_not_open_the_internship_certificate(client, w):
    """Module 22 §3: an Internship Certificate needs verified internship evidence, not just a completed course."""
    client.put(f"{API}/attendance/sessions/{w.recent.session_id}", json={"default_status": "Present"}, headers=w.h["t1"])
    assert post(client, w, "ac", "/certificates", {"enrolment_id": w.e1, "certificate_type": "Internship Certificate"}).status_code == 201
    review_id = post(client, w, "t1", "/completion-reviews", {"enrolment_id": w.e1}).get_json()["data"]["review_id"]
    post(client, w, "t1", f"/completion-reviews/{review_id}/recommendation", {"recommendation": "Complete"})
    assert post(client, w, "ac", f"/completion-reviews/{review_id}/decision", {"decision": "Complete"}).status_code == 200
    statuses = dict(db.session.execute(select(Certificate.certificate_type, Certificate.status).where(Certificate.enrolment_id == w.e1)).all())
    assert statuses == {"Course Completion Certificate": "Eligibility Review", "Internship Certificate": "Not Yet Eligible"}


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


def test_issuing_queues_one_whatsapp_message_with_the_number_for_the_button(client, w, run_sql):
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    run_sql("UPDATE app_settings SET setting_value = '[\"nipuna_lms_certificate_issued_u_v1\"]' WHERE setting_key = 'whatsapp_approved_templates'")
    cid, certificate = issued(client, w)
    message = db.session.execute(select(WhatsappMessage)).scalar_one()
    assert message.template_name == "nipuna_lms_certificate_issued_u_v1" and message.status in ("Queued", "Skipped")
    assert message.params[4] == certificate["certificate_number"] and message.button_params == [certificate["certificate_number"]]
    assert message.dedupe_key == f"certificate-issued:{cid}:1"

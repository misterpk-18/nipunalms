"""Placement & career support: opt-in, consent, CV versions, opportunities, applications and verified outcomes."""
import io
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog
from repositories import catalog as catalog_repo
from tests.services_fixtures import world  # noqa: F401

ME = "/api/v1/me/career"
API = "/api/v1"


def pdf(name="cv.pdf"):
    return {"file": (io.BytesIO(b"%PDF-1.4 sample cv"), name)}


def opt_in(client, w, student, consent=True):
    h = w.h(student)
    assert client.put(f"{ME}/profile", headers=h, json={"opted_in": True}).status_code == 200
    if consent:
        assert client.put(f"{ME}/consent", headers=h, json={"sharing_consent": True}).status_code == 200


def upload_reviewed_cv(client, w, student):
    cv = client.post(f"{ME}/cvs", headers=w.h(student), data=pdf(), content_type="multipart/form-data")
    assert cv.status_code == 201, cv.get_json()
    cv_id = cv.get_json()["data"]["cv_id"]
    review = client.post(f"{API}/cv-documents/{cv_id}/review", headers=w.h(w.people.ac), json={"status": "Reviewed"})
    assert review.status_code == 200, review.get_json()
    return cv_id


def make_active_opportunity(client, w, **extra):
    body = {"title": "Junior Data Analyst", "employer_name": "Sample Analytics Pvt Ltd", "branch_id": 1, **extra}
    created = client.post(f"{API}/opportunities", headers=w.h(w.people.ac), json=body)
    assert created.status_code == 201, created.get_json()
    oid = created.get_json()["data"]["opportunity_id"]
    assert client.post(f"{API}/opportunities/{oid}/status", headers=w.h(w.people.ac), json={"status": "Verification Pending"}).status_code == 200
    activated = client.post(f"{API}/opportunities/{oid}/status", headers=w.h(w.people.bm),
                            json={"status": "Active", "verification_source": "Employer website and HR call"})
    assert activated.status_code == 200, activated.get_json()
    return oid


class TestProfile:
    def test_opting_in_starts_the_support_period(self, client, world):
        h = world.h(world.students.s1)
        before = client.get(ME, headers=h).get_json()["data"]
        assert before["profile"]["opted_in"] is False and "no guaranteed placement" in before["notice"]
        assert "Opt in" in before["next_action"] and before["opportunities"] == []

        response = client.put(f"{ME}/profile", headers=h, json={"opted_in": True, "preferred_roles": ["Data Analyst"],
                                                                  "skills": ["SQL", "Python"], "graduation_year": 2025})
        profile = response.get_json()["data"]["profile"]
        assert profile["opted_in"] and profile["support_start"]
        assert profile["support_end"] > profile["support_start"]
        assert profile["skills"] == [{"name": "SQL", "confidence": "Student Reported"}, {"name": "Python", "confidence": "Student Reported"}]
        assert 0 < profile["completeness"]["percent"] < 100 and "Portfolio or project link" in profile["completeness"]["missing"]
        assert db.session.execute(select(AuditLog).where(AuditLog.action == "CAREER_OPT_IN")).scalars().first() is not None

    def test_consent_needs_opt_in_and_can_be_withdrawn(self, client, world):
        h = world.h(world.students.s1)
        assert client.put(f"{ME}/consent", headers=h, json={"sharing_consent": True}).status_code == 422
        opt_in(client, world, world.students.s1)
        assert client.get(ME, headers=h).get_json()["data"]["profile"]["sharing_consent"] is True
        withdrawn = client.put(f"{ME}/consent", headers=h, json={"sharing_consent": False}).get_json()["data"]["profile"]
        assert withdrawn["sharing_consent"] is False and withdrawn["opted_in"] is True
        actions = [a.action for a in db.session.execute(select(AuditLog)).scalars()]
        assert "CAREER_CONSENT_GIVEN" in actions and "CAREER_CONSENT_WITHDRAWN" in actions

    def test_opting_out_clears_consent(self, client, world):
        opt_in(client, world, world.students.s1)
        profile = client.put(f"{ME}/profile", headers=world.h(world.students.s1), json={"opted_in": False}).get_json()["data"]["profile"]
        assert profile["opted_in"] is False and profile["sharing_consent"] is False

    @pytest.mark.parametrize("body", [{}, {"portfolio_url": "not a link"}, {"work_mode": "Sometimes"}, {"graduation_year": 1800}])
    def test_invalid_profiles_are_rejected(self, client, world, body):
        assert client.put(f"{ME}/profile", headers=world.h(world.students.s1), json=body).status_code == 400

    def test_only_students_have_a_career_screen(self, client, world):
        assert client.get(ME, headers=world.h(world.people.t1)).status_code == 403


class TestCv:
    def test_versions_are_kept_and_reviewed(self, client, world):
        h = world.h(world.students.s1)
        opt_in(client, world, world.students.s1)
        first = client.post(f"{ME}/cvs", headers=h, data={**pdf("cv1.pdf"), "label": "CV v1"}, content_type="multipart/form-data").get_json()["data"]
        assert first["version_no"] == 1 and first["review_status"] == "Pending Review" and first["label"] == "CV v1"
        review = client.post(f"{API}/cv-documents/{first['cv_id']}/review", headers=world.h(world.people.ac),
                             json={"status": "Changes Requested"})
        assert review.status_code == 400                                       # feedback needed
        client.post(f"{API}/cv-documents/{first['cv_id']}/review", headers=world.h(world.people.ac),
                    json={"status": "Changes Requested", "feedback": "Add your projects"})
        second = client.post(f"{ME}/cvs", headers=h, data=pdf("cv2.pdf"), content_type="multipart/form-data").get_json()["data"]
        assert second["version_no"] == 2 and second["label"] == "cv2"
        cvs = client.get(ME, headers=h).get_json()["data"]["cvs"]
        assert [(c["version_no"], c["review_status"]) for c in cvs] == [(2, "Pending Review"), (1, "Superseded")]
        assert client.post(f"{API}/cv-documents/{first['cv_id']}/review", headers=world.h(world.people.ac),
                           json={"status": "Reviewed"}).status_code == 422       # a superseded version is not reviewed again

    def test_file_rules(self, client, world):
        h = world.h(world.students.s1)
        assert client.post(f"{ME}/cvs", headers=h, data=pdf(), content_type="multipart/form-data").status_code == 422   # not opted in
        opt_in(client, world, world.students.s1)
        assert client.post(f"{ME}/cvs", headers=h, data=pdf("cv.exe"), content_type="multipart/form-data").status_code == 400
        assert client.post(f"{ME}/cvs", headers=h, data={}, content_type="multipart/form-data").status_code == 400
        empty = {"file": (io.BytesIO(b""), "cv.pdf")}
        assert client.post(f"{ME}/cvs", headers=h, data=empty, content_type="multipart/form-data").status_code == 400

    def test_download_is_for_the_owner_and_staff_of_the_branch(self, client, world):
        opt_in(client, world, world.students.s1)
        cv_id = client.post(f"{ME}/cvs", headers=world.h(world.students.s1), data=pdf(), content_type="multipart/form-data").get_json()["data"]["cv_id"]
        url = f"{API}/cv-documents/{cv_id}/download"
        own = client.get(url, headers=world.h(world.students.s1))
        assert own.status_code == 200 and own.data.startswith(b"%PDF")
        assert client.get(url, headers=world.h(world.people.ac)).status_code == 200
        for outsider in (world.students.s2, world.people.ac_vij):
            assert client.get(url, headers=world.h(outsider)).status_code == 404
        assert client.get(url, headers=world.h(world.people.t1)).status_code == 403


class TestOpportunitiesAndApplications:
    def test_only_verified_active_opportunities_reach_students(self, client, world):
        opt_in(client, world, world.students.s1)
        draft = client.post(f"{API}/opportunities", headers=world.h(world.people.ac), json={"title": "Draft role", "employer_name": "X", "branch_id": 1})
        assert draft.get_json()["data"]["status"] == "Draft" and draft.get_json()["data"]["opportunity_code"].startswith("OPP-")
        active = make_active_opportunity(client, world)
        shown = client.get(ME, headers=world.h(world.students.s1)).get_json()["data"]["opportunities"]
        assert [o["opportunity_id"] for o in shown] == [active]
        assert "verified_by" not in shown[0] and shown[0]["applied"] is False

    def test_eligibility_by_branch_course_and_closing_date(self, client, world):
        opt_in(client, world, world.students.s1)
        other_branch = make_active_opportunity(client, world, title="Vijayawada role")     # created for branch 1; move it via a vij one below
        vij = client.post(f"{API}/opportunities", headers=world.h(world.people.ac_vij), json={"title": "VIJ only", "employer_name": "Y", "branch_id": 2})
        oid = vij.get_json()["data"]["opportunity_id"]
        client.post(f"{API}/opportunities/{oid}/status", headers=world.h(world.people.ac_vij), json={"status": "Verification Pending"})
        client.post(f"{API}/opportunities/{oid}/status", headers=world.h(world.people.bm_vij), json={"status": "Active", "verification_source": "Call"})
        expired = make_active_opportunity(client, world, title="Closed already", closing_date=(date.today() - timedelta(days=1)).isoformat())
        wrong_course = make_active_opportunity(client, world, title="Other course", course_id=catalog_repo.get_course_by_code("NIT-CRS-019").course_id)
        ids = {o["opportunity_id"] for o in client.get(ME, headers=world.h(world.students.s1)).get_json()["data"]["opportunities"]}
        assert ids == {other_branch}
        assert oid not in ids and expired not in ids and wrong_course not in ids

    def test_verification_needs_a_second_person_and_a_source(self, client, world):
        created = client.post(f"{API}/opportunities", headers=world.h(world.people.ac), json={"title": "Role", "employer_name": "Z", "branch_id": 1})
        oid = created.get_json()["data"]["opportunity_id"]
        url = f"{API}/opportunities/{oid}/status"
        client.post(url, headers=world.h(world.people.ac), json={"status": "Verification Pending"})
        assert client.post(url, headers=world.h(world.people.ac), json={"status": "Active", "verification_source": "Website"}).status_code == 422
        assert client.post(url, headers=world.h(world.people.bm), json={"status": "Active"}).status_code == 400
        assert client.post(url, headers=world.h(world.people.bm), json={"status": "Draft"}).status_code == 200
        assert client.post(url, headers=world.h(world.people.bm), json={"status": "Active"}).status_code == 422   # not from Draft

    def test_editing_a_verified_opportunity_needs_fresh_verification(self, client, world):
        oid = make_active_opportunity(client, world)
        url = f"{API}/opportunities/{oid}"
        assert client.patch(url, headers=world.h(world.people.ac), json={"title": "Changed"}).status_code == 422   # Active is not editable
        client.post(f"{url}/status", headers=world.h(world.people.bm), json={"status": "On Hold"})
        edited = client.patch(url, headers=world.h(world.people.ac), json={"title": "Changed"}).get_json()["data"]
        assert edited["title"] == "Changed" and edited["status"] == "Verification Pending" and edited["verified_by"] is None
        assert client.patch(url, headers=world.h(world.people.ac), json={}).status_code == 400

    def test_staff_scope_for_opportunities(self, client, world):
        oid = make_active_opportunity(client, world)
        assert client.get(f"{API}/opportunities/{oid}", headers=world.h(world.people.ac_vij)).status_code == 404
        assert client.get(f"{API}/opportunities/{oid}", headers=world.h(world.people.bm)).status_code == 200
        assert client.get(f"{API}/opportunities", headers=world.h(world.people.ac_vij)).get_json()["data"] == []
        denied = client.post(f"{API}/opportunities", headers=world.h(world.people.ac), json={"title": "All", "employer_name": "Z"})
        assert denied.status_code == 400                                          # only an admin publishes to every branch
        assert client.post(f"{API}/opportunities", headers=world.h(world.people.admin), json={"title": "All", "employer_name": "Z"}).status_code == 201
        assert client.get(f"{API}/opportunities", headers=world.h(world.students.s1)).status_code == 403

    def test_applying_needs_opt_in_consent_a_reviewed_cv_and_an_eligible_opportunity(self, client, world):
        oid = make_active_opportunity(client, world)
        url = f"{ME}/opportunities/{oid}/apply"
        h = world.h(world.students.s1)
        assert client.post(url, headers=h).status_code == 422                     # not opted in
        opt_in(client, world, world.students.s1, consent=False)
        assert client.post(url, headers=h).status_code == 422                     # no consent
        client.put(f"{ME}/consent", headers=h, json={"sharing_consent": True})
        assert client.post(url, headers=h).status_code == 422                     # no reviewed CV
        cv_id = upload_reviewed_cv(client, world, world.students.s1)
        assert client.post(f"{ME}/opportunities/99999/apply", headers=h).status_code == 404

        applied = client.post(url, headers=h)
        assert applied.status_code == 201
        assert applied.get_json()["data"]["status"] == "Applied" and applied.get_json()["data"]["cv"]["cv_id"] == cv_id
        assert client.post(url, headers=h).status_code == 409                     # one application per opportunity and cycle
        overview = client.get(ME, headers=h).get_json()["data"]
        assert overview["opportunities"][0]["applied"] is True and overview["applications"][0]["opportunity"]["title"] == "Junior Data Analyst"

    def test_the_student_can_withdraw_until_the_application_is_closed(self, client, world):
        opt_in(client, world, world.students.s1)
        upload_reviewed_cv(client, world, world.students.s1)
        oid = make_active_opportunity(client, world)
        h = world.h(world.students.s1)
        app_id = client.post(f"{ME}/opportunities/{oid}/apply", headers=h).get_json()["data"]["application_id"]
        assert client.post(f"{ME}/applications/{app_id}/withdraw", headers=world.h(world.students.s2)).status_code == 404
        assert client.post(f"{ME}/applications/{app_id}/withdraw", headers=h).get_json()["data"]["status"] == "Withdrawn"
        assert client.post(f"{ME}/applications/{app_id}/withdraw", headers=h).status_code == 422

    def test_staff_move_an_application_and_the_history_is_kept(self, client, world):
        opt_in(client, world, world.students.s1)
        upload_reviewed_cv(client, world, world.students.s1)
        oid = make_active_opportunity(client, world)
        app_id = client.post(f"{ME}/opportunities/{oid}/apply", headers=world.h(world.students.s1)).get_json()["data"]["application_id"]
        url = f"{API}/applications/{app_id}/status"
        h = world.h(world.people.ac)

        assert client.post(url, headers=h, json={"status": "Interview Scheduled"}).status_code == 400            # needs a time
        scheduled = client.post(url, headers=h, json={"status": "Interview Scheduled", "interview_round": "Technical round 2",
                                                      "interview_at": "2026-10-02T15:00:00+05:30"})
        assert scheduled.get_json()["data"]["interview_round"] == "Technical round 2"
        offer = client.post(url, headers=h, json={"status": "Offer Received", "note": "Offer letter seen"})   # stages may be skipped
        assert offer.status_code == 200
        events = offer.get_json()["data"]["events"]
        assert [e["to_status"] for e in events] == ["Applied", "Interview Scheduled", "Offer Received"]
        assert events[-1]["note"] == "Offer letter seen" and events[-1]["actor_user_id"] == world.people.ac.user_id

        client.post(url, headers=h, json={"status": "Rejected"})
        assert client.post(url, headers=h, json={"status": "Shortlisted"}).status_code == 422                    # closed is final
        listed = client.get(f"{API}/applications?open=true", headers=h).get_json()["data"]
        assert listed == []
        assert client.get(f"{API}/applications/{app_id}", headers=world.h(world.people.ac_vij)).status_code == 404

    def test_database_blocks_applying_to_an_inactive_opportunity(self, client, world, run_sql):
        opt_in(client, world, world.students.s1)
        created = client.post(f"{API}/opportunities", headers=world.h(world.people.ac), json={"title": "D", "employer_name": "E", "branch_id": 1})
        oid = created.get_json()["data"]["opportunity_id"]
        with pytest.raises(Exception, match="not open for applications"):
            run_sql("INSERT INTO applications (student_id, opportunity_id) VALUES (:s, :o)", s=world.students.s1.student_id, o=oid)


class TestProfilesAndSupport:
    def test_staff_review_readiness_and_skills(self, client, world):
        client.put(f"{ME}/profile", headers=world.h(world.students.s1), json={"opted_in": True, "skills": ["SQL", "Python"]})
        sid = world.students.s1.student_id
        listed = client.get(f"{API}/career-profiles", headers=world.h(world.people.ac)).get_json()["data"]
        assert [p["student"]["student_id"] for p in listed] == [sid]
        assert client.get(f"{API}/career-profiles", headers=world.h(world.people.ac_vij)).get_json()["data"] == []

        reviewed = client.post(f"{API}/career-profiles/{sid}/review", headers=world.h(world.people.ac), json={
            "readiness": "Ready for referral", "note": "Strong SQL", "skills": [{"name": "SQL", "confidence": "Verified"}]})
        assert reviewed.status_code == 200
        skills = client.get(f"{API}/career-profiles/{sid}", headers=world.h(world.people.ac)).get_json()["data"]["profile"]["skills"]
        assert skills == [{"name": "SQL", "confidence": "Verified"}, {"name": "Python", "confidence": "Student Reported"}]
        assert client.post(f"{API}/career-profiles/{sid}/review", headers=world.h(world.people.ac), json={
            "readiness": "In Preparation", "skills": [{"name": "Rust", "confidence": "Verified"}]}).status_code == 400
        assert client.get(f"{API}/career-profiles/{sid}", headers=world.h(world.people.ac_vij)).status_code == 404

    def test_only_an_admin_extends_the_support_period_with_a_reason(self, client, world):
        client.put(f"{ME}/profile", headers=world.h(world.students.s1), json={"opted_in": True})
        sid = world.students.s1.student_id
        url = f"{API}/career-profiles/{sid}/extend-support"
        end = (date.today() + timedelta(days=400)).isoformat()
        assert client.post(url, headers=world.h(world.people.ac), json={"support_end": end, "reason": "Agreed"}).status_code == 403
        assert client.post(url, headers=world.h(world.people.admin), json={"support_end": end}).status_code == 400
        assert client.post(url, headers=world.h(world.people.admin), json={"support_end": "2020-01-01", "reason": "Agreed"}).status_code == 400
        done = client.post(url, headers=world.h(world.people.admin), json={"support_end": end, "reason": "Longer accepted commitment"})
        assert done.get_json()["data"]["support_end"] == end
        assert db.session.execute(select(AuditLog).where(AuditLog.action == "CAREER_SUPPORT_EXTENDED")).scalars().first().reason


class TestOutcomes:
    def record(self, client, w, **extra):
        body = {"student_id": w.students.s1.student_id, "outcome_type": "Offer Received", "employer_name": "Example AI Labs",
                "role_title": "ML Intern", "event_date": "2026-09-25", **extra}
        return client.post(f"{API}/placement-outcomes", headers=w.h(w.people.ac), json=body)

    def test_an_outcome_counts_only_once_verified_by_someone_else(self, client, world):
        recorded = self.record(client, world)
        assert recorded.status_code == 201 and recorded.get_json()["data"]["verification_status"] == "Pending Verification"
        oid = recorded.get_json()["data"]["outcome_id"]
        url = f"{API}/placement-outcomes/{oid}/verify"
        assert client.get(f"{API}/placement-outcomes/summary", headers=world.h(world.people.bm)).get_json()["data"] == []

        assert client.post(url, headers=world.h(world.people.ac), json={"decision": "Verified", "evidence_note": "Offer letter"}).status_code == 422
        assert client.post(url, headers=world.h(world.people.bm), json={"decision": "Verified"}).status_code == 400
        assert client.post(url, headers=world.h(world.people.bm), json={"decision": "Verified", "evidence_note": "Offer letter seen"}).status_code == 200
        assert client.post(url, headers=world.h(world.people.bm), json={"decision": "Verified", "evidence_note": "again"}).status_code == 422

        summary = client.get(f"{API}/placement-outcomes/summary", headers=world.h(world.people.bm)).get_json()["data"]
        assert summary == [{"outcome_type": "Offer Received", "outcomes": 1, "students": 1}]
        assert client.get(f"{API}/placement-outcomes/summary", headers=world.h(world.people.bm_vij)).get_json()["data"] == []

    def test_a_rejected_outcome_never_counts_and_students_do_not_see_evidence(self, client, world):
        oid = self.record(client, world).get_json()["data"]["outcome_id"]
        client.post(f"{API}/placement-outcomes/{oid}/verify", headers=world.h(world.people.bm), json={"decision": "Rejected", "evidence_note": "No proof"})
        assert client.get(f"{API}/placement-outcomes/summary", headers=world.h(world.people.bm)).get_json()["data"] == []
        client.put(f"{ME}/profile", headers=world.h(world.students.s1), json={"opted_in": True})
        outcomes = client.get(ME, headers=world.h(world.students.s1)).get_json()["data"]["outcomes"]
        assert outcomes[0]["verification_status"] == "Rejected" and outcomes[0]["evidence_note"] is None

    def test_outcomes_are_scoped_to_the_branch(self, client, world):
        denied = client.post(f"{API}/placement-outcomes", headers=world.h(world.people.ac_vij), json={
            "student_id": world.students.s1.student_id, "outcome_type": "Joined", "employer_name": "E", "role_title": "R", "event_date": "2026-09-25"})
        assert denied.status_code == 404
        assert self.record(client, world, application_id=99999).status_code == 400
        assert client.get(f"{API}/placement-outcomes", headers=world.h(world.people.ac_vij)).get_json()["data"] == []

    def test_the_database_needs_evidence_and_an_independent_verifier(self, client, world, run_sql):
        oid = self.record(client, world).get_json()["data"]["outcome_id"]
        with pytest.raises(Exception, match="placement_outcomes_verified"):
            run_sql("UPDATE placement_outcomes SET verification_status = 'Verified', verified_by = :u, verified_at = now() WHERE outcome_id = :o",
                    u=world.people.bm.user_id, o=oid)

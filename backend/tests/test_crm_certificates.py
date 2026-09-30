"""db 070: certificates and completion authorisation sent to the CRM (outbox + status pull)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from config.database import db
from tests.test_certificates import issued, post, w  # noqa: F401  (w is the shared attendance-world fixture)

HEADERS = {"X-Service-Key": "test-crm-service-key"}


def _outbox(event_type: str) -> list[dict]:
    rows = db.session.execute(text("SELECT payload FROM crm_outbox WHERE event_type = :t ORDER BY outbox_id"), {"t": event_type})
    return [row[0] for row in rows]


def test_issue_reissue_and_revoke_are_sent_to_the_crm(client, w):
    assert _outbox("CertificateChanged") == []  # eligibility steps are not sent
    cid, done = issued(client, w)

    (issue,) = _outbox("CertificateChanged")
    assert issue["certificate_number"] == done["certificate_number"] and issue["status"] == "Issued"
    assert issue["version"] == 1 and issue["certificate_type"] == "Course Completion Certificate"
    assert issue["crm_admission_id"] and issue["crm_person_id"] and issue["course_code"] and issue["issued_by_email"]

    v2 = post(client, w, "bm", f"/certificates/{cid}/reissue", {"reason": "Name correction", "holder_name": "Anvitha Kolli"})
    assert v2.status_code == 201, v2.get_json()
    events = _outbox("CertificateChanged")
    assert sorted((e["version"], e["status"]) for e in events[1:]) == [(1, "Superseded"), (2, "Issued")]
    reissue = next(e for e in events if e["version"] == 2)
    assert reissue["supersedes_version"] == 1 and reissue["holder_name"] == "Anvitha Kolli"
    assert reissue["certificate_number"] == done["certificate_number"]

    revoked = post(client, w, "admin", f"/certificates/{v2.get_json()['data']['certificate_id']}/revocation", {"reason": "Record error"})
    assert revoked.status_code == 200, revoked.get_json()
    last = _outbox("CertificateChanged")[-1]
    assert last["status"] == "Revoked" and last["reason"] == "Record error" and last["revoked_by_email"]


def test_completion_authoriser_is_in_the_academic_state(client, w):
    issued(client, w)
    completed = [p for p in _outbox("AdmissionAcademicsChanged") if p["enrolment_status"] == "Completed"]
    assert completed and completed[-1]["completion_authorised_by_email"] == w.ac.email
    assert completed[-1]["academic_completed_at"]


def test_status_pull_includes_issued_certificates(client, w):
    before = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _, done = issued(client, w)

    data = client.get("/api/v1/integrations/crm/status", headers=HEADERS, query_string={"since": before}).get_json()["data"]

    assert [c["certificate_number"] for c in data["certificates"]] == [done["certificate_number"]]

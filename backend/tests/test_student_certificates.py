"""UX phase U10: the student's Certificates screen (a card per course with a tracker and the blocker) and the certificate PDF."""
import pytest
from reportlab import rl_config
from sqlalchemy import select

from config.database import db
from models import AuditLog
from tests import attendance_world
from tests.test_certificates import API, change, complete, decide, issued, post, w  # noqa: F401 (w is a fixture)


@pytest.fixture(autouse=True)
def readable_pdfs(monkeypatch):
    """Leave page streams uncompressed so a test can look for the text drawn on the page."""
    monkeypatch.setattr(rl_config, "pageCompression", 0)


def mine(client, w, who="s1"):
    response = client.get(f"{API}/me/certificates", headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def card_of(client, w, who="s1"):
    (card,) = mine(client, w, who)["cards"]
    return card


def states(card) -> list[str]:
    return [step["state"] for step in card["steps"]]


def pdf(client, w, cid, who="s1"):
    return client.get(f"{API}/me/certificates/{cid}/pdf", headers=w.h[who])


# ---------------------------------------------------------------- the card and its tracker

def test_a_course_still_being_studied_shows_the_first_step_as_current(client, w):
    card = card_of(client, w)
    assert card["course"]["course_code"] == "NIT-CRS-047"
    assert card["certificate"] is None and card["certificate_type"] == "Course Completion Certificate"
    assert states(card) == ["current", "todo", "todo"] and [s["key"] for s in card["steps"]] == ["completed", "review", "issued"]
    assert card["blocker"] == {"code": "not_completed", "params": {}} and card["can_download"] is False and card["fee"] is None


def test_the_tracker_follows_the_certificate_from_review_to_issued(client, w):
    cid = complete(client, w)
    card = card_of(client, w)
    assert (card["certificate"]["status"], states(card), card["blocker"]["code"]) == ("Eligibility Review", ["done", "current", "todo"], "in_review")
    assert card["fee"] == {"state": "Cleared", "cleared": True, "balance": "0.00"}

    post(client, w, "bm", f"/certificates/{cid}/approval")
    card = card_of(client, w)
    assert (states(card), card["blocker"]["code"], card["can_download"]) == (["done", "done", "current"], "ready_to_issue", False)

    post(client, w, "bm", f"/certificates/{cid}/issue")
    card = card_of(client, w)
    assert states(card) == ["done", "done", "done"] and card["blocker"] is None and card["can_download"] is True
    assert card["verify_path"] == f"/verify/{card['certificate']['certificate_number']}"
    assert card["certificate"]["issue_date"] is not None


def test_an_unpaid_fee_is_the_blocker_in_plain_terms(client, w, run_sql):
    attendance_world.set_fee(run_sql, w.e1, balance=5000)
    complete(client, w)
    card = card_of(client, w)
    assert card["blocker"] == {"code": "fee_outstanding", "params": {"balance": "5000.00"}}
    assert card["fee"]["state"] == "Outstanding" and card["fee"]["cleared"] is False
    assert states(card) == ["done", "current", "todo"]

    run_sql("DELETE FROM finance_summaries")  # nothing has arrived from the CRM
    assert card_of(client, w)["blocker"] == {"code": "fee_unknown", "params": {}}


def test_a_revoked_certificate_says_why_and_cannot_be_downloaded(client, w):
    cid, _ = issued(client, w)
    request_id = change(client, w, "ac", cid, "Revocation", reason="Record error", evidence="Wrong enrolment").get_json()["data"]["request_id"]
    assert decide(client, w, "founder", request_id).status_code == 200
    card = card_of(client, w)
    assert card["blocker"] == {"code": "revoked", "params": {"reason": "Record error"}} and card["can_download"] is False
    assert card["certificate"]["status"] == "Revoked" and card["verify_path"] is None


def test_the_old_keys_are_still_there_and_each_student_sees_only_their_own(client, w):
    complete(client, w)
    data = mine(client, w)
    assert len(data["certificates"]) == 1 and data["configuration_pending"] == []
    other = mine(client, w, "s2")
    assert [c["enrolment"]["enrolment_id"] for c in other["cards"]] == [w.e2]
    assert other["cards"][0]["certificate"]["status"] == "Not Yet Eligible" and states(other["cards"][0]) == ["current", "todo", "todo"]
    assert client.get(f"{API}/me/certificates", headers=w.h["ac"]).status_code == 403


# ---------------------------------------------------------------- the PDF

def test_the_owner_downloads_the_pdf_of_an_issued_certificate(client, w, app):
    cid, done = issued(client, w)
    app.config["PUBLIC_BASE_URL"] = "https://lms.example.test/"
    response = pdf(client, w, cid)
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF") and response.data.rstrip().endswith(b"%%EOF")
    number = done["certificate_number"]
    assert response.headers["Content-Disposition"] == f'attachment; filename="{number}.pdf"'
    assert response.headers["Cache-Control"] == "private, no-store"
    for text in (b"Anvitha K.", number.encode(), b"Certificate of Completion", b"https://lms.example.test/verify/" + number.encode()):
        assert text in response.data, text
    audited = db.session.execute(select(AuditLog.action).where(AuditLog.entity_type == "certificate", AuditLog.action == "CERTIFICATE_DOWNLOADED")).scalars().all()
    assert audited == ["CERTIFICATE_DOWNLOADED"]


def test_without_a_public_address_the_pdf_has_no_qr_code_but_still_names_the_number(client, w, app):
    cid, done = issued(client, w)
    app.config["PUBLIC_BASE_URL"] = None
    response = pdf(client, w, cid)
    assert response.status_code == 200 and f"/verify/{done['certificate_number']}".encode() in response.data


def test_only_the_owning_student_can_download(client, w):
    cid, _ = issued(client, w)
    assert pdf(client, w, cid, "s2").status_code == 404                      # another student: it does not exist for them
    assert pdf(client, w, cid, "ac").status_code == 403                      # staff use the register, not the student download
    assert pdf(client, w, cid, "admin").status_code == 403
    assert client.get(f"{API}/me/certificates/{cid}/pdf").status_code == 401
    assert pdf(client, w, 999999).status_code == 404


def test_a_certificate_that_is_not_issued_has_no_pdf(client, w):
    cid = complete(client, w)
    blocked = pdf(client, w, cid)
    assert blocked.status_code == 422 and "not been issued" in blocked.get_json()["error"]["message"]
    post(client, w, "bm", f"/certificates/{cid}/approval")
    assert pdf(client, w, cid).status_code == 422                            # approved is not issued


def test_a_revoked_certificate_has_no_pdf(client, w):
    cid, _ = issued(client, w)
    request_id = change(client, w, "ac", cid, "Revocation", reason="Record error", evidence="Wrong enrolment").get_json()["data"]["request_id"]
    decide(client, w, "founder", request_id)
    refused = pdf(client, w, cid)
    assert refused.status_code == 422 and "revoked" in refused.get_json()["error"]["message"]


def test_a_corrected_version_is_drawn_from_its_own_data_and_the_old_one_is_refused(client, w):
    cid, done = issued(client, w)
    request_id = change(client, w, "ac", cid, "Correction", reason="Name correction", holder_name="Anvitha Kolli").get_json()["data"]["request_id"]
    decide(client, w, "admin", request_id)
    card = card_of(client, w)
    assert card["certificate"]["version"] == 2 and card["certificate"]["certificate_id"] != cid and card["can_download"] is True

    old = pdf(client, w, cid)
    assert old.status_code == 422 and "corrected version" in old.get_json()["error"]["message"]
    current = pdf(client, w, card["certificate"]["certificate_id"])
    assert current.status_code == 200 and b"Anvitha Kolli" in current.data and b"\\(version 2\\)" in current.data
    assert current.headers["Content-Disposition"] == f'attachment; filename="{done["certificate_number"]}-v2.pdf"'


def test_a_name_the_standard_fonts_cannot_draw_is_replaced_not_dropped(client, w, run_sql):
    cid, _ = issued(client, w)
    run_sql("UPDATE certificates SET holder_name = :name WHERE certificate_id = :id", name="Anvitha అ", id=cid)
    response = pdf(client, w, cid)
    assert response.status_code == 200 and b"Anvitha ?" in response.data

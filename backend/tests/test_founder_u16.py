"""UX phase U16: the Founder's inbox, the AI budget, the Branch Managers' own requests that the Founder decides, and the CRM-connected flag."""

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog
from tests import attendance_world
from tests.test_attendance import correction, decide as decide_correction
from tests.test_certificates import change, complete, decide as decide_certificate, issued, post as post_as, w  # noqa: F401
from tests.test_crm_branches_finance import snapshot
from tests.test_delivery import call, data, future, iso, world  # noqa: F401

API = attendance_world.API


# ---------------------------------------------------------------- the inbox

def inbox(client, w, who, group=None):
    response = client.get(f"{API}/founder/inbox" + (f"?group={group}" if group else ""), headers=w.h[who])
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def test_only_the_founder_and_super_admin_open_the_inbox(client, w):
    for who in ("t1", "s1"):
        assert client.get(f"{API}/founder/inbox", headers=w.h[who]).status_code == 403
    assert client.get(f"{API}/founder/inbox?group=nope", headers=w.h["founder"]).status_code == 400
    assert inbox(client, w, "admin")["total"] == inbox(client, w, "founder")["total"]


def test_the_inbox_lists_each_kind_oldest_first_and_feeds_the_nav_badges(client, w, run_sql):
    cid, _ = issued(client, w)
    revocation = change(client, w, "ac", cid, "Revocation", reason="Record error", evidence="Wrong enrolment").get_json()["data"]
    attendance_world.set_fee(run_sql, w.e2, balance=5000)
    cid2 = complete(client, w, w.e2)
    exception = post_as(client, w, "ac", f"/certificates/{cid2}/financial-exception", {"reason": "Scholarship letter pending"}).get_json()["data"]

    view = inbox(client, w, "founder")
    kinds = [i["kind"] for i in view["items"]]
    assert kinds == ["certificate", "fee_exception", "ai_budget"]  # oldest first; the undated AI budget last
    cert, fee, ai = view["items"]
    assert cert["title"].startswith("Revocation of certificate NIT-CERT-") and cert["where"] and cert["from_branch_manager"] is True
    assert cert["detail"]["request_id"] == revocation["request_id"] and cert["detail"]["actions"] == ["decide"] and cert["detail"]["reason"] == "Record error"
    assert fee["id"] == exception["exception_id"] and "₹5,000" in fee["title"] and fee["detail"]["actions"] == ["decide"]
    assert ai["detail"] == {"state": "Configuration Pending"} and ai["since"] is None
    assert view["counts"]["certificate"] == 1 and view["counts"]["fee_exception"] == 1 and view["total"] == 3 and view["crm_connected"] is False

    assert [i["kind"] for i in inbox(client, w, "founder", "certificates")["items"]] == ["certificate", "fee_exception"]
    assert [i["kind"] for i in inbox(client, w, "founder", "other")["items"]] == ["ai_budget"]
    assert inbox(client, w, "founder", "access")["items"] == []
    assert client.get(f"{API}/founder/inbox?group=curriculum", headers=w.h["founder"]).status_code == 400  # the group is gone

    badges = client.get(f"{API}/me/nav-counts?workspace=founder", headers=w.h["founder"]).get_json()["data"]
    assert {k: badges[k] for k in ("inbox", "certificates", "access")} == {"inbox": 3, "certificates": 2, "access": 0}
    assert "curriculum" not in badges
    assert {"home", "users", "issues", "calendar", "crm_sync", "student_accounts", "setup"} <= set(badges)  # plus everything the Super Admin's nav counts

    # a decision takes the item out of the inbox
    assert decide_certificate(client, w, "founder", revocation["request_id"], "Rejected", "Evidence is not enough").status_code == 200
    assert [i["kind"] for i in inbox(client, w, "founder")["items"]] == ["fee_exception", "ai_budget"]


def test_a_request_the_person_made_is_not_in_their_own_inbox(client, w):
    cid, _ = issued(client, w)
    change(client, w, "admin", cid, "Revocation", reason="Duplicate", evidence="Same student twice")
    mine = inbox(client, w, "admin")
    assert [(i["kind"], i["can_decide"]) for i in mine["items"] if i["kind"] == "certificate"] == [("certificate", False)]  # listed, another approver decides it
    assert mine["counts"]["certificate"] == 0 and mine["total"] == 1  # only the AI budget is the Super Admin's to decide
    assert [(i["kind"], i["can_decide"]) for i in inbox(client, w, "founder")["items"] if i["kind"] == "certificate"] == [("certificate", True)]
    badges = client.get(f"{API}/me/nav-counts", headers=w.h["admin"]).get_json()["data"]
    assert "certificates" not in badges or badges["certificates"] == 0


def test_access_extensions_reach_the_inbox_with_the_branch_managers_recommendation(client, w, run_sql):
    for enrolment, note in ((w.e1, None), (w.e2, "Placed late")):
        student = w.s1 if enrolment == w.e1 else w.s2
        run_sql("INSERT INTO access_extension_requests (enrolment_id, student_id, branch_id, scope, reason, needs_exception, original_expiry) "
                "VALUES (:e, :s, 1, 'Recording', 'Project revision', true, '2026-01-01')", e=enrolment, s=student.student_id)
    assert inbox(client, w, "founder", "access")["items"] == []  # nobody recommended yet: it waits for the Branch Manager
    run_sql("UPDATE access_extension_requests SET recommended_decision = 'approve', recommendation = 'Placed late', recommended_by = :u, "
            "recommended_at = now(), recommended_expiry = '2027-06-30' WHERE enrolment_id = :e", u=w.ac.user_id, e=w.e2)
    items = inbox(client, w, "founder", "access")["items"]
    assert len(items) == 1 and items[0]["kind"] == "access_extension" and items[0]["title"] == "Access beyond two years for Learner Two"
    assert items[0]["detail"]["recommendation"]["note"] == "Placed late" and items[0]["detail"]["with_founder"] is True and items[0]["detail"]["can_decide"] is True
    badges = client.get(f"{API}/me/nav-counts?workspace=founder", headers=w.h["founder"]).get_json()["data"]
    assert badges["access"] == 1


# ---------------------------------------------------------------- the AI budget

def test_the_founder_approves_the_ai_budget_and_it_leaves_the_inbox(client, w):
    url = f"{API}/founder/ai-budget"
    assert client.put(url, json={"amount_inr": 25000}, headers=w.h["ac"]).status_code == 403
    assert client.put(url, json={}, headers=w.h["founder"]).status_code == 400
    assert client.put(url, json={"amount_inr": 0}, headers=w.h["founder"]).status_code == 400
    assert client.put(url, json={"amount_inr": 99999999999}, headers=w.h["founder"]).status_code == 400
    saved = client.put(url, json={"amount_inr": 25000}, headers=w.h["founder"])
    assert saved.status_code == 200 and saved.get_json()["data"] == {"state": "Configured", "amount_inr": 25000}
    assert [i for i in inbox(client, w, "founder")["items"] if i["kind"] == "ai_budget"] == []
    summary = client.get(f"{API}/founder/summary", headers=w.h["founder"]).get_json()["data"]
    assert summary["decisions"]["ai_ceiling"] == {"state": "Configured", "amount_inr": 25000}
    audit = db.session.execute(select(AuditLog).where(AuditLog.action == "AI_BUDGET_APPROVED")).scalar_one()
    assert audit.new_values == {"amount_inr": 25000} and audit.old_values == {"amount_inr": None}


# ---------------------------------------------------------------- Branch Managers' own requests

def bm_items(client, w):
    return [i for i in inbox(client, w, "founder", "other")["items"] if i["kind"].startswith("bm_")]


def test_a_branch_managers_own_attendance_correction_is_decided_by_the_founder(client, w):
    own = correction(client, w, "ac", w.older, w.e1, "Absent", "Wrong entry").get_json()["data"]["correction_id"]
    trainers = correction(client, w, "t1", w.older, w.e2, "Present", "Marked late").get_json()["data"]["correction_id"]
    items = bm_items(client, w)
    assert [(i["kind"], i["id"]) for i in items] == [("bm_correction", own)]  # the trainer's goes to the Branch Manager
    assert items[0]["from_branch_manager"] is True and "Coordinator Guntur asks to change attendance" in items[0]["title"]
    assert decide_correction(client, w, "founder", trainers, "Rejected", "Not now").status_code == 200  # the Founder decides any branch's correction too
    assert decide_correction(client, w, "founder", own, "Rejected").status_code == 400  # a rejection needs a note
    done = decide_correction(client, w, "founder", own, "Rejected", "The register is right")
    assert done.status_code == 200 and done.get_json()["data"]["status"] == "Rejected"
    assert bm_items(client, w) == []
    listed = client.get(f"{API}/attendance/corrections?status=Pending", headers=w.h["ac"]).get_json()["data"]
    assert [c["correction_id"] for c in listed] == []  # the Founder already decided both


def test_a_branch_managers_own_reschedule_request_is_decided_by_the_founder(client, w, login, make_session, run_sql):
    """A request a person raised while they held both roles (before the split) still has a Branch Manager as requester."""
    own_session = make_session(w.b1, w.t1, future(3, 10), title="Own class")
    other_session = make_session(w.b1, w.t1, future(5, 10), title="Other class")

    def ask(session, day):
        return client.post(f"{API}/class-sessions/{session.session_id}/reschedule-requests", headers=w.h["t1"], json={
            "proposed_starts_at": iso(future(day, 10)), "proposed_ends_at": iso(future(day, 12)), "reason": "Away that day"}).get_json()["data"]

    mine = ask(own_session, 4)
    theirs = ask(other_session, 6)
    run_sql("UPDATE session_change_requests SET requested_by = :bm WHERE request_id = :r", bm=w.ac.user_id, r=mine["request_id"])

    items = bm_items(client, w)
    assert [(i["kind"], i["id"]) for i in items] == [("bm_reschedule", mine["request_id"])]
    assert items[0]["title"] == "Coordinator Guntur asks to move Own class" and items[0]["detail"]["can_decide"] is True
    assert client.post(f"{API}/reschedule-requests/{mine['request_id']}/reject", json={"note": "No"}, headers=w.h["ac"]).status_code == 422
    done = client.post(f"{API}/reschedule-requests/{mine['request_id']}/reject", json={"note": "Please keep the date"}, headers=w.h["founder"])
    assert done.status_code == 200 and done.get_json()["data"]["status"] == "Rejected"
    assert bm_items(client, w) == []


# ---------------------------------------------------------------- the CRM tiles

def test_the_founder_summary_says_when_the_crm_has_sent_its_figures(client, w, crm_event):
    summary = lambda: client.get(f"{API}/founder/summary", headers=w.h["founder"]).get_json()["data"]  # noqa: E731
    assert summary()["crm_connected"] is False and inbox(client, w, "founder")["crm_connected"] is False
    assert crm_event("BranchFinanceSnapshot", snapshot()).status_code == 201
    assert summary()["crm_connected"] is True and inbox(client, w, "founder")["crm_connected"] is True


def test_a_branch_manager_sees_only_certificate_requests_and_waits_for_an_admin_on_their_own(client, w):
    """The same inbox serves the Branch Manager's section in Completion: certificate requests only, never the other kinds. What a
    Branch Manager asked for is listed as waiting: the Founder or a Super Admin decides it."""
    cid, _ = issued(client, w)
    asked = change(client, w, "ac", cid, "Correction", reason="Name misspelt", holder_name="Learner One").get_json()["data"]
    view = inbox(client, w, "ac")
    assert {i["kind"] for i in view["items"]} <= {"certificate", "fee_exception"}  # no AI budget, no access extensions
    mine = [i for i in view["items"] if i["id"] == asked["request_id"]]
    assert len(mine) == 1 and mine[0]["can_decide"] is False and view["total"] == 0 and view["counts"]["certificate"] == 0
    assert [i["kind"] for i in inbox(client, w, "ac", "other")["items"]] == []
    assert [i["can_decide"] for i in inbox(client, w, "admin")["items"] if i["id"] == asked["request_id"]] == [True]

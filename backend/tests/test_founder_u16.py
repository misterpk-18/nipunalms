"""UX phase U16: the Founder's inbox, "Approve & activate" for curriculum with an optional activation day, the summary of what a version
changes, the AI budget, the Branch Managers' own requests that the Founder decides, and the CRM-connected flag."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from config.database import db
from config.timezone import today_ist
from models import AuditLog, CurriculumVersion
from services import curriculum as curriculum_service
from services import jobs
from tests import attendance_world
from tests.test_attendance import correction, decide as decide_correction
from tests.test_certificates import change, complete, decide as decide_certificate, issued, post as post_as, w  # noqa: F401
from tests.test_crm_branches_finance import snapshot
from tests.test_delivery import call, complete_draft, data, future, iso, world  # noqa: F401

API = attendance_world.API


# ---------------------------------------------------------------- curriculum: Approve & activate

def _submitted(client, login, people, label, topic="Basics"):
    """A complete draft of a course with no active version of its own, submitted for review by the branch manager."""
    course_id = next(c["course_id"] for c in client.get(f"{API}/reference/courses", headers=login(people["ac"].email)).get_json()["data"]
                     if c["course_code"] == "NIT-CRS-052")
    vid = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id, "version_label": label, "blank": True}), 201)["curriculum_version_id"]
    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/modules", json={"title": topic}), 201)
    call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": f"{topic} one"})
    complete_draft(client, login, people["ac"], vid)
    data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit"), 200)
    return vid


def _version(vid) -> CurriculumVersion:
    db.session.expire_all()
    return db.session.get(CurriculumVersion, vid)


def test_approve_alone_keeps_the_version_approved(world, client, login):
    people, _, _ = world
    vid = _submitted(client, login, people, "CV 7.0")
    approved = data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve"), 200)
    assert approved["status"] == "Approved" and approved["activate_on"] is None and approved["released"] is None


def test_approve_and_activate_in_one_step_with_today(world, client, login):
    people, _, _ = world
    vid = _submitted(client, login, people, "CV 7.0")
    done = data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": today_ist().isoformat()}), 200)
    assert done["status"] == "Active" and done["activate_on"] is None and set(done["released"]) == {"enrolments_released", "batches_mapped"}
    assert [e["action"] for e in done["events"]][-2:] == ["Approved", "Activated"]
    assert db.session.execute(select(AuditLog.action).where(AuditLog.action == "CURRICULUM_MAPPING_RELEASED")).first() is not None


def test_a_later_day_schedules_the_activation_and_the_job_activates_it_that_day(world, client, login, run_sql):
    people, _, _ = world
    vid = _submitted(client, login, people, "CV 7.0")
    tomorrow = (today_ist() + timedelta(days=1)).isoformat()
    scheduled = data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": tomorrow}), 200)
    assert scheduled["status"] == "Approved" and scheduled["activate_on"] == tomorrow and scheduled["released"] is None
    assert "Activates on" in scheduled["events"][-1]["note"]

    inbox = data(call(client, login, people["founder"], "get", "/founder/inbox"), 200)
    assert [i for i in inbox["items"] if i["kind"] == "curriculum"] == []  # nothing waits for the Founder any more
    assert [s["curriculum_version_id"] for s in inbox["scheduled"]] == [vid]

    assert jobs.curriculum_activate() == {"activated": []}  # tomorrow has not come
    run_sql("UPDATE curriculum_versions SET activate_on = :d WHERE curriculum_version_id = :v", d=today_ist().isoformat(), v=vid)
    assert jobs.curriculum_activate() == {"activated": ["CV 7.0"]}
    version = _version(vid)
    assert version.status == "Active" and version.activate_on is None
    assert jobs.curriculum_activate() == {"activated": []}  # once only


def test_the_day_cannot_be_in_the_past_and_a_retired_version_loses_its_day(world, client, login):
    people, _, _ = world
    vid = _submitted(client, login, people, "CV 7.0")
    yesterday = (today_ist() - timedelta(days=1)).isoformat()
    refused = call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": yesterday})
    assert refused.status_code == 400 and _version(vid).status == "Under Review"
    assert call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": "soon"}).status_code == 400

    tomorrow = (today_ist() + timedelta(days=1)).isoformat()
    data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": tomorrow}), 200)
    retired = data(call(client, login, people["founder"], "post", f"/curriculum-versions/{vid}/retire", json={"reason": "Changed our mind"}), 200)
    assert retired["status"] == "Retired" and retired["activate_on"] is None


def test_you_cannot_approve_and_activate_what_you_submitted(world, client, login):
    people, _, _ = world
    course_id = next(c["course_id"] for c in client.get(f"{API}/reference/courses", headers=login(people["admin"].email)).get_json()["data"]
                     if c["course_code"] == "NIT-CRS-052")
    vid = data(call(client, login, people["admin"], "post", "/curriculum-versions", json={"course_id": course_id, "version_label": "CV 8"}), 201)["curriculum_version_id"]
    module = data(call(client, login, people["admin"], "post", f"/curriculum-versions/{vid}/modules", json={"title": "M"}), 201)
    call(client, login, people["admin"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "T"})
    complete_draft(client, login, people["admin"], vid)
    data(call(client, login, people["admin"], "post", f"/curriculum-versions/{vid}/submit"), 200)
    assert call(client, login, people["admin"], "post", f"/curriculum-versions/{vid}/approve", json={"activate_on": today_ist().isoformat()}).status_code == 422
    assert _version(vid).status == "Under Review"
    # and it is not in the submitter's inbox, only in the other approver's
    assert data(call(client, login, people["admin"], "get", "/founder/inbox?group=curriculum"), 200)["items"] == []
    assert [i["id"] for i in data(call(client, login, people["founder"], "get", "/founder/inbox?group=curriculum"), 200)["items"]] == [vid]


def test_the_summary_says_what_changes_and_who_is_affected(world, client, login, make_batch, allocate):
    from repositories import catalog as catalog_repo
    from tests.test_delivery import _java_version
    people, _, student = world
    course_id = catalog_repo.get_course_by_code("NIT-CRS-047").course_id
    running = make_batch(1, trainers=[people["g1"]], state="Running", curriculum_version_id=_java_version())
    allocate(student, running)
    draft = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id}), 201)  # copies the Active version
    vid = draft["curriculum_version_id"]
    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/modules", json={"title": "Cloud basics"}), 201)
    call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "Deploying to the cloud"})
    complete_draft(client, login, people["ac"], vid)
    data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/submit"), 200)

    impact = data(call(client, login, people["founder"], "get", f"/curriculum-versions/{vid}/impact"), 200)
    assert impact["version_label"] == draft["version_label"] and impact["previous"]["version_label"] == "CV 5.1"
    assert impact["submitted_by"]["full_name"] == "AC Guntur"
    assert "Deploying to the cloud" in impact["added_topics"] and impact["removed_topics"] == []
    assert impact["what_changes"][0].startswith("Compared with CV 5.1: 1 module added, 0 modules removed; 1 topic added, 0 topics removed")
    assert impact["who_is_affected"] == ["1 batch with no curriculum yet (0 students) would get it as soon as it is active.",
                                         "1 batch (1 student) stay on CV 5.1."]
    assert impact["batches_getting_it"] == 1 and impact["batches_staying"] == 1
    assert impact["outline"][-1] == {"module": "Cloud basics", "topics": ["Deploying to the cloud"]}
    assert call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}/impact").status_code == 403  # approvers only
    assert call(client, login, people["admin"], "get", f"/curriculum-versions/{vid}/impact").status_code == 200
    assert call(client, login, people["founder"], "get", "/curriculum-versions/999999/impact").status_code == 404


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
    assert inbox(client, w, "founder", "curriculum")["items"] == [] and inbox(client, w, "founder", "access")["items"] == []

    badges = client.get(f"{API}/me/nav-counts?workspace=founder", headers=w.h["founder"]).get_json()["data"]
    assert {k: badges[k] for k in ("inbox", "curriculum", "certificates", "access")} == {"inbox": 3, "curriculum": 0, "certificates": 2, "access": 0}
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
    assert decide_correction(client, w, "founder", trainers).status_code == 403  # the Founder only decides a Branch Manager's own
    assert decide_correction(client, w, "founder", own, "Rejected").status_code == 400  # a rejection needs a note
    done = decide_correction(client, w, "founder", own, "Rejected", "The register is right")
    assert done.status_code == 200 and done.get_json()["data"]["status"] == "Rejected"
    assert bm_items(client, w) == []
    listed = client.get(f"{API}/attendance/corrections?status=Pending", headers=w.h["ac"]).get_json()["data"]
    assert [c["correction_id"] for c in listed] == [trainers]


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
    assert client.post(f"{API}/reschedule-requests/{theirs['request_id']}/reject", json={"note": "No"}, headers=w.h["founder"]).status_code == 403
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

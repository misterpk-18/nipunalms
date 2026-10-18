"""UX phase U15: the Branch Manager's Issues inbox, Curriculum checklist and auto names, Marks gaps and publish preview, Content & questions
claim and counts, Recordings problem reasons, Student support views, access-extension recommendation, Completion pipeline, Attendance
counts and Reports with CSV export."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, Notification
from services import exports
from tests import attendance_world, helpers
from tests import library_helpers as h
from tests.library_helpers import API, auth, get, post
from tests.services_fixtures import world as service_world  # noqa: F401
from tests.test_delivery import _java_version, call, data, world  # noqa: F401


# ---------------------------------------------------------------- Issues

def test_issues_are_one_paged_role_aware_list_with_go_fix_links(client, login, catalog, make_user, make_student, make_batch, run_sql):
    ac = make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM Guntur")
    other = make_user(roles=[("BRANCH_MANAGER", 2)], full_name="BM Vijayawada")
    sa = make_user(roles=[("SUPER_ADMIN", None)])
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    trainer = make_user(roles=[("TRAINER", 1)])
    students = [make_student(person_id=f"P-I{i}", admission_id=f"A-I{i}", email=f"i{i}@example.test") for i in range(3)]
    run_sql("INSERT INTO crm_events (event_id, event_type, source_version, occurred_at, payload, status, error) "
            "VALUES ('evt-x', 'AdmissionQualified', 1, now(), '{}', 'Failed', 'Unknown course')")

    page = client.get(f"{API}/issues?per_page=2", headers=login(ac.email)).get_json()
    assert page["meta"]["total"] == 3 and page["meta"]["pages"] == 2 and len(page["data"]) == 2  # real paging, exact total
    second = client.get(f"{API}/issues?per_page=2&page=2", headers=login(ac.email)).get_json()
    assert len(second["data"]) == 1 and {i["id"] for i in page["data"]}.isdisjoint({i["id"] for i in second["data"]})
    item = page["data"][0]
    assert item["type"] == "students" and item["go_fix"] == {"to": "/branch/waiting", "search": {}} and item["can_note"] is True
    assert page["meta"]["counts"]["students"] == 3 and page["meta"]["counts"]["system"] == 0 and page["meta"]["counts"]["all"] == 3

    # company-wide items belong to the Super Admin (the Founder can do what the Super Admin can, notes included)
    everything = client.get(f"{API}/issues?type=system", headers=login(sa.email)).get_json()
    assert everything["meta"]["total"] == 1 and everything["data"][0]["go_fix"]["to"] == "/admin/crm-sync"
    assert client.get(f"{API}/issues?type=system", headers=login(ac.email)).get_json()["meta"]["total"] == 0
    assert client.get(f"{API}/issues", headers=login(other.email)).get_json()["meta"]["total"] == 0
    read_only = client.get(f"{API}/issues?type=students", headers=login(founder.email)).get_json()["data"][0]
    assert read_only["can_note"] is True

    # "Go fix it" follows the session's role: the Super Admin and Founder never get a /branch/* link (decision 19), they get a read-only detail
    for who, prefix in ((sa, "/admin"), (founder, "/founder")):
        rows = client.get(f"{API}/issues", headers=login(who.email)).get_json()["data"]
        assert rows and not any(r["go_fix"]["to"].startswith("/branch") for r in rows), prefix
        student_issue = next(r for r in rows if r["type"] == "students")
        assert student_issue["go_fix"]["to"] == f"{prefix}/issues/{student_issue['source']}/{student_issue['source_id']}"
        assert next(r for r in rows if r["type"] == "system")["go_fix"]["to"] == f"{prefix}/crm-sync"
        detail = client.get(f"{API}/issues/{student_issue['source']}/{student_issue['source_id']}", headers=login(who.email))
        assert detail.status_code == 200 and detail.get_json()["data"]["id"] == student_issue["id"] and detail.get_json()["data"]["can_assign"] is True
    mine = page["data"][0]
    assert client.get(f"{API}/issues/{mine['source']}/{mine['source_id']}", headers=login(ac.email)).status_code == 200
    assert client.get(f"{API}/issues/{mine['source']}/{mine['source_id']}", headers=login(other.email)).status_code == 404  # another branch
    assert client.get(f"{API}/issues/{mine['source']}/{mine['source_id']}", headers=login(trainer.email)).status_code == 403
    assert client.get(f"{API}/issues", headers=login(trainer.email)).status_code == 403
    assert client.get(f"{API}/issues?type=nope", headers=login(ac.email)).status_code == 400

    # filters: owner and age
    assert client.get(f"{API}/issues?owner=none", headers=login(ac.email)).get_json()["meta"]["total"] == 3
    assert client.get(f"{API}/issues?owner=me", headers=login(ac.email)).get_json()["meta"]["total"] == 0
    assert client.get(f"{API}/issues?age=today", headers=login(sa.email)).get_json()["meta"]["total"] == 4
    run_sql("UPDATE crm_events SET received_at = now() - interval '10 days' WHERE event_id = 'evt-x'")
    assert client.get(f"{API}/issues?age=over_7", headers=login(sa.email)).get_json()["meta"]["total"] == 1
    assert client.get(f"{API}/issues?age=over_30", headers=login(sa.email)).get_json()["meta"]["total"] == 0
    assert client.get(f"{API}/issues?age=today", headers=login(sa.email)).get_json()["meta"]["total"] == 3

    # "Add note" is the recovery step: the person becomes the owner and the filter follows
    first = page["data"][0]
    logged = client.post(f"{API}/exceptions/{first['source']}/{first['source_id']}/steps", json={"reason": "Calling the student today"},
                         headers=login(ac.email))
    assert logged.status_code == 201
    assert client.get(f"{API}/issues?owner=me", headers=login(ac.email)).get_json()["meta"]["total"] == 1


# ---------------------------------------------------------------- Curriculum

def test_new_drafts_are_named_for_you_and_copy_the_active_version(world, client, login):
    people, _, _ = world
    from repositories import catalog as catalog_repo
    course_id = catalog_repo.get_course_by_code("NIT-CRS-047").course_id
    active = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{_java_version()}"), 200)
    draft = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id}), 201)
    assert active["version_label"] == "CV 5.1" and draft["version_label"] == "CV 5.2" and draft["status"] == "Draft"
    assert len(draft["modules"]) == len(active["modules"])
    # a second draft cannot start while one is open; after discarding, the next name is free again
    assert call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id}).status_code == 409
    assert call(client, login, people["ac"], "delete", f"/curriculum-versions/{draft['curriculum_version_id']}").status_code == 204
    blank = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id, "blank": True}), 201)
    assert blank["version_label"] == "CV 5.2" and blank["modules"] == []


def test_the_submit_checklist_marks_incomplete_topics_by_name(world, client, login):
    people, _, _ = world
    from repositories import catalog as catalog_repo
    course_id = catalog_repo.get_course_by_code("NIT-CRS-047").course_id
    draft = data(call(client, login, people["ac"], "post", "/curriculum-versions", json={"course_id": course_id, "blank": True}), 201)
    vid = draft["curriculum_version_id"]
    checklist = draft["checklist"]
    assert [s["key"] for s in checklist["steps"]] == ["modules", "topics", "hours", "rules", "assessments"]
    assert checklist["ready"] is False and checklist["next"] == "modules"

    module = data(call(client, login, people["ac"], "post", f"/curriculum-versions/{vid}/modules", json={"title": "Core Java"}), 201)
    topic = data(call(client, login, people["ac"], "post", f"/curriculum-modules/{module['module_id']}/topics", json={"title": "Streams"}), 201)
    steps = {s["key"]: s for s in data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["checklist"]["steps"]}
    assert steps["modules"]["done"] is True and steps["topics"]["done"] is False
    marked = steps["topics"]["items"][0]
    assert marked["topic_id"] == topic["topic_id"] and marked["title"] == "Streams" and marked["module_title"] == "Core Java"
    assert set(marked["missing"]) == {"outcome", "estimated minutes", "progress weight", "evidence of completion"}
    from tests.test_delivery import complete_draft
    complete_draft(client, login, people["ac"], vid)
    done = data(call(client, login, people["ac"], "get", f"/curriculum-versions/{vid}"), 200)["checklist"]
    assert done["ready"] is True and done["next"] is None and all(s["done"] for s in done["steps"] if s["required"])


# ---------------------------------------------------------------- Access extensions beyond the limit

@pytest.fixture
def library_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql):
    return h.build_world(catalog, make_user, make_student, make_batch, make_session, allocate, run_sql)


def test_the_branch_manager_recommends_and_the_request_goes_to_the_founder(client, login, library_world, run_sql):
    w = library_world
    run_sql("UPDATE enrolments SET joining_date = :d WHERE student_id = :s", d=h.days_ago(900), s=w.students.s1.student_id)
    created = client.post(f"{API}/access-extension-requests", headers=auth(login, w.students.s1), json={
        "enrolment_id": w.students.s1.enrolments[0]["enrolment_id"], "scope": "Both", "reason": "Interview preparation"}).get_json()["data"]
    rid = created["request_id"]
    assert created["needs_exception"] is True and "recommendation" not in created  # a student never sees staff notes
    # the Branch Manager is asked for a recommendation; nobody else is told yet
    asked = db.session.execute(select(Notification).where(Notification.recipient_user_id == w.people.ac.user_id, Notification.category == "Access")).scalar_one()
    assert "recommendation" in asked.title and asked.link == "/branch/support?tab=extensions"
    row = get(client, f"/access-extension-requests/{rid}", auth(login, w.people.ac))
    assert row["limit"] == "beyond" and row["can_recommend"] is True and row["can_decide"] is False and row["with_founder"] is False

    url = f"/access-extension-requests/{rid}/recommendation"
    assert client.post(f"{API}{url}", headers=auth(login, w.people.ac), json={"decision": "approve"}).status_code == 400  # a note is required
    assert client.post(f"{API}{url}", headers=auth(login, w.people.ac_vij), json={"decision": "approve", "note": "x"}).status_code == 404
    assert client.post(f"{API}{url}", headers=auth(login, w.people.founder), json={"decision": "approve", "note": "x"}).status_code == 403
    assert client.post(f"{API}{url}", headers=auth(login, w.students.s1), json={"decision": "approve", "note": "x"}).status_code == 403
    assert client.post(f"{API}{url}", headers=auth(login, w.people.ac),
                       json={"decision": "approve", "note": "Placed late", "expiry": h.days_ago(1)}).status_code == 400  # a future date
    future = date.today().replace(year=date.today().year + 1).isoformat()
    saved = post(client, url, auth(login, w.people.ac), json={"decision": "approve", "note": "Placed late", "expiry": future})
    assert saved["with_founder"] is True and saved["recommendation"]["decision"] == "approve" and saved["recommendation"]["expiry"] == future
    assert saved["recommendation"]["by"]["full_name"] == "AC Guntur"
    told = db.session.execute(select(Notification).where(Notification.recipient_user_id == w.people.founder.user_id, Notification.category == "Access")).scalar_one()
    assert "waiting for your decision" in told.title and "Placed late" in told.body
    assert db.session.execute(select(AuditLog).where(AuditLog.action == "ACCESS_EXTENSION_RECOMMENDED")).scalar_one().reason == "Placed late"

    # the Founder sees the recommendation, the nav count counts it, and the Branch Manager still cannot decide
    seen = get(client, f"/access-extension-requests/{rid}", auth(login, w.people.founder))
    assert seen["recommendation"]["note"] == "Placed late" and seen["can_decide"] is True
    assert get(client, "/me/nav-counts?workspace=founder", auth(login, w.people.founder))["access"] == 1
    assert client.post(f"{API}/access-extension-requests/{rid}/decision", headers=auth(login, w.people.ac), json={"decision": "approve"}).status_code == 403
    granted = post(client, f"/access-extension-requests/{rid}/decision", auth(login, w.people.founder), json={"decision": "approve", "new_expiry": future})
    assert granted["status"] == "Approved" and client.post(f"{API}{url}", headers=auth(login, w.people.ac),
                                                          json={"decision": "reject", "note": "late"}).status_code == 422


def test_within_the_limit_the_branch_manager_sees_the_new_end_date(client, login, library_world, run_sql):
    w = library_world
    created = client.post(f"{API}/access-extension-requests", headers=auth(login, w.students.s1), json={
        "enrolment_id": w.students.s1.enrolments[0]["enrolment_id"], "scope": "Both", "reason": "Revision"}).get_json()["data"]
    row = get(client, f"/access-extension-requests/{created['request_id']}", auth(login, w.people.ac))
    assert row["limit"] == "within" and row["current_end_date"] == "2027-03-02" and row["new_end_date"] == "2028-03-02"
    assert row["can_decide"] is True and row["can_recommend"] is False
    assert client.post(f"{API}/access-extension-requests/{created['request_id']}/recommendation", headers=auth(login, w.people.ac),
                       json={"decision": "approve", "note": "ok"}).status_code == 422  # within the limit: decide yourself
    decided = post(client, f"/access-extension-requests/{created['request_id']}/decision", auth(login, w.people.ac), json={"decision": "approve"})
    assert decided["new_end_date"] == "2028-03-02" and decided["status"] == "Approved"


# ---------------------------------------------------------------- Recordings

def test_hold_partial_and_unavailable_are_problem_reasons(client, login, library_world):
    w = library_world
    created = client.post(f"{API}/recordings", json={"session_id": w.delivered.session_id, "media_ref": "drive-file-1"}, headers=auth(login, w.people.ac)).get_json()["data"]
    rid = created["recording_id"]
    assert created["problem"] == {"reason": "processing", "label": "Still being prepared", "note": None}
    url = f"{API}/recordings/{rid}/problem"
    assert client.post(url, json={"reason": "on_hold"}, headers=auth(login, w.people.ac)).status_code == 400  # say what happened
    assert client.post(url, json={"reason": "broken", "note": "x"}, headers=auth(login, w.people.ac)).status_code == 400
    assert client.post(url, json={"reason": "on_hold", "note": "x"}, headers=auth(login, w.people.t1)).status_code == 403
    for reason, status, note in (("on_hold", "Held", "Sensitive content"), ("partial", "Partial", "Last half hour missing"),
                                 ("unavailable", "Unavailable", "Nothing was captured")):
        body = client.post(url, json={"reason": reason, "note": note}, headers=auth(login, w.people.ac)).get_json()["data"]
        assert body["status"] == status and body["problem"]["reason"] == reason
    released = post(client, f"/recordings/{rid}/release", auth(login, w.people.ac))
    assert released["status"] == "Released" and released["problem"] is None
    back = client.post(url, json={"reason": "processing"}, headers=auth(login, w.people.ac)).get_json()["data"]
    assert back["status"] == "Processing" and back["problem"]["reason"] == "processing"
    assert client.post(url, json={"reason": "processing"}, headers=auth(login, w.people.ac)).status_code == 422  # already so


def test_the_class_picker_lists_classes_of_a_day_with_their_recordings(client, login, library_world):
    w = library_world
    day = w.delivered.starts_at.astimezone(helpers_ist()).date().isoformat()
    rows = get(client, f"/recordings/classes?date={day}&batch_id={w.g1.batch_id}", auth(login, w.people.ac))
    assert [r["session_id"] for r in rows] == [w.delivered.session_id] and rows[0]["recordings"] == []
    assert get(client, f"/recordings/classes?date={day}", auth(login, w.people.ac_vij)) == []  # another branch sees nothing
    assert client.get(f"{API}/recordings/classes", headers=auth(login, w.people.t1)).status_code == 403


def helpers_ist():
    from config.timezone import IST
    return IST


# ---------------------------------------------------------------- Content & questions

def test_opening_a_submission_claims_it_and_the_tabs_have_counts(client, login, library_world):
    w = library_world
    item = h.create_item(client, auth(login, w.people.t1), w)
    client.post(f"{API}/content-items/{item['content_item_id']}/submit", headers=auth(login, w.people.t1))
    counts = get(client, "/content-items/review-summary", auth(login, w.people.ac))
    assert counts["awaiting"] == 1 and counts["ready"] == 0 and counts["questions"] == 0
    claimed = post(client, f"/content-items/{item['content_item_id']}/claim", auth(login, w.people.ac))
    assert claimed["claimed_by_me"] is True and claimed["can_decide"] is True
    listed = get(client, "/content-items?status=Under Review", auth(login, w.people.ac))
    assert listed[0]["status"] == "Under Review" and listed[0]["claimed_by"]["full_name"] == "AC Guntur"
    again = post(client, f"/content-items/{item['content_item_id']}/claim", auth(login, w.people.ac))
    assert again["claimed_by_me"] is True
    other = post(client, f"/content-items/{item['content_item_id']}/claim", auth(login, w.people.bm))
    assert other["claimed_by"]["full_name"] == "AC Guntur" and other["claimed_by_me"] is False and "is reviewing" in other["reason"]
    assert client.get(f"{API}/content-items/review-summary", headers=auth(login, w.people.t1)).status_code == 403
    assert client.post(f"{API}/content-items/{item['content_item_id']}/claim", headers=auth(login, w.people.t1)).status_code == 403


# ---------------------------------------------------------------- Student support

def test_support_views_open_on_needs_action_by_nearest_deadline_with_reply_marks(client, service_world, run_sql):  # noqa: F811
    w = service_world
    first = client.post("/api/v1/support-requests", headers=w.h(w.students.s1), json={"category": "Recording access", "details": "Cannot watch"}).get_json()["data"]
    second = client.post("/api/v1/support-requests", headers=w.h(w.students.s1), json={"category": "Other", "details": "Question about fees"}).get_json()["data"]
    third = client.post("/api/v1/support-requests", headers=w.h(w.students.s1), json={"category": "Other", "details": "Another thing"}).get_json()["data"]
    run_sql("UPDATE support_requests SET sla_due_at = now() + interval '5 hours' WHERE support_request_id = :i", i=first["support_request_id"])
    run_sql("UPDATE support_requests SET sla_due_at = now() + interval '1 hour' WHERE support_request_id = :i", i=second["support_request_id"])
    run_sql("UPDATE support_requests SET sla_due_at = now() + interval '3 hours' WHERE support_request_id = :i", i=third["support_request_id"])
    bm = w.h(w.people.bm)
    listed = client.get("/api/v1/support-requests?view=needs_action", headers=bm).get_json()
    assert [r["support_request_id"] for r in listed["data"]] == [second["support_request_id"], third["support_request_id"], first["support_request_id"]]
    assert {r["reply_mark"] for r in listed["data"]} == {"new_request"}
    assert client.get("/api/v1/support-requests/counts", headers=bm).get_json()["data"] == {"needs_action": 3, "waiting": 0, "done": 0, "all": 3}

    # staff answer one, the student answers back: that one is marked as a new reply
    owner = w.h(w.people.bm)
    client.post(f"/api/v1/support-requests/{first['support_request_id']}/messages", headers=owner, json={"body": "Try again now"})
    marks = {r["support_request_id"]: r["reply_mark"] for r in client.get("/api/v1/support-requests?view=needs_action", headers=bm).get_json()["data"]}
    assert marks[first["support_request_id"]] is None
    client.post(f"/api/v1/support-requests/{first['support_request_id']}/messages", headers=w.h(w.students.s1), json={"body": "Still stuck"})
    marks = {r["support_request_id"]: r["reply_mark"] for r in client.get("/api/v1/support-requests?view=needs_action", headers=bm).get_json()["data"]}
    assert marks[first["support_request_id"]] == "new_reply" and marks[second["support_request_id"]] == "new_request"
    # the badge counts what is near its deadline (within 4 h: the 1 h and 3 h ones) and the new reply
    assert client.get("/api/v1/me/nav-counts?workspace=branch", headers=bm).get_json()["data"]["support"] == 3
    assert client.get("/api/v1/support-requests/counts", headers=w.h(w.students.s1)).status_code == 403
    waiting = client.post(f"/api/v1/support-requests/{third['support_request_id']}/status", headers=bm, json={"status": "Waiting on Student"})
    assert waiting.status_code == 200
    assert client.get("/api/v1/support-requests/counts", headers=bm).get_json()["data"]["waiting"] == 1


# ---------------------------------------------------------------- Attendance & progress

def test_attendance_summary_and_risk_first_order(world, client, login):
    people, _, _ = world
    summary = data(call(client, login, people["ac"], "get", "/branch/attendance-summary"), 200)
    assert set(summary) == {"students_at_risk", "recoveries", "corrections"} and summary["recoveries"] == 0
    assert call(client, login, people["g1"], "get", "/branch/attendance-summary").status_code == 403
    assert call(client, login, people["ac"], "get", "/progress/students?sort=risk").status_code == 200
    assert call(client, login, people["ac"], "get", "/progress/students?sort=zzz").status_code == 400


# ---------------------------------------------------------------- Reports

def test_reports_default_to_this_month_with_drill_downs_and_trends(world, client, login):
    people, _, _ = world
    report = data(call(client, login, people["ac"], "get", "/branch/reports"), 200)
    today = datetime.now(timezone.utc).astimezone(helpers_ist()).date()
    assert report["period"]["key"] == "this_month" and report["period"]["from"] == today.replace(day=1).isoformat() and report["period"]["to"] == today.isoformat()
    figures = {f["key"]: f for f in report["figures"]}
    assert {"classes_held", "attendance_rate", "at_risk", "certificates", "support_overdue", "issues"} <= set(figures)
    assert all(f["drill"]["to"].startswith("/branch/") for f in report["figures"])
    assert figures["attendance_rate"]["value"] is None and figures["attendance_rate"]["hint"]  # nothing marked: not zero
    assert figures["certificates"]["drill"] == {"to": "/branch/completion", "search": {"stage": "issued"}}
    assert len(report["trends"]) == 6 and report["trends"][-1]["month"] == today.strftime("%Y-%m")
    last = data(call(client, login, people["ac"], "get", "/branch/reports?period=last_month"), 200)
    assert last["period"]["to"] == (today.replace(day=1) - timedelta(days=1)).isoformat()
    assert call(client, login, people["ac"], "get", "/branch/reports?period=custom").status_code == 400
    assert call(client, login, people["ac"], "get", "/branch/reports?period=custom&from=2026-05-02&to=2026-05-01").status_code == 400
    assert call(client, login, people["ac"], "get", "/branch/reports?branch_id=2").status_code == 404
    assert call(client, login, people["g1"], "get", "/branch/reports").status_code == 403


def test_reports_for_super_admin_and_founder_cover_all_or_one_branch(client, login, catalog, make_user):
    bm = make_user(roles=[("BRANCH_MANAGER", 1)])
    sa = make_user(roles=[("SUPER_ADMIN", None)])
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    trainer = make_user(roles=[("TRAINER", 1)])
    for who, prefix in ((sa, "/admin"), (founder, "/founder")):
        everything = client.get(f"{API}/branch/reports", headers=login(who.email))
        assert everything.status_code == 200, prefix  # no 403 for the Founder
        one = client.get(f"{API}/branch/reports?branch_id=1", headers=login(who.email))
        assert one.status_code == 200 and one.get_json()["data"]["scope"] == {"branch_id": 1}
        assert client.get(f"{API}/branch/reports?branch_id=999", headers=login(who.email)).status_code in (200, 404)
        # never a link into /branch/*; a figure with no screen under their own workspace has no link at all
        report = everything.get_json()["data"]
        drills = [f["drill"] for f in report["figures"]]
        assert not any(d and d["to"].startswith("/branch") for d in drills)
        by_key = {f["key"]: f["drill"] for f in report["figures"]}
        assert by_key["attendance_rate"]["to"] == f"{prefix}/attendance" and by_key["issues"]["to"] == f"{prefix}/issues"
        assert by_key["support_opened"]["to"] == f"{prefix}/support" and by_key["certificates"] is None
        assert client.get(f"{API}/branch/reports/export?section=figures", headers=login(who.email)).status_code == 200
    assert client.get(f"{API}/branch/reports", headers=login(bm.email)).status_code == 200
    assert client.get(f"{API}/branch/reports", headers=login(trainer.email)).status_code == 403


def test_report_export_is_csv_and_never_a_formula(world, client, login):
    people, _, _ = world
    response = call(client, login, people["ac"], "get", "/branch/reports/export?section=figures")
    assert response.status_code == 200 and response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"].startswith('attachment; filename="report-figures-')
    body = response.data.decode("utf-8-sig").splitlines()
    assert body[0] == "Figure,Value,Unit,Period" and any(line.startswith("Classes held,") for line in body)
    assert call(client, login, people["ac"], "get", "/branch/reports/export?section=batches").status_code == 200
    assert call(client, login, people["ac"], "get", "/branch/reports/export?section=trends").status_code == 200
    assert call(client, login, people["ac"], "get", "/branch/reports/export?section=certificates").status_code == 200
    assert call(client, login, people["ac"], "get", "/branch/reports/export?format=xlsx").status_code == 400
    assert call(client, login, people["ac"], "get", "/branch/reports/export?section=zzz").status_code == 400
    assert exports.safe_cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")" and exports.safe_cell("-5") == "-5" and exports.safe_cell("@cmd") == "'@cmd"
    assert exports.safe_cell(None) == "" and exports.safe_cell(date(2026, 1, 2)) == "2026-01-02"
    assert exports.to_csv(["a"], [["+1+2"]]).startswith(b"\xef\xbb\xbf")


# ---------------------------------------------------------------- the buttons follow the independence rule

def test_a_branch_managers_own_reschedule_request_is_decided_by_an_admin(world, client, login, make_session, run_sql):
    """After the role split a Branch Manager no longer raises reschedule requests (only a trainer does), but requests raised earlier by a
    person who then held both roles still wait: nobody at the branch may decide them, the Super Admin and Founder do. Every other
    request stays with the branch's Branch Manager, and the Super Admin and Founder only read it."""
    from tests.test_delivery import future, iso
    people, batch, _ = world
    own = make_session(batch, people["g1"], future(3, 10))
    other = make_session(batch, people["g1"], future(5, 10))
    asked = data(call(client, login, people["g1"], "post", f"/class-sessions/{own.session_id}/reschedule-requests", json={
        "proposed_starts_at": iso(future(4, 10)), "proposed_ends_at": iso(future(4, 12)), "reason": "Away that day"}), 201)
    plain = data(call(client, login, people["g1"], "post", f"/class-sessions/{other.session_id}/reschedule-requests", json={
        "proposed_starts_at": iso(future(6, 10)), "proposed_ends_at": iso(future(6, 12)), "reason": "Clinic visit"}), 201)
    run_sql("UPDATE session_change_requests SET requested_by = :bm WHERE request_id = :r", bm=people["ac"].user_id, r=asked["request_id"])
    assert call(client, login, people["ac"], "post", f"/class-sessions/{own.session_id}/reschedule-requests", json={}).status_code == 403  # no longer raises them

    def decide_flags(who):
        rows = data(call(client, login, who, "get", "/reschedule-requests?status=Open"), 200)
        return {r["request_id"]: r["can_decide"] for r in rows}

    assert decide_flags(people["ac"]) == {asked["request_id"]: False, plain["request_id"]: True}
    assert decide_flags(people["ac2"]) == {asked["request_id"]: False, plain["request_id"]: True}  # not another Branch Manager's either
    assert decide_flags(people["admin"]) == {asked["request_id"]: True, plain["request_id"]: False}
    assert decide_flags(people["founder"]) == {asked["request_id"]: True, plain["request_id"]: False}
    reject = lambda who, request: call(client, login, people[who], "post", f"/reschedule-requests/{request['request_id']}/reject", json={"note": "No"})  # noqa: E731
    assert reject("ac", asked).status_code == 422 and reject("ac2", asked).status_code == 422
    assert reject("admin", plain).status_code == 403 and reject("founder", plain).status_code == 403
    assert reject("ac", plain).status_code == 200
    assert reject("admin", asked).status_code == 200

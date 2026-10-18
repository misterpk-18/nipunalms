"""UX phase U17: the Super Admin's workspace. Needs action and the Setup checklist, Setup & health (plain states and a staff owner),
AI controls (both the Super Admin and the Founder can switch off and restore company-wide), CRM sync Needs attention with a plain
cause, Users & access (locked filter, staff options), Student accounts (suggested next step and the attention filter), Calendar
edit and cancel with their impact, the Audit log in plain sentences (presets, actors, CSV), and Issues assignment."""
from datetime import timedelta

from sqlalchemy import select, text

from config.database import db
from config.timezone import IST, today_ist
from models import AuditLog, CalendarClosure, Notification
from types import SimpleNamespace

from services import audit_sentences, crm_causes, student_next_step
from tests.services_fixtures import world  # noqa: F401
from tests.test_exception_queue import world as issue_world  # noqa: F401

API = "/api/v1"


def get(client, headers, path, expect=200):
    response = client.get(f"{API}{path}", headers=headers)
    assert response.status_code == expect, response.get_json()
    return response.get_json()["data"] if expect == 200 else response.get_json()


def send(client, method, headers, path, body=None, expect=200):
    response = getattr(client, method)(f"{API}{path}", headers=headers, json=body or {})
    assert response.status_code == expect, response.get_json()
    return response.get_json().get("data")


# ---------------------------------------------------------------- Setup & health

def test_setup_lists_both_registers_with_plain_states(client, make_user, login):
    admin = make_user()
    checklist = get(client, login(admin.email), "/admin/setup")
    kinds = {i["kind"] for i in checklist["items"]}
    assert kinds == {"integration", "security"}
    assert {i["state"] for i in checklist["items"]} <= {"Not set up", "Set up", "Working", "Broken"}
    by_code = {i["code"]: i for i in checklist["items"]}
    assert by_code["GOOGLE_MEET"]["state"] == "Not set up"
    assert by_code["CRM"]["state"] == "Set up"                    # Configured, waiting for a check
    assert by_code["EMAIL"]["state"] == "Not set up"              # Configuration Pending still counts as not set up
    assert checklist["summary"]["done"] is False and checklist["summary"]["total"] == len(checklist["items"])
    assert sum(checklist["summary"]["counts"].values()) == checklist["summary"]["total"]


def test_a_plain_state_update_sets_the_statuses_and_needs_evidence_to_be_working(client, make_user, login):
    admin = make_user(full_name="Setup Owner")
    headers = login(admin.email)
    items = {i["code"]: i for i in get(client, headers, "/admin/setup")["items"]}
    meet = items["GOOGLE_MEET"]

    send(client, "patch", headers, f"/integrations/{meet['id']}", {"state": "Working"}, expect=422)          # no evidence yet (a business rule)
    updated = send(client, "patch", headers, f"/integrations/{meet['id']}",
                   {"state": "Working", "evidence": "Test meeting created on 11 Oct", "owner_user_id": admin.user_id})
    assert (updated["configuration_status"], updated["verification_status"]) == ("Configured", "Verified")
    assert updated["owner"] == "Setup Owner" and updated["owner_user_id"] == admin.user_id

    again = {i["code"]: i for i in get(client, headers, "/admin/setup")["items"]}["GOOGLE_MEET"]
    assert again["state"] == "Working" and again["owner"] == {"user_id": admin.user_id, "full_name": "Setup Owner", "label": "Setup Owner"}

    broken = send(client, "patch", headers, f"/integrations/{meet['id']}", {"state": "Broken", "notes": "Meet link creation returns an error"})
    assert broken["verification_status"] == "Failed" and broken["verified_at"] is None
    assert {i["code"]: i for i in get(client, headers, "/admin/setup")["items"]}["GOOGLE_MEET"]["state"] == "Broken"
    back = send(client, "patch", headers, f"/integrations/{meet['id']}", {"state": "Not set up"})
    assert (back["configuration_status"], back["verification_status"]) == ("Not Configured", "Not Verified")

    send(client, "patch", headers, f"/integrations/{meet['id']}", {"state": "Set up", "verification_status": "Verified"}, expect=400)  # not both
    audited = db.session.execute(select(AuditLog).where(AuditLog.action == "INTEGRATION_UPDATED", AuditLog.entity_id == "GOOGLE_MEET")
                                 .order_by(AuditLog.audit_id)).scalars().all()
    assert audited and "owner_user_id" in audited[0].new_values


def test_the_owner_must_be_active_staff_and_a_security_row_takes_one_too(client, make_user, login, make_student):
    admin = make_user()
    gone = make_user(is_active=False)
    student = make_student()
    headers = login(admin.email)
    control = next(i for i in get(client, headers, "/admin/setup")["items"] if i["kind"] == "security")
    for who in (gone.user_id, student.student_id + 100000):
        send(client, "patch", headers, f"/security-controls/{control['id']}", {"owner_user_id": who}, expect=400)
    picked = send(client, "patch", headers, f"/security-controls/{control['id']}", {"owner_user_id": admin.user_id})
    assert picked["owner_user_id"] == admin.user_id
    cleared = send(client, "patch", headers, f"/security-controls/{control['id']}", {"owner_user_id": None})
    assert cleared["owner_user_id"] is None and cleared["owner"] == "Unassigned"


def test_the_checklist_is_done_when_every_row_is_working_and_broken_rows_count_for_the_badge(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    assert get(client, headers, "/me/nav-counts?workspace=admin")["setup"] == 0
    for table in ("integrations", "security_controls"):
        db.session.execute(text(f"UPDATE {table} SET configuration_status = 'Configured', verification_status = 'Verified', evidence = 'checked', "
                                f"verified_by = :u, verified_at = now()"), {"u": admin.user_id})
    db.session.commit()
    home = get(client, headers, "/admin/needs-action")
    assert home["setup"]["done"] is True and home["setup"]["items"] == []
    db.session.execute(text("UPDATE integrations SET verification_status = 'Failed', verified_by = NULL, verified_at = NULL WHERE integration_code = 'EMAIL'"))
    db.session.commit()
    home = get(client, headers, "/admin/needs-action")
    assert home["setup"]["done"] is False and [i["name"] for i in home["setup"]["items"]] == ["Email"]
    assert get(client, headers, "/me/nav-counts?workspace=admin")["setup"] == 1
    assert any(r["kind"] == "setup" and r["count"] == 1 for r in home["rows"])


def test_only_the_super_admin_and_founder_read_the_overview(client, make_user, login):
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    for path in ("/admin/setup", "/admin/needs-action", "/admin/staff-options"):
        get(client, login(manager.email), path, expect=403)
        get(client, login(founder.email), path)


def test_staff_options_lists_active_staff_only_with_their_roles(client, make_user, login):
    admin = make_user(full_name="Aaa Admin")
    make_user(roles=[("TRAINER", 1)], full_name="Zed Trainer")
    make_user(roles=[("TRAINER", 1)], full_name="Gone Trainer", is_active=False)
    options = get(client, login(admin.email), "/admin/staff-options")
    names = [o["full_name"] for o in options]
    assert "Zed Trainer" in names and "Gone Trainer" not in names and names == sorted(names)
    assert next(o for o in options if o["full_name"] == "Zed Trainer")["roles"] == ["Trainer"]


# ---------------------------------------------------------------- AI controls

def test_ai_status_is_on_or_off_per_audience_and_both_roles_can_switch_company_wide(client, make_user, login):
    admin, founder = make_user(), make_user(roles=[("FOUNDER_CEO", None)])
    for who in (admin, founder):
        headers = login(who.email)
        status = get(client, headers, "/ai-controls/status")
        assert [(a["audience"], a["state"]) for a in status["audiences"]] == [("Student", "On"), ("Staff", "On")] and status["all"]["state"] == "On"
        off = send(client, "post", headers, "/ai-controls", {"audience": "Student", "reason": "Wrong fee answers"}, expect=201)
        status = get(client, headers, "/ai-controls/status")
        student = next(a for a in status["audiences"] if a["audience"] == "Student")
        assert student["state"] == "Off" and student["control"]["disabled_by_name"] and not student["via_all"]
        assert next(a for a in status["audiences"] if a["audience"] == "Staff")["state"] == "On"
        every = send(client, "post", headers, "/ai-controls", {"audience": "All", "reason": "Provider incident"}, expect=201)
        status = get(client, headers, "/ai-controls/status")
        assert status["all"]["state"] == "Off" and all(a["state"] == "Off" for a in status["audiences"])
        assert next(a for a in status["audiences"] if a["audience"] == "Staff")["via_all"] is True
        # either of the two restores what the other switched off
        other = login((founder if who is admin else admin).email)
        send(client, "post", other, f"/ai-controls/{every['control_id']}/restore", {"restoration_note": "Incident over"})
        send(client, "post", other, f"/ai-controls/{off['control_id']}/restore", {"restoration_note": "Fixed"})
        assert all(a["state"] == "On" for a in get(client, headers, "/ai-controls/status")["audiences"])


def test_branch_switches_are_listed_apart_and_others_are_refused(client, make_user, login):
    admin, manager = make_user(), make_user(roles=[("BRANCH_MANAGER", 1)])
    send(client, "post", login(admin.email), "/ai-controls", {"audience": "Staff", "branch_id": 1, "reason": "Testing"}, expect=201)
    status = get(client, login(admin.email), "/ai-controls/status")
    assert [b["branch_id"] for b in status["branches"]] == [1] and all(a["state"] == "On" for a in status["audiences"])
    get(client, login(manager.email), "/ai-controls/status", expect=403)
    send(client, "post", login(manager.email), "/ai-controls", {"audience": "Student", "reason": "x"}, expect=403)


# ---------------------------------------------------------------- CRM sync

def _failed_event(run_sql, event_id="evt-x", event_type="AdmissionQualified", error="Unknown course 'NIT-CRS-999': its CourseUpserted event has not been applied yet",
                  status="Failed"):
    run_sql("INSERT INTO crm_events (event_id, event_type, source_version, occurred_at, payload, status, error) "
            "VALUES (:i, :t, 1, now(), CAST(:p AS jsonb), CAST(:s AS crm_event_status), :e)",
            i=event_id, t=event_type, s=status, e=error, p='{"admission": {"admission_code": "NIT-GNT-1", "course_code": "NIT-CRS-999"}}')


def test_needs_attention_lists_failed_first_with_a_plain_cause_and_a_summary(client, make_user, login, run_sql):
    admin = make_user()
    headers = login(admin.email)
    _failed_event(run_sql, "evt-ok", status="Applied", error=None)
    _failed_event(run_sql, "evt-received", status="Received", error=None)
    _failed_event(run_sql, "evt-bad")
    _failed_event(run_sql, "evt-weird", error="boom")
    rows = get(client, headers, "/admin/crm-sync/events?attention=true")
    assert [r["event_id"] for r in rows] == ["evt-weird", "evt-bad", "evt-received"]        # failed first (newest first), then unfinished
    bad = next(r for r in rows if r["event_id"] == "evt-bad")
    assert "course NIT-CRS-999 has not reached the LMS yet" in bad["plain_cause"] and bad["error"].startswith("Unknown course")
    assert bad["summary"] == "A student's admission was confirmed (admission NIT-GNT-1, course NIT-CRS-999)" and bad["can_retry"] is True
    assert "pass them to the CRM team" in next(r for r in rows if r["event_id"] == "evt-weird")["plain_cause"]
    assert next(r for r in rows if r["event_id"] == "evt-received")["plain_cause"] is None
    one = get(client, headers, f"/admin/crm-sync/events/{bad['crm_event_id']}")
    assert one["payload"]["admission"]["admission_code"] == "NIT-GNT-1" and one["label"] == "A student's admission was confirmed"
    assert get(client, headers, "/admin/crm-sync/summary")["needs_attention"] == 3
    assert get(client, headers, "/me/nav-counts?workspace=admin")["crm_sync"] == 3


def test_an_old_event_type_cannot_be_retried():
    old = SimpleNamespace(event_type="AdmissionCurriculumMapped", status="Failed", payload={}, error="There is no curriculum CV 4.2 for NIT-CRS-007 in the LMS")
    described = crm_causes.describe(old)
    assert described["can_retry"] is False and "no longer uses" in described["plain_cause"] and described["label"] == "Admission curriculum mapped"


def test_the_home_lists_the_newest_failures_with_retry_and_counts_the_rest(client, make_user, login, run_sql):
    admin = make_user()
    headers = login(admin.email)
    for n in range(5):
        _failed_event(run_sql, f"evt-{n}")
    rows = get(client, headers, "/admin/needs-action")["rows"]
    events = [r for r in rows if r["kind"] == "crm_event"]
    assert len(events) == 3 and all(r["retry"] for r in events)                              # the three newest; each can be retried
    more = next(r for r in rows if r["kind"] == "crm_events")
    assert more["count"] == 2 and more["to"] == "/admin/crm-sync"


# ---------------------------------------------------------------- Users and access

def test_locked_accounts_can_be_filtered_and_show_until_when(client, make_user, login, run_sql):
    admin = make_user()
    locked = make_user(roles=[("TRAINER", 1)], full_name="Locked Trainer")
    make_user(roles=[("TRAINER", 1)], full_name="Fine Trainer")
    run_sql("UPDATE users SET locked_until = now() + interval '20 minutes', failed_login_attempts = 5 WHERE user_id = :u", u=locked.user_id)
    rows = get(client, login(admin.email), "/admin/users?locked=true")
    assert [u["full_name"] for u in rows] == ["Locked Trainer"] and rows[0]["is_locked"] and rows[0]["locked_until"]
    home = get(client, login(admin.email), "/admin/needs-action")["rows"]
    assert next(r for r in home if r["kind"] == "locked_users")["count"] == 1
    send(client, "post", login(admin.email), f"/admin/users/{locked.user_id}/unlock", {"reason": "Rang the helpdesk"})
    assert get(client, login(admin.email), "/admin/users?locked=true") == []


# ---------------------------------------------------------------- Student accounts

def test_the_suggested_step_follows_the_link_and_the_filter_agrees(client, make_user, login, make_student, run_sql):
    admin = make_user()
    headers = login(admin.email)
    active = make_student(name="Active Learner")
    fresh = make_student(activate=False, name="Fresh Learner")                       # CRM link, WhatsApp off: never carried
    expired = make_student(activate=False, name="Expired Learner")
    suspended = make_student(name="Suspended Learner")
    run_sql("UPDATE student_activations SET expires_at = now() - interval '1 hour' WHERE student_id = :s", s=expired.student_id)
    send(client, "post", headers, f"/admin/students/{suspended.student_id}/suspend", {"reason": "Paused"})

    rows = {r["full_name"]: r for r in get(client, headers, "/admin/students")}
    assert rows["Active Learner"]["suggested_step"]["code"] == "nothing" and rows["Active Learner"]["needs_attention"] is False
    assert rows["Fresh Learner"]["suggested_step"]["code"] == "link_not_delivered" and rows["Fresh Learner"]["suggested_step"]["action"] == "send_link"
    assert rows["Expired Learner"]["suggested_step"] == {
        "code": "link_expired", "label": "Link expired", "detail": "The last link ran out before the student used it.", "action": "send_link",
        "action_label": "Send new link", "attention": True}
    assert rows["Suspended Learner"]["suggested_step"]["action"] == "reactivate" and rows["Suspended Learner"]["needs_attention"] is False

    flagged = get(client, headers, "/admin/students?needs_attention=true")
    assert {r["full_name"] for r in flagged} == {"Fresh Learner", "Expired Learner"}
    assert get(client, headers, "/me/nav-counts?workspace=admin")["student_accounts"] == 2

    detail = get(client, headers, f"/admin/students/{expired.student_id}")
    assert detail["suggested_step"]["code"] == "link_expired" and detail["activation"]["status"] == "expired"

    # sending a new link by WhatsApp (queued) moves the student to "waiting"
    run_sql("UPDATE app_settings SET setting_value = 'true' WHERE setting_key = 'whatsapp_enabled'")
    issued = send(client, "post", headers, f"/students/{fresh.student_id}/activation", expect=201)
    after = get(client, headers, f"/admin/students/{fresh.student_id}")["suggested_step"]
    assert issued["whatsapp"]["state"] in ("Queued", "Skipped")
    assert after["code"] in ("waiting", "link_not_delivered")


def test_a_blocked_login_and_held_back_enrolments_need_attention(client, make_user, login, make_student, run_sql):
    admin = make_user()
    headers = login(admin.email)
    blocked = make_student(name="Blocked Learner")
    held = make_student(name="Held Learner")
    run_sql("UPDATE users SET is_active = FALSE WHERE student_id = :s", s=blocked.student_id)
    run_sql("UPDATE enrolments SET status = 'Provisioning Pending' WHERE student_id = :s", s=held.student_id)
    rows = {r["full_name"]: r for r in get(client, headers, "/admin/students")}
    assert rows["Blocked Learner"]["suggested_step"]["code"] == "login_blocked"
    assert rows["Held Learner"]["suggested_step"]["code"] == "provisioning" and rows["Held Learner"]["suggested_step"]["action"] == "issues"
    assert {r["full_name"] for r in get(client, headers, "/admin/students?needs_attention=true")} == {"Blocked Learner", "Held Learner"}
    # every row's flag equals the SQL filter (one rule set, two renderings)
    flagged = {r["student_id"] for r in get(client, headers, "/admin/students?needs_attention=true")}
    assert flagged == {r["student_id"] for r in rows.values() if r["needs_attention"]}
    assert student_next_step.PENDING == ("Account Created", "Activation Pending")


# ---------------------------------------------------------------- Calendar

def _holiday(client, headers, starts_on, ends_on=None, **extra):
    body = {"kind": "Company Holiday", "starts_on": starts_on.isoformat(), "ends_on": (ends_on or starts_on).isoformat(), "title": "Festival", **extra}
    return send(client, "post", headers, "/calendar/closures", body, expect=201)


def test_edit_shows_the_impact_first_then_saves_and_tells_the_branch_managers(client, world):
    admin = world.h(world.people.admin)
    upcoming = world.sessions.upcoming.starts_at.astimezone(IST).date()
    holiday = _holiday(client, admin, upcoming + timedelta(days=10))
    path = f"/calendar/closures/{holiday['closure_id']}"
    assert holiday["affected_sessions"] if "affected_sessions" in holiday else True

    preview = send(client, "patch", admin, path, {"starts_on": upcoming.isoformat(), "ends_on": upcoming.isoformat(), "dry_run": True})
    assert preview["saved"] is False and preview["affected_count"] == 1 and preview["newly_affected_count"] == 1 and preview["freed_count"] == 0
    assert preview["affected_sessions"][0]["session_code"] == world.sessions.upcoming.session_code
    stored = db.session.get(CalendarClosure, holiday["closure_id"])
    assert stored.starts_on == upcoming + timedelta(days=10)                                     # nothing saved by the preview

    saved = send(client, "patch", admin, path, {"starts_on": upcoming.isoformat(), "ends_on": upcoming.isoformat(), "title": "Festival of lights"})
    assert saved["saved"] is True and saved["affected_count"] == 1 and saved["title"] == "Festival of lights"
    db.session.expire_all()
    assert db.session.get(CalendarClosure, holiday["closure_id"]).starts_on == upcoming
    titles = list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == world.people.bm.user_id)).scalars())
    assert any("1 class(es) need a replacement" in t for t in titles)
    audited = db.session.execute(select(AuditLog).where(AuditLog.action == "CALENDAR_CLOSURE_UPDATED")).scalars().one()
    assert audited.new_values["title"] == "Festival of lights" and audited.old_values["title"] == "Festival"

    moved_off = send(client, "patch", admin, path, {"starts_on": (upcoming + timedelta(days=20)).isoformat(), "ends_on": (upcoming + timedelta(days=20)).isoformat(),
                                                    "dry_run": True})
    assert moved_off["affected_count"] == 0 and moved_off["freed_count"] == 1


def test_edit_checks_the_dates_and_who_may_change_what(client, world):
    admin, founder, bm = world.h(world.people.admin), world.h(world.people.founder), world.h(world.people.bm)
    start = today_ist() + timedelta(days=5)
    holiday = _holiday(client, admin, start, start + timedelta(days=1))
    path = f"/calendar/closures/{holiday['closure_id']}"
    send(client, "patch", admin, path, {"ends_on": (start - timedelta(days=1)).isoformat()}, expect=400)                 # To before From
    send(client, "patch", admin, path, {"ends_on": (start + timedelta(days=70)).isoformat()}, expect=400)                # too long
    send(client, "patch", admin, path, {}, expect=400)
    send(client, "patch", bm, path, {"title": "Mine now"}, expect=403)                                                     # a Branch Manager does not change company holidays
    assert send(client, "patch", founder, path, {"title": "Founder's edit"})["title"] == "Founder's edit"

    past = today_ist() - timedelta(days=3)
    old = _holiday(client, admin, past)
    send(client, "patch", admin, f"/calendar/closures/{old['closure_id']}", {"title": "Too late"}, expect=422)
    send(client, "post", admin, f"/calendar/closures/{old['closure_id']}/cancel", {"reason": "Too late"}, expect=422)

    branch = send(client, "post", bm, "/calendar/closures", {"kind": "Branch Closure", "branch_id": 1, "starts_on": start.isoformat(),
                                                             "ends_on": start.isoformat(), "title": "Branch day"}, expect=201)
    assert send(client, "patch", bm, f"/calendar/closures/{branch['closure_id']}", {"title": "Branch day (moved)"})["title"] == "Branch day (moved)"
    other = world.h(world.people.bm_vij)
    send(client, "patch", other, f"/calendar/closures/{branch['closure_id']}", {"title": "Not mine"}, expect=404)


def test_cancel_shows_the_classes_it_frees_then_cancels_and_working_days_return(client, world):
    from services import working_days

    admin = world.h(world.people.admin)
    upcoming = world.sessions.upcoming.starts_at.astimezone(IST).date()
    holiday = _holiday(client, admin, upcoming)
    path = f"/calendar/closures/{holiday['closure_id']}"
    assert not working_days.is_working_day(upcoming, 1)

    send(client, "post", admin, f"{path}/cancel", {}, expect=400)                                                          # a reason is required
    preview = send(client, "post", admin, f"{path}/cancel", {"reason": "Holiday moved", "dry_run": True})
    assert preview["saved"] is False and preview["affected_count"] == 1 and preview["status"] == "Approved"
    assert not working_days.is_working_day(upcoming, 1)

    done = send(client, "post", admin, f"{path}/cancel", {"reason": "Holiday moved"})
    assert done["status"] == "Cancelled" and done["cancel_reason"] == "Holiday moved" and done["saved"] is True and done["affected_count"] == 1
    assert working_days.is_working_day(upcoming, 1)                                                                          # classes run as scheduled again
    titles = list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == world.people.bm.user_id)).scalars())
    assert any("was cancelled: 1 class(es) run as scheduled" in t for t in titles)

    send(client, "post", admin, f"{path}/cancel", {"reason": "again"}, expect=422)
    send(client, "patch", admin, path, {"title": "Revived"}, expect=422)
    cancelled = [c["closure_id"] for c in get(client, admin, "/calendar/closures?status=Cancelled")]
    assert cancelled == [holiday["closure_id"]]
    assert get(client, admin, "/calendar/closures?status=Approved") == []


def test_a_pending_closure_can_be_cancelled_and_is_then_not_decided(client, world, run_sql):
    admin = world.h(world.people.admin)
    start = today_ist() + timedelta(days=3)
    run_sql("INSERT INTO calendar_closures (kind, branch_id, starts_on, ends_on, title, status, requested_by) "
            "SELECT 'Branch Closure', 1, :s, :s, 'Proposed', 'Pending', user_id FROM users LIMIT 1", s=start)
    closure_id = db.session.execute(text("SELECT closure_id FROM calendar_closures WHERE title = 'Proposed'")).scalar_one()
    assert get(client, admin, "/me/nav-counts?workspace=admin")["calendar"] == 1
    send(client, "post", admin, f"/calendar/closures/{closure_id}/cancel", {"reason": "Proposed by mistake"})
    send(client, "post", admin, f"/calendar/closures/{closure_id}/decision", {"decision": "Approved"}, expect=422)
    assert get(client, admin, "/me/nav-counts?workspace=admin")["calendar"] == 0


def test_the_list_puts_what_is_ahead_first_and_pages_properly(client, world):
    admin = world.h(world.people.admin)
    today = today_ist()
    for days, title in ((-30, "Long ago"), (20, "Later"), (5, "Soon"), (-2, "Just over")):
        _holiday(client, admin, today + timedelta(days=days), title=title)
    titles = [c["title"] for c in get(client, admin, "/calendar/closures?sort=upcoming")]
    assert titles == ["Soon", "Later", "Just over", "Long ago"]
    first = client.get(f"{API}/calendar/closures?sort=upcoming&per_page=3&page=1", headers=admin).get_json()
    second = client.get(f"{API}/calendar/closures?sort=upcoming&per_page=3&page=2", headers=admin).get_json()
    assert first["meta"]["total"] == 4 and first["meta"]["pages"] == 2
    assert [c["title"] for c in first["data"] + second["data"]] == titles
    send(client, "post", admin, "/calendar/closures", {"kind": "Company Holiday", "starts_on": today.isoformat(),
                                                       "ends_on": (today + timedelta(days=90)).isoformat(), "title": "Too long"}, expect=400)


# ---------------------------------------------------------------- Audit log

def test_the_audit_log_reads_as_sentences_with_links_and_a_fallback(client, make_user, login):
    admin = make_user(full_name="Asha Admin")
    staff = make_user(roles=[("BRANCH_MANAGER", 2)], full_name="Tara Trainer", email="tara@nipuna.test")
    headers = login(admin.email)
    send(client, "post", headers, f"/admin/users/{staff.user_id}/scopes", {"role_code": "BRANCH_MANAGER", "branch_id": 1}, expect=201)
    db.session.add(AuditLog(actor_user_id=admin.user_id, action="SOMETHING_NEW_HAPPENED", entity_type="widget", entity_id="9"))
    db.session.add(AuditLog(actor_user_id=None, action="PASSWORD_RESET_CODE_REQUESTED", entity_type="user", entity_id=str(staff.user_id)))
    db.session.commit()
    rows = get(client, headers, "/audit-log?per_page=50")
    by_action = {r["action"]: r for r in rows}
    granted = by_action["SCOPE_GRANTED"]
    assert granted["sentence"] == "Asha Admin gave Tara Trainer the role BRANCH_MANAGER" and granted["target"] == "Tara Trainer"
    assert granted["link"] == {"to": "/admin/users", "search": {"q": "tara@nipuna.test"}}
    assert by_action["SOMETHING_NEW_HAPPENED"]["sentence"] == "Something new happened by Asha Admin" and by_action["SOMETHING_NEW_HAPPENED"]["link"] is None
    assert by_action["PASSWORD_RESET_CODE_REQUESTED"]["sentence"] == "Tara Trainer asked for a password reset code"
    assert granted["old_values"] is None and "new_values" in granted                       # the raw snapshot still travels with the row


def test_every_action_in_the_code_has_a_sentence_or_reads_well_without_one():
    assert audit_sentences.humanise("USER_UNLOCKED") == "User unlocked"
    for action, template in audit_sentences.SENTENCES.items():
        assert template.strip() and template.count("{") == template.count("}"), action
    for preset, actions in audit_sentences.PRESETS.items():
        assert actions and set(actions) <= set(audit_sentences.SENTENCES), preset


def test_preset_filters_and_the_actor_list_cover_everyone(client, make_user, login):
    admin = make_user(full_name="Asha Admin")
    headers = login(admin.email)
    names = [f"Actor {n:02d}" for n in range(30)]                                                              # more than one page of staff
    actors = [make_user(roles=[("TRAINER", 1)], full_name=name) for name in names]
    for actor in actors:
        db.session.add(AuditLog(actor_user_id=actor.user_id, action="INTEGRATION_UPDATED", entity_type="integration", entity_id="CRM"))
    db.session.add(AuditLog(actor_user_id=admin.user_id, action="SCOPE_GRANTED", entity_type="user", entity_id=str(actors[0].user_id)))
    db.session.add(AuditLog(actor_user_id=admin.user_id, action="USER_UNLOCKED", entity_type="user", entity_id=str(actors[0].user_id)))
    db.session.add(AuditLog(actor_user_id=admin.user_id, action="BATCH_CREATED", entity_type="batch", entity_id="1"))
    db.session.commit()

    facets = get(client, headers, "/audit-log/facets")
    assert {a["full_name"] for a in facets["actors"]} >= set(names) | {"Asha Admin"}                 # not just page 1 of staff
    assert [p["key"] for p in facets["presets"]] == ["accounts", "roles", "integrations"]
    assert {r["action"] for r in get(client, headers, "/audit-log?preset=roles&per_page=100")} == {"SCOPE_GRANTED"}
    assert {r["action"] for r in get(client, headers, "/audit-log?preset=accounts&per_page=100")} >= {"USER_UNLOCKED"}
    integrations = client.get(f"{API}/audit-log?preset=integrations&per_page=100", headers=headers).get_json()
    assert integrations["meta"]["total"] >= 30 and {r["action"] for r in integrations["data"]} == {"INTEGRATION_UPDATED"}
    get(client, headers, "/audit-log?preset=nope", expect=400)
    today = today_ist().isoformat()
    assert get(client, headers, f"/audit-log?from={today}&to={today}&preset=roles")


def test_the_audit_log_exports_as_csv_with_plain_sentences_and_guarded_cells(client, make_user, login):
    admin = make_user(full_name="=Evil Admin")
    staff = make_user(roles=[("BRANCH_MANAGER", 2)], full_name="Tara Trainer")
    headers = login(admin.email)
    send(client, "post", headers, f"/admin/users/{staff.user_id}/scopes", {"role_code": "BRANCH_MANAGER", "branch_id": 1}, expect=201)
    response = client.get(f"{API}/audit-log/export?preset=roles", headers=headers)
    assert response.status_code == 200 and response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    body = response.data.decode("utf-8-sig")
    lines = body.strip().split("\r\n")
    assert lines[0] == "When (IST),What happened,Who,Action,Record type,Record,Reason"
    assert len(lines) == 2 and "gave Tara Trainer the role BRANCH_MANAGER" in lines[1] and ",'=Evil Admin," in lines[1]
    assert client.get(f"{API}/audit-log/export", headers={}).status_code == 401


def test_a_students_recent_history_reads_as_sentences(client, make_user, login, make_student):
    admin = make_user(full_name="Asha Admin")
    student = make_student(name="Maya Learner")
    headers = login(admin.email)
    send(client, "post", headers, f"/admin/students/{student.student_id}/suspend", {"reason": "Paused"})
    history = get(client, headers, f"/admin/students/{student.student_id}")["audit"]
    suspended = next(h for h in history if h["action"] == "STUDENT_SUSPENDED")
    assert suspended["sentence"].startswith("Asha Admin suspended the account of Maya Learner")
    assert suspended["link"]["to"] == "/admin/students/$id"


# ---------------------------------------------------------------- Issues: assign

def test_the_super_admin_assigns_an_issue_and_it_changes_owner_and_counts(client, login, issue_world):  # noqa: F811
    people = issue_world.people
    headers = login(people.sa.email)
    rows = get(client, headers, "/issues?per_page=50")
    allocation = next(r for r in rows if r["source"] == "ALLOCATION")
    assert allocation["can_assign"] is True and allocation["owner"] is None
    before = get(client, headers, "/me/nav-counts?workspace=admin")["issues"]

    assigned = send(client, "post", headers, f"/exceptions/ALLOCATION/{allocation['source_id']}/assign",
                    {"assignee_user_id": people.bm_g.user_id, "note": "Please allocate before Monday"})
    assert assigned["owner"]["user_id"] == people.bm_g.user_id and assigned["state"] == "Recovery In Progress" and assigned["step_count"] == 1
    assert get(client, headers, "/me/nav-counts?workspace=admin")["issues"] == before - 1
    steps = get(client, headers, f"/exceptions/ALLOCATION/{allocation['source_id']}/steps")
    assert steps[0]["reason"] == "Assigned to BM Guntur: Please allocate before Monday" and steps[0]["assigned_to"]["user_id"] == people.bm_g.user_id
    assert [r["owner"]["user_id"] for r in get(client, headers, f"/issues?owner={people.bm_g.user_id}")] == [people.bm_g.user_id]
    told = list(db.session.execute(select(Notification).where(Notification.recipient_user_id == people.bm_g.user_id)).scalars())
    assert any(n.title.startswith("An issue was assigned to you") and n.link == "/branch/issues" for n in told)
    audited = db.session.execute(select(AuditLog).where(AuditLog.action == "EXCEPTION_ASSIGNED")).scalars().one()
    assert audited.new_values["assigned_to"] == people.bm_g.user_id

    # a second hand-over replaces the owner
    again = send(client, "post", headers, f"/exceptions/ALLOCATION/{allocation['source_id']}/assign", {"assignee_user_id": people.ac_g.user_id})
    assert again["owner"]["user_id"] == people.ac_g.user_id and again["step_count"] == 2


def test_assigning_needs_a_super_admin_an_active_staff_member_and_an_issue_without_its_own_owner(client, login, make_user, issue_world):  # noqa: F811
    people = issue_world.people
    sa = login(people.sa.email)
    allocation = next(r for r in get(client, sa, "/issues?per_page=50") if r["source"] == "ALLOCATION")
    path = f"/exceptions/ALLOCATION/{allocation['source_id']}/assign"
    send(client, "post", login(people.ac_g.email), path, {"assignee_user_id": people.bm_g.user_id}, expect=403)
    send(client, "post", login(people.founder.email), path, {"assignee_user_id": people.bm_g.user_id}, expect=200)  # the Founder can do what the Super Admin can
    send(client, "post", sa, path, {"assignee_user_id": make_user(is_active=False).user_id}, expect=400)
    send(client, "post", sa, path, {}, expect=400)
    send(client, "post", sa, "/exceptions/ALLOCATION/999999/assign", {"assignee_user_id": people.bm_g.user_id}, expect=404)
    # the Branch Manager's own Issues list offers no Assign
    assert all(r["can_assign"] is False for r in get(client, login(people.ac_g.email), "/issues?per_page=50"))

    recording = next(r for r in get(client, sa, "/issues?per_page=50") if r["source"] == "RECORDING")
    send(client, "post", sa, f"/exceptions/RECORDING/{recording['source_id']}/assign", {"assignee_user_id": people.ac_g.user_id}, expect=200)  # no owner yet: allowed
    owned = next(r for r in get(client, sa, "/issues?per_page=50") if r["source"] == "RECORDING")
    assert owned["owner"]["user_id"] == people.ac_g.user_id


def test_issues_page_properly_beyond_one_hundred_rows(client, login, make_user, run_sql):
    admin = make_user()
    run_sql("INSERT INTO integrations (integration_code, integration_name, requirement, configuration_status, verification_status, owner) "
            "SELECT 'X' || g, 'Extra ' || g, 'x', 'Misconfigured', 'Failed', 'Super Admin' FROM generate_series(1, 120) g")
    page = client.get(f"{API}/issues?per_page=100&page=2", headers=login(admin.email)).get_json()
    assert page["meta"]["total"] >= 120 and page["meta"]["pages"] >= 2 and 0 < len(page["data"]) <= 100
    assert page["data"][0]["go_fix"]["to"] == "/admin/setup"

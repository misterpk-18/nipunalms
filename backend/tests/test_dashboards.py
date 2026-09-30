"""Staff dashboards: one summary per workspace, branch-locked, reading the slices' own records.
CRM-authoritative figures stay Not Configured and never become a number."""
import json

import pytest

from tests.library_helpers import API, auth
from tests.test_exception_queue import world  # noqa: F401  (the same two-branch world the queue tests use)


def summary(client, login, who, path, expect=200):
    response = client.get(f"{API}{path}", headers=auth(login, who))
    assert response.status_code == expect, response.get_json()
    return response.get_json().get("data")


def assert_not_configured(block):
    assert block["state"] == "Not Configured" and block["reason"]
    assert not {"count", "value", "amount", "percent", "total"} & block.keys()  # never a number, never 0


# ---------------------------------------------------------------- academic

def test_academic_dashboard_counts_the_coordinators_branch_only(client, login, world):
    data = summary(client, login, world.people.ac_g, "/academic/summary")
    assert [b["branch_id"] for b in data["scope"]["branches"]] == [1] and data["scope"]["all_branches"] is False
    assert data["allocation_queue"] == {"count": 2, "curriculum_mapping_pending": 1, "allocation_pending": 1}
    assert data["recording_exceptions"]["count"] == 1
    assert data["results_awaiting_publication"]["count"] == 0
    assert data["batches_ready"] == {"ready": 1, "total": 1}
    # mapping + allocation + recording exceptions: none has a named owner
    assert data["open_exceptions"] == {"count": 3, "awaiting_owner": 3}

    other = summary(client, login, world.people.ac_v, "/academic/summary")
    assert other["allocation_queue"]["count"] == 1 and other["recording_exceptions"]["count"] == 0
    assert other["open_exceptions"]["count"] == 1 and other["batches_ready"]["total"] == 0


def test_academic_dashboard_branch_lock_and_admin_view(client, login, world):
    assert client.get(f"{API}/academic/summary?branch_id=2", headers=auth(login, world.people.ac_g)).status_code == 404
    everything = summary(client, login, world.people.sa, "/academic/summary")
    assert everything["scope"]["all_branches"] is True and everything["allocation_queue"]["count"] == 3
    only_v = summary(client, login, world.people.sa, "/academic/summary?branch_id=2")
    assert only_v["allocation_queue"]["count"] == 1
    assert summary(client, login, world.people.founder, "/academic/summary")["allocation_queue"]["count"] == 3
    summary(client, login, world.people.trainer, "/academic/summary", expect=403)
    summary(client, login, world.g_mapping, "/academic/summary", expect=403)


def test_academic_dashboard_lists_batches_that_are_not_ready(client, login, world, run_sql):
    run_sql("UPDATE batches SET readiness = 'Blocked', readiness_reason = 'Curriculum Mapping Pending', recovery_owner = 'Academic Coordinator — Guntur'")
    data = summary(client, login, world.people.ac_g, "/academic/summary")
    assert data["batches_ready"] == {"ready": 0, "total": 1}
    assert data["batch_risks"][0]["reason"] == "Curriculum Mapping Pending" and data["batch_risks"][0]["recovery_owner"].startswith("Academic")


# ---------------------------------------------------------------- branch

def test_branch_dashboard_is_locked_to_the_managers_branch(client, login, world):
    data = summary(client, login, world.people.bm_g, "/branch/summary")
    assert [b["branch_id"] for b in data["scope"]["branches"]] == [1]
    assert data["batches_running"]["total_open"] == 1
    assert data["schedule_and_recording_exceptions"]["recording_exceptions"] == 1
    assert data["requests_open"] == {"count": 0, "escalations": 0, "extension_requests": 0}
    assert client.get(f"{API}/branch/summary?branch_id=2", headers=auth(login, world.people.bm_g)).status_code == 404
    # a coordinator has the academic dashboard, not the manager's
    summary(client, login, world.people.ac_g, "/branch/summary", expect=403)
    assert summary(client, login, world.people.founder, "/branch/summary?branch_id=2")["schedule_and_recording_exceptions"]["count"] == 0


def test_branch_dashboard_crm_figures_are_not_configured_never_zero(client, login, world):
    data = summary(client, login, world.people.bm_g, "/branch/summary")
    assert set(data["crm"]) == {"verified_collections", "new_paid_admissions", "overdue_followups"}
    for block in data["crm"].values():
        assert_not_configured(block)


def test_branch_dashboard_counts_escalations_and_extension_requests(client, login, world, run_sql):
    student = world.g_alloc
    run_sql("INSERT INTO access_extension_requests (enrolment_id, student_id, branch_id, scope, reason, original_expiry) "
            "VALUES (:e, :s, 1, 'Both', 'Interview prep', '2027-01-01')", e=student.enrolments[0]["enrolment_id"], s=student.student_id)
    data = summary(client, login, world.people.bm_g, "/branch/summary")
    assert data["requests_open"] == {"count": 1, "escalations": 0, "extension_requests": 1}
    assert summary(client, login, world.people.sa, "/branch/summary?branch_id=2")["requests_open"]["count"] == 0


# ---------------------------------------------------------------- admin

def test_admin_dashboard(client, login, world):
    data = summary(client, login, world.people.sa, "/admin/summary")
    assert_not_configured(data["crm"]["overdue_payment_verifications"])
    assert data["integration_failures"] == {"count": 1, "codes": ["EMAIL"], "source": data["integration_failures"]["source"]}
    assert data["integrations_verified"]["verified"] == 0 and data["integrations_verified"]["total"] >= 8
    assert data["open_exceptions"]["count"] == 6 and data["awaiting_owner"]["count"] == 6
    assert data["open_exceptions"]["by_source"]["CURRICULUM_MAPPING"]["count"] == 2
    assert data["sync"]["failed_events"] == 1 and data["sync"]["failed_event_items"][0]["source"] == "CRM_EVENT"
    flows = {f["flow"]: f for f in data["sync"]["flows"]}
    assert flows["LMS → CRM status outbox"]["state"] == "Integration Unavailable"
    assert flows["CRM → LMS events"]["detail"] == "1 failed event(s)" and flows["CRM → LMS events"]["state"] == "Pending Verification"
    assert data["ai"]["monthly_ceiling"] == {"state": "Configuration Pending"}
    assert data["ai"]["student_daily_limit"] == 50 and data["ai"]["staff_daily_limit"] == 100
    summary(client, login, world.people.bm_g, "/admin/summary", expect=403)
    summary(client, login, world.people.ac_g, "/admin/summary", expect=403)


def test_admin_dashboard_lists_provisioning_items(client, login, world, run_sql):
    run_sql("UPDATE enrolments SET status = 'Provisioning Pending' WHERE enrolment_code = :c", c=world.g_alloc.enrolments[0]["enrolment_code"])
    data = summary(client, login, world.people.sa, "/admin/summary")
    assert data["provisioning"]["count"] == 1 and data["provisioning"]["items"][0]["reference"] == world.g_alloc.enrolments[0]["enrolment_code"]


# ---------------------------------------------------------------- founder

def test_founder_dashboard(client, login, world, run_sql):
    run_sql("UPDATE enrolments SET status = 'Active', joining_date = '2026-09-01' WHERE enrolment_code = :c",
            c=world.g_alloc.enrolments[0]["enrolment_code"])
    data = summary(client, login, world.people.founder, "/founder/summary")
    assert set(data["crm"]) == {"verified_collections", "new_paid_admissions", "overdue_amount"}
    for block in data["crm"].values():
        assert_not_configured(block)
    assert data["active_enrolments"]["count"] == 1
    assert {(row["branch"]["branch_id"], row["count"]) for row in data["active_enrolments"]["by_branch"]} == {(1, 1), (2, 0)}
    assert data["batches_at_risk"]["count"] == 0
    assert data["certificates_awaiting_approval"]["count"] == 0
    assert data["decisions"]["ai_ceiling"] == {"state": "Configuration Pending"}
    assert data["decisions"]["access_exceptions"]["count"] == 0
    summary(client, login, world.people.bm_g, "/founder/summary", expect=403)
    summary(client, login, world.people.ac_g, "/founder/summary", expect=403)


def test_founder_decisions_show_a_configured_ceiling_and_waiting_exceptions(client, login, world, run_sql):
    student = world.g_alloc
    run_sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('ai_monthly_ceiling_inr', '25000')")
    run_sql("INSERT INTO access_extension_requests (enrolment_id, student_id, branch_id, scope, reason, needs_exception, original_expiry) "
            "VALUES (:e, :s, 1, 'Recording', 'Project revision', true, '2026-01-01')", e=student.enrolments[0]["enrolment_id"], s=student.student_id)
    decisions = summary(client, login, world.people.founder, "/founder/summary")["decisions"]
    assert decisions["ai_ceiling"] == {"state": "Configured", "amount_inr": 25000}
    waiting = decisions["access_exceptions"]
    assert waiting["count"] == 1 and waiting["state"] == "Awaiting Approval" and waiting["items"][0]["request_code"].startswith("EXT-")


def test_no_crm_block_carries_a_number_anywhere(client, login, world):
    # walk every summary: anything keyed under "crm" is a Not Configured block
    for who, path in ((world.people.bm_g, "/branch/summary"), (world.people.sa, "/admin/summary"), (world.people.founder, "/founder/summary")):
        text = json.dumps(summary(client, login, who, path)["crm"])
        assert "Not Configured" in text and ": 0" not in text

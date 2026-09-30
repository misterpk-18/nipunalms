"""Audit log viewer and CRM sync monitor."""
from sqlalchemy import select

from config.database import db
from models import AuditLog, CrmEvent
from tests import helpers


def _failed_event(crm_event):
    """An AdmissionQualified for a course the LMS does not know yet: stored as Failed, retryable once the course arrives."""
    data = helpers.admission_data(person_id="P-900", admission_id="A-900", course="NIT-CRS-999", email="late@example.test")
    response = crm_event("AdmissionQualified", data, event_id="evt-failed-1")
    assert response.status_code == 422
    return db.session.execute(select(CrmEvent).where(CrmEvent.event_id == "evt-failed-1")).scalar_one()


# ---------------------------------------------------------------- audit log

def test_audit_log_is_for_super_admin_and_founder(client, make_user, login):
    assert client.get("/api/v1/audit-log", headers=login(make_user().email)).status_code == 200
    assert client.get("/api/v1/audit-log", headers=login(make_user(roles=[("FOUNDER_CEO", None)]).email)).status_code == 200
    for role in (("BRANCH_MANAGER", 1), ("ACADEMIC_COORDINATOR", 1), ("TRAINER", 1)):
        assert client.get("/api/v1/audit-log", headers=login(make_user(roles=[role]).email)).status_code == 403
    assert client.get("/api/v1/audit-log").status_code == 401


def test_filter_by_actor_entity_action_and_date(client, make_user, login):
    admin = make_user(full_name="Ada Admin")
    other = make_user(full_name="Other Admin")
    login(other.email)
    headers = login(admin.email)
    target = client.post("/api/v1/admin/users", headers=headers,
                         json={"full_name": "New Staff", "email": "new.staff@nipuna.test", "scopes": [{"role_code": "TRAINER", "branch_id": 1}]}).get_json()["data"]
    client.post(f"/api/v1/admin/users/{target['user_id']}/deactivate", headers=headers, json={"reason": "Test"})

    everything = client.get("/api/v1/audit-log", headers=headers).get_json()
    actions = [e["action"] for e in everything["data"]]
    assert actions[:2] == ["USER_DEACTIVATED", "USER_CREATED"] and "LOGIN" in actions  # newest first
    assert everything["data"][0]["actor"] == {"user_id": admin.user_id, "full_name": "Ada Admin", "email": admin.email}
    assert everything["data"][0]["reason"] == "Test"

    def ids(query):
        return [e["action"] for e in client.get(f"/api/v1/audit-log?{query}", headers=headers).get_json()["data"]]

    assert ids("action=USER_CREATED") == ["USER_CREATED"]
    assert ids(f"entity_type=user&entity_id={target['user_id']}") == ["USER_DEACTIVATED", "USER_CREATED"]
    assert set(ids(f"actor_user_id={other.user_id}")) == {"LOGIN"}
    assert ids("from=2999-01-01") == [] and ids("to=2000-01-01") == []
    assert len(ids("from=2000-01-01&to=2999-01-01")) == len(actions)
    assert client.get("/api/v1/audit-log?from=yesterday", headers=headers).status_code == 400


def test_pagination_and_facets(client, make_user, login):
    admin = make_user()
    headers = login(admin.email)
    for _ in range(3):
        login(admin.email)

    page = client.get("/api/v1/audit-log?per_page=2&page=2", headers=headers).get_json()
    assert len(page["data"]) == 2 and page["meta"]["total"] == 4 and page["meta"]["pages"] == 2
    facets = client.get("/api/v1/audit-log/facets", headers=headers).get_json()["data"]
    assert facets["actions"] == ["LOGIN"] and facets["entity_types"] == ["user"]
    assert db.session.execute(select(AuditLog.action)).scalars().first() == "LOGIN"


# ---------------------------------------------------------------- CRM sync

def test_crm_sync_monitor_is_for_super_admin_and_founder_and_retry_only_for_super_admin(client, make_user, login, catalog, crm_event):
    event = _failed_event(crm_event)
    founder = make_user(roles=[("FOUNDER_CEO", None)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    retry = f"/api/v1/admin/crm-sync/events/{event.crm_event_id}/retry"

    assert client.get("/api/v1/admin/crm-sync/events", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/admin/crm-sync/outbox", headers=login(founder.email)).status_code == 200
    assert client.get("/api/v1/admin/crm-sync/summary", headers=login(manager.email)).status_code == 403
    assert client.post(retry, headers=login(founder.email)).status_code == 403


def test_summary_counts_events_and_outbox(client, make_user, login, make_student, crm_event):
    make_student()
    _failed_event(crm_event)

    summary = client.get("/api/v1/admin/crm-sync/summary", headers=login(make_user().email)).get_json()["data"]

    assert summary["events"]["Applied"] >= 1 and summary["failed_events"] == 1
    assert summary["pending_outbox"] >= 1 and summary["outbox"]["Pending"] == summary["pending_outbox"]
    assert "AdmissionQualified" in summary["event_types"] and "LmsAccountProvisioned" in summary["outbox_event_types"]
    assert summary["last_event_received_at"] is not None and summary["oldest_pending_outbox_at"] is not None


def test_event_list_filters_and_detail_shows_the_payload(client, make_user, login, make_student, crm_event):
    make_student()
    failed = _failed_event(crm_event)
    headers = login(make_user().email)

    all_events = client.get("/api/v1/admin/crm-sync/events", headers=headers).get_json()
    assert all_events["meta"]["total"] >= 3 and "payload" not in all_events["data"][0]
    only_failed = client.get("/api/v1/admin/crm-sync/events?status=Failed", headers=headers).get_json()["data"]
    assert [e["event_id"] for e in only_failed] == ["evt-failed-1"] and only_failed[0]["error"]
    by_type = client.get("/api/v1/admin/crm-sync/events?event_type=CourseUpserted", headers=headers).get_json()["data"]
    assert by_type and {e["event_type"] for e in by_type} == {"CourseUpserted"}
    assert [e["event_id"] for e in client.get("/api/v1/admin/crm-sync/events?q=failed-1", headers=headers).get_json()["data"]] == ["evt-failed-1"]
    assert client.get("/api/v1/admin/crm-sync/events?from=2999-01-01", headers=headers).get_json()["data"] == []
    assert client.get("/api/v1/admin/crm-sync/events?status=Nope", headers=headers).status_code == 400

    detail = client.get(f"/api/v1/admin/crm-sync/events/{failed.crm_event_id}", headers=headers).get_json()["data"]
    assert detail["payload"]["admission"]["crm_admission_id"] == "A-900" and detail["status"] == "Failed"
    assert client.get("/api/v1/admin/crm-sync/events/99999", headers=headers).status_code == 404


def test_retry_applies_a_failed_event_once_its_cause_is_fixed_and_is_audited(client, make_user, login, catalog, crm_event):
    failed = _failed_event(crm_event)
    admin = make_user()
    headers = login(admin.email)
    url = f"/api/v1/admin/crm-sync/events/{failed.crm_event_id}/retry"

    still_failing = client.post(url, headers=headers)
    assert still_failing.status_code == 422
    assert client.get(f"/api/v1/admin/crm-sync/events/{failed.crm_event_id}", headers=headers).get_json()["data"]["retries"] == 1

    assert crm_event("CourseUpserted", {"course_code": "NIT-CRS-999", "title": "Late course"}).status_code == 201
    retried = client.post(url, headers=headers)

    data = retried.get_json()["data"]
    assert retried.status_code == 200 and data["status"] == "Applied" and data["retries"] == 2 and data["result"]["student_id"]
    entry = db.session.execute(select(AuditLog).where(AuditLog.action == "CRM_EVENT_RETRIED")).scalar_one()
    assert entry.entity_id == str(failed.crm_event_id) and entry.actor_user_id == admin.user_id
    assert entry.old_values["status"] == "Failed" and entry.new_values["status"] == "Applied"
    assert client.post(url, headers=headers).status_code == 422  # only failed events retry
    assert client.post("/api/v1/admin/crm-sync/events/99999/retry", headers=headers).status_code == 404


def test_outbox_list_filters_and_detail(client, make_user, login, make_student):
    make_student()
    headers = login(make_user().email)

    pending = client.get("/api/v1/admin/crm-sync/outbox?status=Pending", headers=headers).get_json()
    assert pending["meta"]["total"] >= 1 and pending["data"][0]["status"] == "Pending" and pending["data"][0]["payload"]
    assert client.get("/api/v1/admin/crm-sync/outbox?status=Delivered", headers=headers).get_json()["data"] == []
    typed = client.get("/api/v1/admin/crm-sync/outbox?event_type=LmsAccountProvisioned", headers=headers).get_json()["data"]
    assert typed and {r["event_type"] for r in typed} == {"LmsAccountProvisioned"}

    detail = client.get(f"/api/v1/admin/crm-sync/outbox/{pending['data'][0]['outbox_id']}", headers=headers)
    assert detail.status_code == 200 and client.get("/api/v1/admin/crm-sync/outbox/99999", headers=headers).status_code == 404

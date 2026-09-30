"""Support requests: routing to a named owner, scope, the thread, status rules, escalation and reopening."""
import pytest
from sqlalchemy import select

from config.database import db
from models import AuditLog, Notification
from repositories import users as users_repo
from services import support as support_service
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1/support-requests"


def raise_request(client, w, student, category="Academic", details="I cannot open the regression notes", **extra):
    response = client.post(API, headers=w.h(student), json={"category": category, "details": details, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def user_of(student) -> int:
    """The login (user id) of a student."""
    return users_repo.get_by_student_id(student.student_id).user_id


def notifications_for(user_id):
    return list(db.session.execute(select(Notification).where(Notification.recipient_user_id == user_id)).scalars())


class TestRaisingAndRouting:
    def test_academic_request_goes_to_the_lead_trainer_of_the_batch(self, client, world):
        request = raise_request(client, world, world.students.s1)
        assert request["request_code"].startswith("SR-")
        assert request["status"] == "Open"
        assert request["owner"]["user_id"] == world.people.t1.user_id
        assert request["owner"]["label"] == "Trainer — Guntur"
        assert request["raised_via"] == "Student"
        assert [m["body"] for m in request["messages"]] == ["I cannot open the regression notes"]
        assert request["subject"] == "I cannot open the regression notes"
        assert request["sla_due_at"] > request["created_at"]
        [note] = notifications_for(world.people.t1.user_id)
        assert note.title.startswith("New support request") and note.action_status == "Open" and note.link == "/trainer/support"

    def test_recording_access_goes_to_the_academic_coordinator(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        assert request["owner"]["user_id"] == world.people.ac.user_id
        assert request["owner"]["label"] == "Academic Coordinator — Guntur"

    @pytest.mark.parametrize("category", ["LMS", "Account", "Device access"])
    def test_lms_and_account_requests_go_to_the_super_admin_as_lms_support(self, client, world, category):
        request = raise_request(client, world, world.students.s1, category)
        assert request["owner"]["user_id"] == world.people.admin.user_id
        assert request["owner"]["label"] == "LMS Support — Guntur"

    def test_routing_is_by_the_students_service_branch(self, client, world):
        request = raise_request(client, world, world.students.s3, "Other")
        assert request["branch"]["branch_code"] == "NIT-VIJ"
        assert request["owner"]["user_id"] == world.people.ac_vij.user_id

    def test_academic_request_without_a_batch_falls_back_to_the_coordinator(self, client, world, make_student):
        unallocated = make_student(name="No Batch")
        request = raise_request(client, world, unallocated)
        assert request["owner"]["user_id"] == world.people.ac.user_id

    def test_a_missing_owner_is_reported_not_hidden(self, client, world, run_sql):
        for person in (world.people.ac_vij, world.people.bm_vij, world.people.admin):
            run_sql("UPDATE user_role_scopes SET revoked_at = now() WHERE user_id = :u", u=person.user_id)
        response = client.post(API, headers=world.h(world.students.s3),
                               json={"category": "Recording access", "details": "Recording missing"})
        assert response.status_code == 422
        assert "No owner is configured" in response.get_json()["error"]["message"]

    def test_the_request_can_name_one_of_the_students_courses(self, client, world):
        enrolment_id = world.students.s1.enrolments[0]["enrolment_id"]
        request = raise_request(client, world, world.students.s1, enrolment_id=enrolment_id)
        assert request["enrolment"]["enrolment_id"] == enrolment_id
        assert request["owner"]["user_id"] == world.people.t1.user_id

    def test_someone_elses_enrolment_is_rejected(self, client, world):
        other = world.students.s2.enrolments[0]["enrolment_id"]
        response = client.post(API, headers=world.h(world.students.s1),
                               json={"category": "Academic", "details": "About a course", "enrolment_id": other})
        assert response.status_code == 400
        assert "enrolment_id" in response.get_json()["error"]["details"]

    @pytest.mark.parametrize("body", [{}, {"category": "Nope", "details": "abc"}, {"category": "LMS"}, {"category": "LMS", "details": "x"}])
    def test_invalid_input_is_rejected(self, client, world, body):
        assert client.post(API, headers=world.h(world.students.s1), json=body).status_code == 400

    def test_a_student_cannot_raise_a_request_for_another_student(self, client, world):
        response = client.post(API, headers=world.h(world.students.s1),
                               json={"category": "LMS", "details": "hello", "student_id": world.students.s2.student_id})
        assert response.status_code == 400


class TestStaffFlags:
    def test_a_trainer_flags_a_student_of_their_batch(self, client, world):
        response = client.post(API, headers=world.h(world.people.t1), json={
            "category": "Academic", "details": "Missing three classes in a row", "student_id": world.students.s1.student_id})
        assert response.status_code == 201
        request = response.get_json()["data"]
        assert request["raised_via"] == "Staff flag"
        assert request["owner"]["user_id"] == world.people.t1.user_id
        assert any("raised support request" in n.title for n in notifications_for(user_of(world.students.s1)))

    def test_a_trainer_cannot_flag_a_student_outside_their_batches(self, client, world):
        response = client.post(API, headers=world.h(world.people.t1), json={
            "category": "Academic", "details": "Concern", "student_id": world.students.s2.student_id})
        assert response.status_code == 404

    def test_a_staff_flag_needs_a_student(self, client, world):
        assert client.post(API, headers=world.h(world.people.t1), json={"category": "Academic", "details": "Concern"}).status_code == 400

    def test_the_coordinator_flags_within_their_branch_only(self, client, world):
        ok = client.post(API, headers=world.h(world.people.ac), json={
            "category": "Other", "details": "Follow up needed", "student_id": world.students.s2.student_id})
        assert ok.status_code == 201
        denied = client.post(API, headers=world.h(world.people.ac), json={
            "category": "Other", "details": "Follow up needed", "student_id": world.students.s3.student_id})
        assert denied.status_code == 404

    def test_the_trainers_students_carry_open_requests_as_flags(self, client, world):
        raise_request(client, world, world.students.s1, "Academic", "Attendance question")
        rows = client.get("/api/v1/trainer/students", headers=world.h(world.people.t1)).get_json()["data"]
        assert [r["student"]["student_code"] for r in rows] == [world.students.s1.student_code]
        assert rows[0]["flag"] == "Open — Academic" and rows[0]["batch"]["batch_code"] == world.batches.b1.batch_code
        assert client.get("/api/v1/trainer/students", headers=world.h(world.students.s1)).status_code == 403


class TestScope:
    def test_each_role_sees_only_its_own_requests(self, client, world):
        mine = raise_request(client, world, world.students.s1, "Academic")
        theirs = raise_request(client, world, world.students.s2, "Academic")
        vij = raise_request(client, world, world.students.s3, "Other")

        def ids(person):
            response = client.get(API, headers=world.h(person))
            assert response.status_code == 200
            return {r["support_request_id"] for r in response.get_json()["data"]}

        assert ids(world.students.s1) == {mine["support_request_id"]}
        assert ids(world.people.t1) == {mine["support_request_id"]}          # owner of s1's request only
        assert ids(world.people.t2) == {theirs["support_request_id"]}
        assert ids(world.people.ac) == {mine["support_request_id"], theirs["support_request_id"]}   # the whole branch
        assert ids(world.people.admin) == {mine["support_request_id"], theirs["support_request_id"], vij["support_request_id"]}

    def test_branch_staff_see_their_branch(self, client, world):
        gnt = raise_request(client, world, world.students.s1, "Recording access")
        vij = raise_request(client, world, world.students.s3, "Other")
        assert {r["support_request_id"] for r in client.get(API, headers=world.h(world.people.ac)).get_json()["data"]} == {gnt["support_request_id"]}
        assert {r["support_request_id"] for r in client.get(API, headers=world.h(world.people.bm)).get_json()["data"]} == {gnt["support_request_id"]}
        assert {r["support_request_id"] for r in client.get(API, headers=world.h(world.people.ac_vij)).get_json()["data"]} == {vij["support_request_id"]}

    def test_a_request_outside_scope_is_a_404(self, client, world):
        mine = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{mine['support_request_id']}"
        assert client.get(url, headers=world.h(world.students.s1)).status_code == 200
        for outsider in (world.students.s2, world.people.ac_vij, world.people.bm_vij, world.people.t2):
            assert client.get(url, headers=world.h(outsider)).status_code == 404
        assert client.post(f"{url}/messages", headers=world.h(world.students.s2), json={"body": "hi"}).status_code == 404

    def test_filters(self, client, world):
        raise_request(client, world, world.students.s1, "Recording access")
        raise_request(client, world, world.students.s1, "LMS", "The site is slow today")
        rows = client.get(f"{API}?category=LMS", headers=world.h(world.people.admin)).get_json()
        assert [r["category"] for r in rows["data"]] == ["LMS"] and rows["meta"]["total"] == 1
        assert len(client.get(f"{API}?q=slow", headers=world.h(world.people.admin)).get_json()["data"]) == 1
        assert client.get(f"{API}?status=Bogus", headers=world.h(world.people.admin)).status_code == 400


class TestThread:
    def test_replies_move_the_request_along_and_notify_the_other_side(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        reply = client.post(f"{url}/messages", headers=world.h(world.people.ac), json={"body": "Looking into it"})
        assert reply.status_code == 201
        assert reply.get_json()["data"]["status"] == "In Progress"
        assert any(n.title.startswith("New reply") for n in notifications_for(user_of(world.students.s1)))

        client.post(f"{url}/status", headers=world.h(world.people.ac), json={"status": "Waiting on Student", "note": "Which recording?"})
        back = client.post(f"{url}/messages", headers=world.h(world.students.s1), json={"body": "The one from 24 Sep"})
        assert back.get_json()["data"]["status"] == "In Progress"
        assert [m["from_student"] for m in back.get_json()["data"]["messages"]][0] is True

    def test_internal_remarks_are_hidden_from_the_student(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        note = client.post(f"{url}/messages", headers=world.h(world.people.ac), json={"body": "Check with trainer first", "internal": True})
        assert note.status_code == 201
        assert note.get_json()["data"]["status"] == "Open"          # an internal remark is not a reply
        staff_view = client.get(url, headers=world.h(world.people.ac)).get_json()["data"]["messages"]
        student_view = client.get(url, headers=world.h(world.students.s1)).get_json()["data"]["messages"]
        assert len(staff_view) == 2 and len(student_view) == 1
        assert client.post(f"{url}/messages", headers=world.h(world.students.s1), json={"body": "x", "internal": True}).status_code == 403

    def test_the_thread_is_append_only(self, client, world, run_sql):
        request = raise_request(client, world, world.students.s1)
        with pytest.raises(Exception, match="append-only"):
            run_sql("UPDATE support_messages SET body = 'changed' WHERE support_request_id = :id", id=request["support_request_id"])


class TestStatus:
    def resolve(self, client, world, url, note="Access restored"):
        return client.post(f"{url}/status", headers=world.h(world.people.ac), json={"status": "Resolved", "note": note})

    def test_resolving_needs_a_note_and_notifies_the_student(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        assert client.post(f"{url}/status", headers=world.h(world.people.ac), json={"status": "Resolved"}).status_code == 400
        resolved = self.resolve(client, world, url).get_json()["data"]
        assert resolved["status"] == "Resolved" and resolved["resolution_note"] == "Access restored" and resolved["resolved_at"]
        assert any("resolved" in n.title for n in notifications_for(user_of(world.students.s1)))
        assert db.session.execute(select(AuditLog).where(AuditLog.action == "SUPPORT_RESOLVED")).scalars().first() is not None

    def test_illegal_transitions_are_rejected_by_the_database(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        response = client.post(f"{url}/status", headers=world.h(world.people.ac), json={"status": "Closed"})
        assert response.status_code == 422
        assert "cannot move from Open to Closed" in response.get_json()["error"]["message"]

    def test_only_managers_change_status(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        assert client.post(f"{url}/status", headers=world.h(world.students.s1), json={"status": "In Progress"}).status_code == 403
        assert client.post(f"{url}/status", headers=world.h(world.people.t1), json={"status": "In Progress"}).status_code == 404
        assert client.post(f"{url}/status", headers=world.h(world.people.bm), json={"status": "In Progress"}).status_code == 200

    def test_the_student_closes_a_resolved_request_and_can_reopen_it(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}"
        assert client.post(f"{url}/close", headers=world.h(world.students.s1)).status_code == 422   # not resolved yet
        self.resolve(client, world, url)
        closed = client.post(f"{url}/close", headers=world.h(world.students.s1)).get_json()["data"]
        assert closed["status"] == "Closed" and closed["closed_at"]
        assert client.post(f"{url}/messages", headers=world.h(world.students.s1), json={"body": "hello"}).status_code == 422

        assert client.post(f"{url}/reopen", headers=world.h(world.students.s1), json={}).status_code == 400
        reopened = client.post(f"{url}/reopen", headers=world.h(world.students.s1), json={"reason": "Still cannot play the video"})
        data = reopened.get_json()["data"]
        assert data["status"] == "Open" and data["reopened_count"] == 1 and data["resolved_at"] is None
        assert data["messages"][-1]["kind"] == "Reopened"
        assert db.session.execute(select(AuditLog).where(AuditLog.action == "SUPPORT_REOPENED")).scalars().first() is not None

    def test_only_a_finished_request_can_be_reopened(self, client, world):
        request = raise_request(client, world, world.students.s1)
        response = client.post(f"{API}/{request['support_request_id']}/reopen", headers=world.h(world.students.s1), json={"reason": "why not"})
        assert response.status_code == 422


class TestEscalationAndAssignment:
    def test_a_trainer_request_escalates_to_the_coordinator_then_the_branch_manager(self, client, world):
        request = raise_request(client, world, world.students.s1, "Academic")
        url = f"{API}/{request['support_request_id']}"
        first = client.post(f"{url}/escalate", headers=world.h(world.people.t1), json={"reason": "Needs coordinator decision"})
        assert first.status_code == 200
        data = first.get_json()["data"]
        assert data["escalation_level"] == "Academic Coordinator" and data["owner"]["user_id"] == world.people.ac.user_id
        assert any(n.title.startswith("Escalated to you") for n in notifications_for(world.people.ac.user_id))

        second = client.post(f"{url}/escalate", headers=world.h(world.people.ac), json={"reason": "Unresolved for days"})
        assert second.get_json()["data"]["escalation_level"] == "Branch Manager"
        assert any("needs the Branch Manager" in n.title for n in notifications_for(world.people.bm.user_id))
        assert client.post(f"{url}/escalate", headers=world.h(world.people.ac), json={"reason": "again"}).status_code == 422

    def test_the_branch_manager_lists_escalations(self, client, world):
        escalated = raise_request(client, world, world.students.s1, "Recording access")
        raise_request(client, world, world.students.s1, "Other", "A calmer question")
        client.post(f"{API}/{escalated['support_request_id']}/escalate", headers=world.h(world.people.ac), json={"reason": "Beyond my authority"})
        rows = client.get(f"{API}?escalated=true", headers=world.h(world.people.bm)).get_json()["data"]
        assert [r["support_request_id"] for r in rows] == [escalated["support_request_id"]]
        assert rows[0]["escalation_level"] == "Branch Manager"
        assert client.get(f"{API}?escalated=true", headers=world.h(world.people.bm_vij)).get_json()["data"] == []

    def test_a_student_cannot_escalate(self, client, world):
        request = raise_request(client, world, world.students.s1)
        response = client.post(f"{API}/{request['support_request_id']}/escalate", headers=world.h(world.students.s1), json={"reason": "please hurry"})
        assert response.status_code == 403

    def test_requests_past_their_sla_escalate_to_the_branch_manager(self, app, client, world, run_sql):
        request = raise_request(client, world, world.students.s1, "Recording access")
        fresh = raise_request(client, world, world.students.s1, "Other", "Not overdue")
        run_sql("UPDATE support_requests SET sla_due_at = now() - interval '1 hour' WHERE support_request_id = :id", id=request["support_request_id"])
        detail = client.get(f"{API}/{request['support_request_id']}", headers=world.h(world.people.ac)).get_json()["data"]
        assert detail["sla_breached"] is True

        assert support_service.escalate_overdue() == 1
        db.session.commit()
        after = client.get(f"{API}/{request['support_request_id']}", headers=world.h(world.people.bm)).get_json()["data"]
        assert after["escalation_level"] == "Branch Manager" and "SLA breached" in after["messages"][-1]["body"]
        assert after["messages"][-1]["author"]["full_name"] == "System"
        assert client.get(f"{API}/{fresh['support_request_id']}", headers=world.h(world.people.ac)).get_json()["data"]["escalation_level"] is None
        assert support_service.escalate_overdue() == 0                       # idempotent
        assert db.session.execute(select(AuditLog).where(AuditLog.action == "SUPPORT_ESCALATED")).scalars().first().actor_user_id is None

    def test_the_coordinator_reassigns_to_a_colleague_of_the_branch(self, client, world):
        request = raise_request(client, world, world.students.s1, "Recording access")
        url = f"{API}/{request['support_request_id']}/assign"
        assert client.post(url, headers=world.h(world.people.ac), json={"owner_user_id": world.people.ac_vij.user_id}).status_code == 400
        assert client.post(url, headers=world.h(world.people.ac), json={"owner_user_id": 0}).status_code == 400
        assigned = client.post(url, headers=world.h(world.people.ac), json={"owner_user_id": world.people.t2.user_id})
        assert assigned.status_code == 200
        assert assigned.get_json()["data"]["owner"]["user_id"] == world.people.t2.user_id
        assert assigned.get_json()["data"]["owner"]["label"] == "Trainer — Guntur"
        assert any(n.title.endswith("assigned to you") for n in notifications_for(world.people.t2.user_id))
        assert client.post(url, headers=world.h(world.students.s1), json={"owner_user_id": world.people.t2.user_id}).status_code == 403
        assert client.post(url, headers=world.h(world.people.t1), json={"owner_user_id": world.people.t1.user_id}).status_code == 403


def test_the_database_requires_a_resolution_note(run_sql, world, client):
    request = raise_request(client, world, world.students.s1, "Recording access")
    with pytest.raises(Exception, match="support_requests_resolution"):
        run_sql("UPDATE support_requests SET status = 'Resolved' WHERE support_request_id = :id", id=request["support_request_id"])


def test_the_overdue_job_runs_from_the_jobs_runner(app, client, world, run_sql):
    request = raise_request(client, world, world.students.s1, "Recording access")
    run_sql("UPDATE support_requests SET sla_due_at = now() - interval '1 hour' WHERE support_request_id = :id", id=request["support_request_id"])
    db.session.commit()
    result = app.test_cli_runner().invoke(args=["jobs", "run", "support-escalate-overdue"])
    assert result.exit_code == 0 and "support-escalate-overdue: {'escalated': 1}" in result.output
    assert "support-escalate-overdue" in app.test_cli_runner().invoke(args=["jobs", "list"]).output
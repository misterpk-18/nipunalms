"""Academic Calendar and working days (Module 15 §6, §9; Module 19–21 targets): closures, allocation deadlines and the
Founder / Super Admin escalation, the next-day attendance alert, and review targets."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text

from config.database import db
from config.timezone import IST, today_ist
from models import Enrolment, Notification
from services import batch_allocations, working_days
from services.jobs import JOBS
from tests import helpers
from tests.services_fixtures import world  # noqa: F401

API = "/api/v1/calendar/closures"
MONDAY = today_ist() + timedelta(days=7 - today_ist().weekday())   # next Monday: review targets must not be overdue yet


def closure(run_sql, starts_on, ends_on=None, branch_id=None, status="Approved"):
    kind = "Branch Closure" if branch_id else "Company Holiday"
    run_sql("INSERT INTO calendar_closures (kind, branch_id, starts_on, ends_on, title, status, requested_by, decided_by, decided_at) "
            "SELECT CAST(:k AS calendar_closure_kind), :b, :s, :e, 'Closed', CAST(:st AS approval_status), user_id, "
            "CASE WHEN CAST(:st AS text) = 'Pending' THEN NULL ELSE user_id END, "
            "CASE WHEN CAST(:st AS text) = 'Pending' THEN NULL ELSE now() END FROM users LIMIT 1",
            k=kind, b=branch_id, s=starts_on, e=ends_on or starts_on, st=status)


def titles_for(user_id):
    return list(db.session.execute(select(Notification.title).where(Notification.recipient_user_id == user_id)).scalars())


# ---------------------------------------------------------------- working days

def test_every_day_counts_until_the_calendar_or_the_setting_says_otherwise(world, run_sql):
    """Module 15 §9: Sundays, weekends and bank holidays are not assumed closed."""
    saturday = MONDAY - timedelta(days=2)
    assert working_days.add_working_days(saturday, 1) == saturday + timedelta(days=1)          # Sunday counts by default
    closure(run_sql, MONDAY + timedelta(days=1))                                               # company holiday on Tuesday
    assert working_days.add_working_days(MONDAY, 1) == MONDAY + timedelta(days=2)
    closure(run_sql, MONDAY + timedelta(days=2), branch_id=2)                                  # Vijayawada closed Wednesday
    assert working_days.add_working_days(MONDAY, 1, 1) == MONDAY + timedelta(days=2)
    assert working_days.add_working_days(MONDAY, 1, 2) == MONDAY + timedelta(days=3)
    closure(run_sql, MONDAY + timedelta(days=3), branch_id=1, status="Pending")                # not approved: still a working day
    assert working_days.is_working_day(MONDAY + timedelta(days=3), 1)
    run_sql("UPDATE app_settings SET setting_value = '[1,2,3,4,5]' WHERE setting_key = 'working_weekdays'")
    friday = MONDAY + timedelta(days=4)
    assert working_days.add_working_days(friday, 1) == friday + timedelta(days=3)              # Mon–Fri when configured
    assert working_days.working_days_between(MONDAY, friday, 1) == 3                           # Tue is a holiday


# ---------------------------------------------------------------- closures

def test_a_branch_manager_records_a_branch_closure_and_it_is_approved_as_recorded(client, world):
    people = world.people
    upcoming = world.sessions.upcoming.starts_at.astimezone(IST).date()
    body = {"kind": "Branch Closure", "branch_id": 1, "starts_on": upcoming.isoformat(), "ends_on": upcoming.isoformat(),
            "title": "Flooding", "reason": "Road closed"}
    assert client.post(API, json=body, headers=world.h(people.t1)).status_code == 403
    assert client.post(API, json={**body, "branch_id": 2}, headers=world.h(people.ac)).status_code == 404
    assert client.post(API, json={**body, "kind": "Company Holiday", "branch_id": None}, headers=world.h(people.ac)).status_code == 403
    assert working_days.is_working_day(upcoming, 1)
    recorded = client.post(API, json=body, headers=world.h(people.ac))
    assert recorded.status_code == 201 and recorded.get_json()["data"]["status"] == "Approved"   # the Branch Manager's own entry
    closure_id = recorded.get_json()["data"]["closure_id"]
    assert not working_days.is_working_day(upcoming, 1)

    detail = client.get(f"{API}/{closure_id}", headers=world.h(people.ac)).get_json()["data"]
    assert [s["session_code"] for s in detail["affected_sessions"]] == [world.sessions.upcoming.session_code]
    assert client.get(f"{API}/{closure_id}", headers=world.h(people.ac_vij)).status_code == 404
    assert client.post(f"{API}/{closure_id}/decision", json={"decision": "Approved"}, headers=world.h(people.bm)).status_code == 422  # nothing is pending
    assert any("1 class(es) need a replacement" in t for t in titles_for(people.bm.user_id))   # classes are not moved automatically
    listed = client.get(API, headers=world.h(people.t1)).get_json()["data"]
    assert [c["title"] for c in listed] == ["Flooding"]
    assert client.get(API, headers=world.h(people.ac_vij)).get_json()["data"] == []


def test_company_holidays_are_set_centrally_and_approved_at_once(client, world):
    body = {"kind": "Company Holiday", "starts_on": "2026-10-20", "ends_on": "2026-10-21", "title": "Diwali"}
    assert client.post(API, json=body, headers=world.h(world.people.bm)).status_code == 403
    made = client.post(API, json=body, headers=world.h(world.people.founder))
    assert made.status_code == 201 and made.get_json()["data"]["status"] == "Approved"
    assert not working_days.is_working_day(date(2026, 10, 21), 2)
    assert client.post(API, json={**body, "ends_on": "2026-10-19"}, headers=world.h(world.people.admin)).status_code == 400


# ---------------------------------------------------------------- allocation deadline and escalation

def _admit(crm_event, admission_id, *, start, seat_type=None, admitted=None):
    data = helpers.admission_data(person_id=f"P-{admission_id}", admission_id=admission_id, email=f"{admission_id}@example.test")
    data["admission"]["planned_start_date"] = start.isoformat()
    data["admission"]["admission_date"] = (admitted or MONDAY).isoformat()
    if seat_type:
        data["admission"]["seat_type"] = seat_type
    assert crm_event("AdmissionQualified", data).status_code == 201
    return db.session.execute(select(Enrolment).join(Enrolment.admission).where(text("admissions.crm_admission_id = :a")),
                              {"a": admission_id}).scalars().one()


def test_the_allocation_deadline_follows_module_15(catalog, crm_event, run_sql):
    confirmed = _admit(crm_event, "A-201", start=MONDAY + timedelta(days=10), seat_type="Confirmed Seat")
    assert batch_allocations.allocation_due_on(confirmed) == MONDAY + timedelta(days=1)       # one working day after Admission
    closure(run_sql, MONDAY + timedelta(days=1))
    assert batch_allocations.allocation_due_on(confirmed) == MONDAY + timedelta(days=2)       # skipping the holiday
    soon = _admit(crm_event, "A-202", start=MONDAY + timedelta(days=1), seat_type="Confirmed Seat")
    assert batch_allocations.allocation_due_on(soon) == MONDAY                                 # never past the first class
    future = _admit(crm_event, "A-203", start=MONDAY + timedelta(days=10), seat_type="Future Plan")
    assert batch_allocations.allocation_due_on(future) == MONDAY + timedelta(days=8)          # 48 hours before the first class
    late = _admit(crm_event, "A-204", start=MONDAY + timedelta(days=1), seat_type="Future Plan")
    assert batch_allocations.allocation_due_on(late) == MONDAY + timedelta(days=1)            # inside the window: before the class


def test_an_unresolved_allocation_is_escalated_to_the_founder_and_super_admin(catalog, crm_event, make_user, client, login):
    founder, admin = make_user(roles=[("FOUNDER_CEO", None)]), make_user(roles=[("SUPER_ADMIN", None)])
    manager = make_user(roles=[("BRANCH_MANAGER", 1)])
    _admit(crm_event, "A-301", start=today_ist() + timedelta(days=1), admitted=today_ist())
    assert batch_allocations.escalate_unallocated() == 1
    for person in (founder, admin, manager):
        assert any(t.startswith("Allocate a batch now") for t in titles_for(person.user_id))
    coordinator = make_user(roles=[("BRANCH_MANAGER", 1)])
    queue = client.get("/api/v1/allocation-queue", headers=login(coordinator.email)).get_json()["data"]
    assert queue[0]["allocation_due_on"] == today_ist().isoformat()


# ---------------------------------------------------------------- attendance confirmation

def test_unconfirmed_attendance_alerts_the_branch_manager_from_the_next_working_day(world, run_sql):
    delivered = world.sessions.delivered                                                       # three days ago, nobody marked
    assert JOBS["attendance-unconfirmed"]() == {"alerted": 1}
    assert JOBS["attendance-unconfirmed"]() == {"alerted": 0}                                  # once per class
    assert any(t.startswith(f"Attendance not confirmed: {delivered.session_code}") for t in titles_for(world.people.ac.user_id))

    yesterday = datetime.now(IST).replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=1)
    run_sql("INSERT INTO class_sessions (batch_id, title, starts_at, ends_at, mode, trainer_user_id, state, delivered_at) "
            "VALUES (:b, 'Yesterday', :s, :e, 'Classroom', :t, 'Delivered', :e)",
            b=world.batches.b1.batch_id, s=yesterday, e=yesterday + timedelta(hours=2), t=world.people.t1.user_id)
    closure(run_sql, today_ist(), branch_id=1)                                                 # today is closed: not yet the next working day
    assert JOBS["attendance-unconfirmed"]() == {"alerted": 0}
    run_sql("DELETE FROM calendar_closures")
    assert JOBS["attendance-unconfirmed"]() == {"alerted": 1}


# ---------------------------------------------------------------- review targets

def test_review_targets_count_working_days_by_kind(world, run_sql):
    """Module 19 §8 / Module 20 §8: 3 working days for routine work, 5 for mini projects and coding, 7 for final work."""
    from services import review_clock

    submitted = datetime.combine(MONDAY, datetime.min.time(), tzinfo=IST).replace(hour=11)
    assert review_clock.review_due("Module assignment", submitted, 1)["due_on"] == MONDAY + timedelta(days=3)
    assert review_clock.review_due("Mini project", submitted, 1)["target_days"] == 5
    assert review_clock.review_due("Final test", submitted, 1, tests=True)["due_on"] == MONDAY + timedelta(days=7)
    assert review_clock.review_due("Practice quiz", submitted, 1, tests=True) is None
    closure(run_sql, MONDAY + timedelta(days=2))
    assert review_clock.review_due("Module assignment", submitted, 1)["due_on"] == MONDAY + timedelta(days=4)
    assert review_clock.review_due("Module assignment", submitted, 1)["overdue"] is False
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    assert review_clock.review_due("Module assignment", month_ago, 1)["overdue"] is True

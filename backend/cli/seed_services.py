"""Staging data for the student-services slice: support requests, notifications, career support and Ask Nipuna samples.

Built from the prototype's sample data through the real API (logging in as the student and the staff, as they would),
so every rule applies. Appended to the seeders in cli/seed.py.
"""
import io
from datetime import date
from typing import TYPE_CHECKING

import click
from sqlalchemy import text

from config.database import db
from repositories import users as users_repo
from services.notifications import notify

if TYPE_CHECKING:
    from cli.seed import SeedContext

API = "/api/v1"
PASSWORD = "Nipuna-staging-1"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
EDGE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Edg/120.0"
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"

OPPORTUNITIES = [
    dict(title="Junior Data Analyst", employer_name="Sample Analytics Pvt Ltd", location="Hyderabad", work_mode="Hybrid",
         required_skills=["SQL", "Python"], compensation_text="Not Disclosed"),
    dict(title="ML Intern", employer_name="Example AI Labs", location="Remote", work_mode="Remote", employment_type="Internship",
         required_skills=["Python", "Machine Learning"], compensation_text="Stipend INR 15,000 per month"),
    dict(title="BI Developer", employer_name="Demo Retail Co.", location="Vijayawada", required_skills=["Power BI", "SQL"]),
    dict(title="Data Engineer Trainee", employer_name="Sample Cloud Ltd", location="Guntur", required_skills=["SQL", "AWS"], openings=3),
]


class Actor:
    """Calls the API as one signed-in person."""

    def __init__(self, ctx: "SeedContext", login: str, user_agent: str | None = None):
        headers = {"User-Agent": user_agent} if user_agent else {}
        response = ctx.client.post(f"{API}/auth/login", json={"login": login, "password": PASSWORD}, headers=headers)
        if response.status_code != 200:
            raise click.ClickException(f"Seed login failed for {login}: {response.get_json()}")
        self.ctx = ctx
        self.headers = {"Authorization": f"Bearer {response.get_json()['data']['token']}"}

    def call(self, method: str, path: str, expect: int | tuple[int, ...] = (200, 201), **kwargs):
        response = getattr(self.ctx.client, method)(f"{API}{path}", headers=self.headers, **kwargs)
        allowed = (expect,) if isinstance(expect, int) else expect
        if response.status_code not in allowed:
            raise click.ClickException(f"{method.upper()} {path} failed ({response.status_code}): {response.get_json()}")
        return (response.get_json() or {}).get("data")


def _next_support_code(number: int) -> None:
    """The next support request gets SR-<number> (the prototype's codes)."""
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES ('SR', :v) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = :v"), {"v": number - 1})
    db.session.commit()


def _support(ctx: "SeedContext") -> None:
    anvitha = Actor(ctx, ctx.students["anvitha"]["student_code"])
    coordinator = Actor(ctx, "coordinator.gnt@nipuna.test")
    admin = Actor(ctx, "admin@nipuna.test")
    manager = Actor(ctx, "bm.gnt@nipuna.test")

    _next_support_code(1019)
    login_issue = anvitha.call("post", "/support-requests", json={"category": "Account", "details": "I cannot sign in on my phone after changing it."})
    admin.call("post", f"/support-requests/{login_issue['support_request_id']}/messages", json={"body": "Please try again now; your old session was cleared."})
    admin.call("post", f"/support-requests/{login_issue['support_request_id']}/status", json={"status": "Resolved", "note": "Old sessions cleared; sign-in works."})
    anvitha.call("post", f"/support-requests/{login_issue['support_request_id']}/close")

    _next_support_code(1042)
    recording = anvitha.call("post", "/support-requests", json={
        "category": "Recording access", "details": "The recording for the 24 Sep class is held. When will it be released?"})
    coordinator.call("post", f"/support-requests/{recording['support_request_id']}/messages", json={"body": "It is under review; we will release it once checked."})

    trainer = Actor(ctx, "trainer.g1@nipuna.test")
    _next_support_code(1051)
    flag = trainer.call("post", "/support-requests", json={
        "category": "Academic", "details": "Attendance is 71%, below the 75% alert threshold. Recovery needed.",
        "student_id": ctx.students["G"]["student_id"]})
    trainer.call("post", f"/support-requests/{flag['support_request_id']}/escalate", json={"reason": "Needs a recovery plan from the coordinator"})
    coordinator.call("post", f"/support-requests/{flag['support_request_id']}/escalate", json={"reason": "Recovery approval is beyond routine follow-up"})
    manager.call("post", f"/support-requests/{flag['support_request_id']}/messages", json={"body": "Reviewing the recovery options with the coordinator.", "internal": True})

    _next_support_code(1060)
    Actor(ctx, "trainer.v1@nipuna.test").call("post", "/support-requests", json={
        "category": "Device access", "details": "Cannot open the class link from the phone.", "student_id": ctx.students["J"]["student_id"]})


def _notifications(ctx: "SeedContext") -> None:
    student = users_repo.get_by_student_id(ctx.students["anvitha"]["student_id"]).user_id
    notify(category="Assignment", title="Assignment 'Regression on housing dataset' due 29 Sep", event_key="seed:n1", link="/assignments",
           recipient_user_ids=[student], action_required=True)
    notify(category="Recording", title="Recording for 24 Sep held for review", event_key="seed:n2", link="/recordings", recipient_user_ids=[student])
    notify(category="Session", title="Module test scheduled 03 Oct", event_key="seed:n5", link="/tests", recipient_user_ids=[student])
    db.session.execute(text("UPDATE notifications SET read_at = now(), acknowledged_at = now() WHERE event_key = 'seed:n2'"))
    db.session.execute(text("INSERT INTO notifications (recipient_user_id, category, title, event_key, channel, delivery_status, delivery_note) "
                            "VALUES (:u, 'Session', 'WhatsApp reminder for class 28 Sep', 'seed:n3', 'WhatsApp', 'Failed', "
                            "'Integration Pending Verification')"), {"u": student})

    for key, batch in (("trainer_g1", "G1"), ("trainer_v1", "V1")):
        trainer = ctx.users[key]
        code = ctx.batches[batch].batch_code
        notify(category="Attendance", title=f"Attendance for the 24 Sep class of {code} is not marked yet", event_key=f"seed:{key}:a1",
               link="/trainer/attendance", recipient_user_ids=[trainer], action_required=True)
        notify(category="Review", title="Three submissions are waiting for your review", event_key=f"seed:{key}:a2",
               link="/trainer/reviews", recipient_user_ids=[trainer])
        notify(category="Session", title=f"Class of {code} rescheduled to 05 Oct", event_key=f"seed:{key}:a3", recipient_user_ids=[trainer])
        db.session.execute(text("UPDATE notifications SET read_at = now(), acknowledged_at = now(), action_status = 'Completed' "
                                "WHERE event_key = :k"), {"k": f"seed:{key}:a3"})
        db.session.execute(text("INSERT INTO notifications (recipient_user_id, category, title, event_key, channel, delivery_status, delivery_note) "
                                "VALUES (:u, 'Session', 'WhatsApp reminder for tomorrow''s class', :k, 'WhatsApp', 'Failed', "
                                "'Integration Not Configured')"), {"u": trainer, "k": f"seed:{key}:a4"})
    db.session.commit()


def _career(ctx: "SeedContext") -> None:
    anvitha = Actor(ctx, ctx.students["anvitha"]["student_code"])
    coordinator = Actor(ctx, "coordinator.gnt@nipuna.test")
    manager = Actor(ctx, "bm.gnt@nipuna.test")

    anvitha.call("put", "/me/career/profile", json={
        "opted_in": True, "preferred_roles": ["Data Analyst", "ML Engineer"], "preferred_locations": ["Hyderabad", "Vijayawada", "Remote"],
        "work_mode": "Any", "qualification": "B.Tech (CSE)", "graduation_year": 2025, "experience_level": "Fresher",
        "skills": ["SQL", "Python", "Pandas"], "availability": "Immediately"})
    anvitha.call("put", "/me/career/consent", json={"sharing_consent": True})
    db.session.execute(text("UPDATE career_profiles SET opted_in_at = :at, support_start = :s, support_end = :e WHERE student_id = :id"),
                       {"at": "2026-08-14T10:00:00+05:30", "s": date(2026, 8, 14), "e": date(2027, 7, 12), "id": ctx.students["anvitha"]["student_id"]})
    db.session.commit()
    for version, label in enumerate(("CV v1", "CV v2", "CV v3 — Data roles"), 1):
        cv = anvitha.call("post", "/me/career/cvs", data={"file": (io.BytesIO(PDF), f"anvitha-cv-v{version}.pdf"), "label": label},
                          content_type="multipart/form-data")
    coordinator.call("post", f"/cv-documents/{cv['cv_id']}/review", json={"status": "Reviewed"})
    coordinator.call("post", f"/career-profiles/{ctx.students['anvitha']['student_id']}/review", json={
        "readiness": "In Preparation", "note": "Add a project link", "skills": [{"name": "SQL", "confidence": "Verified"}]})

    ids = []
    for opportunity in OPPORTUNITIES:
        created = coordinator.call("post", "/opportunities", json={**opportunity, "branch_id": 1})
        coordinator.call("post", f"/opportunities/{created['opportunity_id']}/status", json={"status": "Verification Pending"})
        manager.call("post", f"/opportunities/{created['opportunity_id']}/status",
                     json={"status": "Active", "verification_source": "Employer website and HR contact call"})
        ids.append(created["opportunity_id"])

    applications = [anvitha.call("post", f"/me/career/opportunities/{oid}/apply") for oid in ids[:3]]
    coordinator.call("post", f"/applications/{applications[0]['application_id']}/status", json={
        "status": "Interview Scheduled", "interview_round": "Technical round 2", "interview_at": "2026-10-02T15:00:00+05:30"})
    coordinator.call("post", f"/applications/{applications[1]['application_id']}/status", json={"status": "Offer Received", "note": "Offer letter received"})
    coordinator.call("post", f"/applications/{applications[2]['application_id']}/status", json={"status": "Rejected", "note": "Not shortlisted"})
    coordinator.call("post", "/placement-outcomes", json={
        "student_id": ctx.students["anvitha"]["student_id"], "application_id": applications[1]["application_id"],
        "outcome_type": "Offer Received", "employer_name": "Example AI Labs", "role_title": "ML Intern", "event_date": "2026-09-25"})


def _assistant(ctx: "SeedContext") -> None:
    anvitha = Actor(ctx, ctx.students["anvitha"]["student_code"], EDGE)
    Actor(ctx, ctx.students["anvitha"]["student_code"], ANDROID)  # a second device for the profile screen
    first = anvitha.call("post", "/ask-nipuna/queries", json={"question": "When is my next class?"})
    anvitha.call("post", f"/ask-nipuna/queries/{first['ai_query_id']}/feedback", json={"rating": "Helpful"})
    anvitha.call("post", "/ask-nipuna/queries", json={"question": "How am I doing in my course?", "action": "Explain my progress"})
    anvitha.call("post", "/ask-nipuna/queries", json={"question": "What is another student's attendance in my batch?"})
    Actor(ctx, "trainer.g1@nipuna.test").call("post", "/ask-nipuna/queries", json={
        "question": "Summarize batch progress", "action": "Summarize batch progress"})


def seed_student_services(ctx: "SeedContext") -> None:
    _support(ctx)
    _notifications(ctx)
    _career(ctx)
    _assistant(ctx)
    ctx.notes.append("Student services: support requests SR-1019 / 1042 / 1051 (escalated to the Branch Manager) / 1060, career profile "
                     "with CVs, four approved opportunities and three applications, notifications in every state, sample Ask Nipuna answers")

"""flask --app app seed-dev: load staging data into the dev replica (nipunalms-dev), built from the prototype sample data.

Courses, admissions, activation and finance go through the real intake and auth code (CRM events posted with the
service key, POST /auth/activate), so every rule applies exactly as it does in production. Only what the LMS itself
owns and has no API for yet (curriculum, batches, trainer assignments, class sessions, learning progress) is written
through the models.

Run on a freshly rebuilt database: `flask --app app create-dev-db --yes && flask --app app seed-dev`.
All people, phones and emails are fictional (example.test / nipuna.test).

Later slices add their own data by appending a function to SEEDERS; each takes the shared SeedContext and runs in order.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from config.database import db
from config.timezone import IST
from models import (
    ActivityEvent, Batch, BatchTrainer, ClassSession, Course, CourseComponent, CurriculumModule, CurriculumTopic,
    CurriculumVersion, Enrolment, Student, User,
)
from models import (
    Assignment, AssignmentSubmission, AttemptAnswer, InterviewSlot, Question, Result, SubmissionReview, Test, TestAttempt, TestQuestion,
)
from repositories import batches as batches_repo
from services import users as users_service
from services.scoring import score_answer

API = "/api/v1"
STAGING_PASSWORD = "Nipuna-staging-1"
GNT, VIJ = 1, 2
TRAINER_ROLE = "TRAINER"

# key: (full name, login, [(role, branch_id)])
STAFF = {
    "founder": ("Founder / CEO", "founder", [("FOUNDER_CEO", None)]),
    "admin": ("Super Admin", "admin", [("SUPER_ADMIN", None)]),
    "bm_gnt": ("Branch Manager (GNT)", "bm.gnt", [("BRANCH_MANAGER", GNT)]),
    "bm_vij": ("Branch Manager (VIJ)", "bm.vij", [("BRANCH_MANAGER", VIJ)]),
    "coord_gnt": ("Academic Coordinator (GNT)", "coordinator.gnt", [("ACADEMIC_COORDINATOR", GNT)]),
    "coord_vij": ("Academic Coordinator (VIJ)", "coordinator.vij", [("ACADEMIC_COORDINATOR", VIJ)]),
    "trainer_g1": ("Trainer R. Sample", "trainer.g1", [(TRAINER_ROLE, GNT)]),
    "trainer_g2": ("Trainer M. Demo", "trainer.g2", [(TRAINER_ROLE, GNT)]),
    "trainer_g3": ("Trainer K. Sample", "trainer.g3", [(TRAINER_ROLE, GNT)]),
    "trainer_v1": ("Trainer S. Example", "trainer.v1", [(TRAINER_ROLE, VIJ)]),
    "trainer_v2": ("Trainer P. Demo", "trainer.v2", [(TRAINER_ROLE, VIJ)]),
}

# code, title, category (prototype course list; NIT-CRS-019 first because NIT-CRS-018 includes it as a booster)
COURSES = [
    ("NIT-CRS-019", "Microsoft Power BI Data Analytics & Business Intelligence", "Data & Analytics"),
    ("NIT-CRS-047", "Java Full Stack Developer", "Software Development"),
    ("NIT-CRS-052", "Python Full Stack Developer", "Software Development"),
    ("NIT-CRS-007", "AWS with DevOps", "Cloud & DevOps"),
]
COMBO = {
    "course_code": "NIT-CRS-018",
    "title": "Data Science with Python, SQL, Machine Learning & Applied AI",
    "category": "Data & Analytics",
    "is_combo": True,
    "components": [
        {"track_code": "NIT-CRS-018/T1", "track_name": "Python & SQL Foundations", "sort_order": 1},
        {"track_code": "NIT-CRS-018/T2", "track_name": "Machine Learning", "sort_order": 2},
        {"track_code": "NIT-CRS-018/T3", "track_name": "Applied AI", "sort_order": 3},
        {"track_code": "NIT-CRS-019", "track_name": "Microsoft Power BI Data Analytics & Business Intelligence",
         "role": "Included booster", "sort_order": 4, "component_course_code": "NIT-CRS-019"},
    ],
}

# course, track (None = whole course), version label, [(module, module in Telugu, [topics])]. Every version is Active,
# except that NIT-CRS-052 deliberately has none: its enrolments stay in Curriculum Mapping Pending.
CURRICULA = [
    ("NIT-CRS-018", None, "Parent Programme v2026.1", [
        ("Programme Orientation & Learning Plan", None, ["Programme Roadmap & Assessment Scheme", "Learning Tools Setup"]),
        ("Capstone Project", None, ["Capstone Scoping", "Capstone Presentation"]),
    ]),
    ("NIT-CRS-018", "NIT-CRS-018/T1", "Track CV 3.2", [
        ("Python Foundations", "పైథాన్ ఫౌండేషన్స్", ["Python Basics & Data Structures", "Functions & Modules", "DataFrames"]),
        ("Data Cleaning & EDA", None, ["Data Cleaning with Pandas", "Exploratory Data Analysis"]),
        ("SQL for Analytics", "అనలిటిక్స్ కోసం SQL", ["Aggregations & Subqueries", "Joins, Window Functions"]),
    ]),
    ("NIT-CRS-018", "NIT-CRS-018/T2", "Track CV 2.4", [
        ("Supervised Learning", "సూపర్వైజ్డ్ లెర్నింగ్",
         ["Linear & Logistic Regression", "Decision Trees & Ensembles", "k-NN & Naive Bayes"]),
        ("Model Evaluation", "మోడల్ మూల్యాంకనం", ["Cross-validation & Metrics", "Hyperparameter Tuning"]),
        ("Unsupervised Learning", None, ["Clustering (K-Means)", "Dimensionality Reduction (PCA)"]),
    ]),
    ("NIT-CRS-018", "NIT-CRS-018/T3", "Track CV 1.1", [
        ("Generative AI Foundations", None, ["LLM Basics & Prompting", "Embeddings & Vector Search"]),
        ("Building Applied AI Solutions", None, ["Building a RAG Pipeline", "Evaluating AI Applications"]),
    ]),
    ("NIT-CRS-018", "NIT-CRS-019", "Booster CV 1.3", [
        ("Power BI Essentials", None, ["Getting Data & Power Query", "Data Modelling", "DAX Basics", "Building Dashboards"]),
    ]),
    ("NIT-CRS-019", None, "CV 1.3", [
        ("Getting Data & Modelling", None, ["Getting Data & Power Query", "Data Modelling"]),
        ("DAX & Visuals", None, ["DAX Basics", "Building Dashboards"]),
    ]),
    ("NIT-CRS-047", None, "CV 5.1", [
        ("Core Java", None, ["OOP & Collections", "Streams & Lambdas"]),
        ("Spring Boot", None, ["REST APIs with Spring Boot", "JPA & Hibernate"]),
        ("React Front End", None, ["Components & State"]),
    ]),
    ("NIT-CRS-007", None, "CV 4.0", [
        ("AWS Core Services", None, ["EC2 & VPC Networking", "S3 & IAM Policies"]),
        ("DevOps on AWS", None, ["CI/CD with CodePipeline", "Docker & Containers", "Terraform Basics"]),
    ]),
]

# key: code, course, branch, curriculum label, capacity, mode, state, readiness, reason, recovery owner, start, end,
#      trainers (Lead first), crm batch id, seats to fill with sample learners
BATCHES = {
    "G1": dict(code="NIT-GNT-BAT-2026-000001", course="NIT-CRS-018", branch=GNT, version="Parent Programme v2026.1",
               capacity=30, mode="Hybrid", state="Running", start=date(2026, 1, 12), end=date(2026, 12, 18),
               trainers=["trainer_g1", "trainer_g2"], crm="CRM-BAT-101", fillers=20),
    "G2": dict(code="NIT-GNT-BAT-2026-000002", course="NIT-CRS-047", branch=GNT, version="CV 5.1", capacity=30,
               mode="Classroom", state="Full", start=date(2026, 6, 15), end=date(2026, 12, 11),
               trainers=["trainer_g3"], crm="CRM-BAT-102", fillers=30),
    "G3": dict(code="NIT-GNT-BAT-2026-000003", course="NIT-CRS-052", branch=GNT, version=None, capacity=25,
               mode="Classroom", state="Forming", readiness="Blocked",
               reason="Curriculum Mapping Pending: NIT-CRS-052 has no Active curriculum version",
               recovery_owner="Academic Coordinator GNT", start=date(2026, 10, 15), end=None,
               trainers=[], crm="CRM-BAT-103", fillers=3),
    "V1": dict(code="NIT-VIJ-BAT-2026-000001", course="NIT-CRS-007", branch=VIJ, version="CV 4.0", capacity=25,
               mode="Live Online", state="Starting", readiness="Pending Verification",
               reason="Meet organizer Pending Verification", recovery_owner="Super Admin", start=date(2026, 9, 30),
               end=date(2027, 1, 15), trainers=["trainer_v1"], crm="CRM-BAT-201", fillers=16),
    "V2": dict(code="NIT-VIJ-BAT-2026-000002", course="NIT-CRS-019", branch=VIJ, version="CV 1.3", capacity=20,
               mode="Classroom", state="Running", start=date(2026, 8, 24), end=date(2026, 11, 20),
               trainers=["trainer_v2"], crm="CRM-BAT-202", fillers=12),
}

ANVITHA = dict(person="CRM-PER-1001", name="Anvitha K.", name_te="అన్విత కె.", email="anvitha.sample@example.test",
               mobile="9876500417")

# key, name, email, branch, course, batch key (None = not allocated yet), outcome
NAMED_LEARNERS = [
    ("G", "Sample Learner G.", "learner.g@example.test", GNT, "NIT-CRS-018", "G1", None),
    ("H", "Sample Learner H.", "learner.h@example.test", GNT, "NIT-CRS-018", "G1", None),
    ("I", "Sample Learner I.", "learner.i@example.test", GNT, "NIT-CRS-018", "G1", None),
    ("J", "Sample Learner J.", "learner.j@example.test", VIJ, "NIT-CRS-007", "V1", "activation pending"),
    ("A", "Sample Learner A.", "learner.a@example.test", GNT, "NIT-CRS-047", None, "completed: certificate issued"),
    ("B", "Sample Learner B.", "learner.b@example.test", VIJ, "NIT-CRS-052", None, None),
    ("C", "Sample Learner C.", "learner.c@example.test", GNT, "NIT-CRS-019", None, None),
    ("D", "Sample Learner D.", "learner.d@example.test", VIJ, "NIT-CRS-007", None, None),
    ("E", "Sample Learner E.", "learner.e@example.test", VIJ, "NIT-CRS-047", None, None),
    ("F", "Sample Learner F.", "learner.f@example.test", GNT, "NIT-CRS-019", None, "completed: certificate revoked"),
]

# batch key, trainer key, (label, topic) or None, title, date, start, end, mode, state, code
SESSIONS = [
    # Guntur, Data Science (batch G1): the prototype sessions plus the weeks around them
    ("G1", "trainer_g1", ("Track CV 3.2", "Python Basics & Data Structures"), "Python data structures", "2026-08-12", "10:00", "12:00", "Classroom", "Delivered", None),
    ("G1", "trainer_g1", ("Track CV 3.2", "DataFrames"), "Pandas DataFrames lab", "2026-08-14", "10:00", "12:00", "Classroom", "Delivered", None),
    ("G1", "trainer_g2", ("Track CV 3.2", "Data Cleaning with Pandas"), "Cleaning messy data", "2026-08-19", "10:00", "12:00", "Live Online", "Delivered", None),
    ("G1", "trainer_g1", ("Track CV 3.2", "Exploratory Data Analysis"), "EDA case study", "2026-08-21", "10:00", "12:00", "Classroom", "Delivered", None),
    ("G1", "trainer_g1", ("Track CV 3.2", "Aggregations & Subqueries"), "SQL aggregations", "2026-08-26", "10:00", "12:00", "Classroom", "Delivered", None),
    ("G1", "trainer_g1", ("Track CV 3.2", "Joins, Window Functions"), "Window functions lab", "2026-09-02", "10:00", "12:00", "Classroom", "Delivered", "SES-000090"),
    ("G1", "trainer_g2", None, "SQL doubt-clearing", "2026-09-04", "10:00", "11:30", "Live Online", "Delivered", None),
    ("G1", "trainer_g1", None, "Track 1 revision", "2026-09-09", "10:00", "12:00", "Classroom", "Delivered", None),
    ("G1", "trainer_g2", ("Track CV 2.4", "k-NN & Naive Bayes"), "Naive Bayes and k-NN", "2026-09-14", "10:00", "12:00", "Live Online", "Delivered", None),
    ("G1", "trainer_g2", ("Track CV 2.4", "Linear & Logistic Regression"), "Linear regression intuition", "2026-09-21", "10:00", "12:00", "Live Online", "Delivered", "SES-000101"),
    ("G1", "trainer_g2", ("Track CV 2.4", "Linear & Logistic Regression"), "Logistic regression & odds", "2026-09-24", "10:00", "12:00", "Classroom", "Delivered", "SES-000102"),
    ("G1", "trainer_g2", ("Track CV 2.4", "Decision Trees & Ensembles"), "Decision trees", "2026-09-28", "10:00", "12:00", "Live Online", "Scheduled", "SES-000103"),
    ("G1", "trainer_g1", ("Track CV 2.4", "Cross-validation & Metrics"), "Cross-validation workshop", "2026-10-01", "14:00", "16:00", "Classroom", "Scheduled", "SES-000104"),
    ("G1", "trainer_g2", ("Track CV 2.4", "Decision Trees & Ensembles"), "Random forests & boosting", "2026-10-05", "10:00", "12:00", "Live Online", "Scheduled", None),
    ("G1", "trainer_g1", ("Track CV 2.4", "Cross-validation & Metrics"), "Precision, recall and ROC", "2026-10-08", "10:00", "12:00", "Classroom", "Scheduled", None),
    ("G1", "trainer_g2", ("Track CV 2.4", "Hyperparameter Tuning"), "Hyperparameter tuning", "2026-10-12", "10:00", "12:00", "Live Online", "Scheduled", None),
    ("G1", "trainer_g2", ("Track CV 2.4", "Clustering (K-Means)"), "Clustering with K-Means", "2026-10-15", "10:00", "12:00", "Live Online", "Scheduled", None),
    ("G1", "trainer_g1", ("Track CV 2.4", "Dimensionality Reduction (PCA)"), "PCA lab", "2026-10-19", "10:00", "12:00", "Classroom", "Scheduled", None),
    # Guntur, Java Full Stack (batch G2)
    ("G2", "trainer_g3", ("CV 5.1", "OOP & Collections"), "OOP recap", "2026-09-01", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "OOP & Collections"), "Collections deep dive", "2026-09-03", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "Streams & Lambdas"), "Streams and lambdas", "2026-09-08", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "Streams & Lambdas"), "Streams lab", "2026-09-10", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "REST APIs with Spring Boot"), "Spring Boot: first REST API", "2026-09-15", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "REST APIs with Spring Boot"), "Controllers and validation", "2026-09-17", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "JPA & Hibernate"), "JPA entities", "2026-09-22", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "JPA & Hibernate"), "Repositories and queries", "2026-09-24", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", None, "Mini project kick-off", "2026-09-29", "16:00", "18:00", "Classroom", "Delivered", None),
    ("G2", "trainer_g3", ("CV 5.1", "JPA & Hibernate"), "Transactions in JPA", "2026-10-01", "16:00", "18:00", "Classroom", "Scheduled", None),
    ("G2", "trainer_g3", None, "Spring Security basics", "2026-10-06", "16:00", "18:00", "Classroom", "Scheduled", None),
    ("G2", "trainer_g3", ("CV 5.1", "Components & State"), "React components", "2026-10-08", "16:00", "18:00", "Classroom", "Scheduled", None),
    # Vijayawada, AWS with DevOps (batch V1): starts today
    ("V1", "trainer_v1", None, "AWS orientation (VIJ)", "2026-09-30", "18:00", "19:30", "Live Online", "Scheduled", "SES-000201"),
    ("V1", "trainer_v1", ("CV 4.0", "EC2 & VPC Networking"), "EC2 and VPC networking", "2026-10-02", "18:00", "19:30", "Live Online", "Scheduled", None),
    ("V1", "trainer_v1", ("CV 4.0", "S3 & IAM Policies"), "S3 storage and IAM policies", "2026-10-05", "18:00", "19:30", "Live Online", "Scheduled", None),
    ("V1", "trainer_v1", ("CV 4.0", "S3 & IAM Policies"), "IAM roles lab", "2026-10-07", "18:00", "19:30", "Live Online", "Scheduled", None),
    # Vijayawada, Power BI (batch V2)
    ("V2", "trainer_v2", ("CV 1.3", "Getting Data & Power Query"), "Power BI interface and data import", "2026-08-31", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "Getting Data & Power Query"), "Power Query transformations", "2026-09-02", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "Data Modelling"), "Star schema modelling", "2026-09-09", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "Data Modelling"), "Relationships and cardinality", "2026-09-11", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "DAX Basics"), "DAX measures", "2026-09-16", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "DAX Basics"), "Time intelligence in DAX", "2026-09-18", "11:00", "13:00", "Classroom", "Delivered", "SES-000095"),
    ("V2", "trainer_v2", ("CV 1.3", "Building Dashboards"), "Dashboard design", "2026-09-23", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", ("CV 1.3", "Building Dashboards"), "Dashboard lab", "2026-09-25", "11:00", "13:00", "Classroom", "Delivered", None),
    ("V2", "trainer_v2", None, "Capstone briefing", "2026-10-01", "11:00", "13:00", "Classroom", "Scheduled", None),
    ("V2", "trainer_v2", None, "Capstone check-in", "2026-10-03", "11:00", "13:00", "Classroom", "Scheduled", None),
    ("V2", "trainer_v2", None, "Capstone review", "2026-10-08", "11:00", "13:00", "Classroom", "Scheduled", None),
]

# person, admission, receipts: Anvitha's finance summaries as the CRM would send them
FINANCE = [
    ("CRM-ADM-214", dict(fee_total=45000, verified_paid=30000, balance=15000, next_due_date="2026-10-10", next_due_amount=15000,
                         receipts=[{"receipt_number": "GNT-R-2627-00014", "date": "2026-01-10", "amount": 15000},
                                   {"receipt_number": "GNT-R-2627-00031", "date": "2026-04-10", "amount": 15000}])),
    ("CRM-ADM-88", dict(fee_total=22000, verified_paid=22000, balance=0, next_due_date=None, next_due_amount=None,
                        receipts=[{"receipt_number": "GNT-R-2627-00102", "date": "2026-09-20", "amount": 22000}])),
]


@dataclass
class SeedContext:
    client: object
    users: dict[str, int] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)      # curriculum label -> version id
    topics: dict[tuple[str, str], int] = field(default_factory=dict)  # (version label, topic title) -> topic id
    batches: dict[str, Batch] = field(default_factory=dict)
    students: dict[str, dict] = field(default_factory=dict)     # key -> {student_id, student_code, admission ids, token}
    notes: list[str] = field(default_factory=list)              # lines printed at the end
    event_counter: int = 0
    admission_counter: int = 300

    def crm_event(self, event_type: str, data: dict, *, version: int = 1, expect: tuple[int, ...] = (200, 201),
                  occurred_at: str = "2026-09-28T10:00:00+05:30") -> dict:
        """Post a CRM event with the service key, as the CRM does."""
        self.event_counter += 1
        response = self.client.post(
            f"{API}/integrations/crm/events",
            json={"event_id": f"seed-{self.event_counter:05d}", "event_type": event_type, "source_version": version,
                  "occurred_at": occurred_at, "data": data},
            headers={"X-Service-Key": current_app.config["CRM_SERVICE_KEY"]},
        )
        body = response.get_json()
        if response.status_code not in expect:
            raise click.ClickException(f"{event_type} failed ({response.status_code}): {body}")
        return body.get("data", body)

    def activate(self, token: str) -> None:
        response = self.client.post(f"{API}/auth/activate", json={"token": token, "password": STAGING_PASSWORD})
        if response.status_code != 200:
            raise click.ClickException(f"Activation failed: {response.get_json()}")

    def next_admission_number(self) -> int:
        self.admission_counter += 1
        return self.admission_counter


def at(day: str, clock: str) -> datetime:
    """A class time: date + HH:MM, IST."""
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(clock), tzinfo=IST)


# ---------------------------------------------------------------- seeders

def seed_staff(ctx: SeedContext) -> None:
    for key, (full_name, login, scopes) in STAFF.items():
        user = users_service.create_staff_user(full_name, f"{login}@nipuna.test", STAGING_PASSWORD, scopes)
        ctx.users[key] = user.user_id
    db.session.commit()


def seed_courses(ctx: SeedContext) -> None:
    for code, title, category in COURSES:
        ctx.crm_event("CourseUpserted", {"course_code": code, "title": title, "category": category})
    ctx.crm_event("CourseUpserted", COMBO)


def seed_curriculum(ctx: SeedContext) -> None:
    approved_at = datetime(2026, 1, 5, 12, 0, tzinfo=IST)
    for course_code, track_code, label, modules in CURRICULA:
        course = db.session.execute(select(Course).where(Course.course_code == course_code)).scalar_one()
        component = (db.session.execute(select(CourseComponent).where(CourseComponent.track_code == track_code)).scalar_one()
                     if track_code else None)
        version = CurriculumVersion(course_id=course.course_id, component_id=component.component_id if component else None,
                                    version_label=label, status="Active", approved_by=ctx.users["admin"], approved_at=approved_at)
        db.session.add(version)
        db.session.flush()
        ctx.versions[label] = version.curriculum_version_id
        for module_order, (module_title, module_te, topic_titles) in enumerate(modules, 1):
            module = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=module_title,
                                      title_te=module_te, sort_order=module_order)
            db.session.add(module)
            db.session.flush()
            for topic_order, title in enumerate(topic_titles, 1):
                topic = CurriculumTopic(module_id=module.module_id, title=title, sort_order=topic_order)
                db.session.add(topic)
                db.session.flush()
                ctx.topics[(label, title)] = topic.topic_id
    db.session.commit()


def seed_batches(ctx: SeedContext) -> None:
    for key, spec in BATCHES.items():
        course = db.session.execute(select(Course).where(Course.course_code == spec["course"])).scalar_one()
        batch = Batch(batch_code=spec["code"], crm_batch_id=spec["crm"], course_id=course.course_id, branch_id=spec["branch"],
                      curriculum_version_id=ctx.versions[spec["version"]] if spec["version"] else None,
                      capacity=spec["capacity"], mode=spec["mode"], planned_start=spec["start"], planned_end=spec["end"],
                      state=spec["state"], readiness=spec.get("readiness", "Ready"), readiness_reason=spec.get("reason"),
                      recovery_owner=spec.get("recovery_owner"))
        db.session.add(batch)
        db.session.flush()
        for index, trainer in enumerate(spec["trainers"]):
            db.session.add(BatchTrainer(batch_id=batch.batch_id, trainer_user_id=ctx.users[trainer],
                                        role="Lead" if index == 0 else "Co-trainer", from_date=spec["start"]))
        ctx.batches[key] = batch
    db.session.commit()


def _qualify(ctx: SeedContext, key: str, *, person: str, name: str, email: str | None, mobile: str | None, branch: int,
             course: str, crm_batch: str | None, name_te: str | None = None, activate: bool = True) -> None:
    """One paid standalone admission (a combo when the course is one) through AdmissionQualified."""
    number = ctx.next_admission_number()
    code = "GNT" if branch == GNT else "VIJ"
    branch_code = "NIT-GNT" if branch == GNT else "NIT-VIJ"
    combo = course == COMBO["course_code"]
    enrolment = {"course_code": course, **({"kind": "Combo"} if combo else {}), **({"crm_batch_id": crm_batch} if crm_batch else {})}
    data = ctx.crm_event("AdmissionQualified", {
        "person": {"crm_person_id": person, "full_name": name, "name_te": name_te, "email": email, "mobile": mobile},
        "admission": {"crm_admission_id": f"CRM-ADM-{number}", "admission_code": f"ADM-{code}-2026-{number:06d}",
                      "course_code": course, "original_branch_code": branch_code, "service_branch_code": branch_code,
                      "collecting_branch_code": branch_code, "mode": "Classroom", "admission_date": "2026-09-01"},
        "enrolments": [enrolment],
    })
    ctx.students[key] = {**data["result"], "token": data["activation_token"]}
    if activate:
        ctx.activate(data["activation_token"])


def seed_students(ctx: SeedContext) -> None:
    """Anvitha's three enrolments, the named learners, and sample learners to fill the batches."""
    # The first student created gets the sample Student ID NIT-STU-2026-004182
    year = db.session.execute(text("SELECT business_year()")).scalar()
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES (:k, 4181) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = 4181"), {"k": f"STU-{year}"})
    db.session.commit()

    person = {"crm_person_id": ANVITHA["person"], "full_name": ANVITHA["name"], "name_te": ANVITHA["name_te"],
              "email": ANVITHA["email"], "mobile": ANVITHA["mobile"], "preferred_language": "en"}
    combo = ctx.crm_event("AdmissionQualified", {
        "person": person,
        "admission": {"crm_admission_id": "CRM-ADM-214", "admission_code": "ADM-GNT-2026-000214", "course_code": "NIT-CRS-018",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT",
                      "mode": "Hybrid", "admission_date": "2026-01-10"},
        "enrolments": [
            {"course_code": "NIT-CRS-018", "kind": "Combo", "mode": "Hybrid", "crm_batch_id": "CRM-BAT-101"},
            {"course_code": "NIT-CRS-052", "kind": "Complimentary", "mode": "Classroom", "parent_course_code": "NIT-CRS-018",
             "benefit_gate": {"met": True, "note": "Promotional offer: qualifying payment verified on the paid combo admission"}},
        ],
    })
    aws = ctx.crm_event("AdmissionQualified", {
        "person": person,
        "admission": {"crm_admission_id": "CRM-ADM-88", "admission_code": "ADM-VIJ-2026-000088", "course_code": "NIT-CRS-007",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-VIJ", "collecting_branch_code": "NIT-GNT",
                      "mode": "Live Online", "admission_date": "2026-09-20"},
        "enrolments": [{"course_code": "NIT-CRS-007", "kind": "Separately purchased", "crm_batch_id": "CRM-BAT-201"}],
    })
    ctx.students["anvitha"] = {**combo["result"], "token": combo["activation_token"]}
    ctx.activate(combo["activation_token"])
    ctx.students["anvitha_aws"] = aws["result"]

    for key, name, email, branch, course, batch_key, outcome in NAMED_LEARNERS:
        n = len(ctx.students)
        _qualify(ctx, key, person=f"CRM-PER-{1100 + n}", name=name, email=email, mobile=f"98765{40000 + n}", branch=branch,
                 course=course, crm_batch=BATCHES[batch_key]["crm"] if batch_key else None,
                 activate=outcome != "activation pending")
        if outcome == "activation pending":
            ctx.notes.append(f"{name} ({ctx.students[key]['student_code']}) is in Activation Pending; "
                             f"activation link: /activate?token={ctx.students[key]['token']}")

    filler = 0
    for spec in BATCHES.values():
        for _ in range(spec["fillers"]):
            filler += 1
            _qualify(ctx, f"filler-{filler}", person=f"CRM-PER-{2000 + filler}", name=f"Sample Learner {filler:03d}",
                     email=None, mobile=f"98700{10000 + filler}", branch=spec["branch"], course=spec["course"],
                     crm_batch=spec["crm"], activate=filler % 7 != 0)  # every 7th stays Invited


def seed_progress(ctx: SeedContext) -> None:
    """Learners in a running batch have started (joining date = the batch's first class); two learners have completed."""
    enrolments = db.session.execute(select(Enrolment).where(Enrolment.status == "Allocated — awaiting first regular class")).scalars().all()
    for enrolment in enrolments:
        allocation = batches_repo.active_allocation(enrolment.enrolment_id)
        if allocation is not None and allocation.batch.state in ("Running", "Full"):
            enrolment.status = "Active"
            enrolment.joining_date = allocation.batch.planned_start
    for key, certificate_status in (("A", "Issued"), ("F", "Revoked")):
        enrolment = db.session.execute(select(Enrolment).where(Enrolment.student_id == ctx.students[key]["student_id"])).scalar_one()
        enrolment.status = "Completed"
        enrolment.joining_date = date(2026, 3, 2)
        enrolment.certificate_status = certificate_status
    complimentary = db.session.execute(select(Enrolment).where(Enrolment.kind == "Complimentary")).scalar_one()
    complimentary.certificate_status = "Configuration Pending: completion rule not configured for complimentary offer"

    for key, days in (("anvitha", (2, 5, 9, 12, 16, 21, 24, 28)), ("G", (5, 21, 24)), ("H", (2, 4, 9, 14, 21, 24, 28))):
        for day in days:
            db.session.add(ActivityEvent(student_id=ctx.students[key]["student_id"], kind="login",
                                         occurred_at=datetime(2026, 9, day, 9, 30, tzinfo=IST)))
    db.session.commit()


def seed_sessions(ctx: SeedContext) -> None:
    for batch_key, trainer, topic, title, day, start, end, mode, state, code in SESSIONS:
        batch = ctx.batches[batch_key]
        live_online = mode == "Live Online"
        meet_status = ("Linked" if batch.branch_id == GNT else "Pending Verification") if live_online else "Not Required"
        start_at, end_at = at(day, start), at(day, end)
        db.session.add(ClassSession(
            session_code=code, batch_id=batch.batch_id, topic_id=ctx.topics[topic] if topic else None, title=title,
            starts_at=start_at, ends_at=end_at, mode=mode, trainer_user_id=ctx.users[trainer],
            room=None if live_online else ("Lab 1" if batch.branch_id == GNT else "Room 2"),
            meet_status=meet_status,
            meet_link=f"https://meet.google.com/nip-{batch_key.lower()}-{day[-2:]}" if meet_status == "Linked" else None,
            state=state, delivered_at=end_at if state == "Delivered" else None))
    db.session.commit()


def seed_finance(ctx: SeedContext) -> None:
    for crm_admission_id, summary in FINANCE:
        ctx.crm_event("FinanceSummaryUpdated", {"crm_admission_id": crm_admission_id, **summary}, version=2,
                      occurred_at="2026-09-28T18:00:00+05:30")


def seed_crm_inbox_examples(ctx: SeedContext) -> None:
    """Two events for the CRM sync monitor: one that could not be applied yet, one that arrived late and was ignored."""
    ctx.crm_event("AdmissionQualified", {
        "person": {"crm_person_id": "CRM-PER-9001", "full_name": "Sample Learner Z.", "mobile": "9876599001"},
        "admission": {"crm_admission_id": "CRM-ADM-999", "admission_code": "ADM-GNT-2026-000999", "course_code": "NIT-CRS-999",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT"},
        "enrolments": [{"course_code": "NIT-CRS-999"}],
    }, expect=(422,))
    ctx.crm_event("AdmissionUpdated", {"crm_admission_id": "CRM-ADM-214", "mode": "Hybrid"}, version=3)
    ctx.crm_event("AdmissionUpdated", {"crm_admission_id": "CRM-ADM-214", "mode": "Classroom"}, version=2)  # late: ignored


# ---------------------------------------------------------------- assessments (slice S3)

TRACK_ML, TRACK_PY = "Track CV 2.4", "Track CV 3.2"

# key: (curriculum label, topic, type, stem, options, answer key, marks, difficulty, tags, author, status)
QUESTIONS = {
    "metric": (TRACK_ML, "Cross-validation & Metrics", "Single choice", "Which metric suits an imbalanced binary classifier?",
               [("A", "Accuracy"), ("B", "F1-score"), ("C", "R²")], {"option": "B"}, 2, "Medium", ["metrics"], "trainer_g2", "Approved"),
    "regularisation": (TRACK_ML, "Hyperparameter Tuning", "Multiple choice", "Select all regularisation methods.",
                       [("A", "L1 (Lasso)"), ("B", "L2 (Ridge)"), ("C", "One-hot encoding")], {"options": ["A", "B"]}, 2, "Medium", ["regularisation"],
                       "trainer_g2", "Approved"),
    "logistic": (TRACK_ML, "Linear & Logistic Regression", "True / False", "Logistic regression outputs probabilities.", [], {"value": True}, 1, "Easy",
                 ["regression"], "trainer_g2", "Approved"),
    "slope": (TRACK_ML, "Linear & Logistic Regression", "Numeric", "Slope for y = 3x + 2?", [], {"value": 3, "tolerance": 0}, 1, "Easy", ["regression"],
              "trainer_g2", "Approved"),
    "ensemble": (TRACK_ML, "Decision Trees & Ensembles", "Short answer", "Name one ensemble method.", [],
                 {"variants": ["Random forest", "Gradient boosting", "Bagging", "AdaBoost"]}, 2, "Easy", ["ensembles"], "trainer_g2", "Approved"),
    "bias_variance": (TRACK_ML, "Cross-validation & Metrics", "Descriptive", "Explain the bias–variance trade-off.", [],
                      {"rubric": "Defines bias and variance, links them to under- and over-fitting, names a way to balance them"}, 4, "Hard",
                      ["theory"], "trainer_g2", "Approved"),
    "mean": (TRACK_PY, "Python Basics & Data Structures", "Coding", "Write a function returning the mean of a list.", [],
             {"rubric": "Returns sum(xs) / len(xs); handles the empty list explicitly"}, 4, "Easy", ["python"], "trainer_g1", "Approved"),
    "set_len": (TRACK_PY, "Python Basics & Data Structures", "Output prediction", "What does print(len({1, 1, 2})) print?", [], {"variants": ["2"]}, 1,
                "Easy", ["python"], "trainer_g1", "Approved"),
    "dense_rank": (TRACK_PY, "Joins, Window Functions", "Single choice", "Which window function ranks rows without gaps after ties?",
                   [("A", "RANK"), ("B", "DENSE_RANK"), ("C", "ROW_NUMBER")], {"option": "B"}, 1, "Medium", ["sql", "window"], "trainer_g1", "Approved"),
    "top_earner": (TRACK_PY, "Joins, Window Functions", "Coding", "Write a query returning the top earner per department using a window function.", [],
                   {"rubric": "Partitions by department, orders by salary descending, filters rank = 1"}, 6, "Hard", ["sql", "window"], "trainer_g1",
                   "Approved"),
    "having": (TRACK_PY, "Aggregations & Subqueries", "Short answer", "Which clause filters groups after aggregation?", [], {"variants": ["HAVING"]}, 1,
               "Easy", ["sql"], "trainer_g1", "Approved"),
    "left_join": (TRACK_PY, "Joins, Window Functions", "Single choice", "Which join keeps every row of the left table?",
                  [("A", "INNER JOIN"), ("B", "LEFT JOIN"), ("C", "CROSS JOIN")], {"option": "B"}, 1, "Easy", ["sql"], "trainer_g1", "Draft"),
    "knn_k": (TRACK_ML, "k-NN & Naive Bayes", "Numeric", "How many neighbours vote in 5-NN?", [], {"value": 5, "tolerance": 0}, 1, "Easy", ["knn"],
              "trainer_g2", "Draft"),
}

# key, code, title, kind, topic (label, title), required, release, due, max marks, reviewer, brief. asg-11 is due two days after the
# prototype's date so it still reads "Due" (not Overdue) when the staging data is loaded on the prototype's "today", 30 Sep 2026.
ASSIGNMENTS = [
    ("asg06", "ASG-0006", "Python data structures worksheet", "Class assignment", (TRACK_PY, "Python Basics & Data Structures"), True,
     ("2026-08-12", "12:00"), ("2026-08-19", "23:59"), 10, "trainer_g1", "Complete the worksheet on lists, dicts and sets."),
    ("asg07", "ASG-0007", "Data cleaning checkpoint", "Class assignment", (TRACK_PY, "Data Cleaning with Pandas"), True,
     ("2026-09-10", "12:00"), ("2026-09-24", "23:59"), 10, "trainer_g1", "Clean the provided messy dataset and document each step."),
    ("asg08", "ASG-0008", "Pandas cleaning practice", "Class assignment", (TRACK_PY, "DataFrames"), False,
     ("2026-08-25", "12:00"), ("2026-09-01", "23:59"), 10, "trainer_g2", "Optional practice: reshape and clean a small DataFrame."),
    ("asg09", "ASG-0009", "SQL window functions set", "Module assignment", (TRACK_PY, "Joins, Window Functions"), True,
     ("2026-09-02", "12:00"), ("2026-09-09", "23:59"), 20, "trainer_g1", "Solve the ten window-function exercises."),
    ("asg10", "ASG-0010", "EDA mini report", "Mini project", (TRACK_PY, "Joins, Window Functions"), False,
     ("2026-09-10", "12:00"), ("2026-09-20", "23:59"), 20, "trainer_g1", "A short exploratory analysis of the sales dataset."),
    ("asg11", "ASG-0011", "Regression on housing dataset", "Module assignment", (TRACK_ML, "Linear & Logistic Regression"), True,
     ("2026-09-21", "12:00"), ("2026-10-02", "23:59"), 20, "trainer_g1",
     "Build and evaluate a model on the provided dataset; include a short write-up of assumptions. Resources: housing.csv, starter notebook."),
    ("asg12", "ASG-0012", "Decision tree tuning notebook", "Module assignment", (TRACK_ML, "Decision Trees & Ensembles"), True,
     ("2026-09-28", "12:00"), ("2026-10-05", "23:59"), 20, "trainer_g2", "Tune a decision tree and report the effect of each hyperparameter."),
]


def _gnt_enrolment(ctx: SeedContext, key: str) -> Enrolment:
    """The student's Data Science (batch G1) enrolment."""
    course = db.session.execute(select(Course).where(Course.course_code == "NIT-CRS-018")).scalar_one()
    return db.session.execute(select(Enrolment).where(Enrolment.student_id == ctx.students[key]["student_id"],
                                                      Enrolment.course_id == course.course_id)).scalar_one()


def seed_assessments(ctx: SeedContext) -> None:
    """Assignments asg-06..12, the question bank, tests tst-1..8, interview slots and results, as in the prototype's sample data."""
    batch = ctx.batches["G1"]
    coord = ctx.users["coord_gnt"]
    people = {k: _gnt_enrolment(ctx, k) for k in ("anvitha", "G", "H")}

    # ---- question bank
    questions: dict[str, Question] = {}
    for key, (label, title, qtype, stem, options, answer_key, marks, difficulty, tags, author, status) in QUESTIONS.items():
        approved = status == "Approved"
        question = Question(course_id=batch.course_id, branch_id=GNT, topic_id=ctx.topics[(label, title)], question_type=qtype, stem=stem,
                            options=[{"key": k, "text": t} for k, t in options], answer_key=answer_key, marks=marks, difficulty=difficulty,
                            tags=tags, author_user_id=ctx.users[author], status=status, reviewed_by=coord if approved else None,
                            approved_at=at("2026-09-01", "12:00") if approved else None)
        db.session.add(question)
        questions[key] = question
    db.session.flush()

    # ---- assignments, submissions, reviews
    assignments: dict[str, Assignment] = {}
    for key, code, title, kind, topic, required, release, due, max_marks, reviewer, brief in ASSIGNMENTS:
        due_at = at(*due)
        assignment = Assignment(assignment_code=code, batch_id=batch.batch_id, topic_id=ctx.topics[topic], title=title, kind=kind, brief=brief,
                                attachments=[{"name": "housing.csv", "url": "https://example.test/files/housing.csv"}] if key == "asg11" else [],
                                is_required=required, max_marks=max_marks, release_at=at(*release), due_at=due_at,
                                closes_at=due_at + timedelta(days=7), reviewer_user_id=ctx.users[reviewer], status="Released",
                                released_by=ctx.users[reviewer], created_by=ctx.users[reviewer])
        db.session.add(assignment)
        assignments[key] = assignment
    db.session.flush()

    def submit(key, who, version, attempt_no, day, clock, text, started_review=False):
        enrolment = people[who]
        submission = AssignmentSubmission(
            assignment_id=assignments[key].assignment_id, enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id,
            version_no=version, attempt_no=attempt_no, body_text=text, submitted_at=at(day, clock),
            review_started_at=at(day, "22:30") if started_review else None,
            review_started_by=assignments[key].reviewer_user_id if started_review else None)
        db.session.add(submission)
        db.session.flush()
        return submission

    def review(submission, outcome, feedback, day, marks=None, resubmit_due=None):
        db.session.add(SubmissionReview(submission_id=submission.submission_id, reviewer_user_id=assignments_by_id[submission.assignment_id].reviewer_user_id,
                                        outcome=outcome, feedback=feedback, marks=marks, resubmission_due_at=resubmit_due, reviewed_at=at(day, "17:00")))
        db.session.flush()

    assignments_by_id = {a.assignment_id: a for a in assignments.values()}

    v1 = submit("asg06", "anvitha", 1, 1, "2026-08-18", "20:10", "Worksheet answers attached in the notebook.")
    review(v1, "Resubmission Requested", "Dictionary questions 4 and 5 need working shown.", "2026-08-20", resubmit_due=at("2026-10-05", "23:59"))
    submit("asg08", "anvitha", 1, 1, "2026-08-31", "21:00", "Cleaned the DataFrame; notebook link in the class folder.")
    v1 = submit("asg09", "anvitha", 1, 1, "2026-09-05", "19:30", "First attempt at the window functions.")
    review(v1, "Resubmission Requested", "Partitioning is right; rework questions 6-8.", "2026-09-06", resubmit_due=at("2026-09-10", "23:59"))
    v2 = submit("asg09", "anvitha", 2, 2, "2026-09-08", "22:15", "Reworked answers.")
    review(v2, "Reviewed", "Good partitioning; revisit RANK vs DENSE_RANK.", "2026-09-10", marks=18)
    db.session.add(Result(enrolment_id=v2.enrolment_id, student_id=v2.student_id, batch_id=batch.batch_id, assignment_id=v2.assignment_id,
                          submission_id=v2.submission_id, max_marks=20, provisional_marks=18, status="Published", final_marks=18,
                          published_by=coord, published_at=at("2026-09-11", "11:00")))
    submit("asg10", "anvitha", 1, 1, "2026-09-19", "20:40", "EDA report: sales by region and month.", started_review=True)
    g1 = submit("asg11", "G", 1, 1, "2026-09-25", "21:05", "Linear regression with two features.")
    h1 = submit("asg11", "H", 1, 1, "2026-09-24", "18:20", "Baseline model only.")
    review(h1, "Resubmission Requested", "Add the assumptions write-up.", "2026-09-25", resubmit_due=at("2026-10-01", "23:59"))
    submit("asg11", "H", 2, 2, "2026-09-26", "20:00", "Model plus assumptions write-up.")
    assert g1.version_no == 1

    # ---- tests
    def add_test(code, title, kind, *, batch_row=batch, status, topic=None, duration=None, opens=None, closes=None, attempts=None, pass_marks=None,
                 required=None, reviewer="trainer_g1", question_keys=(), marks_override=None, approved=False, instructions=None):
        test = Test(test_code=code, batch_id=batch_row.batch_id, topic_id=ctx.topics[topic] if topic else None, title=title, kind=kind,
                    instructions=instructions, is_required=kind in ("Module test", "Coding exercise", "Final test") if required is None else required,
                    duration_minutes=duration, opens_at=opens, closes_at=closes, attempts_allowed=attempts, pass_marks=pass_marks,
                    release_status=status, approved_by=coord if approved else None, approved_at=at("2026-09-20", "12:00") if approved else None,
                    released_at=at("2026-09-20", "12:30") if status in ("Released", "Closed") else None,
                    reviewer_user_id=ctx.users[reviewer], created_by=ctx.users[reviewer])
        db.session.add(test)
        db.session.flush()
        for position, qkey in enumerate(question_keys, 1):
            q = questions[qkey]
            db.session.add(TestQuestion(test_id=test.test_id, question_id=q.question_id, position=position, question_version=q.version,
                                        question_type=q.question_type, stem=q.stem, options=q.options, answer_key=q.answer_key,
                                        marks=(marks_override or {}).get(qkey, q.marks)))
        db.session.flush()
        db.session.refresh(test)
        return test

    rules = "Answer every question. The timer runs on the server: closing the tab does not pause it."
    add_test("TST-0001", "Regression practice quiz", "Practice quiz", status="Released", duration=20, topic=(TRACK_ML, "Linear & Logistic Regression"),
             question_keys=("logistic", "slope", "metric", "regularisation"), instructions=rules)
    add_test("TST-0002", "Supervised Learning module test", "Module test", status="Released", duration=60, attempts=1, pass_marks=4,
             opens=at("2026-10-03", "10:00"), closes=at("2026-10-03", "13:00"), approved=True, reviewer="trainer_g2",
             question_keys=("metric", "regularisation", "logistic", "slope", "ensemble"), instructions=rules)
    sql_test = add_test("TST-0003", "SQL coding exercise", "Coding exercise", status="Released", duration=45, attempts=1, pass_marks=4,
                        opens=at("2026-09-25", "09:00"), closes=at("2026-09-27", "18:00"), approved=True,
                        question_keys=("dense_rank", "top_earner", "having"), instructions=rules)
    add_test("TST-0004", "Data Science mock test", "Mock test", status="Not Released", duration=90, attempts=1, question_keys=("metric", "slope", "set_len"))
    interview = add_test("TST-0005", "Mock interview — ML basics", "Mock interview", status="Released", duration=30, attempts=1, required=False,
                         instructions="A 30-minute practice interview. It carries no marks and does not promise placement.")
    add_test("TST-0006", "Final test — Track 1", "Final test", status="Configuration Pending", duration=120, attempts=1)
    python_test = add_test("TST-0007", "Python Foundations module test", "Module test", status="Released", duration=60, attempts=1, pass_marks=25,
                           opens=at("2026-09-20", "10:00"), closes=at("2026-09-22", "18:00"), approved=True,
                           question_keys=("logistic", "slope", "ensemble", "metric", "set_len", "regularisation"),
                           marks_override={"logistic": 10, "slope": 10, "ensemble": 10, "metric": 6, "set_len": 6, "regularisation": 8})
    add_test("TST-0008", "AWS final test paper", "Final test", batch_row=ctx.batches["V1"], status="Configuration Pending", duration=60, attempts=1,
             reviewer="trainer_v1")

    # ---- attempts: answers are stored while the attempt is open, then the real deadline and the receipt are set
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES ('RCPT-T', 930) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = 930"))

    def attempt(test, who, day, clock, answers, grades=None):
        enrolment = people[who]
        started = at(day, clock)
        row = TestAttempt(test_id=test.test_id, enrolment_id=enrolment.enrolment_id, student_id=enrolment.student_id, attempt_no=1,
                          started_at=started, deadline_at=datetime.now(IST) + timedelta(hours=1))
        db.session.add(row)
        db.session.flush()
        for qkey, value in answers.items():
            db.session.add(AttemptAnswer(attempt_id=row.attempt_id, question_id=questions[qkey].question_id, answer=value))
        db.session.flush()
        row.deadline_at = started + timedelta(minutes=test.duration_minutes)
        row.status, row.submit_reason, row.submitted_at = "Submitted", "Student", started + timedelta(minutes=test.duration_minutes - 11)
        db.session.flush()
        db.session.refresh(row)
        saved = {a.question_id: a for a in db.session.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == row.attempt_id)).scalars()}
        auto_total = manual_total = Decimal("0")
        for tq in test.questions:
            given = saved.get(tq.question_id)
            if given is None:
                given = AttemptAnswer(attempt_id=row.attempt_id, question_id=tq.question_id, answer=None)
                db.session.add(given)
            score = score_answer(tq.question_type, tq.answer_key, given.answer, tq.marks)
            if score is None:
                qkey = next(k for k, q in questions.items() if q.question_id == tq.question_id)
                given.awarded_marks = Decimal((grades or {}).get(qkey, 0))
                given.graded_by, given.graded_at = ctx.users["trainer_g1"], row.submitted_at + timedelta(days=1)
                given.grader_feedback = "Correct approach; check the empty-input case." if qkey in (grades or {}) else None
                manual_total += given.awarded_marks
            else:
                given.awarded_marks, given.is_auto_graded = score, True
                auto_total += score
        row.auto_score, row.total_score = auto_total, auto_total + manual_total
        row.grading_status, row.graded_by, row.graded_at = "Graded", ctx.users["trainer_g1"], row.submitted_at + timedelta(days=1)
        db.session.flush()
        return row

    def test_result(test, row, status="Provisional", published_day=None):
        db.session.add(Result(enrolment_id=row.enrolment_id, student_id=row.student_id, batch_id=test.batch_id, test_id=test.test_id,
                              attempt_id=row.attempt_id, max_marks=sum((q.marks for q in test.questions), Decimal("0")),
                              provisional_marks=row.total_score, status=status, final_marks=row.total_score if published_day else None,
                              published_by=coord if published_day else None, published_at=at(published_day, "11:00") if published_day else None))

    sql = "SELECT * FROM (SELECT *, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) r FROM emp) t WHERE r = 1"
    test_result(sql_test, attempt(sql_test, "anvitha", "2026-09-26", "10:00", {"dense_rank": "B", "top_earner": sql, "having": "having"},
                                  grades={"top_earner": 4}))
    test_result(sql_test, attempt(sql_test, "G", "2026-09-26", "11:30", {"dense_rank": "A", "top_earner": "SELECT max(salary) FROM emp", "having": "HAVING"},
                                  grades={"top_earner": 2}))
    test_result(sql_test, attempt(sql_test, "H", "2026-09-26", "14:00", {"dense_rank": "B", "top_earner": "window query", "having": "where"},
                                  grades={"top_earner": 4}))
    test_result(python_test, attempt(python_test, "anvitha", "2026-09-21", "10:30",
                                     {"logistic": True, "slope": 3, "ensemble": "Random forest", "metric": "B", "set_len": "2", "regularisation": ["A"]}),
                status="Published", published_day="2026-09-24")

    # ---- mock interview slots: Anvitha booked the first and waits for the trainer to confirm
    for day, clock, who in (("2026-10-02", "16:00", "anvitha"), ("2026-10-03", "16:00", None), ("2026-10-05", "11:00", None)):
        starts = at(day, clock)
        slot = InterviewSlot(test_id=interview.test_id, trainer_user_id=ctx.users["trainer_g1"], starts_at=starts, ends_at=starts + timedelta(minutes=30))
        if who:
            slot.status, slot.enrolment_id, slot.student_id = "Slot Confirmation Pending", people[who].enrolment_id, people[who].student_id
            slot.booked_at = at("2026-09-29", "18:00")
        db.session.add(slot)
    db.session.commit()


# Run in order; later slices append their own seeders here
SEEDERS: list[Callable[[SeedContext], None]] = [
    seed_staff,
    seed_courses,
    seed_curriculum,
    seed_batches,
    seed_students,
    seed_progress,
    seed_sessions,
    seed_finance,
    seed_crm_inbox_examples,
    seed_assessments,
]


@click.command("seed-dev")
@with_appcontext
def seed_dev_command() -> None:
    """Load staging data into the dev replica. Run right after `flask create-dev-db --yes`."""
    database = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"]).database
    if not database.endswith(("-dev", "_test")):
        raise click.ClickException(f"Refusing to seed '{database}': only *-dev and *_test databases can be seeded")
    if db.session.execute(select(User.user_id).limit(1)).first() is not None:
        raise click.ClickException(f"'{database}' already has users. Rebuild it first: flask --app app create-dev-db --yes")

    ctx = SeedContext(client=current_app.test_client())
    for seeder in SEEDERS:
        seeder(ctx)
        db.session.commit()
        click.echo(f"  {seeder.__name__.removeprefix('seed_')} done")

    student_count = db.session.execute(select(func.count()).select_from(Student)).scalar()
    click.echo(f"Seeded {len(STAFF)} staff, {student_count} students. Password for every account: {STAGING_PASSWORD}")
    click.echo(f"  Student login: {ctx.students['anvitha']['student_code']} (Anvitha K.)")
    for note in ctx.notes:
        click.echo(f"  {note}")

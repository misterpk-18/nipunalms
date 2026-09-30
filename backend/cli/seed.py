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
    ActivityEvent, AttendanceRecord, AttendanceRecovery, Batch, BatchEvent, BatchTrainer, Certificate, ClassSession, Course, CourseComponent,
    CurriculumEvent, CurriculumModule, CurriculumTopic, CurriculumVersion, Enrolment, MeetEvent, SessionChange, SessionChangeRequest, Student, User,
)
from repositories import batches as batches_repo
from repositories import users as users_repo
from services import certificates as certificates_service
from services import users as users_service

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
    ("K", "Sample Learner K.", "learner.k@example.test", GNT, "NIT-CRS-019", None, None),  # waits in the allocation queue for a Power BI batch
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

# Anvitha's finance summaries as the CRM would send them (admission_balances + installment_dues + verified receipts).
# Receipt numbers follow the collecting branch and the April–March financial year.
FINANCE = [
    ("CRM-ADM-214", dict(fee_total=45000, verified_paid=30000, balance=15000, next_due_date="2026-10-10", next_due_amount=15000,
                         pending_verification=0, payment_completion="Part Paid", invoice_numbers=["INV-GNT-2526-0214"],
                         installments=[{"installment_no": 1, "due_date": "2026-01-10", "amount": 15000, "covered": 15000, "balance": 0,
                                        "due_position": "Paid"},
                                       {"installment_no": 2, "due_date": "2026-04-10", "amount": 15000, "covered": 15000, "balance": 0,
                                        "due_position": "Paid"},
                                       {"installment_no": 3, "due_date": "2026-10-10", "amount": 15000, "covered": 0, "balance": 15000,
                                        "due_position": "Due soon"}],
                         receipts=[{"receipt_number": "GNT-R-2526-00148", "date": "2026-01-10", "amount": 15000},
                                   {"receipt_number": "GNT-R-2627-00031", "date": "2026-04-10", "amount": 15000}])),
    ("CRM-ADM-88", dict(fee_total=22000, verified_paid=22000, balance=0, next_due_date=None, next_due_amount=None,
                        pending_verification=0, payment_completion="Paid", invoice_numbers=["INV-GNT-2627-0088"],
                        installments=[{"installment_no": 1, "due_date": "2026-09-20", "amount": 22000, "covered": 22000, "balance": 0,
                                       "due_position": "Paid"}],
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
        "person": {"crm_person_id": person, "person_code": f"PER-{code}-{number:05d}", "full_name": name, "name_te": name_te,
                   "email": email, "phone": mobile, "preferred_language": "English"},
        "admission": {"crm_admission_id": f"CRM-ADM-{number}", "admission_code": f"NIT-{code}-2026-{number:06d}",
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

    # Sent the way the CRM sends it: its own field names and values (phone, English / Telugu, Online), one course per admission
    person = {"crm_person_id": ANVITHA["person"], "person_code": "PER-GNT-00148", "full_name": ANVITHA["name"],
              "name_te": ANVITHA["name_te"], "email": ANVITHA["email"], "phone": ANVITHA["mobile"], "preferred_language": "English"}
    combo = ctx.crm_event("AdmissionQualified", {
        "person": person,
        "admission": {"crm_admission_id": "CRM-ADM-214", "admission_code": "NIT-GNT-2026-000214", "course_code": "NIT-CRS-018",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT",
                      "delivery_mode": "Hybrid", "seat_type": "Confirmed Seat", "admission_date": "2026-01-10",
                      "crm_batch_id": "CRM-BAT-101"},
    })
    # The CRM grants a complimentary course as its own admission, linked to the paid one
    ctx.crm_event("AdmissionQualified", {
        "person": person,
        "admission": {"crm_admission_id": "CRM-ADM-215", "admission_code": "NIT-GNT-2026-000215", "course_code": "NIT-CRS-052",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT",
                      "delivery_mode": "Classroom", "admission_date": "2026-01-10",
                      "complimentary_of_crm_admission_id": "CRM-ADM-214", "access_until": "2027-01-09"},
    })
    aws = ctx.crm_event("AdmissionQualified", {
        "person": person,
        "admission": {"crm_admission_id": "CRM-ADM-88", "admission_code": "NIT-VIJ-2026-000088", "course_code": "NIT-CRS-007",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-VIJ", "collecting_branch_code": "NIT-GNT",
                      "delivery_mode": "Online", "seat_type": "Future Plan", "planned_start_date": "2026-09-30",
                      "admission_date": "2026-09-20"},
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


def seed_delivery(ctx: SeedContext) -> None:
    """S1 Delivery states: batch history, a curriculum draft in review, a rescheduled and a cancelled class, a failed Meet
    association, a trainer's open reschedule request, and the Meet association log of every online class."""
    for key, batch in ctx.batches.items():
        db.session.add(BatchEvent(batch_id=batch.batch_id, event_type="Created", to_value="Forming", actor_user_id=ctx.users["coord_gnt" if batch.branch_id == GNT else "coord_vij"],
                                  created_at=datetime.combine(BATCHES[key]["start"] - timedelta(days=30), time(10, 0), tzinfo=IST)))
        if batch.state != "Forming":
            db.session.add(BatchEvent(batch_id=batch.batch_id, event_type="State changed", from_value="Forming", to_value=batch.state,
                                      actor_user_id=ctx.users["coord_gnt" if batch.branch_id == GNT else "coord_vij"],
                                      created_at=datetime.combine(BATCHES[key]["start"], time(9, 0), tzinfo=IST)))

    # NIT-CRS-052: a draft submitted for review (still no Active version, so its enrolments stay in Curriculum Mapping Pending)
    course = db.session.execute(select(Course).where(Course.course_code == "NIT-CRS-052")).scalar_one()
    draft = CurriculumVersion(course_id=course.course_id, version_label="CV 3.0", status="Under Review")
    db.session.add(draft)
    db.session.flush()
    for order, (module_title, topics) in enumerate([("Python Foundations", ["Syntax & Data Types", "Functions & Modules"]),
                                                     ("Django & REST APIs", ["Models & ORM", "Views & Serializers", "Authentication"])], 1):
        module = CurriculumModule(curriculum_version_id=draft.curriculum_version_id, title=module_title, sort_order=order)
        db.session.add(module)
        db.session.flush()
        for topic_order, title in enumerate(topics, 1):
            db.session.add(CurriculumTopic(module_id=module.module_id, title=title, sort_order=topic_order))
    db.session.add(CurriculumEvent(curriculum_version_id=draft.curriculum_version_id, action="Created", to_status="Draft", actor_user_id=ctx.users["coord_gnt"]))
    db.session.add(CurriculumEvent(curriculum_version_id=draft.curriculum_version_id, action="Submitted", from_status="Draft", to_status="Under Review",
                                   actor_user_id=ctx.users["coord_gnt"]))

    def session_by_title(title: str) -> ClassSession:
        return db.session.execute(select(ClassSession).where(ClassSession.title == title)).scalar_one()

    # A rescheduled class (with 2 days' notice) and a cancelled one
    moved = session_by_title("Precision, recall and ROC")
    new_start = moved.starts_at + timedelta(days=1)
    db.session.add(SessionChange(session_id=moved.session_id, change_type="Rescheduled", reason="Trainer at a workshop on 8 Oct", old_starts_at=moved.starts_at,
                                 old_ends_at=moved.ends_at, new_starts_at=new_start, new_ends_at=new_start + (moved.ends_at - moved.starts_at),
                                 notice_hours=50, short_notice=False, changed_by=ctx.users["coord_gnt"], created_at=at("2026-09-28", "16:00")))
    moved.starts_at, moved.ends_at, moved.state = new_start, new_start + (moved.ends_at - moved.starts_at), "Rescheduled"
    cancelled = session_by_title("Capstone check-in")
    db.session.add(SessionChange(session_id=cancelled.session_id, change_type="Cancelled", reason="Institute closed for a local holiday", old_starts_at=cancelled.starts_at,
                                 old_ends_at=cancelled.ends_at, notice_hours=72, short_notice=False, changed_by=ctx.users["coord_vij"], created_at=at("2026-09-29", "12:00")))
    cancelled.state = "Cancelled"

    # An open request from Trainer R. Sample
    asked = session_by_title("Cross-validation workshop")
    proposed = asked.starts_at + timedelta(days=2)
    db.session.add(SessionChangeRequest(session_id=asked.session_id, requested_by=ctx.users["trainer_g1"], proposed_starts_at=proposed,
                                        proposed_ends_at=proposed + (asked.ends_at - asked.starts_at), reason="Lab is booked for an exam on 1 Oct"))

    # Meet: the Vijayawada organizer is unverified; one class failed its association
    failed = session_by_title("EC2 and VPC networking")
    failed.meet_status = "Unavailable"
    db.session.flush()
    for session in db.session.execute(select(ClassSession).where(ClassSession.meet_status != "Not Required").order_by(ClassSession.session_id)).scalars():
        mailbox = session.batch.branch.mailbox
        db.session.add(MeetEvent(session_id=session.session_id, event_type="Requested", meet_status="Pending Verification", organizer_email=mailbox,
                                 detail="Awaiting the organizer link", actor_user_id=ctx.users["coord_gnt" if session.batch.branch_id == GNT else "coord_vij"]))
        if session.meet_status == "Linked":
            db.session.add(MeetEvent(session_id=session.session_id, event_type="Link associated", meet_status="Linked", organizer_email=mailbox,
                                     meet_link=session.meet_link, detail="Entered manually", actor_user_id=ctx.users["coord_gnt"]))
        elif session.meet_status == "Unavailable":
            db.session.add(MeetEvent(session_id=session.session_id, event_type="Association failed", meet_status="Unavailable", organizer_email=mailbox,
                                     detail="Organizer account licence Pending Verification", actor_user_id=ctx.users["coord_vij"]))


def seed_finance(ctx: SeedContext) -> None:
    for crm_admission_id, summary in FINANCE:
        ctx.crm_event("FinanceSummaryUpdated", {"crm_admission_id": crm_admission_id, **summary}, version=2,
                      occurred_at="2026-09-28T18:00:00+05:30")


def seed_crm_inbox_examples(ctx: SeedContext) -> None:
    """Two events for the CRM sync monitor: one that could not be applied yet, one that arrived late and was ignored."""
    ctx.crm_event("AdmissionQualified", {
        "person": {"crm_person_id": "CRM-PER-9001", "full_name": "Sample Learner Z.", "mobile": "9876599001"},
        "admission": {"crm_admission_id": "CRM-ADM-999", "admission_code": "NIT-GNT-2026-000999", "course_code": "NIT-CRS-999",
                      "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT"},
        "enrolments": [{"course_code": "NIT-CRS-999"}],
    }, expect=(422,))
    ctx.crm_event("AdmissionUpdated", {"crm_admission_id": "CRM-ADM-214", "mode": "Hybrid"}, version=3)
    ctx.crm_event("AdmissionUpdated", {"crm_admission_id": "CRM-ADM-214", "mode": "Classroom"}, version=2)  # late: ignored


def seed_admin_readiness(ctx: SeedContext) -> None:
    """Readiness registers, staff and student account states for the admin screens, all through the admin API as the Super Admin.

    Nothing is Verified in the integrations register (the prototype: no successful evidence exists); the controls the
    platform already enforces are verified with evidence, the rest keep their migration status.
    """
    login = ctx.client.post(f"{API}/auth/login", json={"login": "admin@nipuna.test", "password": STAGING_PASSWORD})
    headers = {"Authorization": f"Bearer {login.get_json()['data']['token']}"}

    def call(method: str, path: str, body: dict | None = None) -> dict:
        response = getattr(ctx.client, method)(f"{API}{path}", headers=headers, json=body if body is not None else {})
        if response.status_code >= 400:
            raise click.ClickException(f"{method.upper()} {path} failed ({response.status_code}): {response.get_json()}")
        return response.get_json()["data"]

    integrations = {i["integration_code"]: i for i in call("get", "/integrations")}
    call("patch", f"/integrations/{integrations['GOOGLE_MEET']['integration_id']}",
         {"notes": "Organizer licences for both branch mailboxes are Pending Verification; nothing is Live Verified"})
    call("patch", f"/integrations/{integrations['CRM']['integration_id']}",
         {"notes": "Inbound events supported; outbound delivery worker not built yet (values are queued in the outbox)"})

    controls = {c["control_code"]: c for c in call("get", "/security-controls")}
    for code, evidence in (
        ("SESSION_IDLE", "Session unusable after 30 idle minutes in staging (checked 29 Sep 2026)"),
        ("SESSION_MAX", "Session ended at 12 hours in staging (checked 29 Sep 2026)"),
        ("LOGIN_LOCKOUT", "Account locked after 5 failed sign-ins and released after 15 minutes"),
        ("UNIQUE_LMS_LOGIN", "Second admission for the same CRM Person reused the existing Student ID"),
        ("AUDIT_IMMUTABLE", "UPDATE and DELETE on audit_log raise an error in staging"),
    ):
        call("patch", f"/security-controls/{controls[code]['control_id']}", {"verification_status": "Verified", "evidence": evidence})

    newjoin = call("post", "/admin/users", {"full_name": "Trainer A. Newjoin", "email": "trainer.new@nipuna.test",
                                            "scopes": [{"role_code": "TRAINER", "branch_id": GNT}]})
    ctx.notes.append(f"Trainer A. Newjoin (trainer.new@nipuna.test) must change the temporary password {newjoin['temporary_password']}")
    former = call("post", "/admin/users", {"full_name": "Former Trainer T. Sample", "email": "trainer.former@nipuna.test",
                                           "scopes": [{"role_code": "TRAINER", "branch_id": VIJ}]})
    call("post", f"/admin/users/{former['user_id']}/deactivate", {"reason": "Left the company on 15 Sep 2026"})

    call("post", f"/admin/students/{ctx.students['E']['student_id']}/suspend", {"reason": "Duplicate enrolment under review"})
# ---------------------------------------------------------------- slice S4: attendance, recovery, certificates

# Extra delivered classes of batch G1 before the prototype's August sessions (a batch that started in January has many more)
EARLIER_G1_SESSIONS = [
    (("Parent Programme v2026.1", "Programme Roadmap & Assessment Scheme"), "Programme orientation", "2026-07-27", "10:00", "12:00"),
    (("Track CV 3.2", "Functions & Modules"), "Functions and modules", "2026-07-29", "10:00", "12:00"),
    (("Parent Programme v2026.1", "Learning Tools Setup"), "Learning tools setup", "2026-08-05", "10:00", "12:00"),
]
# Absent class numbers (1 = oldest of the batch's 14 delivered classes) per learner of G1
G1_ABSENCES = {"anvitha": {6, 13}, "G": {2, 5, 7, 10}, "H": {8}, "I": set()}
STAFF_LOGINS = {"coord_gnt": "coordinator.gnt", "coord_vij": "coordinator.vij", "bm_gnt": "bm.gnt", "bm_vij": "bm.vij", "admin": "admin"}
# learner, certificate type, how far it goes in the register, the branch coordinator and manager who work it
CERTIFICATE_PLAN = [
    ("A", "Course Completion Certificate", "issued", "coord_gnt", "bm_gnt"),
    ("B", "Internship Certificate", "issued", "coord_vij", "bm_vij"),
    ("F", "Course Completion Certificate", "revoked", "coord_gnt", "bm_gnt"),
    ("C", "Course Completion Certificate", "eligibility", "coord_gnt", "bm_gnt"),
    ("D", "Internship Certificate", "awaiting", "coord_vij", "bm_vij"),
    ("E", "Course Completion Certificate", "approved", "coord_vij", "bm_vij"),
]


def _staff_call(ctx: SeedContext, staff_key: str, path: str, body: dict | None = None) -> dict:
    """POST as a staff member (real login, real permissions and audit)."""
    login = ctx.client.post(f"{API}/auth/login", json={"login": f"{STAFF_LOGINS[staff_key]}@nipuna.test", "password": STAGING_PASSWORD})
    headers = {"Authorization": f"Bearer {login.get_json()['data']['token']}"}
    response = ctx.client.post(f"{API}{path}", json=body or {}, headers=headers)
    if response.status_code not in (200, 201):
        raise click.ClickException(f"{path} failed ({response.status_code}): {response.get_json()}")
    return response.get_json()["data"]


def _enrolment_of(ctx: SeedContext, key: str, kind: str | None = None) -> Enrolment:
    enrolments = [db.session.get(Enrolment, e["enrolment_id"]) for e in ctx.students[key]["enrolments"]]
    return next(e for e in enrolments if kind is None or e.kind == kind)


def seed_attendance(ctx: SeedContext) -> None:
    """Trainer-confirmed attendance for batch G1 (REC-0041 included) and the eight prototype Certificate Register rows."""
    g1 = ctx.batches["G1"]
    for topic, title, day, start, end in EARLIER_G1_SESSIONS:
        db.session.add(ClassSession(batch_id=g1.batch_id, topic_id=ctx.topics[topic], title=title, starts_at=at(day, start),
                                    ends_at=at(day, end), mode="Classroom", trainer_user_id=ctx.users["trainer_g1"], room="Lab 1",
                                    state="Delivered", delivered_at=at(day, end)))
    db.session.flush()

    delivered = db.session.execute(select(ClassSession).where(ClassSession.batch_id == g1.batch_id, ClassSession.state == "Delivered")
                                   .order_by(ClassSession.starts_at)).scalars().all()
    absence_of_rec = None
    for key, absences in G1_ABSENCES.items():
        enrolment = _enrolment_of(ctx, key, "Combo" if key == "anvitha" else None)
        for number, session in enumerate(delivered, 1):
            if key == "I" and number == len(delivered):
                continue  # Learner I's last class is still unmarked: Partial Data
            status = "Absent" if number in absences else "Late" if key == "anvitha" and number == 4 else "Present"
            record = AttendanceRecord(session_id=session.session_id, enrolment_id=enrolment.enrolment_id, status=status,
                                      marked_by=session.trainer_user_id, marked_at=session.ends_at + timedelta(hours=1))
            db.session.add(record)
            db.session.flush()
            if key == "anvitha" and session.session_code == "SES-000101":
                absence_of_rec = record
    # The first recovery gets the prototype's code REC-0041
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES ('REC', 40) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = 40"))
    student_user = users_repo.get_by_student_id(ctx.students["anvitha"]["student_id"])
    db.session.add(AttendanceRecovery(
        attendance_id=absence_of_rec.attendance_id, method="Recording watched", status="Approved",
        reason="Was unwell on the day; will watch the recording and submit the regression exercise",
        requested_by=student_user.user_id, decided_by=ctx.users["coord_gnt"], decided_at=at("2026-09-22", "12:00"),
        decision_note="Approved: recording plus the regression exercise", target_date=date(2026, 10, 5)))
    db.session.commit()

    # Learners A-F have finished: each goes through the real completion review and register steps
    for key, kind, stage, coordinator, manager in CERTIFICATE_PLAN:
        enrolment = _enrolment_of(ctx, key)
        enrolment.status, enrolment.joining_date = "Active", enrolment.joining_date or date(2026, 3, 2)
        db.session.commit()
        if kind == "Internship Certificate":
            _staff_call(ctx, coordinator, "/certificates", {"enrolment_id": enrolment.enrolment_id, "certificate_type": kind})
        review = _staff_call(ctx, coordinator, "/completion-reviews", {"enrolment_id": enrolment.enrolment_id})
        _staff_call(ctx, coordinator, f"/completion-reviews/{review['review_id']}/decision", {"decision": "Complete"})
        cid = db.session.execute(select(Certificate.certificate_id).where(
            Certificate.enrolment_id == enrolment.enrolment_id, Certificate.certificate_type == kind)).scalar_one()
        if stage != "eligibility":
            _staff_call(ctx, coordinator, f"/certificates/{cid}/recommendation")
        if stage in ("approved", "issued", "revoked"):
            _staff_call(ctx, manager, f"/certificates/{cid}/approval")
        if stage in ("issued", "revoked"):
            _staff_call(ctx, manager, f"/certificates/{cid}/issue")
        if stage == "revoked":
            _staff_call(ctx, "admin", f"/certificates/{cid}/revocation", {"reason": "Record error: issued against the wrong enrolment"})
        if key == "A":
            _staff_call(ctx, manager, f"/certificates/{cid}/reissue", {"reason": "Name correction"})
    # Anvitha is still studying: her register entry waits as Not Yet Eligible
    certificates_service.ensure_register_entry(_enrolment_of(ctx, "anvitha", "Combo"))
    db.session.execute(text("UPDATE enrolments SET certificate_status = 'Configuration Pending — completion rule not configured "
                            "for complimentary offer' WHERE kind = 'Complimentary'"))


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
    seed_delivery,
    seed_attendance,
    seed_admin_readiness,  # last: it suspends a learner whose certificate the attendance seed works
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


# ---------------------------------------------------------------- S2 content & recordings

_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
_NOTEBOOK = b'{"cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# Sample notebook"]}], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}'
_CSV = b"area,bedrooms,price\n1200,2,5400000\n1500,3,7200000\n900,1,3100000\n"
_T2, _T1 = "Track CV 2.4", "Track CV 3.2"

# title, type, file name (None = a link), file bytes (or the link), topic (curriculum label, title), batch key, trainer, final state
CONTENT_ITEMS = [
    ("Regression notes", "PDF", "regression-notes.pdf", _PDF, (_T2, "Linear & Logistic Regression"), "G1", "trainer_g2", "Released"),
    ("housing.csv", "Dataset", "housing.csv", _CSV, (_T2, "Linear & Logistic Regression"), "G1", "trainer_g2", "Released"),
    ("SQL window functions cheatsheet", "Notes", "window-functions.md", b"# Window functions\n\nROW_NUMBER, RANK, LAG, LEAD\n",
     (_T1, "Joins, Window Functions"), "G1", "trainer_g1", "Released + v2 submitted"),
    ("starter_tree.py", "Code", "starter_tree.py", b"from sklearn.tree import DecisionTreeClassifier\n",
     (_T2, "Decision Trees & Ensembles"), "G1", "trainer_g2", "Released"),
    ("Practice set 3", "Practice material", "practice-set-3.pdf", _PDF, (_T2, "Linear & Logistic Regression"), "G1", "trainer_g2", "Released"),
    ("scikit-learn docs", "Link", None, b"https://scikit-learn.org/stable/documentation.html", (_T2, "Linear & Logistic Regression"), "G1",
     "trainer_g2", "Released"),
    ("AWS lab guide", "Lab", "aws-lab-guide.pdf", _PDF, ("CV 4.0", "EC2 & VPC Networking"), "V1", "trainer_v1", "Released"),
    ("AWS IAM lab", "Lab", "aws-iam-lab.pdf", _PDF, ("CV 4.0", "S3 & IAM Policies"), "V1", "trainer_v1", "Submitted"),
    ("Decision trees slides", "PDF", "decision-trees.pdf", _PDF, (_T2, "Decision Trees & Ensembles"), "G1", "trainer_g2", "Submitted"),
    ("Random forest lab", "Lab", "random-forest-lab.ipynb", _NOTEBOOK, (_T2, "Decision Trees & Ensembles"), "G1", "trainer_g2", "Changes Requested"),
    ("Regression walkthrough", "Code", "regression-walkthrough.ipynb", _NOTEBOOK, (_T2, "Linear & Logistic Regression"), "G1", "trainer_g2", "Draft"),
    ("Cross-validation cheatsheet", "PDF", "cross-validation.pdf", _PDF, (_T2, "Cross-validation & Metrics"), "G1", "trainer_g1", "Under Review"),
    ("Model evaluation notes", "PDF", "model-evaluation.pdf", _PDF, (_T2, "Cross-validation & Metrics"), "G1", "trainer_g1", "Approved"),
    ("Scraped customer dataset", "Dataset", "customers.csv", _CSV, (_T2, "Clustering (K-Means)"), "G1", "trainer_g2", "Rejected"),
    ("Old Pandas notes", "PDF", "pandas-notes.pdf", _PDF, (_T1, "Data Cleaning with Pandas"), "G1", "trainer_g1", "Retired"),
]


def _bearer(ctx: SeedContext, login: str) -> dict:
    response = ctx.client.post(f"{API}/auth/login", json={"login": login, "password": STAGING_PASSWORD})
    if response.status_code != 200:
        raise click.ClickException(f"Login failed for {login}: {response.get_json()}")
    return {"Authorization": f"Bearer {response.get_json()['data']['token']}"}


def _call(ctx: SeedContext, method: str, path: str, headers: dict, **kwargs) -> dict:
    response = getattr(ctx.client, method)(f"{API}{path}", headers=headers, **kwargs)
    if response.status_code >= 400:
        raise click.ClickException(f"{method.upper()} {path} failed ({response.status_code}): {response.get_json()}")
    return (response.get_json() or {}).get("data")


def seed_content_library(ctx: SeedContext) -> None:
    """Content in every review state, created and reviewed through the API as the trainers and coordinators."""
    from io import BytesIO

    heads = {key: _bearer(ctx, f"{login}@nipuna.test") for key, login in
             (("trainer_g1", "trainer.g1"), ("trainer_g2", "trainer.g2"), ("trainer_v1", "trainer.v1"))}
    coordinators = {GNT: _bearer(ctx, "coordinator.gnt@nipuna.test"), VIJ: _bearer(ctx, "coordinator.vij@nipuna.test")}
    for title, content_type, filename, content, topic, batch_key, trainer, state in CONTENT_ITEMS:
        batch = ctx.batches[batch_key]
        form = {"title": title, "content_type": content_type, "topic_id": str(ctx.topics[topic]), "batch_id": str(batch.batch_id)}
        if filename is None:
            form["url"] = content.decode()
        else:
            form["file"] = (BytesIO(content), filename)
        item = _call(ctx, "post", "/content-items", heads[trainer], data=form, content_type="multipart/form-data")
        path, coordinator = f"/content-items/{item['content_item_id']}", coordinators[batch.branch_id]
        if state == "Draft":
            continue
        _call(ctx, "post", f"{path}/submit", heads[trainer])
        if state == "Submitted":
            continue
        if state == "Under Review":
            _call(ctx, "post", f"{path}/review", coordinator, json={"decision": "start"})
        elif state == "Changes Requested":
            _call(ctx, "post", f"{path}/review", coordinator,
                  json={"decision": "request_changes", "comment": "Add the evaluation section and remove the hard-coded file path."})
        elif state == "Rejected":
            _call(ctx, "post", f"{path}/review", coordinator, json={"decision": "reject", "comment": "Contains personal data; anonymise it first."})
        else:
            _call(ctx, "post", f"{path}/review", coordinator, json={"decision": "approve", "release": state != "Approved", "comment": "Approved"})
        if state == "Retired":
            _call(ctx, "post", f"{path}/retire", coordinator, json={"reason": "Replaced by the Track CV 3.2 Pandas lab"})
        if state == "Released + v2 submitted":
            _call(ctx, "post", f"{path}/versions", heads[trainer], content_type="multipart/form-data",
                  data={"file": (BytesIO(b"# Window functions v2\n\nNTILE, FIRST_VALUE\n"), "window-functions-v2.md"),
                        "change_summary": "Added NTILE and FIRST_VALUE examples"})
            _call(ctx, "post", f"{path}/submit", heads[trainer])


def seed_recordings(ctx: SeedContext) -> None:
    """Recordings for the prototype sessions and exceptions RX-0012 to RX-0015 (raised through the same services)."""
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES ('RX', 11) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = 11"))
    db.session.commit()
    sessions = {s.session_code: s.session_id for s in db.session.execute(select(ClassSession)).scalars()}
    gnt, vij = _bearer(ctx, "coordinator.gnt@nipuna.test"), _bearer(ctx, "coordinator.vij@nipuna.test")
    trainer_v = _bearer(ctx, "trainer.v1@nipuna.test")

    def register(code: str, headers: dict, **body) -> int:
        return _call(ctx, "post", "/recordings", headers, json={"session_id": sessions[code], **body})["recording_id"]

    released = register("SES-000090", gnt, media_ref="drive:1Qa9-ses090", duration_minutes=120)
    _call(ctx, "post", f"/recordings/{released}/release", gnt)
    partial = register("SES-000101", gnt, media_ref="drive:1Qa9-ses101", duration_minutes=60)
    _call(ctx, "post", f"/recordings/{partial}/partial", gnt, json={"note": "second hour missing"})  # RX-0012
    held = register("SES-000102", gnt, media_ref="drive:1Qa9-ses102", duration_minutes=118)
    _call(ctx, "post", f"/recordings/{held}/hold", gnt, json={"reason": "whiteboard shows sample PII"})  # RX-0013
    register("SES-000103", gnt, status="Unavailable")
    register("SES-000104", gnt, status="Unavailable")
    register("SES-000201", vij, status="Unavailable")
    _call(ctx, "post", "/recording-exceptions", trainer_v, json={"session_id": sessions["SES-000201"], "issue_type": "Integration Unavailable",
                                                                  "issue": "Organizer account licence Pending Verification"})  # RX-0014
    register("SES-000095", vij, status="Unavailable")
    _call(ctx, "post", "/recording-exceptions", vij, json={"session_id": sessions["SES-000095"], "issue_type": "Unavailable",
                                                            "issue": "No recording mapped to actual Class Session"})  # RX-0015
    ctx.notes.append("Run `flask --app app jobs run recording-check` to flag the other delivered classes that have no recording yet")


def seed_access_extensions(ctx: SeedContext) -> None:
    """EXT-031 waiting, EXT-032 approved after the first expiry, EXT-033 after the second anniversary (needs an exception)."""
    db.session.execute(text("INSERT INTO code_counters (counter_key, last_value) VALUES ('EXT', 30) "
                            "ON CONFLICT (counter_key) DO UPDATE SET last_value = 30"))
    # Two completed learners get earlier Joining Dates so their first / second anniversaries have passed
    for key, joining in (("A", date(2025, 6, 10)), ("F", date(2024, 8, 19))):
        db.session.execute(text("UPDATE enrolments SET joining_date = :d WHERE student_id = :s"),
                           {"d": joining, "s": ctx.students[key]["student_id"]})
    db.session.commit()

    def ask(student_key: str, reason: str) -> dict:
        student = ctx.students[student_key]
        return _call(ctx, "post", "/access-extension-requests", _bearer(ctx, student["student_code"]),
                     json={"enrolment_id": student["enrolments"][0]["enrolment_id"], "scope": "Both", "reason": reason})

    ask("anvitha", "I would like to keep the recordings and notes for revision before interviews")  # EXT-031
    second = ask("A", "Preparing for a certification exam; the first year has ended")  # EXT-032
    _call(ctx, "post", f"/access-extension-requests/{second['request_id']}/decision", _bearer(ctx, "coordinator.gnt@nipuna.test"),
          json={"decision": "approve", "note": "Joining Date and history verified"})
    ask("F", "Returning to revise after the second anniversary")  # EXT-033

    for kind, detail in (("resource_view", {"item_code": "CNT-000001"}), ("recording_view", {"session_code": "SES-000090"})):
        db.session.add(ActivityEvent(student_id=ctx.students["anvitha"]["student_id"], kind=kind, detail=detail,
                                     occurred_at=datetime(2026, 9, 29, 19, 0, tzinfo=IST)))
    db.session.commit()


SEEDERS += [seed_content_library, seed_recordings, seed_access_extensions]

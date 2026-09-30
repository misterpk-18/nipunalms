"""A small Guntur world for the attendance / progress / completion / certificate tests.

Guntur batch B1 (NIT-CRS-047, curriculum CV 5.1 with three required topics) taught by trainer T1; student S1 and S2 are
allocated to it. Trainer T2 teaches another batch, AC / BM / admin cover Guntur, AC_V is a Vijayawada coordinator.
Sessions: `recent` (yesterday, inside the lock window), `older` (20 days ago, locked), `future` (Scheduled).
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from config.database import db
from config.timezone import IST
from models import CurriculumModule, CurriculumTopic, CurriculumVersion

API = "/api/v1"


def add_topics(version_label: str = "CV 5.1") -> list[int]:
    """Three required topics under two modules of the Active CV 5.1 version; returns the topic ids in order."""
    version = db.session.execute(select(CurriculumVersion).where(CurriculumVersion.version_label == version_label)).scalar_one()
    topic_ids = []
    for order, (module_title, titles) in enumerate([("Core Java", ["OOP", "Collections"]), ("Spring Boot", ["REST APIs"])], 1):
        module = CurriculumModule(curriculum_version_id=version.curriculum_version_id, title=module_title, sort_order=order)
        db.session.add(module)
        db.session.flush()
        for topic_order, title in enumerate(titles, 1):
            topic = CurriculumTopic(module_id=module.module_id, title=title, sort_order=topic_order)
            db.session.add(topic)
            db.session.flush()
            topic_ids.append(topic.topic_id)
    return topic_ids


def build(make_user, make_student, make_batch, make_session, allocate, login) -> SimpleNamespace:
    w = SimpleNamespace()
    w.t1 = make_user(roles=[("TRAINER", 1)], full_name="Trainer One")
    w.t2 = make_user(roles=[("TRAINER", 1)], full_name="Trainer Two")
    w.ac = make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="Coordinator Guntur")
    w.ac2 = make_user(roles=[("ACADEMIC_COORDINATOR", 1)], full_name="Second Coordinator")
    w.bm = make_user(roles=[("BRANCH_MANAGER", 1)], full_name="Manager Guntur")
    w.admin = make_user(roles=[("SUPER_ADMIN", None)], full_name="Admin")
    w.ac_v = make_user(roles=[("ACADEMIC_COORDINATOR", 2)], full_name="Coordinator Vijayawada")
    w.bm_v = make_user(roles=[("BRANCH_MANAGER", 2)], full_name="Manager Vijayawada")

    w.topics = add_topics()
    w.b1 = make_batch(1, trainers=[w.t1], state="Running")
    w.b2 = make_batch(1, trainers=[w.t2], state="Running")
    w.s1 = make_student(name="Anvitha K.")
    w.s2 = make_student(name="Learner Two")
    w.s3 = make_student(name="Other Batch Learner")
    allocate(w.s1, w.b1)
    allocate(w.s2, w.b1)
    allocate(w.s3, w.b2)

    def enrolment_id(student):
        return next(e["enrolment_id"] for e in student.enrolments)

    w.e1, w.e2, w.e3 = enrolment_id(w.s1), enrolment_id(w.s2), enrolment_id(w.s3)

    now = datetime.now(IST)
    w.recent_start = (now - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    w.older_start = (now - timedelta(days=20)).replace(hour=10, minute=0, second=0, microsecond=0)

    def delivered(start, topic=None, title="Delivered class"):
        return make_session(w.b1, w.t1, start, state="Delivered", delivered_at=start + timedelta(hours=2), topic_id=topic, title=title)

    w.recent = delivered(w.recent_start, w.topics[0], "Recent class")
    w.older = delivered(w.older_start, w.topics[1], "Older class")
    w.future = make_session(w.b1, w.t1, now + timedelta(days=3), title="Future class")
    w.delivered = delivered

    w.h = {name: login(getattr(w, name).email) for name in ("t1", "t2", "ac", "ac2", "bm", "admin", "ac_v", "bm_v", "s1", "s2", "s3")}
    return w

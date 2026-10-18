"""`flask seed-crm-batches`: real batches for the students the CRM has sent, so the CRM pull has batches to read (dev only).

`flask seed-dev` batches carry made-up CRM IDs and are hidden from the pull (seed_data). This command instead creates what a
Branch Manager would: one confirmed batch per course and branch that has students waiting for a batch, with a timetable, a
location and a lead trainer, plus a Branch Manager and a trainer login per branch. It allocates nobody: allocation stays a
Branch Manager's step on the "Waiting for a batch" screen. Running it again only adds what is missing.
"""
from datetime import date, time, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from cli.seed import STAGING_PASSWORD
from config.database import db
from models import Admission, Batch, BatchTrainer, Branch, Course, Enrolment, User
from services import batches as batches_service
from services import users as users_service

WAITING = "Allocation Pending"
WEEKS = 12
# Alternate two timetables across courses, so the batches of one branch don't all sit in one slot
TIMETABLES = (([1, 3, 5], time(10, 0), time(12, 0)), ([2, 4, 6], time(14, 0), time(16, 0)))


def _next_monday(today: date) -> date:
    return today + timedelta(days=7 - today.weekday() + 7)  # the Monday after next: time to allocate before it starts


def _staff(full_name: str, login: str, role_code: str, branch_id: int) -> tuple[int, bool]:
    email = f"{login}@nipuna.test"
    user_id = db.session.execute(select(User.user_id).where(func.lower(User.email) == email)).scalar_one_or_none()
    if user_id is not None:
        return user_id, False
    return users_service.create_staff_user(full_name, email, STAGING_PASSWORD, [(role_code, branch_id)]).user_id, True


@click.command("seed-crm-batches")
@with_appcontext
def seed_crm_batches_command() -> None:
    """Create a confirmed batch per course and branch with students waiting, and a Branch Manager and trainer per branch."""
    database = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"]).database
    if not database.endswith("-dev"):
        raise click.ClickException(f"Refusing to write to '{database}': only *-dev databases")

    waiting = db.session.execute(
        select(Enrolment.course_id, Enrolment.service_branch_id, func.count())
        .join(Admission, Admission.admission_id == Enrolment.admission_id)
        .where(Enrolment.status == WAITING, Admission.seed_data.is_(False))
        .group_by(Enrolment.course_id, Enrolment.service_branch_id)
        .order_by(Enrolment.service_branch_id, Enrolment.course_id)).all()
    if not waiting:
        raise click.ClickException("No enrolments are waiting for a batch. Has the CRM sent its admissions?")

    start = _next_monday(date.today())
    trainers: dict[int, int] = {}
    created_logins = []
    for branch_id in sorted({b for _, b, _ in waiting}):
        branch = db.session.get(Branch, branch_id)
        short = branch.branch_code.removeprefix("NIT-").lower()
        _, new_bm = _staff(f"Branch Manager ({branch.branch_name})", f"bm.{short}", "BRANCH_MANAGER", branch_id)
        trainers[branch_id], new_trainer = _staff(f"Trainer ({branch.branch_name})", f"trainer.{short}", "TRAINER", branch_id)
        created_logins += [f"bm.{short}@nipuna.test"] * new_bm + [f"trainer.{short}@nipuna.test"] * new_trainer

    made = []
    for index, (course_id, branch_id, count) in enumerate(waiting):
        exists = db.session.execute(select(Batch.batch_id).where(
            Batch.course_id == course_id, Batch.branch_id == branch_id, Batch.seed_data.is_(False),
            Batch.state.not_in(("Completed", "Cancelled", "Archived")))).first()
        if exists:
            continue
        course, branch = db.session.get(Course, course_id), db.session.get(Branch, branch_id)
        days, starts, ends = TIMETABLES[index % len(TIMETABLES)]
        batch = Batch(course_id=course_id, branch_id=branch_id, capacity=max(30, -(-(count + 5) // 5) * 5), mode="Classroom",
                      planned_start=start, planned_end=start + timedelta(weeks=WEEKS) - timedelta(days=3), state="Starting",
                      schedule_days=days, start_time=starts, end_time=ends,
                      location=f"Nipuna Technologies, {branch.branch_name}")
        db.session.add(batch)
        db.session.flush()
        db.session.add(BatchTrainer(batch_id=batch.batch_id, trainer_user_id=trainers[branch_id], role="Lead", from_date=start))
        db.session.flush()
        db.session.refresh(batch)
        suggestion = batches_service.suggested_readiness(batch, batches_service.readiness_checks(batch, 0))
        batch.readiness, batch.readiness_reason, batch.recovery_owner = (
            suggestion["readiness"], suggestion["readiness_reason"], suggestion["recovery_owner"])
        made.append((batch, course, branch, count))
    db.session.commit()

    for batch, course, branch, count in made:
        click.echo(f"  {batch.batch_code}  {course.course_code} at {branch.branch_code}: {count} waiting, "
                   f"{batch.capacity} seats, {batch.readiness}" + (f" ({batch.readiness_reason})" if batch.readiness_reason else ""))
    click.echo(f"Created {len(made)} batches starting {start:%d %b %Y}; nobody is allocated.")
    if created_logins:
        click.echo(f"New logins ({STAGING_PASSWORD}): " + ", ".join(created_logins))

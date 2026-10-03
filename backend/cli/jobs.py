"""flask --app app jobs run [NAME ...]: run background jobs (all by default). Schedule with cron, e.g. every 30 minutes."""
from datetime import datetime, timezone

import click
from flask.cli import AppGroup

from config.database import db
from models import JobRun
from services.jobs import JOBS

jobs_cli = AppGroup("jobs", help="Background jobs: recording check, support escalation, allocation escalation.")


@jobs_cli.command("list")
def list_jobs() -> None:
    """Show the available jobs."""
    for name, job in JOBS.items():
        click.echo(f"{name:18} {((job.__doc__ or '').strip().splitlines() or [''])[0]}")


@jobs_cli.command("run")
@click.argument("names", nargs=-1)
def run_jobs(names: tuple[str, ...]) -> None:
    """Run the named jobs (or all). Each job commits on its own, so one failure doesn't undo the others."""
    unknown = set(names) - set(JOBS)
    if unknown:
        raise click.BadParameter(f"Unknown job(s): {', '.join(sorted(unknown))}. See `flask jobs list`.")
    failed = False
    for name in names or JOBS:
        started = datetime.now(timezone.utc)
        try:
            result = JOBS[name]()
            _record_run(name, started, result=str(result))
            db.session.commit()
            click.echo(f"{name}: {result}")
        except Exception as exc:
            db.session.rollback()
            failed = True
            _record_run(name, started, error=str(exc)[:2000])
            db.session.commit()
            click.echo(f"{name}: FAILED ({exc})", err=True)
    if failed:
        raise SystemExit(1)


def _record_run(name: str, started: datetime, *, result: str | None = None, error: str | None = None) -> None:
    """When the job last ran and last succeeded (shown on the Meet operations view as the reconciliation time)."""
    run = db.session.get(JobRun, name) or JobRun(job_name=name, last_started_at=started)
    run.last_started_at, run.last_finished_at = started, datetime.now(timezone.utc)
    if error is None:
        run.last_ok_at, run.last_result, run.last_error = run.last_finished_at, result, None
    else:
        run.last_error = error
    db.session.add(run)

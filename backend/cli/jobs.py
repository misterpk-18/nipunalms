"""flask --app app jobs run [NAME ...]: run background jobs (all by default). Schedule with cron, e.g. every 30 minutes.
Locally, `jobs run --loop` stands in for cron."""
import time
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
@click.option("--loop", is_flag=True, help="Keep running until stopped (Ctrl+C), in place of cron for local use.")
@click.option("--interval", default=60, show_default=True, help="Seconds between runs with --loop.")
def run_jobs(names: tuple[str, ...], loop: bool, interval: int) -> None:
    """Run the named jobs (or all). Each job commits on its own, so one failure doesn't undo the others."""
    unknown = set(names) - set(JOBS)
    if unknown:
        raise click.BadParameter(f"Unknown job(s): {', '.join(sorted(unknown))}. See `flask jobs list`.")
    if not loop:
        if _run_once(names or tuple(JOBS)):
            raise SystemExit(1)
        return
    while True:  # a failed job is logged and retried on the next run, like cron would
        click.echo(f"-- {datetime.now().astimezone():%Y-%m-%d %H:%M:%S}")
        _run_once(names or tuple(JOBS))
        db.session.remove()
        time.sleep(interval)


def _run_once(names: tuple[str, ...]) -> bool:
    """Run each job once; True when any of them failed."""
    failed = False
    for name in names:
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
    return failed


def _record_run(name: str, started: datetime, *, result: str | None = None, error: str | None = None) -> None:
    """When the job last ran and last succeeded (shown on the Meet operations view as the reconciliation time)."""
    run = db.session.get(JobRun, name) or JobRun(job_name=name, last_started_at=started)
    run.last_started_at, run.last_finished_at = started, datetime.now(timezone.utc)
    if error is None:
        run.last_ok_at, run.last_result, run.last_error = run.last_finished_at, result, None
    else:
        run.last_error = error
    db.session.add(run)

"""flask --app app google check | send-test: try the Google connection before switching anything on."""
import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext

from repositories import google as google_repo
from services import integrations
from services.google import check as google_check
from services.google import gmail
from services.google.client import GoogleError

google_cli = AppGroup("google", help="Check the Google Workspace connection (docs/GOOGLE_WORKSPACE.md).")


def _mailbox(mailbox: str | None, branch: int | None) -> str | None:
    if mailbox:
        return mailbox
    return google_repo.branch_mailbox(branch) if branch else None


@google_cli.command("check")
@click.option("--mailbox", help="The mailbox to act as (default: GOOGLE_DELEGATED_ADMIN)")
@click.option("--branch", type=int, help="Use this branch's calendar mailbox")
@with_appcontext
def check_command(mailbox: str | None, branch: int | None) -> None:
    """Read-only checks: key, delegation for each scope, then a read of the mailbox's calendar and Drive. Exit 1 if any fail."""
    results = google_check.run(_mailbox(mailbox, branch))
    for result in results:
        click.echo(f"{'ok  ' if result.ok else 'FAIL'}  {result.name}: {result.detail}")
        if not result.ok and result.hint:
            click.echo(f"      -> {result.hint}")
    click.echo("")
    for code in ("GOOGLE_MEET", "GOOGLE_DRIVE", "EMAIL"):
        status = integrations.integration_status(code)
        click.echo(f"Register {code}: {status.configuration_status}, {status.verification_status}")
    if all(r.ok for r in results):
        click.echo("\nThe connection works. Next: mark each feature Working in Setup & health, with a note of how you checked it.")
    else:
        raise SystemExit(1)


@google_cli.command("send-test")
@click.option("--to", "to", required=True, help="Who to send one test email to")
@click.option("--mailbox", help="Send from this mailbox (default: GOOGLE_DELEGATED_ADMIN)")
@click.option("--branch", type=int, help="Send from this branch's email sender")
@with_appcontext
def send_test_command(to: str, mailbox: str | None, branch: int | None) -> None:
    """Send one plain test email through Gmail. This really sends: use your own address."""
    sender = mailbox or (google_repo.gmail_sender(branch) if branch else None) or current_app.config.get("GOOGLE_DELEGATED_ADMIN")
    if not sender:
        raise click.UsageError("No sender: set GOOGLE_DELEGATED_ADMIN or pass --mailbox")
    try:
        message_id = gmail.send(sender, to, "Nipuna LMS: Gmail test", "This is a test message from the Nipuna LMS. Nothing needs doing.")
    except GoogleError as exc:
        click.echo(f"FAIL  {exc}", err=True)
        raise SystemExit(1) from exc
    click.echo(f"Sent from {sender} to {to} (Gmail message {message_id}).")

"""flask --app app whatsapp status | list: the WhatsApp outbox (messages handed to the CRM)."""
import click
from flask.cli import with_appcontext

from models.whatsapp import WHATSAPP_STATUSES
from repositories import whatsapp as whatsapp_repo
from services import whatsapp


@click.group("whatsapp")
def whatsapp_cli() -> None:
    """WhatsApp messages the LMS sends through the CRM."""


@whatsapp_cli.command("status")
@with_appcontext
def status_command() -> None:
    """Why messages are or are not going out, and how many are in each state."""
    current = whatsapp.status()
    click.echo(f"State: {current['state']}")
    click.echo(f"Approved templates: {', '.join(current['approved_templates']) or 'none'}")
    click.echo("Messages: " + (", ".join(f"{k} {v}" for k, v in sorted(current["counts"].items())) or "none"))


@whatsapp_cli.command("list")
@click.option("--status", type=click.Choice(WHATSAPP_STATUSES), help="Only messages in this state")
@click.option("--limit", default=50, show_default=True)
@with_appcontext
def list_command(status: str | None, limit: int) -> None:
    rows = whatsapp_repo.list_messages(status, limit)
    if not rows:
        click.echo("The WhatsApp outbox is empty.")
    for row in rows:
        click.echo(f"{row.outbox_id:>5}  {row.status:<8} {row.template_name:<44} {row.created_at:%Y-%m-%d %H:%M}  {row.status_note or ''}")

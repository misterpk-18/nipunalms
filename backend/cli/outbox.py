"""flask --app app crm-outbox list: what is queued for the CRM (values it stores about the LMS)."""
import click
from flask.cli import with_appcontext

from models.enums import OUTBOX_STATUSES
from repositories import crm as crm_repo


@click.group("crm-outbox")
def crm_outbox_cli() -> None:
    """The outbox of LmsAccountProvisioned / AdmissionLmsStatusChanged / BatchLinked events (no delivery worker yet)."""


@crm_outbox_cli.command("list")
@click.option("--status", type=click.Choice(OUTBOX_STATUSES), help="Only rows with this status")
@click.option("--limit", default=50, show_default=True)
@with_appcontext
def list_outbox_command(status: str | None, limit: int) -> None:
    rows = crm_repo.list_outbox(status, limit)
    if not rows:
        click.echo("Outbox is empty.")
    for row in rows:
        click.echo(f"{row.outbox_id:>5}  {row.status:<9} {row.event_type:<26} {row.created_at:%Y-%m-%d %H:%M:%S}  {row.payload}")

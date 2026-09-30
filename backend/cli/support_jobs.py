"""flask --app app support-escalate-overdue: the job that escalates support requests past their SLA to the Branch Manager."""
import click
from flask.cli import with_appcontext

from config.database import db
from services import support as support_service


@click.command("support-escalate-overdue")
@with_appcontext
def support_escalate_overdue_command() -> None:
    """Escalate every open support request past its SLA (app_settings.support_sla_hours) to the Branch Manager."""
    count = support_service.escalate_overdue()
    db.session.commit()
    click.echo(f"Escalated {count} overdue support request(s)")

"""Flask CLI commands (run from backend/: flask --app app <command>)."""
from flask import Flask

from cli.api_http import api_http_command
from cli.cartograph import cartograph_cli
from cli.crm_batches import seed_crm_batches_command
from cli.database import create_dev_db_command, create_test_db_command
from cli.google import google_cli
from cli.jobs import jobs_cli
from cli.outbox import crm_outbox_cli
from cli.seed import seed_dev_command
from cli.uploads import uploads_cli
from cli.users import create_admin_command
from cli.whatsapp import whatsapp_cli


def register_cli(app: Flask) -> None:
    app.cli.add_command(create_test_db_command)
    app.cli.add_command(create_dev_db_command)
    app.cli.add_command(seed_dev_command)
    app.cli.add_command(seed_crm_batches_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(crm_outbox_cli)
    app.cli.add_command(api_http_command)
    app.cli.add_command(jobs_cli)
    app.cli.add_command(google_cli)
    app.cli.add_command(whatsapp_cli)
    app.cli.add_command(cartograph_cli)
    app.cli.add_command(uploads_cli)

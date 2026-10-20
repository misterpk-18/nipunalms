"""flask --app app uploads migrate [--apply] [--delete-local]: copy files from UPLOAD_DIR into the S3 bucket of this environment."""
import click
from flask import current_app
from flask.cli import AppGroup

from services import storage

uploads_cli = AppGroup("uploads", help="Uploaded files: move local files to the S3 bucket.")


@uploads_cli.command("migrate")
@click.option("--apply", is_flag=True, help="Upload for real. Without it nothing is changed: it only lists what would be copied.")
@click.option("--delete-local", is_flag=True, help="With --apply: remove each local file once it is confirmed in the bucket.")
def migrate(apply: bool, delete_local: bool) -> None:
    """Copy every file under UPLOAD_DIR that is not yet in the bucket. Keys stay the same, so the database needs no change."""
    if not storage.uses_s3():
        raise click.ClickException("STORAGE_BACKEND is not s3; set it (and S3_BUCKET) first.")
    root = current_app.config["UPLOAD_DIR"]
    keys = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and not path.name.startswith("."))
    click.echo(f"{len(keys)} local files; bucket {current_app.config['S3_BUCKET']}" + ("" if apply else " (dry run, use --apply)"))
    copied = skipped = 0
    for key in keys:
        if storage.in_bucket(key):
            skipped += 1
        elif apply:
            storage.copy_local_to_bucket(key)
            copied += 1
        else:
            copied += 1
            click.echo(f"  would copy {key}")
            continue
        if apply and delete_local and storage.in_bucket(key):
            (root / key).unlink()
    click.echo(f"{'copied' if apply else 'would copy'} {copied}, already in the bucket {skipped}")

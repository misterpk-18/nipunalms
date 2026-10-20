"""Where uploaded files live: local disk under UPLOAD_DIR, or an S3 bucket (STORAGE_BACKEND=s3).

Every file has a key relative to the storage root (`content/ab12-notes.pdf`, `cv/7/…`); that key is what the database keeps.
Callers stage a file under UPLOAD_DIR as before, then `publish` it (S3: uploaded and the staged copy removed). `resolve` gives back a
local path to serve; for S3 the object is fetched once into a cache folder. While moving to S3, a key that is not in the bucket
but still exists on local disk is served from disk.
"""
import mimetypes
import tempfile
from pathlib import Path

from flask import current_app

from services.errors import NotFound

_client = None


def uses_s3() -> bool:
    return current_app.config.get("STORAGE_BACKEND") == "s3"


def _s3():
    global _client
    if _client is None:
        import boto3

        config = current_app.config
        _client = boto3.client(
            "s3", region_name=config["AWS_REGION"],
            aws_access_key_id=config.get("AWS_ACCESS_KEY") or None, aws_secret_access_key=config.get("AWS_SECRET_KEY") or None,
        )
    return _client


def _bucket() -> str:
    return current_app.config["S3_BUCKET"]


def _root() -> Path:
    return Path(current_app.config["UPLOAD_DIR"])


def _cache_path(key: str) -> Path:
    return Path(tempfile.gettempdir()) / "nipunalms-s3-cache" / _bucket() / key


def _local(key: str) -> Path | None:
    """The file on local disk, or None; the key must stay inside UPLOAD_DIR."""
    target = (_root() / key).resolve()
    if _root().resolve() not in target.parents or not target.is_file():
        return None
    return target


def staging_path(key: str) -> Path:
    """Where to write a new file before publishing it."""
    target = _root() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def publish(key: str) -> None:
    """Make the staged file at `key` permanent. Local: nothing to do. S3: upload it, then drop the staged copy."""
    if not uses_s3():
        return
    path = _root() / key
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    _s3().upload_file(str(path), _bucket(), key, ExtraArgs={"ContentType": content_type})
    path.unlink(missing_ok=True)


def in_bucket(key: str) -> bool:
    try:
        _s3().head_object(Bucket=_bucket(), Key=key)
        return True
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def copy_local_to_bucket(key: str) -> None:
    """Upload the file at `key` under UPLOAD_DIR and keep the local copy (publish() would remove it)."""
    _s3().upload_file(str(_root() / key), _bucket(), key, ExtraArgs={"ContentType": mimetypes.guess_type(key)[0] or "application/octet-stream"})


def put_bytes(key: str, content: bytes) -> None:
    staging_path(key).write_bytes(content)
    publish(key)


def delete(key: str) -> None:
    if uses_s3():
        _s3().delete_object(Bucket=_bucket(), Key=key)
        _cache_path(key).unlink(missing_ok=True)
    (_root() / key).unlink(missing_ok=True)


def resolve(key: str) -> Path:
    """A local path to the file; 404 if it is gone. Keys come from the database, never from a request."""
    if uses_s3():
        cached = _cache_path(key)
        if cached.is_file():
            return cached
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            partial = cached.with_name(cached.name + ".part")
            _s3().download_file(_bucket(), key, str(partial))
            partial.replace(cached)
            return cached
        except Exception as error:  # botocore ClientError: 404 / NoSuchKey; anything else is also "not available"
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code not in ("404", "NoSuchKey", "NotFound"):
                current_app.logger.warning("S3 fetch of %s failed: %s", key, error)
    local = _local(key)
    if local is None:
        raise NotFound("The file is not available")
    return local

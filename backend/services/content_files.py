"""Files behind content versions: local disk under UPLOAD_DIR (object storage later).

Uploads are checked before they are kept: extension allow-list, size limit per kind (ordinary file / dataset or archive),
a magic-number check of the formats that have one, and a safe-archive inspection for ZIP files (no unsafe paths, no
nested archives, no executables, bounded expansion). Uploaded code and notebooks are stored and served, never executed.
Malware scanning is not available yet (see docs/BACKLOG.md).
"""
import json
import mimetypes
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from repositories import settings as settings_repo
from services.errors import NotFound, ValidationError

DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "md", "png", "jpg", "jpeg", "gif"}
CODE_EXTENSIONS = {"py", "ipynb", "sql", "java", "js", "ts", "json", "sh", "html", "css", "yml", "yaml"}
DATASET_EXTENSIONS = {"csv", "tsv", "parquet", "xlsx"}
ARCHIVE_EXTENSIONS = {"zip"}
ALLOWED_EXTENSIONS = DOCUMENT_EXTENSIONS | CODE_EXTENSIONS | DATASET_EXTENSIONS | ARCHIVE_EXTENSIONS
LARGE_EXTENSIONS = DATASET_EXTENSIONS | ARCHIVE_EXTENSIONS  # get the dataset limit
# Shown in the browser; everything else is only ever served as a download
INLINE_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "txt", "md", "csv"}
UNSAFE_ARCHIVE_MEMBERS = {"exe", "dll", "bat", "cmd", "com", "scr", "msi", "jar", "app", "dmg", "sh", "ps1", "vbs"}
NESTED_ARCHIVES = {"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz"}
MAX_ARCHIVE_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_RATIO = 100
MAGIC = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "zip": (b"PK\x03\x04", b"PK\x05\x06"),
    "docx": (b"PK\x03\x04",),
    "pptx": (b"PK\x03\x04",),
    "xlsx": (b"PK\x03\x04",),
    "doc": (b"\xd0\xcf\x11\xe0",),
    "ppt": (b"\xd0\xcf\x11\xe0",),
    "xls": (b"\xd0\xcf\x11\xe0",),
}


@dataclass(frozen=True)
class StoredFile:
    file_path: str
    original_filename: str
    mime_type: str
    file_size_bytes: int


def max_upload_bytes() -> int:
    """The largest upload accepted at all (the dataset limit); the request must be allowed this much."""
    return settings_repo.get_int("content_dataset_max_upload_mb", 250) * 1024 * 1024


def _limit_bytes(extension: str) -> int:
    key = "content_dataset_max_upload_mb" if extension in LARGE_EXTENSIONS else "content_max_upload_mb"
    return settings_repo.get_int(key, 250 if extension in LARGE_EXTENSIONS else 50) * 1024 * 1024


def _root() -> Path:
    return Path(current_app.config["UPLOAD_DIR"])


def _fail(message: str, field: str = "file") -> ValidationError:
    return ValidationError(message, {field: [message]})


def save_content_file(upload: FileStorage, folder: str = "content") -> StoredFile:
    """Validate and keep an uploaded content file; returns where it is and what it is."""
    name = secure_filename(upload.filename or "")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise _fail(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    relative = Path(folder) / f"{secrets.token_hex(8)}-{name}"
    target = _root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    upload.save(target)
    try:
        size = target.stat().st_size
        if size == 0:
            raise _fail("The file is empty")
        limit = _limit_bytes(extension)
        if size > limit:
            raise _fail(f"The file is larger than the {limit // (1024 * 1024)} MB limit for this kind of file")
        _check_contents(target, extension)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return StoredFile(str(relative), upload.filename or name, mime_type, size)


def _check_contents(path: Path, extension: str) -> None:
    with path.open("rb") as handle:
        head = handle.read(16)
    signatures = MAGIC.get(extension)
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise _fail(f"The file does not look like a real .{extension} file")
    if extension == "ipynb":
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _fail("The notebook is not valid JSON") from None
        if not isinstance(notebook, dict) or "cells" not in notebook:
            raise _fail("The notebook has no cells")
    if extension == "zip":
        _inspect_archive(path)


def _inspect_archive(path: Path) -> None:
    """Reject archives with unsafe paths, nested archives, executables, or an implausible expanded size."""
    try:
        with zipfile.ZipFile(path) as archive:
            expanded = 0
            for info in archive.infolist():
                member = PurePosixPath(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts or (member.parts and ":" in member.parts[0]):
                    raise _fail("The archive contains an unsafe file path")
                if info.is_dir():
                    continue
                member_ext = member.suffix.lstrip(".").lower()
                if member_ext in UNSAFE_ARCHIVE_MEMBERS:
                    raise _fail(f"The archive contains a file type that is not allowed (.{member_ext})")
                if member_ext in NESTED_ARCHIVES:
                    raise _fail("Archives inside archives are not allowed")
                expanded += info.file_size
                if info.compress_size and info.file_size / info.compress_size > MAX_ARCHIVE_RATIO:
                    raise _fail("The archive expands far more than a normal file would")
            if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                raise _fail("The archive is too large once expanded")
    except zipfile.BadZipFile:
        raise _fail("The archive is damaged") from None


def delete_file(relative_path: str) -> None:
    (_root() / relative_path).unlink(missing_ok=True)


def resolve(relative_path: str) -> Path:
    """The file on disk; 404 if it went missing. Paths come from the database, never from a request."""
    target = (_root() / relative_path).resolve()
    if _root().resolve() not in target.parents or not target.is_file():
        raise NotFound("The file is not available")
    return target


def is_inline(filename: str | None) -> bool:
    """May this file be shown in the browser (rather than only downloaded)?"""
    extension = (filename or "").rsplit(".", 1)[-1].lower()
    return extension in INLINE_EXTENSIONS

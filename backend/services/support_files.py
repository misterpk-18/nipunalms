"""Files attached to support messages: local disk under UPLOAD_DIR/support (object storage later), like CV files.

A screenshot or a document is enough to explain a problem, so the allow-list is short (images, PDF, plain text, Word), each file
is limited to 5 MB and a message carries at most 3. The first bytes must match the file type (a renamed program is refused).
Ownership is not decided here: the support service checks that the person may see the request before a file is served.
"""
import mimetypes
import secrets
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services import content_files, storage
from services.errors import ValidationError

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "txt", "doc", "docx"}
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_MESSAGE = 3


def _fail(message: str) -> ValidationError:
    return ValidationError(message, {"files": [message]})


def check_count(uploads: list[FileStorage]) -> list[FileStorage]:
    """The chosen files without blank form parts; at most MAX_FILES_PER_MESSAGE."""
    chosen = [u for u in uploads if u and u.filename]
    if len(chosen) > MAX_FILES_PER_MESSAGE:
        raise _fail(f"Attach at most {MAX_FILES_PER_MESSAGE} files")
    return chosen


def validate(upload: FileStorage) -> tuple[str, str, bytes]:
    """(safe name, extension, content) of a file that may be attached; raises a 400 explaining what is wrong."""
    name = secure_filename(upload.filename or "")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise _fail(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    content = upload.read(MAX_BYTES + 1)
    if not content:
        raise _fail("The file is empty")
    if len(content) > MAX_BYTES:
        raise _fail(f"The file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    signatures = content_files.MAGIC.get(extension)
    if signatures and not any(content.startswith(sig) for sig in signatures):
        raise _fail(f"The file does not look like a real .{extension} file")
    if extension == "txt" and b"\x00" in content:
        raise _fail("The file does not look like a text file")
    return name, extension, content


def store(upload: FileStorage, support_request_id: int, name: str, content: bytes) -> dict:
    """Keep a validated file. Returns file_path, original_filename, mime_type and file_size_bytes."""
    relative = Path("support") / str(support_request_id) / f"{secrets.token_hex(8)}-{name}"
    storage.put_bytes(str(relative), content)
    return {"file_path": str(relative), "original_filename": upload.filename or name,
            "mime_type": mimetypes.guess_type(name)[0] or "application/octet-stream", "file_size_bytes": len(content)}


def resolve(relative_path: str) -> Path:
    return content_files.resolve(relative_path)


def delete(relative_path: str) -> None:
    content_files.delete_file(relative_path)

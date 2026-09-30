"""Storage for CV files: local disk under UPLOAD_DIR/cv (object storage later). Returns a path relative to UPLOAD_DIR."""
import secrets
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.errors import NotFound, ValidationError

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
MAX_CV_BYTES = 5 * 1024 * 1024


def save_cv(upload: FileStorage | None, student_id: int) -> dict:
    """Validate and store an uploaded CV. Returns file_path, original_filename, mime_type and file_size_bytes."""
    if upload is None or not upload.filename:
        raise ValidationError("Choose a CV file", {"file": ["Required"]})
    name = secure_filename(upload.filename)
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("File type not allowed", {"file": [f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"]})
    content = upload.read()
    if not content:
        raise ValidationError("The file is empty", {"file": ["Empty file"]})
    if len(content) > MAX_CV_BYTES:
        raise ValidationError("The file is too large", {"file": [f"At most {MAX_CV_BYTES // (1024 * 1024)} MB"]})

    relative = Path("cv") / str(student_id) / f"{secrets.token_hex(8)}-{name}"
    target = Path(current_app.config["UPLOAD_DIR"]) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {"file_path": str(relative), "original_filename": upload.filename, "mime_type": upload.mimetype,
            "file_size_bytes": len(content)}


def absolute_path(relative_path: str) -> Path:
    """The stored file; 404 when it is missing from disk."""
    path = Path(current_app.config["UPLOAD_DIR"]) / relative_path
    if not path.is_file():
        raise NotFound("The CV file is not available")
    return path

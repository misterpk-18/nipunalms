"""Calls to Google as a Workspace mailbox, using one service account with domain-wide delegation.

The key comes from Secret Manager (GOOGLE_SA_SECRET_NAME) or a local file (GOOGLE_SA_KEY_FILE). Every call names the mailbox it
acts as (`subject`). Nothing else in the LMS imports a Google library; tests replace `request` and never reach Google.
"""
import base64
import json
import logging
from pathlib import Path
from urllib.parse import urlencode

import google.auth
import urllib3
from flask import current_app
import google.auth.transport.urllib3
from google.auth.transport.urllib3 import AuthorizedHttp
from google.oauth2 import service_account

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
SECRET_MANAGER_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

_key_cache: dict[str, dict] = {}


class GoogleError(Exception):
    """A Google call failed. `retryable` is True for a timeout, 429 and 5xx; everything else will fail the same way again."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.retryable = status, retryable


def _key_file() -> Path | None:
    value = current_app.config.get("GOOGLE_SA_KEY_FILE")
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def is_configured() -> bool:
    """A key is available (a Secret Manager name, or a key file that exists) and a mailbox to act as when none is named."""
    if not current_app.config.get("GOOGLE_DELEGATED_ADMIN"):
        return False
    if current_app.config.get("GOOGLE_SA_SECRET_NAME"):
        return True
    key_file = _key_file()
    return key_file is not None and key_file.is_file()


def _load_key() -> dict:
    secret_name = current_app.config.get("GOOGLE_SA_SECRET_NAME")
    if secret_name:
        if secret_name not in _key_cache:
            credentials, _ = google.auth.default(scopes=[SECRET_MANAGER_SCOPE])
            http = AuthorizedHttp(credentials, http=urllib3.PoolManager())
            response = http.request("GET", f"https://secretmanager.googleapis.com/v1/{secret_name}:access",
                                    timeout=current_app.config["GOOGLE_REQUEST_TIMEOUT"])
            if response.status != 200:
                raise GoogleError(f"Secret Manager returned {response.status}", status=response.status, retryable=response.status >= 500)
            _key_cache[secret_name] = json.loads(base64.b64decode(json.loads(response.data)["payload"]["data"]))
        return _key_cache[secret_name]
    key_file = _key_file()
    if key_file is None or not key_file.is_file():
        raise GoogleError("The Google service-account key is not configured")
    key = str(key_file)
    if key not in _key_cache:
        _key_cache[key] = json.loads(key_file.read_text())
    return _key_cache[key]


def key_summary() -> dict:
    """What identifies the service account (never the private key): the address, the client id a Workspace admin authorises, the project."""
    key = _load_key()
    return {"type": key.get("type"), "client_email": key.get("client_email"), "client_id": key.get("client_id"), "project_id": key.get("project_id")}


def mint_token(subject: str, scopes: list[str]) -> None:
    """Ask Google for an access token as `subject` for these scopes, and do nothing with it. Fails when the service account has not
    been authorised (domain-wide delegation) for the mailbox or a scope."""
    try:
        credentials = service_account.Credentials.from_service_account_info(_load_key(), scopes=scopes, subject=subject)
        credentials.refresh(google.auth.transport.urllib3.Request(urllib3.PoolManager()))
    except GoogleError:
        raise
    except google.auth.exceptions.RefreshError as exc:
        raise GoogleError(f"Google refused the service account for {subject}: {exc}") from exc
    except (urllib3.exceptions.HTTPError, google.auth.exceptions.TransportError) as exc:
        raise GoogleError(f"Could not reach Google: {exc}", retryable=True) from exc


def request(method: str, url: str, *, subject: str | None, scopes: list[str], body: dict | None = None,
            params: dict | None = None) -> dict:
    """One Google REST call as `subject` (default: GOOGLE_DELEGATED_ADMIN); the decoded JSON reply ({} for no content)."""
    subject = subject or current_app.config.get("GOOGLE_DELEGATED_ADMIN")
    if not subject:
        raise GoogleError("No mailbox to act as")
    timeout = current_app.config["GOOGLE_REQUEST_TIMEOUT"]
    try:
        credentials = service_account.Credentials.from_service_account_info(_load_key(), scopes=scopes, subject=subject)
        http = AuthorizedHttp(credentials, http=urllib3.PoolManager())
        if params:
            url = f"{url}?{urlencode(params)}"
        response = http.request(method, url, body=json.dumps(body).encode() if body is not None else None,
                                headers={"Content-Type": "application/json"} if body is not None else None, timeout=timeout)
    except GoogleError:
        raise
    except google.auth.exceptions.RefreshError as exc:
        # The delegation is not authorised for this scope or mailbox: fixing it takes a Workspace admin, so do not keep retrying fast
        raise GoogleError(f"Google refused the service account for {subject}: {exc}", retryable=False) from exc
    except (urllib3.exceptions.HTTPError, google.auth.exceptions.TransportError) as exc:
        raise GoogleError(f"Could not reach Google: {exc}", retryable=True) from exc
    return _decode(response)


def _decode(response) -> dict:
    status = response.status
    if status in (200, 201):
        return json.loads(response.data) if response.data else {}
    if status == 204:
        return {}
    try:
        detail = json.loads(response.data)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        detail = (response.data or b"")[:200].decode(errors="replace")
    raise GoogleError(f"Google returned {status}: {detail}", status=status, retryable=status == 429 or status >= 500)

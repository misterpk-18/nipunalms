"""The Google client's own rules: when it counts as configured, and how Google's replies become results or errors. No network."""
import json
from types import SimpleNamespace

import pytest

from services.google import client
from services.google.client import GoogleError


def reply(status, body=None):
    return SimpleNamespace(status=status, data=json.dumps(body).encode() if body is not None else b"")


def test_not_configured_without_a_mailbox_or_a_key(app):
    assert client.is_configured() is False
    app.config["GOOGLE_DELEGATED_ADMIN"] = "admin@example.test"
    assert client.is_configured() is False  # still no key


def test_a_key_file_or_a_secret_name_configures_it(app, tmp_path):
    app.config["GOOGLE_DELEGATED_ADMIN"] = "admin@example.test"
    app.config["GOOGLE_SA_KEY_FILE"] = str(tmp_path / "missing.json")
    assert client.is_configured() is False
    key = tmp_path / "key.json"
    key.write_text("{}")
    app.config["GOOGLE_SA_KEY_FILE"] = str(key)
    assert client.is_configured() is True
    app.config["GOOGLE_SA_KEY_FILE"] = None
    app.config["GOOGLE_SA_SECRET_NAME"] = "projects/p/secrets/s/versions/latest"
    assert client.is_configured() is True


def test_a_relative_key_path_is_read_from_the_backend_folder(app):
    app.config["GOOGLE_SA_KEY_FILE"] = "secrets/google-service-account.json"
    assert client._key_file().parts[-3:] == ("backend", "secrets", "google-service-account.json")


def test_replies_become_results_or_errors(app):
    assert client._decode(reply(200, {"id": "e1"})) == {"id": "e1"}
    assert client._decode(reply(204)) == {}
    with pytest.raises(GoogleError) as bad:
        client._decode(reply(403, {"error": {"message": "Not Authorized to access this resource"}}))
    assert bad.value.status == 403 and not bad.value.retryable and "Not Authorized" in str(bad.value)
    for status in (429, 500, 503):
        with pytest.raises(GoogleError) as slow:
            client._decode(reply(status, {"error": {"message": "later"}}))
        assert slow.value.retryable


def test_a_call_without_a_key_says_so(app):
    app.config["GOOGLE_DELEGATED_ADMIN"] = "admin@example.test"
    with pytest.raises(GoogleError, match="not configured"):
        client.request("GET", "https://example.test", subject=None, scopes=[client.CALENDAR_SCOPE])

"""`flask google check` and `google send-test`: the first-day tools. Google is faked: nothing here reaches it."""
import pytest

from services.google import check as google_check
from services.google import client as google_client
from services.google import gmail
from services.google.client import GoogleError

KEY = {"type": "service_account", "client_email": "lms@project.iam.example", "client_id": "1234567890", "project_id": "nipuna-lms"}


@pytest.fixture
def connected(app, monkeypatch, tmp_path):
    """A key file, a mailbox to act as, and a Google that answers."""
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    app.config.update(GOOGLE_SA_KEY_FILE=str(key_file), GOOGLE_DELEGATED_ADMIN="admin@example.test")
    minted, calls = [], []
    monkeypatch.setattr(google_client, "key_summary", lambda: KEY)
    monkeypatch.setattr(google_client, "mint_token", lambda subject, scopes: minted.append((subject, scopes)))
    monkeypatch.setattr(google_client, "request", lambda method, url, **kw: calls.append((method, url, kw)) or {"items": [], "files": [{"id": "f"}]})
    return SimpleCalls(minted, calls)


class SimpleCalls:
    def __init__(self, minted, calls):
        self.minted, self.calls = minted, calls


def test_a_working_connection_passes_every_check(connected):
    results = google_check.run()
    assert all(r.ok for r in results), [(r.name, r.detail) for r in results if not r.ok]
    assert [r.name for r in results] == ["Mailbox to act as", "Service-account key", "Key is a service account", "Delegation: Calendar events",
                                         "Delegation: Drive files", "Delegation: Gmail send", "Read the mailbox's calendar", "Read Drive"]
    assert "client ID 1234567890" in results[2].detail  # what the Workspace admin authorises
    assert {m for m, _ in connected.minted} == {"admin@example.test"} and len(connected.minted) == 3
    assert all(c[0] == "GET" for c in connected.calls)  # only reads


def test_a_branch_mailbox_can_be_checked_instead(connected):
    google_check.run("guntur@example.test")
    assert {m for m, _ in connected.minted} == {"guntur@example.test"}
    assert "guntur@example.test" in connected.calls[0][1]


def test_a_scope_that_was_not_authorised_is_named_with_the_fix(connected, monkeypatch):
    def mint(subject, scopes):
        if scopes == [google_client.GMAIL_SEND_SCOPE]:
            raise GoogleError("Google refused the service account for admin@example.test: unauthorized_client")

    monkeypatch.setattr(google_client, "mint_token", mint)
    results = google_check.run()
    failed = [r for r in results if not r.ok]
    assert [r.name for r in failed] == ["Delegation: Gmail send"] and "Domain-wide delegation" in failed[0].hint
    assert any(r.name == "Read Drive" and r.ok for r in results)  # the other features are still checked


def test_nothing_is_tried_without_a_mailbox_or_a_key(app):
    results = google_check.run()
    assert [r.ok for r in results] == [False, False] and "GOOGLE_DELEGATED_ADMIN" in results[0].hint


def test_a_key_that_is_not_a_service_account_stops_the_checks(connected, monkeypatch):
    monkeypatch.setattr(google_client, "key_summary", lambda: {"type": "authorized_user"})
    results = google_check.run()
    assert results[-1].name == "Key is a service account" and not results[-1].ok and connected.minted == []


# ---------------------------------------------------------------- the commands

def test_the_check_command_reports_and_exits_zero(connected, app):
    result = app.test_cli_runner().invoke(args=["google", "check"])
    assert result.exit_code == 0, result.output
    assert "ok    Delegation: Calendar events" in result.output and "Register GOOGLE_MEET:" in result.output
    assert "The connection works" in result.output


def test_the_check_command_exits_one_and_says_what_to_fix(app):
    result = app.test_cli_runner().invoke(args=["google", "check"])
    assert result.exit_code == 1
    assert "FAIL  Mailbox to act as" in result.output and "-> Set GOOGLE_DELEGATED_ADMIN" in result.output


def test_send_test_sends_one_message_as_the_chosen_sender(connected, app, monkeypatch):
    sent = []
    monkeypatch.setattr(gmail, "send", lambda sender, to, subject, body: sent.append((sender, to, subject)) or "gm-1")
    result = app.test_cli_runner().invoke(args=["google", "send-test", "--to", "me@example.test"])
    assert result.exit_code == 0 and "Gmail message gm-1" in result.output
    assert sent == [("admin@example.test", "me@example.test", "Nipuna LMS: Gmail test")]
    app.test_cli_runner().invoke(args=["google", "send-test", "--to", "me@example.test", "--mailbox", "hello@example.test"])
    assert sent[-1][0] == "hello@example.test"


def test_send_test_reports_a_refusal(connected, app, monkeypatch):
    def refuse(*args):
        raise GoogleError("Google returned 403: Delegation denied", status=403)

    monkeypatch.setattr(gmail, "send", refuse)
    result = app.test_cli_runner().invoke(args=["google", "send-test", "--to", "me@example.test"])
    assert result.exit_code == 1 and "Delegation denied" in result.output

"""Send one plain-text email as a Workspace mailbox through the Gmail API (scope gmail.send)."""
import base64
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app

from services.google import client

SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _identity(sender: str) -> tuple[str, str]:
    """(mailbox to act as, From header). The LMS sender can be a Google alias of a real user (GOOGLE_EMAIL_SENDER_MAILBOX):
    Google lets only that user's login send, with the alias in From and the display name (GOOGLE_EMAIL_SENDER_NAME) in front."""
    config = current_app.config
    if sender.lower() != (config.get("GOOGLE_EMAIL_SENDER") or "").lower():
        return sender, sender
    name = config.get("GOOGLE_EMAIL_SENDER_NAME")
    return config.get("GOOGLE_EMAIL_SENDER_MAILBOX") or sender, formataddr((name, sender)) if name else sender


def send(sender: str, to: str, subject: str, body: str) -> str:
    """Send the message from `sender`; the Gmail message id."""
    mailbox, from_header = _identity(sender)
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = from_header, to, subject
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    reply = client.request("POST", SEND_URL, subject=mailbox, scopes=[client.GMAIL_SEND_SCOPE], body={"raw": raw})
    return reply.get("id", "")

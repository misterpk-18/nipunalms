"""Send one plain-text email as a Workspace mailbox through the Gmail API (scope gmail.send)."""
import base64
from email.message import EmailMessage

from services.google import client

SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def send(sender: str, to: str, subject: str, body: str) -> str:
    """Send the message from `sender`'s mailbox; the Gmail message id."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to, subject
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    reply = client.request("POST", SEND_URL, subject=sender, scopes=[client.GMAIL_SEND_SCOPE], body={"raw": raw})
    return reply.get("id", "")

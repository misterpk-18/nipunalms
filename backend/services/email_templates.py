"""The LMS's own emails (Gmail). Plain text, one subject line each; `{name}` marks a value. Sign-in links are `essential`:
they go out whatever the person's message preferences say, and the stored copy is blanked once the message is done."""
from dataclasses import dataclass

from services.whatsapp_templates import REMINDERS, SERVICE, clean


@dataclass(frozen=True)
class Template:
    name: str
    group: str  # the notification preference group that governs it
    subject: str
    body: str
    fields: tuple[str, ...]
    essential: bool = False

    def render(self, values: dict) -> tuple[str, str]:
        """(subject, body), or ValueError naming the first value that is missing."""
        cleaned = {}
        for field in self.fields:
            value = clean(values.get(field, "")) if values.get(field) is not None else ""
            if not value:
                raise ValueError(f"No {field.replace('_', ' ')}")
            cleaned[field] = value
        return self.subject.format_map(cleaned), self.body.format_map(cleaned)


SIGNATURE = "\n\nNipuna Technologies"

STUDENT_ACTIVATION_LINK = Template(
    "student_activation_link", SERVICE, "Activate your Nipuna learning account",
    "Hello {student},\n\nNipuna Technologies, {branch}, has created your learning account. Your Student ID is {student_code}.\n\n"
    "Set your own password here:\n{link}\n\nThe link works once and expires on {expires}. If you did not expect this email, "
    "please contact your branch." + SIGNATURE,
    ("student", "branch", "student_code", "link", "expires"), essential=True)
STAFF_ACCOUNT_INVITE = Template(
    "staff_account_invite", SERVICE, "Your Nipuna LMS staff account",
    "Hello {name},\n\nA Nipuna Technologies LMS staff account has been created for you as {role} at {branch}. You will sign in with "
    "this email address.\n\nChoose your password here:\n{link}\n\nThe link works once and expires on {expires}. If you were not "
    "expecting this, please tell your Super Admin." + SIGNATURE,
    ("name", "role", "branch", "link", "expires"), essential=True)
CLASS_REMINDER = Template(
    "class_reminder", REMINDERS, "Reminder: {class_title} starts at {start}",
    "Hello {student},\n\nThis is a reminder from Nipuna Technologies, {branch}. Your class {class_title} for {course} starts at "
    "{start}. Mode: {mode}.\n\nPlease be on time; the Join button opens 15 minutes before the start on your Schedule page." + SIGNATURE,
    ("student", "branch", "class_title", "course", "start", "mode"))

TEMPLATES = {t.name: t for t in (STUDENT_ACTIVATION_LINK, STAFF_ACCOUNT_INVITE, CLASS_REMINDER)}

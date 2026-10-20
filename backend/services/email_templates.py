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
    optional: tuple[str, ...] = ()  # values that may be empty (their line is then left out of the text)

    def render(self, values: dict) -> tuple[str, str]:
        """(subject, body), or ValueError naming the first value that is missing."""
        cleaned = {}
        for field in self.fields:
            if field in self.optional:  # built by the caller (it may hold line breaks), so not flattened to one line
                cleaned[field] = str(values.get(field) or "")
                continue
            value = clean(values.get(field, "")) if values.get(field) is not None else ""
            if not value and field not in self.optional:
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

CLASS_CANCELLED = Template(
    "class_cancelled", SERVICE, "Class cancelled: {class_title}",
    "Hello {student},\n\nNipuna Technologies, {branch}, has cancelled your class {class_title} for {course} that was planned for "
    "{planned_start}.\n\nReason: {reason}\nWhat happens next: {next_step}\n\nThis cancellation is not marked as an absence. "
    "Please check your Schedule page for updates." + SIGNATURE,
    ("student", "branch", "class_title", "course", "planned_start", "reason", "next_step"))
CLASS_RESCHEDULED = Template(
    "class_rescheduled", SERVICE, "Class moved: {class_title}",
    "Hello {student},\n\nNipuna Technologies, {branch}, has moved your class {class_title} for {course}.\n\nOld time: {old_start}\n"
    "New time: {new_start}\nMode: {mode}\n\nPlease check your Schedule page for the latest details." + SIGNATURE,
    ("student", "branch", "class_title", "course", "old_start", "new_start", "mode"))
RESULT_PUBLISHED = Template(
    "result_published", SERVICE, "Your result is published: {assessment}",
    "Hello {student},\n\nNipuna Technologies, {branch}, has published your result for {assessment} in {course}. You can see your marks "
    "and your trainer's feedback under My Progress in your learning account." + SIGNATURE,
    ("student", "branch", "assessment", "course"))
CERTIFICATE_ISSUED = Template(
    "certificate_issued", SERVICE, "Your certificate is ready: {number}",
    "Hello {student},\n\nNipuna Technologies, {branch}, has issued your {certificate_type} for {course}. Certificate number: {number}.\n\n"
    "You can download it from Certificates in your learning account.{verify_line}" + SIGNATURE,
    ("student", "branch", "certificate_type", "course", "number", "verify_line"), optional=("verify_line",))
BATCH_CHANGE_AGREEMENT = Template(
    "batch_change_agreement", SERVICE, "Your agreement is needed: a change to your batch",
    "Hello {student},\n\nNipuna Technologies, {branch}, proposes a change to your batch for {course}.\n\nNow: {now}\nProposed: {proposed}\n"
    "Reason: {reason}\n\nPlease open your learning account and choose Agree or Decline by {reply_by}. Nothing changes for you until you "
    "answer." + SIGNATURE,
    ("student", "branch", "course", "now", "proposed", "reason", "reply_by"))

TEMPLATES = {t.name: t for t in (STUDENT_ACTIVATION_LINK, STAFF_ACCOUNT_INVITE, CLASS_REMINDER, CLASS_CANCELLED, CLASS_RESCHEDULED,
                                 RESULT_PUBLISHED, CERTIFICATE_ISSUED, BATCH_CHANGE_AGREEMENT)}

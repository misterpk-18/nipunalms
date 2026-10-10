"""The LMS's own WhatsApp templates (drafts in docs/whatsapp-templates/, submitted to Pinbot by the owner).

Same shape as the CRM's registry: name, language, category, body, and the order of the `{{n}}` values. `build()` checks every
value before a message is queued, because Pinbot rejects a message with an empty value and Meta forbids line breaks. The
codes below are the template names; whether Meta has approved one is `app_settings.whatsapp_approved_templates`.
"""
import re
from dataclasses import dataclass

# The kinds of message a person can switch off (notification preferences)
SERVICE = "Service"
REMINDERS = "Learning reminders"


@dataclass(frozen=True)
class Template:
    name: str
    category: str  # Utility | Authentication
    body: str
    params: tuple[str, ...]  # what {{1}}..{{n}} mean, in order
    group: str  # the notification preference group that governs it
    button: str | None = None  # what the URL button's {{1}} holds, when it has one
    language: str = "en"


CLASS_REMINDER = Template(
    "nipuna_lms_class_reminder_u_v1", "Utility",
    "Hello {{1}}, this is a reminder from Nipuna Technologies, {{2}}. Your class {{3}} for {{4}} starts at {{5}}. Mode: {{6}}. "
    "Please be on time; the Join button opens 15 minutes before the start on your Schedule page.",
    ("student", "branch", "class", "course", "start", "mode"), REMINDERS)
CLASS_CANCELLED = Template(
    "nipuna_lms_class_cancelled_u_v1", "Utility",
    "Hello {{1}}, Nipuna Technologies, {{2}}, has cancelled your class {{3}} for {{4}} that was planned for {{5}}. Reason: {{6}}. "
    "What happens next: {{7}}. This cancellation is not marked as an absence. Please check your Schedule page for updates.",
    ("student", "branch", "class", "course", "planned_start", "reason", "next_step"), SERVICE)
CLASS_RESCHEDULED = Template(
    "nipuna_lms_class_rescheduled_u_v1", "Utility",
    "Hello {{1}}, Nipuna Technologies, {{2}}, has moved your class {{3}} for {{4}}. Old time: {{5}}. New time: {{6}}. Mode: {{7}}. "
    "Please check your Schedule page for the latest details.",
    ("student", "branch", "class", "course", "old_start", "new_start", "mode"), SERVICE)
RESULT_PUBLISHED = Template(
    "nipuna_lms_result_published_u_v1", "Utility",
    "Hello {{1}}, Nipuna Technologies, {{2}}, has published your result for {{3}} in {{4}}. You can see your marks and your "
    "trainer's feedback under My Progress in your learning account.",
    ("student", "branch", "assessment", "course"), SERVICE)
CERTIFICATE_ISSUED = Template(
    "nipuna_lms_certificate_issued_u_v1", "Utility",
    "Hello {{1}}, Nipuna Technologies, {{2}}, has issued your {{3}} for {{4}}. Certificate number: {{5}}. You can download it from "
    "Certificates in your learning account, and anyone can check it with the Verify certificate link below.",
    ("student", "branch", "certificate_type", "course", "number"), SERVICE, button="number")
BATCH_CHANGE_AGREEMENT = Template(
    "nipuna_lms_batch_change_agreement_u_v1", "Utility",
    "Hello {{1}}, Nipuna Technologies, {{2}}, proposes a change to your batch for {{3}}. Now: {{4}}. Proposed: {{5}}. Reason: {{6}}. "
    "Please open your learning account and choose Agree or Decline by {{7}}. Nothing changes for you until you answer.",
    ("student", "branch", "course", "now", "proposed", "reason", "reply_by"), SERVICE)

# Templates 1-3 (reset code, student activation link, staff invite) are added in UX phase U7
TEMPLATES: dict[str, Template] = {t.name: t for t in (
    CLASS_REMINDER, CLASS_CANCELLED, CLASS_RESCHEDULED, RESULT_PUBLISHED, CERTIFICATE_ISSUED, BATCH_CHANGE_AGREEMENT)}

MAX_VALUE_LENGTH = 200


def clean(value: object, limit: int = MAX_VALUE_LENGTH) -> str:
    """One line of plain text: Meta forbids line breaks, tabs and runs of spaces in a value."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build(template: Template, values: dict[str, object]) -> tuple[list[str], list[str]]:
    """The body values and button values in order. Raises ValueError naming the missing value (an empty value is rejected by Pinbot)."""
    body = [clean(values.get(name)) for name in template.params]
    missing = [name for name, value in zip(template.params, body) if not value]
    if missing:
        raise ValueError(f"{template.name}: no value for {', '.join(missing)}")
    button = [clean(values.get(template.button))] if template.button else []
    if template.button and not button[0]:
        raise ValueError(f"{template.name}: no value for the button")
    return body, button


def render(template: Template, body_values: list[str]) -> str:
    """The message text, for logs and tests."""
    text = template.body
    for index, value in enumerate(body_values, start=1):
        text = text.replace("{{%d}}" % index, value)
    return text

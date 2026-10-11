"""The "Suggested next step" on Student Accounts (UX phase U17): what a Super Admin should do about a student's account, and
whether it needs attention. One rule set, read by the list, the account page and the nav badge; the "Needs attention" filter
(`repositories/admin_students.needs_attention_clause`) is the same rules in SQL, and a test keeps the two in step.

Order of the rules, first match wins:
  1. Suspended: nothing is wrong; offer Reactivate.
  2. Not activated yet and no link a student can use (none, expired, or one that WhatsApp did not carry): Send a link.
  3. Activated but sign-in is switched off: open the account.
  4. Enrolments held back because the account was not ready: open Issues.
  5. Not activated yet, link sent: wait. Activated: nothing to do.
"""
from dataclasses import dataclass
from datetime import datetime

from models import Student, StudentActivation, User, WhatsappMessage

PENDING = ("Account Created", "Activation Pending")
CARRIED = ("Queued", "Sent")  # the WhatsApp states that mean the link is on its way


@dataclass(frozen=True)
class NextStep:
    code: str
    label: str
    detail: str
    action: str | None  # send_link | reactivate | open | issues | None
    action_label: str | None
    attention: bool

    def to_dict(self) -> dict:
        return {"code": self.code, "label": self.label, "detail": self.detail, "action": self.action,
                "action_label": self.action_label, "attention": self.attention}


def next_step(student: Student, user: User | None, activation: StudentActivation | None, message: WhatsappMessage | None,
              enrolment_counts: dict[str, int], now: datetime) -> NextStep:
    if student.activation_status == "Suspended":
        return NextStep("suspended", "Account is suspended", "The student cannot sign in. Reactivate the account when the reason no longer applies.",
                        "reactivate", "Reactivate account", False)

    if student.activation_status in PENDING:
        state = activation.status(now) if activation else None
        if activation is None:
            return NextStep("no_link", "No activation link yet", "The student cannot sign in until they get a link.", "send_link",
                            "Send activation link", True)
        if state == "expired":
            return NextStep("link_expired", "Link expired", "The last link ran out before the student used it.", "send_link", "Send new link", True)
        if message is None or message.status not in CARRIED:
            why = (message.status_note if message and message.status_note else "WhatsApp did not carry it")
            return NextStep("link_not_delivered", "The link did not reach the student", f"{why}. Send a new link, or copy it and give it to them.",
                            "send_link", "Send new link", True)

    elif user is None or not user.is_active:
        return NextStep("login_blocked", "Sign-in is switched off", "The student has an account but cannot sign in. Open the account to see why.", "open",
                        "Open account", True)

    if enrolment_counts.get("Provisioning Pending", 0):
        return NextStep("provisioning", "Course access is held back", "An enrolment is waiting because the account was not ready. See the issue and fix it there.",
                        "issues", "See issues", True)

    if student.activation_status in PENDING:
        return NextStep("waiting", "Waiting for the student to activate", f"The link works until {activation.expires_at:%d %b %Y}.", None, None, False)
    return NextStep("nothing", "Nothing to do", "The account is active.", None, None, False)

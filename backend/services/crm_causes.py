"""Plain words for the CRM sync screens (UX phase U17): what an event is, and one line on why a failed one failed.

The raw error stays on the event (and the raw JSON under "Technical details" on the screen); this module turns the usual
causes into a sentence a Super Admin can act on without reading the CRM contract.
"""
import re

EVENT_LABELS = {
    "WhatsappStatusUpdated": "A WhatsApp delivery update",
    "CourseUpserted": "A course was added or changed",
    "AdmissionQualified": "A student's admission was confirmed",
    "AdmissionUpdated": "A student's admission details changed",
    "AdmissionCancelled": "An admission was cancelled",
    "FinanceSummaryUpdated": "A student's fee summary changed",
    "BranchUpserted": "A branch was added or changed",
    "BranchFinanceSnapshot": "Branch finance figures",
}

# (pattern on the error text, the sentence). The first match wins; {1} and {2} are the groups of the pattern.
CAUSES = (
    (r"Unknown (branch|course|admission) '([^']+)': .*not been applied yet",
     "The {1} {2} has not reached the LMS yet. Once the CRM has sent it, press Retry."),
    (r"Admission (\S+) is cancelled and cannot be updated",
     "Admission {1} was cancelled, so a later update to it cannot be applied. Nothing to fix here unless the cancellation was a mistake in the CRM."),
    (r"Admission (\S+) belongs to a different person",
     "Admission {1} is already linked to another student. Ask the CRM team which person it belongs to."),
    (r"Complimentary admission",
     "A free (complimentary) admission must belong to the same student as the paid one it comes with. Ask the CRM team to check both."),
    (r"Short code (\S+) is already used",
     "Branch short code {1} is already used by another branch. The CRM needs to send a different code."),
    (r"keeps short code",
     "A branch cannot change its short code once students have codes with it. Ask the CRM team to send the original code."),
    (r"Track (\S+) already belongs to another course",
     "Track {1} is already part of another course. Ask the CRM team to check the course and its tracks."),
    (r"Unknown track",
     "The course mentions a track the LMS does not know. Ask the CRM team to send the track first."),
    (r"There is no curriculum|is Draft in the LMS|curriculum",
     "The CRM refers to a curriculum version that this LMS no longer uses. The LMS owns curriculum now; this event can stay as it is."),
    (r"Invalid request data|\{'",
     "The CRM sent details the LMS could not accept (a missing or wrongly formatted field). Open Technical details and pass them to the CRM team."),
    (r"duplicate key|unique constraint",
     "The LMS already holds a record that clashes with this one (for example the same phone number or Student ID). Open Technical details and pass them to the CRM team."),
)
FALLBACK_CAUSE = "The LMS could not apply this event. Open Technical details and pass them to the CRM team."


def event_label(event_type: str) -> str:
    return EVENT_LABELS.get(event_type) or re.sub(r"(?<!^)(?=[A-Z])", " ", event_type).capitalize()


def plain_cause(error: str | None) -> str | None:
    """One sentence on why the event failed, or None when it did not."""
    if not error:
        return None
    for pattern, sentence in CAUSES:
        match = re.search(pattern, error)
        if match:
            groups = {str(i): g for i, g in enumerate(match.groups(), start=1)}
            return re.sub(r"\{(\d)\}", lambda m: groups.get(m.group(1), ""), sentence)
    return FALLBACK_CAUSE


def _find(payload, *keys):
    """The first value stored under any of `keys`, looking through nested objects and lists."""
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), (str, int)) and payload[key] != "":
                return payload[key]
        for value in payload.values():
            found = _find(value, *keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find(value, *keys)
            if found is not None:
                return found
    return None


def summary(event_type: str, payload) -> str:
    """What the event is about, in a sentence: the kind plus the admission, course, branch or person it names."""
    parts = []
    for label, keys in (("admission", ("admission_code",)), ("student", ("full_name",)), ("course", ("course_code",)), ("branch", ("branch_code", "branch_name"))):
        value = _find(payload, *keys)
        if value is not None:
            parts.append(f"{label} {value}")
    label = event_label(event_type)
    return f"{label} ({', '.join(parts[:2])})" if parts else label


def describe(event) -> dict:
    """The plain-words fields added to an event for the screens."""
    from services.crm import HANDLERS  # the CRM intake imports a lot; load it only when an event is described

    return {"label": event_label(event.event_type), "summary": summary(event.event_type, event.payload),
            "plain_cause": plain_cause(event.error) if event.status == "Failed" else None,
            "can_retry": event.status in ("Failed", "Received") and event.event_type in HANDLERS}

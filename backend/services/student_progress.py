"""My Progress, "What to do next" (`GET /me/progress/next-steps`, UX phase U10).

A short, ordered list of the things that would help the student most right now, built from the same services the other student
screens read, so it always agrees with them:

  work overdue -> a certificate waiting for the fee -> an absence that can still be recovered -> attendance below the alert level
  -> recording or material access ended or ending -> work to do -> a certificate ready to download -> topics still to finish
  -> no activity lately.

Each step is `{kind, course, params}`; it carries no sentence and no link. The screen words each kind (in English or Telugu) and
knows where it leads. An empty list means the student is up to date.
"""
from datetime import timedelta

from config.timezone import today_ist
from services import attendance, progress, student_certificates, student_library, student_work

MAX_STEPS = 6
ORDER = ("work_overdue", "certificate_fee", "recovery", "attendance_low", "access_ended", "access_ending", "work_todo", "certificate_ready",
         "topics_left", "inactive")
EXPIRY_WARNING_DAYS = 30


def _course(enrolment: dict) -> dict:
    course = enrolment["course"]
    return {"course_code": course["course_code"], "title": course["title"]}


def _step(kind: str, course: dict | None = None, **params) -> dict:
    return {"kind": kind, "course": course, "params": params}


def _work_steps() -> list[dict]:
    counts = student_work.get_work()["counts"]
    steps = []
    if counts["overdue"]:
        steps.append(_step("work_overdue", n=counts["overdue"]))
    waiting_on_me = counts["todo"] - counts["overdue"]
    if waiting_on_me > 0:
        steps.append(_step("work_todo", n=waiting_on_me))
    return steps


def _certificate_steps() -> list[dict]:
    fee_steps, ready_steps = [], []
    for card in student_certificates.cards():
        course = {"course_code": card["course"]["course_code"], "title": card["course"]["title"]}
        blocker = card["blocker"]
        if blocker is not None and blocker["code"] == "fee_outstanding":
            fee_steps.append(_step("certificate_fee", course, balance=blocker["params"]["balance"]))
        elif card["can_download"]:
            ready_steps.append(_step("certificate_ready", course))
    return fee_steps + ready_steps


def _attendance_steps() -> list[dict]:
    recovery, low = [], []
    for block in attendance.my_attendance():
        course = _course(block["enrolment"])
        can_recover = [row for row in block["rows"] if row["can_request_recovery"]]
        if can_recover:
            recovery.append(_step("recovery", course, n=len(can_recover), session=can_recover[0]["session"]["title"]))
        summary = block["summary"]
        if summary["alert"]:
            low.append(_step("attendance_low", course, percent=round(summary["percent"]), threshold=summary["alert_threshold"]))
    return recovery + low


def _access_steps() -> list[dict]:
    """A course whose recording or material access has ended, or ends within a month. When both end on the same day the step says so once."""
    steps = []
    today = today_ist()
    for row in student_library.access_overview():
        course = _course(row["enrolment"])
        can_request = any(row["can_request"].values())
        found = {}
        for what, state in (("recordings", row["recording"]), ("materials", row["material"])):
            if state["state"] == "Expired":
                found[what] = ("access_ended", state["expiry"])
            elif state["state"] == "Available" and state["expiry"] is not None and state["expiry"] - today <= timedelta(days=EXPIRY_WARNING_DAYS):
                found[what] = ("access_ending", state["expiry"])
        if len(found) == 2 and found["recordings"] == found["materials"]:
            kind, until = found["recordings"]
            steps.append(_step(kind, course, what="both", until=until, can_request=can_request))
            continue
        steps.extend(_step(kind, course, what=what, until=until, can_request=can_request) for what, (kind, until) in found.items())
    return steps


def _learning_steps() -> list[dict]:
    topics, quiet = [], []
    for block in progress.my_progress():
        if block["enrolment"]["status"] not in ("Active", "Allocated — awaiting first regular class"):
            continue
        course = _course(block["enrolment"])
        learning = block["required_learning"]
        left = learning["required_topics"] - learning["covered_topics"]
        if left > 0 and block["attendance"]["state"] != "Not started":
            topics.append(_step("topics_left", course, n=left))
        engagement = block["engagement"]
        if engagement["level"] == "Low" and block["attendance"]["state"] != "Not started":  # nothing to be quiet about before classes begin
            quiet.append(_step("inactive", course, days=engagement["window_days"]))
    return topics + quiet


def next_steps() -> list[dict]:
    steps = _work_steps() + _certificate_steps() + _attendance_steps() + _access_steps() + _learning_steps()
    steps.sort(key=lambda step: ORDER.index(step["kind"]))  # stable: courses keep their order within a kind
    return steps[:MAX_STEPS]

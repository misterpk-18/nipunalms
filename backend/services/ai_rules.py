"""The rule-based writer behind Ask Nipuna: answers from the user's permitted facts alone, with no AI provider.

It is used when no ANTHROPIC_API_KEY is configured or the provider call fails. It never explains subject matter it has not
been given: it says what the curriculum, schedule and delivery records show and points to the right screen.
"""
import re

from services.ai_facts import Facts

STOP_WORDS = {
    "explain", "about", "what", "the", "how", "topic", "this", "that", "from", "with", "tell", "give", "please", "practice",
    "questions", "question", "generate", "summarize", "summary", "draft", "class", "for", "and", "can", "you", "are", "was",
    "does", "into", "make", "some", "show", "need", "want", "help", "my", "me", "is", "in", "of", "to", "a", "on", "it",
}
PRACTICE_LABEL = "AI-generated practice, ungraded (rule-based). It is not an assessment and awards no marks."


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9+#]+", text.lower()) if len(w) >= 3 and w not in STOP_WORDS]


def _find_topic(question: str, facts: Facts) -> tuple[str, str, bool] | None:
    """(topic title, module title, required) of the topic whose words best match the question."""
    tokens = _tokens(question)
    best, best_score = None, 0
    for version in _curricula(facts):
        for module in version["modules"]:
            for topic in module["topics"]:
                haystack = f"{topic['title']} {module['title']}".lower()
                score = sum(1 for t in tokens if t in haystack)
                if score > best_score:
                    best, best_score = (topic["title"], module["title"], topic["required"]), score
    return best


def _curricula(facts: Facts) -> list[dict]:
    """Curriculum versions of the facts (a student has several; a staff batch has one each)."""
    if "curriculum" in facts.data:
        return facts.data["curriculum"]
    return [b["curriculum"] for b in facts.data.get("batches", []) if b.get("curriculum")]


def _pick(facts: Facts, *types: str) -> list[dict]:
    return [s for s in facts.sources if s["type"] in types]


def _session_lines(sessions: list[dict], limit: int = 5) -> str:
    return "\n".join(f"- {s['starts']}: {s['title']} ({s['mode']}, {s['batch']})" for s in sessions[:limit])


def _first_topic(facts: Facts) -> tuple[str, str, bool] | None:
    for version in _curricula(facts):
        for module in version["modules"]:
            for topic in module["topics"]:
                return topic["title"], module["title"], topic["required"]
    return None


def _practice(topic: str) -> str:
    return (
        f"{PRACTICE_LABEL}\n"
        f"1. In your own words, what problem does \"{topic}\" solve?\n"
        f"2. Give one example where you would use \"{topic}\" and one where you would not.\n"
        f"3. Write down the steps you would follow to apply \"{topic}\" to a small dataset or task from class."
    )


# ---------------------------------------------------------------- student

def student_answer(question: str, action: str | None, facts: Facts) -> tuple[str, list[dict]]:
    text = f"{action or ''} {question}".lower()
    enrolments = facts.data["enrolments"]
    if not enrolments:
        return "I can't see an active enrolment on your account, so I have no course to answer from. Please raise a support request.", []

    if "progress" in text or "attendance" in text or "how am i doing" in text:
        lines = [f"- {d['batch']}: {d['delivered']} of {d['planned']} planned sessions delivered so far." for d in facts.data["delivery"]]
        body = "\n".join(lines) or "You are not allocated to a batch yet, so no sessions have been delivered to you."
        return (
            "Here is what your records show.\n" + body + "\nYour attendance, marks and completion are recorded by your trainer and coordinator, "
            "so I don't estimate them. Open Progress to see the four measures.",
            _pick(facts, "batch", "enrolment"),
        )
    if re.search(r"\b(next class|schedule|when|today|tomorrow|upcoming|timetable)\b", text):
        sessions = facts.data["upcoming_sessions"]
        if not sessions:
            return "You have no upcoming class sessions in the next two weeks.", _pick(facts, "batch")
        return "Your upcoming classes:\n" + _session_lines(sessions), _pick(facts, "class_session")
    if re.search(r"\b(due|assignment|homework|deadline|test|exam)\b", text):
        due = facts.data.get("due_work")
        if due is None:
            return "Data unavailable / not verified: due work isn't connected to me yet. Open Tasks and Tests to see what is due.", []
        return f"Your due work: {due}", _pick(facts, "assignment", "test")
    if re.search(r"\b(career|job|placement|resume|cv|interview)\b", text):
        return (
            "Career support is placement / career assistance only, with no guaranteed placement. Open Career to opt in, keep your "
            "profile and CV up to date and see approved opportunities.",
            [],
        )

    topic = _find_topic(question, facts)
    if "practice" in text:
        chosen = topic or _first_topic(facts)
        if chosen is None:
            return "I have no curriculum topics to write practice questions from yet.", []
        return _practice(chosen[0]), _pick(facts, "curriculum_version")
    if topic is not None:
        title, module, required = topic
        sessions = [s for s in facts.data["upcoming_sessions"] if s["topic"] == title]
        upcoming = f"\nYour next session on it: {sessions[0]['starts']} ({sessions[0]['title']})." if sessions else ""
        return (
            f"\"{title}\" is part of the module \"{module}\" in your curriculum and is {'a required' if required else 'an optional'} topic."
            f"{upcoming}\nI can only outline it from your curriculum; for the full explanation use your class notes and resources, "
            "or ask your trainer.",
            _pick(facts, "curriculum_version", "class_session"),
        )
    courses = "; ".join(f"{e['course']} ({e['status']})" for e in enrolments)
    return (
        f"You are enrolled in: {courses}. You can ask me about your schedule, a topic in your curriculum, your delivery progress "
        "or for practice questions.",
        _pick(facts, "enrolment"),
    )


# ---------------------------------------------------------------- staff

def staff_answer(question: str, action: str | None, facts: Facts) -> tuple[str, list[dict]]:
    text = f"{action or ''} {question}".lower()
    batches = facts.data["batches"]
    if not batches:
        return "No batches are in your scope, so I have nothing to summarise.", []

    if "feedback" in text:
        return (
            "A structure for feedback: 1) Start with one specific thing the student did well. 2) Name the single most important "
            "improvement, with an example from their work. 3) Give one concrete next step and when you will look again. "
            "Keep it factual and about the work, not the person. Review and personalise it before sending.",
            [],
        )
    if "practice" in text or "question" in text:
        chosen = _find_topic(question, facts) or _first_topic(facts)
        if chosen is None:
            return "None of your batches has curriculum topics to write practice questions from.", []
        return _practice(chosen[0]), _pick(facts, "batch")
    topic = _find_topic(question, facts)
    if "explain" in text and topic is not None:
        title, module, required = topic
        return (
            f"Topic \"{title}\" sits in the module \"{module}\" ({'required' if required else 'optional'}). "
            "I can outline where it falls in the curriculum; prepare the explanation itself from your own notes and the approved resources.",
            _pick(facts, "batch"),
        )
    lines = [
        f"- {b['batch']} ({b['course']}): {b['allocated_students']}/{b['capacity']} seats, {b['sessions_delivered']} of "
        f"{b['sessions_planned']} sessions delivered, {b['state']}, readiness {b['readiness']}."
        for b in batches
    ]
    return "Batch summary:\n" + "\n".join(lines), _pick(facts, "batch")

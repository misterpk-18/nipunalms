"""Question bank (Module 20 §2): trainers draft, the Academic Coordinator approves, approved questions can be put in tests.

The answer key never leaves these staff endpoints. An approved question is frozen: a change is a new version (a new Draft that
retires its parent when approved), so earlier papers and results keep the wording and key they were scored against.
"""
from datetime import datetime, timezone

from config.database import db
from models import Question
from repositories import batches as batches_repo
from repositories import catalog as catalog_repo
from repositories import questions as questions_repo
from repositories.common import paginate
from services import audit, scope
from services.context import ASSESSMENT_AUTHOR_ROLES, MODERATOR_ROLES, current_user
from services.errors import BusinessRule, Forbidden, NotFound, ValidationError
from services.scoring import validate_question_key


def question_branch_ids() -> set[int] | None:
    """Branches whose bank the user works with: those they run (Academic Coordinator) or teach at (trainer); None = all."""
    branch_ids = scope.visible_branch_ids()
    if branch_ids is None:
        return None
    return branch_ids | {s.branch_id for s in current_user().scopes if s.role_code == "TRAINER"}


def _resolve_branch(branch_id: int | None) -> int:
    user = current_user()
    if branch_id is None:
        branches = question_branch_ids()
        if branches is None or len(branches) != 1:
            raise ValidationError("Invalid request data", {"branch_id": ["Required: say which branch owns this question"]})
        branch_id = next(iter(branches))
    if not user.has_role(*ASSESSMENT_AUTHOR_ROLES, branch_id=branch_id):
        raise Forbidden("You can't add questions for this branch")
    return branch_id


def _assert_can_author(course_id: int, branch_id: int) -> None:
    """A trainer drafts only for courses they teach at the branch; coordinators and Super Admin for any course."""
    user = current_user()
    if user.has_role(*MODERATOR_ROLES, branch_id=branch_id):
        return
    taught = (batches_repo.get_batch(batch_id) for batch_id in scope.trainer_batch_ids())
    if not any(b.course_id == course_id and b.branch_id == branch_id for b in taught):
        raise Forbidden("You can only add questions for courses you teach")


def _load(question_id: int) -> Question:
    question = questions_repo.get_question(question_id)
    branches = question_branch_ids()
    if question is None or (branches is not None and question.branch_id not in branches):
        raise NotFound("Question not found")
    return question


def _can_moderate(question: Question) -> bool:
    return current_user().has_role(*MODERATOR_ROLES, branch_id=question.branch_id)


def list_questions(filters: dict, page: int, per_page: int) -> tuple[list[Question], dict]:
    return paginate(questions_repo.list_stmt(filters, question_branch_ids()), page, per_page)


def get_question(question_id: int) -> Question:
    return _load(question_id)


def create_question(data: dict) -> Question:
    if catalog_repo.get_course(data["course_id"]) is None:
        raise ValidationError("Invalid request data", {"course_id": ["Unknown course"]})
    branch_id = _resolve_branch(data.get("branch_id"))
    _assert_can_author(data["course_id"], branch_id)
    options, key = validate_question_key(data["question_type"], data.get("options", []), data.get("answer_key"))
    question = Question(
        course_id=data["course_id"], branch_id=branch_id, topic_id=data.get("topic_id"), question_type=data["question_type"],
        stem=data["stem"], options=options, answer_key=key, explanation=data.get("explanation"), marks=data.get("marks", 1),
        difficulty=data.get("difficulty", "Medium"), tags=[t.lower() for t in data.get("tags", [])], author_user_id=current_user().user_id,
    )
    db.session.add(question)
    db.session.flush()
    db.session.refresh(question)
    audit.record("create", "question", question.question_id, new={"code": question.question_code, "type": question.question_type},
                 branch_id=branch_id)
    return question


def update_question(question_id: int, data: dict) -> Question:
    question = _load(question_id)
    if question.status != "Draft":
        raise BusinessRule("Only a draft question can be edited; create a new version of an approved one")
    if question.author_user_id != current_user().user_id and not _can_moderate(question):
        raise Forbidden("Only the author or the Academic Coordinator can edit this question")
    question_type = data.get("question_type", question.question_type)
    options, key = validate_question_key(question_type, data.get("options", question.options),
                                         data.get("answer_key", question.answer_key))
    question.question_type, question.options, question.answer_key = question_type, options, key
    for field in ("topic_id", "stem", "explanation", "marks", "difficulty"):
        if field in data:
            setattr(question, field, data[field])
    if "tags" in data:
        question.tags = [t.lower() for t in data["tags"]]
    db.session.flush()
    return question


def approve_question(question_id: int) -> Question:
    """The Academic Coordinator approves stem, key and explanation for use in tests; never the author's own question."""
    question = _load(question_id)
    if not _can_moderate(question):
        raise Forbidden("Only the Academic Coordinator can approve questions")
    if question.status != "Draft":
        raise BusinessRule(f"Only a draft can be approved (this one is {question.status})")
    user = current_user()
    if question.author_user_id == user.user_id:
        raise BusinessRule("You wrote this question; another reviewer has to approve it")
    question.status, question.reviewed_by, question.approved_at = "Approved", user.user_id, datetime.now(timezone.utc)
    if question.parent_question_id:
        parent = questions_repo.get_question(question.parent_question_id)
        if parent is not None and parent.status == "Approved":
            parent.status = "Retired"
    db.session.flush()
    audit.record("approve", "question", question_id, new={"status": "Approved", "version": question.version}, branch_id=question.branch_id)
    return question


def retire_question(question_id: int) -> Question:
    """Retired questions cannot be added to new tests; tests that already froze them keep them."""
    question = _load(question_id)
    if not _can_moderate(question) and not (question.status == "Draft" and question.author_user_id == current_user().user_id):
        raise Forbidden("Only the Academic Coordinator can retire this question")
    if question.status == "Retired":
        raise BusinessRule("This question is already retired")
    old = question.status
    question.status = "Retired"
    db.session.flush()
    audit.record("retire", "question", question_id, old={"status": old}, new={"status": "Retired"}, branch_id=question.branch_id)
    return question


def new_version(question_id: int) -> Question:
    """Copy an approved (or retired) question into a new Draft, version + 1, ready to edit and approve."""
    parent = _load(question_id)
    if parent.status == "Draft":
        raise BusinessRule("A draft can simply be edited")
    _assert_can_author(parent.course_id, parent.branch_id)
    question = Question(
        course_id=parent.course_id, branch_id=parent.branch_id, topic_id=parent.topic_id, question_type=parent.question_type,
        stem=parent.stem, options=parent.options, answer_key=parent.answer_key, explanation=parent.explanation, marks=parent.marks,
        difficulty=parent.difficulty, tags=list(parent.tags or []), version=parent.version + 1, parent_question_id=parent.question_id,
        author_user_id=current_user().user_id,
    )
    db.session.add(question)
    db.session.flush()
    db.session.refresh(question)
    return question

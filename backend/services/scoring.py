"""Deterministic scoring of test answers and validation of question keys (Module 20 §2 and §6).

Objective types are scored by the answer key frozen in the test: single choice, multiple choice (exact set, no partial
credit), true / false, numeric (with an approved tolerance), short answer and output prediction (accepted variants).
Descriptive and coding answers are never scored here: they need a trainer.
No negative marking.
"""
import re
from decimal import Decimal
from typing import Any

from services.errors import ValidationError

CHOICE_TYPES = ("Single choice", "Multiple choice")
VARIANT_TYPES = ("Short answer", "Output prediction")
MANUAL_TYPES = ("Descriptive", "Coding")


def is_auto_graded(question_type: str) -> bool:
    return question_type not in MANUAL_TYPES


def _normalise(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def score_answer(question_type: str, answer_key: dict, answer: Any, marks: Decimal) -> Decimal | None:
    """Marks for an answer: full marks when correct, 0 when wrong or blank, None for a written answer that needs a trainer."""
    if answer is None or answer == "" or answer == []:
        return Decimal("0")  # nothing to read, whatever the type
    if not is_auto_graded(question_type):
        return None
    if question_type == "Single choice":
        correct = answer == answer_key["option"]
    elif question_type == "Multiple choice":
        correct = isinstance(answer, list) and set(answer) == set(answer_key["options"])
    elif question_type == "True / False":
        correct = isinstance(answer, bool) and answer == answer_key["value"]
    elif question_type == "Numeric":
        try:
            correct = abs(float(answer) - float(answer_key["value"])) <= float(answer_key.get("tolerance", 0))
        except (TypeError, ValueError):
            correct = False
    else:  # Short answer, Output prediction
        correct = _normalise(answer) in {_normalise(v) for v in answer_key["variants"]}
    return Decimal(marks) if correct else Decimal("0")


def validate_question_key(question_type: str, options: list[dict], answer_key: Any) -> tuple[list[dict], dict]:
    """Check the options and answer key belong together for the question type; returns the cleaned pair."""
    errors: dict[str, list[str]] = {}
    keys = [o.get("key") for o in options]
    if question_type in CHOICE_TYPES:
        if len(options) < 2:
            errors["options"] = ["Add at least two options"]
        elif len(set(keys)) != len(keys):
            errors["options"] = ["Option keys must be unique"]
    elif options:
        errors["options"] = [f"{question_type} questions have no options"]
        options = []

    if not isinstance(answer_key, dict):
        errors["answer_key"] = ["Must be an object"]
        raise ValidationError("Invalid request data", errors)

    cleaned: dict[str, Any] = {}
    if question_type == "Single choice":
        if answer_key.get("option") not in keys:
            errors["answer_key"] = ["`option` must be one of the option keys"]
        else:
            cleaned = {"option": answer_key["option"]}
    elif question_type == "Multiple choice":
        chosen = answer_key.get("options")
        if not isinstance(chosen, list) or not chosen or not set(chosen) <= set(keys):
            errors["answer_key"] = ["`options` must list at least one option key"]
        else:
            cleaned = {"options": list(dict.fromkeys(chosen))}
    elif question_type == "True / False":
        if not isinstance(answer_key.get("value"), bool):
            errors["answer_key"] = ["`value` must be true or false"]
        else:
            cleaned = {"value": answer_key["value"]}
    elif question_type == "Numeric":
        value, tolerance = answer_key.get("value"), answer_key.get("tolerance", 0)
        numbers = all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in (value, tolerance))
        if not numbers or tolerance < 0:
            errors["answer_key"] = ["`value` must be a number and `tolerance` zero or more"]
        else:
            cleaned = {"value": value, "tolerance": tolerance}
    elif question_type in VARIANT_TYPES:
        variants = answer_key.get("variants")
        if not isinstance(variants, list) or not variants or not all(isinstance(v, str) and v.strip() for v in variants):
            errors["answer_key"] = ["`variants` must list at least one accepted answer"]
        else:
            cleaned = {"variants": list(dict.fromkeys(v.strip() for v in variants))}
    else:  # Descriptive, Coding: a rubric for the grader
        rubric = answer_key.get("rubric")
        if not isinstance(rubric, str) or not rubric.strip():
            errors["answer_key"] = ["`rubric` is required so the grader knows what to look for"]
        else:
            cleaned = {"rubric": rubric.strip()}
    if errors:
        raise ValidationError("Invalid request data", errors)
    return options, cleaned

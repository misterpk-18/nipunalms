"""Trainer screens that read across the trainer's batches: the to-grade inbox, students at risk, and the batch and student pages."""
from flask import request

from controllers.common import Validator, ok
from services import trainer_grading, trainer_people, trainer_risk


def to_grade():
    v = Validator(request.args.to_dict())
    v.integer("batch_id", min_value=1)
    return ok(trainer_grading.to_grade(v.validate().get("batch_id")))


def at_risk():
    return ok(trainer_risk.at_risk())


def batches():
    return ok(trainer_people.batches())


def batch_page(batch_id: int):
    return ok(trainer_people.batch_page(batch_id))


def student_page(student_id: int):
    return ok(trainer_people.student_page(student_id))

"""The student's own library: released resources, recordings and access dates."""
from flask import request

from controllers.common import Validator, ok
from models.content import CONTENT_TYPES, RECORDING_STATUSES
from services import content as content_service
from services import recordings as recordings_service
from services import student_library as library_service


def list_resources():
    v = Validator(request.args.to_dict())
    for field in ("course_id", "module_id", "topic_id"):
        v.integer(field, min_value=1)
    v.choice("content_type", CONTENT_TYPES)
    v.string("q", max_length=100)
    return ok(content_service.student_resources(v.validate()))


def list_recordings():
    v = Validator(request.args.to_dict())
    v.integer("session_id", min_value=1)
    v.choice("status", RECORDING_STATUSES)
    return ok(recordings_service.student_recordings(v.validate()))


def get_access():
    return ok(library_service.access_overview())

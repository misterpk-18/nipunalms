from flask import request

from controllers.common import Validator, get_page_params, ok, paginated
from services import my_courses as my_courses_service


def _module(row) -> dict:
    return {
        "module_id": row.module.module_id,
        "title": row.module.title,
        "title_te": row.module.title_te,
        "sort_order": row.module.sort_order,
        "topic_count": row.topic_count,
        "required_topic_count": row.required_topic_count,
        "session_count": row.session_count,
        "delivered_count": row.delivered_count,
        "status": row.status,
    }


def _track(row) -> dict:
    return {**row.track.to_dict(), "delivery": row.delivery}


def _card(view) -> dict:
    enrolment = view.enrolment
    return {
        **enrolment.to_dict(batch=view.batch.to_summary() if view.batch else None),
        "trainers": [t.to_dict() for t in view.trainers],
        "delivery": view.delivery,
        "explanation": view.explanation,
        "linked_admission_code": view.linked_admission_code,
    }


def list_enrolments():
    return ok([_card(v) for v in my_courses_service.list_enrolments()])


def get_enrolment(enrolment_id: int):
    view = my_courses_service.get_enrolment(enrolment_id)
    return ok({
        **_card(view),
        "tracks": [_track(t) for t in view.tracks],
        "modules": [_module(m) for m in view.modules],
        "next_sessions": [{**s.to_summary(), "mode": s.mode, "trainer": s.trainer.full_name} for s in view.next_sessions],
        "finance": view.finance.to_dict() if view.finance else None,
    })


def get_track(enrolment_id: int, enrolment_track_id: int):
    view = my_courses_service.get_track(enrolment_id, enrolment_track_id)
    return ok({
        "enrolment": {**view.enrolment.to_summary(), "curriculum_version": view.enrolment.curriculum_version.to_summary()
                      if view.enrolment.curriculum_version else None},
        "track": view.track.to_dict(),
        "delivery": view.delivery,
        "modules": [_module(m) for m in view.modules],
    })


def schedule():
    v = Validator(request.args.to_dict())
    v.integer("course_id", min_value=1)
    v.date("from")
    v.date("to")
    page, per_page = get_page_params()
    rows, meta, by_batch = my_courses_service.schedule(v.validate(), page, per_page)
    data = []
    for row in rows:
        enrolment = by_batch.get(row.session.batch_id)
        data.append({**row.session.to_dict(include_link=False, join=row.join),
                     "enrolment": {"enrolment_id": enrolment.enrolment_id, "enrolment_code": enrolment.enrolment_code} if enrolment else None})
    return paginated(data, meta)

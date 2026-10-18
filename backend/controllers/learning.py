from controllers.common import ok
from services import learning as learning_service
from services import topic_hub


def _context(context) -> dict | None:
    if context is None:
        return None
    return {"enrolment": context.enrolment.to_summary(), "track": context.track.to_dict() if context.track else None}


def _module_head(module) -> dict:
    return {
        "module_id": module.module_id,
        "title": module.title,
        "title_te": module.title_te,
        "sort_order": module.sort_order,
        "course_id": module.course_id,
        "component_id": module.component_id,
    }


def _session(session) -> dict:
    return {**session.to_summary(), "mode": session.mode, "trainer": session.trainer.full_name, "batch": session.batch.to_summary()}


def get_module(module_id: int):
    page = learning_service.get_module(module_id)
    return ok({
        **_module_head(page.module),
        "context": _context(page.context),
        "status": page.status,
        "topics": [{**topic.to_dict(), "session_count": count,
                    "progress": page.progress[topic.topic_id].to_dict() if topic.topic_id in page.progress else None}
                   for topic, count in page.topics],
    })


def get_topic(topic_id: int):
    page = learning_service.get_topic(topic_id)
    return ok({
        **page.topic.to_dict(),
        "module": _module_head(page.topic.module),
        "context": _context(page.context),
        "sessions": [_session(s) for s in page.sessions],
    })


def topic_hub_page(topic_id: int):
    return ok(topic_hub.get_hub(topic_id))

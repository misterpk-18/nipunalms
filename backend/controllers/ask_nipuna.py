from controllers.common import Validator, created, get_page_params, json_body, ok, paginated
from services import ask_nipuna as ask_service


def _usage(usage: ask_service.Usage) -> dict:
    return {"used": usage.used, "limit": usage.limit, "resets_at": usage.resets_at}


def status():
    s = ask_service.status()
    return ok({
        "status": s.status,
        "mode": s.mode,
        "audience": s.audience,
        "usage": _usage(s.usage),
        "actions": list(s.actions),
        "scope_note": s.scope_note,
    })


def ask():
    v = Validator(json_body())
    v.string("question", required=True, min_length=2, max_length=2000)
    v.string("action", nullable=True, max_length=60)
    data = v.validate()
    query, usage = ask_service.ask(data["question"], data.get("action"))
    return created({**query.to_dict(), "usage": _usage(usage)})


def list_queries():
    page, per_page = get_page_params()
    items, meta = ask_service.list_queries(page, per_page)
    return paginated([q.to_dict() for q in items], meta)


def give_feedback(ai_query_id: int):
    v = Validator(json_body())
    v.choice("rating", ("Helpful", "Not helpful"), required=True)
    v.string("comment", nullable=True, max_length=1000)
    data = v.validate()
    return ok(ask_service.give_feedback(ai_query_id, data["rating"], data.get("comment")).to_dict())

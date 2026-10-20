"""Who sees what, for every role, on every list endpoint.

Found 20 Oct 2026: the Super Admin and Founder got an empty Tests list because "no restriction" was passed to .where() as None
(WHERE NULL). These checks sweep every no-argument GET route with a populated world so a whole class of that mistake cannot return:
  1. no route fails with a server error for any role;
  2. the Super Admin and Founder never see fewer rows than a narrower role on the same route;
  3. a Branch Manager sees their own branch's records and nothing of another branch's;
  4. a trainer sees only the batches they are assigned to.
"""
from flask import current_app

from tests.assessment_world import API, make_question, make_test, world  # noqa: F401 (fixtures)
from tests.assessment_world import assignment_body

# Per-user or non-list routes: counts differ by design, or the route needs arguments / a service key
SKIP = ("/auth/", "/health", "/export", "/search", "/me/", "/notifications", "/ask-nipuna", "/audit-log", "/integrations/crm/status", "/ai-controls")

ROLES = {"wide": ("admin", "founder"), "narrow": ("ac", "ac_vij", "g1", "g2", "v1")}


def list_routes() -> list[str]:
    return sorted({r.rule for r in current_app.url_map.iter_rules()
                   if "GET" in r.methods and "<" not in r.rule and r.rule.startswith(API) and not any(s in r.rule for s in SKIP)})


def rows(client, world, who: str, route: str):
    """(status, row count or None) of one route for one role."""
    response = client.get(f"{route}?per_page=100", headers=world.h[who])
    body = response.get_json(silent=True) or {}
    data = body.get("data")
    count = (body.get("meta") or {}).get("total", len(data) if isinstance(data, list) else None)
    return response.status_code, count


def populate(client, world) -> None:
    """Content in both branches: a test, an assignment and a question in Guntur."""
    question = make_question(client, world)
    make_test(client, world, [question["question_id"]])
    created = client.post(f"{API}/assignments", json=assignment_body(world, release_now=True), headers=world.h["g1"])
    assert created.status_code == 201, created.get_json()


def test_no_list_route_fails_for_any_role(client, world):
    populate(client, world)
    for route in list_routes():
        for who in (*ROLES["wide"], *ROLES["narrow"], "s1"):
            status, _ = rows(client, world, who, route)
            assert status < 500, f"{route} as {who} -> {status}"


def test_the_super_admin_and_founder_never_see_less_than_a_narrower_role(client, world):
    populate(client, world)
    for route in list_routes():
        for wide in ROLES["wide"]:
            wide_status, wide_count = rows(client, world, wide, route)
            if wide_status != 200 or wide_count is None:
                continue
            for narrow in ROLES["narrow"]:
                status, count = rows(client, world, narrow, route)
                if status == 200 and count is not None:
                    assert wide_count >= count, f"{route}: {wide} sees {wide_count} but {narrow} sees {count}"


def test_the_assessment_lists_show_the_super_admin_and_founder_everything(client, world):
    populate(client, world)
    for route in ("/tests", "/assignments", "/questions"):
        for who in ROLES["wide"]:
            assert rows(client, world, who, f"{API}{route}") == (200, 1), f"{route} as {who}"


def test_branches_and_trainers_stay_inside_their_own_records(client, world):
    populate(client, world)
    # the test, assignment and question all belong to Guntur batch G1
    for route in ("/tests", "/assignments", "/questions"):
        assert rows(client, world, "ac", f"{API}{route}") == (200, 1), f"{route} as the Guntur Branch Manager"
        assert rows(client, world, "g1", f"{API}{route}")[1] >= 1, f"{route} as the batch's own trainer"
        others = ("ac_vij", "v1") if route == "/questions" else ("ac_vij", "g2", "v1")  # the bank is per course: G2 teaches the same course here
        for who in others:
            assert rows(client, world, who, f"{API}{route}")[1] == 0, f"{route} as {who}"
    batches = {who: rows(client, world, who, f"{API}/batches")[1] for who in ("admin", "founder", "ac", "ac_vij", "g1", "g2", "v1")}
    assert batches == {"admin": 3, "founder": 3, "ac": 2, "ac_vij": 1, "g1": 1, "g2": 1, "v1": 1}

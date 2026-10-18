"""A notification or record link never sends a Super Admin or Founder / CEO to a /branch/* page (they have no Branch workspace) or to
the other central workspace; the same link opens a page that exists under their own prefix."""
import re
from pathlib import Path

import pytest
from sqlalchemy import select

from config.database import db
from models import Notification
from services import role_links
from services.notifications import notify

ROOT = Path(__file__).resolve().parent.parent
ROUTES = ROOT.parent / "frontend" / "src" / "routes"
PREFIX = {"SUPER_ADMIN": "/admin", "FOUNDER_CEO": "/founder"}
LINK = re.compile(r"""["'](/(?:branch|admin|founder)(?:/[A-Za-z0-9_\-$/{}.]*)?(?:\?[^"']*)?)["']""")


def _route_exists(path: str) -> bool:
    """Whether a frontend route file serves this path (dynamic segments `$x` and the `?query` are ignored)."""
    segments = [s for s in path.split("?")[0].split("/") if s]
    if len(segments) == 1:
        return (ROUTES / f"{segments[0]}.index.tsx").exists() or (ROUTES / f"{segments[0]}.tsx").exists()
    name = ".".join(segments[:2])
    return any((ROUTES / f"{name}{suffix}").exists() for suffix in (".tsx", ".index.tsx", ".$id.tsx", ".$.tsx")) or any(ROUTES.glob(f"{name}.*"))


def _literals() -> set[str]:
    found = set()
    for folder in ("services", "controllers"):
        for file in (ROOT / folder).glob("*.py"):
            for match in LINK.finditer(file.read_text()):
                found.add(re.sub(r"\{[^}]*\}", "1", match.group(1)))  # f-string holes
    return found


@pytest.mark.parametrize("role", ["SUPER_ADMIN", "FOUNDER_CEO"])
def test_every_link_the_backend_writes_opens_a_page_the_central_role_has(role):
    links = _literals()
    assert any(link.startswith("/branch") for link in links)  # the sweep sees the branch links at all
    for link in sorted(links):
        mapped = role_links.for_role(link, role)
        assert mapped.startswith(PREFIX[role]), f"{link} -> {mapped}"
        assert _route_exists(mapped), f"{link} -> {mapped} has no page"


def test_other_roles_keep_their_links():
    for link in ("/branch/support", "/branch/completion", "/trainer/support", "/dashboard", "/branch/extensions"):
        for role in ("BRANCH_MANAGER", "TRAINER", "STUDENT", None):
            assert role_links.for_role(link, role) == link
    assert role_links.for_role(None, "SUPER_ADMIN") is None


def test_the_translation_picks_the_page_that_holds_the_same_work():
    cases = {
        "/branch/support?tab=extensions": "/admin/approvals",
        "/branch/extensions": "/admin/approvals",
        "/branch/completion": "/admin/approvals",
        "/branch/attendance": "/admin/attendance",
        "/branch/batches/12": "/admin/batches/12",
        "/branch/recordings": "/admin/issues",
        "/branch": "/admin",
    }
    for link, expected in cases.items():
        assert role_links.for_role(link, "SUPER_ADMIN") == expected, link
    assert role_links.for_role("/branch/support?request=7", "FOUNDER_CEO") == "/founder/support?request=7"
    assert role_links.for_role("/admin/exceptions", "FOUNDER_CEO") == "/founder/issues"
    assert role_links.for_role("/founder/certificates", "SUPER_ADMIN") == "/admin/approvals"


def test_a_notification_carries_the_link_of_each_recipient(make_user):
    bm = make_user(roles=[("BRANCH_MANAGER", 1)], full_name="BM")
    admin = make_user(roles=[("SUPER_ADMIN", None)], full_name="SA")
    founder = make_user(roles=[("FOUNDER_CEO", None)], full_name="CEO")

    notify(category="Support", title="Escalated", event_key="role-links-1", link="/branch/support",
           recipient_user_ids=[bm.user_id, admin.user_id, founder.user_id])
    db.session.commit()

    links = dict(db.session.execute(select(Notification.recipient_user_id, Notification.link)).all())
    assert links == {bm.user_id: "/branch/support", admin.user_id: "/admin/support", founder.user_id: "/founder/support"}

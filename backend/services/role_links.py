"""Links that fit the person who opens them.

Notifications and record links are written once, usually with the Branch Manager's `/branch/*` screen in mind. The Super Admin and the
Founder / CEO have no Branch workspace (one role per account), so for them the same link is translated to a page under their own
prefix (`/admin/...` or `/founder/...`) that exists, never into a `/branch/*` page or the other central workspace.
"""
from urllib.parse import urlsplit

CENTRAL_PREFIX = {"SUPER_ADMIN": "/admin", "FOUNDER_CEO": "/founder"}

# `/branch/<page>` -> the central page that serves the same work (read-only views or the shared Approvals inbox)
FROM_BRANCH = {
    "support": "support",
    "progress": "attendance",
    "attendance": "attendance",
    "batches": "batches",
    "courses": "courses",
    "completion": "approvals",
    "certificates": "approvals",
    "requests": "approvals",
    "extensions": "approvals",
    "certificate-requests": "approvals",
    "payments": "setup",
    "schedule": "calendar",
    "issues": "issues",
    "reports": "reports",
    "notifications": "notifications",
    "waiting": "students",
}
# Pages that exist for one central role only, or moved: `<page>` under /admin or /founder -> the shared page
FROM_CENTRAL = {"exceptions": "issues", "integrations": "setup", "security": "setup", "certificates": "approvals", "access": "approvals"}


def for_role(link: str | None, role_code: str | None) -> str | None:
    """`link` as the role should open it; unchanged for every role but Super Admin and Founder / CEO."""
    prefix = CENTRAL_PREFIX.get(role_code or "")
    if not link or prefix is None or not link.startswith("/"):
        return link
    parts = urlsplit(link)
    segments = [s for s in parts.path.split("/") if s]
    if not segments or segments[0] not in ("branch", "admin", "founder"):
        return link
    area, rest = segments[0], segments[1:]
    if area == "branch":
        if not rest:
            return prefix + _suffix(parts)
        page = FROM_BRANCH.get(rest[0])
        if rest[0] == "support" and "tab=extensions" in parts.query:
            page = "approvals"
        if page is None:
            # Class day, recordings, results, content, meet operations...: branch work, the cross-branch list of what is wrong
            page = "issues"
            return f"{prefix}/{page}"
        tail = rest[1:] if rest[0] in ("batches", "courses") else []
        keep_query = rest[0] in ("support", "issues", "reports", "batches", "courses") and "tab=extensions" not in parts.query
        return "/".join([prefix, page, *tail]) + (_suffix(parts) if keep_query else "")
    # /admin/... <-> /founder/...
    if area == prefix.strip("/"):
        return link
    if rest and rest[0] in FROM_CENTRAL:
        rest = [FROM_CENTRAL[rest[0]]]
    return "/".join([prefix, *rest]) + _suffix(parts)


def _suffix(parts) -> str:
    return (f"?{parts.query}" if parts.query else "") + (f"#{parts.fragment}" if parts.fragment else "")

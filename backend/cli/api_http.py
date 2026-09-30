"""`flask --app app api-http`: rewrite backend/api.http from the Flask URL map (run after adding endpoints)."""
import re
from collections import defaultdict
from pathlib import Path

import click
from flask import current_app

# Machine endpoints called by the CRM with X-Service-Key instead of a user session
SERVICE_KEY_ENDPOINTS = {"crm.receive_event", "crm.get_status"}

HEADER = """# Nipuna LMS API — request collection (VS Code REST Client / JetBrains HTTP client).
# Generated from the Flask URL map (flask --app app api-http). Log in first, then paste the token into @token.
@base = http://127.0.0.1:5060
@token = paste-token-here
@service_key = dev-crm-service-key

### Log in (staff email, Student ID or student email)
POST {{base}}/api/v1/auth/login
Content-Type: application/json

{"login": "admin@nipuna.test", "password": "Nipuna-staging-1"}
"""


@click.command("api-http")
def api_http_command() -> None:
    """Write backend/api.http with one request per endpoint, grouped by blueprint."""
    groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:\w+:)?\w+>", "1", rule.rule)
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            groups[rule.endpoint.split(".")[0]].append((rule.endpoint, method, path))

    lines = [HEADER]
    for group in sorted(groups):
        lines.append(f"# ================================================================ {group}")
        for endpoint, method, path in sorted(groups[group]):
            auth = "X-Service-Key: {{service_key}}" if endpoint in SERVICE_KEY_ENDPOINTS else "Authorization: Bearer {{token}}"
            lines += [f"### {endpoint}", f"{method} {{{{base}}}}{path}", auth]
            if method in ("POST", "PATCH", "PUT"):
                lines += ["Content-Type: application/json", "", "{}"]
            lines.append("")

    target = Path(current_app.root_path) / "api.http"
    target.write_text("\n".join(lines))
    click.echo(f"Wrote {target} ({sum(len(v) for v in groups.values())} requests)")

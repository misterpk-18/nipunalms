# nipunalms

Nipuna LMS — the learning side of Nipuna Technologies (curriculum, batches, class sessions, content, recordings,
assignments, tests, attendance, progress, certificates, career support). The CRM (`nipuna-crm`) stays authoritative for
Admission and finance; the LMS receives admissions from it and shows read-only finance summaries.

| Folder | What it is |
|---|---|
| `backend/` | Flask API (routes → controllers → services → repositories → models), pytest suite, CLI |
| `frontend/` | React SPA (Vite + TanStack Router/Query), Playwright e2e tests |
| `db/` | Numbered SQL migrations — the source of truth for the schema |
| `deploy/` | Server templates: systemd unit, nginx site, crontab, backup script ([DEVELOPMENT.md Part F](docs/DEVELOPMENT.md#part-f--deployment)) |
| `docs/` | All project documentation — start with [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |

## Documentation

| Doc | What it covers |
|---|---|
| [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) | What the product does, as flowcharts: admission to first class, batches, a class day, attendance, work and tests, certificates, who decides what |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Start here: setup, databases, staging accounts, running and testing, the frontend, running with the local CRM, status, backlog and deployment |
| [docs/API.md](docs/API.md) | Backend architecture, conventions, domain model and every endpoint with its rules |
| [docs/DATABASE.md](docs/DATABASE.md) | Migrations and the rules the schema enforces |
| [docs/CRM_INTEGRATION.md](docs/CRM_INTEGRATION.md) | The LMS ↔ CRM contract, how each side runs it, open items and the history of the integration rounds |

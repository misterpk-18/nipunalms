# nipunalms

Nipuna LMS — the learning side of Nipuna Technologies (curriculum, batches, class sessions, content, recordings,
assignments, tests, attendance, progress, certificates, career support). The CRM (`nipuna-crm`) stays authoritative for
Admission and finance; the LMS receives admissions from it and shows read-only finance summaries.

| Folder | What it is |
|---|---|
| `backend/` | Flask API (routes → controllers → services → repositories → models), pytest suite, CLI |
| `frontend/` | React SPA (Vite + TanStack Router/Query), Playwright e2e tests |
| `db/` | Numbered SQL migrations — the source of truth for the schema |
| `prototype/` | Readable copy of the Lovable LMS prototype — reference only for layout and wording |
| `docs/` | All project documentation — start with [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |

## Documentation

| Doc | What it covers |
|---|---|
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Start here: setup, databases, staging accounts, running and testing, the frontend, running with the local CRM, status and backlog |
| [docs/API.md](docs/API.md) | Backend architecture, conventions, domain model and every endpoint with its rules |
| [docs/DATABASE.md](docs/DATABASE.md) | Migrations and the rules the schema enforces |
| [docs/CRM_INTEGRATION.md](docs/CRM_INTEGRATION.md) | The LMS ↔ CRM contract, the work on the CRM side, status and integration rounds |

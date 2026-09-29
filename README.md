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

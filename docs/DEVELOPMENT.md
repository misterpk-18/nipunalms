# Nipuna LMS — Development Guide

How to set up, run and test the LMS locally. Architecture and conventions: [API_PLAN.md](API_PLAN.md) (backend), [FRONTEND_PLAN.md](FRONTEND_PLAN.md) (frontend), [DB_PHASES.md](DB_PHASES.md) (schema).

---

## 1. Repository layout

```
nipunalms/
├── backend/      Flask API (routes → controllers → services → repositories → models), pytest suite, CLI
├── frontend/     React SPA (Vite + TanStack Router/Query), Playwright e2e tests
├── db/           Numbered SQL migrations — the source of truth for the schema
├── prototype/    Readable copy of the Lovable LMS prototype — reference only for layout and wording
├── docs/         All project documentation (this folder)
└── venv/         Python virtualenv
```

The layout, layers and conventions are the same as `nipuna-crm`.

## 2. Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` (uses the dev database), `test`, `production` |
| `DATABASE_URL` | Main database `nipunalms`; production config |
| `DEV_DATABASE_URL` | Dev replica `nipunalms-dev` with staging data; used when `APP_ENV=development` |
| `TEST_DATABASE_URL` | Optional; defaults to `DATABASE_URL` + `_test` (`nipunalms_test`) |
| `SECRET_KEY`, `LOG_LEVEL`, `UPLOAD_DIR` | App settings |
| `CRM_SERVICE_KEY` | Shared secret the CRM sends as `X-Service-Key` on `/integrations/crm/*` |
| `ANTHROPIC_API_KEY`, `AI_MODEL` | Ask Nipuna; without a key the rule-based fallback answers |

`backend/.env.example` lists the same variables without secrets.

## 3. Databases

| Database | Used by | Rules |
|---|---|---|
| `nipunalms` | Main database | Never used by local development or tests |
| `nipunalms-dev` | Local API + frontend + e2e tests | Rebuildable replica with staging data |
| `nipunalms_test` | pytest | Rebuilt from `db/*.sql` on every run |

Rebuild the dev replica and load staging data (from `backend/`):

```bash
APP_ENV=development ../venv/bin/flask --app app create-dev-db --yes   # drops and replays db/*.sql (refuses names not ending in -dev / _test)
APP_ENV=development ../venv/bin/flask --app app seed-dev              # staging data, created through the real services
```

The seed builds the prototype's sample world through the same code paths the CRM integration uses (`CourseUpserted`, `AdmissionQualified`, `FinanceSummaryUpdated` events): 11 staff accounts, the five sample courses (NIT-CRS-018 as a 3 + 1 combo with tracks T1–T3 and the Power BI booster), curriculum versions with modules and topics (NIT-CRS-052 deliberately has no active version → *Curriculum Mapping Pending*), five batches in both branches, the sample student **Anvitha K.** with her combo, separately purchased and complimentary enrolments, the other sample learners, class sessions for Sep–Oct 2026, finance summaries, one student in *Activation Pending* (its activation link is printed) and a failed CRM event for the retry screen. Later slices append their own seeders to `SEEDERS` in `backend/cli/seed.py`.

### Staging accounts

Also in [STAGING_ACCOUNTS.md](STAGING_ACCOUNTS.md). Password for all: **`Nipuna-staging-1`**. Student: `NIT-STU-2026-004182`. Staff: `founder`, `admin`, `bm.gnt`, `bm.vij`, `coordinator.gnt`, `coordinator.vij`, `trainer.g1`–`g3`, `trainer.v1`–`v2` at `@nipuna.test`.

## 4. Running

```bash
# API on :5060 (the CRM uses :5050; macOS AirPlay holds :5000)
cd backend
APP_ENV=development ../venv/bin/flask --app app run --port 5060

# Frontend on :5174 (proxies /api → 127.0.0.1:5060; override with VITE_API_TARGET)
cd frontend && npm install && npm run dev
```

Open http://localhost:5174 and sign in with a staging account.

Other backend commands (from `backend/`): `flask --app app create-admin` (first Super Admin on a fresh database), `flask --app app create-test-db`, `flask --app app crm-outbox list` (values waiting for the CRM), `flask --app app api-http` (regenerate `backend/api.http` after adding endpoints).

## 5. Testing

| Suite | Command | Notes |
|---|---|---|
| Backend | `cd backend && ../venv/bin/pytest -q` | Rebuilds `nipunalms_test`; each test runs in a rolled-back transaction |
| Frontend types | `cd frontend && npm run typecheck` | |
| Frontend build | `cd frontend && npm run build` | Type-check + production build into `dist/` |
| Lint | `cd frontend && npm run lint` | |
| End-to-end | `cd frontend && npx playwright test` | Needs the API (dev DB) and Vite running; desktop + `@mobile` projects |

E2E specs live in `frontend/e2e/`; `e2e/helpers.ts` has the staging users and `login()`. `E2E_BASE_URL` points Playwright at another Vite port. Run one Playwright process at a time (they share `test-results/`).

## 6. Docs to keep up to date

| When you… | Update |
|---|---|
| Add or change a migration | [DB_PHASES.md](DB_PHASES.md) (status table + section) |
| Add or change an endpoint | [API_PLAN.md](API_PLAN.md) (endpoint table + "As built"), `backend/api.http` |
| Change a screen or frontend convention | [FRONTEND_PLAN.md](FRONTEND_PLAN.md) |
| Find a gap or make a product decision | [BACKLOG.md](BACKLOG.md) |
| Change setup, environments or test commands | this file |

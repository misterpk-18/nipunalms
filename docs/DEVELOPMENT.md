# Nipuna LMS — Development

How to set up, run and test the LMS, how the frontend is built, how to run it against the local CRM, what is left to
clean up, and the backlog of open gaps and decisions.

| Part | What it covers |
|---|---|
| [A — Local development](#part-a--local-development) | Layout, `.env`, databases, seed and staging accounts, running, testing, which doc to update |
| [B — Frontend](#part-b--frontend) | Decisions, structure, shell, conventions, every screen and the API it uses |
| [C — Running with the local CRM](#part-c--running-with-the-local-crm) | Both systems on one laptop, the smoke test, checking received events |
| [D — Status and clean-up](#part-d--status-and-clean-up) | What is built, what is left to tidy |
| [E — Backlog](#part-e--backlog) | Open product decisions and gaps found while building |
| [F — Deployment](#part-f--deployment) | The server templates in `deploy/`: API service, nginx, cron jobs, backups, redeploy and migrations |

The other docs: [API.md](API.md) (backend architecture, conventions, every endpoint), [DATABASE.md](DATABASE.md)
(migrations and schema rules), [CRM_INTEGRATION.md](CRM_INTEGRATION.md) (the LMS ↔ CRM contract),
[GAP_FIX_PLAN.md](GAP_FIX_PLAN.md) and [GAPS.md](GAPS.md) (the gaps against the approved modules and the plan to close them).

---

## Part A — Local development

### 1. Repository layout

```
nipunalms/
├── backend/          Flask API (routes → controllers → services → repositories → models), pytest suite, CLI
├── frontend/         React SPA (Vite + TanStack Router/Query), Playwright e2e tests
├── db/               Numbered SQL migrations — the source of truth for the schema
├── deploy/           Server templates: systemd unit, nginx site, crontab, backup script (Part F)
├── prototype/        Readable copy of the Lovable LMS prototype — reference only for layout and wording
├── docs/             The project docs (this folder) and the content data request (PDF)
├── nipuna crm-docs/  Only while a CRM integration round is open: the round's brief, replies and test results (see
│                     CRM_INTEGRATION.md §5; deleted once the round is recorded there)
└── venv/             Python virtualenv
```

The layout, layers and conventions are the same as `nipuna-crm`.

### 2. Configuration (`backend/.env`)

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development` (uses the dev database), `test`, `production` |
| `DATABASE_URL` | Main database `nipunalms`; production config |
| `DEV_DATABASE_URL` | Dev replica `nipunalms-dev` with staging data; used when `APP_ENV=development` |
| `TEST_DATABASE_URL` | Optional; defaults to `DATABASE_URL` + `_test` (`nipunalms_test`) |
| `SECRET_KEY`, `LOG_LEVEL`, `UPLOAD_DIR` | App settings |
| `PUBLIC_BASE_URL` | Optional. The address people open the LMS at (for example `https://lms.example.com`). Certificate PDFs print `<it>/verify/<number>` with a QR code; unset = the PDF names the number and the `/verify/` path only |
| `CRM_BASE_URL` | Optional. The CRM API base (dev `http://127.0.0.1:5050/api/v1`) the LMS hands WhatsApp messages to (`POST /lms/whatsapp`, same service key). Unset = WhatsApp not available. Turn it on with `app_settings.whatsapp_enabled` and `whatsapp_approved_templates` (`flask whatsapp status` shows why it is off) |
| `CRM_SERVICE_KEY` | Shared secret the CRM sends as `X-Service-Key` on `/integrations/crm/*` (dev: `dev-crm-service-key`) |
| `ANTHROPIC_API_KEY`, `AI_MODEL` | Ask Nipuna; without a key the rule-based fallback answers |

`backend/.env.example` lists the same variables without secrets.

### 3. Databases

| Database | Used by | Rules |
|---|---|---|
| `nipunalms` | Main database | Never used by local development or tests |
| `nipunalms-dev` | Local API + frontend + e2e tests + the local CRM's events | Rebuildable replica with staging data |
| `nipunalms_test` | pytest | Rebuilt from `db/*.sql` on every run |

Rebuild the dev replica and load staging data (from `backend/`):

```bash
APP_ENV=development ../venv/bin/flask --app app create-dev-db --yes   # drops and replays db/*.sql (refuses names not ending in -dev / _test)
APP_ENV=development ../venv/bin/flask --app app seed-dev              # staging data, created through the real services
```

Rebuilding drops every event the local CRM has sent; ask the CRM side to run `flask lms backfill --force` afterwards
(Part C). **Tell the CRM before you rebuild:** a rebuild re-issues student codes (`NIT-STU-…`) to different people, while
the CRM's persons still hold the old ones as `lms_user_id`. The next pull then holds records on a duplicate `lms_user_id`
until the CRM clears its stale ids (round 5 hit this with 12 persons). When the CRM's test data must survive, apply a new migration in place instead:
`psql -d nipunalms-dev -v ON_ERROR_STOP=1 -1 -f db/<file>.sql`.

`nipunalms-dev` is shared by the local CRM, so it is **not** the place for a clean e2e run: CRM joint tests (curricula
activated, finance snapshots, extra batches) and earlier e2e runs leave data behind, and a few delivery and dashboard
specs fail on it. For a clean baseline use a **scratch database** (UX phase U18), which never touches `nipunalms-dev`:

```bash
# from backend/ — the name must end in -dev (create-dev-db refuses anything else); DEV_DATABASE_URL overrides .env
createdb nipunalms_sweeptpl-dev
export APP_ENV=development DEV_DATABASE_URL=postgresql+psycopg://<you>@localhost:5432/nipunalms_sweeptpl-dev WHATSAPP_API_URL= WHATSAPP_API_KEY= WHATSAPP_TEST_NUMBERS=
../venv/bin/flask --app app create-dev-db --yes && ../venv/bin/flask --app app seed-dev   # the pristine template
# before every spec file: copy the template, then run a temporary API on :5061 against the copy
dropdb --force nipunalms_sweep-dev; createdb -T nipunalms_sweeptpl-dev nipunalms_sweep-dev
DEV_DATABASE_URL=postgresql+psycopg://<you>@localhost:5432/nipunalms_sweep-dev ../venv/bin/flask --app app run --port 5061
# frontend/: VITE_API_TARGET=http://127.0.0.1:5061 npx vite --port 5175 --strictPort, then
# E2E_BASE_URL=http://localhost:5175 npx playwright test e2e/<spec>
```

The `WHATSAPP_*` overrides keep the temporary API from sending anything to the real test number. `e2e/handouts.spec.ts` inserts a split-account row with `psql`, so run it with `E2E_DB_NAME=nipunalms_sweep-dev` (it skips without it). Drop both scratch
databases and stop the two servers when done. Never use :5060 / :5174 (the owner's servers).

### Batches for the CRM's own students

`seed-dev` batches are `seed_data` and stay out of the CRM pull. When `nipunalms-dev` instead holds what the CRM sent
(`flask lms backfill` on the CRM side), give those students real batches with:

```bash
APP_ENV=development ../venv/bin/flask --app app seed-crm-batches
```

One confirmed, Ready Classroom batch per course and branch with students waiting (timetable, location, lead trainer),
plus `bm.<branch>` and `trainer.<branch>` logins (`Nipuna-staging-1`) when missing. It allocates nobody; a Branch
Manager does that on the "Waiting for a batch" screen. Running it again only adds what is missing. `*-dev` only.

### 4. Staging data

`seed-dev` builds the prototype's sample world through the same code paths the CRM integration uses (`CourseUpserted`,
`AdmissionQualified`, `FinanceSummaryUpdated` events):

- 10 staff accounts, one role each (including `bm.multi@nipuna.test`, a Branch Manager of both branches for the branch picker), plus the two deactivated former Academic Coordinators.
- The CRM's eight courses (codes, titles and categories as in the CRM, all single courses) plus the seed-only combo
  **NIT-CRS-900** (3 + 1: tracks T1–T3 and the Power BI booster NIT-CRS-019; the CRM has no combo yet).
- A course outline (modules and topics on the course itself; there are no curriculum versions) for every course except
  NIT-CRS-028 and NIT-CRS-052. NIT-CRS-052 has no outline yet, so its enrolments are allocatable and its batch
  (NIT-GNT-BAT-2026-000003) shows "No course outline yet" until a Super Admin or Founder builds one on `/admin/courses`.
- Five batches across both branches and class sessions for Sep–Oct 2026, with display names, type and pattern, verified
  capacity and recording provision; a sixth, the weekend Java batch NIT-GNT-BAT-2026-000004, is **Proposed** and waits for
  the Guntur Branch Manager's confirmation.
- Phase 6 samples: G1's afternoon timetable change waiting for its students' agreement (Anvitha has not answered), a
  capacity request on G2, a transfer request into the weekend batch, a replacement for the cancelled Vijayawada class
  waiting for approval, a substitute cover request, a backup host on an online class, an open connection-failure
  disruption, and Anvitha's waitlisted Saturday slot request.
- The sample student **Anvitha K.** with her combo, separately purchased and complimentary enrolments, and the other
  sample learners.
- Finance summaries, one student in *Activation Pending* (its activation link is printed) and a failed CRM event for
  the retry screen.
- Learners A and F (completed) get Joining Dates 2025-06-10 and 2024-08-19, so EXT-032 / EXT-033 show a request after
  the first / second anniversary. Assignment asg-11 is due 02 Oct 2026 (prototype: 29 Sep) so it reads Due, not
  Overdue.

Every seeded student, admission and batch is marked `seed_data` (its CRM IDs are made up), so
`GET /integrations/crm/status` leaves them out. New seeders are appended to `SEEDERS` in `backend/cli/seed.py`.

### Staging accounts

Created by `seed-dev` in `nipunalms-dev`. **Never use these in production.** Password for every account:
**`Nipuna-staging-1`**.

| Role | Guntur (NIT-GNT, branch 1) | Vijayawada (NIT-VIJ, branch 2) |
|---|---|---|
| Founder / CEO | `founder@nipuna.test` (company-wide) | |
| Super Admin | `admin@nipuna.test` (company-wide) | |
| Branch Manager | `bm.gnt@nipuna.test` | `bm.vij@nipuna.test` |
| Branch Manager of both branches | `bm.multi@nipuna.test`: after sign-in it shows "Choose a branch" (Guntur or Vijayawada); the header then reads `Branch Manager · <branch>` and "Change branch" in the account menu returns to the picker | |
| Trainer | `trainer.g1@nipuna.test` (Trainer R. Sample), `trainer.g2@nipuna.test` (Trainer M. Demo), `trainer.g3@nipuna.test` (Trainer K. Sample) | `trainer.v1@nipuna.test` (Trainer S. Example), `trainer.v2@nipuna.test` (Trainer P. Demo) |

**One account per role** (role separation, db 118–119): a login carries exactly one role, and the database refuses a second active role on one user (trigger `check_one_role_per_user`). Every staging user above already holds a single role, so no staging user needed splitting. On a database that had multi-role users, `db/118` kept the highest role on the existing account and created `name.<role>@…` accounts for the rest; Users & access has the hand-out section that lists them and issues their one-time activation links. To test one person with two roles, create two accounts with different emails.

The two former Academic Coordinator accounts (`coordinator.gnt@nipuna.test`, `coordinator.vij@nipuna.test`) exist only as **deactivated** examples: the role was merged into the Branch Manager (UX phase U2, db 106).

Students sign in with their **Student ID** (or email, when they have one) — never a mobile number.

| Student ID | Name | State |
|---|---|---|
| `NIT-STU-2026-004182` | Anvitha K. | Activated — the prototype's sample student (combo, separately purchased and complimentary enrolments) |
| `NIT-STU-2026-004183`…`004185` | Sample Learners G, H, I | Activated |
| `NIT-STU-2026-004186` | Sample Learner J. | **Activation Pending** — `seed-dev` prints its one-time link `/activate?token=…` |
| `NIT-STU-2026-004187`… | Sample Learners A–F, K (waiting for a Power BI batch) and batch fillers | Activated |

### 5. Running

```bash
# API on :5060 (the CRM uses :5050; macOS AirPlay holds :5000)
cd backend
APP_ENV=development ../venv/bin/flask --app app run --port 5060

# Frontend on :5174 (proxies /api → 127.0.0.1:5060; override with VITE_API_TARGET)
cd frontend && npm install && npm run dev
```

Open http://localhost:5174 and sign in with a staging account.

Other backend commands (from `backend/`, prefix `APP_ENV=development ../venv/bin/flask --app app`):

| Command | What it does |
|---|---|
| `create-admin` | First Super Admin on a fresh database |
| `create-test-db` | Rebuild `nipunalms_test` by hand |
| `crm-outbox list` | Values queued in the LMS outbox (not delivered: the CRM pulls instead) |
| `jobs list`, `jobs run [name] [--loop]` | Background jobs (`services/jobs.JOBS`): `recording-check`, `support-escalate-overdue`, `allocation-escalation`, `attempts-expire`, `attendance-unconfirmed`, `session-delay-check`, `class-log-check`, `class-reminders`, `whatsapp-send`. Each run is recorded in `job_runs`. Locally, `jobs run --loop` (every 60 s, `--interval` to change) stands in for cron |
| `seed-crm-batches` | Batches (and `bm.*` / `trainer.*` logins) for the students the CRM sent; `*-dev` only, allocates nobody ([details](#batches-for-the-crms-own-students)) |
| `api-http` | Regenerate `backend/api.http` after adding endpoints |

### 6. Testing

| Suite | Command | Notes |
|---|---|---|
| Backend | `cd backend && ../venv/bin/pytest -q` | Rebuilds `nipunalms_test`; each test runs in a rolled-back transaction |
| Frontend types | `cd frontend && npm run typecheck` | |
| Frontend build | `cd frontend && npm run build` | Type-check + production build into `dist/` |
| Lint | `cd frontend && npm run lint` | |
| End-to-end | `cd frontend && npx playwright test` (or `npm run e2e`) | Needs the API (dev DB) and Vite running; desktop + `@mobile` projects |

E2E specs live in `frontend/e2e/` (one per area: `shell` (one nav per account, cross-role denial, branch picker, Founder bell), `sign-in`, `admin`, `admin-u17`, `delivery`, `batch-operations`, `content`, `assessments`,
`attendance`, `services`, `calendar`, `governance`, `student-u10`, `student-u11`, `trainer-u12`, `trainer-u13`, `branch-u14`, `branch-u15`,
`founder-u16`, `dashboards-learning`, `dashboards-staff`, `staff-account`, and `sweep-u18`); `e2e/helpers.ts` has the staging users and
`login()`. `sweep-u18` is the final sweep: it opens every link of every role's navigation at desktop and phone width, in light and
dark mode (no server error, a heading, no leftover spec wording, no sideways scroll, badge contrast, an active nav item), and walks the
student's Join and recording and the Branch Manager's completion decision. Tests that change data assume a freshly seeded database,
and several are serial chains: **run one spec file per fresh database** (see "Databases" above), because earlier files leave classes,
requests and approvals behind (for example `trainer-u12` cannot schedule a class when an earlier file booked the trainer at that
minute). The trainer specs (`trainer-u12`, and the Today and register steps of `dashboards-learning`, `delivery`, `attendance`) schedule a class for today
through the API, so it is skipped within ten minutes of midnight IST. `E2E_BASE_URL` points Playwright at another Vite
port. `admin-u17` locks `trainer.g3@nipuna.test` by failing six sign-ins and unlocks it again through the Users screen, and adds one holiday that it cancels (the cancelled entry stays in the calendar list); the AI switch it flips is restored in the same test. Run one Playwright process at a time (they share `test-results/`).

### 7. Docs to keep up to date

| When you… | Update |
|---|---|
| Add or change a migration | [DATABASE.md](DATABASE.md) (status table + a section) |
| Add or change an endpoint | [API.md](API.md) (endpoint table + rules), `backend/api.http` |
| Change what the LMS accepts from or sends to the CRM | [CRM_INTEGRATION.md](CRM_INTEGRATION.md) §2 and §4 |
| Change a screen or frontend convention | Part B of this file |
| Find a gap or make a product decision | Part E of this file |
| Change setup, environments or test commands | Part A of this file |

---

## Part B — Frontend

React SPA in `frontend/`, built to mirror **nipuna-crm/frontend**. The product is the approved interactive prototype
(https://nipuna-lms-prototype.lovable.app/, readable copy in `prototype/reference/`); the API is in [API.md](API.md).

### 1. Decisions

| Decision | Choice | Why |
|---|---|---|
| Stack | Vite 8, React 19, TanStack Router (file routes, auto code splitting), TanStack Query, shadcn `new-york` + Radix, Tailwind 4, react-hook-form + zod, sonner toasts | Identical to the CRM; a change to one repo can be copied to the other |
| Dev ports | SPA `:5174` (preview `:4174`), API `:5060` via Vite proxy `/api` (`VITE_API_TARGET` overrides) | CRM uses 5173 / 5050; both stacks can run side by side. No CORS |
| Workspace from URL | `workspaceForPath(path)` — `/trainer*` trainer, `/branch*` branch, `/admin*` admin, `/founder*` founder, everything else student (except `/login`, `/activate`, `/change-password`; `/account/*` has no workspace of its own and is framed by the user's home workspace) | Same rule as the prototype |
| Who may open a workspace | `profile.workspaces` from `/auth/me` (exactly one workspace: the account's role; no role expands to another); `canOpen(workspaces, workspace)` | The API is the authority; the SPA never derives access from role codes |
| Guard | Root route: public paths (`/login`, `/activate`) → anonymous → `/login?redirect=` → `must_change_password` → `/change-password` → workspace not permitted → **Permission Restricted** view (link home) → `/` redirects to `home_route`. Not a security boundary; every endpoint re-checks scope | Same as the CRM |
| Static role label, no "Acting as" | Header shows a static `Role · Branch` label (Super Admin and Founder: `Role · All branches`). One account has one role (role separation); a Branch Manager with several branches picks the branch on the sign-in screen (`components/lms/branch-pick.tsx`, `POST /auth/branch`) and the branch is fixed on the session; the account menu has "Change branch" (`POST /auth/change-branch`, back to sign-in). Pages read `useAuth().branchId`; nav counts and the Getting started card take role and branch from the session | The "Acting as" switcher and the `localStorage` branch pick are removed (R4) |
| Navigation | `NavItem` has `group` (heading in the sidebar and the More sheet) and `badgeKey` (the count shown from `GET /me/nav-counts`, polled every minute). The count is a visual badge plus a screen-reader description outside the link, so a link's name stays the page name. Trainer, Branch Manager, Super Admin and Founder navs are grouped; the student nav is Home · My Learning · Schedule · Tasks & Tests · Class Materials · My Progress · Certificates · Career · Ask Nipuna · Support (Fees & Receipts and Profile are tabs of **My Account**, opened from the avatar menu and the phone More sheet) | One place that says what waits for you |
| Search | Ctrl/Cmd+K or the header search button opens `command-palette.tsx`: the pages of the account's own workspace, plus `GET /search` records (students, batches, certificates) within scope. A record opens the list that holds it in the current workspace (record pages arrive with their screens) | Find a screen or a person without remembering where it is |
| Getting started | `getting-started.tsx` on the Student, Trainer, Branch Manager and Super Admin homes, from `GET /me/getting-started`; hidden once every step is done; dismissal kept in `localStorage` | First-run guidance that ticks itself |
| Session | Bearer token in memory + `sessionStorage` (`nipuna-lms-session`); `["me"]` query holds the profile; `FRESH_AUTH_REQUIRED` opens a password dialog and retries once | Same as the CRM |
| Language | `en` / `te`, dictionary in `src/lib/i18n.ts`; choice stored per user in `localStorage` (`nipuna-lms-lang:<user_id>`), default `profile.student.preferred_language`; sets `<html lang>` (Telugu switches font and line height). Only student-workspace labels and the sign-in / activation screens are translated | Same scope as the prototype |
| Look | Prototype tokens (navy header, blue primary, tone colours) as CSS variables mapped onto shadcn variables; IBM Plex Sans + Noto Sans Telugu; `.tap` = 44px touch target | Visual parity with the approved prototype |
| Phones | Sidebar hidden below `md`; 5-slot bottom bar (4 items + More bottom sheet); `DataTable` turns into labelled cards | Prototype behaviour; e2e checks no horizontal scroll at 360px |
| Routes vs features | One thin route file per prototype route imports a feature component from `src/features/<workspace>/` | Screens change feature files, never route files or the shell |
| Formatting | Prettier via ESLint, `printWidth: 160` (`.prettierrc.json`) | Matches the CRM's long-line style |

### 2. Structure

```
frontend/
├── index.html                 title "Nipuna LMS", IBM Plex Sans + Noto Sans Telugu
├── vite.config.ts             ports 5174 / 4174, /api proxy → :5060
├── playwright.config.ts       desktop + @mobile projects, baseURL :5174
├── e2e/                       helpers.ts (staging users, login()) + one spec per area
└── src/
    ├── main.tsx               QueryClient, router, AuthProvider
    ├── styles.css             Tailwind 4 theme + prototype tokens, .tap, :lang(te)
    ├── api/                   client.ts (fetch wrapper: ApiError, bearer token, get / post / patch / put / del / list / upload / download),
    │                          types.ts, auth.ts, and one file per domain (delivery, content, assessments, support, notifications,
    │                          career, profile, ask-nipuna, admin, dashboards, exceptions, …)
    ├── auth/                  auth.tsx (AuthProvider, useAuth(), fresh-auth dialog), access.ts (workspaceForPath, canOpen, NAV, mobileBarItems) (`useAuth()` also gives `workspace`, `branchId`, `allowedBranches`, `selectBranch`, `changeBranch`)
    ├── lib/                   i18n.ts (dictionary, useT, useLanguage), mutation.ts (useApiMutation), format.ts (IST helpers, formatMoney), utils.ts (cn)
    ├── hooks/                 use-mobile.tsx
    ├── components/
    │   ├── ui/                shadcn primitives (copied from the CRM)
    │   └── lms/               app-shell, branch-pick, command-palette, getting-started, ui, forms, auth-page, language-toggle, password-field
    ├── routes/                thin file routes (see §5)
    └── features/              student/ trainer/ academic/ branch/ admin/ founder/ shared/
```

Route file naming follows the CRM. `assignments` and `tests` use `assignments.index.tsx` + `assignments.$id.tsx` so the
list and the detail are siblings (no `<Outlet>`); `courses.$enrolmentId_.tracks.$trackId.tsx` (trailing underscore)
keeps the track screen out of the enrolment route's nesting for the same reason.

### 3. Shell and theme

**Header** (navy, sticky): logo → `home_route`; static `Role · Branch` label (Super Admin and Founder: `Role · All branches`); the search button (Ctrl/Cmd+K); language toggle (student workspace);
notifications bell (`notification-bell.tsx`) counting what is new or needs action, with a preview of the latest five and "Open inbox"
(student → `/notifications`, trainer / branch / admin → `<workspace>/notifications`; the founder has none: their inbox and the nav counts stand in);
account menu (My Account — `/my-account` for students, Profile at `/account/profile` for staff — Change password, Sign out).

**Sidebar** (≥ `md`, 240px): the workspace's nav list from `NAV` in `auth/access.ts`, grouped under headings, with a count badge on items that
have work waiting (`GET /me/nav-counts`, `badgeKey`). There is no Notifications item: the bell holds it. Student labels come from the
dictionary. **Bottom bar** (< `md`): four pinned items (`mobileBarItems`) + **More** bottom sheet with the rest of the list.

| Role | Navigation (group: items) |
|---|---|
| Student | Home · My Learning · Schedule · Tasks & Tests · Class Materials · My Progress · Certificates · Career · Ask Nipuna · Support. The avatar menu holds My Account (Profile, Fees & Receipts), Change password and Sign out |
| Trainer | Teach: Today, Class schedule, Attendance, Holidays & closures, My requests, My uploads · Grade: To grade, Assignments, Assessments · People: Batches, Students, Course completion, Support · Insights: Reports, Ask Nipuna |
| Branch Manager | Today: My work, Class day · Batches & students: Batches, Waiting for a batch, Schedule & calendar, Attendance & progress (`/branch/attendance`) · Teaching: Courses, Content review, Question approvals, Marks & results, Recordings · Completion: Completion & certificates, Certificate requests · Help: Student support, Access extensions, Issues · Branch: Reports, Payment instructions |
| Founder | Home (the inbox) · Approvals · Company: Courses · People: Staff accounts, Student accounts · Operations: Batches, Attendance, Issues, Reports, Academic calendar, Support · System: CRM sync, Setup & health, AI controls, Audit log |
| Super Admin | Home · Approvals · People: Staff accounts, Student accounts · Operations: Batches, Attendance, Support, Reports, Issues, Academic calendar · Academic: Courses · System: CRM sync, Setup & health, AI controls, Audit log |

One account has one role, so the sidebar shows only that role's workspace (no role switcher). The Academic
Coordinator workspace no longer exists: it was merged into the Branch Manager's (db 106) and `/academic/*` redirects to `/branch/*`.

**Theme** (`src/styles.css`): the prototype's oklch tokens — `--navy`, `--navy-foreground`, `--navy-muted`, `--primary`,
`--accent`, tone pairs `--success|warning|danger|info|neutral` (+ `-soft`), `--radius: 0.625rem` — mapped onto shadcn's
`--background/--card/--border/…`. Tone utilities: `bg-success-soft text-success`, etc. A `.dark` token block follows the system
setting (`main.tsx` toggles the class on `<html>` and listens for changes); status tones keep their meaning in both modes.

**Shared components** (`components/lms/`), the design system every screen reuses (UX phase U3):
- `ui.tsx`: `PageHead` (also sets `document.title`), `Section`, `Grid`, `Note`, `KeyValue`, `StatusBadge` (a dictionary status),
  `Tag` (a label that is not a status, with an explicit tone), `StatusNote` (info / success / warning / danger message),
  `DataTable` (table → cards), `PillTabs`, `QueryView` (skeleton while loading, error, `EmptyState` when empty), `LoadingSkeleton`.
- One file each: `EmptyState` (reason + next action), `ConfirmDialog` (title + a one-line consequence; use it before anything
  that cannot be undone or that students will see), `HowThisWorks` (policy text, collapsed), `Breadcrumbs`, `NeedsYouList`
  (rows of what / where / age / button for a home screen), `StepBar` (ordered setup steps and the next action).
- `forms.tsx`: `Field`, `NativeSelect`, `applyServerErrors`, `cleanBody`. `features/shared/reason-dialog` asks for a written
  reason (minimum length shown, destructive variant).
- `lib/mutation.ts` `useApiMutation` toasts say what happened, an optional `next` line says what happens next and
  `view: { to, label }` adds a "View" link to the changed item.

**The status dictionary** (`lib/status.ts`): `STATUS[domain][code] = { label, tone, help }` and `statusInfo(domain, code)`. Every
status on screen is `<StatusBadge domain="…" code={…} />`: the colour, the plain label and the tooltip ("what it means / what to
do") come from the dictionary, never from the text. Use `label=` only when the API sends a richer label (an attendance entry
with its recovery). An unknown code shows its own text in grey and warns once in development: add it to the dictionary.

**Shared feature parts** (`features/shared/`): `notification-centre` (the inbox and the `NotificationRow` the bell reuses), `notification-preferences` (on My Account / the staff Profile; `translated` for students), `staff-profile`, `assistant` (Ask Nipuna, student and trainer), `support-desk` (staff), `support-attachments` (`FilePicker`, `AttachmentLinks`),
`reason-dialog`, `certificate-register`, `attendance-parts` (`MeasureCards`, `Meter`), `content-detail`, `delivery-ui`
(IST `fmtDate` / `fmtRange`, DeliveryBar, MeetBadge, field-driven `ActionDialog`), `sessions`, `dashboard-parts`
(`Tile`, `CrmTile`, `TileRow`, `QuickLinks`, `CardGap`), `recovery-step` (`RecoveryStepButton`, `OwnerCell`,
`ItemCell`), `format.ts` (plain date forms, `percent`, `ageText`).

### 4. Conventions

**Add an API file** — `src/api/<domain>.ts`: export the response types and an object of calls built on
`get / list / post / patch / del` from `client.ts` (paths without `/api/v1`). Query keys start with the domain:
`["enrolments", "list", params]`. Mutations use `useApiMutation(fn, { success, invalidate: [["enrolments"]] })`.

**Build a feature** — put screens, tables and forms in `src/features/<workspace>/`. Fetch with `useQuery` and render
with `<QueryView query={q}>{(data) => …}</QueryView>`; lists use `DataTable` (or `list()` + pagination meta); forms use
react-hook-form with `applyServerErrors(form, error)` in the mutation's `onError`. Student-facing strings that must be
bilingual go into `DICTIONARY` in `lib/i18n.ts` and are read with `useT()`; staff screens stay English. Route params:
`const { enrolmentId } = useParams({ from: "/courses/$enrolmentId" })`. A new route needs a route file, a nav entry in
`access.ts` and a row in §5.

**Status wording** — a list with nothing in it is an `EmptyState` that says why and offers the next action; loading is a
skeleton; partial, restricted or failed data is a `StatusNote` with a tone; a row status is a `StatusBadge`; anything that is
only a label (a kind, a role, a count) is a `Tag`. A figure with nothing behind it shows "Not available" / "Not connected" /
"Out of date", never 0. Policy and rule text goes in `HowThisWorks`, not in the page description.

**Tests** — one Playwright spec per area in `e2e/`, logging in with `login(page, USERS.<role>)`; desktop plus a
`@mobile` check for new screens.

### 5. Screens → API

#### Public and account

| Route | Feature | API | Notes |
|---|---|---|---|
| `/login` | auth page | `POST /auth/login` | Student ID / student email / staff email + password, show / hide password, forgot-password guidance ("Ask your branch to reissue an activation link"), activation-state explanation, EN/తెలుగు |
| `/activate?token=` | auth page | `GET /auth/activation/{token}`, `POST /auth/activate` | Checks the token (valid / expired / used), set + confirm password, success → `/login` |
| `/change-password` | auth page | `POST /auth/change-password` | Forced when `must_change_password`, also from the account menu |
| `/account/profile` | `shared/staff-profile` | `GET /me/profile` | Staff: role, branch, devices, password, last sign-in; read-only. Framed by the user's home workspace |
| `/` | — | `GET /auth/me` | Never renders: redirects to `home_route` |

#### Student (`features/student/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/dashboard` | `dashboard` | `/me/home` | **Home**: the **Up next** hero (live class, then work due today or overdue, then the next topic, then the next class) with one button; four cards (Due work, Continue learning, Latest recording, Attendance); a batch-change banner with Agree / Decline behind a confirm and the reply-by date; the preferred-slot request only while a course waits for a batch; the Getting started card. Career, Support, Ask Nipuna and Certificates are in the nav, not on Home. A card with nothing to show says why (`CardGap`) |
| `/my-courses` | `my-courses`, `batch-changes` | `/me/enrolments`, `/me/material-changes`, `/me/slot-options`, `/me/slot-preferences` | Enrolment cards with gate / delivery state; changes needing the student's agreement (Agree / Decline; reading a notice is not agreement); the preferred-slot request and its status (a request reserves no seat) |
| `/courses/$enrolmentId` | `course-detail` | `/me/enrolments/{id}` | Programme, combo tracks and booster, modules with delivery progress |
| `/courses/$enrolmentId/tracks/$trackId` | `track-detail` | `/me/enrolments/{id}/tracks/{track_id}` | |
| `/modules/$moduleId`, `/topics/$topicId` | `module-detail`, `topic-detail` | `/modules/{id}`, `/topics/{id}`, `/me/resources?topic_id=` | Topics, classes, resources and recordings |
| `/sessions/$sessionId` | `session-detail` | `/class-sessions/{id}`, `/me/recordings?session_id=` | Class page with Meet join state |
| `/schedule` | `schedule`, `class-time` | `/me/schedule` | Coming up grouped Today / Tomorrow / This week / Later with plain states (Live now, Starts in 2 h, Link not ready, Cancelled, Moved); the Join button shows 15 minutes before and is highlighted when live (the page refetches every 30 s). Past tab (`?past=1`): attendance and recording link per class. Session page: `session-detail` |
| `/tasks` | `tasks` | `/me/work` | **Tasks & Tests**: To do / Waiting for review / Done tabs with counts, overdue first. `/assignments` and `/tests` (the lists) redirect here |
| `/assignments/$id` | `assignment-detail` | `/assignments/{id}`, `/assignments/{id}/submissions` | Leads with the brief; a Submit button beside the title jumps to the form. Text / link / file; the window explains replace vs resubmit |
| `/tests/$id` | `test-detail` | `/tests`, `/tests/{id}/attempts`, `/attempts/{id}/answers`, `/attempts/{id}/submit`, interview slots | Start asks first (minutes, no pause, attempts left); submit warns of unanswered questions; a question navigator marks answered and flagged (flags live in the page only). Autosave every 10 s; the timer counts down to the server's `deadline_at`, corrected for clock skew. After submitting: receipt, Back to tasks, and where the result will appear (Results) |
| `/materials` | `materials`, `access-window` | `/me/recordings`, `/me/resources`, `/me/access`, `/recordings/{id}/watch`, `/content-items/{id}/open`, `/access-extension-requests` | **Class Materials**: tabs Recordings / Files (`?tab=files`), grouped by course then topic (or week for a recording with no topic). Recordings are video cards (Watch, status, "Watch only, no download"); files are rows (Open / Download; filters by course, type, title). One access line per course ("Available until 12 Jan 2027 · Request extension"); the extension dialog lives here; the rules are in "How access works". `/recordings` and `/resources` redirect here |
| `/progress` | `progress`, `attendance`, `results` | `/me/progress`, `/me/progress/next-steps`, `/me/attendance`, `/attendance/recoveries`, `/attendance/corrections`, `/me/results` | **My Progress**: tabs Overview · Attendance · Results (`?tab=`). Overview: "What to do next" then four separate measure cards (course tabs when several enrolments). Attendance: a table per course; **Request recovery** only on an Absent row without one, **Report a mistake** in the row menu, and the row shows each request's status, who decides and the decision note. Results: a row links to the assignment or test (feedback is there); a score shows only once published. `/attendance` and `/results` redirect here |
| `/certificates` | `certificates` | `/me/certificates`, `/me/certificates/{id}/pdf` | One card per course with the 3-step tracker (Course completed → Review → Issued), the blocker in plain words, a fee banner linked to Fees, and, once issued, **Download PDF** and **Copy verification link** |
| `/career` | `career` | `/me/career/*` | A four-step checklist on top (Opt in → Profile → CV reviewed → Share with employers, from `steps`); Apply is disabled with "Needs: …" linking to the step (`apply_needs`); the no-guarantee note sits under Jobs for you; profile editor, CV upload / versions / download, opportunities, applications with Withdraw, outcomes |
| `/ask-nipuna` | `shared/assistant` | `/ask-nipuna/*` | Chat thread oldest first with the box pinned under it; quick actions pre-fill the box and never override typed text; sources are links; quota shown from 80% used; an answer with `answered: false` is tagged "Can't answer this" and offers "Raise a support request with this question" (opens `/support?new=1` filled in). The trainer variant (`/trainer/ask-nipuna`) has trainer example prompts |
| `/support` | `support` | `/support-requests` | Requests waiting on the student first with a badge and a banner; guided form (subject, help per category, up to 3 attachments) that opens the new request. `?new=1&category=&subject=&details=` opens the form filled in. `/support/$requestId` (`support-request`): breadcrumbs, thread (the student's own lines say "You"), reply with files, confirm and close, reopen |
| `/notifications` | `shared/notification-centre` | `/notifications/*` | Inbox: tabs Needs action (first when any, with a count) · All · Done; one status (New / Needs action / Done) and one button per item; mark as done / read. Reached from the bell, not the sidebar. Preferences are on My Account |
| `/my-account` | `account` | `/me/profile`, `/me/email/*`, `/me/finance`, `/me/finance/receipts/…/pdf` | **My Account**, tabs Profile · Fees & Receipts (`?tab=fees`). Profile: identity with masked mobile ("Contact your branch" for everything but the email), add or change email with a WhatsApp code, language, notification preferences, devices, password and recovery. Fees: the **Next payment** card (amount, date, overdue in red, how to pay from the branch setting), per course fee / paid / dues with a **Download PDF** per receipt, the instalment schedule once per invoice. `/profile` and `/finance` redirect here |

#### Trainer (`features/trainer/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/trainer` (`?session=<id>`) | `today`, `class-flow` | `/trainer/today`, `/class-sessions/{id}/flow` | The only way to run a class. "Next up" class expanded with its flow (Start class → Join → Attendance → Class log; progress and the draft log saved on the server so a refresh resumes), the others compact, finished ones collapsed; "No Meet link" has an Ask Branch Manager button; a **To do** list (classes without a log, assignments, test attempts, attendance, corrections, recoveries) with a button each; tomorrow's classes when nothing is left today. `?session=` opens one class (Run class from Sessions, or a missing log from an earlier day) |
| `/trainer/batches` | `batches` | `/trainer/batches` | **Batches** (PEOPLE): own batches with seats, next class, attendance and how many students need attention; each opens its page |
| `/trainer/batches/$id` | `batch-page` | `/trainer/batches/{id}` | Batch page: step-free overview (students, classes covered, attendance, need attention), Classes (coming up, recent), Students (with Flag), Assignments, Content; breadcrumbs |
| `/trainer/sessions` | `sessions` | `/class-sessions` | The schedule (Coming up / Past) and reschedule requests waiting; Run class / Continue class / Add class log open the Today flow; Request reschedule. No Start or Mark delivered |
| `/trainer/requests` | `requests` | `/me/requests` | **My requests** (TEACH, after Attendance): reschedule, correction and recovery requests, Waiting / Decided, with the decider and reason |
| `/trainer/students` (`?batch=<id>`) | `students` | `/trainer/students` | **Students**: search, batch filter, "only students who need attention"; why each needs attention, support flag, Open and Flag on every row |
| `/trainer/students/$id` | `student-page` | `/trainer/students/{id}` | Student page: Needs your attention (each reason with a button), attendance, work (Grade on hand-ins waiting), results, support requests, **Flag this student** |
| `/trainer/to-grade` (`?batch=<id>`) | `to-grade` | `/trainer/to-grade` | **To grade** (GRADE, badge): one inbox of hand-ins and test attempts, overdue then oldest, tabs All / Assignments / Tests, batch filter, "Start with the first". `/trainer/reviews` redirects here |
| `/trainer/to-grade/$kind/$id` | `grade-screen` | `/submissions/{id}`, `/attempts/{id}`, `/trainer/to-grade` | Focused grading: the work, an explicit **Start review** button, feedback and marks checked against the maximum, **Save & next** (the next item is fixed when pressed), Save, More (ask to resubmit, with a confirm); a test attempt marks every written answer; "n of m waiting" |
| `/trainer/attendance` (`?session=<id>`) | `attendance` | `/attendance/*` | **Unmarked & corrections**: Classes to mark · Corrections waiting · Recoveries to check · Recent classes (opens on the first with work). A class opens the register (the same `RegisterForm` as Today) with a sticky Save bar; correction requests when the register is closed |
| `/trainer/content` (`?batch=<id>`) | `content` | `/content-items/*` | Filters by batch and status; upload with **Save & submit for review** (primary) or Save draft; the reviewer's comment shows on a "Changes requested" or "Rejected" row (`last_decision`) with **Fix and resubmit**; new version; details |
| `/trainer/assignments` | `assignments` | `/assignments/*` | Create, **edit a draft**, release (confirm), extend, withdraw, submissions list |
| `/trainer/assessments` (`?tab=questions\|tests\|interviews`) | `assessments` (tabs `question-bank`, `test-builder`, `interviews`) | `/tests`, `/questions`, slots | Tabs in workflow order with counts and a one-line hint. Drafts of questions, tests and interviews can be edited; **New mock interview**; Release and Close ask first. The grading queue moved to To grade (`?tab=grading` redirects) |
| `/trainer/support` | `support` | `/support-requests` | The simple view (`SupportDesk simple`): raise a request (the shared Flag dialog), reply, status and owner; Escalate and internal remarks under **More** in the request. Flag from a student row or page |
| `/trainer/notifications`, `/trainer/ask-nipuna` | `shared/notification-centre`, `shared/assistant` | | The inbox is reached from the bell |
| `/trainer/reports` | `reports` | `/trainer/at-risk`, `/trainer/reports` | **Students who need you** per batch, each reason with a button to where to act; the averages (attendance, classes covered, time to review, activity) as one Summary |

#### Branch Manager screens (`features/academic/`, served under `/branch/*`)

The Academic Coordinator workspace was merged into the Branch Manager's (UX phase U2): its screens now live under `/branch/*`, and `/academic/*` redirects there. U14 redesigned the first five (My work, Batches, Waiting for a batch, Schedule & calendar, Class day) and U15 the rest (Courses, Content & questions, Marks & results, Attendance & progress, Completion & certificates, Issues, Recordings, Student support, Reports); their files are in `features/branch/`. Courses is shared with the Super Admin and Founder in `features/shared/course-outline/`.

| Route | Feature | API | Notes |
|---|---|---|---|
| `/branch` | `branch/dashboard`, `branch/my-work` | `/branch/my-work`, `/branch/summary`, `/academic/summary`, `/branches/{id}/payment-instructions` | **My work** (TODAY): the "My work today" list (students waiting, decisions on the schedule, results to publish, content to review, recovery and correction requests, support near its deadline, classes at risk today), one button per row, the Getting started card, then how the branch is doing (CRM tiles, academic tiles) and a collapsed "How students pay fees" form for the branch's payment instructions |
| `/branch/batches` (`?new=1&course=<id>`) | `branch/batches`, `branch/new-batch-wizard` | `/batches`, `/reference/courses`, `/reference/staff` | **Batches**: every batch with seats, state and what it needs next; "New batch" is a three-step wizard (Course, Mode / dates / timetable, Trainer) that opens the batch page |
| `/branch/batches/$id` | `branch/batch-page`, `branch/batch-dialogs`, reusing `academic/batch-panel` and `batch-operations` | `/batches/{id}`, `/batches/{id}/progress`, `/batches/{id}/confirm`, `/batches/{id}/waiting`, `/batches/{id}/generate-sessions`, `/batches/{id}/trainers`, `/class-sessions` | A `StepBar` (Created, Trainer, Ready, Confirmed, Students, Classes) with the next action as the one main button (assign a trainer, finish the setup, confirm, add students from the waiting list, create classes), what blocks a confirmation shown before it, warnings that need a written reason, and tabs Overview, Students, Classes, Trainers, Checks, Requests, History. Create classes previews the timetable (holidays and closures skipped) first |
| `/branch/waiting` | `branch/waiting` | `/branch/waiting`, `/batches/{id}/allocations` | **Waiting for a batch**: the count and each student with the batches that could take them (same course and branch, a seat left) and a one-click Allocate; a match with a warning asks first; a blocked student is told why; "Academic mapping" stays here from the old allocation queue |
| `/branch/schedule` (`?view=list&by=trainer&week=&batch=&decide=1`) | `branch/schedule`, `branch/class-actions`, `branch/new-class` | `/class-sessions`, `/reschedule-requests`, `/class-sessions/{id}/*`, `/calendar/closures` | **Schedule & calendar**: a **Needs decision** strip (reschedule requests and proposed extra classes, with the count, Approve and a menu), a week calendar by batch or trainer (a list on phones) or a list, one primary action per class (Approve, Add Meet link, Confirm, Plan a replacement) plus a More menu, class details with technical IDs under Advanced, "New class" filled in from the batch, and the holidays and closures calendar below |
| `/branch/class-day` | `branch/class-day`, `academic/class-operations` | `/meet-operations`, `/class-sessions/{id}/meet` | **Class day** (TODAY; `/branch/meet-operations` redirects): the day's classes, tiles that filter the list (all, Meet link missing, delayed or disrupted, attendance to mark, class log overdue), the Meet link set inline, open disruptions, replacements owed, classes waiting for approval, class logs not written, evidence to review. The Meet integration status and the background checks are on `/admin/integrations` (`admin/meet-health`) |
| `/branch/courses` (`/$id`) | `shared/course-outline/course-list`, `course-page`, `outline-view`, `planning`, `tree` | `/courses`, `/courses/{id}/outline` | **Courses** (TEACHING), read-only: the CRM's courses (code, title, category, combo tracks, status) with modules and topics, batches running at my branch and students waiting; a course page shows the outline, hours, completion rules and required assessments, and "New batch for this course" opens `/branch/batches?new=1&course=<id>`. No curriculum versions, drafts or approvals (R6) |
| `/admin/courses`, `/founder/courses` (`/$id`) | same files, `CoursePage` / `CourseList` with `base="/admin"` or `"/founder"` | `/courses`, `/courses/{id}/outline`, `/course-modules/*`, `/course-topics/*`, `/courses/{id}/hours-verification`, `/completion-profile`, `/assessment-requirements`, `/track-pins`, `/course-library` | **Courses** (edit): list with batches and active students per branch; a course page shows the CRM fields read-only ("From the CRM"), and edits apply at once: add, rename, drag or Move up / Move down, remove modules and topics (a used topic cannot be removed: the 422 shows; a used module is archived), Details per topic, Hours with Verify, Completion rules, Required assessments, combo track pins (a match note, then the track follows its own course's outline) and the module library. Fresh sign-in is asked for through the shared dialog |
| `/branch/content` (`?tab=&item=`) | `branch/content`, `content-review`, `content-audience` | `/content-items`, `/content-items/review-summary`, `/content-items/{id}/claim`, `/content-items/{id}/review`, `/questions` | **Content review**: tabs To review / Ready to release / Changes requested / Released with counts (`?tab=questions` redirects to `/branch/questions`, **Question approvals**: the shared question bank with `canApprove`); one Review (preview, claimed on opening) with Approve & release (primary, confirm), Approve and release later, Request changes (comment required), Reject under More. `/branch/content-review` redirects |
| `/branch/results` (`?batch=`) | `branch/results`, `results-review`, `results-text` | `/assessment-reviews`, `/results`, `/results/publish-preview`, `/results/publish`, `/tests/{id}/approve` | **Marks & results**: what needs review first, then what waits on the trainer (each gap names its owner), then published; Review marks with moderation and Publish from inside the review, which asks first with the counts. `/branch/assessments` redirects |
| `/branch/attendance` (`?tab=students\|recoveries\|corrections&risk=0`) | `branch/attendance`, `attendance-students`, `attendance-queues` | `/progress/students?sort=risk`, `/progress/enrolments/{id}`, `/branch/attendance-summary`, `/attendance/recoveries`, `/attendance/corrections` | **Attendance & progress**: tabs with counts; students below the alert first (a "Show all students" toggle), a row opens the four measures; recovery and correction decisions confirm with the consequence and hide when `can_decide` is false |
| `/branch/completion` (`?stage=`) | `branch/completion`, `completion-actions`, `completion-evidence` | `/branch/completion`, `/completion-reviews/*`, `/certificates/*` | **Completion & certificates** (COMPLETION): pipeline tabs Ready to decide, Completed, Waiting for fee, Ready to issue, Issued with counts; evidence against the course's thresholds as ticks and crosses; Decide has no default and confirms; approve and issue confirm; correction, revocation and fee release under More; certificate change requests and fee releases in a collapsed section. `/branch/certificates` redirects |
| `/branch/issues` (`?type=&age=&owner=&page=`) | `branch/issues` | `/issues`, `/exceptions/{source}/{id}/steps` | **Issues** (HELP): one paged inbox across every source, filters by type, age and owner, Go fix it (deep link) and Add note. `/branch/exceptions` redirects. The Super Admin's read-and-assign view (U17) reuses `IssuesList` |
| `/branch/recordings` (`?date=&batch=&exception=`) | `branch/recordings`, `recordings-dialogs` | `/recordings`, `/recordings/classes`, `/recordings/{id}/problem`, `/recording-exceptions` | **Recordings** (TEACHING, in the sidebar; also reached from Class day and Issues): pick the class by date and batch, Release with a confirm or Report a problem with a plain reason (still being prepared, only part captured, no recording, on hold); the Drive file id has a "where to find it" hint. `/branch/recording-exceptions` redirects |
| `/branch/support` (`?tab=requests\|extensions&request=`) | `branch/support`, `extensions-requests`, `shared/support-desk` | `/support-requests?view=`, `/support-requests/counts`, `/access-extension-requests`, `/access-extension-requests/{id}/recommendation` | **Student support** (HELP): opens on Needs action sorted by the nearest reply deadline with a New reply marker; Access extensions tab: within the limit the Branch Manager approves (the new end date and "the student will be told" are shown), beyond it adds a recommendation that goes to the Founder. `/branch/requests` redirects |
| `/branch/extensions` | `branch/extensions-page`, `extensions-requests` | `/access-extension-requests`, `/access-extension-requests/{id}/recommendation` | **Access extensions** (HELP; `/branch/requests` and `/branch/support?tab=extensions` redirect here): waiting and decided requests; within the Branch Manager's limit they decide, beyond it they recommend and the Founder decides |
| `/branch/certificate-requests` | `branch/certificate-requests`, `shared/approvals` | `/founder/inbox` (certificate kinds only for a Branch Manager) | **Certificate requests** (COMPLETION): corrections, revocations, reinstatements and fee releases and who decides each |
| `/branch/payments` | `branch/payments`, `shared/payment-instructions` | `/branches/{id}/payment-instructions` | **Payment instructions** (BRANCH): the text on the student's Next payment card, for the session's branch. Super Admin and Founder edit any branch under Setup & health > Branches |
| `/branch/reports` (`?period=&from=&to=`) | `branch/reports`, `reports-parts` | `/branch/reports`, `/branch/reports/export` | **Reports**: period filter (default this month), every figure a drill-down link, progress by batch, six-month trend chart and table, CSV download per table (no Excel library installed). `/branch/academic-reports` redirects |
| `/branch/notifications` | `shared/notification-centre` | | The inbox is reached from the bell |

#### Super Admin and Founder

| Route | Feature | API | Notes |
|---|---|---|---|
| `/branch/operations` | (redirect) | | Split in U14: redirects to `/branch/batches`; the students, trainers and calendar sections now live on Batches, Waiting for a batch and Schedule & calendar |
| `/branch/notifications` | `shared/notification-centre` | | |
| `/admin` | `admin/dashboard` | `/admin/needs-action` | **Home** (U17): "Needs action" first (the newest three failed CRM updates each with Retry, issues nobody owns, locked accounts, closures waiting, student accounts needing attention, broken setup items), the **Setup checklist** card (what is not Working yet; gone once everything is), Quick actions (Add staff user, student accounts needing attention, Add holiday or closure, the audit log) and the Getting started card |
| `/admin/users` (`?add=1`, `?locked=true`, `?q=`) | `admin/users` | `/admin/users/*` | Filters (Locked is one of them), role chips with revoke, add role (temporary access), reset password, deactivate / reactivate; the role picker explains each role in a line; **Unlock** (with a reason) is the first button on a locked row; **Send invite / Resend invite**; temporary password shown once (`SecretDialog`) |
| `/admin/students` (`?q=&status=&attention=true&page=`), `/admin/students/$id` | `admin/students`, `admin/student-page`, `admin/student-actions` | `/admin/students/*`, `/students/{id}/activation` | **Student accounts**: each row has a Suggested next step and its main button (Send new link, Reactivate, Open); "Needs attention" filter. The student opens as **its own page** (breadcrumbs, Suggested next step, Account, Courses, Recent history as sentences, Other actions: suspend / reactivate, sign out everywhere). Send new link shows the WhatsApp outcome and the link to copy |
| `/admin/setup` (`/admin/integrations` and `/admin/security` redirect here) | `admin/setup`, `setup-dialog`, `meet-health` | `/admin/setup`, `PATCH /integrations/{id}`, `/security-controls/{id}`, `/admin/staff-options`, `/delivery/meet-operations` | **Setup & health**: one checklist of connections and security settings, grouped, with plain states (Not set up / Set up / Working / Broken), an owner picked from staff and the evidence; filter chips with counts; Update dialog (state, owner, how you checked it, notes; Working needs the note); the Meet and class checks section lives here |
| `/admin/calendar` (`?view=list`, `?month=YYYY-MM`, `?add=1`) | `admin/calendar`, `calendar-dialogs` (`shared/academic-calendar` stays on `/branch/schedule`) | `/calendar/closures` (`sort=upcoming`), `PATCH /calendar/closures/{id}`, `POST /calendar/closures/{id}/cancel`, `/decision` | **Academic calendar**: month grid (company holidays blue, branch closures amber, proposals dashed) or a list with what is ahead first; primary **Add holiday / closure** whose fields change with the kind; To can't be before From; **Edit** and **Cancel** show "This affects N classes" from a dry run before anything is saved |
| `/admin/crm-sync` (`?tab=all\|sent`, `?event=`) | `admin/crm-sync` | `/admin/crm-sync/*` | **CRM sync** opens on Needs attention (failed first, a plain cause, Retry); All updates (filters) and Sent to the CRM; the update opens a plain summary and keeps the raw JSON under "Technical details" |
| `/admin/audit` (`?preset=&actor=&type=&id=&action=&from=&to=&page=`) | `admin/audit` | `/audit-log`, `/audit-log/facets`, `/audit-log/export` | **Audit log** in sentences with a link to the person or record; preset chips Accounts / Roles / Integrations, Last 7 days, Download CSV; the raw before / after is under Details; the actor filter lists everyone with an entry |
| `/admin/issues` (`/admin/exceptions` redirects) | `admin/issues` (reuses `branch/issues` `IssuesList` with `canAssign`, no branch pick) | `/issues`, `/exceptions/{source}/{id}/assign` | **Issues** across every branch with real paging; **Assign** hands an issue to a staff member (not for items whose own screen names the owner); the Founder reads |
| `/admin/ai-controls`, `/founder/ai-controls` | `admin/ai-controls`, `ai-switch-dialogs` | `/ai-controls/status`, `/ai-controls`, `/ai-controls/{id}/restore` | **AI controls**: a card per audience (student, staff, all AI) with a big ON / OFF; company-wide switch-off asks for a typed `SWITCH OFF`; one-branch switches and a paged history; the Super Admin and the Founder can both switch off and restore |
| `/admin/notifications` | `shared/notification-centre` | | The inbox, plus a "System issues" tab (delivery failures) for the Super Admin only |
| `/founder/certificates` (`?item=`) | `founder/certificates`, `panel-certificate` | `/founder/inbox?group=certificates`, `/certificate-requests/{id}/decision`, `/certificate-financial-exceptions/{id}/decision` | **Certificate decisions**: corrections, revocations, reinstatements and fee releases. Approve and Reject sit side by side with the same weight; Approve confirms with what it does (the consequence line differs per kind), Reject asks for a reason; a fee release also asks for the basis. A Branch Manager's own request says so |
| `/founder/access` (`?item=`) | `founder/access`, `panel-access` | `/access-extension-requests?status=Pending&needs_exception=true`, `/access-extension-requests/{id}/decision` | **Access extensions** beyond two years: every waiting request with the Branch Manager's recommendation (or "waiting for the recommendation"); Review opens the panel; Approve asks for the new end date (the Branch Manager's suggestion is filled in), Reject asks for a reason. Replaces the Founder's old link to `/branch/requests` |
| `/verify/:number` | `routes/verify.$number.tsx` | `/certificates/verify/{number}` | Public, no sign-in and no shell (`OPEN_PATH_ROOTS`); `?version=` shows an older copy |
| `/founder` (`?item=`) | `founder/dashboard`, `inbox-list`, `panel`, `panel-other` | `/founder/inbox`, `/founder/summary`, `/founder/ai-budget` | **Home**: "Needs you" first (certificate decisions, access extensions with the recommendation, the AI budget, Branch Managers' own reschedule and attendance requests), oldest first, one Review button each that opens the item in a side panel on the same page (`?item=<kind>-<id>`); then "How the company is doing": the CRM tiles only once the CRM has sent finance figures (`crm_connected`), active enrolments per branch, batches at risk, certificates waiting for a Branch Manager. The AI budget panel takes the monthly amount in rupees and confirms. Nav: Home (count of everything waiting) |

Admin helpers: `features/admin/shared.tsx` (Pager, FormDialog, SecretDialog), `features/admin/url-params.ts` (screen state kept in the address), `features/admin/staff-options.ts` (every active staff member for a picker), `features/admin/format.ts` (IST
formatter, `useCanAdminister`).

---

## Part C — Running with the local CRM

Both systems on one laptop, each with its own dev database: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on
:5060. The CRM never touches the LMS database: it posts events to `POST /api/v1/integrations/crm/events` and pulls
`GET /api/v1/integrations/crm/status`. The contract is [CRM_INTEGRATION.md](CRM_INTEGRATION.md).

### 1. Connection

| Item | Value |
|---|---|
| LMS base URL | `http://127.0.0.1:5060` |
| Auth header | `X-Service-Key: <key>` = `CRM_SERVICE_KEY` in the LMS `backend/.env`. Share it directly; never commit it |
| CRM config | `LMS_BASE_URL=http://127.0.0.1:5060` and `LMS_SERVICE_KEY=<same key>` in the CRM `backend/.env` |

### 2. Start

```bash
# LMS (from nipunalms/backend), two terminals
APP_ENV=development ../venv/bin/flask --app app run --port 5060
APP_ENV=development ../venv/bin/flask --app app jobs run --loop    # stands in for cron: whatsapp-send, reminders, escalations

# CRM (from nipuna-crm/backend, APP_ENV=development)
flask --app app lms backfill            # events for everything that exists, branches first (--force after an LMS rebuild)
flask --app app lms worker              # deliver every 10 s and pull every minute (--duration N stops after N seconds)
flask --app app lms pull [--full]       # one pull now
flask --app app lms reconcile           # compare both sides per admission (--admission ID, --fix)
flask --app app lms outbox --failed     # counts and errors; lms holds lists pulled records waiting to apply
```

Neither server reloads on its own: restart :5060 after a backend change, and start both loops again after a restart.
The CRM's own `flask whatsapp deliver --loop` sends WhatsApp only; events and status updates to the LMS need `lms worker`.

**After a rebuild, when the CRM has backfilled:** `flask seed-crm-batches` gives its students batches
([Batches for the CRM's own students](#batches-for-the-crms-own-students)). A Branch Manager (`bm.gnt` / `bm.vij`)
then allocates on **Waiting for a batch**, and the CRM's next pull sends `batch_allocated`.

**WhatsApp in dev.** Three switches, all set in `nipunalms-dev` since 18 Oct 2026:

| Switch | Value |
|---|---|
| `CRM_BASE_URL` in `backend/.env` | `http://127.0.0.1:5050/api/v1` (read at start-up; the `jobs` CLI reads it fresh) |
| `app_settings.whatsapp_enabled` | `true` |
| `app_settings.whatsapp_approved_templates` | All nine `nipuna_lms_*` names, ahead of Pinbot's approval |

The CRM sends only to its `WHATSAPP_TEST_NUMBERS`, which in dev is the single owner's number, `+919392329248`; every other number
is Skipped. Never put a student on another number. Until Pinbot approves a template, its messages end `Failed` with
`#132001`. `flask whatsapp status` and `flask whatsapp list` show the LMS side; the `WhatsappStatusUpdated` events are on
**CRM sync**. A fresh `create-dev-db` turns the two `app_settings` values off again; `.env` is not touched.

### 3. Smoke test

```bash
KEY=<service key>
curl -s -X POST http://127.0.0.1:5060/api/v1/integrations/crm/events \
  -H "X-Service-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"event_id":"smoke-1","event_type":"CourseUpserted","source_version":1,
       "occurred_at":"2026-09-30T10:00:00+05:30",
       "data":{"course_code":"NIT-CRS-047","course_title":"Java Full Stack Developer","status":"Active"}}'
```

Expect `201` with `"status":"Applied"`. Run it again: `200` with `"replayed":true`. Change the title but keep
`event_id`: `409`. A wrong key: `401`.

### 4. Check what arrived

- Super Admin → **CRM sync** (`/admin/crm-sync`): every event with its status, payload and result; retry a Failed one.
- Pull what the CRM would store: `GET /api/v1/integrations/crm/status?since=2026-09-30T00:00:00%2B05:30` with the
  service key. Seed rows are left out, so right after a rebuild it returns nothing until the CRM backfills.
- Rules: dev databases only, never real student data; never log the service key or an `activation_token`.

---

## Part D — Status and clean-up

Every screen in the prototype is built on `main`, and every screen has been redesigned in the UX plan (U0–U18, [UX_PLAN.md](UX_PLAN.md)):
the shell and navigation, notifications, sign-in and accounts, and the Student, Trainer, Branch Manager, Founder and Super Admin
workspaces. CRM integration rounds 1–8 are done on both sides (db 090–110, 116, 122; [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).
The last three cover WhatsApp through the CRM, the preferred batch, and the batch / allocation / WhatsApp alignment. WhatsApp is on in dev
and waits only on Pinbot approving the nine templates.

**Gap fix plan** ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md), register [GAPS.md](GAPS.md)): the app was checked against the
approved modules 14–27, which found 109 gaps.

| Phase | Commit | Migration |
|---|---|---|
| 1. Correctness and privacy | `bf5569e` | 099 |
| 2. Deployment templates | `5a124d9` | — |
| 3. Governance and approvals | `ea71866` | 100 |
| 4. Academic Calendar | `be996e1` | 101 |
| 5. Module 14 curriculum model | `506a7e7` | 102 |
| 6. Batches and delivery (Modules 15, 16) | `2953780` | 103 |

42 of the 109 gaps are closed (three more are partly closed by the UX plan). The UX plan took migrations 104–115, so **phase 7
(assessments) is next and starts at `db/116`**; phases 7–12 were rewritten in U18 for the merged Branch Manager role and the new screens.

Still to do:

| Item | Notes |
|---|---|
| Gap fix phases 7–12 | Assessments, attendance and certificates, content and recordings, notifications and integrations (the CRM restrictions intake), reports and AI, career and guardians (the last after CRM round 4) |
| Owner actions | The single list is in [UX_PLAN.md](UX_PLAN.md#owner-actions-in-one-place): restart the :5060 API, apply db 111–115 to any other database, submit the WhatsApp templates in Pinbot, and the open CRM questions |
| Product / role guide | A guide like the CRM's `PRODUCT_GUIDE.md`. Not started |
| Deployment | Templates only (`deploy/`, Part F); nothing is deployed |

## Part E — Backlog

Open product decisions and gaps found while building. Newest at the bottom of each section.

### CRM connection

Open items and decisions are in [CRM_INTEGRATION.md §4](CRM_INTEGRATION.md#4-open-items) (activation link delivery,
placement, support cross-link, staff accounts, course fee). LMS-side gaps:

| Item | Notes |
|---|---|
| One course per admission | `enrolments` is unique on (admission, course), so the schema still accepts a second course under one admission. The CRM never sends that and no row in the dev data does it; a migration could require `enrolments.course_id = admissions.course_id` |
| Batch timetable vs class sessions | The batch timetable (days, times, room) is what sales promises; class sessions are scheduled separately and are not checked against it |

### Integrations (not connected)

| Item | Notes |
|---|---|
| Google Workspace / Meet / Drive | Meet association and recording import are recorded as states against the `integrations` register; no Google API calls |
| Sign-in | One login form, self-service reset code (WhatsApp; no email fallback yet), activation and staff invite links that sign the person in (UX phase U7, API.md §4.14). Templates 1–3 are queued like 4–9 and reach the phone once Pinbot approves them |
| WhatsApp | Built (UX phase U6) and connected (rounds 6, 8): messages are queued in `whatsapp_outbox`, handed to the CRM's `POST /lms/whatsapp`, and their outcome comes back as `WhatsappStatusUpdated`. Ships switched off; on in dev (Part C). Waiting on Pinbot approval of the nine templates (API.md §4.13) |
| Email / telephony | None; in-app notifications only |
| Jobs scheduler | `flask jobs run` holds `recording-check`, `support-escalate-overdue`, `allocation-escalation`, `attempts-expire`, `attendance-unconfirmed`, `session-delay-check`, `class-log-check`, `class-reminders` and `whatsapp-send`; `deploy/crontab` runs them every 5 minutes on a server; locally `flask jobs run --loop` does. New jobs go in `services/jobs.JOBS` |

### Admin & security

| Item | Notes |
|---|---|
| Emergency / elevated access | Security control `EMERGENCY_ACCESS` (max 4 hours, reviewed afterwards) has no mechanism yet; only routine temporary access (7 days) is enforced |
| Student MFA | `students.mfa_status` exists but no second factor is implemented |
| Integration alerts | A Failed integration verification does not yet notify anyone |

### Delivery

| Item | Notes |
|---|---|
| Google Meet creation | Links are entered by hand; no Calendar / Meet API call until the organizer accounts are verified |
| Pre-approved cover arrangements | Cover is requested, approved and verified per class (`session_cover_requests`). A standing cover rota with documented limits (Module 15 §11) is not modelled |
| Trainer availability, leave and travel buffers | Conflicts cover overlapping classes of the trainer, backup or assistant, booked rooms and the students' other classes; leave calendars, working hours and cross-branch travel buffers are not modelled |
| Material changes and future classes | Applying a material change updates the batch's plan (dates, mode, days / times); classes already scheduled are not re-timed automatically, the Branch Manager reschedules them |
| Shared classes beyond attendance | A joined batch's students see the class, are notified and are on its register; its recordings and content still follow the host batch |
| Phase 6 screens: API only or thin | No staff screen for slot requests (`GET / PATCH /slot-preferences`); an interbranch track placement has no target picker for another branch's batches; cover pickers list the class's branch only; shared-class topics, participant matching and disruption replacement / owner are typed as ids. Session reminders 24 h / 1 h before a class are not sent |
| Meet participation import | Join / leave evidence is entered through `POST /class-sessions/{id}/participation` (manual or a future Meet API feed); nothing imports it from Google yet |
| Bulk timetable import | Sessions are created one batch at a time with a repeat rule; no CSV / calendar import as in the prototype's schedule screen |
| Calendar export | The Super Admin's calendar has a month grid and the Branch Manager's Schedule a week calendar (UX phases U14 and U17); the prototype's iCal export is not built |
| Curriculum diff between versions | The prototype shows what changed between versions; only the review trail is stored |
| Re-mapping running batches to a new version | Activating a version maps pending enrolments and batches. A student moves through an individual academic mapping (`/academic-mappings`); moving a whole Running batch at once is not built |
| Academic mapping credits in the UI | The allocation queue's "Academic mapping" dialog prepares a version move without credits; credited topics are API only (`credits` with an approved `rule_id`). Proposing an equivalence rule is API only |
| Batch capacity waitlist | Students' slot requests can be marked Waitlisted, but there is no ordered waiting list or automatic offer when a seat frees up |
| Session reminders | The `class-reminders` job queues a WhatsApp reminder (switched off with WhatsApp); there is no in-app reminder 24 hours / 1 hour before a class (Module 15 §20) |
| Duplicate date helpers | `shared/delivery-ui.tsx` and `shared/format.ts` format IST dates in slightly different forms; the datetime-local helpers (`toIstInput`, `fromIstInput`) live once in `lib/format.ts`. Unify the display formatters when the design settles |

### Content & recordings

| Item | Notes |
|---|---|
| Malware scanning of uploads | Module 18 §7 asks for scanning; not available. Files are validated (type, magic number, safe archive) and never executed |
| Scheduled release and urgent hide | Module 18 §4 / §9: only immediate release and retire (withdraw) are built |
| Separate placements per asset | The library keeps one placement per item (course / version / topic / batch). Reusing one asset in several placements without duplicating bytes needs a placement table |
| Selected-student and company-wide audiences | Audience is branch + course (+ batch). Selected students and cross-branch publishing need the explicit company-wide permission Module 18 §3–4 describes |
| "Report a problem" on a resource | Module 18 §10; would create a support request tied to the item and enrolment |
| Recording access after a delayed release | Module 17 §8: at least 30 days of access after a substantially delayed release is not applied; access is Joining Date based only |
| Batch recording commitment | `batches.recording_provision` (Included / Not Included / Limited + terms) is stored and a Not Included batch raises no missing-recording alert; per-session coverage of a Limited promise and the recording milestones (Configured … Playback Ready, Review Required, Failed) are phase 9 |
| Student notices on 24 h delay | Module 17 §6 asks to update affected students at 24 h; only staff escalation notices are sent |
| Recording playback | Needs the verified Drive integration and a proxy with per-request entitlement (Module 17 §7); today `watch` records the view and returns the integration state |

### Assessments

| Item | Notes |
|---|---|
| Individual extensions | Module 19 §5 (trainer up to 3 days, AC beyond) is not built; the AC can reopen a submission window with a reason, and the trainer can extend the batch due time |
| Validation pending / failed | Submissions are accepted on receipt; no scanning or link verification, so `Received — Validation Pending` and `Validation Failed` don't exist. The upload limit is the API's 10 MB, not the 50 MB of Module 19 |
| Extra attempts, group projects, completion-only / pass-fail work | Only numeric marks with one initial attempt and 2 resubmissions; additional attempts by AC approval are not built |
| Reminders | The 24 h / due date / +1 day assignment reminders and the 24 h / 1 h test reminders need a job; none is registered |
| Reassessment and answer release | A formal test has one attempt; authorised reassessments, a later better attempt after publication, and the separate answer-release step are not built. Correcting a published result (independent review) is not built |
| Tab-switch / similarity flags, question randomisation | Not built |
| Coding runner | Coding answers are marked by a trainer; the isolated runner stays Pending Verification |
| Question bank scope | One bank per branch; company-wide reuse by a global publisher is not built |
| Assessment evidence in Completion Review | Required learning is topic coverage from attendance, not assessment work. Required assignments and published test results are not yet shown in the completion evidence or counted in any measure; decide with the completion profile per course |

### Attendance, progress & certificates

| Item | Notes |
|---|---|
| Minute-based attendance | Module 21 measures attended teaching minutes; the LMS counts sessions (Present + Late / marked). Needs delivered-minute capture and Late / Left Early flags |
| Completion profile per course | Each curriculum version now stores a completion profile and topic weights (db 102), but Completion Review does not apply them yet: it shows evidence and the Branch Manager decides. Applying the profile is gap fix phase 8 |
| Complimentary completion rule | Configuration Pending until `complimentary_completion_rule_configured` is set; needs a business decision |
| Attendance at-risk support cases | Module 21 triggers (two consecutive absences, late pattern, no activity for 7 days) do not open support requests yet |
| Combo per-track attendance | Progress is per enrolment; the module also wants each combo track and the booster separately |
| Certificate document | The certificate PDF is built in the LMS (UX phase U10; Latin-1 fonts, so a Telugu holder name prints as `?`, and the QR needs `PUBLIC_BASE_URL`); email delivery is not available (no Email integration). The register and public verification exist |
| Joining date on correction | An approved correction to Present sets the joining date; changing the first Present to Absent does not reset it |

### Student services

| Item | Notes |
|---|---|
| Fees & Receipts fields | The screen shows fee, verified paid, balance and receipts per course and one instalment schedule per invoice, and the amount still being checked (`pending_verification`). `waived`, `refunded` and `payment_completion` are stored but not shown |
| Staff profile details | `/account/profile` is read-only: no phone number (the API does not return one for staff), MFA shown as Not Configured, staff cannot edit their name or email |
| Founder notifications | The Founder has a bell and `/founder/notifications` (role separation R6); the Home inbox and the nav counts remain the place to act |
| Placement Team | Module 23 names a Placement Team role; there is none, so Branch Manager and Super Admin run career staff work. Employer-sharing per opportunity (individual consent references) and interview reminders are not built |
| Support SLA | One `support_sla_hours` for all categories and priorities |
| External channels | Email, quiet hours and delivery status for WhatsApp (Module 26) are not built; WhatsApp and email appear in preferences only when live |
| Ask Nipuna | No spend ceiling / cost tracking (Module 24 §11); Telugu answer quality untested against a live model; the due-work facts cover the student's own batch seats only, with no per-question detail |
| Career file storage | CV files on local disk under `UPLOAD_DIR/cv` |
| Support attachments | Files on local disk under `UPLOAD_DIR/support` (png, jpg, pdf, txt, doc, docx; 5 MB; 3 per message) |
| Email change code | Delivered by WhatsApp only (no email sender). With WhatsApp off the student is told no code was sent and the email stays as it is |

### Home, Today & reports

| Item | Notes |
|---|---|
| Multiple delivered topics per class | A class session carries one topic, so "Save delivered topics" confirms that topic and marks the class Delivered. Recording extra topics needs a `session_topics` table |
| Engagement refresh | No scheduled engagement refresh exists; `refreshed_at` is the latest recorded learning activity |
| Review turnaround timestamps | Partial Data only appears for impossible pairs (review before submission). `review_started_at` is not used yet; academic reports do not include turnaround |
| Certificate issue lead time | Measured from the completion decision to `issue_date` (a date, not a timestamp); Not Configured until issued certificates trace back to a decided review. No target or SLA is configured |
| Trainer Today: substitute and co-trainers | Today lists sessions where the trainer is the session's trainer; a co-trainer who is not the session trainer sees the batch but not the session |

### Exception queue & staff dashboards

| Item | Notes |
|---|---|
| Recovery steps are notes | A step records what is being done and names an owner; it does not assign work, set a due date or change the source record. Reassigning a recording exception's owner from the queue is not built |
| Allocation Pending waits on Waiting for a batch | Every enrolment waiting for a seat is listed on the Branch Manager's Waiting for a batch screen and counted on My work, however recent. A waiting-time threshold (e.g. 7 days) would keep normal flow out of the queue; needs a product decision |
| Support queue rule | A support request enters the queue when escalated or past `sla_due_at`; the Branch Manager's escalations are also on `/branch/support (Needs action)` |
| Post-2nd-anniversary access exceptions | The Branch Manager adds a recommendation first (db 113); the request then shows in the Founder's inbox and on `/founder/access`, where the Founder decides it with the new end date (U16). Still listed in the exception queue |
| AI rupee ceiling | The Founder (or a Super Admin) approves the monthly amount from the inbox (`PUT /founder/ai-budget`, U16); it is `app_settings.ai_monthly_ceiling_inr`, and the dashboards show Configuration Pending while it is absent. Nothing enforces it yet: Ask Nipuna does not read it, and the AI controls page (U17) does not show or change it |
| Integration failures | Setup & health counts what is Broken (nav badge and Home); there is no live monitoring, alerting or notification, and "Working" is set by hand |
| Provisioning | "Provisioning" means an enrolment held in `Provisioning Pending` (complimentary offer, unmet payment gate). The seed has none; a failed LMS-account creation has no stored state to list. The Super Admin's Home no longer has a Provisioning table (U17), so these are found through Student accounts (Needs attention) |
| Dashboard freshness | Summaries are read live on each visit (no caching, no auto-refresh); `as_of` is returned but not shown |
| Academic "reviews awaiting" | Counts content awaiting review, open completion reviews and certificates in Eligibility Review / Awaiting Approval; assessment moderation is shown separately as "results awaiting publication review" |

---

## Part F — Deployment

The LMS is not deployed yet. `deploy/` holds the templates for a server laid out like the CRM's EC2 test server
(`~/nipuna-crm/docs/DEVELOPMENT.md` Part C): nginx serves the built frontend and proxies `/api` to gunicorn, Postgres
runs on the same machine, cron runs the jobs and the nightly backup. **Which host it runs on (the CRM's instance or its
own) is not decided, and nothing is deployed without the owner's go-ahead.** On a shared host the LMS keeps
`127.0.0.1:5060` and the CRM `5050`; a t3.micro (1 GB) is tight for both.

### 1. Layout on the server

| Path / unit | What | Template |
|---|---|---|
| `/srv/nipunalms/backend` | Flask app (no tests, no local `.env`) | — |
| `/srv/nipunalms/backend/.env` | Server-only, mode 600, generated on the server: `APP_ENV=production`, `DATABASE_URL`, `SECRET_KEY`, `CRM_SERVICE_KEY`, `UPLOAD_DIR`, optionally `ANTHROPIC_API_KEY`. Production refuses to start with the default `SECRET_KEY` or without `CRM_SERVICE_KEY` | — |
| `/srv/nipunalms/backend/uploads` | Content files, submissions, CVs (local disk until production storage is decided) | — |
| `/srv/nipunalms/db`, `/srv/nipunalms/deploy` | SQL migrations; these templates and `backup.sh` | — |
| `/srv/nipunalms/frontend` | Built frontend (`frontend/dist` contents) | — |
| `/srv/nipunalms/venv` | Python venv: `requirements.txt` + `gunicorn` | — |
| `nipunalms.service` (systemd) | gunicorn, 2 workers, `127.0.0.1:5060`, `app:create_app()`, restarts automatically | `deploy/nipunalms.service` |
| `/etc/nginx/sites-available/nipunalms` | Static frontend with SPA fallback, `/api/` → `127.0.0.1:5060`, 260 MB upload limit (the API applies the per-type limits); certbot adds TLS and the HTTP → HTTPS redirect | `deploy/nginx-nipunalms.conf` |
| `ubuntu` crontab | `flask --app app jobs run` every 5 minutes → `/srv/nipunalms/jobs.log`; `backup.sh` at 02:30 | `deploy/crontab` |
| `/srv/nipunalms/backups` | Nightly `pg_dump -Fc` and an uploads tarball, 14 days kept (`RETENTION_DAYS`) | `deploy/backup.sh` |

### 2. First install

```bash
sudo mkdir -p /srv/nipunalms && sudo chown ubuntu: /srv/nipunalms
python3 -m venv /srv/nipunalms/venv
# copy the code (section 3), then:
/srv/nipunalms/venv/bin/pip install -r /srv/nipunalms/backend/requirements.txt gunicorn
createdb nipunalms   # as the database owner; then apply every db/*.sql in order (section 4)
sudo cp /srv/nipunalms/deploy/nipunalms.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now nipunalms
sudo cp /srv/nipunalms/deploy/nginx-nipunalms.conf /etc/nginx/sites-available/nipunalms   # set LMS_HOST
sudo ln -s /etc/nginx/sites-available/nipunalms /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <LMS_HOST>
crontab /srv/nipunalms/deploy/crontab
```

### 3. Redeploy code

```bash
(cd frontend && npm run build)    # build on the laptop
rsync -az --delete -e "$KEY" --exclude '.env' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'uploads/' --exclude 'tests/' --exclude 'api.http' backend db deploy ubuntu@$IP:/srv/nipunalms/
rsync -az --delete -e "$KEY" frontend/dist/ ubuntu@$IP:/srv/nipunalms/frontend/
$KEY ubuntu@$IP 'sudo systemctl restart nipunalms && systemctl is-active nipunalms'
```

### 4. Migrations

Locally every rebuild replays all of `db/*.sql`; a server database is never rebuilt. There is no migrations table, so
**apply only the new files, once each, in order, after a backup**:

```bash
$KEY ubuntu@$IP '/srv/nipunalms/deploy/backup.sh'
$KEY ubuntu@$IP 'cd /srv/nipunalms && set -a && . backend/.env && set +a &&
  psql "${DATABASE_URL/+psycopg/}" -v ON_ERROR_STOP=1 --single-transaction -f db/099_gap_fixes.sql'
```

Keep a list of the files applied on each server here once one exists.

### 5. Check it works, backups

```bash
curl -s https://<LMS_HOST>/api/v1/health                  # {"data":{"status":"ok","database":"ok"}}
$KEY ubuntu@$IP 'sudo journalctl -u nipunalms -n 50 --no-pager; tail -20 /srv/nipunalms/jobs.log'
$KEY ubuntu@$IP 'ls -lh /srv/nipunalms/backups; tail -3 /srv/nipunalms/backups/backup.log'
```

A restore is `pg_restore --clean --if-exists -d <database> nipunalms-<stamp>.dump` plus the uploads tarball. Copy a dump
off the server now and then: the backups share the instance disk. The security controls `BACKUPS` and `HTTPS` stay
Pending Verification until a real server has run a backup, a restore drill and certbot.

Checked locally (3 Oct 2026): the API under gunicorn with the unit's command and `APP_ENV=production` answers
`/api/v1/health`, production refuses the default secret, and `backup.sh` (with `LMS_ROOT` pointing at a scratch folder)
writes a restorable dump and an uploads tarball and prunes old files. nginx was not tested (not installed locally).


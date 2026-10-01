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

The other docs: [API.md](API.md) (backend architecture, conventions, every endpoint), [DATABASE.md](DATABASE.md)
(migrations and schema rules), [CRM_INTEGRATION.md](CRM_INTEGRATION.md) (the LMS ↔ CRM contract).

---

## Part A — Local development

### 1. Repository layout

```
nipunalms/
├── backend/          Flask API (routes → controllers → services → repositories → models), pytest suite, CLI
├── frontend/         React SPA (Vite + TanStack Router/Query), Playwright e2e tests
├── db/               Numbered SQL migrations — the source of truth for the schema
├── prototype/        Readable copy of the Lovable LMS prototype — reference only for layout and wording
├── docs/             The four project docs (this folder)
├── nipuna crm-docs/  Copy of the CRM's docs and its integration-round replies (owned by the CRM side; read only)
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
(Part C).

### 4. Staging data

`seed-dev` builds the prototype's sample world through the same code paths the CRM integration uses (`CourseUpserted`,
`AdmissionQualified`, `FinanceSummaryUpdated` events):

- 11 staff accounts.
- The CRM's eight courses (codes, titles and categories as in the CRM, all single courses) plus the seed-only combo
  **NIT-CRS-900** (3 + 1: tracks T1–T3 and the Power BI booster NIT-CRS-019; the CRM has no combo yet).
- Curriculum versions with modules and topics. NIT-CRS-052 deliberately has no active version → *Curriculum Mapping
  Pending*.
- Five batches across both branches and class sessions for Sep–Oct 2026.
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
| Academic Coordinator | `coordinator.gnt@nipuna.test` | `coordinator.vij@nipuna.test` |
| Trainer | `trainer.g1@nipuna.test` (Trainer R. Sample), `trainer.g2@nipuna.test` (Trainer M. Demo), `trainer.g3@nipuna.test` (Trainer K. Sample) | `trainer.v1@nipuna.test` (Trainer S. Example), `trainer.v2@nipuna.test` (Trainer P. Demo) |

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
| `crm-outbox list` | Values waiting for the CRM |
| `jobs list`, `jobs run [name]` | Background jobs: `recording-check`, `support-escalate-overdue`, `allocation-escalation`. No scheduler runs them yet |
| `api-http` | Regenerate `backend/api.http` after adding endpoints |

### 6. Testing

| Suite | Command | Notes |
|---|---|---|
| Backend | `cd backend && ../venv/bin/pytest -q` | Rebuilds `nipunalms_test`; each test runs in a rolled-back transaction |
| Frontend types | `cd frontend && npm run typecheck` | |
| Frontend build | `cd frontend && npm run build` | Type-check + production build into `dist/` |
| Lint | `cd frontend && npm run lint` | |
| End-to-end | `cd frontend && npx playwright test` (or `npm run e2e`) | Needs the API (dev DB) and Vite running; desktop + `@mobile` projects |

E2E specs live in `frontend/e2e/` (one per area: `shell`, `admin`, `delivery`, `content`, `assessments`, `attendance`,
`services`, `dashboards-learning`, `dashboards-staff`, `staff-account`); `e2e/helpers.ts` has the staging users and
`login()`. Tests that change data assume a freshly seeded database. The Trainer Today spec schedules a class for today
through the API, so it is skipped within ten minutes of midnight IST. `E2E_BASE_URL` points Playwright at another Vite
port. Run one Playwright process at a time (they share `test-results/`).

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
| Workspace from URL | `workspaceForPath(path)` — `/trainer*` trainer, `/academic*` academic, `/branch*` branch, `/admin*` admin, `/founder*` founder, everything else student (except `/login`, `/activate`, `/change-password`; `/account/*` has no workspace of its own and is framed by the user's home workspace) | Same rule as the prototype |
| Who may open a workspace | `profile.workspaces` from `/auth/me` (already expanded per role: Super Admin also holds academic and branch, Founder also admin and branch); `canOpen(workspaces, workspace)` | The API is the authority; the SPA never derives access from role codes |
| Guard | Root route: public paths (`/login`, `/activate`) → anonymous → `/login?redirect=` → `must_change_password` → `/change-password` → workspace not permitted → **Permission Restricted** view (link home) → `/` redirects to `home_route`. Not a security boundary; every endpoint re-checks scope | Same as the CRM |
| Workspace switcher | Header `<select>` shown only when the user has more than one workspace; goes to that workspace's home | Replaces the prototype's UAT role simulator; no prototype banner, no "Demo" badges |
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
    ├── auth/                  auth.tsx (AuthProvider, useAuth(), fresh-auth dialog), access.ts (workspaceForPath, canOpen, NAV, mobileBarItems)
    ├── lib/                   i18n.ts (dictionary, useT, useLanguage), mutation.ts (useApiMutation), format.ts (IST helpers, formatMoney), utils.ts (cn)
    ├── hooks/                 use-mobile.tsx
    ├── components/
    │   ├── ui/                shadcn primitives (copied from the CRM)
    │   └── lms/               app-shell, ui, forms, auth-page, language-toggle, password-field
    ├── routes/                thin file routes (see §5)
    └── features/              student/ trainer/ academic/ branch/ admin/ founder/ shared/
```

Route file naming follows the CRM. `assignments` and `tests` use `assignments.index.tsx` + `assignments.$id.tsx` so the
list and the detail are siblings (no `<Outlet>`); `courses.$enrolmentId_.tracks.$trackId.tsx` (trailing underscore)
keeps the track screen out of the enrolment route's nesting for the same reason.

### 3. Shell and theme

**Header** (navy, sticky): logo → `home_route`; `role label · branch` chip (large screens); language toggle (student
workspace); workspace switcher (only when the user has several workspaces); notifications bell with the unread count
(student → `/notifications`, trainer / academic / branch / admin → `<workspace>/notifications`; the founder has none);
account menu (Profile — `/profile` for students, `/account/profile` for staff — Change password, Sign out).

**Sidebar** (≥ `md`, 240px): the workspace's nav list from `NAV` in `auth/access.ts` (same items, labels, order and
icons as the prototype). Student labels come from the dictionary. **Bottom bar** (< `md`): four pinned items
(`mobileBarItems`) + **More** bottom sheet with the rest of the list.

**Theme** (`src/styles.css`): the prototype's oklch tokens — `--navy`, `--navy-foreground`, `--navy-muted`, `--primary`,
`--accent`, tone pairs `--success|warning|danger|info|neutral` (+ `-soft`), `--radius: 0.625rem` — mapped onto shadcn's
`--background/--card/--border/…`. Tone utilities: `bg-success-soft text-success`, etc.

**Shared components** (`components/lms/`): `PageHead`, `Section`, `Grid`, `Note`, `KeyValue`, `StatusNote` (13-state
catalogue), `StatusBadge` (tone from the status text via `toneFor`), `DataTable` (table → cards), `PillTabs`,
`QueryView`, `ConfirmAction` in `ui.tsx`; `Field`, `NativeSelect`, `applyServerErrors`, `cleanBody` in `forms.tsx`.

**Shared feature parts** (`features/shared/`): `notification-centre`, `assistant` (Ask Nipuna), `support-desk`,
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

**Status wording** — use `StatusNote` states for loading / empty / partial / restricted / failed data and `StatusBadge`
for row statuses; pass `tone` explicitly when the text-based mapping is wrong. A figure with nothing behind it shows
Empty / Not Yet Calculable / Not Configured / Stale, never 0.

**Tests** — one Playwright spec per area in `e2e/`, logging in with `login(page, USERS.<role>)`; desktop plus a
`@mobile` check for new screens.

### 5. Screens → API

#### Public and account

| Route | Feature | API | Notes |
|---|---|---|---|
| `/login` | auth page | `POST /auth/login` | Student ID / student email / staff email + password, show / hide password, forgot-password guidance ("Ask your branch Academic Coordinator to reissue an activation link"), activation-state explanation, EN/తెలుగు |
| `/activate?token=` | auth page | `GET /auth/activation/{token}`, `POST /auth/activate` | Checks the token (valid / expired / used), set + confirm password, success → `/login` |
| `/change-password` | auth page | `POST /auth/change-password` | Forced when `must_change_password`, also from the account menu |
| `/account/profile` | `student/profile` | `GET /me/profile` | Staff: role, branch, devices, password, last sign-in; read-only. Framed by the user's home workspace |
| `/` | — | `GET /auth/me` | Never renders: redirects to `home_route` |

#### Student (`features/student/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/dashboard` | `dashboard` | `/me/home` | Header (name EN / తెలుగు, Master ID, service branch), three ranked tiles (Next Class, Due Work, Current Course Progress), Join Class (disabled with the reason; Meet organizer Pending Verification), eight cards, engagement freshness note (Stale, never zero). Each card shows its own Empty / Unavailable text via `CardGap` |
| `/my-courses` | `my-courses` | `/me/enrolments` | Enrolment cards with gate / delivery state |
| `/courses/$enrolmentId` | `course-detail` | `/me/enrolments/{id}` | Programme, combo tracks and booster, modules with delivery progress |
| `/courses/$enrolmentId/tracks/$trackId` | `track-detail` | `/me/enrolments/{id}/tracks/{track_id}` | |
| `/modules/$moduleId`, `/topics/$topicId` | `module-detail`, `topic-detail` | `/modules/{id}`, `/topics/{id}`, `/me/resources?topic_id=` | Topics, classes, resources and recordings |
| `/sessions/$sessionId` | `session-detail` | `/class-sessions/{id}`, `/me/recordings?session_id=` | Class page with Meet join state |
| `/schedule` | `schedule` | `/me/schedule` | Upcoming / past classes |
| `/assignments`, `/assignments/$id` | `assignments`, `assignment-detail` | `/assignments`, `/assignments/{id}/submissions` | Text / link / file; the window explains replace vs resubmit |
| `/tests`, `/tests/$id` | `tests`, `test-detail` | `/tests`, `/tests/{id}/attempts`, `/attempts/{id}/answers`, `/attempts/{id}/submit`, interview slots | Autosave every 10 s; the timer counts down to the server's `deadline_at`, corrected for clock skew |
| `/results` | `results` | `/me/results` | Provisional rows never show a score |
| `/recordings` | `recordings` | `/me/recordings`, `/recordings/{id}/watch` | Status, access-until, download policy, Watch dialog (playback placeholder that states the Drive integration status) |
| `/resources` | `resources` | `/me/resources`, `/content-items/{id}/open`, `/file` | Filters by course, type, title; Open / Download; access column ("Until 12 Jan 2027", "Pending — no Joining Date yet", "External link"). Both screens use `access-window` (entitlement card + extension request dialog) |
| `/attendance` | `attendance` | `/me/attendance`, `/attendance/recoveries`, `/attendance/corrections` | Per-enrolment table with the prototype labels, request recovery, dispute an entry |
| `/progress` | `progress` | `/me/progress` | Four separate measure cards, course tabs when several enrolments |
| `/certificates` | `certificates` | `/me/certificates` | Own register entries + "Configuration Pending" note for complimentary offers |
| `/career` | `career` | `/me/career/*` | Opt-in, profile editor, consent (withdraw), CV upload / versions / download, approved opportunities with Apply, applications with Withdraw, outcomes |
| `/ask-nipuna` | `shared/assistant` | `/ask-nipuna/*` | Status, scope, usage, actions, sources, warnings, thumbs; refusals shown as "Not answered: out of scope" |
| `/support` | `support` | `/support-requests` | Raise form, my requests, request panel with the thread (reply, confirm and close, reopen) |
| `/notifications` | `shared/notification-centre` | `/notifications/*` | Five views, separate Read / Acknowledged / Action controls, preferences matrix |
| `/finance` | `finance` | `/me/finance` | Per course: fee, verified paid, balance, receipts; the instalment schedule once per invoice (`INV-… · Course A + Course B`); as-of time and source |
| `/profile` | `profile` | `/me/profile` | Identity with masked mobile, language (stored on the student), devices (sign out / sign out others), password and recovery |

#### Trainer (`features/trainer/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/trainer` | `today` | `/trainer/today` | Three tiles, then "Today's flow" per session: open session (`start`) → Join / Start Meet → save delivered topics (`deliver`) → attendance (`RegisterForm` from `trainer/attendance`) → notes and close-out (`PUT /class-sessions/{id}/notes`). Empty state "No assigned session scheduled today." and the scope note |
| `/trainer/batches`, `/trainer/sessions` | `batches`, `sessions` | `/batches`, `/class-sessions` | Own batches with roster; sessions with Start / Deliver / request reschedule |
| `/trainer/students` | `students` | `/trainer/students` | Assigned students with support flag |
| `/trainer/reviews` | `reviews` | `/submissions?status=Awaiting Review&reviewer_me=true` | Start review, review |
| `/trainer/attendance` | `attendance` | `/attendance/*` | Pending / All sessions, register with radio marking, Mark all Present, Confirm, request correction when locked, recoveries to verify |
| `/trainer/content` | `content` | `/content-items/*` | Upload (batch → topic picker from `/content-items/options`, file or link), submit for review, new version, details |
| `/trainer/assignments` | `assignments` | `/assignments/*` | Create / release / extend / withdraw, submissions list |
| `/trainer/assessments` | `assessments` (tabs `test-builder`, `question-bank`, `grading`, `interviews`) | `/tests`, `/questions`, `/attempts`, slots | |
| `/trainer/support` | `support` | `/support-requests` | "Flag a student" dialog, requests the trainer owns or raised, students with open flags |
| `/trainer/notifications`, `/trainer/ask-nipuna` | `shared/notification-centre`, `shared/assistant` | | |
| `/trainer/reports` | `reports` | `/trainer/reports` | Delivery and attendance per assigned batch (Meter), review turnaround (Partial Data), engagement (Stale) |

#### Academic Coordinator (`features/academic/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/academic` | `dashboard` | `/academic/summary` | Ranked tiles (allocation queue, results awaiting review, unfulfilled recording promises), widgets (batches delivery-ready, reviews awaiting, open exceptions), a note for each batch that is not ready, quick links, the "four distinct records" note |
| `/academic/batches` | `batches` + `batch-panel`, `allocation-queue` | `/batches/*`, `/allocation-queue` | Batch list and panel (roster, trainers, readiness, history), allocation queue with the per-check review dialog, transfer and deallocate |
| `/academic/curriculum` | `curriculum` | `/curriculum/*`, `/curriculum-versions/*` | Overview, version editor (modules / topics), submit / return / approve / activate / retire |
| `/academic/schedule` | `schedule` | `/class-sessions/*`, `/reschedule-requests` | Session table with create / reschedule / cancel / Meet actions and the request queue |
| `/academic/assessments` | `assessments` | `/assessment-reviews`, `/results` | Moderate, publish, approve tests and questions |
| `/academic/exceptions` | `exceptions` | `/exceptions` | "Exception / Recovery queue": one table (branch column only when rows span branches), type filter, recovery owner ("Awaiting named owner" + the role that should own it), **Update** logs a recovery step. Read only for the Branch Manager |
| `/academic/content-review` | `content-review` | `/content-items/*` | Tabs Awaiting review / Ready to release / Released / Changes requested / All; review dialog (approve, approve & release, request changes, reject), retire |
| `/academic/recording-exceptions` | `recording-exceptions` | `/recording-exceptions`, `/recordings` | Tabs Exceptions (start / resolve, escalation step) and Recordings (register, media reference, release, hold, partial, unavailable) |
| `/academic/progress` | `progress` | `/progress/students` | Table per student with batch / alert filters, recovery and correction queues |
| `/academic/completion` | `completion` | `/completion-reviews/*` | Evidence table, open review, recommend, decide |
| `/academic/certificates` | `shared/certificate-register` | `/certificates/*` | The API's `actions` decide which buttons show (recommend / approve / issue / reissue / revoke) |
| `/academic/support` | `support` | `/support-requests` | Branch requests with reply, internal remark, status, resolve, escalate, reassign |
| `/academic/reports` | `reports` | `/academic/reports`, `/progress/summary` | Per-branch block plus the branch summary table |
| `/academic/notifications` | `shared/notification-centre` | | |

#### Branch Manager, Super Admin, Founder

| Route | Feature | API | Notes |
|---|---|---|---|
| `/branch` | `branch/dashboard` | `/branch/summary` | Three CRM tiles rendered **Unavailable** with the Not Configured hint (never 0); running batches, schedule and recording exceptions, escalations and extension requests; "Go to" links; locked-branch note |
| `/branch/operations` | `branch/operations` | `/batches`, `/class-sessions`, `/reschedule-requests` | Branch view of batches, requests and Meet exceptions |
| `/branch/requests` | `branch/requests` | `/support-requests?escalated=true`, `/access-extension-requests` | Tabs Escalations (`BranchEscalations`) and Access extensions (`AccessExtensions`, with the note that repeated requests do not stack years) |
| `/branch/reports` | `shared/certificate-register` + summary | `/progress/summary`, `/certificates` | |
| `/branch/notifications` | `shared/notification-centre` | | |
| `/admin` | `admin/dashboard` | `/admin/summary` | Integration failures, work awaiting a named owner, overdue payment verifications (Unavailable), integrations verified x / total, provisioning, open exceptions; CRM / LMS sync table, provisioning table, AI status, links |
| `/admin/users` | `admin/users` | `/admin/users/*` | Filters, role chips with revoke, add role (temporary access), reset password, deactivate / reactivate; temporary password shown once (`SecretDialog`) |
| `/admin/students` | `admin/students` | `/admin/students/*`, `/students/{id}/activation` | Search, "Activation link from" filter, detail dialog, activation link shown once, suspend / reactivate, revoke sessions |
| `/admin/integrations`, `/admin/security` | `admin/integrations`, `admin/security` | `/integrations`, `/security-controls` | Shared `readiness-table` (requirement, configuration, verification, evidence, owner, last check); Update dialog for Super Admin only; Founder reads |
| `/admin/crm-sync` | `admin/crm-sync` | `/admin/crm-sync/*` | Inbox (filters, payload view, retry) and outbox; event types come from the data |
| `/admin/audit` | `admin/audit` | `/audit-log` | Filters by actor, entity, action, date (IST) |
| `/admin/exceptions` | `admin/exceptions` | `/exceptions` | "Exception Queues — all branches": a section per queue with a branch column (company-wide rows say "All branches"); Super Admin can Update, the Founder reads |
| `/admin/notifications` | `shared/notification-centre` | | |
| `/founder` | `founder/dashboard` | `/founder/summary` | CRM tiles (Unavailable), active enrolments per branch, batches at risk, certificates awaiting approval, "Decisions needing you" (AI rupee ceiling, recording-access exceptions after the 2nd anniversary with a link to `/branch/requests`) |

Admin helpers: `features/admin/shared.tsx` (Pager, FormDialog, SecretDialog), `features/admin/format.ts` (IST
formatter, `useCanAdminister`).

---

## Part C — Running with the local CRM

Both systems on one laptop, each with its own dev database: CRM `nipunacrm-dev` on :5050 → LMS `nipunalms-dev` on
:5060. The CRM never touches the LMS database; everything goes through `POST /api/v1/integrations/crm/events`. The
contract is [CRM_INTEGRATION.md](CRM_INTEGRATION.md).

### 1. Connection

| Item | Value |
|---|---|
| LMS base URL | `http://127.0.0.1:5060` |
| Auth header | `X-Service-Key: <key>` = `CRM_SERVICE_KEY` in the LMS `backend/.env`. Share it directly; never commit it |
| CRM config | `LMS_BASE_URL=http://127.0.0.1:5060` and `LMS_SERVICE_KEY=<same key>` in the CRM `backend/.env` |

### 2. Start

```bash
# LMS (from nipunalms/backend)
APP_ENV=development ../venv/bin/flask --app app run --port 5060

# CRM (from nipuna-crm/backend, APP_ENV=development)
flask --app app lms backfill            # write events for everything that exists (--force after an LMS rebuild)
flask --app app lms deliver --loop      # deliver them (or: flask jobs run lms-sync)
flask --app app lms outbox --failed     # counts and errors
flask --app app lms status-check        # call the LMS status pull once
```

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

Every screen in the prototype is built on `main`: foundation and CRM intake, delivery, content and recordings,
assessments, attendance / progress / certificates, student services, admin and security, the exception queue, the six
dashboards, both reports pages, staff notifications and `/account/profile`. The CRM round-1 fixes are in (db 090), and
the LMS side of round 2 (db 095; `nipuna crm-docs/CRM_ROUND2_LMS_REPLY.md`).

Still to do:

| Item | Notes |
|---|---|
| Remove the agent worktrees | Nine under `.claude/worktrees/agent-*`, each with a `worktree-agent-*` branch, all merged. `git worktree remove <path>` then `git branch -d <branch>` |
| Drop the per-module databases | `nipunalms-{admin,assessments,attendance,content,delivery,services,p3a,p3b,p3c}-dev` and the matching `nipunalms_*_test`. Keep `nipunalms`, `nipunalms-dev`, `nipunalms_test` |
| Validation pass | A cross-role acceptance run (desktop + mobile) against the merged app, and a product / role guide like the CRM's `PRODUCT_GUIDE.md`. Not started |
| CRM round 2 | See [CRM_INTEGRATION.md §4](CRM_INTEGRATION.md#4-status) |

---

## Part E — Backlog

Open product decisions and gaps found while building. Newest at the bottom of each section.

### CRM connection

Details and options are in [CRM_INTEGRATION.md](CRM_INTEGRATION.md).

| Item | Notes |
|---|---|
| CRM applies the LMS status | Round 2: the CRM's `lms-status-pull` job and the academic, batch and certificate mirrors (§3.2–3.4, §3.6). LMS answers and the CRM's to-do list: `nipuna crm-docs/CRM_ROUND2_LMS_REPLY.md` |
| Push or pull | The CRM plans to pull `/integrations/crm/status`. The LMS `crm_outbox` rows are queued but not delivered; a push worker is only needed if push is chosen (§3.2) |
| `lms_last_synced_at` | Set by the CRM when it applies a pull; the LMS reports `now` at pull time (`as_of` can be slightly earlier: it stays below any open transaction) |
| Activation link delivery | Decided: B now, A later. The CRM discards the token; coordinators reissue with the "Activation link from: CRM provisioning" filter until the CRM delivers links (§3.7) |
| Branches | The LMS accepts `BranchUpserted` (db 096); the CRM still has to send it (§3.12) |
| Dashboard finance figures | The LMS accepts `BranchFinanceSnapshot` and shows it (db 096); the tiles stay Not Configured until the CRM's 15-minute job sends one (§3.13) |
| Certificate numbering | Decided: the LMS series `NIT-CERT-2026-000001`; the CRM mirrors it (§3.6) |
| Placement owner | Decided: the CRM keeps employers / openings / applications; the LMS Career screen reads and submits through the CRM, in a later round (§3.9) |
| Course fee and branches | `CourseUpserted` carries neither; ask the CRM if needed (§3.11) |
| One course per admission | `enrolments` is unique on (admission, course), so the schema still accepts a second course under one admission. The CRM never sends that and no row in the dev data does it; a migration could require `enrolments.course_id = admissions.course_id` |

### Integrations (not connected)

| Item | Notes |
|---|---|
| Google Workspace / Meet / Drive | Meet association and recording import are recorded as states against the `integrations` register; no Google API calls |
| WhatsApp / email / telephony | In-app notifications only |
| Jobs scheduler | `flask jobs run` holds `recording-check`, `support-escalate-overdue` and `allocation-escalation`; no cron runs it yet. New jobs go in `services/jobs.JOBS` |

### Admin & security

| Item | Notes |
|---|---|
| Emergency / elevated access | Security control `EMERGENCY_ACCESS` (max 4 hours, reviewed afterwards) has no mechanism yet; only routine temporary access (7 days) is enforced |
| Student MFA | `students.mfa_status` exists but no second factor is implemented |
| Integration alerts | A Failed integration verification does not yet notify anyone |
| Audit actor filter | The Actor filter lists staff only; student sign-ins are found by entity |

### Delivery

| Item | Notes |
|---|---|
| Google Meet creation | Links are entered by hand; no Calendar / Meet API call until the organizer accounts are verified |
| Substitute trainer on a single class | `session_changes` can record it, but the prototype's substitute picker with availability is not built |
| Trainer availability and leave | Conflicts are only overlapping classes and rooms; leave calendars and working hours are not modelled |
| Bulk timetable import | Sessions are created one batch at a time with a repeat rule; no CSV / calendar import as in the prototype's schedule screen |
| Calendar month grid | Schedules are list / week tables; the prototype's month calendar view and iCal export are not built |
| Curriculum diff between versions | The prototype shows what changed between versions; only the review trail is stored |
| Re-mapping running batches to a new version | Activating a version maps pending enrolments and batches; moving Running batches to a newer version is manual |
| Batch capacity waitlist | Full batches have no waiting list; the allocation queue just lists unseated enrolments |
| Session reminders | Students are notified of changes but not reminded before a class (needs a job) |
| Topic-level self study progress | Topic pages show classes and resources; students cannot mark a topic as studied |
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
| Batch recording commitment | Included / Not Included / Limited terms per batch (Module 17 §2) are not modelled; the check job flags every Delivered session without a recording |
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
| Review clocks | The 3 / 5 / 7 working-day review targets need the academic working calendar; none is configured |
| Tab-switch / similarity flags, question randomisation | Not built |
| Coding runner | Coding answers are marked by a trainer; the isolated runner stays Pending Verification |
| Question bank scope | One bank per branch; company-wide reuse by a global publisher is not built |
| Assessment evidence in Completion Review | Required learning is topic coverage from attendance, not assessment work. Required assignments and published test results are not yet shown in the completion evidence or counted in any measure; decide with the completion profile per course |

### Attendance, progress & certificates

| Item | Notes |
|---|---|
| Minute-based attendance | Module 21 measures attended teaching minutes; the LMS counts sessions (Present + Late / marked). Needs delivered-minute capture and Late / Left Early flags |
| Completion profile per course | Minimum attendance, required learning weights and recovery rules are not configured per course / curriculum version; Completion Review shows evidence and the coordinator decides |
| Complimentary completion rule | Configuration Pending until `complimentary_completion_rule_configured` is set; needs a business decision |
| Attendance at-risk support cases | Module 21 triggers (two consecutive absences, late pattern, no activity for 7 days) do not open support requests yet |
| Combo per-track attendance | Progress is per enrolment; the module also wants each combo track and the booster separately |
| Certificate document | No PDF / template and no email delivery (Email integration not verified); the register and public verification exist |
| Public verification page | `/certificates/verify/{number}` is API only; a public SPA route needs `/verify` in the public paths |
| Joining date on correction | An approved correction to Present sets the joining date; changing the first Present to Absent does not reset it |

### Student services

| Item | Notes |
|---|---|
| Fees & Receipts fields | The screen shows fee, verified paid, balance and receipts per course and one instalment schedule per invoice. `pending_verification`, `waived`, `refunded` and `payment_completion` are stored but not shown |
| Staff profile details | `/account/profile` is read-only: no phone number (the API does not return one for staff), MFA shown as Not Configured, staff cannot edit their name or email |
| Founder notifications | No event is addressed to the Founder role, so the founder workspace has no notification route or bell |
| Placement Team | Module 23 names a Placement Team role; there is none, so Academic Coordinator, Branch Manager and Super Admin run career staff work. Employer-sharing per opportunity (individual consent references) and interview reminders are not built |
| Support SLA | One `support_sla_hours` for all categories and priorities |
| External channels | WhatsApp / email delivery, quiet hours and retry (Module 26) need the integrations verified first; preferences are stored only |
| Ask Nipuna | No spend ceiling / cost tracking (Module 24 §11); Telugu answer quality untested against a live model; the due-work facts cover the student's own batch seats only, with no per-question detail |
| Career file storage | CV files on local disk under `UPLOAD_DIR/cv` |

### Home, Today & reports

| Item | Notes |
|---|---|
| Multiple delivered topics per class | A class session carries one topic, so "Save delivered topics" confirms that topic and marks the class Delivered. Recording extra topics needs a `session_topics` table |
| Engagement refresh | No scheduled engagement refresh exists; `refreshed_at` is the latest recorded learning activity |
| Review turnaround timestamps | Partial Data only appears for impossible pairs (review before submission). `review_started_at` is not used yet; academic reports do not include turnaround |
| Certificate issue lead time | Measured from the completion decision to `issue_date` (a date, not a timestamp); Not Configured until issued certificates trace back to a decided review. No target or SLA is configured |
| Trainer Today: substitute and co-trainers | Today lists sessions where the trainer is the session's trainer; a co-trainer who is not the session trainer sees the batch but not the session |
| Student Home language | Card titles follow the EN / తెలుగు setting; card bodies are English, as in the prototype. The Telugu greeting uses `name_te` when the CRM sent it |
| Join Class on the home tile | Shows the next class only; a second class the same day is reachable from Schedule |

### Exception queue & staff dashboards

| Item | Notes |
|---|---|
| Recovery steps are notes | A step records what is being done and names an owner; it does not assign work, set a due date or change the source record. Reassigning a recording exception's owner from the queue is not built |
| Allocation Pending is always an exception | Every enrolment waiting for a seat is listed, however recent. A waiting-time threshold (e.g. 7 days) would keep normal flow out of the queue; needs a product decision |
| Support queue rule | A support request enters the queue when escalated or past `sla_due_at`; the Branch Manager's escalations are also on `/branch/requests` |
| Post-2nd-anniversary access exceptions | Listed in the queue and the Founder's decisions with a link to `/branch/requests`; the Founder cannot decide from the dashboard itself |
| AI rupee ceiling | No setting exists; the dashboards read `app_settings.ai_monthly_ceiling_inr` and show Configuration Pending while it is absent |
| Integration failures tile | Counts the readiness register (Failed / Misconfigured); no live monitoring, alerting or notification |
| Provisioning | "Provisioning" means an enrolment held in `Provisioning Pending` (complimentary offer, unmet payment gate). The seed has none, so the Provisioning table on `/admin` is empty in staging; a failed LMS-account creation has no stored state to list |
| Dashboard freshness | Summaries are read live on each visit (no caching, no auto-refresh); `as_of` is returned but not shown |
| Academic "reviews awaiting" | Counts content awaiting review, open completion reviews and certificates in Eligibility Review / Awaiting Approval; assessment moderation is shown separately as "results awaiting publication review" |

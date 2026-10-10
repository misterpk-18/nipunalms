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

`nipunalms-dev` is shared by the e2e suite and the local CRM. The e2e specs assume a freshly seeded database, so CRM
joint tests (curricula activated, finance snapshots, extra batches) can make a few delivery and dashboard specs fail
until the next rebuild.

### 4. Staging data

`seed-dev` builds the prototype's sample world through the same code paths the CRM integration uses (`CourseUpserted`,
`AdmissionQualified`, `FinanceSummaryUpdated` events):

- 11 staff accounts.
- The CRM's eight courses (codes, titles and categories as in the CRM, all single courses) plus the seed-only combo
  **NIT-CRS-900** (3 + 1: tracks T1–T3 and the Power BI booster NIT-CRS-019; the CRM has no combo yet).
- Curriculum versions with modules and topics for every course except NIT-CRS-028 and NIT-CRS-052. NIT-CRS-052 has a
  `CV 3.0` draft under review, so its enrolments are allocatable and its batch (NIT-GNT-BAT-2026-000003) has no curriculum until
  that draft is activated.
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
| Trainer | `trainer.g1@nipuna.test` (Trainer R. Sample), `trainer.g2@nipuna.test` (Trainer M. Demo), `trainer.g3@nipuna.test` (Trainer K. Sample) | `trainer.v1@nipuna.test` (Trainer S. Example), `trainer.v2@nipuna.test` (Trainer P. Demo) |

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
| `jobs list`, `jobs run [name]` | Background jobs (`services/jobs.JOBS`): `recording-check`, `support-escalate-overdue`, `allocation-escalation`, `attempts-expire`, `attendance-unconfirmed`, `session-delay-check`, `class-log-check`, `class-reminders`, `whatsapp-send`. Each run is recorded in `job_runs`. Locally nothing runs them on a schedule |
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
| Workspace from URL | `workspaceForPath(path)` — `/trainer*` trainer, `/branch*` branch, `/admin*` admin, `/founder*` founder, everything else student (except `/login`, `/activate`, `/change-password`; `/account/*` has no workspace of its own and is framed by the user's home workspace) | Same rule as the prototype |
| Who may open a workspace | `profile.workspaces` from `/auth/me` (already expanded per role: Super Admin also holds branch, Founder also admin and branch); `canOpen(workspaces, workspace)` | The API is the authority; the SPA never derives access from role codes |
| Guard | Root route: public paths (`/login`, `/activate`) → anonymous → `/login?redirect=` → `must_change_password` → `/change-password` → workspace not permitted → **Permission Restricted** view (link home) → `/` redirects to `home_route`. Not a security boundary; every endpoint re-checks scope | Same as the CRM |
| "Acting as" switcher | Header pill "Acting as: <role> ▾" (`acting-as.tsx`), shown when the user has more than one workspace or, in the Branch Manager workspace, more than one branch. A menu lists each workspace with a one-line description and goes to that workspace's home; the branch picker (All branches / one branch) is kept per user in `localStorage` (`lib/acting-branch.ts`, `auth/acting.ts`) and narrows the nav counts and the Getting started card. Single-role, single-branch users keep the static "role · branch" chip. The cross-workspace nav items ("Branch views", "Super Admin view") are gone | Replaces the prototype's UAT role simulator; no prototype banner, no "Demo" badges |
| Navigation | `NavItem` has `group` (heading in the sidebar and the More sheet) and `badgeKey` (the count shown from `GET /me/nav-counts`, polled every minute). The count is a visual badge plus a screen-reader description outside the link, so a link's name stays the page name. Trainer, Branch Manager, Super Admin and Founder navs are grouped; the student nav stays flat until its screens merge (UX U9 / U10) | One place that says what waits for you |
| Search | Ctrl/Cmd+K or the header search button opens `command-palette.tsx`: the pages of every workspace the user holds, plus `GET /search` records (students, batches, certificates) within scope. A record opens the list that holds it in the current workspace (record pages arrive with their screens) | Find a screen or a person without remembering where it is |
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
    ├── auth/                  auth.tsx (AuthProvider, useAuth(), fresh-auth dialog), access.ts (workspaceForPath, canOpen, NAV, mobileBarItems), acting.ts (useActing: the branch pick)
    ├── lib/                   i18n.ts (dictionary, useT, useLanguage), mutation.ts (useApiMutation), format.ts (IST helpers, formatMoney), utils.ts (cn)
    ├── hooks/                 use-mobile.tsx
    ├── components/
    │   ├── ui/                shadcn primitives (copied from the CRM)
    │   └── lms/               app-shell, acting-as, command-palette, getting-started, ui, forms, auth-page, language-toggle, password-field
    ├── routes/                thin file routes (see §5)
    └── features/              student/ trainer/ academic/ branch/ admin/ founder/ shared/
```

Route file naming follows the CRM. `assignments` and `tests` use `assignments.index.tsx` + `assignments.$id.tsx` so the
list and the detail are siblings (no `<Outlet>`); `courses.$enrolmentId_.tracks.$trackId.tsx` (trailing underscore)
keeps the track screen out of the enrolment route's nesting for the same reason.

### 3. Shell and theme

**Header** (navy, sticky): logo → `home_route`; `role label · branch` chip (large screens) or, for people with several workspaces or branches, the
"Acting as" switcher (see the decisions table); the search button (Ctrl/Cmd+K); language toggle (student workspace);
notifications bell (`notification-bell.tsx`) counting what is new or needs action, with a preview of the latest five and "Open inbox"
(student → `/notifications`, trainer / branch / admin → `<workspace>/notifications`; the founder has none);
account menu (Profile — `/profile` for students, `/account/profile` for staff — Change password, Sign out).

**Sidebar** (≥ `md`, 240px): the workspace's nav list from `NAV` in `auth/access.ts` (same items, labels, order and
icons as the prototype, grouped under headings and with count badges for staff workspaces; there is no Notifications item, the bell
holds it). Student labels come from the dictionary. **Bottom bar** (< `md`): four pinned items
(`mobileBarItems`) + **More** bottom sheet with the rest of the list.

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

**Shared feature parts** (`features/shared/`): `notification-centre` (the inbox and the `NotificationRow` the bell reuses), `notification-preferences` (on the Profile screen), `assistant` (Ask Nipuna), `support-desk`,
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
| `/account/profile` | `student/profile` | `GET /me/profile` | Staff: role, branch, devices, password, last sign-in; read-only. Framed by the user's home workspace |
| `/` | — | `GET /auth/me` | Never renders: redirects to `home_route` |

#### Student (`features/student/`)

| Route | Feature | API | Notes |
|---|---|---|---|
| `/dashboard` | `dashboard` | `/me/home` | Header (name EN / తెలుగు, Master ID, service branch), three ranked tiles (Next Class, Due Work, Current Course Progress), Join Class (disabled with the reason; Meet organizer Pending Verification), eight cards, engagement freshness note (Stale, never zero). Each card shows its own Empty / Unavailable text via `CardGap` |
| `/my-courses` | `my-courses`, `batch-changes` | `/me/enrolments`, `/me/material-changes`, `/me/slot-options`, `/me/slot-preferences` | Enrolment cards with gate / delivery state; changes needing the student's agreement (Agree / Decline; reading a notice is not agreement); the preferred-slot request and its status (a request reserves no seat) |
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
| `/notifications` | `shared/notification-centre` | `/notifications/*` | Inbox: tabs Needs action (first when any, with a count) · All · Done; one status (New / Needs action / Done) and one button per item; mark as done / read. Reached from the bell, not the sidebar. Preferences are on `/profile` |
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
| `/trainer/notifications`, `/trainer/ask-nipuna` | `shared/notification-centre`, `shared/assistant` | | The inbox is reached from the bell |
| `/trainer/reports` | `reports` | `/trainer/reports` | Delivery and attendance per assigned batch (Meter), review turnaround (Partial Data), engagement (Stale) |

#### Branch Manager screens (`features/academic/`, served under `/branch/*`)

The Academic Coordinator workspace was merged into the Branch Manager's (UX phase U2): its screens now live under `/branch/*`, and `/academic/*` redirects there. The screens are moved, not yet redesigned (UX phases U14 and U15 do that).

| Route | Feature | API | Notes |
|---|---|---|---|
| `/branch` (below the branch tiles) | `dashboard` | `/academic/summary` | Ranked tiles (allocation queue, results awaiting review, unfulfilled recording promises), widgets (batches delivery-ready, reviews awaiting, open exceptions), a note for each batch that is not ready, quick links |
| `/branch/batches` | `batches` + `batch-panel`, `batch-operations`, `allocation-queue` | `/batches/*`, `/allocation-queue`, `/batch-*-requests`, `/material-changes`, `/batch-successions` | Batch list (state labels, display names) and panel: overview, readiness checks and the 7-point readiness record, trainers, roster with transfer requests, handovers and deallocate, the Requests tab (capacity, transfers, material changes and student answers, merge / split, handovers) and the lifecycle buttons (propose, confirm / return, start, hold / resume, complete, cancel, archive); allocation queue with the per-check review dialog and a combo track choice |
| `/branch/curriculum` | `curriculum` | `/curriculum/*`, `/curriculum-versions/*` | Overview, version editor (modules / topics), submit / return / approve / activate / retire |
| `/branch/schedule` | `schedule` | `/class-sessions/*`, `/reschedule-requests` | Session table (state labels, purpose, approval) with create (purpose, replacement link, owner, deadline, Meet ids), confirm, class log, reschedule / cancel (emergency reason and next action inside 24 hours), approve a replacement / remedial / extra class (Branch Manager), replacement waiver, Meet actions and the request queue. A scheduling warning shows the Branch Manager an override reason field |
| `/branch/meet-operations` | `meet-operations`, `class-operations` | `/meet-operations`, `/class-sessions/{id}/operations` and its actions | One day of classes: link and host readiness, delays and disruptions, attendance awaiting, recordings; open disruptions (resolve), replacements owed, classes awaiting approval, missing logs, evidence to review, Meet integration and the last background checks. Per class: hosts, backups and guests, incidents, disruptions, cover requests, shared batches, participation |
| `/branch/assessments` | `assessments` | `/assessment-reviews`, `/results` | Moderate, publish, approve tests and questions |
| `/branch/exceptions` | `exceptions` | `/exceptions` | "Exception / Recovery queue": one table (branch column only when rows span branches), type filter, recovery owner ("Awaiting named owner" + the role that should own it), **Update** logs a recovery step. The Branch Manager and Super Admin log steps |
| `/branch/content-review` | `content-review` | `/content-items/*` | Tabs Awaiting review / Ready to release / Released / Changes requested / All; review dialog (approve, approve & release, request changes, reject), retire |
| `/branch/recording-exceptions` | `recording-exceptions` | `/recording-exceptions`, `/recordings` | Tabs Exceptions (start / resolve, escalation step) and Recordings (register, media reference, release, hold, partial, unavailable) |
| `/branch/progress` | `progress` | `/progress/students` | Table per student with batch / alert filters, recovery and correction queues |
| `/branch/completion` | `completion` | `/completion-reviews/*` | Evidence table, open review, recommend, decide |
| `/branch/certificates` | `shared/certificate-register` | `/certificates/*` | The API's `actions` decide which buttons show (recommend / approve / issue / reissue / revoke) |
| `/branch/support` | `support` | `/support-requests` | Branch requests with reply, internal remark, status, resolve, escalate, reassign |
| `/branch/academic-reports` | `reports` | `/academic/reports`, `/progress/summary` | Per-branch block plus the branch summary table |
| `/branch/notifications` | `shared/notification-centre` | | The inbox is reached from the bell |

#### Branch Manager, Super Admin, Founder

| Route | Feature | API | Notes |
|---|---|---|---|
| `/branch` | `branch/dashboard` | `/branch/summary` | Three CRM tiles rendered **Unavailable** with the Not Configured hint (never 0); running batches, schedule and recording exceptions, escalations and extension requests; "Go to" links; locked-branch note |
| `/branch/operations` | `branch/operations` | `/batches`, `/class-sessions`, `/reschedule-requests` | Branch view of batches, requests and Meet exceptions |
| `/branch/batches`, `/branch/schedule`, `/branch/meet-operations` | the screens above | as above | Where the Branch Manager prepares and confirms batches (one step) and decides transfers, capacity increases, material changes, merges / splits, replacement classes, cover and guests |
| `/branch/requests` | `branch/requests` | `/support-requests?escalated=true`, `/access-extension-requests` | Tabs Escalations (`BranchEscalations`) and Access extensions (`AccessExtensions`, with the note that repeated requests do not stack years) |
| `/branch/reports` | `shared/certificate-register` + summary | `/progress/summary`, `/certificates` | Certificates & reports |
| `/branch/notifications` | `shared/notification-centre` | | |
| `/admin` | `admin/dashboard` | `/admin/summary` | Integration failures, work awaiting a named owner, overdue payment verifications (Unavailable), integrations verified x / total, provisioning, open exceptions; CRM / LMS sync table, provisioning table, AI status, links |
| `/admin/users` | `admin/users` | `/admin/users/*` | Filters, role chips with revoke, add role (temporary access), reset password, deactivate / reactivate; temporary password shown once (`SecretDialog`) |
| `/admin/students` | `admin/students` | `/admin/students/*`, `/students/{id}/activation` | Search, "Activation link from" filter, detail dialog, activation link shown once, suspend / reactivate, revoke sessions |
| `/admin/integrations`, `/admin/security` | `admin/integrations`, `admin/security` | `/integrations`, `/security-controls` | Shared `readiness-table` (requirement, configuration, verification, evidence, owner, last check); Update dialog for Super Admin only; Founder reads |
| `/admin/calendar` | `admin/calendar` (`shared/academic-calendar`, also on `/branch/operations` and `/branch/schedule`) | `/calendar/closures` | Company holidays (Founder / Super Admin) and branch closures (recorded and approved by the Branch Manager) |
| `/admin/crm-sync` | `admin/crm-sync` | `/admin/crm-sync/*` | Inbox (filters, payload view, retry) and outbox; event types come from the data |
| `/admin/audit` | `admin/audit` | `/audit-log` | Filters by actor, entity, action, date (IST) |
| `/admin/exceptions` | `admin/exceptions` | `/exceptions` | "Exception Queues — all branches": a section per queue with a branch column (company-wide rows say "All branches"); Super Admin can Update, the Founder reads |
| `/admin/notifications` | `shared/notification-centre` | | The inbox, plus a "System issues" tab (delivery failures) for the Super Admin only |
| `/founder/curriculum` | `founder/curriculum` (reuses `academic/curriculum` `VersionEditor`) | `/curriculum-versions?status=` | Versions Under Review or Approved; Approve / Return / Activate |
| `/founder/certificates` | `founder/certificates` (`shared/certificate-register` `CertificateDecisions`) | `/certificate-requests`, `/certificate-financial-exceptions` | Revocations, reinstatements and fee exceptions to decide |
| `/verify/:number` | `routes/verify.$number.tsx` | `/certificates/verify/{number}` | Public, no sign-in and no shell (`OPEN_PATH_ROOTS`); `?version=` shows an older copy |
| `/founder` | `founder/dashboard` | `/founder/summary` | CRM tiles (Unavailable), active enrolments per branch, batches at risk, certificates awaiting approval, "Decisions needing you" (AI rupee ceiling, recording-access exceptions after the 2nd anniversary with a link to `/branch/requests`) |

Admin helpers: `features/admin/shared.tsx` (Pager, FormDialog, SecretDialog), `features/admin/format.ts` (IST
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
# LMS (from nipunalms/backend)
APP_ENV=development ../venv/bin/flask --app app run --port 5060

# CRM (from nipuna-crm/backend, APP_ENV=development)
flask --app app lms backfill            # events for everything that exists, branches first (--force after an LMS rebuild)
flask --app app lms worker              # deliver every 10 s and pull every minute (--duration N stops after N seconds)
flask --app app lms pull [--full]       # one pull now
flask --app app lms reconcile           # compare both sides per admission (--admission ID, --fix)
flask --app app lms outbox --failed     # counts and errors; lms holds lists pulled records waiting to apply
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
dashboards, both reports pages, staff notifications and `/account/profile`. CRM integration rounds 1–3 are done on both
sides (db 090–098; [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

**Gap fix plan** ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md), register [GAPS.md](GAPS.md)): the app was checked against the
approved modules 14–27, which found 109 gaps.

| Phase | Commit | Migration |
|---|---|---|
| 1. Correctness and privacy | `bf5569e` | 099 |
| 2. Deployment templates | `5a124d9` | — |
| 3. Governance and approvals | `ea71866` | 100 |
| 4. Academic Calendar | `be996e1` | 101 |
| 5. Module 14 curriculum model | `506a7e7` | 102 |

25 of the 109 gaps are closed. **Phase 6 (batches and delivery, Modules 15–16) is next**; the plan's "Resuming in a new
session" section lists the steps and what earlier phases changed.

Still to do:

| Item | Notes |
|---|---|
| Gap fix phases 6–12 | Batches and delivery, assessments, attendance and certificates, content and recordings, notifications and integrations, reports and AI, career and guardians (the last after CRM round 4) |
| Validation pass | A cross-role acceptance run (desktop + mobile) against the merged app, and a product / role guide like the CRM's `PRODUCT_GUIDE.md`. Not started |

---

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
| Sign-in | One login form, self-service reset code (WhatsApp; no email fallback yet), activation and staff invite links that sign the person in (UX phase U7, API.md §4.14). Templates 1–3 are queued like 4–9 and also stay off until the CRM endpoint exists |
| WhatsApp | Built and switched off (UX phase U6): messages are queued in `whatsapp_outbox` and handed to the CRM's `POST /lms/whatsapp`, which does not exist yet; needs `CRM_BASE_URL`, `whatsapp_enabled` and approved templates (API.md §4.13) |
| Email / telephony | None; in-app notifications only |
| Jobs scheduler | `flask jobs run` holds `recording-check`, `support-escalate-overdue`, `allocation-escalation`, `attempts-expire`, `attendance-unconfirmed`, `session-delay-check`, `class-log-check`, `class-reminders` and `whatsapp-send`; `deploy/crontab` runs them every 5 minutes on a server, but nothing runs them locally. New jobs go in `services/jobs.JOBS` |

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
| Pre-approved cover arrangements | Cover is requested, approved and verified per class (`session_cover_requests`). A standing cover rota with documented limits (Module 15 §11) is not modelled |
| Trainer availability, leave and travel buffers | Conflicts cover overlapping classes of the trainer, backup or assistant, booked rooms and the students' other classes; leave calendars, working hours and cross-branch travel buffers are not modelled |
| Material changes and future classes | Applying a material change updates the batch's plan (dates, mode, days / times); classes already scheduled are not re-timed automatically, the Branch Manager reschedules them |
| Shared classes beyond attendance | A joined batch's students see the class, are notified and are on its register; its recordings and content still follow the host batch |
| Phase 6 screens: API only or thin | No staff screen for slot requests (`GET / PATCH /slot-preferences`); an interbranch track placement has no target picker for another branch's batches; cover pickers list the class's branch only; shared-class topics, participant matching and disruption replacement / owner are typed as ids. Session reminders 24 h / 1 h before a class are not sent |
| Meet participation import | Join / leave evidence is entered through `POST /class-sessions/{id}/participation` (manual or a future Meet API feed); nothing imports it from Google yet |
| Bulk timetable import | Sessions are created one batch at a time with a repeat rule; no CSV / calendar import as in the prototype's schedule screen |
| Calendar month grid | Schedules are list / week tables; the prototype's month calendar view and iCal export are not built |
| Curriculum diff between versions | The prototype shows what changed between versions; only the review trail is stored |
| Re-mapping running batches to a new version | Activating a version maps pending enrolments and batches. A student moves through an individual academic mapping (`/academic-mappings`); moving a whole Running batch at once is not built |
| Academic mapping credits in the UI | The allocation queue's "Academic mapping" dialog prepares a version move without credits; credited topics are API only (`credits` with an approved `rule_id`). Proposing an equivalence rule is API only |
| Batch capacity waitlist | Students' slot requests can be marked Waitlisted, but there is no ordered waiting list or automatic offer when a seat frees up |
| Session reminders | Students are notified of changes and told when a class is 5 minutes late, but not reminded 24 hours / 1 hour before a class (Module 15 §20; needs a job) |
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
| Certificate document | No PDF / template and no email delivery (Email integration not verified); the register and public verification exist |
| Joining date on correction | An approved correction to Present sets the joining date; changing the first Present to Absent does not reset it |

### Student services

| Item | Notes |
|---|---|
| Fees & Receipts fields | The screen shows fee, verified paid, balance and receipts per course and one instalment schedule per invoice. `pending_verification`, `waived`, `refunded` and `payment_completion` are stored but not shown |
| Staff profile details | `/account/profile` is read-only: no phone number (the API does not return one for staff), MFA shown as Not Configured, staff cannot edit their name or email |
| Founder notifications | No event is addressed to the Founder role, so the founder workspace has no notification route or bell |
| Placement Team | Module 23 names a Placement Team role; there is none, so Branch Manager and Super Admin run career staff work. Employer-sharing per opportunity (individual consent references) and interview reminders are not built |
| Support SLA | One `support_sla_hours` for all categories and priorities |
| External channels | Email, quiet hours and delivery status for WhatsApp (Module 26) are not built; WhatsApp and email appear in preferences only when live |
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


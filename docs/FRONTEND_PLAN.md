# Nipuna LMS — Frontend Plan

React SPA in `frontend/`, built to mirror **nipuna-crm/frontend** (Vite + React 19, TanStack Router file routes, TanStack Query, shadcn/Radix, Tailwind 4). The product
is the approved interactive prototype (https://nipuna-lms-prototype.lovable.app/, readable copy in `prototype/reference/`); the API is described in
[API_PLAN.md](API_PLAN.md). Phase 1b (this document) delivers the foundation: shell, auth, per-workspace navigation, EN/తెలుగు, shared components and a placeholder
for every route. Slices S1–S6 then replace placeholders with real screens.

---

## 1. Decisions

| Decision | Choice | Why |
|---|---|---|
| Stack | Vite 8, React 19, TanStack Router (file routes, auto code splitting), TanStack Query, shadcn `new-york` + Radix, Tailwind 4, react-hook-form + zod, sonner toasts | Identical to the CRM; a change to one repo can be copied to the other |
| Dev ports | SPA `:5174` (preview `:4174`), API `:5060` via Vite proxy `/api` (`VITE_API_TARGET` overrides) | CRM uses 5173 / 5050; both stacks can run side by side. No CORS |
| Workspace from URL | `workspaceForPath(path)` — `/trainer*` trainer, `/academic*` academic, `/branch*` branch, `/admin*` admin, `/founder*` founder, everything else student (except `/login`, `/activate`, `/change-password`) | Same rule as the prototype |
| Who may open a workspace | `profile.workspaces` from `/auth/me` (already expanded per role: Super Admin also holds academic and branch, Founder also admin and branch); `canOpen(workspaces, workspace)` | The API is the authority; the SPA never derives access from role codes |
| Guard | Root route: public paths (`/login`, `/activate`) → anonymous → `/login?redirect=` → `must_change_password` → `/change-password` → workspace not permitted → **Permission Restricted** view (link home) → `/` redirects to `home_route`. Not a security boundary; every endpoint re-checks scope | Same as the CRM |
| Workspace switcher | Header `<select>` shown only when the user has more than one workspace; goes to that workspace's home | Replaces the prototype's UAT role simulator; no prototype banner, no "Demo" badges |
| Session | Bearer token in memory + `sessionStorage` (`nipuna-lms-session`); `["me"]` query holds the profile; `FRESH_AUTH_REQUIRED` opens a password dialog and retries once | Same as the CRM |
| Language | `en` / `te`, dictionary in `src/lib/i18n.ts`; choice stored per user in `localStorage` (`nipuna-lms-lang:<user_id>`), default `profile.student.preferred_language`; sets `<html lang>` (Telugu switches font and line height). Only student-workspace labels and the sign-in / activation screens are translated | Same scope as the prototype |
| Look | Prototype tokens (navy header, blue primary, tone colours) as CSS variables mapped onto shadcn variables; IBM Plex Sans + Noto Sans Telugu; `.tap` = 44px touch target | Visual parity with the approved prototype |
| Phones | Sidebar hidden below `md`; 5-slot bottom bar (4 items + More bottom sheet); `DataTable` turns into labelled cards | Prototype behaviour; e2e checks no horizontal scroll at 360px |
| Placeholders | One route file per prototype route imports a feature component from `src/features/<workspace>/`; the component is a `<Placeholder>` until its slice replaces it | Slices touch feature files only, never route files or the shell |
| Formatting | Prettier via ESLint, `printWidth: 160` (`.prettierrc.json`) | Matches the CRM's long-line style |

---

## 2. Structure

```
frontend/
├── index.html                 title "Nipuna LMS", IBM Plex Sans + Noto Sans Telugu
├── vite.config.ts             ports 5174 / 4174, /api proxy → :5060
├── playwright.config.ts       desktop + @mobile projects, baseURL :5174
├── e2e/
│   ├── helpers.ts             staging users (password Nipuna-staging-1), login()
│   └── shell.spec.ts          roles, nav, workspace guard, switcher, Telugu, phone bar
└── src/
    ├── main.tsx               QueryClient, router, AuthProvider
    ├── styles.css             Tailwind 4 theme + prototype tokens, .tap, :lang(te)
    ├── api/
    │   ├── client.ts          fetch wrapper: ApiError, bearer token, get / post / patch / put / del / list / upload / download
    │   ├── types.ts           RoleCode, Workspace, Language, BranchRef, DateTime …
    │   └── auth.ts            Profile types + authApi (login, me, logout, reauthenticate, changePassword, checkActivation, activate)
    ├── auth/
    │   ├── auth.tsx           AuthProvider, useAuth(), fresh-auth dialog
    │   └── access.ts          workspaceForPath, canOpen, NAV per workspace, mobileBarItems, isNavActive
    ├── lib/                   i18n.ts (dictionary, useT, useLanguage), mutation.ts (useApiMutation), utils.ts (cn)
    ├── hooks/                 use-mobile.tsx
    ├── components/
    │   ├── ui/                shadcn primitives (copied from the CRM)
    │   └── lms/               app-shell, ui, forms, placeholder, auth-page, language-toggle, password-field
    ├── routes/                thin file routes (see §3)
    └── features/              student/ trainer/ academic/ branch/ admin/ founder/  (+ shared/ when a slice needs cross-workspace parts)
```

Route file naming follows the CRM. `assignments` and `tests` use `assignments.index.tsx` + `assignments.$id.tsx` so the list and the detail are siblings (no
`<Outlet>`); `courses.$enrolmentId_.tracks.$trackId.tsx` (trailing underscore) keeps the track screen out of the enrolment route's nesting for the same reason.

---

## 3. Screens → API

Legend: **S1** Delivery · **S2** Content & recordings · **S3** Assessments · **S4** Attendance & certificates · **S5** Student services · **S6** Admin · **P3**
Phase 3 dashboards & reports. Title and description of every placeholder come from the prototype's route `head`.

### Student workspace (`student`)

| Route | Route file → feature | API from |
|---|---|---|
| `/dashboard` | `dashboard.tsx` → `student/dashboard` | P3 |
| `/my-courses` | `my-courses.tsx` → `student/my-courses` | S1 |
| `/courses/$enrolmentId` | `courses.$enrolmentId.tsx` → `student/course-detail` | S1 |
| `/courses/$enrolmentId/tracks/$trackId` | `courses.$enrolmentId_.tracks.$trackId.tsx` → `student/track-detail` | S1 |
| `/modules/$moduleId` | `modules.$moduleId.tsx` → `student/module-detail` | S1 |
| `/topics/$topicId` | `topics.$topicId.tsx` → `student/topic-detail` | S1 |
| `/sessions/$sessionId` | `sessions.$sessionId.tsx` → `student/session-detail` | S1 |
| `/schedule` | `schedule.tsx` → `student/schedule` | S1 |
| `/assignments` | `assignments.index.tsx` → `student/assignments` | S3 |
| `/assignments/$id` | `assignments.$id.tsx` → `student/assignment-detail` | S3 |
| `/recordings` | `recordings.tsx` → `student/recordings` | S2 |
| `/resources` | `resources.tsx` → `student/resources` | S2 |
| `/tests` | `tests.index.tsx` → `student/tests` | S3 |
| `/tests/$id` | `tests.$id.tsx` → `student/test-detail` | S3 |
| `/attendance` | `attendance.tsx` → `student/attendance` | S4 |
| `/progress` | `progress.tsx` → `student/progress` | S4 |
| `/results` | `results.tsx` → `student/results` | S3 |
| `/certificates` | `certificates.tsx` → `student/certificates` | S4 |
| `/career` | `career.tsx` → `student/career` | S5 |
| `/ask-nipuna` | `ask-nipuna.tsx` → `student/ask-nipuna` | S5 |
| `/support` | `support.tsx` → `student/support` | S5 |
| `/notifications` | `notifications.tsx` → `student/notifications` | S5 |
| `/finance` | `finance.tsx` → `student/finance` | S5 |
| `/profile` | `profile.tsx` → `student/profile` | S5 |

### Trainer workspace (`trainer`)

| Route | Feature (`features/trainer/`) | API from |
|---|---|---|
| `/trainer` | `today` (`trainer.index.tsx`) | P3 |
| `/trainer/batches` | `batches` | S1 |
| `/trainer/sessions` | `sessions` | S1 |
| `/trainer/students` | `students` | S5 |
| `/trainer/reviews` | `reviews` | S3 |
| `/trainer/attendance` | `attendance` | S4 |
| `/trainer/content` | `content` | S2 |
| `/trainer/assignments` | `assignments` | S3 |
| `/trainer/assessments` | `assessments` | S3 |
| `/trainer/support` | `support` | S5 |
| `/trainer/notifications` | `notifications` | S5 |
| `/trainer/reports` | `reports` | P3 |
| `/trainer/ask-nipuna` | `ask-nipuna` | S5 |

### Academic Coordinator workspace (`academic`)

| Route | Feature (`features/academic/`) | API from |
|---|---|---|
| `/academic` | `dashboard` (`academic.index.tsx`) | P3 |
| `/academic/batches` | `batches` | S1 |
| `/academic/curriculum` | `curriculum` | S1 |
| `/academic/schedule` | `schedule` | S1 |
| `/academic/assessments` | `assessments` | S3 |
| `/academic/exceptions` | `exceptions` | P3 (exception queue view across slices) |
| `/academic/content-review` | `content-review` | S2 |
| `/academic/recording-exceptions` | `recording-exceptions` | S2 |
| `/academic/progress` | `progress` | S4 |
| `/academic/completion` | `completion` | S4 |
| `/academic/certificates` | `certificates` | S4 |
| `/academic/support` | `support` | S5 |
| `/academic/reports` | `reports` | P3 |

### Branch Manager, Super Admin, Founder

| Route | Feature | API from |
|---|---|---|
| `/branch` | `branch/dashboard` (`branch.index.tsx`) | P3 |
| `/branch/operations` | `branch/operations` | S1 |
| `/branch/requests` | `branch/requests` | S2 (access extensions) + S5 (escalations) |
| `/branch/reports` | `branch/reports` | S4 |
| `/admin` | `admin/dashboard` (`admin.index.tsx`) | P3 |
| `/admin/integrations` | `admin/integrations` | S6 |
| `/admin/security` | `admin/security` | S6 |
| `/admin/exceptions` | `admin/exceptions` | P3 |
| `/founder` | `founder/dashboard` (`founder.tsx`) | P3 |

### Public and account screens (built in Phase 1b)

| Route | Notes | API |
|---|---|---|
| `/login` | Student ID / student email / staff email + password, show / hide password, forgot-password guidance ("Ask your branch Academic Coordinator to reissue an activation link"), activation-state explanation, EN/తెలుగు | `POST /auth/login` |
| `/activate?token=` | Checks the token (valid / expired / used), set + confirm password, success → `/login` | `GET /auth/activation/{token}`, `POST /auth/activate` |
| `/change-password` | Forced when `must_change_password`, also from the account menu | `POST /auth/change-password` |
| `/` | Never renders: redirects to `home_route` | `GET /auth/me` |

---

## 4. Shell and theme

**Header** (navy, sticky): logo → `home_route`; `role label · branch` chip (large screens); language toggle (student workspace); workspace switcher (only when the
user has several workspaces); notifications bell (student → `/notifications`, trainer → `/trainer/notifications`); account menu (Profile for students, Change password,
Sign out).

**Sidebar** (≥ `md`, 240px): the workspace's nav list from `NAV` in `auth/access.ts` (same items, labels, order and icons as the prototype). Student labels come from
the dictionary. **Bottom bar** (< `md`): four pinned items (`mobileBarItems`) + **More** bottom sheet with the rest of the list.

**Theme** (`src/styles.css`): the prototype's oklch tokens — `--navy`, `--navy-foreground`, `--navy-muted`, `--primary`, `--accent`, tone pairs `--success|warning|danger|info|neutral`
(+ `-soft`), `--radius: 0.625rem` — mapped onto shadcn's `--background/--card/--border/…`. Tone utilities: `bg-success-soft text-success`, etc.

**Shared components** (`components/lms/`): `PageHead`, `Section`, `Grid`, `Note`, `KeyValue`, `StatusNote` (13-state catalogue), `StatusBadge` (tone from the status text via
`toneFor`), `DataTable` (table → cards), `PillTabs`, `QueryView`, `ConfirmAction` in `ui.tsx`; `Field`, `NativeSelect`, `applyServerErrors`, `cleanBody` in `forms.tsx`.

---

## 5. Conventions for later slices

**Add an API file** — `src/api/<domain>.ts` (e.g. `courses.ts`): export the response types and an object of calls built on `get / list / post / patch / del` from `client.ts`
(paths without `/api/v1`). Query keys start with the domain: `["enrolments", "list", params]`. Mutations use `useApiMutation(fn, { success, invalidate: [["enrolments"]] })`.

**Build a feature** — put screens, tables and forms in `src/features/<workspace>/`. Fetch with `useQuery` and render with `<QueryView query={q}>{(data) => …}</QueryView>`;
lists use `DataTable` (or `list()` + pagination meta); forms use react-hook-form with `applyServerErrors(form, error)` in the mutation's `onError`. Student-facing strings that
must be bilingual go into `DICTIONARY` in `lib/i18n.ts` and are read with `useT()`; staff screens stay English.

**Replace a placeholder** — edit only the feature file the table in §3 names (e.g. `src/features/student/my-courses.tsx`): keep the exported component name, drop
`<Placeholder>`, render `PageHead` + your content. Route params: `const { enrolmentId } = useParams({ from: "/courses/$enrolmentId" })`. Do not touch route files, `app-shell.tsx` or
`access.ts` unless the slice adds a genuinely new route (then add the route file and nav entry, and a row in §3).

**Status wording** — use `StatusNote` states for loading / empty / partial / restricted / failed data and `StatusBadge` for row statuses; pass `tone` explicitly when the
text-based mapping is wrong.

**Tests** — one Playwright spec per slice in `e2e/`, logging in with `login(page, USERS.<role>)`. Tests that mutate data assume a freshly seeded staging database.

---

## 6. Running

```
cd frontend && npm install
npm run dev            # http://localhost:5174, proxies /api to http://127.0.0.1:5060
npm run typecheck && npm run build && npm run lint
npm run e2e            # needs the API on :5060 with the staging users; desktop + @mobile projects
```

Staging logins (password `Nipuna-staging-1`): student `NIT-STU-2026-004182`; staff `founder@`, `admin@`, `bm.gnt@`, `bm.vij@`, `coordinator.gnt@`, `coordinator.vij@`,
`trainer.g1@`, `trainer.v1@` `nipuna.test`.

## S3 — Assessments (as built)

| Route | Feature | API |
|---|---|---|
| `/assignments`, `/assignments/$id` | `student/assignments`, `student/assignment-detail` | `/assignments`, `/assignments/{id}/submissions` (text / link / file; the window explains replace vs resubmit) |
| `/tests`, `/tests/$id` | `student/tests`, `student/test-detail` | `/tests`, `/tests/{id}/attempts`, `/attempts/{id}/answers` (autosave every 10 s), `/attempts/{id}/submit`, interview slots. The timer counts down to the server's `deadline_at`, corrected for clock skew |
| `/results` | `student/results` | `/me/results` (provisional rows never show a score) |
| `/trainer/reviews` | `trainer/reviews` | `/submissions?status=Awaiting Review&reviewer_me=true`, start-review, review |
| `/trainer/assignments` | `trainer/assignments` | create / release / extend / withdraw, submissions list |
| `/trainer/assessments` | `trainer/assessments` (tabs: `test-builder`, `question-bank`, `grading`, `interviews`) | `/tests`, `/questions`, `/attempts`, slots |
| `/academic/assessments` | `academic/assessments` | `/assessment-reviews`, `/results`, moderate, publish, approve tests and questions |

`src/api/assessments.ts` holds all calls; `src/lib/format.ts` has the IST helpers (`formatIst`, `toIstInput` / `fromIstInput` for datetime-local inputs). Student screens keep the prototype wording. Spec: `e2e/assessments.spec.ts`.

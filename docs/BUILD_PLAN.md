# Nipuna LMS — What's missing and the plan to finish it

Snapshot 30 Sep 2026, `main` at `2643287`. Compared the running app (`frontend/src/features/*`) against the prototype
(`prototype/reference/screens/*`) for every role. A screen counts as **missing** while its feature file still renders
`<Placeholder>`.

## 1. Where things stand

| Slice | Status |
|---|---|
| Phase 1 — foundation, CRM intake, shell | Merged |
| S2 — Content & recordings | Merged |
| S4 — Attendance, progress & certificates | Merged |
| S6 — Admin & security | Merged |
| **S1 — Delivery** (courses, curriculum, batches, sessions, schedule) | **Built but not committed** in worktree `.claude/worktrees/agent-a48cc8c2e961d83a0` (db `010_delivery.sql`, 26 files changed + new files, e2e `delivery.spec.ts`). Docs (`API_PLAN`, `DB_PHASES`, `FRONTEND_PLAN`, `BACKLOG`) were **not** updated |
| **S3 — Assessments** (assignments, tests, results, question bank) | **Built but not committed** in worktree `.claude/worktrees/agent-a162927c7b20d9621` (db `030_assessments.sql`, e2e `assessments.spec.ts`, docs updated) |
| **S5 — Student services** (support, notifications, finance, profile, career, Ask Nipuna) | **Built but not committed** in worktree `.claude/worktrees/agent-a16dd51a7976e6314` (db `050_student_services.sql`, e2e `services.spec.ts`, docs updated) |
| **P3 — Dashboards, exceptions & reports** | **Not started.** Nothing built for it in any worktree |

All three unmerged worktrees branch from Phase 1 (`4fd55ba`), so none of them has S2, S4 or S6. Merging them means
resolving conflicts in shared files that `main` has changed since then:

- **All three:** `backend/cli/seed.py`, `backend/models/__init__.py`, `backend/routes/__init__.py`
- **S1:** `models/batches.py`, `models/enums.py`, `repositories/catalog.py`
- **S3 and S5:** `backend/api.http` and the four docs
- **S5:** `cli/__init__.py`, `models/system.py`

## 2. Missing screens by role

✅ built on `main` · 🟡 built in an unmerged worktree (slice in brackets) · ❌ not built anywhere

### Student

| Route | Screen | State |
|---|---|---|
| `/dashboard` | **Student Home** | ❌ P3 |
| `/my-courses` | My Courses | 🟡 S1 |
| `/courses/$enrolmentId` | Course (programme, tracks, modules, progress) | 🟡 S1 |
| `/courses/$enrolmentId/tracks/$trackId` | Track | 🟡 S1 |
| `/modules/$moduleId` | Module | 🟡 S1 |
| `/topics/$topicId` | Topic | 🟡 S1 |
| `/sessions/$sessionId` | Class Session | 🟡 S1 |
| `/schedule` | Schedule | 🟡 S1 |
| `/assignments`, `/assignments/$id` | Assignments, Assignment | 🟡 S3 |
| `/tests`, `/tests/$id` | Tests & Coding, Assessment | 🟡 S3 |
| `/results` | Results | 🟡 S3 |
| `/support` | Support | 🟡 S5 |
| `/notifications` | Notifications | 🟡 S5 |
| `/finance` | Fees & Receipts | 🟡 S5 |
| `/profile` | Profile | 🟡 S5 |
| `/career` | Career support | 🟡 S5 |
| `/ask-nipuna` | Ask Nipuna | 🟡 S5 |
| `/recordings`, `/resources` | Recordings, Resources | ✅ |
| `/attendance`, `/progress`, `/certificates` | Attendance, Progress, Certificates | ✅ |

The prototype's **Student Home** (`dashboard.js`) has these sections:

1. Welcome header with the student's name (EN / తెలుగు), Master ID and service branch.
2. Three ranked tiles: **Next class** (topic, date, IST time, mode, trainer), **Due work** (count and the nearest due item), **Course progress** (curriculum-delivered bar with a note that it is separate from attendance).
3. **Join Class** button (Meet, marked Pending Verification).
4. Cards:
   - **Continue learning** (track → module → topic link)
   - **Latest recording** (status and access-until date)
   - **Upcoming work** (next test)
   - **Attendance alert** (absence and recovery reference)
   - **Certificate status**
   - **Career support** (opt-in and profile %)
   - **Support** (open requests and owner)
   - **Ask Nipuna** (usage out of the daily limit)
5. **Stale data** note: engagement freshness is shown as Stale, never as zero.

### Trainer

| Route | Screen | State |
|---|---|---|
| `/trainer` | **Today** | ❌ P3 |
| `/trainer/reports` | **Reports** | ❌ P3 |
| `/trainer/batches`, `/trainer/sessions` | Batches, Sessions | 🟡 S1 |
| `/trainer/reviews`, `/trainer/assignments`, `/trainer/assessments` | Reviews, Assignments, Assessments (+ grading, interviews, question bank, test builder) | 🟡 S3 |
| `/trainer/students`, `/trainer/support`, `/trainer/notifications`, `/trainer/ask-nipuna` | Students, Support, Notifications, Ask Nipuna | 🟡 S5 |
| `/trainer/attendance`, `/trainer/content` | Attendance, Content | ✅ |

The prototype's **Today** page has:

- Tiles: assigned sessions in the next 7 days, submissions awaiting my review (with the oldest's age), assigned students with open support flags.
- **Today's flow** for the current session: open session → Join / Start Meet → save the topics delivered → attendance register → session notes → close out (recording mapping shows Pending Verification).
- An Empty state when no session is scheduled today, and a scope note (assigned batches and students only).

The prototype's **Reports** page has:

- Curriculum delivered per batch
- Trainer-confirmed attendance (batch average)
- Review turnaround (Partial Data when timestamps are missing)
- Engagement (Stale)

### Academic Coordinator

| Route | Screen | State |
|---|---|---|
| `/academic` | **Academic dashboard** | ❌ P3 |
| `/academic/exceptions` | **Exception / Recovery queue** | ❌ P3 |
| `/academic/reports` | **Academic Reports** | ❌ P3 |
| `/academic/batches`, `/academic/curriculum`, `/academic/schedule` | Batches (+ allocation queue), Curriculum, Schedule | 🟡 S1 |
| `/academic/assessments` | Assessments | 🟡 S3 |
| `/academic/support` | Support desk | 🟡 S5 |
| `/academic/progress`, `/academic/completion`, `/academic/certificates`, `/academic/content-review`, `/academic/recording-exceptions` | | ✅ |

What the prototype shows on each missing page:

- **Dashboard.** Tiles for:
  - enrolments awaiting batch allocation (including Curriculum Mapping Pending)
  - results awaiting publication review
  - unfulfilled recording promises
  - batches ready for delivery
  - academic reviews awaiting (content, assessments, completion)
  - open exceptions

  Plus quick links and the "four distinct records" note (Delivery Plan · Batch · Enrolment · Actual Class Session).
- **Exceptions.** One queue across slices: curriculum mapping, recording, allocation and provisioning. Each row has an owner, an Update action and a logged recovery step.
- **Reports.** Curriculum delivered (branch), attendance and approved recovery (branch average), completion reviews closed (Partial Data per branch), and certificate issue lead time (Not Configured).

### Branch Manager

| Route | Screen | State |
|---|---|---|
| `/branch` | **Branch academic dashboard** | ❌ P3 |
| `/branch/requests` | **Escalations & access extensions** | ❌ wiring only. The parts exist but nothing imports them: `features/branch/access-extensions.tsx` on `main` (S2) and `features/branch/escalations.tsx` in the S5 worktree. The route still renders a placeholder |
| `/branch/operations` | Batches, schedule & people | 🟡 S1 |
| `/branch/reports` | Reports | ✅ (S4) |

The prototype's **Dashboard** has:

- Tiles for verified collections vs target, new paid Admissions and overdue follow-ups. These are CRM figures, so they show "Unavailable / Not Configured" until the CRM sends them.
- Tiles for running or starting batches, schedule and recording exceptions, and open escalations and extension requests.
- "Go to" links, and a note that the view is locked to the manager's branch.

### Super Admin

| Route | Screen | State |
|---|---|---|
| `/admin` | **Super Admin overview** | ❌ P3 |
| `/admin/exceptions` | **Exception Queues — all branches** | ❌ P3 (BACKLOG: "belongs to the dashboards phase") |
| `/admin/users`, `/admin/students`, `/admin/integrations`, `/admin/security`, `/admin/crm-sync`, `/admin/audit` | | ✅ |

The prototype's **Overview** has:

- Tiles:
  - critical integration failures
  - work awaiting a named owner or cover
  - overdue payment verifications (Unavailable, from the CRM)
  - integrations verified (x / 8)
  - failed provisioning
  - open exceptions across all queues
- CRM/LMS sync and provisioning exception links, an AI status card, and "Go to" links.

### Founder / CEO

| Route | Screen | State |
|---|---|---|
| `/founder` | **Founder / CEO overview** | ❌ P3 |

The prototype's **Overview** has:

- Tiles for verified collections vs target, new paid Admissions vs target and overdue amount. These are CRM figures and show Not Configured, never zero.
- Tiles for active enrolments in delivery (per branch), batches at delivery risk and certificates awaiting approval.
- **Decisions needing you**: the AI rupee ceiling, and recording-access exceptions after the second anniversary.
- Links to the Super Admin and Branch views.

### Cross-role gaps (logged in the S5 backlog)

- The notification bell and route exist only for student and trainer. Academic, branch and admin need `/…/notifications` and a nav entry.
- There is no staff profile screen (`GET /me/profile` already works for staff).

## 3. Plan

### Step 1 — Merge S1 Delivery (first, because everything else reads courses, batches and sessions)

1. In the S1 worktree: run `pytest -q`, `npm run typecheck`, `npm run lint`. Fix any failures.
2. Update `API_PLAN.md`, `DB_PHASES.md` (010), `FRONTEND_PLAN.md` and `BACKLOG.md` for S1 — this part was never done.
3. Commit on the worktree branch, rebase onto `main` and resolve conflicts:
   - **Registration lists** (`models/__init__.py`, `routes/__init__.py`, and `SEEDERS` in `cli/seed.py`): keep both sides.
   - **Overlapping models and repositories** (`batches.py`, `enums.py`, `catalog.py`): merge the columns and enum values by hand, and check them against db 005, 020 and 040.
4. Rebuild the dev DB (`create-dev-db --yes` + `seed-dev`), run the full backend suite, then `delivery.spec.ts` + the existing e2e.
5. Merge to `main` ("Merge S1 delivery").

### Step 2 — Merge S3 Assessments

Same routine as Step 1: test in the worktree, commit, rebase, resolve conflicts, rebuild the DB, run e2e, merge. Extra checks:

- **Due-work facts:** register S3's provider for Ask Nipuna, or leave a note for Step 3.
- **Reminders:** register the S3 reminder jobs in `services/jobs.JOBS`, since the jobs runner arrived with S2.

### Step 3 — Merge S5 Student services

Same routine. Extra checks:

- **Shared components:** S1 and S5 both add files under `frontend/src/features/shared/`. Check that no two files share a name and that the helpers don't duplicate each other (e.g. `ist.ts` vs `shared/format.ts`; done: folded into `format.ts`).
- **Jobs:** move `cli/support_jobs.py` into the S2 jobs runner (`flask jobs run`) rather than keeping a separate CLI.
- **Ask Nipuna:** hook up the S3 due-work provider.

### Step 4 — Wire `/branch/requests`

Compose `access-extensions.tsx` (S2) and `escalations.tsx` (S5) into one tabbed page:

- Tab **Escalations**
- Tab **Access extensions**, with the note "Repeated extension requests do not stack years"

Add an e2e check.

### Step 5 — P3: exception queue (backend first)

- `db/080_exception_queue.sql`: an `exception_queue` view that unions the open exceptions each slice already stores:
  - curriculum mapping pending (S1)
  - unallocated enrolments (S1)
  - recording exceptions (S2)
  - failed CRM events and provisioning (Phase 1 / S6)
  - overdue support (S5)
  - results awaiting publication (S3)

  Each row carries `source`, `branch_id`, `owner`, `age`, `state` and `link`.
- Endpoints:
  - `GET /exceptions` (branch-scoped)
  - `POST /exceptions/{source}/{id}/steps` (log a recovery step, audited)
- Screens:
  - `/academic/exceptions`: one branch, with the Update action
  - `/admin/exceptions`: all branches, grouped by queue

### Step 6 — P3: dashboards (one summary endpoint per workspace)

Each dashboard gets a single endpoint so the page makes one request. Each endpoint only aggregates existing services.
**CRM figures** (collections, paid Admissions, overdue amounts, payment verifications) come from `finance_summaries` where
present. Otherwise they are returned as `{state: "Not Configured"}` so the UI shows **Unavailable**, never 0. Stale
sources carry `refreshed_at`.

| Order | Screen | Endpoint | Pulls from |
|---|---|---|---|
| 1 | Student Home `/dashboard` | `GET /me/home` | next session + Join (S1), due work (S3), curriculum-delivered % (S4), latest recording (S2), attendance alert + certificate status (S4), career/support/Ask Nipuna usage (S5) |
| 2 | Trainer Today `/trainer` | `GET /trainer/today` | assigned sessions (S1), review queue (S3), support flags (S5); the "Today's flow" stepper reuses S1 session delivered-topics + S4 attendance register + session notes/close-out |
| 3 | Academic dashboard `/academic` | `GET /academic/summary` | allocation queue (S1), results awaiting publication (S3), recording exceptions (S2), batch readiness (S1), review counts (S2/S3/S4), exception count (Step 5) |
| 4 | Branch dashboard `/branch` | `GET /branch/summary` | CRM figures (Not Configured), batches (S1), exceptions, escalations + extensions (S2/S5) |
| 5 | Super Admin `/admin` | `GET /admin/summary` | integration readiness (S6), CRM sync / provisioning failures (S6), unowned work + exceptions (Step 5), AI status (S5) |
| 6 | Founder `/founder` | `GET /founder/summary` | CRM figures (Not Configured), active enrolments per branch, batches at risk, certificates awaiting approval (S4), decisions (AI ceiling config, anniversary access exceptions from S2) |

Each dashboard gets a pytest for scope (branch lock, trainer assigned-only) and a Playwright check of its tiles, on both
desktop and `@mobile`.

### Step 7 — P3: reports

- **`/trainer/reports`**: curriculum delivered per assigned batch, trainer-confirmed attendance, review turnaround (from S3 timestamps, showing Partial Data when some are missing), and engagement (Stale).
- **`/academic/reports`**: curriculum delivered, attendance and approved recovery, completion reviews closed, and certificate issue lead time. Reuse the S4 branch summary, and add the S1 delivered % and S3 turnaround.

### Step 8 — Cross-role finish

- Add notification routes and the header bell for the academic, branch and admin workspaces, reusing the S5 `notification-centre.tsx`.
- Add a staff profile route (`/account/profile`) on `GET /me/profile`.
- Update `FRONTEND_PLAN.md` §3 so no route is left on a placeholder, then delete `components/lms/placeholder.tsx`.

### Step 9 — Clean up

- Remove the six agent worktrees (`git worktree remove`) and delete their branches once merged.
- Drop the per-slice dev and test databases (`nipunalms-*-dev`, `nipunalms_*_test`).

## 4. Out of scope here (already in BACKLOG.md)

These are product decisions, or depend on integrations that aren't live yet. They stay in the backlog and don't block
the steps above:

- CRM event emission and outbox delivery
- Google Meet and Drive, including recording playback
- WhatsApp and email delivery
- Minute-based attendance
- Completion profiles per course
- Certificate PDF
- Emergency access and student MFA
- The assessment extras: individual extensions, reassessment, coding runner and plagiarism flags
- The AI spend ceiling

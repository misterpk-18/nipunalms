# Role separation plan (draft)

Goal: every role gets its own, complete view. No "Acting as" switcher, no screen that changes shape depending on which other roles the person holds, and nothing a user needs is hidden or hard to find.

## Decisions made

| # | Decision | Choice |
|---|---|---|
| 1 | Multi-role model | **One account per role.** A login carries exactly one role. |
| 2 | Implicit extra workspaces | **Removed.** Super Admin no longer gets Branch; Founder no longer gets Admin + Branch. They get cross-branch filters inside their own pages. |
| 3 | Backend enforcement | **Yes.** Authorization uses the account's single role, not the union. |
| 4 | Multi-branch Branch Manager | **Pick branch at sign-in.** Branch is fixed for the session and shown in the header. |
| 5 | Curriculum | **Replaced by Courses.** There are no curriculum versions, drafts or approvals; only courses. |
| 6 | Who edits courses | **Super Admin and Founder** (Founder is a superset of Super Admin, decision 16). Branch Manager read-only. |
| 7 | Split-account sign-in | **Separate email per role.** No change to the unique-login rule. |
| 8 | Migrating multi-role users | **Keep the primary role on the existing account; create a new account for each extra role.** Super Admin gets a list to hand out credentials; affected sessions end. |
| 9 | Shared screens | **One shared component with a fixed config per role.** Components never call `hasRole` themselves. |
| 10 | Curriculum data | **Drop the curriculum draft, version and approval tables in a migration.** Courses stay. |
| 11 | Where the outline lives | **On the course itself.** Every table that points at `curriculum_version_id` (14 migrations: 002, 003, 004, 005, 010, 020, 030, 040, 095, 097, 098, 102, 105, 109) is re-pointed to the course before the version tables are dropped. |
| 12 | What is editable on a course | **Only modules and topics** (in the LMS). Code, title, status and tracks stay read-only, owned by the CRM `CourseUpserted` event. |
| 13 | Course features kept | **Completion rules, hours and required assessments**, now on the course. Draft, version, checklist and approval are removed. |
| 14 | Editing a course with running batches | **Applies at once, affected Branch Managers are notified, change is audited.** |
| 15 | Super Admin and branch work | **Read-only cross-branch views plus an Approvals page** under `/admin`. Branch actions stay with Branch Managers. |
| 16 | Founder | **Everything Super Admin can do, plus approvals,** with read-write, across all branches, under `/founder`. Day-to-day branch actions (attendance, running classes) stay with Branch Managers. Gets a notification bell, inbox and Getting started card. (This also lets the Founder edit course outlines; decision 6 now reads "Super Admin and Founder".) |
| 17 | "All branches" at sign-in | **No.** One branch per session. Cross-branch views belong to Super Admin and Founder. |
| 18 | Calendar | **Branch Manager proposes closures, Super Admin approves.** Founder and Super Admin add company-wide holidays. |
| 19 | Issues "Go fix it" for Super Admin | **Opens a read-only detail under `/admin`,** with Assign to the right Branch Manager. |
| 20 | Trainer courses | **Read-only outline block on the batch page.** No new nav item. |
| 21 | Career/placements staff screens | **Out of scope.** Recorded in `docs/GAPS.md`. |
| 22 | Credential hand-out | **Hand-out page in Users & access** with a one-time activation link per new account. |
| 23 | Primary role on a split user | **Founder > Super Admin > Branch Manager > Trainer > Student.** |
| 24 | Super Admin Approvals page | **Same inbox as the Founder:** Super Admin and Founder can both see and decide every item (fee exceptions, access extensions, certificates, AI budget, Branch Managers' own requests). The existing independence rule (nobody decides their own request) still applies. |
| 25 | Course extras kept | **Combo track pins and the reusable module library** survive on the course. Equivalence rules, branch variations and the "prepare mapping" helper are removed. |

## What is wrong today

- One shared shell; the "active role" is only the URL prefix (`frontend/src/auth/access.ts:54-62`).
- The "Acting as" menu only navigates between prefixes (`frontend/src/components/lms/acting-as.tsx`).
- The session carries no role; every request is authorized against the union of all scopes (`backend/routes/decorators.py`, `backend/services/scope.py`).
- Super Admin and Founder get extra workspaces automatically (`backend/services/auth.py:25-31`).
- Shared pages decide what to show from `hasRole(...)`, not from where you are: notification centre, academic calendar, support desk, issues list, batch panel, AI controls, staff profile.

## Target state

- Five roles, five separate experiences: Student, Trainer, Branch Manager, Super Admin, Founder/CEO.
- One login = one role. The session stores that role. Header shows `Role · Branch` as a plain label, no dropdown.
- Branch Manager with several branches picks the branch at sign-in. Changing branch means signing in again (or "Change branch", which ends the session and returns to the picker).
- Every nav item lives under exactly one role's prefix. A role never sees another role's screens, and never sees a screen that behaves differently because of a second role.

## Phases

### R1. Inventory and per-role screen map (no code)
- Per role: full list of screens, what each does, what the user can do, where it is in the nav.
- Find every screen a role can reach today only through another role's workspace, and decide where it belongs.
- Find the "hidden" paths: things reachable by URL but not by nav, and nav items with no clear purpose.
- Output: `docs/ROLE_SCREEN_MAP.md`.

### R2. Data model: one role per account
- Migration: for each user with several roles, keep the highest role on the existing account and create a new account (own email, e.g. `name.trainer@...`) for each other role. Produce a hand-out list for Super Admin. End the sessions of every user that was split.
- `user_role_scopes` constraint: one active role per user; branch scopes only for Branch Manager.
- Admin "Users" screen: create/edit one account per role; remove the "add role" form.
- End sessions of any user that was split.

### R3. Backend: session role and enforcement
- Resolve the single role in `services/auth.py`; drop the implicit `WORKSPACE_ROLES` fan-out (Super Admin → branch, Founder → admin + branch).
- Add the active role (and active branch, for Branch Manager) to the session and `CurrentUser`.
- Tighten `services/scope.py`: `visible_branch_ids`, `require_branch`, trainer batch scope use the single role.
- Re-check the ~40 `require_roles(...)` patterns in `backend/routes/*` so no endpoint depends on a second role.
- Remove union-dependent branches: `support.py` trainer flag, `my_requests.py`, `ask_nipuna.py` audience, `delivery_access.py`.
- `/me/nav-counts` and `/me/getting-started` take the role from the session, not a `workspace` query parameter.
- Tests: update `backend/tests/test_auth.py`; add cross-role denial tests.

### R4. Frontend shell: remove "Acting as"
- Delete `acting-as.tsx`, `useActing`, `acting-branch.ts` localStorage pick.
- Header shows a static `Role · Branch` label.
- Add the branch picker at sign-in for multi-branch Branch Managers.
- Landing: login goes straight to the account's one home route; the `/` and `AccessDenied` flows simplified.
- `workspaceForPath` and `canOpen` stay as a guard, but the workspace now comes from the session.

### R5. Split the shared screens per role
Each shared screen becomes a role-specific screen (or a shared component with a fixed per-role config, never `hasRole` checks inside):
- Notifications (System issues tab only on Super Admin's page)
- Academic calendar (central vs proposer/approver variants)
- Support desk (student, trainer, branch)
- Issues list (branch vs admin)
- Batch panel and class operations
- AI controls (admin and founder copies)
- Staff profile (shows only the account's role and branch)
- Command palette (result links are per role)
Remove the cross-feature imports (`founder/*` importing `branch/*`, `branch/content` importing `trainer/question-bank`) by moving shared pieces into `features/shared` as role-neutral components.

### R6. Curriculum → Courses
- Nav: Branch "Curriculum" → read-only "Courses"; Founder "Curriculum approvals" removed (including the inbox badge); Super Admin gets "Courses" with create/edit.
- Remove draft, version, checklist and approval UI and endpoints (`features/academic/curriculum*.tsx`, `branch.curriculum`, `founder.curriculum` routes).
- Database: a migration drops the curriculum draft, version and approval tables (from `db/102_curriculum_model.sql` and related). First list every foreign key, view and query that touches them, and confirm that batches, enrolments, sessions and topic progress still hang off courses only. Courses are never dropped.
- Founder inbox and nav counts: drop the curriculum item.
- Add the migration to `docs/DATABASE.md`.

### R7. Make everything visible
- Every role's sidebar and phone bottom bar reviewed so each task a role does is reachable in at most two taps.
- Empty states and "where do I go next" hints on each landing page, driven by the screen map.
- Remove dead nav items and unlabeled icons.
- Add per-role "Getting started" checklist where missing.

### R8. Tests and docs
- e2e: rewrite `frontend/e2e/shell.spec.ts` (no switcher; one nav per account; cross-role denial; branch picker at sign-in).
- Seed data: one account per role, for each existing staging user.
- Update `docs/UX_PLAN.md` (line 55 decision), `docs/DEVELOPMENT.md` (workspace/acting-as rows), `docs/API.md` (role table, nav-counts), `docs/DATABASE.md`, `docs/GAPS.md`.

## Risks

- Existing people holding several roles lose single sign-on across them. They need clear sign-in guidance and migrated accounts.
- The backend change touches most of the role guards; it needs the full backend test suite and a staging pass before frontend work depends on it.
- The CRM integration (`docs/CRM_INTEGRATION.md`) assumes the current roles; check no event intake depends on a multi-role user.

## Build rules

- The `@fresh_auth` (recent password) guard stays on the same sensitive actions as today, for Founder and Super Admin alike.
- Course code, title, category, status and tracks stay owned by the CRM `CourseUpserted` event, for every role (decision 12).
- R2 starts by checking that no CRM event intake relies on a user holding more than one role; any that does is changed as part of R2.

Detailed per-role screens, the shared-screen config tables and the list of cross-feature imports are in `docs/ROLE_SCREEN_MAP.md`.

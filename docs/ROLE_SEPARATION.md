# Role separation: plan, checklist and screen specs

One file for the whole change. Part A is the checklist to work through. Part B is the decisions and the target state. Part C is the per-role screen specs and shared-screen configs the checklist refers to (file:line references are against commit `ae7ee4c`; paths are relative to `frontend/src/` unless they start with `backend/` or `db/`).

Goal: every role gets its own, complete view. No "Acting as" switcher, no screen that changes shape depending on which other roles the person holds, and nothing a user needs is hidden or hard to find.

---

# Part A. Checklist

Work top to bottom. R2 and R3 (data and backend) come before any frontend phase, because the frontend needs the session to carry one role. Do the work on a feature branch off `main`.

## R0. Before any code

- [x] Create a feature branch off `main` (`role-separation`)
- [x] Take a backup of the staging database before running any migration (`~/nipunalms-dev-backup-pre-role-split-2026-10-18.dump`, `pg_dump -Fc` of `nipunalms-dev`)
- [x] Check that no CRM event intake (`docs/CRM_INTEGRATION.md`, `backend/routes/crm*`, `backend/services/crm*`) relies on a user holding more than one role; change any that does as part of R2 (none does: intake only notifies by `role_code` + branch, and `/crm` admin routes need Super Admin)
- [x] Count users with more than one active row in `user_role_scopes` (dry run), and list them with their roles and branches (6 on `nipunalms-dev`, all e2e leftovers `trainer.e2e.*@nipuna.test` with Trainer + Branch Manager at Guntur: users 116, 128, 129, 140, 145, 146; no Branch Manager holds two branches; Founder and Super Admin hold one role each. Note: Student and Trainer scopes also carry a branch today, 81 and 24 rows, so the R2 constraint keeps a branch on those roles and only forbids several rows for anything but Branch Manager)
- [x] Note the next free migration number in `db/` (118)

## R1. Inventory (done)

- [x] Per-role screen map (Part C)
- [x] Decisions recorded (Part B)

## R2. Data model: one role per account

- [x] Migration: for each user holding several roles, keep the highest role on the existing account (order Founder > Super Admin > Branch Manager > Trainer > Student) and create a new account for each other role, with its own email (for example `name.trainer@...`) (`db/118_split_multi_role_accounts.sql`)
- [x] Migration: move each non-primary scope (role and branch) onto its new account and revoke it on the old one (`db/118`)
- [x] Migration: end the sessions of every user that was split (`db/118`)
- [x] Migration: record every new account in a table the hand-out page reads (account, role, branch, one-time activation link, created at, handed out at) (`db/118`: `split_account_handouts`; the link itself is issued from the hand-out page, because only a token hash is stored)
- [x] Constraint on `user_role_scopes`: one active role per user; branch scopes only for Branch Manager; company-wide roles take no branch (`db/119_one_role_per_account.sql`, trigger `check_one_role_per_user`)
- [x] Backend: stop `admin_users` accepting several scopes per user (`backend/routes/admin_users.py`, `backend/services/admin_users.py`); remove `POST /admin/users/<id>/scopes` (grant) behaviour that adds a second role (`services/admin_users.py`; `POST /admin/users/<id>/scopes` now only adds a branch to a Branch Manager; hand-out endpoints in `routes/admin_users.py`, `services/handouts.py`)
- [x] Users & access screen (`features/admin/users.tsx`): create one account per role; remove the "Add role" form (`:210,282,362-400`) and `adminApi.grantScope`; change the Founder description at `:36` (`features/admin/users.tsx`, `api/admin.ts`; no add-branch control, the API route remains; e2e `admin.spec.ts` updated)
- [x] Hand-out page in Users & access, visible to Super Admin and Founder: list of accounts created by the split, one-time activation link per account, mark as handed out (section at the foot of Users & access)
- [x] Migration test on a copy of staging data: row counts before and after, no user left with two roles, no orphaned scopes (dry run on a pg_dump copy, then applied to `nipunalms-dev`: users 266 to 272, live scopes 115 to 115, 0 multi-role users, 0 orphaned scopes)

## R3. Backend: session role and enforcement

- [x] `backend/services/auth.py`: resolve the single role; delete the implicit `WORKSPACE_ROLES` fan-out (Super Admin to branch; Founder to admin and branch); one workspace and one home route per role (`WORKSPACE_OF_ROLE` and `HOME_OF_WORKSPACE`, one workspace and one home route per role; `workspaces` in the API is a one-element list)
- [x] Add the active role (and, for Branch Manager, the active branch) to the session and to `CurrentUser` (`backend/services/context.py`) (db/120 adds `user_sessions.role_code` and `branch_id`; `CurrentUser.role_code`, `active_branch_id`, `needs_branch`; `scopes` holds only the session's scope)
- [x] Sign-in for a Branch Manager with several branches: return the list of branches, accept the chosen branch, store it on the session; a branch outside the account's scope is refused (login returns a real token plus `needs_branch: true` and `branches`; `POST /auth/branch {branch_id}` fixes the branch, or send `branch_id` on login; outside the account is 403; other endpoints answer 403 `BRANCH_REQUIRED` until picked; see API.md 4.22)
- [x] "Change branch" ends the session and returns to the branch picker (`POST /auth/change-branch`, 204; the frontend returns to sign-in and picks again)
- [x] `backend/services/scope.py`: `visible_branch_ids`, `require_branch`, `trainer_batch_ids` and the `assert_can_view_*` helpers use the single role and, for Branch Manager, the session's branch (`visible_branch_ids` is all for Super Admin and Founder, the session's branch for a Branch Manager, empty otherwise; `trainer_batch_ids` reads the session role; notices also follow the session's branch)
- [x] Re-check the roughly 40 `require_roles(...)` patterns in `backend/routes/*` so none depends on a second role (each route reviewed: branch actions are Branch Manager only through `MANAGE_ROLES`, `MODERATOR_ROLES`, `ASSESSMENT_AUTHOR_ROLES` and the per-route tuples; Super Admin-only guards now also admit the Founder; the table is in API.md 4.22)
- [x] Remove the union-dependent logic listed in 7.16: `backend/services/support.py` trainer flag, `my_requests.py:88`, `ask_nipuna.py:95`, `delivery_access.py:22`, `search.py:19` (support trainer flag and student check, `my_requests`, `ask_nipuna`, `delivery_access`, `search` now read `role_code`)
- [x] `/me/nav-counts` and `/me/getting-started` read the role from the session, not a `workspace` query parameter (`backend/services/nav.py`) (`workspace` and `branch_id` query parameters accepted and ignored)
- [x] `/me/nav-counts` and `/me/getting-started` work for the Founder (bell counts, Getting started card) (Founder counts = Super Admin counts plus inbox keys; Getting started = the Super Admin's two steps with `/founder/...` links; notification endpoints are role-neutral)
- [x] Keep `@fresh_auth` on the same sensitive actions as today, for Founder and Super Admin alike (unchanged on every route; Founder and Super Admin share the same guards)
- [x] Founder: allow the Founder everything the Super Admin can do on the backend (admin users, CRM Retry, setup edit, calendar decisions, issue assign, course outline edit) and the same inbox (admin users, CRM Retry, setup/integrations/security edits, calendar decisions, issue assign and notes, student suspend and activation links, course outline edit, inbox)
- [x] Super Admin: allow the Super Admin to decide every Founder-inbox item, keeping the independence rule (nobody decides their own request) (unchanged inbox for both; nobody decides their own request; `approvals.admin_may_decide` replaces `founder_may_decide`, and batch capacity, transfer, merge or split, material change, cover, guest and reschedule requests of a Branch Manager are decided by an admin)
- [x] Super Admin and Founder reports: serve `/admin/reports` and `/founder/reports` from `GET /academic/reports` with a branch filter (removes the Founder 403 on `/branch/reports`) (`GET /academic/reports?branch_id=` serves both; `/branch/reports` is Branch Manager only)
- [x] Super Admin and Founder read-only cross-branch endpoints with a branch filter: batches, students, attendance, support (read and reassign) (batches, students, attendance, progress, support, issues and finance summaries already take `?branch_id=` and are open to both; attendance marking, class operations, results publishing, content review stay Branch Manager only; allocating a student to a batch, and taking the seat away, is the one branch action Super Admin and Founder share: `/admin/waiting`, `/founder/waiting`)
- [x] Update `backend/tests/test_auth.py`; add tests: each role reaches only its own workspace, a split user cannot reach the other role's data, Branch Manager cannot see another branch, Super Admin has no branch actions, Founder has Super Admin's actions (`test_auth.py` updated; new `test_session_role.py`, 19 tests; the two skipped reschedule tests rewritten; about 20 tests in other files updated to the new model)
- [x] Run the full backend test suite and a staging pass before starting R4 (full suite green; staging pass on a temporary API at :5061 against `nipunalms-dev`, sign-in plus one request per role; see the R3 report)

## R4. Frontend shell: remove "Acting as"

- [x] Delete `components/lms/acting-as.tsx`, `auth/acting.ts` and `lib/acting-branch.ts` (the localStorage branch pick); update the 20 or so callers that use `useActing("branch")` to read the session's branch (all three files deleted; callers read `useAuth().branchId`, null for Super Admin and Founder; `branches` readers use `allowedBranches`)
- [x] Header shows a static `Role · Branch` label (`components/lms/app-shell.tsx:115-121`) (also in the account menu header and avatar title; Super Admin and Founder show `Role · All branches`)
- [x] Remove the repeated `BranchPicker` from page heads (`features/branch/my-work.tsx:37-51`) (component and all 11 uses removed; the Branch Manager's one branch is fixed on the session)
- [x] Branch picker on the sign-in screen for Branch Managers with several branches; "Change branch" in the account menu (new `components/lms/branch-pick.tsx`, rendered by the root guard while `needs_branch` is true, calls `selectBranch` and lands on `home_route`; "Change branch" in the account menu for a Branch Manager with more than one branch calls `changeBranch`, clears the local session and routes to `/login`. Not exercised in a browser: the dev data has no multi-branch Branch Manager)
- [x] Landing: sign-in goes straight to the account's one home route; simplify `routes/__root.tsx` and the `AccessDenied` flow (login returns at once to `home_route` or `redirect`; `AccessDenied` now names the session role and says "cannot open this page")
- [x] `workspaceForPath` and `canOpen` stay as a guard; the workspace comes from the session (`auth/access.ts:54-70`) (the shell's navigation and the palette use `useAuth().workspace`; `homeWorkspace` and `WORKSPACE_DESCRIPTIONS` removed; the command palette lists only the session workspace's pages)
- [x] Remove stale comment at `auth/auth.tsx:19-20` (it described a Super Admin also holding academic and branch workspaces; replaced)
- [x] `useNavCounts` and `GettingStartedCard` take the role from the session, not a `workspace` argument (no arguments; the API reads role and branch from the session)

## R5. Shared screens: one component, fixed config per role

No component calls `hasRole`, `useCanManage`, `useIsManager` or `useCanAdminister` itself; the route passes the config (tables in Part C, section 7). Remove those hooks once nothing uses them.

- [x] 7.1 Notification centre: `showSystemIssuesTab` (Super Admin and Founder only); add the Founder route `/founder/notifications` (`NotificationCentre` takes `showSystemIssuesTab` from the route (Super Admin and Founder pass it); `/founder/notifications` added and the shell's bell now has a Founder entry; backend notification endpoints were already role-neutral and show delivery failures to Founder too)
- [x] 7.2 Staff profile: role and branch label from the session (`StaffProfile` takes `role` and `branchLabel`; `routes/account.profile.tsx` reads them from the session)
- [x] 7.3 Academic calendar: one component replacing `features/admin/calendar.tsx` and `features/shared/academic-calendar.tsx`; Branch Manager proposes, Super Admin and Founder approve (`features/shared/academic-calendar.tsx` + `calendar-dialogs.tsx`, `CalendarConfig` (`CALENDAR_CENTRAL`, `calendarForBranchManager`); routes `/admin/calendar`, `/founder/calendar`, Branch Manager section in Schedule. Backend: a Branch Manager's closure is created Pending, only Super Admin/Founder decide, edit or cancel; the proposer is told the outcome; proposals notify Super Admin and Founder with their own links)
- [x] 7.4 Issues list: props `canNote`, `canAssign`, `branchScoped`, `goFix` per role (`IssuesList` props `canNote`, `canAssign`, `branchScoped`, `goFix`; `features/shared/issues.tsx` has the Branch Manager page, `CrossBranchIssues` (branch filter) and `IssueDetail`; `backend/services/issues.py` builds `go_fix` from the session role, new `GET /issues/{source}/{id}`; routes `/admin/issues`, `/founder/issues`, `/{admin,founder}/issues/$source/$id`. System-type issues link to `/founder/students|crm-sync|setup` for the Founder, which the per-role phase still has to create)
- [x] 7.5 Support desk: `simple`, `views`, `canReassign`, `canEscalate`, `branchId` per role; remove the duplicate `canEscalate` row from the table (props `simple`, `views`, `branchId`, `branchFilter`, `canReassign`, `canEscalate`, `canRespond` (off for Super Admin and Founder: they read and reassign); `profile.scopes` read removed; routes `/admin/support`, `/founder/support`)
- [x] 7.6 Batch page parts and operations: `manage` and `approve` only for Branch Manager; read-only for Super Admin and Founder with a branch filter (`manage` and `approve` are props from the route (true only on `/branch/*`); `useCanManage` and `useIsManager` deleted (nothing used them); `BatchList` and `BatchPage` serve `/branch/batches`, `/admin/batches` and `/founder/batches` (+ `$id`) with a branch filter on the read-only ones)
- [x] 7.7 Class sessions table and requests: `manager` and `trainer` config (`SessionActions` no longer calls `useIsManager`; the trainer route already passes `{manager: false, trainer: true}`)
- [x] 7.8 Certificate and completion decisions: merge `CertificateDecisions` and the Founder `InboxList` panels into one inbox component (one `ApprovalsInbox` (`features/shared/approvals/`, panels moved there) with `kinds`; `CertificateDecisions` deleted; Branch Manager section in Completion uses `kinds=[certificate]`; `/admin/approvals` added with Approvals nav badge; `GET /founder/inbox` now also serves a Branch Manager (certificate requests only) and flags `can_decide` so the independence rule shows)
- [x] 7.9 Question bank: move `features/trainer/question-bank.tsx` to `features/shared`; `canApprove` for Branch Manager only (moved to `features/shared/question-bank.tsx`; `canApprove` is a prop, passed only by the Branch Manager's Content & questions)
- [x] 7.10 AI controls: one page, two routes (`features/shared/ai-controls.tsx` (+ `ai-switch-dialogs.tsx`), routes `/admin/ai-controls` and `/founder/ai-controls`, no role logic in the page)
- [x] 7.11 Assistant: `variant` per role (`Assistant` takes `variant`; the student and trainer routes pass it; no role read in the component)
- [x] 7.12 Dashboard building blocks: role-neutral, Founder gets Getting started (`GettingStartedCard` and `useNavCounts` read the session; Founder Home now has the Getting started card (backend `/me/getting-started` already served the Founder))
- [x] 7.13 Reports: one component with a branch filter, three routes (one `Reports` (`features/shared/reports.tsx`) with `area` for the Super Admin and Founder (branch filter, plus a branch-by-branch table from `GET /academic/reports?branch_id=`); routes `/branch/reports`, `/admin/reports`, `/founder/reports`. Backend: `GET /branch/reports` and its export now also admit Super Admin and Founder (all branches or `branch_id`), because the BM report shape is what the one component renders; figure drill links are built per role (never `/branch/*`, none where the role has no screen))
- [x] 7.14 App shell and command palette: one nav per role, record links per role (Founder student result opens a founder page), explicit mobile bar list for every role (Super Admin and Founder nav per 4.7 / 5.7 (Courses added in R6; Curriculum approvals no longer exist); `RECORD_TARGETS` per role (Founder student opens `/founder/students/$id`, batch results open `/admin|founder/batches/$id`, nothing links to `/branch/*` for them); `MOBILE_BAR` is an explicit list for all five roles; new `/founder/approvals`)
- [x] 7.15 Move the cross-feature imports into `features/shared` (list in Part C) and retire the leftover `features/academic/` directory (moved to `features/shared`: url-state, pager, url-params, form-parts (was `admin/shared`), staff-options, question-bank, batches, batch-page, batch-panel, batch-operations, class-operations, class-actions, batch-dialogs, new-class, new-batch-wizard, timetable, attendance-students, waiting-student (split out of `branch/waiting`), reports; `features/academic/dashboard` became `branch/academic-dashboard`; `features/academic/` now holds only `curriculum.tsx` and `curriculum-model.tsx` for R6 to delete; the only remaining cross-feature imports are curriculum ones)
- [x] Frontend: delete the union readers listed in 7.16 (`shared/delivery-ui.tsx`, `auth/auth.tsx:77,85`, `admin/format.ts:20-22`, `shared/support-desk.tsx:444`, `shared/staff-profile.tsx:29-32`, `components/lms/app-shell.tsx:80-82`) (`useCanAdminister` deleted: `canEdit` / `area` (`features/shared/central-area.ts`, `ADMIN_AREA`, `FOUNDER_AREA`, both editable) is passed by the route; `auth/auth.tsx` derives the role and workspace from the session role (no scopes union); `hasRole` is deleted (curriculum, its last user, is gone); support desk `can_respond` comes from the API)

## R6. Curriculum to Courses

Backend and database
- [x] List every foreign key, view and query that touches the curriculum version, draft and approval tables, and the 14 migrations that use `curriculum_version_id` (002, 003, 004, 005, 010, 020, 030, 040, 095, 097, 098, 102, 105, 109) (done: `db/121` header lists what it re-points; all 14 migrations' `curriculum_version_id` columns are dropped)
- [x] Migration: put modules and topics directly on the course; re-point enrolments, batches, sessions, content, assessments, attendance and topic progress to the course; verify row counts (`db/121_course_outlines.sql`: Active, else latest, version's rows re-parented to the course; row counts checked inside the migration; dev: modules 44 to 29, topic_progress 1,721 to 1,726)
- [x] Migration: move hours, completion rules, required assessments, combo track pins and the reusable module library onto the course (hours verification and completion profile on `courses`, `course_assessment_requirements`, `course_components.pinned_course_id`, library kept without approval)
- [x] Migration: drop the curriculum draft, version and approval tables; courses are never dropped (also `curriculum_events`, `curriculum_version_components`, `learning_credits`, type `curriculum_status`)
- [x] Remove equivalence rules, branch variations and the "prepare mapping" helper (code and data) (code and tables gone; the per-track equivalence review note on `course_components` stays)
- [x] Remove `backend/routes/curriculum.py` and `academic_records.py` curriculum routes and `founder.py:27`; add course outline endpoints (Super Admin and Founder edit, everyone else read) (`services/course_outline.py`, `controllers/routes course_outline.py`: `GET /courses`, `GET /courses/{id}/outline`, module, topic, hours, completion profile, requirement, track-pin and library endpoints; Super Admin and Founder edit, everyone with sight of the course reads)
- [x] Keep course code, title, category, status and tracks read-only, owned by the CRM `CourseUpserted` event (the outline endpoints never write them; a CRM `CourseUpserted` leaves the outline alone, tested)
- [x] A course edit applies at once, notifies the Branch Managers of branches with running batches of that course, and is written to the audit log (audit `COURSE_OUTLINE_CHANGED`; notice category Courses, link `/branch/courses/{id}`; the editor is not notified)
- [x] Remove the `curriculum` inbox kind, group and page, `_curriculum_items`, and the nav count key (`backend/services/founder_inbox.py`, `backend/services/nav.py`) (inbox kind, group, `_curriculum_items` and the nav count key removed)

Frontend
- [x] Remove routes `routes/branch.curriculum.tsx`, `routes/founder.curriculum.tsx` and the nav items `auth/access.ts:139,162` and badge `curriculum` (routes and nav items removed; Branch Manager nav has Courses under Teaching, Super Admin Courses under a new "Academic" group, Founder Courses under "Company"; nav count key `curriculum` gone)
- [x] Remove `features/academic/curriculum.tsx`, `curriculum-model.tsx`, `features/branch/curriculum-checklist.tsx`, `curriculum-new-draft.tsx`, `curriculum-pickers.tsx`, `features/founder/curriculum.tsx`, `panel-curriculum.tsx`, and the `panel.tsx:5,10-11` references (all deleted; `features/academic/` removed; `panel.tsx` has no curriculum case)
- [x] Move `curriculum-tree.tsx` to `features/shared` as the course outline editor (now `features/shared/course-outline/tree.tsx` with `topic-details`, `planning` (hours, completion rules, required assessments, module library), `tracks` (combo pins), `library`, `pickers`, `mutation`)
- [x] Remove `api/curriculum.ts`, curriculum calls in `api/delivery.ts` and `api/founder.ts:8-24,76-80` (new client `api/courses.ts`; `api/founder.ts` has no curriculum kind, group, impact or approve calls; `api/delivery.ts` keeps only outline types)
- [x] Reword links and labels: `features/academic/dashboard.tsx:7`, `lib/status.ts:270`, `components/lms/notification-centre.tsx:27`, `lib/i18n.ts` (`noCurriculumYet`), `features/admin/users.tsx:36`, `features/founder/decision-bar.tsx:19` (academic-dashboard link now Courses; status domain `curriculum` became `course` (Active / Inactive / Archived); notification category Courses; `noCurriculumYet` became `noOutlineYet` ("No course outline yet"); the Founder description in `users.tsx` and nothing else needed rewording; decision-bar comment)
- [x] Show the course name instead of "Curriculum version" in `features/academic/batch-panel.tsx:54`, `batch-operations.tsx:843`, `features/trainer/batch-page.tsx:62`, `features/shared/content-detail.tsx:27`, `features/branch/attendance-students.tsx:139,199` ("Curriculum version" rows removed from batch panel and content detail (the Course row is already there); trainer batch page says "Course <title>"; batch operations text reworded; the "Curriculum delivered" figure labels in attendance-students / attendance-parts stay (they name the delivered-classes metric, not a version))
- [x] Topic pickers in `features/trainer/assignments.tsx` and `question-bank.tsx` read the course outline (trainer assignments, question bank, new class and content upload read the outline (`/assessments/curriculum`, `/content-items/options` `outlines[]`, `/courses/{id}/outline`))
- [x] Student pages (`/courses/*`, `/modules/*`, `/topics/*`) still work with the outline coming from the course (types now use the course (`course_id`, `component_id` on module heads); smoke checked My courses and a course page, not every student page)
- [x] Branch Manager `/branch/courses` (read-only), Super Admin `/admin/courses` (edit), Founder `/founder/courses` (edit); Trainer read-only "Course outline" block on the batch page, no route (`/branch/courses` and `/$id`, `/admin/courses` and `/$id`, `/founder/courses` and `/$id` (one `CourseList` / `CoursePage`); Trainer "Course outline" block on the batch page (`features/trainer/course-outline-block.tsx`, collapsed))
- [x] Remove the `PrepareMapping` import from `features/branch/waiting.tsx:14` (import and its use removed)
- [x] CRM "Open in LMS" link `/academic/batches?crm_admission_id=&student=` still works (`routes/academic.$.tsx:11-12`) (`routes/academic.$.tsx` unchanged for `/academic/batches?...&student=`; `/academic/curriculum` now redirects to `/branch/courses`)

## Per-role build

### Student
- [x] No nav change; verify every page still works after R3 and R6 (smoked every student page and legacy redirect on a temp stack (dashboard, courses, schedule, tasks, materials, progress tabs, certificates, career, ask, support, account, notifications): no failed API call after fixing the Home slot-preference card, which asked for slot options on a completed course)
- [x] Show batch trainer, room and timetable on `/courses/$enrolmentId` (Your batch section on the course page: batch, trainers, room, weekly timetable, mode; coming-up classes show their room; `GET /me/enrolments/{id}` returns `timetable`, test in `test_delivery.py`)
- [x] Reword "No curriculum yet" (`features/student/my-courses.tsx:82`) (`noOutlineYet` "No course outline yet" (and `noTopicsYet`, `noModulesYet` reworded))
- [x] Keep all legacy redirect routes as they are (`/assignments`, `/tests`, `/attendance`, `/results`, `/finance`, `/profile`, `/recordings`, `/resources`) (all eight routes exist and redirect (checked))

### Trainer
- [x] Rename the "Content" nav item out of the "Grade" group (it is uploads and review state) (now "My uploads" in Teach)
- [x] Course outline block on the trainer batch page (`features/trainer/batch-page.tsx`) (read-only block, no route)
- [x] Completion recommendation screen (the backend `completion.py:19,33` already allows it) (`/trainer/completion`, nav "Course completion" under People: start a review, recommend Complete / Not yet / Needs recovery with a note)
- [x] Read-only holiday and closure view for planning (`/trainer/calendar` ("Holidays & closures", Teach) with `CALENDAR_READ_ONLY`)
- [x] Trainer support, requests, profile and notifications use the shared components with the trainer config (verified: support uses `SupportDesk` (`simple`), notifications use `NotificationCentre`, profile is the shared `StaffProfile`, requests reads the role-neutral `/me/requests`)

### Branch Manager
- [x] One branch per session: remove "All branches" (verified: no "All branches" choice exists for a Branch Manager (the only remaining "All branches" is the Super Admin / Founder filter))
- [x] Add `/branch/recordings` to the nav (Recordings under Teaching)
- [x] Surface payment instructions, access extensions and certificate requests as visible items, not buried sections (as in R7) (new nav items: Payment instructions (`/branch/payments`, group Branch; read-only for the Branch Manager: the text is set by the Super Admin or Founder in Setup & health, the write endpoint returns 403 for a Branch Manager), Access extensions (`/branch/extensions`, Help), Certificate requests (`/branch/certificate-requests`, Completion), each with its own badge; the old tab and section links redirect)
- [x] `/branch/courses` replaces Curriculum under "Teaching" (nav item "Courses" under Teaching)
- [x] Branch Manager proposes closures; cannot decide them
- [x] Rename the "Attendance & progress" URL to match the label or the label to match the URL (URL is now `/branch/attendance` (label stays "Attendance & progress"); `/branch/progress` redirects)
- [x] Split "Content & questions" or label its two jobs clearly (two nav items: Content review (`/branch/content`) and Question approvals (`/branch/questions`); `?tab=questions` redirects; separate badges `content_review` and `questions`)

### Super Admin
- [x] (built except Courses, which R6 adds) Nav under `/admin`: Home, Approvals, Users & access, Student accounts, Batches, Attendance, Support, Reports, Issues, Academic calendar, Courses, CRM sync, Setup & health, AI controls, Audit log (Courses added; order matches 4.7)
- [x] `/admin/approvals`: the same inbox as the Founder, decides every item
- [x] `/admin/courses`: outline editor and kept blocks (add, rename, reorder, remove modules and topics; topic details; hours; completion rules; required assessments; combo track pins; module library; CRM fields read-only)
- [x] `/admin/batches`, `/admin/students` (branch filter), `/admin/attendance`, `/admin/reports`: read-only cross-branch (read-only cross-branch views; students and attendance have a branch filter, reports have one too)
- [x] `/admin/support`: read and reassign
- [x] "Go fix it" on `/admin/issues` opens a read-only detail with Assign (`backend/services/issues.py:45-64`)
- [x] Payment instructions edited in `/admin/setup`, branches section (Branches section on Setup & health (both `/admin` and `/founder`), any branch; owner decision: the Branch Manager is READ-ONLY on `/branch/payments` ("Set by the Super Admin in Setup & health"); `PUT /branches/{id}/payment-instructions` is Super Admin and Founder only (BM gets 403, tested in `test_branch_u14`; e2e `branch-u14` edits as Super Admin and asserts the BM is read-only))
- [x] Approve closures proposed by Branch Managers on `/admin/calendar`
- [x] Users & access hand-out page (the hand-out section is in the shared Users & access component, served on `/admin/users` and `/founder/users`)
- [x] Remove the implicit Branch workspace and its "Acting as" entry (verified: `WORKSPACE_OF_ROLE` gives one workspace per role, no Acting as in the frontend)

### Founder
- [x] (built except Courses, which R6 adds; "Curriculum approvals" still listed until R6) Nav under `/founder`: Home, Approvals, Courses, Users & access, Students, Batches, Attendance, Issues, Reports, Academic calendar, Support, CRM sync, Setup & health, AI controls, Audit log (Courses added, Curriculum approvals removed; order matches 5.7)
- [x] (all built except `/founder/courses`, R6) `/founder/users` with hand-out page, `/founder/students`, `/founder/batches`, `/founder/attendance`, `/founder/issues`, `/founder/reports`, `/founder/calendar`, `/founder/support`, `/founder/crm-sync` (with Retry), `/founder/setup` (editable), `/founder/audit`, `/founder/courses` (all routes exist)
- [x] Bell, `/founder/notifications`, Getting started card (bell and `/founder/notifications` from part 1; Getting started card on Founder Home)
- [x] Phone "More" sheet carries every item beyond the four pinned (explicit four pinned (Home, Approvals, Students, Issues); the shell's More sheet lists the rest)
- [x] Remove the implicit Admin and Branch workspaces and the "Acting as" entries (verified as above for the Founder)
- [x] Add the Founder's Home empty state and next-step hints (empty text names what appears there; "Where to go next" links; Home icon is no longer the brand shield)

## R7. Make everything visible

- [x] Every role's sidebar and phone bottom bar reviewed: each task reachable in at most two taps (explicit `MOBILE_BAR` for all five roles; every other page is one More tap away (two taps total); hints under labels that could be confused)
- [x] Empty states and "where do I go next" hints on every landing page (Founder, Super Admin and Trainer Today empty texts now point to the next page; Student, Branch Manager already had them)
- [x] Remove dead nav items and unlabeled icons; the Founder Home shield icon differs from the brand logo (`auth/access.ts:161`) (Founder Home uses the House icon; no nav item without a page)
- [x] Getting started card on every role's home (verified on all five homes)
- [x] Student: Progress, Certificates, Support reachable in one tap on a phone, or fees and receipts promoted out of My Account (Quick links on Home: My Progress, Certificates, Support, Fees & receipts)
- [x] Trainer: resolve the overlap of Today, Sessions and Attendance (labels or grouping) (Today (run today), Class schedule (all classes), Attendance (registers), each with a one-line hint)
- [x] Branch Manager: items listed under the Branch Manager checklist above (see the Branch Manager checklist)
- [x] Super Admin: label "Student accounts" and "Users & access" so the difference is clear; move CRM sync out of "Operations" into "System" ("Staff accounts" and "Student accounts" with hints; CRM sync already sits under System)
- [x] Founder: items listed under the Founder checklist above (see the Founder checklist; Founder labels match Super Admin)
- [x] Record Career and placements staff screens as a known gap in `docs/GAPS.md` (out of scope) (added to `docs/GAPS.md`)
- [x] Record the finance summaries screen gap (API exists for Branch Manager, Super Admin and Founder, no screen) in `docs/GAPS.md` (added to `docs/GAPS.md`)

## R8. Tests and docs

- [x] Rewrite `frontend/e2e/shell.spec.ts`: no switcher; one nav per account; cross-role denial; branch picker at sign-in; Founder bell (per role: sidebar equals `access.ts` and has no link into another role's home, no switcher; every role opening each other role's home sees "cannot open this page"; `bm.multi@nipuna.test` gets the picker, header `Branch Manager · Guntur`, Change branch ends the session and the next sign-in offers the picker again; Founder bell opens `/founder/notifications`))
- [x] Add e2e: Founder opens `/founder/reports` with no 403 (`founder-u16.spec.ts`: no 4xx/5xx API response and no access-denied text))
- [x] Add e2e: Branch Manager cannot decide a closure; Super Admin can (`calendar.spec.ts`: the Branch Manager proposes, sees "Waiting for a decision" and no Decide button, the API answers 403; the Super Admin decides it))
- [x] Seed data (`frontend/e2e/helpers.ts:7-17` and staging seed): one account per role for every existing staging user (every existing staging user already holds one role (the seed never created multi-role users), so the change is one new account: `bm.multi@nipuna.test`, a Branch Manager of both branches (`backend/cli/seed.py`, accepted by the db 119 trigger); `USERS.bmMulti` in `helpers.ts`; `DEVELOPMENT.md` documents the accounts))
- [x] Update `docs/UX_PLAN.md` (line 55 decision and U4 notes), `docs/DEVELOPMENT.md` (workspace and acting-as rows, nav-by-role table), `docs/API.md` (role table, nav-counts, `/me/profile`), `docs/DATABASE.md` (new migrations, dropped curriculum tables), `docs/GAPS.md` (UX_PLAN (superseded notes on the decision and U4), DEVELOPMENT (accounts, workspace row, search row, Founder bell row, seed text), API (curriculum rules removed, nav-counts, `/me/profile`, `can_change_branch`), DATABASE (118 to 121 were present; dropped-table notes added to the schema list), GAPS (both gaps verified present)))
- [x] Update `docs/CRM_INTEGRATION.md` if the CRM role assumptions change (the outline section already said no CRM contract change; fixed the `CourseUpserted` row (no curriculum version needed; outline modules, not versions, block removing a track)))

## Final acceptance (walk each role through staging)

- [x] Student: sign in, see only student pages, finish a task from Home (`student-u10`, `student-u11`, `sweep-u18` (every student nav link, light and dark, phone width) and `shell.spec.ts` on a scratch database))
- [x] Trainer: sign in, see only trainer pages, no Branch or Admin links anywhere (`shell.spec.ts` (sidebar has no Branch or Admin link; every other workspace is refused), `trainer-u12/u13`, `sweep-u18`))
- [x] Branch Manager with two branches: picks a branch at sign-in, header shows `Branch Manager · <branch>`, no other branch's data appears, "Change branch" works (`shell.spec.ts` with `bm.multi@nipuna.test`: picker, header, Change branch. "No other branch's data" is covered by the backend tests (`test_session_role.py`), not by e2e))
- [x] Super Admin: no Branch workspace, read-only cross-branch views, Approvals works, closures approved, courses editable, hand-out page works (no Branch workspace, Approvals (`governance`), closures (`calendar`), courses editable (`branch-u15`, `delivery`) and the hand-out page (`handouts`: Accounts to hand out, one-time link, mark handed out) are verified by e2e; the `handouts` spec inserts a split row with psql and needs `E2E_DB_NAME`)
- [x] Founder: everything above plus Founder-only approvals, bell works, reports load (bell, reports and Approvals are verified by e2e (`shell`, `founder-u16`, `governance`); the Founder's hand-out section on `/founder/users` by `handouts`)
- [x] A user who held two roles signs in with each account and sees only that role (the seed has no multi-role user; accounts are one-role by the db 119 trigger and `test_session_role.py` / `shell.spec.ts` show each role sees only its own pages. The db 118 split itself was checked on `nipunalms-dev` in R2))
- [x] No page anywhere changes shape depending on another role (`sweep-u18` walks every nav link of all five roles and `shell.spec.ts` denies cross-role URLs; components take a config per role))
- [x] Curriculum screens are gone; Courses pages exist for all five roles as specified (`shell.spec.ts` (old `/academic/curriculum` lands on Courses), `branch-u15` (Courses read-only for the Branch Manager, Super Admin adds a module), `delivery` (outline built on `/admin/courses`), `founder-u16` (no Curriculum nav link), `sweep-u18`))
- [x] Backend and e2e suites green (backend 932 passed; e2e 195 passed, 0 failed, 13 skipped (mobile-only or data-conditional) on a clean scratch database, one spec file per fresh copy))

---

# Part B. Decisions, current problems, target state

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
| 16 | Founder | **Everything Super Admin can do, plus approvals,** with read-write, across all branches, under `/founder`. Day-to-day branch actions (attendance, running classes) stay with Branch Managers. Gets a notification bell, inbox and Getting started card. (This also lets the Founder edit course outlines; decision 6 reads "Super Admin and Founder".) |
| 17 | "All branches" at sign-in | **No.** One branch per session. Cross-branch views belong to Super Admin and Founder. |
| 18 | Calendar | **Branch Manager proposes closures, Super Admin approves.** Founder and Super Admin add company-wide holidays. |
| 19 | Issues "Go fix it" for Super Admin | **Opens a read-only detail under `/admin`,** with Assign to the right Branch Manager. |
| 20 | Trainer courses | **Read-only outline block on the batch page.** No new nav item. |
| 21 | Career/placements staff screens | **Out of scope.** Recorded in `docs/GAPS.md`. |
| 22 | Credential hand-out | **Hand-out page in Users & access** with a one-time activation link per new account. |
| 23 | Primary role on a split user | **Founder > Super Admin > Branch Manager > Trainer > Student.** |
| 24 | Super Admin Approvals page | **Same inbox as the Founder:** Super Admin and Founder can both see and decide every item (fee exceptions, access extensions, certificates, AI budget, Branch Managers' own requests). The independence rule (nobody decides their own request) still applies. |
| 25 | Course extras kept | **Combo track pins and the reusable module library** survive on the course. Equivalence rules, branch variations and the "prepare mapping" helper are removed. |

## What is wrong today

- One shared shell; the "active role" is only the URL prefix (`auth/access.ts:54-62`).
- The "Acting as" menu only navigates between prefixes (`components/lms/acting-as.tsx`).
- The session carries no role; every request is authorized against the union of all scopes (`backend/routes/decorators.py`, `backend/services/scope.py`).
- Super Admin and Founder get extra workspaces automatically (`backend/services/auth.py:25-31`).
- Shared pages decide what to show from `hasRole(...)`, not from where you are: notification centre, academic calendar, support desk, issues list, batch panel, AI controls, staff profile.

## Target state

- Five roles, five separate experiences: Student, Trainer, Branch Manager, Super Admin, Founder/CEO.
- One login = one role. The session stores that role. Header shows `Role · Branch` as a plain label, no dropdown.
- A Branch Manager with several branches picks the branch at sign-in. Changing branch means "Change branch", which ends the session and returns to the picker.
- Every nav item lives under exactly one role's prefix. A role never sees another role's screens, and never sees a screen that behaves differently because of a second role.

## Risks and build rules

- Existing people holding several roles lose single sign-on across them. They need clear sign-in guidance and migrated accounts.
- The backend change touches most of the role guards; it needs the full backend test suite and a staging pass before frontend work depends on it.
- The `@fresh_auth` (recent password) guard stays on the same sensitive actions as today, for Founder and Super Admin alike.
- Course code, title, category, status and tracks stay owned by the CRM `CourseUpserted` event, for every role (decision 12).

---

# Part C. Per-role screen specs

### How the app decides who sees what today

| Piece | Where | Behaviour today |
|---|---|---|
| Workspace from the URL | `auth/access.ts:54-61` | `/trainer`, `/branch`, `/admin`, `/founder` prefixes; every other path (no prefix) is "student". `/account/*`, `/change-password`, `/login`, `/activate`, `/forgot-password`, `/verify/*` have no workspace. |
| Who may open a workspace | `auth/access.ts:68-70`, `routes/__root.tsx:49`, `backend/services/auth.py:25-31` | `workspaces` from the API: Founder = founder + admin + branch; Super Admin = admin + branch; Branch Manager = branch; Trainer = trainer; Student = student. |
| Landing | `backend/services/auth.py:33-39,188-192`, `routes/__root.tsx:47` | First workspace in the order founder > admin > branch > trainer > student. |
| "Acting as" switcher | `components/lms/app-shell.tsx:115-121`, `components/lms/acting-as.tsx:19-64` | Shown when the person has more than one workspace, or more than one branch. Otherwise a static `Role · Branch` label. |
| Branch pick | `auth/acting.ts:6-14`, `lib/acting-branch.ts` | Only in the `branch` workspace and only with more than one branch. `branchId = null` means "all branches". **Admin and Founder pages never get a branch filter today.** |
| "Can this person change things" | `features/shared/delivery-ui.tsx:16-18` (`useCanManage`), `:59-61` (`useIsManager`), `features/admin/format.ts:20-22` (`useCanAdminister`) | Read from the union of all the person's roles. |
| Bell | `components/lms/app-shell.tsx:26-31` | Student, trainer, branch, admin have a notification centre. **Founder has none** ("nothing is sent to the founder"). |
| Phone bottom bar | `auth/access.ts:177-187` | Student, trainer, branch pin four items. Admin and Founder use their first four (Founder has only four, so its "More" sheet is empty). |
| Search palette | `components/lms/command-palette.tsx:15-20,46-52` | Pages of every workspace the person holds; record links depend on the active workspace. |

After the plan one account holds one role. A user who holds several roles today keeps the highest role on the existing account, in the order Founder > Super Admin > Branch Manager > Trainer > Student, and every other role moves to a new account (decisions 1, 8 and 23).

---

## 1. Student

### 1.1 Nav (`auth/access.ts:100-114`)

Workspace `student`, home `/dashboard`. Flat list, labels translated (EN / తెలుగు, `translated` at `components/lms/app-shell.tsx:74`). Header: language toggle, search, bell (`/notifications`), avatar menu (My Account, Change password, Sign out; `app-shell.tsx:146-158`).

| Sidebar item | Route | Badge |
|---|---|---|
| Home | `/dashboard` | |
| My Learning | `/my-courses` | |
| Schedule | `/schedule` | |
| Tasks & Tests | `/tasks` | `tasks` |
| Class Materials | `/materials` | |
| My Progress | `/progress` | |
| Certificates | `/certificates` | |
| Career | `/career` | |
| Ask Nipuna | `/ask-nipuna` | |
| Support | `/support` | `support` |

Phone bottom bar (`access.ts:178`): Home, My Learning, Schedule, Tasks & Tests, **More** (Class Materials, My Progress, Certificates, Career, Ask Nipuna, Support, and `My Account` from `STUDENT_ACCOUNT`, `access.ts:114`, `app-shell.tsx:245`).

### 1.2 Screens

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/dashboard` | `features/student/dashboard.tsx:314` | The one thing to do now, Getting started, next payment, material-change answers | Y | none | none. `GettingStartedCard workspace="student"` (`components/lms/getting-started.tsx:28`) |
| `/my-courses` | `features/student/my-courses.tsx:57` | One card per enrolment with a Continue button | Y | none | none |
| `/courses/$enrolmentId` | `features/student/course-detail.tsx:36` | One course: status, tracks, modules, batch | N (from My Learning) | none | none |
| `/courses/$enrolmentId/tracks/$trackId` | `features/student/track-detail.tsx:9` | One track of a combo | N | none | none |
| `/modules/$moduleId` | `features/student/module-detail.tsx:9` | Topics of a module | N | none | none |
| `/topics/$topicId` | `features/student/topic-detail.tsx:25` | One topic: recordings, files, work | N | none | none |
| `/schedule` | `features/student/schedule.tsx:138` | Live / upcoming classes with Join | Y | none | none |
| `/sessions/$sessionId` | `features/student/session-detail.tsx:11` | One class | N | none | none |
| `/tasks` | `features/student/tasks.tsx:123` | Assignments and tests on one list | Y | none | none |
| `/assignments/$id` | `features/student/assignment-detail.tsx:137` | Brief, submit, feedback | N | none | none |
| `/tests/$id` | `features/student/test-detail.tsx:430` | Take a test, book an interview | N | none | none |
| `/materials` | `features/student/materials.tsx:293` | Recordings and files by course and topic; access-extension request (`access-window.tsx:25`) | Y | none | none |
| `/progress` (`?tab=`) | `features/student/progress.tsx:235` (+ `attendance.tsx:190`, `results.tsx:32`) | Overview, Attendance (with recovery and correction requests), Results | Y | none (uses `shared/attendance-parts.tsx` pieces) | none |
| `/certificates` | `features/student/certificates.tsx:136` | Certificate tracker per course, PDF | Y | none | none |
| `/career` | `features/student/career.tsx:54` | Opt in, profile, CV, jobs, applications | Y | none | none |
| `/ask-nipuna` | `features/student/ask-nipuna.tsx:3` | Chat assistant | Y | Trainer | `Assistant variant="student"` (`features/shared/assistant.tsx:46,48,190,325,410`) |
| `/support` | `features/student/support.tsx:41` | Requests, guided form to raise one | Y | none (`shared/support-attachments.tsx`) | none |
| `/support/$requestId` | `features/student/support-request.tsx:21` | One request: thread, reply | N | none | none |
| `/my-account` (`?tab=fees`) | `features/student/account.tsx:25` | Profile, language, email change, devices, Fees & Receipts | N (avatar menu, phone More) | none | `NotificationPreferences translated` shared with staff profile |
| `/notifications` | `features/student/notifications.tsx:4` -> `features/shared/notification-centre.tsx:89` | Inbox | N (bell) | Trainer, Branch, Super Admin | `hasRole("SUPER_ADMIN")` for the "System issues" tab (`notification-centre.tsx:90-91`) |
| `/change-password` | `routes/change-password.tsx` | Change password | N (avatar menu) | all | none |
| `/verify/$number` | `routes/verify.$number.tsx` | Public certificate check | N | public | none |

### 1.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/courses/*`, `/modules/*`, `/topics/*`, `/sessions/*`, `/assignments/$id`, `/tests/$id`, `/support/$requestId`, `/notifications`, `/my-account` | Detail pages and inbox; reached by links, bell or avatar menu. Fine, but `/my-account` (Fees & Receipts, profile) is only in the avatar menu and the phone "More" sheet. |
| Legacy redirects (no screen) | `/assignments`, `/tests`, `/attendance`, `/results`, `/finance`, `/profile`, `/recordings`, `/resources` (`routes/*.tsx`). Keep or drop in R7. |
| "Class Materials" vs "My Learning" | Both list recordings and files per topic; `materials.tsx:1` groups them by course/topic again. Purpose overlap, not unclear to the user. |
| Phone bar | 4 of 10 items pinned; Progress, Certificates, Support are two taps (More, then item). |

### 1.4 Screens reached only through another role's workspace

None. A Student holds only the student workspace.

### 1.5 Curriculum-related screens

| Where | What | After R6 |
|---|---|---|
| `/courses/*`, `/modules/*`, `/topics/*`, `features/student/my-courses.tsx:82` ("No curriculum yet") | The modules and topics a student sees come from the batch's curriculum version | Must keep working. The outline comes from the course (decision 11). Rename "No curriculum yet" wording (`lib/i18n.ts` key `noCurriculumYet`). |
| Courses page for the Student | `My Learning` (`/my-courses`) already is the student's course list | No new page. Course detail stays read-only. |

### 1.6 Gaps

| Gap | Evidence |
|---|---|
| Preferred-slot request exists only on Home and only while a course has no batch | `features/student/batch-changes.tsx:1` |
| Material-change answers are handled on Home only | `features/student/dashboard.tsx:143` |
| Fees and receipts are inside My Account, two taps on a phone | `access.ts:114`, `routes/finance.tsx` |
| Batch trainer, room and timetable are not reachable from nav outside a class page; R7 shows them on `/courses/$enrolmentId` | `/my-courses`, `/courses/$enrolmentId` |

---

## 2. Trainer

### 2.1 Nav (`auth/access.ts:116-130`)

Workspace `trainer`, home `/trainer`. Bell: `/trainer/notifications`. Avatar menu: Profile (`/account/profile`), Change password, Sign out.

| Group | Item | Route | Badge |
|---|---|---|---|
| Teach | Today | `/trainer` | `class_logs` |
| Teach | Sessions | `/trainer/sessions` | |
| Teach | Attendance | `/trainer/attendance` | `attendance` |
| Teach | My requests | `/trainer/requests` | |
| Grade | To grade | `/trainer/to-grade` | `to_grade` |
| Grade | Assignments | `/trainer/assignments` | |
| Grade | Assessments | `/trainer/assessments` | |
| Grade | Content | `/trainer/content` | |
| People | Batches | `/trainer/batches` | |
| People | Students | `/trainer/students` | |
| People | Support | `/trainer/support` | `support` |
| Insights | Reports | `/trainer/reports` | |
| Insights | Ask Nipuna | `/trainer/ask-nipuna` | |

Phone bottom bar (`access.ts:179`): Today, Sessions, To grade, Students, **More** (the other nine).

### 2.2 Screens

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/trainer` (`?session=`) | `features/trainer/today.tsx:221` (+ `class-flow.tsx:427`) | Today's classes; guided Start, Join, Attendance, Class log | Y | none | Getting started (`workspace="trainer"`) |
| `/trainer/sessions` | `features/trainer/sessions.tsx:13` | Schedule list and reschedule requests | Y | `shared/sessions.tsx` | Passes `manager:false, trainer:true` (`sessions.tsx:29`) and `manager={false}` (`:40`) to `SessionsTable` / `RequestsPanel`; inside, `useIsManager()` (`shared/sessions.tsx:26,107,182`) |
| `/trainer/attendance` | `features/trainer/attendance.tsx:313` | Mark attendance; unmarked and corrections | Y | `RegisterForm` shared with Today's flow | none |
| `/trainer/requests` | `features/trainer/requests.tsx:61` | Moves, corrections, recoveries I asked for, and what the Branch Manager decided | Y | none | API is `GET /me/requests` for any staff role (`backend/routes/my_requests.py`); text depends on `has_role("BRANCH_MANAGER")` (`backend/services/my_requests.py:88`) |
| `/trainer/to-grade` | `features/trainer/to-grade.tsx:39` | Grading queue | Y | none | none |
| `/trainer/to-grade/$kind/$id` | `features/trainer/grade-screen.tsx:88` | One hand-in or attempt, Save and next | N | none | none |
| `/trainer/assignments` | `features/trainer/assignments.tsx:200` | Write, release, withdraw assignments; topic picker from the curriculum (`:30-31,89,124`) | Y | none | none |
| `/trainer/assessments` (`?tab=`) | `features/trainer/assessments.tsx:22` | Question bank, tests, mock interviews | Y | `QuestionBank` with Branch | `QuestionBank canApprove` default false (`question-bank.tsx:242,256,282-297`) |
| `/trainer/content` | `features/trainer/content.tsx:27` | My content items and their review state | Y | `shared/content-detail.tsx:10` (also Branch) | none; detail shows "Curriculum version" (`content-detail.tsx:27`) |
| `/trainer/batches` | `features/trainer/batches.tsx:11` | Batches I teach | Y | none | none |
| `/trainer/batches/$id` | `features/trainer/batch-page.tsx:29` | One batch: classes, students, content, progress | N | none (Branch has its own, `features/branch/batch-page.tsx`) | shows curriculum version label (`:62`) |
| `/trainer/students` | `features/trainer/students.tsx:14` | Students in my batches, flag a problem | Y | none | none |
| `/trainer/students/$id` | `features/trainer/student-page.tsx:114` | One student: attendance, work, results | N | none | none |
| `/trainer/support` | `features/trainer/support.tsx:12` | Raise and follow requests about my students | Y | `SupportDesk` with Branch | `simple` flag (`trainer/support.tsx:21-22`, `support-desk.tsx:100`); reassign control shown by `profile.scopes.some(BM/SA/FOUNDER)` (`support-desk.tsx:444`) |
| `/trainer/reports` | `features/trainer/reports.tsx:65` | Students needing me, batch figures | Y | none | none |
| `/trainer/ask-nipuna` | `features/trainer/ask-nipuna.tsx:3` | Chat assistant | Y | Student | `Assistant variant="trainer"` (`shared/assistant.tsx:410`) |
| `/trainer/notifications` | `features/trainer/notifications.tsx:3` | Inbox | N (bell) | Student, Branch, Super Admin | `hasRole("SUPER_ADMIN")` (`notification-centre.tsx:90`) |
| `/account/profile` | `features/shared/staff-profile.tsx:12` | Identity, notification channels, devices, password | N (avatar menu) | Branch, Super Admin, Founder | role and branch printed from `profile.scopes` union (`staff-profile.tsx:29-32`) |

### 2.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/trainer/to-grade/$kind/$id`, `/trainer/batches/$id`, `/trainer/students/$id`, `/trainer/notifications` | Detail pages and inbox, opened by links or bell. |
| `/trainer/reviews` | Redirect to To grade (`routes/trainer.reviews.tsx`). |
| `Content` sits under group "Grade" | It is the trainer's uploads and their review state, not grading. |
| `Assignments` vs `Assessments` | Two Grade items with near-identical names; assessments hold questions, tests and interviews. |
| `My requests` under "Teach" | It is a status list of asks to the Branch Manager. |
| `Today` / `Sessions` / `Attendance` | Three ways into a class; the UX plan already notes this overlap (`docs/UX_PLAN.md`). |

### 2.4 Screens reached only through another role's workspace

None today. Hand-offs to other roles (no screen of the trainer's own): question approval is on the Branch Manager's `/branch/content` (`features/branch/content.tsx:216`), reschedule and correction decisions are on `/branch/schedule` and `/branch/progress`.

### 2.5 Curriculum-related screens

| Where | What | After R6 |
|---|---|---|
| `trainer/assignments.tsx:30-31,89,124`, `trainer/question-bank.tsx:132-133` | Topic picker fed by `GET /assessments/curriculum` | Same picker fed by the course's outline |
| `trainer/batch-page.tsx:62`, `shared/content-detail.tsx:27` | "Curriculum <version>" / "No approved curriculum yet" | Show the course name |
| Courses page for the Trainer | None today | A read-only "Course outline" block on the trainer batch page; no nav item (decision 20) |

### 2.6 Gaps

| Gap | Evidence |
|---|---|
| Backend lets a Trainer recommend a course completion, no trainer screen exists | `backend/routes/completion.py:19,33`; `features/trainer/*` has no completion UI |
| No holiday / closure view for trainers when planning | `features/trainer/*` has no calendar; the calendar lives on `/branch/schedule` and `/admin/calendar` |
| No course outline outside the class flow and topic pickers | `features/trainer/batch-page.tsx` shows only a version label |
| Student flags (`FlagStudentDialog`) reachable only from Students rows, Support button, student page | `trainer/support.tsx:8-11` |

---

## 3. Branch Manager

### 3.1 Nav (`auth/access.ts:132-146`)

Workspace `branch`, home `/branch`. Bell: `/branch/notifications`. Branch picker (header "Acting as" menu, and `BranchPicker` repeated in page heads, `features/branch/my-work.tsx:37-51`) when the account has more than one branch.

| Group | Item | Route | Badge |
|---|---|---|---|
| Today | My work | `/branch` | `my_work` |
| Today | Class day | `/branch/class-day` | `class_day` |
| Batches & students | Batches | `/branch/batches` | |
| Batches & students | Waiting for a batch | `/branch/waiting` | `waiting` |
| Batches & students | Schedule & calendar | `/branch/schedule` | `schedule` |
| Batches & students | Attendance & progress | `/branch/progress` | `attendance` |
| Teaching | **Curriculum** | `/branch/curriculum` | |
| Teaching | Content & questions | `/branch/content` | `content_review` |
| Teaching | Marks & results | `/branch/results` | `marks` |
| Completion | Completion & certificates | `/branch/completion` | `completion` |
| Help | Student support | `/branch/support` | `support` |
| Help | Issues | `/branch/issues` | `issues` |
| Reports | Reports | `/branch/reports` | |

Phone bottom bar (`access.ts:180`): My work, Class day, Batches, Schedule & calendar, **More** (the other nine).

### 3.2 Screens

"Role-dependent logic" lists what changes with the person's roles today. `manage` = `useCanManage()` (Branch Manager or Super Admin; `shared/delivery-ui.tsx:16-18`), `approver` = `useIsManager()` (same two roles; `:59-61`). For a Branch Manager both are always true; they exist because the same screens are opened by Super Admin (true) and Founder (false).

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/branch` | `features/branch/dashboard.tsx:18` | My work list, Getting started, branch tiles, academic tiles, payment instructions | Y | Super Admin, Founder (read) | `PaymentInstructions` (`dashboard.tsx:71`) hidden unless `manage` (`payment-instructions.tsx:15,31`); embeds `AcademicDashboard` (`features/academic/dashboard.tsx:16`) whose quick links include `/branch/curriculum` (`:7`); `useActing("branch")` (`dashboard.tsx:19`) |
| `/branch/class-day` | `features/branch/class-day.tsx:66` | Today's classes: Meet link, hosts, disruptions | Y | SA, Founder (read) | `manage` (`:67`) gates Meet-link edit (`:46,145`) and Resolve (`:223`); `ClassOperationsDialog` (`features/academic/class-operations.tsx`): `useCanManage` `:35,183,276`, `useIsManager` `:277`, `hasRole("BRANCH_MANAGER","SUPER_ADMIN")` `:278` (verifier) and `:380-381` (allowed) |
| `/branch/batches` (`?new=1&course=`) | `features/branch/batches.tsx:34` | Batch list, New batch wizard | Y | SA, Founder (read) | `manage` (`:35`) gates wizard (`:55,75`); wizard reads `profile.allowed_branches` and `useActing` (`new-batch-wizard.tsx:76,78`) |
| `/branch/batches/$id` | `features/branch/batch-page.tsx:192` | One batch: step bar, overview, students, classes, trainers, checks, requests, history | N | SA, Founder (read) | `manage` (`:99,160,198`) passed as `manager` to `Overview/StudentsTab/TrainersTab/ReadinessTab` (`:170-174`, defined `features/academic/batch-panel.tsx:32,89,149,226`); `LifecycleActions` uses `useCanManage`/`useIsManager` (`features/academic/batch-operations.tsx:41-42`; buttons `:60,64,96,106,126`); `RequestsTab` (`:947-962`) passes `manager` and `approver` into capacity, transfer, material-change and succession panels (`:376,494,612,816`); confirm warning override only for approver (`batch-dialogs.tsx:154,180`) |
| `/branch/waiting` (`?q=`) | `features/branch/waiting.tsx:147` | Students with no batch, one-click Allocate | Y | SA, Founder (read) | `manage` (`:148`) gates "Open Batches" (`:187`) and Allocate (`:94,118,128`); `useActing` (`:149`) decides `withBranch` column; imports `PrepareMapping` from `academic/curriculum-model` (`:14`) |
| `/branch/schedule` | `features/branch/schedule.tsx:290` | Week / list of classes, New class, reschedule requests, **embedded academic calendar** (`:488`) | Y | SA, Founder (read) | `manager = useCanManage()` (`:291`); `RequestRow` uses `useIsManager` and the API's `can_decide` (`:44-46`), shows "Decided by the Founder or a Super Admin" (`:65`); `NewClassDialog` approver (`features/branch/new-class.tsx:46,201`); `ClassActions` `manager/approver` (`features/branch/class-actions.tsx:23-26,73-74,193,218`); `AcademicCalendar` `hasRole` x3 (`features/shared/academic-calendar.tsx:40-43`) |
| `/branch/progress` | `features/branch/attendance.tsx:14` | Students (at risk first), recovery requests, corrections | Y | SA, Founder (read) | `useActing` (`:15`); no role checks; shows "Curriculum delivered" (`attendance-students.tsx:139,199`) |
| `/branch/curriculum` | `features/academic/curriculum.tsx:310` | Draft, submit and review curriculum versions | Y | Founder + SA also use `/founder/curriculum` | `author = hasRole(BM, SA)` (`:30`), `approver = hasRole(FOUNDER, SA)` (`:31`; buttons `:136,154,164`); `curriculum-model.tsx:473-476` (`central`, `reviewer`) |
| `/branch/content` | `features/branch/content.tsx:178` | Content waiting for review; questions waiting for approval | Y | Trainer (content detail, question bank) | `QuestionBank canApprove` (`:216`) imports a trainer component (`:11`); `ContentReviewDialog` (`content-review.tsx:293`) |
| `/branch/results` | `features/branch/results.tsx:110` | Review, moderate and publish marks | Y | SA | none inside (`results-review.tsx`); API needs BM/SA (`backend/routes/results.py`, `MODERATOR_ROLES`) |
| `/branch/completion` (`?stage=`) | `features/branch/completion.tsx:183` | Completion pipeline: decide, approve, issue certificate; folded "Requests and fee releases" (`:161-180`) | Y | SA; Founder decides the same requests on `/founder/certificates` | `CertificateDecisions` (`shared/certificate-register.tsx:183`) shows what "the signed-in approver" may decide (`:182,235`) |
| `/branch/support` (`?tab=`) | `features/branch/support.tsx:16` | Student support desk + Access extensions tab | Y | Trainer (`SupportDesk`) | `SupportDesk views` (`:55-56`); `ExtensionsTab` (`extensions-requests.tsx:235`: within the Branch Manager's limit they decide, beyond it they recommend and the Founder decides, `:1`) |
| `/branch/issues` | `features/branch/issues.tsx:284` | One inbox for what is wrong or stuck | Y | Super Admin (`IssuesList`) | `IssuesList` props `canNote`, `canAssign`, `branchScoped` (`:175`); `Go fix it` target comes from `backend/services/issues.py:41-64` |
| `/branch/reports` | `features/branch/reports.tsx:57` | Figures, trends, CSV export | Y | SA | `useActing` (`:58`); API `GET /branch/reports` is BM/SA only (`backend/routes/reports.py:24,31`): **a Founder opening this page gets 403** |
| `/branch/recordings` | `features/branch/recordings.tsx:203` | Release a class recording or report a problem | **N** | SA | `useActing` (`:148,204`); API needs BM/SA (`backend/routes/recordings.py:10`) |
| `/branch/notifications` | `routes/branch.notifications.tsx` -> `shared/notification-centre.tsx:89` | Inbox | N (bell) | Student, Trainer, SA | System-issues tab by `hasRole("SUPER_ADMIN")` |
| `/account/profile` | `features/shared/staff-profile.tsx:12` | Profile | N | Trainer, SA, Founder | union of scopes (`:29-32`) |

### 3.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/branch/recordings` | **Not in the sidebar.** Linked from Class day (`class-day.tsx:83`), the academic quick links (`academic/dashboard.tsx:10,43`), Issues and notifications. |
| Payment instructions (how students pay) | Only a block at the bottom of the home page (`dashboard.tsx:71`). |
| Access extensions | A tab inside Student support, not a nav item (`support.tsx:13-14`). |
| Certificate corrections / fee releases | A collapsed section inside Completion & certificates (`completion.tsx:161`). |
| Academic calendar | Embedded at the bottom of Schedule & calendar (`schedule.tsx:488`). |
| Redirect-only routes | `/academic`, `/academic/*`, `/branch/operations`, `/branch/meet-operations`, `/branch/academic-reports`, `/branch/assessments`, `/branch/certificates`, `/branch/content-review`, `/branch/exceptions`, `/branch/recording-exceptions`, `/branch/requests` (`routes/*.tsx`). `/academic/batches?crm_admission_id=&student=` is the CRM "Open in LMS" link and must keep working (`routes/academic.$.tsx:11-12`). |
| Unclear nav items | `Attendance & progress` URL is `/branch/progress`. `Student support` and `Issues` overlap for student requests (an extension or request appears in both; `backend/services/issues.py:51,55`). `Content & questions` mixes two jobs (content review, question approval). |

### 3.4 Screens reached only through another role's workspace

None for a pure Branch Manager. (Super Admin and Founder section below.)

### 3.5 Curriculum-related screens to replace

| Where | What | Replace with |
|---|---|---|
| Nav `Curriculum` (`access.ts:139`), route `routes/branch.curriculum.tsx` | Draft/submit/review versions | **Courses**, read-only (see 3.5.1) |
| `features/academic/curriculum.tsx` (396 lines), `curriculum-model.tsx` (733), `branch/curriculum-checklist.tsx`, `curriculum-new-draft.tsx`, `curriculum-pickers.tsx`, `curriculum-tree.tsx` | Version editor, checklist, tree, library, variations, equivalence, combo pins | Removed, except the module/topic tree (`curriculum-tree.tsx`, reused by the Super Admin and Founder course editor), the reusable module library and combo track pins, which move onto the course (decision 25) |
| `academic/dashboard.tsx:7` quick link "Curriculum versions" | | Link to Courses |
| `branch/waiting.tsx:14` imports `PrepareMapping` from `curriculum-model.tsx` | Student mapping helper in the waiting list | Removed with equivalence rules, branch variations and the "prepare mapping" helper (decision 25); the import goes |
| `batch-panel.tsx:54`, `batch-operations.tsx:843` | "Curriculum version" row, "same curriculum version" text | Show the course |
| `lib/status.ts:270` (`curriculum` status domain), `notification-centre.tsx:27` (category "Curriculum") | | Remove |

#### 3.5.1 Courses page for the Branch Manager

`/branch/courses`, nav group "Teaching" (replaces Curriculum). Read-only. List of courses offered (code, title, category, combo tracks, status as sent by the CRM) with "batches running at my branch" and "students waiting". A course page shows its outline (modules, topics) and a "New batch for this course" button that opens `/branch/batches?new=1&course=<id>` (the wizard already accepts it, `routes/branch.batches.index.tsx`).

### 3.6 Gaps

| Gap | Evidence |
|---|---|
| Career and placements: no staff screen; out of scope, recorded in `docs/GAPS.md` (decision 21). Opportunities, CV review, career profiles, applications and placement outcomes exist in the API and the student's "CV reviewed" step depends on it | `backend/routes/career.py:56-178`; frontend only `api/career.ts` student calls and `features/student/career.tsx` |
| Finance view: the API serves finance summaries to BM, SA and Founder, no screen | `backend/routes/finance.py:37,44`; no frontend caller |
| `Recordings` not in nav | 3.3 |
| Payment instructions buried on the home page | `dashboard.tsx:71` |
| Branch pick repeated as page-head dropdown and header menu; "All branches" option exists | `my-work.tsx:37-51`, `acting-as.tsx:50-61` (plan decisions 4 and 17 remove this: one branch per session, no "All branches") |
| No view of trainers (availability, load) when assigning | `batch-panel.tsx:149` shows only the batch's own trainers |

#### 3.7 End state for the Branch Manager

A Branch Manager works in one branch per session, chosen at sign-in and shown in the header as `Role · Branch`; there is no "All branches" choice and no page-head branch dropdown (decisions 4 and 17). Courses is read-only (3.5.1). The Branch Manager proposes branch closures on the calendar and the Super Admin approves them (decision 18). Career and placements staff screens are out of scope and recorded in `docs/GAPS.md` (decision 21).

---

## 4. Super Admin

### 4.1 Nav (`auth/access.ts:148-158`)

Workspace `admin`, home `/admin`. Bell: `/admin/notifications`. Because the role also opens `branch`, the header shows "Acting as" with Super Admin and Branch Manager (`backend/services/auth.py:25-31`), and the branch picker on `/branch/*`.

| Group | Item | Route | Badge |
|---|---|---|---|
| (none) | Home | `/admin` | `home` (sum of all) |
| People | Users & access | `/admin/users` | `users` |
| People | Student accounts | `/admin/students` | `student_accounts` |
| Operations | Issues | `/admin/issues` | `issues` |
| Operations | Academic calendar | `/admin/calendar` | `calendar` |
| Operations | CRM sync | `/admin/crm-sync` | `crm_sync` |
| System | Setup & health | `/admin/setup` | `setup` |
| System | AI controls | `/admin/ai-controls` | |
| System | Audit log | `/admin/audit` | |

Phone bottom bar: no list, so the first four: Home, Users & access, Student accounts, Issues, **More** (the other five). Check: `access.ts:177-187`.

### 4.2 Screens (own workspace, `/admin/*`)

`edit` = `useCanAdminister()` = `hasRole("SUPER_ADMIN")` (`features/admin/format.ts:20-22`). The Founder opens these screens too, with `edit` false (read-only).

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/admin` | `features/admin/dashboard.tsx:81` | Needs-you list, setup checklist, quick links | Y | Founder (read) | `canEdit` (`:83`) hides Retry (`toItems`, `:26,93`) and quick links (`:100`); Getting started `workspace="admin"` |
| `/admin/users` (`?add=1`) | `features/admin/users.tsx:70` | Staff accounts, create, role scopes, invite, reset, unlock, deactivate | Y | Founder (read) | `canEdit` (`:71,78,106,172,200`). **Add role** per person (`:210,282,362-400`, `adminApi.grantScope`) is the form the plan removes (R2). Role list `:17-40` includes the Founder description "Decides curriculum, certificate exceptions and access extensions" (`:36`) |
| `/admin/students` | `features/admin/students.tsx:17` | Student accounts and next step | Y | Founder (read) | none (actions in `student-actions.tsx:15,35`) |
| `/admin/students/$id` | `features/admin/student-page.tsx:19` | One student's account, activation link, history | N | Founder (read) | `canEdit` (`:22,130`) |
| `/admin/issues` | `features/admin/issues.tsx:7` -> `features/branch/issues.tsx:175` | Everything stuck in every branch, Assign | Y | Branch Manager (same list) | `canAssign = useCanAdminister()` (`:8`), `branchScoped={false}` (`:15`); **Go fix it opens `/branch/*` screens** (`backend/services/issues.py:45-64`) |
| `/admin/calendar` (`?add=1`) | `features/admin/calendar.tsx:201` | Month / list of holidays and closures, add, edit, cancel, decide | Y | Founder (partial). A second copy of the same data is embedded for the Branch Manager (`shared/academic-calendar.tsx:39`) | `central = hasRole(FOUNDER, SA)` (`:207`), `canEdit = hasRole(SA)` (`:208`); add kinds: Company Holiday if central, Branch Closure if canEdit (`:209`); `canDecide={canEdit}` (`:284,312`) |
| `/admin/crm-sync` | `features/admin/crm-sync.tsx:45` | What the CRM sent, failures, Retry, outbox | Y | Founder (read) | `canEdit` (`:124,157,264`) gates Retry (`:146,233,286`) |
| `/admin/setup` | `features/admin/setup.tsx:40` | Connections and security settings checklist, owners | Y | Founder (read) | `canEdit` (`:42`) gates edit (`:31,95`); embeds Meet health (`meet-health.tsx:17`) |
| `/admin/ai-controls` | `features/admin/ai-controls.tsx:168` | Ask Nipuna on/off for students, staff, all, one branch | Y | Founder (same component also at `/founder/ai-controls`) | none in the component; the API sends `can_switch` (`:178`), both roles may switch (`backend/routes/ai_controls.py:23,31`) |
| `/admin/audit` | `features/admin/audit.tsx:86` | Who did what | Y | Founder (read) | none |
| `/admin/notifications` | `routes/admin.notifications.tsx` -> `shared/notification-centre.tsx:89` | Inbox incl. "System issues" tab | N (bell) | Student, Trainer, Branch | `hasRole("SUPER_ADMIN")` (`notification-centre.tsx:90-91`) |
| `/account/profile` | `features/shared/staff-profile.tsx:12` | Profile | N | Trainer, Branch, Founder | union of scopes (`:29-32`) |

### 4.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/admin/students/$id`, `/admin/notifications` | Detail page and inbox. |
| `/admin/exceptions`, `/admin/integrations`, `/admin/security` | Redirects to Issues / Setup & health (`routes/admin.*.tsx`). |
| `Home` badge | Shows the sum of every other badge (`backend/services/nav.py` `_admin_counts`: `"home": sum(...)`). |
| `Student accounts` vs `Users & access` | Two people lists; one is CRM-created students, one is staff. Clear in the page text, not in the labels. |
| `CRM sync` under "Operations" | It is a system integration screen. |

### 4.4 Screens the Super Admin reaches only through the Branch Manager workspace

Today the Super Admin holds the `branch` workspace, so all of 3.2 is open with `manage` and `approver` true. Under decisions 15 and 24 the Super Admin gets read-only cross-branch views plus an Approvals page under `/admin/*`; branch actions stay with Branch Managers. Rows below give what the Super Admin does there today and its home under `/admin/*` (shared component, config in section 7).

| Branch screen used today | What the Super Admin does there | Home under Super Admin |
|---|---|---|
| `/branch` My work | Sees the picked branch's list | None: `/admin` Home already has a needs-you list. |
| `/branch/issues` ("Go fix it" targets) | Issues in `/admin/issues` send the Super Admin to `/branch/waiting`, `/branch/recordings`, `/branch/support`, `/branch/results`, `/branch/class-day`, `/branch/schedule` (`backend/services/issues.py:45-59`) | Assign stays in `/admin/issues`; "Go fix it" opens a read-only detail under `/admin/*` with Assign (decision 19) |
| `/branch/batches`, `/branch/batches/$id` | Full batch management, any branch | `/admin/batches` read-only, with branch filter |
| `/branch/waiting` | Allocate | none (Branch Manager job) |
| `/branch/schedule` + calendar | Approve reschedules, add classes | none; the calendar stays `/admin/calendar`, where the Super Admin approves closures proposed by Branch Managers (decision 18) |
| `/branch/class-day`, `/branch/recordings` | Fix Meet links, release recordings | none |
| `/branch/progress` | Attendance, recovery requests, corrections | `/admin/attendance` read-only, with branch filter; `/admin/students` gets the same branch filter |
| `/branch/results`, `/branch/content` | Review, moderate, publish, approve content and questions | none |
| `/branch/completion` | Decide completions, issue certificates, decide certificate requests and fee releases | decisions only, on the Approvals page (the same inbox as the Founder, section 7.8) |
| `/branch/support` | Reply to students, decide access extensions | `/admin/support` read + reassign; extension decisions in Approvals |
| `/branch/reports` | Reports for any branch | `/admin/reports` with a branch filter (same component) |
| `/branch/curriculum` | Draft, approve, activate versions | `/admin/courses` (Courses, edit) |
| `/branch` PaymentInstructions | Edit a branch's payment text | `/admin/setup`, branches section: edit a branch's payment instructions |
| `/founder/*` items the backend lets the Super Admin decide | Fee exceptions, access extensions beyond limit, AI budget, a Branch Manager's own requests: `backend/services/founder_inbox.py:1-11`, `backend/routes/founder.py:12-19`, `backend/routes/certificates.py:118` | No UI today (the `founder` workspace is Founder-only). The Approvals page under `/admin`, the same inbox as the Founder (decision 24) |

Command palette also sends Super Admin results to `/branch/batches/$id` and `/branch/completion` (`command-palette.tsx:17-19`).

### 4.5 Curriculum-related

| Where | Role today | After R6 |
|---|---|---|
| `/branch/curriculum` | Author and approver (both) | `/admin/courses`: **create and edit** |
| `/founder/curriculum` | Not reachable (founder workspace only); backend allows (`founder.py:27`) | gone |
| `/admin/users` role descriptions `:36` | mentions curriculum | reword |
| `backend/routes/curriculum.py` (24 `require_roles`), `academic_records.py` (15) | versions, library, variations, equivalence | removed; only the course outline endpoints remain (R6) |

#### 4.5.1 Courses page for the Super Admin

`/admin/courses`, nav group "Academic" (new). List: code, title, category, combo/tracks, status, batches, active enrolments. Course page:

- Outline editor for modules and topics (add, rename, reorder, remove), reusing `branch/curriculum-tree.tsx` moved to `features/shared`. Only modules and topics are editable (decision 12).
- Blocks kept on the course: hours, completion rules, required assessments, combo track pins and the reusable module library (decisions 13 and 25). Equivalence rules, branch variations and the "prepare mapping" helper are removed.
- No draft, no version, no checklist, no submit, no approval.
- An edit applies at once, notifies the Branch Managers of branches with running batches of the course, and is audited (decision 14).
- Course code, title, category, status and tracks are read-only and come from the CRM `CourseUpserted` event (`docs/CRM_INTEGRATION.md`, `db/002_catalog_curriculum.sql:5-12`).

### 4.6 Gaps

| Gap | Evidence |
|---|---|
| No reports for the Super Admin except through `/branch/reports` (branch picker) | `access.ts:148-158`; `backend/routes/reports.py:24` |
| No support desk, no batch or schedule view in the admin workspace | same |
| AI budget approval: backend allows Super Admin, no screen | `backend/routes/founder.py:19`; only the Founder's inbox shows it (`features/founder/panel-other.tsx:18`) |
| No Courses | 4.5.1 |
| "Add role" form conflicts with one-account-per-role | `admin/users.tsx:210,362-400` |
| Cross-branch work happens with a hidden branch pick; admin pages have none (no branch filter on `/admin/students`, `/admin/issues` beyond the list) | `auth/acting.ts:12` |
| No hand-out list of migrated accounts yet; Users & access gets a hand-out page (decision 22) | plan R2 |

#### 4.7 End state for the Super Admin

One account, one role, no "Acting as", no implicit Branch workspace. Nav under `/admin`: Home, Approvals (the same inbox the Founder has; the Super Admin sees and decides every item: fee exceptions, access extensions, certificates, AI budget, Branch Managers' own requests), Users & access, Student accounts, Batches, Attendance, Support, Reports, Issues, Academic calendar, Courses, CRM sync, Setup & health, AI controls, Audit log. Batches, Students, Attendance and Reports are read-only cross-branch views with a branch filter; Support is read plus reassign. Payment instructions are edited in Setup & health, in a branches section. The independence rule stays: nobody decides their own request.

Users & access has a hand-out page listing every account created by the role split, with a one-time activation link per account (decision 22). The Super Admin and the Founder see it. A user who held several roles keeps the highest one on the existing account in the order Founder > Super Admin > Branch Manager > Trainer > Student (decision 23).

---

## 5. Founder / CEO

### 5.1 Nav (`auth/access.ts:160-166`)

Workspace `founder`, home `/founder`. No bell, no Getting started (`backend/services/nav.py:167`). Because the role also opens `admin` and `branch`, "Acting as" lists Founder, Super Admin and Branch Manager (`backend/services/auth.py:25-31`).

| Group | Item | Route | Badge |
|---|---|---|---|
| (none) | Home | `/founder` | `inbox` |
| Approvals | **Curriculum approvals** | `/founder/curriculum` | `curriculum` |
| Approvals | Certificate decisions | `/founder/certificates` | `certificates` |
| Approvals | Access extensions | `/founder/access` | `access` |
| Safety | AI controls | `/founder/ai-controls` | |

Phone bottom bar: all four items (no list; first four). The "More" sheet is empty (`app-shell.tsx:245`).

### 5.2 Screens (own workspace, `/founder/*`)

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/founder` | `features/founder/dashboard.tsx:7` | Needs-you list (AI budget, Branch Managers' own requests), company tiles | Y | none | none; panels `features/founder/panel-other.tsx:18,59` |
| `/founder/curriculum` | `features/founder/curriculum.tsx:9` | Approve and activate or return a curriculum version; equivalence rules and required-topic constraints (`CurriculumDecisions`, `academic/curriculum-model.tsx:472`) | Y | `CurriculumDecisions` uses `hasRole` (`:473-476`) | to be removed |
| `/founder/certificates` | `features/founder/certificates.tsx:6` | Certificate corrections, revocations, reinstatements, fee releases | Y | Branch Manager decides the same requests in `/branch/completion` (`shared/certificate-register.tsx:183`) | none; panels `panel-certificate.tsx:24,97` |
| `/founder/access` | `features/founder/access.tsx:16` | Access extensions beyond the Branch Manager's limit | Y | Branch Manager's Access extensions tab | imports `useUrlParams`, `Pager` from `features/branch/attendance-*` (`:8-9`); panel `panel-access.tsx:77` |
| `/founder/ai-controls` | `routes/founder.ai-controls.tsx` -> `features/admin/ai-controls.tsx:168` | Same page as `/admin/ai-controls` | Y | Super Admin | none |

Inbox pieces: `features/founder/inbox-list.tsx:28`, `panel.tsx`, `panel-frame.tsx`, `decision-bar.tsx:31`. Inbox kinds: `curriculum`, `certificate`, `fee_exception`, `access_extension`, `ai_budget`, `bm_reschedule`, `bm_correction` (`api/founder.ts:13-14`).

### 5.3 Reachable by URL, not in nav; unclear nav items

Nothing in `/founder/*` is hidden. `Home` uses the shield icon like the brand logo (`access.ts:161`).

### 5.4 Screens the Founder reaches only through another role's workspace

Today the Founder opens `admin` and `branch` implicitly. Under decision 16 the Founder does everything the Super Admin can do plus approvals, read-write across all branches, under `/founder`; day-to-day branch actions (attendance, running classes) stay with Branch Managers.

#### Through `/admin/*` (read-only today: `useCanAdminister()` false)

| Admin screen | What the Founder can do there today | Home under Founder |
|---|---|---|
| `/admin` Home | read | `/founder` Home |
| `/admin/users`, `/admin/users` filters | read staff list and scopes (`backend/routes/admin_users.py:9,16`) | `/founder/users`, same component as the Super Admin's, read-write, including the hand-out page |
| `/admin/students`, `/admin/students/$id` | read | `/founder/students`, read-write, with branch filter |
| `/admin/issues` | read | `/founder/issues`, with branch filter, Assign, notes |
| `/admin/calendar` | **add a Company Holiday** (`calendar.tsx:207-209`); sees branch closures, cannot decide (`:284`) | `/founder/calendar`: company holidays, branch closures, decide closures |
| `/admin/crm-sync` | read, no Retry | `/founder/crm-sync`, with Retry |
| `/admin/setup` | read | `/founder/setup`, with edit |
| `/admin/ai-controls` | same as `/founder/ai-controls` | already at `/founder/ai-controls`; the admin copy is not used by this role |
| `/admin/audit` | read | `/founder/audit` |
| `/admin/notifications` | open | `/founder/notifications` (the Founder's own bell, decision 16) |

#### Through `/branch/*` (read-only today: `manage` false)

| Branch screen | Founder today | Home under Founder |
|---|---|---|
| `/branch` | tiles and lists for all branches (the API allows Founder: `backend/routes/dashboards.py:10-31`, `branch.py:11`) | `/founder` Home tiles (already has company tiles) |
| `/branch/batches`, `/branch/batches/$id` | read | `/founder/batches`, branch filter, same config as the Super Admin (section 7.6) |
| `/branch/schedule`, `/branch/class-day`, `/branch/recordings` | read; `/recordings/classes` is BM/SA only (`backend/routes/recordings.py:42`), so the picker likely fails | none: running classes stays with Branch Managers |
| `/branch/progress` | read | `/founder/attendance`, read-only, branch filter |
| `/branch/completion` | read | `/founder/certificates` and the Approvals inbox |
| `/branch/waiting`, `/branch/results`, `/branch/content` | read | none (Branch Manager jobs) |
| `/branch/support` | read | `/founder/support`, read and reassign |
| `/branch/issues` | read (this is where "Go fix it" from `/admin/issues` lands) | `/founder/issues` |
| `/branch/reports` | **403**: `GET /branch/reports` is BM/SA only (`backend/routes/reports.py:24`); the Founder-allowed `GET /academic/reports` has no screen (`api/dashboards.ts:291,313`) | `/founder/reports`, company-wide, built on `GET /academic/reports` |
| `/branch/curriculum` | read | `/founder/courses` (edit) |

Command palette: Founder's student result opens `/admin/students/$id`, batch result `/branch/batches/$id`, certificate result `/founder/certificates` (`command-palette.tsx:15-20`).

### 5.5 Curriculum-related

| Where | After R6 |
|---|---|
| Nav `Curriculum approvals` + badge `curriculum` (`access.ts:162`), `routes/founder.curriculum.tsx`, `features/founder/curriculum.tsx`, `panel-curriculum.tsx`, `panel.tsx:5,10-11` | Remove (plan R6) |
| Inbox kind `curriculum` and group `curriculum` (`api/founder.ts:13-14,30`), `backend/services/founder_inbox.py` `_curriculum_items`, `GROUPS`, `PAGES`, nav count key `curriculum` | Remove from inbox and nav counts |
| `founder/decision-bar.tsx:19` comment about curriculum activation dialog | Reword |
| `Equivalence rules and required-topic constraints` section (`founder/curriculum.tsx:44-45`) | Gone: equivalence rules are removed (decision 25) |

#### 5.5.1 Courses page for the Founder

`/founder/courses`, nav group "Company" (replaces "Approvals" as the group for course work; approvals keep their own group). Same page as the Super Admin's (superset): list with company-wide counts per branch (batches, active enrolments), and an outline editor for modules and topics. Same blocks kept (hours, completion rules, required assessments, combo track pins, reusable module library), same rules (edits apply at once, notify affected Branch Managers, are audited; code, title, category, status and tracks stay read-only from the CRM).

### 5.6 Gaps

| Gap | Evidence |
|---|---|
| No notification centre or bell: a decision waiting is visible only on Home and nav badges | `app-shell.tsx:26-31` |
| No company reports screen; `/academic/reports` is unused | 5.4 |
| Finance summaries (API: BM, SA, Founder) have no screen; Home shows CRM money tiles only when the CRM sent figures | `backend/routes/finance.py:37,44`; `founder/dashboard.tsx:17-30` |
| Home has no Getting started; no empty-state hint | `backend/services/nav.py:167` |
| Everything outside the inbox needs the "Acting as" switcher | 5.4 |
| Phone "More" sheet is empty | `app-shell.tsx:245` |

#### 5.7 End state for the Founder

One account, one role, no "Acting as". The Founder does everything the Super Admin can do, plus approvals, read-write across all branches, under `/founder`. Day-to-day branch actions (attendance, running classes) stay with Branch Managers. Nav under `/founder`: Home (the decision inbox), Approvals (certificate decisions, access extensions, fee exceptions, AI budget, Branch Managers' own requests; the same inbox the Super Admin has), Courses (edit), Users & access (with the hand-out page), Students, Batches, Attendance, Issues, Reports (company-wide), Academic calendar, Support, CRM sync, Setup & health, AI controls, Audit log. The Founder has a bell (`/founder/notifications`), a notification inbox and a Getting started card. The phone "More" sheet carries every item beyond the four pinned.

---

## 6. Curriculum screens to replace by Courses (all roles)

| Piece | Files | Action (R6) |
|---|---|---|
| Routes | `routes/branch.curriculum.tsx`, `routes/founder.curriculum.tsx` | Remove; add `/admin/courses`, `/branch/courses`, `/founder/courses` (the Trainer gets a read-only outline block on the batch page, no route) |
| Nav items | `auth/access.ts:139` (Branch), `:162` (Founder) | Replace / remove |
| Nav badge `curriculum` | `access.ts:162`; `backend/services/nav.py` (`_founder_counts` via `founder_inbox.counts()`), `backend/services/founder_inbox.py` | Remove |
| Version editor and model | `features/academic/curriculum.tsx`, `features/academic/curriculum-model.tsx` | Remove (editor of modules/topics survives as the course editor) |
| Branch pieces | `features/branch/curriculum-checklist.tsx`, `curriculum-new-draft.tsx`, `curriculum-pickers.tsx`, `curriculum-tree.tsx` | Remove except the tree, move to `features/shared` |
| Founder pieces | `features/founder/curriculum.tsx`, `panel-curriculum.tsx`, `panel.tsx:5,10-11` | Remove |
| API client | `api/curriculum.ts`, curriculum calls in `api/delivery.ts`, `api/founder.ts:8-24,76-80` | Remove |
| Links and labels | `academic/dashboard.tsx:7`, `lib/status.ts:270`, `notification-centre.tsx:27`, `lib/i18n.ts` | Reword |
| Backend routes | `backend/routes/curriculum.py`, `academic_records.py`, `founder.py:27` | Remove; replaced by course outline endpoints |

**Work for R6:** the modules and topics that students, trainers and sessions use hang off `curriculum_version_id`. That column appears in `db/002, 003, 004, 005, 010, 020, 030, 040, 095, 097, 098, 102, 105, 109` (occurrence counts in that order: 5, 4, 2, 8, 9, 9, 4, 6, 4, 20, 2, 18, 1, 8). Enrolments, batches, sessions, content, assessments, attendance and topic progress all point at it. Decision 11 puts the outline on the course, so the migration re-points every one of these tables (and the queries, views and foreign keys that use them) to the course before the version, draft and approval tables are dropped. Courses are never dropped.

---

## 7. Shared screens

Components used by more than one role, each with a fixed per-role config. Rule from the plan: no `hasRole` inside; the route passes the config.

Legend: Y = on, N = off, `-` = role does not use the component.

### 7.1 Notification centre (`features/shared/notification-centre.tsx:89`)

| Option | Student | Trainer | Branch Manager | Super Admin | Founder |
|---|---|---|---|---|---|
| Route | `/notifications` | `/trainer/notifications` | `/branch/notifications` | `/admin/notifications` | `/founder/notifications` (new bell, decision 16) |
| `showSystemIssuesTab` (today `hasRole("SUPER_ADMIN")`, `:90-91`) | N | N | N | Y | Y |
| `title` | translated | "Notifications" | "Notifications" | "Notifications" | "Notifications" |

The Founder's inbox carries decisions waiting (the nav counts that already exist).

### 7.2 Staff profile (`features/shared/staff-profile.tsx:12`, `/account/profile`)

| Option | Trainer | Branch Manager | Super Admin | Founder |
|---|---|---|---|---|
| `role` label | from session | from session | from session | from session |
| `branchLabel` | its branch | its branch (fixed for the session) | "All branches" | "All branches" |
| Today | union of all scopes (`:29-32`) | same | same | same |

Frames inside the shell of "the workspace the user lands in" (`access.ts:63-66`), which stays valid with one role.

### 7.3 Academic calendar (one component replacing `features/admin/calendar.tsx:201` and `features/shared/academic-calendar.tsx:39`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Surface | Section of Schedule & calendar | `/admin/calendar` | `/founder/calendar` |
| `canAddCompanyHoliday` | N | Y | Y |
| `canProposeBranchClosure` | Y (own branch, waits for approval) | Y (any branch, takes effect at once) | Y (any branch, takes effect at once) |
| `canDecideClosure` | N | Y | Y |
| `canEditOrCancel` | N | Y | Y |
| `branchScope` | the session's branch | any | any |
| `view` | list | month and list | month and list |

Decision 18: the Branch Manager proposes closures and the Super Admin approves; Founder and Super Admin add company holidays. A Branch Manager can no longer decide a closure, so the proposer and decider are never the same person.

### 7.4 Issues list (`features/branch/issues.tsx:175`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| `canNote` | Y | Y | Y |
| `canAssign` | N | Y (today `:8`) | Y |
| `branchScoped` | Y (the session's branch) | N (all) | N (all) |
| `goFix` target | `/branch/*` | read-only detail under `/admin/*`, with Assign (decision 19) | read-only detail under `/founder/*`, with Assign |

### 7.5 Support desk (`features/shared/support-desk.tsx:100`)

| Option | Trainer | Branch Manager | Super Admin | Founder |
|---|---|---|---|---|
| `simple` | Y (`trainer/support.tsx:22`) | N | N | N |
| `views` (tabs with counts) | N | Y (`branch/support.tsx:56`) | Y | Y |
| `base.mine` | Y | N | N | N |
| `branchId` | - | the session's branch | any (filter) | any (filter) |
| `canReassign` (today `profile.scopes.some(BM, SA, FOUNDER)`, `support-desk.tsx:444`) | N | Y | Y | Y |
| `canEscalate` | Y | N | N | N |
| Route | `/trainer/support` | `/branch/support` | `/admin/support` | `/founder/support` |

### 7.6 Batch page parts and operations (`features/academic/batch-panel.tsx`, `batch-operations.tsx`, `features/branch/batch-page.tsx`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| `manage` (today `useCanManage`) | Y | N | N |
| `approve` (today `useIsManager`, overrides and decisions) | Y | N | N |
| `branchScope` | the session's branch | all (filter) | all (filter) |
| Route | `/branch/batches` | `/admin/batches` | `/founder/batches` |

Day-to-day branch actions stay with Branch Managers (decisions 15 and 16); Super Admin and Founder decisions are made in the Approvals inbox, not on the batch page.

Replaces `useCanManage()` / `useIsManager()` in: `branch/batches.tsx:35`, `class-day.tsx:67`, `waiting.tsx:148`, `payment-instructions.tsx:15`, `batch-page.tsx:99,160,198`, `schedule.tsx:44,291`, `new-class.tsx:46`, `class-actions.tsx:73-74`, `batch-dialogs.tsx:154`, `academic/class-operations.tsx:35,183,276-278,380-381`, `academic/batch-operations.tsx:41-42,947-948`, `academic/batch-panel.tsx` (props), `shared/sessions.tsx:26`.

### 7.7 Class sessions table and requests (`features/shared/sessions.tsx`)

| Option | Trainer | Branch Manager |
|---|---|---|
| `actions.manager` | N (`trainer/sessions.tsx:29`) | Y (Branch has its own `ClassActions`, `class-actions.tsx:63`) |
| `actions.trainer` | Y | N |
| `RequestsPanel.manager` | N (`:40`) | Y (decisions are in `schedule.tsx` `NeedsDecision`) |

### 7.8 Certificate and completion decisions (`shared/certificate-register.tsx:183`, `founder/panel-certificate.tsx`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Surface | collapsed section in `/branch/completion` | `/admin/approvals` (Approvals page) | `/founder/certificates` and the Home inbox |
| Decides | change requests and fee releases it may (API: "independent approver") | every item in the shared inbox | every item in the shared inbox |
| `kinds` | certificate | certificate, fee_exception, access_extension, ai_budget, Branch Managers' own requests | same as Super Admin |

The Approvals page is the same inbox the Founder has (`InboxList`); Super Admin and Founder see and decide the same items. The independence rule stays: nobody decides their own request. The `CertificateDecisions` table and the Founder's `InboxList` panels (two UIs today) become one inbox component.

### 7.9 Question bank (`features/trainer/question-bank.tsx:242`)

| Option | Trainer | Branch Manager |
|---|---|---|
| `canApprove` | N | Y (`branch/content.tsx:216`) |
| Can write | Y (`:256`) | N |
| Location | `features/trainer/` imported by `features/branch/content.tsx:11` | move to `features/shared` |

### 7.10 AI controls (`features/admin/ai-controls.tsx:168`)

| Option | Super Admin | Founder |
|---|---|---|
| Route | `/admin/ai-controls` | `/founder/ai-controls` |
| Config | none; identical page | none; identical page |
| `can_switch` | API | API |

### 7.11 Assistant (`features/shared/assistant.tsx:46`)

| Option | Student | Trainer |
|---|---|---|
| `variant` | student | trainer |
| Offer "send to a person" | Y (`:325`) | N |
| Sources open at | student pages | `/trainer/*` (`:410-419`) |

Backend audience uses the union (`backend/services/ask_nipuna.py:95`).

### 7.12 Needs-you / dashboard building blocks

`components/lms/needs-you-list.tsx` (Trainer Today, Branch My work, Admin Home, Founder inbox via `founder/inbox-list.tsx`), `features/shared/dashboard-parts.tsx` (`Tile`, `CrmTile`, `QuickLinks`: Branch, Founder, academic), `components/lms/getting-started.tsx:28` (Student, Trainer, Branch, Admin; the Founder gets the card too, decision 16). Role-neutral. `GettingStartedCard` and `useNavCounts` take a `workspace` argument (`getting-started.tsx:34`, `app-shell.tsx:86`) that the plan turns into the session role (R3).

### 7.13 Reports

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Component | `features/branch/reports.tsx:57` | same component, branch filter | same component, branch filter, company-wide |
| Route | `/branch/reports` | `/admin/reports` | `/founder/reports` |
| `branchScope` | the session's branch | all or one | all or one |
| API | `GET /branch/reports` (BM, SA) | same | `GET /academic/reports` (already allowed for the Founder); this removes the 403 the Founder gets on `/branch/reports` today |

### 7.14 App shell and palette

| Item | Today | Fixed config per role |
|---|---|---|
| Header label | "Acting as" menu or label (`app-shell.tsx:115-121`) | static `Role · Branch` (R4) |
| Bell route | `NOTIFICATIONS[workspace]` (`:26-31`) | one route per role, including `/founder/notifications` |
| Account menu link | student `/my-account`, others `/account/profile` (`:146-158`) | same, from the role |
| Command palette pages and record targets | all held workspaces, `recordTarget` by workspace (`command-palette.tsx:15-20,46-52`) | one nav list, record links per role (Founder student = founder page, not `/admin/students`) |
| Mobile bar | `MOBILE_BAR` for 3 roles (`access.ts:177`) | explicit list for every role |

### 7.15 Cross-feature imports to move into `features/shared` (R5)

| Import | File:line |
|---|---|
| `founder/*` imports `branch/attendance-url`, `branch/attendance-pager` | `founder/access.tsx:8-9`, `founder/inbox-list.tsx:5` |
| `branch/content` imports `trainer/question-bank` | `branch/content.tsx:11` |
| `branch/issues` imports `admin/issue-assign`; `admin/issues` imports `branch/issues` | `branch/issues.tsx:17`, `admin/issues.tsx:4` |
| `shared/academic-calendar` imports `admin/shared` `Pager` | `shared/academic-calendar.tsx:13` |
| `branch/*` imports `academic/*` (batch panel, class operations, timetable, curriculum model) | `branch/batch-page.tsx:11-12`, `class-day.tsx:11`, `new-batch-wizard.tsx:13`, `waiting.tsx:14` |
| `trainer/class-flow` imports `trainer/attendance` `RegisterForm` | `class-flow.tsx:19` (same role, fine) |
| `features/academic/` directory is left over from the Academic Coordinator role (merged into Branch Manager) | whole directory |

### 7.16 Backend code that depends on the union of roles (input for R3)

| Place | Evidence |
|---|---|
| `require_roles` and `has_role` use any scope | `backend/routes/decorators.py:32-45`, `backend/services/context.py:50-56` |
| Scope helpers | `backend/services/scope.py:23-44` (`visible_branch_ids`, `trainer_batch_ids`) |
| Workspaces and home | `backend/services/auth.py:25-39,185-192` |
| `/me/nav-counts`, `/me/getting-started` take `workspace` | `backend/services/nav.py:31-36,111-122,166-176` |
| Support trainer flag, `my_requests` wording, Ask Nipuna audience, delivery access | `backend/services/support.py:56,63,71,125,141,241`, `my_requests.py:88`, `ask_nipuna.py:95`, `delivery_access.py:22` |
| Frontend union readers | `shared/delivery-ui.tsx:16-18,59-61`, `auth/auth.tsx:77,85`, `admin/format.ts:20-22`, `shared/support-desk.tsx:444`, `shared/staff-profile.tsx:29-32`, `components/lms/app-shell.tsx:80-82` |

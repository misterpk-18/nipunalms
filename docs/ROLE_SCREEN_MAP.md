# Role screen map (phase R1)

Read-only inventory for `docs/ROLE_SEPARATION_PLAN.md`. Nothing here is a decision: sections marked **Proposal** are for the product owner to confirm in "Open questions" (last section). File:line references are against commit `ae7ee4c` (HEAD of `main`, 18 Oct 2026). Paths are relative to `frontend/src/` unless they start with `backend/`.

## How the app decides who sees what today

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

---

# 1. Student

## 1.1 Nav (`auth/access.ts:100-114`)

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

## 1.2 Screens

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

## 1.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/courses/*`, `/modules/*`, `/topics/*`, `/sessions/*`, `/assignments/$id`, `/tests/$id`, `/support/$requestId`, `/notifications`, `/my-account` | Detail pages and inbox; reached by links, bell or avatar menu. Fine, but `/my-account` (Fees & Receipts, profile) is only in the avatar menu and the phone "More" sheet. |
| Legacy redirects (no screen) | `/assignments`, `/tests`, `/attendance`, `/results`, `/finance`, `/profile`, `/recordings`, `/resources` (`routes/*.tsx`). Keep or drop in R7. |
| "Class Materials" vs "My Learning" | Both list recordings and files per topic; `materials.tsx:1` groups them by course/topic again. Purpose overlap, not unclear to the user. |
| Phone bar | 4 of 10 items pinned; Progress, Certificates, Support are two taps (More, then item). |

## 1.4 Screens reached only through another role's workspace

None. A Student holds only the student workspace.

## 1.5 Curriculum-related screens

| Where | What | After R6 |
|---|---|---|
| `/courses/*`, `/modules/*`, `/topics/*`, `features/student/my-courses.tsx:82` ("No curriculum yet") | The modules and topics a student sees come from the batch's curriculum version | Must keep working. The outline has to come from the course (open question Q1). Rename "No curriculum yet" wording (`lib/i18n.ts` key `noCurriculumYet`). |
| Courses page for the Student | `My Learning` (`/my-courses`) already is the student's course list | No new page. Course detail stays read-only. |

## 1.6 Gaps

| Gap | Evidence |
|---|---|
| Preferred-slot request exists only on Home and only while a course has no batch | `features/student/batch-changes.tsx:1` |
| Material-change answers are handled on Home only | `features/student/dashboard.tsx:143` |
| Fees and receipts are inside My Account, two taps on a phone | `access.ts:114`, `routes/finance.tsx` |
| Whether the Student can see their batch's trainer, room or timetable outside a class page is not obvious from nav | `/my-courses`, `/courses/$enrolmentId`: confirm in R7 |

---

# 2. Trainer

## 2.1 Nav (`auth/access.ts:116-130`)

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

## 2.2 Screens

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

## 2.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/trainer/to-grade/$kind/$id`, `/trainer/batches/$id`, `/trainer/students/$id`, `/trainer/notifications` | Detail pages and inbox, opened by links or bell. |
| `/trainer/reviews` | Redirect to To grade (`routes/trainer.reviews.tsx`). |
| `Content` sits under group "Grade" | It is the trainer's uploads and their review state, not grading. |
| `Assignments` vs `Assessments` | Two Grade items with near-identical names; assessments hold questions, tests and interviews. |
| `My requests` under "Teach" | It is a status list of asks to the Branch Manager. |
| `Today` / `Sessions` / `Attendance` | Three ways into a class; the UX plan already notes this overlap (`docs/UX_PLAN.md`). |

## 2.4 Screens reached only through another role's workspace

None today. Hand-offs to other roles (no screen of the trainer's own): question approval is on the Branch Manager's `/branch/content` (`features/branch/content.tsx:216`), reschedule and correction decisions are on `/branch/schedule` and `/branch/progress`.

## 2.5 Curriculum-related screens

| Where | What | After R6 |
|---|---|---|
| `trainer/assignments.tsx:30-31,89,124`, `trainer/question-bank.tsx:132-133` | Topic picker fed by `GET /assessments/curriculum` | Same picker fed by the course's outline |
| `trainer/batch-page.tsx:62`, `shared/content-detail.tsx:27` | "Curriculum <version>" / "No approved curriculum yet" | Show the course name |
| Courses page for the Trainer | None today | **Proposal (Q9):** no nav item; a read-only "Course outline" block on the trainer batch page |

## 2.6 Gaps

| Gap | Evidence |
|---|---|
| Backend lets a Trainer recommend a course completion, no trainer screen exists | `backend/routes/completion.py:19,33`; `features/trainer/*` has no completion UI |
| No holiday / closure view for trainers when planning | `features/trainer/*` has no calendar; the calendar lives on `/branch/schedule` and `/admin/calendar` |
| No course outline outside the class flow and topic pickers | `features/trainer/batch-page.tsx` shows only a version label |
| Student flags (`FlagStudentDialog`) reachable only from Students rows, Support button, student page | `trainer/support.tsx:8-11` |

---

# 3. Branch Manager

## 3.1 Nav (`auth/access.ts:132-146`)

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

## 3.2 Screens

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

## 3.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/branch/recordings` | **Not in the sidebar.** Linked from Class day (`class-day.tsx:83`), the academic quick links (`academic/dashboard.tsx:10,43`), Issues and notifications. |
| Payment instructions (how students pay) | Only a block at the bottom of the home page (`dashboard.tsx:71`). |
| Access extensions | A tab inside Student support, not a nav item (`support.tsx:13-14`). |
| Certificate corrections / fee releases | A collapsed section inside Completion & certificates (`completion.tsx:161`). |
| Academic calendar | Embedded at the bottom of Schedule & calendar (`schedule.tsx:488`). |
| Redirect-only routes | `/academic`, `/academic/*`, `/branch/operations`, `/branch/meet-operations`, `/branch/academic-reports`, `/branch/assessments`, `/branch/certificates`, `/branch/content-review`, `/branch/exceptions`, `/branch/recording-exceptions`, `/branch/requests` (`routes/*.tsx`). `/academic/batches?crm_admission_id=&student=` is the CRM "Open in LMS" link and must keep working (`routes/academic.$.tsx:11-12`). |
| Unclear nav items | `Attendance & progress` URL is `/branch/progress`. `Student support` and `Issues` overlap for student requests (an extension or request appears in both; `backend/services/issues.py:51,55`). `Content & questions` mixes two jobs (content review, question approval). |

## 3.4 Screens reached only through another role's workspace

None for a pure Branch Manager. (Super Admin and Founder section below.)

## 3.5 Curriculum-related screens to replace

| Where | What | Replace with |
|---|---|---|
| Nav `Curriculum` (`access.ts:139`), route `routes/branch.curriculum.tsx` | Draft/submit/review versions | **Courses**, read-only (see 3.5.1) |
| `features/academic/curriculum.tsx` (396 lines), `curriculum-model.tsx` (733), `branch/curriculum-checklist.tsx`, `curriculum-new-draft.tsx`, `curriculum-pickers.tsx`, `curriculum-tree.tsx` | Version editor, checklist, tree, library, variations, equivalence, combo pins | Removed; the module/topic tree (`curriculum-tree.tsx`) is reused by the Super Admin course editor |
| `academic/dashboard.tsx:7` quick link "Curriculum versions" | | Link to Courses |
| `branch/waiting.tsx:14` imports `PrepareMapping` from `curriculum-model.tsx` | Student mapping helper in the waiting list | Decide what survives (Q3) |
| `batch-panel.tsx:54`, `batch-operations.tsx:843` | "Curriculum version" row, "same curriculum version" text | Show the course |
| `lib/status.ts:270` (`curriculum` status domain), `notification-centre.tsx:27` (category "Curriculum") | | Remove |

### 3.5.1 Courses page for the Branch Manager (Proposal)

`/branch/courses`, nav group "Teaching" (replaces Curriculum). Read-only. List of courses offered (code, title, category, combo tracks, status as sent by the CRM) with "batches running at my branch" and "students waiting". A course page shows its outline (modules, topics) and a "New batch for this course" button that opens `/branch/batches?new=1&course=<id>` (the wizard already accepts it, `routes/branch.batches.index.tsx`).

## 3.6 Gaps

| Gap | Evidence |
|---|---|
| Career and placements: no staff screen. Opportunities, CV review, career profiles, applications and placement outcomes exist in the API and the student's "CV reviewed" step depends on it | `backend/routes/career.py:56-178`; frontend only `api/career.ts` student calls and `features/student/career.tsx` |
| Finance view: the API serves finance summaries to BM, SA and Founder, no screen | `backend/routes/finance.py:37,44`; no frontend caller |
| `Recordings` not in nav | 3.3 |
| Payment instructions buried on the home page | `dashboard.tsx:71` |
| Branch pick repeated as page-head dropdown and header menu; "All branches" option exists | `my-work.tsx:37-51`, `acting-as.tsx:50-61` (plan decision 4 removes this: see Q7) |
| No view of trainers (availability, load) when assigning | `batch-panel.tsx:149` shows only the batch's own trainers |

---

# 4. Super Admin

## 4.1 Nav (`auth/access.ts:148-158`)

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

## 4.2 Screens (own workspace, `/admin/*`)

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

## 4.3 Reachable by URL, not in nav; unclear nav items

| Item | Note |
|---|---|
| `/admin/students/$id`, `/admin/notifications` | Detail page and inbox. |
| `/admin/exceptions`, `/admin/integrations`, `/admin/security` | Redirects to Issues / Setup & health (`routes/admin.*.tsx`). |
| `Home` badge | Shows the sum of every other badge (`backend/services/nav.py` `_admin_counts`: `"home": sum(...)`). |
| `Student accounts` vs `Users & access` | Two people lists; one is CRM-created students, one is staff. Clear in the page text, not in the labels. |
| `CRM sync` under "Operations" | It is a system integration screen. |

## 4.4 Screens the Super Admin reaches only through the Branch Manager workspace

The Super Admin holds the `branch` workspace, so all of 3.2 is open with `manage` and `approver` true. Rows below are what the Super Admin does there and a **Proposal** for a home under `/admin/*`. All "Proposal" rows depend on Q5 (how much of the branch workflow should a Super Admin keep).

| Branch screen used today | What the Super Admin does there | Proposed home under Super Admin (shared component, config in section 7) |
|---|---|---|
| `/branch` My work | Sees the picked branch's list | None: `/admin` Home already has a needs-you list. |
| `/branch/issues` ("Go fix it" targets) | Issues in `/admin/issues` send the Super Admin to `/branch/waiting`, `/branch/recordings`, `/branch/support`, `/branch/results`, `/branch/class-day`, `/branch/schedule` (`backend/services/issues.py:45-59`) | Keep Assign in `/admin/issues`; "Go fix it" for this role opens a read-only drill-down under `/admin/*`, or is removed (Q5) |
| `/branch/batches`, `/branch/batches/$id` | Full batch management, any branch | `/admin/batches` read-only, with branch filter (Q5) |
| `/branch/waiting` | Allocate | none (Branch Manager job) |
| `/branch/schedule` + calendar | Approve reschedules, add classes | none; calendar stays `/admin/calendar` |
| `/branch/class-day`, `/branch/recordings` | Fix Meet links, release recordings | none |
| `/branch/progress`, `/branch/results`, `/branch/content` | Review, moderate, publish, approve content and questions | none |
| `/branch/completion` | Decide completions, issue certificates, decide certificate requests and fee releases | decisions only: an Approvals page shared with the Founder (see section 7, `InboxList`) |
| `/branch/support` | Reply to students, decide access extensions | `/admin/support` read + reassign (Q5), extension decisions in Approvals |
| `/branch/reports` | Reports for any branch | `/admin/reports` with a branch filter (same component) |
| `/branch/curriculum` | Draft, approve, activate versions | `/admin/courses` (Courses, edit) |
| `/branch` PaymentInstructions | Edit a branch's payment text | `/admin/branches` or within Setup (Q5) |
| `/founder/*` items the backend lets the Super Admin decide | Fee exceptions, access extensions beyond limit, AI budget, a Branch Manager's own requests: `backend/services/founder_inbox.py:1-11`, `backend/routes/founder.py:12-19`, `backend/routes/certificates.py:118` | No UI today (the `founder` workspace is Founder-only). Approvals page for the Super Admin (Q5) |

Command palette also sends Super Admin results to `/branch/batches/$id` and `/branch/completion` (`command-palette.tsx:17-19`).

## 4.5 Curriculum-related

| Where | Role today | After R6 |
|---|---|---|
| `/branch/curriculum` | Author and approver (both) | `/admin/courses`: **create and edit** |
| `/founder/curriculum` | Not reachable (founder workspace only); backend allows (`founder.py:27`) | gone |
| `/admin/users` role descriptions `:36` | mentions curriculum | reword |
| `backend/routes/curriculum.py` (24 `require_roles`), `academic_records.py` (15) | versions, library, variations, equivalence | removed or reduced (R6) |

### 4.5.1 Courses page for the Super Admin (Proposal)

`/admin/courses`, nav group "Academic" (new) or "Operations". List: code, title, category, combo/tracks, status, batches, active enrolments. Course page: outline editor (modules, topics: add, rename, reorder, remove; reuse `branch/curriculum-tree.tsx`); optional blocks pending Q3 (hours, completion rules, required assessments, combo pins). No draft, no submit, no approval. Edits are audited. Course code, title, category and status come from the CRM `CourseUpserted` event (`docs/CRM_INTEGRATION.md`, `db/002_catalog_curriculum.sql:5-12`): see Q2.

## 4.6 Gaps

| Gap | Evidence |
|---|---|
| No reports for the Super Admin except through `/branch/reports` (branch picker) | `access.ts:148-158`; `backend/routes/reports.py:24` |
| No support desk, no batch or schedule view in the admin workspace | same |
| AI budget approval: backend allows Super Admin, no screen | `backend/routes/founder.py:19`; only the Founder's inbox shows it (`features/founder/panel-other.tsx:18`) |
| No Courses | 4.5.1 |
| "Add role" form conflicts with one-account-per-role | `admin/users.tsx:210,362-400` |
| Cross-branch work happens with a hidden branch pick; admin pages have none (no branch filter on `/admin/students`, `/admin/issues` beyond the list) | `auth/acting.ts:12` |
| No hand-out list of migrated accounts yet | plan R2 |

---

# 5. Founder / CEO

## 5.1 Nav (`auth/access.ts:160-166`)

Workspace `founder`, home `/founder`. No bell, no Getting started (`backend/services/nav.py:167`). Because the role also opens `admin` and `branch`, "Acting as" lists Founder, Super Admin and Branch Manager (`backend/services/auth.py:25-31`).

| Group | Item | Route | Badge |
|---|---|---|---|
| (none) | Home | `/founder` | `inbox` |
| Approvals | **Curriculum approvals** | `/founder/curriculum` | `curriculum` |
| Approvals | Certificate decisions | `/founder/certificates` | `certificates` |
| Approvals | Access extensions | `/founder/access` | `access` |
| Safety | AI controls | `/founder/ai-controls` | |

Phone bottom bar: all four items (no list; first four). The "More" sheet is empty (`app-shell.tsx:245`).

## 5.2 Screens (own workspace, `/founder/*`)

| Route | Feature file | Purpose | In nav | Shared with | Role-dependent logic |
|---|---|---|---|---|---|
| `/founder` | `features/founder/dashboard.tsx:7` | Needs-you list (AI budget, Branch Managers' own requests), company tiles | Y | none | none; panels `features/founder/panel-other.tsx:18,59` |
| `/founder/curriculum` | `features/founder/curriculum.tsx:9` | Approve and activate or return a curriculum version; equivalence rules and required-topic constraints (`CurriculumDecisions`, `academic/curriculum-model.tsx:472`) | Y | `CurriculumDecisions` uses `hasRole` (`:473-476`) | to be removed |
| `/founder/certificates` | `features/founder/certificates.tsx:6` | Certificate corrections, revocations, reinstatements, fee releases | Y | Branch Manager decides the same requests in `/branch/completion` (`shared/certificate-register.tsx:183`) | none; panels `panel-certificate.tsx:24,97` |
| `/founder/access` | `features/founder/access.tsx:16` | Access extensions beyond the Branch Manager's limit | Y | Branch Manager's Access extensions tab | imports `useUrlParams`, `Pager` from `features/branch/attendance-*` (`:8-9`); panel `panel-access.tsx:77` |
| `/founder/ai-controls` | `routes/founder.ai-controls.tsx` -> `features/admin/ai-controls.tsx:168` | Same page as `/admin/ai-controls` | Y | Super Admin | none |

Inbox pieces: `features/founder/inbox-list.tsx:28`, `panel.tsx`, `panel-frame.tsx`, `decision-bar.tsx:31`. Inbox kinds: `curriculum`, `certificate`, `fee_exception`, `access_extension`, `ai_budget`, `bm_reschedule`, `bm_correction` (`api/founder.ts:13-14`).

## 5.3 Reachable by URL, not in nav; unclear nav items

Nothing in `/founder/*` is hidden. `Home` uses the shield icon like the brand logo (`access.ts:161`).

## 5.4 Screens the Founder reaches only through another role's workspace

### Through `/admin/*` (read-only: `useCanAdminister()` false)

| Admin screen | What the Founder can do there | Proposed home under Founder (Proposal, Q6) |
|---|---|---|
| `/admin` Home | read | keep `/founder` Home |
| `/admin/users`, `/admin/users` filters | read staff list and scopes (`backend/routes/admin_users.py:9,16`) | none (Q6) |
| `/admin/students`, `/admin/students/$id` | read | `/founder/students` read-only, if kept (Q6) |
| `/admin/issues` | read | `/founder/issues` read-only with branch filter, if kept |
| `/admin/calendar` | **add a Company Holiday** (`calendar.tsx:207-209`); sees branch closures, cannot decide (`:284`) | `/founder/calendar`: company holidays add/edit; closures read |
| `/admin/crm-sync` | read, no Retry | `/founder/...` or none (Q6) |
| `/admin/setup` | read | none or read (Q6) |
| `/admin/ai-controls` | same as `/founder/ai-controls` | already at `/founder/ai-controls`; drop the admin copy for this role |
| `/admin/audit` | read | `/founder/audit` read-only (Q6) |
| `/admin/notifications` | open | none: Founder has no bell today (Q10) |

### Through `/branch/*` (read-only: `manage` false)

| Branch screen | Founder today | Proposed home under Founder (Proposal, Q6) |
|---|---|---|
| `/branch` | tiles and lists for all branches (the API allows Founder: `backend/routes/dashboards.py:10-31`, `branch.py:11`) | `/founder` Home tiles (already has company tiles) |
| `/branch/batches`, `/branch/batches/$id` | read | `/founder/batches` read-only, branch filter |
| `/branch/schedule`, `/branch/class-day`, `/branch/recordings` | read; `/recordings/classes` is BM/SA only (`backend/routes/recordings.py:42`), so the picker likely fails | none, or a read-only schedule (Q6) |
| `/branch/progress`, `/branch/completion` | read | `/founder/students` / certificates register |
| `/branch/waiting`, `/branch/results`, `/branch/content`, `/branch/support` | read | none (Branch Manager jobs) |
| `/branch/issues` | read (this is where "Go fix it" from `/admin/issues` lands) | `/founder/issues` read-only |
| `/branch/reports` | **403**: `GET /branch/reports` is BM/SA only (`backend/routes/reports.py:24`); the Founder-allowed `GET /academic/reports` has no screen (`api/dashboards.ts:291,313`) | `/founder/reports` company-wide (Q8) |
| `/branch/curriculum` | read | gone with curriculum |

Command palette: Founder's student result opens `/admin/students/$id`, batch result `/branch/batches/$id`, certificate result `/founder/certificates` (`command-palette.tsx:15-20`).

## 5.5 Curriculum-related

| Where | After R6 |
|---|---|
| Nav `Curriculum approvals` + badge `curriculum` (`access.ts:162`), `routes/founder.curriculum.tsx`, `features/founder/curriculum.tsx`, `panel-curriculum.tsx`, `panel.tsx:5,10-11` | Remove (plan R6) |
| Inbox kind `curriculum` and group `curriculum` (`api/founder.ts:13-14,30`), `backend/services/founder_inbox.py` `_curriculum_items`, `GROUPS`, `PAGES`, nav count key `curriculum` | Remove from inbox and nav counts |
| `founder/decision-bar.tsx:19` comment about curriculum activation dialog | Reword |
| `Equivalence rules and required-topic constraints` section (`founder/curriculum.tsx:44-45`) | Gone unless Q3 keeps it |

### 5.5.1 Courses page for the Founder (Proposal)

`/founder/courses`, nav group "Approvals" becomes "Company" or similar. Read-only. Same list as the Super Admin's but with company-wide counts per branch (batches, active enrolments). Course page: outline read-only.

## 5.6 Gaps

| Gap | Evidence |
|---|---|
| No notification centre or bell: a decision waiting is visible only on Home and nav badges | `app-shell.tsx:26-31` |
| No company reports screen; `/academic/reports` is unused | 5.4 |
| Finance summaries (API: BM, SA, Founder) have no screen; Home shows CRM money tiles only when the CRM sent figures | `backend/routes/finance.py:37,44`; `founder/dashboard.tsx:17-30` |
| Home has no Getting started; no empty-state hint | `backend/services/nav.py:167` |
| Everything outside the inbox needs the "Acting as" switcher | 5.4 |
| Phone "More" sheet is empty | `app-shell.tsx:245` |

---

# 6. Curriculum screens to replace by Courses (all roles)

| Piece | Files | Action (R6) |
|---|---|---|
| Routes | `routes/branch.curriculum.tsx`, `routes/founder.curriculum.tsx` | Remove; add `/admin/courses`, `/branch/courses`, `/founder/courses` (and optionally trainer, Q9) |
| Nav items | `auth/access.ts:139` (Branch), `:162` (Founder) | Replace / remove |
| Nav badge `curriculum` | `access.ts:162`; `backend/services/nav.py` (`_founder_counts` via `founder_inbox.counts()`), `backend/services/founder_inbox.py` | Remove |
| Version editor and model | `features/academic/curriculum.tsx`, `features/academic/curriculum-model.tsx` | Remove (editor of modules/topics survives as the course editor) |
| Branch pieces | `features/branch/curriculum-checklist.tsx`, `curriculum-new-draft.tsx`, `curriculum-pickers.tsx`, `curriculum-tree.tsx` | Remove except the tree, move to `features/shared` |
| Founder pieces | `features/founder/curriculum.tsx`, `panel-curriculum.tsx`, `panel.tsx:5,10-11` | Remove |
| API client | `api/curriculum.ts`, curriculum calls in `api/delivery.ts`, `api/founder.ts:8-24,76-80` | Remove |
| Links and labels | `academic/dashboard.tsx:7`, `lib/status.ts:270`, `notification-centre.tsx:27`, `lib/i18n.ts` | Reword |
| Backend routes | `backend/routes/curriculum.py`, `academic_records.py`, `founder.py:27` | Remove or reduce |

**Finding for R6 (not in the plan):** the modules and topics that students, trainers and sessions use hang off `curriculum_version_id`. That column appears in `db/002, 003, 004, 005, 010, 020, 030, 040, 095, 097, 098, 102, 105, 109` (occurrence counts in that order: 5, 4, 2, 8, 9, 9, 4, 6, 4, 20, 2, 18, 1, 8). Enrolments, batches, sessions, content, assessments, attendance and topic progress all point at it. "Drop the version tables, courses stay" therefore needs a decision on where modules and topics live (Q1) before the migration is written.

---

# 7. Shared screens

Components used by more than one role, today and as a fixed per-role config (**Proposal**; nothing implemented). Rule from the plan: no `hasRole` inside; the route passes the config.

Legend: Y = on, N = off, `-` = role does not use the component.

## 7.1 Notification centre (`features/shared/notification-centre.tsx:89`)

| Option | Student | Trainer | Branch Manager | Super Admin | Founder |
|---|---|---|---|---|---|
| Route | `/notifications` | `/trainer/notifications` | `/branch/notifications` | `/admin/notifications` | none today (Q10) |
| `showSystemIssuesTab` (today `hasRole("SUPER_ADMIN")`, `:90-91`) | N | N | N | Y | N |
| `title` | translated | "Notifications" | "Notifications" | "Notifications" | - |

## 7.2 Staff profile (`features/shared/staff-profile.tsx:12`, `/account/profile`)

| Option | Trainer | Branch Manager | Super Admin | Founder |
|---|---|---|---|---|
| `role` label | from session | from session | from session | from session |
| `branchLabel` | its branch | its (picked) branch | "All branches" | "All branches" |
| Today | union of all scopes (`:29-32`) | same | same | same |

Frames inside the shell of "the workspace the user lands in" (`access.ts:63-66`), which stays valid with one role.

## 7.3 Academic calendar (two implementations: `features/admin/calendar.tsx:201` and `features/shared/academic-calendar.tsx:39`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Surface | Section of Schedule & calendar | `/admin/calendar` | `/founder/calendar` (Proposal, Q6) |
| `canAddCompanyHoliday` | N | Y | Y (today `central`) |
| `canProposeBranchClosure` | Y (own branch) | Y (any branch, direct) | N |
| `canDecideClosure` | Y (today `approver`, `shared/academic-calendar.tsx:43`) | Y (`calendar.tsx:208,284`) | N |
| `canEditOrCancel` | N | Y | company holidays only (Q8) |
| `branchScope` | own branch | any | any |
| `view` | list | month and list | month and list |

Today the Branch Manager can decide a closure that the same person proposed. See Q8.

## 7.4 Issues list (`features/branch/issues.tsx:175`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| `canNote` | Y | Y | N (the API says via `issue.can_note`, `:134`) |
| `canAssign` | N | Y (today `:8`) | N |
| `branchScoped` | Y (branch pick) | N (all) | N (all) |
| `goFix` target | `/branch/*` | read-only drill-down or removed (Q5) | read-only drill-down |

## 7.5 Support desk (`features/shared/support-desk.tsx:100`)

| Option | Trainer | Branch Manager | Super Admin (Q5) |
|---|---|---|---|
| `simple` | Y (`trainer/support.tsx:22`) | N | N |
| `views` (tabs with counts) | N | Y (`branch/support.tsx:56`) | Y |
| `base.mine` | Y | N | N |
| `branchId` | - | picked branch | any |
| `canReassign` (today `profile.scopes.some(BM, SA, FOUNDER)`, `support-desk.tsx:444`) | N | Y | Y |
| `canEscalate` | Y | N | N |

## 7.6 Batch page parts and operations (`features/academic/batch-panel.tsx`, `batch-operations.tsx`, `features/branch/batch-page.tsx`)

| Option | Branch Manager | Super Admin (Q5) | Founder (Q6) |
|---|---|---|---|
| `manage` (today `useCanManage`) | Y | N | N |
| `approve` (today `useIsManager`, overrides and decisions) | Y | N | N |
| `branchScope` | picked branch | all | all |

Replaces `useCanManage()` / `useIsManager()` in: `branch/batches.tsx:35`, `class-day.tsx:67`, `waiting.tsx:148`, `payment-instructions.tsx:15`, `batch-page.tsx:99,160,198`, `schedule.tsx:44,291`, `new-class.tsx:46`, `class-actions.tsx:73-74`, `batch-dialogs.tsx:154`, `academic/class-operations.tsx:35,183,276-278,380-381`, `academic/batch-operations.tsx:41-42,947-948`, `academic/batch-panel.tsx` (props), `shared/sessions.tsx:26`.

## 7.7 Class sessions table and requests (`features/shared/sessions.tsx`)

| Option | Trainer | Branch Manager |
|---|---|---|
| `actions.manager` | N (`trainer/sessions.tsx:29`) | Y (Branch has its own `ClassActions`, `class-actions.tsx:63`) |
| `actions.trainer` | Y | N |
| `RequestsPanel.manager` | N (`:40`) | Y (decisions are in `schedule.tsx` `NeedsDecision`) |

## 7.8 Certificate and completion decisions (`shared/certificate-register.tsx:183`, `founder/panel-certificate.tsx`)

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Surface | collapsed section in `/branch/completion` | Approvals page (Q5) | `/founder/certificates` |
| Decides | change requests and fee releases it may (API: "independent approver") | same | requests, fee exceptions |
| `kinds` | certificate | certificate, fee_exception | certificate, fee_exception |

Two UIs for the same decision today (`CertificateDecisions` table and the Founder's `InboxList` panels).

## 7.9 Question bank (`features/trainer/question-bank.tsx:242`)

| Option | Trainer | Branch Manager |
|---|---|---|
| `canApprove` | N | Y (`branch/content.tsx:216`) |
| Can write | Y (`:256`) | N |
| Location | `features/trainer/` imported by `features/branch/content.tsx:11` | move to `features/shared` |

## 7.10 AI controls (`features/admin/ai-controls.tsx:168`)

| Option | Super Admin | Founder |
|---|---|---|
| Route | `/admin/ai-controls` | `/founder/ai-controls` |
| Config | none; identical page | none; identical page |
| `can_switch` | API | API |

## 7.11 Assistant (`features/shared/assistant.tsx:46`)

| Option | Student | Trainer |
|---|---|---|
| `variant` | student | trainer |
| Offer "send to a person" | Y (`:325`) | N |
| Sources open at | student pages | `/trainer/*` (`:410-419`) |

Backend audience uses the union (`backend/services/ask_nipuna.py:95`).

## 7.12 Needs-you / dashboard building blocks

`components/lms/needs-you-list.tsx` (Trainer Today, Branch My work, Admin Home, Founder inbox via `founder/inbox-list.tsx`), `features/shared/dashboard-parts.tsx` (`Tile`, `CrmTile`, `QuickLinks`: Branch, Founder, academic), `components/lms/getting-started.tsx:28` (Student, Trainer, Branch, Admin; none for Founder). Role-neutral. `GettingStartedCard` and `useNavCounts` take a `workspace` argument (`getting-started.tsx:34`, `app-shell.tsx:86`) that the plan turns into the session role (R3).

## 7.13 Reports

| Option | Branch Manager | Super Admin | Founder |
|---|---|---|---|
| Component | `features/branch/reports.tsx:57` | same, with branch filter (Q8) | same (Q8) |
| `branchScope` | picked branch | all / one | all / one |
| API | `GET /branch/reports` (BM, SA) | same | `GET /academic/reports` exists, no screen |

## 7.14 App shell and palette

| Item | Today | Fixed config per role |
|---|---|---|
| Header label | "Acting as" menu or label (`app-shell.tsx:115-121`) | static `Role · Branch` (R4) |
| Bell route | `NOTIFICATIONS[workspace]` (`:26-31`) | one route per role |
| Account menu link | student `/my-account`, others `/account/profile` (`:146-158`) | same, from the role |
| Command palette pages and record targets | all held workspaces, `recordTarget` by workspace (`command-palette.tsx:15-20,46-52`) | one nav list, record links per role (Founder student = founder page, not `/admin/students`) |
| Mobile bar | `MOBILE_BAR` for 3 roles (`access.ts:177`) | explicit list for every role |

## 7.15 Cross-feature imports to move into `features/shared` (R5)

| Import | File:line |
|---|---|
| `founder/*` imports `branch/attendance-url`, `branch/attendance-pager` | `founder/access.tsx:8-9`, `founder/inbox-list.tsx:5` |
| `branch/content` imports `trainer/question-bank` | `branch/content.tsx:11` |
| `branch/issues` imports `admin/issue-assign`; `admin/issues` imports `branch/issues` | `branch/issues.tsx:17`, `admin/issues.tsx:4` |
| `shared/academic-calendar` imports `admin/shared` `Pager` | `shared/academic-calendar.tsx:13` |
| `branch/*` imports `academic/*` (batch panel, class operations, timetable, curriculum model) | `branch/batch-page.tsx:11-12`, `class-day.tsx:11`, `new-batch-wizard.tsx:13`, `waiting.tsx:14` |
| `trainer/class-flow` imports `trainer/attendance` `RegisterForm` | `class-flow.tsx:19` (same role, fine) |
| `features/academic/` directory is left over from the Academic Coordinator role (merged into Branch Manager) | whole directory |

## 7.16 Backend code that depends on the union of roles (input for R3)

| Place | Evidence |
|---|---|
| `require_roles` and `has_role` use any scope | `backend/routes/decorators.py:32-45`, `backend/services/context.py:50-56` |
| Scope helpers | `backend/services/scope.py:23-44` (`visible_branch_ids`, `trainer_batch_ids`) |
| Workspaces and home | `backend/services/auth.py:25-39,185-192` |
| `/me/nav-counts`, `/me/getting-started` take `workspace` | `backend/services/nav.py:31-36,111-122,166-176` |
| Support trainer flag, `my_requests` wording, Ask Nipuna audience, delivery access | `backend/services/support.py:56,63,71,125,141,241`, `my_requests.py:88`, `ask_nipuna.py:95`, `delivery_access.py:22` |
| Frontend union readers | `shared/delivery-ui.tsx:16-18,59-61`, `auth/auth.tsx:77,85`, `admin/format.ts:20-22`, `shared/support-desk.tsx:444`, `shared/staff-profile.tsx:29-32`, `components/lms/app-shell.tsx:80-82` |

---

# 8. Open questions

Each has 2 to 4 options; the first is the recommendation. No answer is assumed anywhere above.

**Q1. After curriculum versions are removed, where do a course's modules and topics live?** (Students, trainers, sessions, assessments and topic progress hang off `curriculum_version_id` today.)
1. (Recommended) On the course itself: one outline per course; the Super Admin edits it and every batch follows it.
2. Frozen per batch: a batch copies the course outline when it is created and does not change afterwards.
3. Keep one hidden "current version" per course in the database and hide versions in the UI.

**Q2. What can the Super Admin edit on a course, given the CRM owns course code, title, category, status and combo tracks (`CourseUpserted`)?**
1. (Recommended) Only LMS-owned content: modules, topics and their details. Code, title, category, status and tracks stay read-only, from the CRM.
2. Also the title and status, and the CRM stops being the owner of those fields (needs a CRM change).
3. Nothing in the screen: the outline is loaded by import; Courses is read-only for everyone.

**Q3. Which parts of today's curriculum model survive on a course?** (hours, completion rules, required assessments, combo track pins, equivalence rules, library of reusable modules, branch variations, "mapping" helper in Waiting for a batch)
1. (Recommended) Keep completion rules, hours and required assessments on the course (the completion pipeline needs them); drop library, variations, equivalence and the mapping helper.
2. Keep only modules and topics; completion uses fixed rules.
3. Keep everything and move it onto the course page.

**Q4. When the Super Admin changes the outline of a course that has running batches, what happens?**
1. (Recommended) Change applies at once; Branch Managers of affected branches are notified; audited.
2. Block edits while a batch of that course is running.
3. Change applies only to batches created afterwards (needs Q1 option 2).

**Q5. What does a Super Admin keep of the Branch Manager's work now that the Branch workspace is gone?**
1. (Recommended) A cross-branch read-only view (Batches, Students, Support, Reports, with a branch filter) plus the decisions the backend reserves for "Founder or Super Admin" (fee exceptions, extensions beyond limit, a Branch Manager's own requests, AI budget) on an Approvals page; no daily class or batch actions.
2. Full branch actions inside `/admin/*` (a copy of the Branch Manager screens with an "all branches" filter and a branch to act on).
3. Nothing: a Branch Manager account covers branch work; the Super Admin only does people, setup, issues and calendar.

**Q6. What does the Founder keep outside the inbox, now that Admin and Branch are not implicit?**
1. (Recommended) Read-only company views inside `/founder`: Students, Batches, Issues, Reports and Audit log, with a branch filter, plus Calendar for company holidays.
2. Only Home, Approvals, AI controls and drill-downs from the tiles.
3. The same read-only pages as today (Users, Setup, CRM sync, Audit included) moved under `/founder`.

**Q7. A Branch Manager with several branches picks a branch at sign-in. Is "all my branches" still a choice?** (Today the picker offers "All branches".)
1. (Recommended) No: exactly one branch per session; to see another, sign in again or "Change branch".
2. Yes: the picker also has "All my branches" (read and act across them).
3. Yes for reading (Reports, Issues), single branch for everything else.

**Q8. Who approves a branch closure, and who edits company holidays?** (Today a Branch Manager can both propose and approve; the Founder and Super Admin add company holidays; only Super Admin edits or cancels.)
1. (Recommended) Branch Manager proposes; Super Admin approves; Founder and Super Admin add company holidays; Founder edits only company holidays.
2. Branch Manager proposes and approves for own branch (as today); Super Admin and Founder add company holidays.
3. Only Super Admin adds, edits, cancels and approves everything; Founder reads.

**Q9. Does the Trainer get a Courses view?**
1. (Recommended) No nav item; a read-only "Course outline" block on the trainer batch page.
2. A Trainer nav item "Courses", read-only.
3. No outline for trainers beyond the topic pickers.

**Q10. Does the Founder get a bell and a notification inbox?** (Today none: "nothing is sent to the founder".)
1. (Recommended) Yes: decisions waiting (the nav counts already exist) shown as a bell and an inbox page.
2. No: Home and nav badges only.

**Q11. Staff screens for Career and placements (opportunities, CV review, applications, placement outcomes): in scope for this project?** (The API exists for Branch Manager, Super Admin and Founder; no staff screen exists, so a student's "CV reviewed" step cannot be completed from the UI.)
1. (Recommended) Out of scope here; record in `docs/GAPS.md`; decide owner (Branch Manager) later.
2. Add a Branch Manager "Career" screen in R7.
3. Add it to the Super Admin workspace instead.

**Q12. Super Admin "Go fix it" on Issues (`/admin/issues`) today opens Branch Manager screens. Under Q5 option 1 or 3, what should it do?**
1. (Recommended) Open a read-only detail of the record under `/admin/*`, with Assign as the action.
2. Hide Go fix it for the Super Admin; Assign only.
3. Keep opening the branch screens (needs a Branch Manager account to act).

**Q13. Is there a screen where the Super Admin hands out the migrated accounts (R2), and who may see the list?**
1. (Recommended) A one-time hand-out page in Users & access, Super Admin only, with a download.
2. A CSV produced by the migration command, no screen.
3. Email the new credentials directly to each person.

**Q14. Landing order for a user with several roles during R2 (plan proposes Founder > Super Admin > Branch Manager > Trainer > Student): confirm.**
1. (Recommended) As proposed.
2. Lowest operational role first (Student > Trainer > Branch Manager > Super Admin > Founder).
3. Per person, chosen by the Super Admin in the hand-out list.

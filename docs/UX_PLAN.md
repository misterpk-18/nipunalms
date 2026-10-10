# UX plan: every LMS screen tells you what to do next

## Context

**The goal (owner, 10 Oct 2026):** "I don't want to remember how to do a certain thing. By looking at the UI I should
figure out what to do next."

**How the problems were found.**
- Seven parallel code audits covered every route in all six workspaces:
  - Student (two audits)
  - Trainer
  - Academic Coordinator
  - Branch Manager + Founder
  - Super Admin
  - Shell, auth and design system
- Screenshots of 35 screens, one set per role, were taken on temporary servers.
- The owner then answered follow-up questions for each section.

**What the audits found, in short:**
- **No "what needs me" view anywhere.** Homes are stat tiles, half of which aren't links. Decision queues sit at the bottom of long pages.
- **Long flat navs:**
  - Student 17 items, Academic 15, Trainer 13.
  - Overlapping screens:
    - Progress / Attendance / Results
    - Exceptions / Recording Exceptions / Meet Operations
    - Completion / Certificates
    - Reviews / Grading queue / Assignments
  - The same job is done in different places. A trainer can run a class from Today, Sessions or Attendance, and the data saved differs.
- **Internal spec language on screen:**
  - "Curriculum Mapping Pending", "Pending Verification", "Actual Class Session", "Module 25 ordering", "CRM authoritative", "Outbox", "Recovery Owner".
  - Status badges guess their colour from the text, and notes print the state name first ("Empty:", "Saved: Saved.").
- **Unsafe single clicks.** Publish results, Release, Issue certificate, Remove module and Discard draft all happen in one click. Decision dialogs default to "Approved" or "Complete".
- **Dead ends:**
  - Topic page, trainer Batches and Students, Results, Certificates and Fees offer no next step.
  - Hidden flows: batch setup order, curriculum submit requirements, assessments workflow.
- **Visual:**
  - Text loading lines instead of skeletons.
  - The sidebar background stops at the first screen height.
  - Founder nav highlights two items at once (`WORKSPACE_ROOTS` misses `/founder`).
  - The CRM tiles show "Unavailable" above the fold.

**Not a UI bug.** The red "could not be loaded" cards on :5060 come from the API process started on 4 Oct with no reloader. It still runs code from before migrations 102–104, so `/me/schedule`, `/me/recordings` and `/me/progress` return 500. The same endpoints return 200 on current code. Restart the :5060 API.

**CRM context taken into account** (from `nipuna crm-docs/`):
- **Round 5 (curriculum removal).** The CRM keeps no curriculum, and it deleted its Academic Coordinator role, moving batches, allocation, completion and certificates to the Branch Manager. Joint tests T1–T5 passed.
- **Dev database.** Never rebuild `nipunalms-dev` without telling the CRM, because LMS student codes would collide with the stale ones it holds.
- **WhatsApp.** The CRM sends through Pinbot on one number for both branches, using approved templates only. Callbacks and replies go to the CRM.

## Decisions taken with the owner (10 Oct 2026)

### Whole app
| Topic | Decision |
|---|---|
| Navigation | Merge overlapping screens, then group what's left under headings (lists per role in the phases) |
| Multi-role users | Always-visible **"Acting as: <role> ▾"** switcher in the header, with a one-line description per role and a branch picker where branch matters. The cross-workspace items leave the sidebars |
| Next step | Every role's home starts with a **"Needs you"** list (counts plus a button per item). **Count badges** on nav items. **Empty states** say why and offer the next action |
| Search | **Ctrl/Cmd+K**: pages plus records (students, batches, certificates), limited to what the role can see |
| Wording | **Plain words** per role. No spec or module references. Policy text moves into a collapsible **"How this works"** |
| Statuses | **One status dictionary**: fixed colour, plain label and a one-line "what it means / what to do" per status. No "Empty:" / "Saved:" prefixes |
| Confirmations | Every action that can't be undone, or that students will see, opens a short confirm stating the **consequence** ("Publish 12 results? Students will see their marks now.") |
| Visual | **Loading skeletons**; **toasts with a "View" link** and the next step; **dark mode** (follows the system setting) |
| Not chosen | A blanket "every disabled button explains why" rule (applied only where a screen decision says so). Forced identical page widths and headers |

### Curriculum and roles (backend)
| Topic | Decision |
|---|---|
| "Curriculum Mapping Pending" | **Removed entirely.** A new enrolment is always allocatable. A batch with no approved curriculum shows "No approved curriculum yet", and classes can be scheduled without topics. When a version is activated, the batch and its students pick it up |
| Version match | **Dropped.** A student follows the curriculum version of the batch they're in (same as the CRM) |
| Academic Coordinator | **Merged into Branch Manager**, like the CRM |
| Former two-step approvals | The Branch Manager decides alone. Risky ones (confirm a batch with warnings, schedule clash override) need a **reason that is audited** |
| Independent reviewer | The Branch Manager reviews trainers' corrections and requests. A Branch Manager's own requests go to the **Founder / Super Admin** |
| Existing coordinator accounts | **Deactivated** (as in the CRM). Their open items move to the branch's Branch Managers |
| Round 5 | **Closed out first**: `CRM_INTEGRATION.md` §5 row, delete the round's files in `nipuna crm-docs/` (git keeps them), own commit |

### Sign-in and accounts
| Topic | Decision |
|---|---|
| Forgot password | **Self-service reset code** by WhatsApp (email fallback), template `nipuna_lms_password_reset_code_auth_v1` |
| Login page | **One clean form** for everyone ("Student ID or email"), plus a "First time here? Activate your account" link. The activation steps leave the login page |
| After activation | **Signed in automatically**, landing on Home with the Getting started card |
| Onboarding | A dismissible **"Getting started" checklist card** on each role's home, ticking itself as steps are done |
| Activation links (CRM D1) | **The LMS sends them** by WhatsApp ("Send new link" on Student Accounts); copy-link stays as a fallback |
| Staff credentials | New staff get an **activation link** (WhatsApp/email) instead of a spoken temporary password. The temporary password is a fallback |

### WhatsApp
| Topic | Decision |
|---|---|
| Path (CRM W4) | **Through the CRM's sending endpoint**: one outbox, one switch, one test-number list. Delivery status comes back free (W3) |
| Messages the LMS sends (W1) | Reset code and activation links (student and staff); class reminder, cancelled and moved; result published; certificate issued; batch change needing agreement |
| Drafts | [whatsapp-templates/](whatsapp-templates/README.md). Nine templates for the owner to submit in Pinbot (replace `LMS_HOST` first) |

### Student
| Screen | Decision |
|---|---|
| Nav | Home · My Learning · Schedule · Tasks & Tests · Class Materials · My Progress · Certificates · Career · Ask Nipuna · Support. Bell for notifications. Avatar menu holds **My Account** (Profile + Fees & Receipts), Change password and Sign out |
| Home | One **"Up next"** hero (live class → work due today → continue topic) with one button, then Due work, Continue learning, Latest recording and Attendance. Career, Support, Ask Nipuna and Certificate leave Home. A pending **batch change** shows as a Home banner with Agree / Decline and a reply-by date. Preferred slot shows only when the student has no batch |
| My Learning | Each course card has **"Continue: <topic>"** and progress. The course page shows modules and topics first; enrolment and CRM details go in a collapsed "Course info" |
| Topic page | **Topic hub**: class session(s), recording, materials, assignment or test, and **Next topic →** |
| Topic completion | **Automatic**: done when attended (or recording watched) and any required work submitted. Ticks and % on modules |
| Schedule | Grouped **Today / Tomorrow / This week** with plain states (Live now, Starts 10:00, Link not ready, Cancelled). A **Past** tab shows attendance and the recording link |
| Join button | "Starts in 2 h" countdown; the button appears 15 min before and is highlighted when live |
| Tasks & Tests | **One screen** for assignments and tests: To do (due, overdue, resubmit) · Waiting for review · Done, with counts and overdue first. The assignment page leads with the brief and a Submit button near the top. A timed test confirms first ("30 min, can't be paused"); submit warns about unanswered questions; the attempt has a question navigator |
| Class Materials | Recordings + Resources merged: Recordings / Files tabs, grouped by course → week or topic. Access is one line ("Available until 12 Jan 2027 · Request extension"); the rules sit in "How access works" |
| My Progress | Progress + Attendance + Results merged: Overview (with **"What to do next"**) · Attendance · Results. Result rows open the test or assignment with feedback |
| Attendance rows | **Request recovery** only on Absent rows; **Report a mistake** in a row menu. The row then shows the request status and who decides |
| Certificates | One card per course with a 3-step tracker (Course completed → Review → Issued) and the blocker in plain words, including unpaid fees with a link to Fees. Issued: **Download PDF** and **Copy verification link** |
| Career | **4-step checklist** on top (Opt in → Profile → CV reviewed → Share with employers). Apply is disabled with "Needs: …" and a link. The disclaimer becomes a small note near Jobs |
| Ask Nipuna | **Chat thread**: input pinned at the bottom, quick actions pre-fill the box, sources become links, quota shown only near the limit. "Can't answer" offers to raise a support request with the question |
| Support | Requests waiting on the student float to the top with a badge; a new request opens right after submitting. **Guided form**: subject, help per category, attachment. (Hiding SLA badges and dead-end "Get help" links were not chosen) |
| Notifications | **Inbox: New / Needs action / Done**, one status and one button per item. Opens on Needs action. Every item links to its subject. The bell has a preview dropdown. The sidebar item is removed. Preferences move to My Account, hiding channels that aren't live (all roles) |
| Fees | **"Next payment"** card (date, amount, overdue in red, how and where to pay); **receipt PDFs** |
| Profile | The student can **add or change their email** (needed for reset); other fields say "Contact your branch" |
| Telugu | **Every student screen fully translated**, including statuses and detail pages. Staff stay English |

### Trainer
| Screen | Decision |
|---|---|
| Nav | TEACH: Today, Sessions, Attendance · GRADE: To grade, Assignments, Assessments, Content · PEOPLE: Batches, Students, Support · INSIGHTS: Reports, Ask Nipuna. Phone bar: Today, Sessions, To grade, Students |
| Running a class | **Today's guided flow is the only way.** It records the full class log (outcome, actual times, topics, attendance, notes). Sessions becomes the schedule plus reschedule requests, with "Run class" opening the same flow |
| Today | A **"Next up"** class expanded; the others compact, finished ones collapsed. A **to-do list** below (assignments to review, test attempts to mark, missing class logs), each with a button. An empty day shows tomorrow |
| No Meet link | A one-click **"Ask Branch Manager"** flag for that class; the trainer can continue the flow |
| My requests | A list of the trainer's reschedule and correction requests with status, decider and reason, plus a notification on each decision |
| To grade | **One inbox** for assignment submissions and test attempts, oldest or overdue first, filter by batch. A focused grading screen with **Save & next**. Starting a review is explicit (not triggered by focusing the box) |
| Assessments | Tabs in workflow order: Question bank → Tests → Interviews, with counts and a one-line hint each. "New mock interview" button. Drafts are editable. Release and Close ask for confirmation |
| Batches / Students | Each opens a **batch page** (sessions, roster, content, assignments, progress) or a **student page** (attendance, submissions, results, flags, "Flag this student"). Students get search and a batch filter |
| Content | **"Save & submit for review"** is the primary button (Save draft is secondary). "Changes requested" rows show the reviewer's comment. Filter by batch and status |
| Attendance | Becomes the **"Unmarked & corrections"** list: classes still to mark, corrections pending, recoveries to verify. Each opens the same register as Today, with a sticky Save bar |
| Reports | **Students at risk** per batch (attendance, missing or late work, unmarked classes, overdue reviews), each linked to where to act. Averages shrink to a summary |
| Support | **Simple trainer view**: raise, reply, status and owner. Escalate and reassign sit under "More". The duplicate table is removed. Flag from a student row |

### Branch Manager (merged workspace)
| Screen | Decision |
|---|---|
| Nav | TODAY: My work, Class day · BATCHES & STUDENTS: Batches, Waiting for a batch, Schedule & calendar, Attendance & progress · TEACHING: Curriculum, Content & questions, Marks & results · COMPLETION: Completion & certificates · HELP: Student support, Issues · Reports. Bell for notifications |
| Home | **"My work today"** list in priority order: students waiting for a batch, reschedule and extra-class requests, results to publish, content to review, recovery and correction requests, support near its deadline, classes at risk today. Each item has a button. Branch picker for multi-branch users |
| Batches | A **batch page with a step bar** (Created → Trainer → Ready → Confirmed → Students → Classes); the next action is the main button. Readiness problems show before Confirm. Creation is a short **wizard** (Course → Mode, dates and timetable → Trainer) |
| Class generation | A one-click **"Create classes"** from the batch timetable, with a preview that skips holidays. "New class" pre-fills from the batch |
| Allocation | A **"Waiting for a batch"** screen with a count. Each student shows the matching batches (same course and branch, seats left) and one-click Allocate. The batch page has "Add students from waiting list" |
| Curriculum | **Submit checklist** (Modules → Topic details → Hours → Completion rules → Required assessments → Submit) with incomplete topics marked. **Auto version names** (new drafts copy the Active version). **Drag to reorder** and **searchable prerequisites**. Library, rules and variations stay on the page (an "Advanced" sub-page was not chosen) |
| Schedule | A **week calendar** (by batch or trainer) with a list toggle. A **"Needs decision"** strip on top (reschedule and extra-class requests) with a count. Row actions become one primary action plus a menu. Technical IDs move under "Advanced" |
| Issues + Class day | Exceptions + Recording exceptions become one **Issues** inbox (filters: type, age, owner), with **"Go fix it"** as the main action and "Add note" secondary. Meet Operations becomes **Class day**: today's classes, tiles filter the list, the Meet link is set right there. Admin-only integration checks leave it |
| Recordings | Two actions: **Release** (with confirm) or **Report a problem** with a reason (processing, partial, unavailable, on hold). Pick the class by date and batch. The Drive file id gets a "where to find it" hint until Drive is connected |
| Completion & certificates | **One page with pipeline tabs** and counts: Ready to decide → Completed → Waiting for fee → Ready to issue → Issued. Evidence is shown against the course's thresholds (✓/✗). Decisions have no default and a confirm. Correction and revocation go under "More" |
| Marks & results | Renamed. Each gap says who must fix it. Publish asks first ("Publish 12 results? 3 still unreviewed") and works from inside the review. Question approval moves to Content & questions |
| Content & questions | One **Review** opens the preview with the decision: **Approve & release** (primary), Approve and release later, Request changes (comment required). Opening it claims it. Tabs show counts. Questions to approve live here |
| Attendance & progress | Tabs with counts: Students (at-risk first, "show all" toggle, the row opens the student) · Recovery requests · Corrections. Approve and reject confirm with the consequence |
| Access extensions | **The Branch Manager recommends, the Founder decides**, for requests beyond the Branch Manager's limit. Within the limit the Branch Manager decides; approval shows the new end date and that the student will be told |
| Student support (staff) | Opens on **Needs action**, nearest reply deadline first. New student replies are marked. Requests past their deadline appear on My work and as a nav badge |
| Reports | **Drill-down** links behind every figure, a **period filter** (default this month), **CSV/Excel export**, **trends** over time |

### Founder
| Screen | Decision |
|---|---|
| Home | A **single Founder inbox** for everything waiting on the Founder: curriculum approvals, certificate decisions, fee exceptions, access extensions beyond the limit (with the Branch Manager's recommendation), the AI budget, and Branch Managers' own requests. Each item opens inside the Founder workspace. CRM-dependent tiles are hidden until the CRM is connected |
| Approvals | Review opens a **side panel** with a "what changes / who's affected" summary and a sticky **Approve / Return** bar; Return needs a reason. Curriculum gets **"Approve & activate"** in one step with an optional activation date. Certificate decisions get **two buttons, no default**, plus a consequence line. (A recent-decisions history was not chosen) |

### Super Admin
| Screen | Decision |
|---|---|
| Nav | PEOPLE: Users & access, Student accounts · OPERATIONS: Issues (read and assign), Academic calendar, CRM sync · SYSTEM: Setup & health, AI controls, Audit log |
| Home | A **"Needs action"** list (failed CRM events → Retry, unowned issues, locked users, pending closures) plus quick actions (Add staff user). Pre-go-live integration status becomes a **"Setup checklist"** card that disappears when done |
| Setup & health | Integration Readiness and Security Readiness merged into one checklist with plain states (Not set up / Set up / Working / Broken) and an owner picked from staff |
| AI controls | Its own page, with a clear ON/OFF per audience. **The Super Admin and the Founder can both switch it off and restore it** company-wide |
| CRM Sync | Opens on **Needs attention** (failed first, each with a one-line plain cause and Retry). The event view shows a plain summary, with the raw JSON under "Technical details". (Bulk retry and renaming the outbox were not chosen) |
| Users & access | **Role descriptions** in the picker, a visible **Unlock** action with a reason, **activation-link invites** (see Sign-in). (Several roles at creation was not chosen) |
| Student accounts | A **"Suggested next step"** per student with the main button ("Link expired → Send new link"; the LMS sends it by WhatsApp). The student opens as its own page, not a modal |
| Calendar | **Month grid** with a list toggle, upcoming first. A primary "Add holiday / closure" button whose fields change with the kind; the To date can't be before From. **Edit and cancel** show the impact first ("affects 6 classes"). (Weekly offs and auto-approved admin closures were not chosen) |
| Audit log | **Plain sentences** with links to the person or record, preset filters (Accounts, Roles, Integrations), a "Last 7 days" quick range and CSV export. The raw diff sits under "Details" |

## Progress (10 Oct 2026)

| Phase | Status | Commit | Size |
|---|---|---|---|
| U0. Close CRM round 5 | **Done** | `1193fb3`, `31ceee5` | S |
| U1. Remove Curriculum Mapping Pending | **Done** (db 105) | `51824f0` | M |
| U2. Merge Academic Coordinator into Branch Manager | **Done** (db 106) | `9469df1` | L |
| U3. Design system foundation | **Done** | `b3bee1f` | M |
| U4. Shell, navigation, search, counts | **Done** | `af7c16a` | M |
| U5. Notifications inbox (all roles) | **Done** | `fd464dd` | S |
| U6. WhatsApp through the CRM (CRM round 6) | **Built, switched off** (db 107) | `ea2a1ea` | M |
| U7. Sign-in and accounts | **Built, WhatsApp switched off** (db 108) | `20af964` | M |
| U8. Student: Home and My Learning | **Done** (db 109) | `42451ba` | L |
| U9. Student: Schedule, Tasks & Tests | **Done** | `c902a9a` | M |
| U10. Student: Class Materials, My Progress, Certificates | To do | | L |
| U11. Student: Career, Ask Nipuna, Support, My Account | To do | | M |
| U12. Trainer: Today, class delivery, Attendance, My requests | To do | | M |
| U13. Trainer: To grade, Assessments, Batches/Students, Content, Reports, Support | To do | | L |
| U14. Branch: My work, Batches, Waiting for a batch, Schedule, Class day | To do | | L |
| U15. Branch: Curriculum, Content & questions, Marks, Attendance, Completion & certificates, Issues, Recordings, Support, Extensions, Reports | To do | | L |
| U16. Founder | To do | | S |
| U17. Super Admin | To do | | M |
| U18. Final sweep, then resume gap-fix phase 7 | To do | | S |

**Order matters:**
- **Backend first.** U0–U2 change roles and rules that every later screen depends on.
- **Shared parts next.** U3–U5 build the shared components the screen phases reuse.
- **Messaging before sign-in.** U6 has to come before U7, because the reset code and the links need the sending path.
- **Migrations.** `db/105` is U1, `db/106` is U2, `db/107` is U6, `db/108` is U7, `db/109` is U8 and `db/110` is the WhatsApp status events (CRM round 6 reply) (U4 and U5 need none). Later phases take the next free number and record it here. Gap-fix phase 7 then starts after the last UX migration (see [GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)).

## Resuming in a new session

1. **Read before starting a phase:**
   - This file's Decisions (they are final; don't re-ask).
   - The phase section below.
   - For U6, `nipuna crm-docs/CRM_WHATSAPP_CONNECTION.md` and [whatsapp-templates/](whatsapp-templates/README.md).
2. **Build** in the GAP_FIX_PLAN order: migration, models, services, controllers, routes, tests, frontend, docs. Use the shared components from U3 on every screen; don't create per-screen copies.
3. **Check:**
   - Full backend suite (background).
   - `npx tsc --noEmit -p .`.
   - The jargon check (Conventions below).
   - Playwright for the touched screens on **temporary servers** :5061 / :5175, desktop and mobile projects. Never restart the owner's :5060 / :5174.
   - Screenshots of the touched screens for each affected role.
4. **Dev database:** apply the new migration **in place** (`psql -d nipunalms-dev -f db/NNN_*.sql`) and run the seed only where it is idempotent. **Tell the CRM before any rebuild** of `nipunalms-dev`.
5. **Docs:**
   - `API.md`, `DATABASE.md`.
   - `DEVELOPMENT.md`: Part B screens table, staging accounts after U2, Part E.
   - `CRM_INTEGRATION.md` for U0, U2 and U6.
   - The progress table above.
6. **Commit:** one commit per phase on `main`, styled `UX phase N: …`, with **no co-author trailer**.

## Conventions every phase follows

- **Copy.**
  - Page description = what you can do here, in one line.
  - No module numbers, `§`, "CRM authoritative", "Actual Class Session", "Pending Verification", "readiness", "outbox" or raw enum or field names on screen.
  - Policy text goes in `<HowThisWorks>`.
  - Students see plain words through `t()` (EN/తెలుగు). Staff see plain English.
  - **Jargon check** before each commit: `grep -rnE "Module [0-9]+|§|Pending Verification|Actual Class Session|Mapping Pending|authoritative|[Oo]utbox|Recovery Owner" frontend/src/features frontend/src/routes frontend/src/components/lms` must show only comments.
- **Statuses.**
  - Every status shown goes through `statusInfo(domain, code)` from the U3 dictionary, which gives the label, tone and help.
  - No regex tones. `StatusBadge` shows the help as a tooltip.
- **Next step.**
  - Every list has an `EmptyState` with a reason and, where one exists, an action.
  - Every home lists "Needs you" items with deep links.
  - Every queue screen opens on what needs action, with counts on its tabs.
- **Safety.**
  - `ConfirmDialog` with a consequence line before any action that can't be undone or that students will see.
  - Decisions have no default choice.
  - Reject or return always asks for a reason.
- **Feedback.** Toasts say what happened and what happens next, and carry a "View" link to the changed item.
- **Layout.**
  - Detail views that users need to link to are pages with breadcrumbs, not modals.
  - `PageHead` sets `document.title`.
  - Skeletons while loading.
  - Works in light and dark mode and at phone width.

---

## U0. Close CRM round 5 (no migration)
- **What to commit.** The working tree already holds the round 5 work: `db/104`, backend, tests and docs.
- **Docs.** Add the round 5 row to `CRM_INTEGRATION.md` §5, with a link to the CRM's change list. Delete the round's files in `nipuna crm-docs/`: the request, `CRM_CURRICULUM_REMOVAL_CHANGES.md` and the joint test results.
- **Keep.** `CRM_WHATSAPP_CONNECTION.md` stays until U6 answers it.
- **Gap-fix plan.** Fix the date-dependent test `test_academic_calendar.py::test_review_targets_count_working_days_by_kind`, which uses a fixed Monday.
- **Commit:** `CRM round 5: curriculum removal`.
- **Owner action.** Restart the :5060 API so it runs current code.

## U1. Remove Curriculum Mapping Pending (`db/105`)
- **Backend:**
  - Drop the state from the enrolment status enum and from the exception queue source. Convert existing enrolments in place: move each one to Allocation Pending and close its exception rows with a note.
  - `_map_curriculum` (`services/crm.py`) stops blocking. With no Active version, the enrolment gets none and is allocatable.
  - In `batch_allocations`, remove the "Curriculum mapping / version" block and the version-match check. A student follows the batch's version.
  - Batches may have no version: creation and confirmation warn rather than refuse. Scheduling allows classes without topics.
  - Activating a version (`curriculum.activate`) attaches it to that course's batches that have none, and to their students.
- **Touches:**
  - Services: `services/academic_mappings.py` (the Mapping Pending owner), `allocations.py`, `batches.py`, `my_courses.py`, `dashboards.py`.
  - Other backend: `repositories/catalog.py`, `models/enums.py`, `models/students.py`, `cli/seed.py` (NIT-CRS-052 becomes "no curriculum yet, allocatable").
  - `controllers/academic_records.py`.
- **Frontend.** Remove the badge and notes in the files that render it: student `my-courses`, `course-detail`, `track-detail`; academic `batches`, `batch-panel`, `curriculum`, `dashboard`; trainer `batches`. Show "No approved curriculum yet" on batches only.
- **CRM.** Nothing is needed: these admissions now leave "Waiting for batch" sooner. Mention it in the U6 round document.
- **Tests:**
  - Allocation with no Active version succeeds.
  - Activation picks up batches and students.
  - The mismatch no longer blocks.
  - Rewrite the mapping-pending tests.
  - Fix `e2e/dashboards-staff.spec.ts` "logs a recovery step".

## U2. Merge the Academic Coordinator into the Branch Manager (`db/106`)
- **Roles:**
  - Remove `ACADEMIC_COORDINATOR` from `services/context.py` tuples (`BRANCH_ROLES`, `ASSESSMENT_AUTHOR_ROLES`, `MODERATOR_ROLES` and the others).
  - Update the 26 backend files that check it: everything the coordinator could do becomes the Branch Manager's.
  - The migration deactivates coordinator-only users, ends their sessions and removes their role rows.
  - Open items owned by them move to the branch's Branch Managers: exceptions, support requests, review claims, recovery steps.
  - The role row is retired, not deleted, so history and audit stay readable.
- **Approvals:**
  - Former coordinator→Branch Manager two-step decisions become one Branch Manager step: batch confirm, replacement and extra classes, certificate recommend→approve, cover approve+verify, capacity and transfer.
  - Confirm-with-warnings and clash override need `override_reason` (audited).
  - `services/approvals.require_independent` stays. When the requester is a Branch Manager, the decider must be the Founder or a Super Admin (new rule in the same helper).
- **Completion:**
  - The Branch Manager decides.
  - The trainer's Complete recommendation is still required.
  - `completion_authorised_by_email` is now a Branch Manager email, which will match a CRM user.
- **Frontend:**
  - The `academic` workspace and `/academic/*` routes go away. Redirect `/academic/*` to the matching `/branch/*` route.
  - The Branch nav becomes the grouped list in Decisions. Screens are moved, not yet redesigned; U14 and U15 redesign them.
  - `WORKSPACE_LABELS`, `WORKSPACE_HOME`, mobile bar.
- **Seed and e2e:**
  - `coordinator.gnt` / `coordinator.vij` become deactivated examples. Their seeded actions are re-attributed to `bm.gnt` / `bm.vij`.
  - Update `e2e/helpers.ts` USERS and `DEVELOPMENT.md` staging accounts.
- **CRM.** Contract unchanged. Note it in the U6 round document: the LMS also merged; completion emails will now match.
- **Tests.** Rewrite role-matrix tests: coordinator cases become Branch Manager cases, plus the new "Branch Manager's own request goes to Founder" rule.
- **As built (10 Oct 2026).**
  - **One Branch Manager step** (no independence check, and the matching database constraints dropped): confirming a batch (warnings still need `override_reason`), replacement / remedial / extra classes, approving a certificate (it may be approved straight from Eligibility Review; the recommendation is recorded with it), capacity increases and transfers.
  - **Independent review kept** (`approvals.require_independent(..., requester=...)`): attendance corrections, academic mappings, curriculum variations, library versions, material changes, merges and splits, class guests, cover requests, certificate change requests. When the requester is a Branch Manager, only the Founder / CEO or a Super Admin may decide (`approvals.can_decide` hides the button; 422 otherwise). Opportunity and placement-outcome verification (database independence) is unchanged: the seed has the Super Admin verify the Branch Manager's opportunities.
  - **Frontend.** The `academic` workspace is gone. Its screens moved to `/branch/*` (`/branch/academic-reports` for the old Academic reports, `/branch` shows the Academic dashboard under the branch tiles); `/academic/*` redirects to the matching `/branch/*`. The Branch nav is grouped (Today · Batches & students · Teaching · Completion · Help · Reports); `NavItem.group` is new, U4 builds on it.
  - **Not done here (later phases).** The decide buttons of the independent-review screens do not yet hide for a Branch Manager's own requests (the API refuses with the reason); U15 redesigns them.

## U3. Design system foundation (frontend; no migration)
- **`lib/status.ts`.** The status dictionary, `{domain: {code: {label, tkey?, tone, help}}}`, covering every status the API returns: enrolment, batch, session, attendance, assignment, test, result, certificate, support, content, recording, notification, career, CV, slot, integration, CRM event. `StatusBadge` takes `domain` and `code`. Remove `toneFor`.
- **`StatusNote`.** No catalogue-key prefix. Tones: info, success, warning, danger.
- **New components in `components/lms/`:**
  - `EmptyState` (icon, reason, action)
  - `ConfirmDialog` (title, consequence, destructive style)
  - `HowThisWorks` (collapsible policy text)
  - `Skeleton` presets (cards, table, detail)
  - `Breadcrumbs` (shared, from `ui/breadcrumb`)
  - `NeedsYouList` (rows of what / where / age / button)
  - `StepBar` (setup steps with the next action)
- **Changes to existing pieces:**
  - `QueryView` uses skeletons and `EmptyState`.
  - `ReasonDialog` shows the minimum length and has a destructive variant.
  - `useApiMutation` toasts support `view: {to, label}` and a next-step line.
- **Dark mode.** A `.dark` token block in `styles.css`, following `prefers-color-scheme`. Check contrast for badges and the active nav.
- **Bugs.**
  - The sidebar background runs the full page height.
  - `WORKSPACE_ROOTS` includes `/founder`.
  - `PageHead` sets `document.title`.
- **Migrate the existing call sites** of `StatusBadge` and `StatusNote` (about 116 and 60), so U8–U17 start clean.
- **As built (10 Oct 2026).**
  - **Dictionary** `lib/status.ts`: 30 domains (the plan's list plus `work`, `seat`, `approval`, `exception`, `account`, `question`, `completion`, `figure`, `assistant`, `curriculum`, `meet`, `readiness`). `StatusBadge` takes `domain` and `code` (and `label` when the API sends a richer label); `toneFor` is gone. Anything that is only a label (a kind, a role, a count, a check result) is a `Tag` with an explicit tone. `StatusNote` takes `tone` (info / success / warning / danger), no "State:" prefix.
  - **Components** in `components/lms/`: `EmptyState`, `ConfirmDialog` (replaces `ConfirmAction`, states a consequence), `HowThisWorks`, `Breadcrumbs`, `NeedsYouList`, `StepBar`, `LoadingSkeleton` (in `ui.tsx`). `QueryView` shows skeletons and an `EmptyState`; `ReasonDialog` shows its minimum length and has a destructive variant; `useApiMutation` takes `next` and `view: {to, label}`.
  - **Dark mode** follows the system setting (`.dark` tokens in `styles.css`, applied in `main.tsx`). Contrast of the status pairs was set by token choice, not measured in a browser yet.
  - **Bugs fixed:** the sidebar background runs the full page height, `/founder` is a workspace root (one active item), `PageHead` sets `document.title`.
  - **Wording changed on screen** by the dictionary (plain labels): for example "Not Configured" is now "Not set up", "Pending Verification" "Waiting for a check", "Released" (a recording) "Available", "Submitted" (content) "Waiting for review", "Outbox" "Sent to the CRM". The e2e specs were updated to match.
  - **Jargon check** (`grep` of the plan) now shows only comments and code identifiers (`Outbox` component and type names, the `"Pending Verification"` code literal).
  - **Known failing e2e after U3 (not caused by it, all fixed-seed-date or order dependent):** `admin.spec.ts` "student accounts", `assessments.spec.ts` "student sees each assignment state", `attendance.spec.ts` "trainer marks a class", `delivery.spec.ts` "learner schedule". Serial specs mutate the database, so re-run them on a freshly seeded one.

## U4. Shell, navigation, search and counts (backend endpoints; no migration)
- **Grouped navs per role.** `NavItem` gets `group` and `badgeKey`. The groups are in Decisions. The phone bar and the More sheet use the same groups.
- **"Acting as" switcher.** Header pill with the role, a one-line description and, where needed, a branch picker (stored per user). Remove the cross-workspace nav items and dashboard duplicates. The pill shows at phone width too.
- **Counts.** `GET /me/nav-counts` returns `{key: n}` for the current role: to grade, reviews due, waiting for a batch, issues, requests, support near deadline, failed CRM events, and so on. It is cheap counts only and is polled with notifications.
- **Search.** `GET /search?q=` returns pages plus students, batches and certificates within `visible_branch_ids` / trainer scope. The Ctrl/Cmd+K palette uses `ui/command`.
- **Getting started card.** `GET /me/getting-started` returns steps and their done state for each role.
  - Student: activate, check your batch, join your first class, submit your first task.
  - Trainer: open your first class, mark attendance, grade a submission.
  - Branch Manager: create a batch, allocate students, create classes.
  - Admin: add a staff user, review setup and health.
  - The card can be dismissed.
- **As built (10 Oct 2026).**
  - **Endpoints** `GET /me/nav-counts`, `GET /me/getting-started` (both take `?workspace=` and, for the Branch Manager workspace, `?branch_id=`) and `GET /search?q=`, in `services/nav.py`, `services/search.py` and their repositories. Badge keys and step rules are listed in [API.md](API.md) §4.12. Search returns **records only**: the client lists the pages of the workspaces the user holds, because the nav lives in the frontend. A found record opens the list that holds it in the current workspace; deep links come with the record pages (U13 trainer, U14 branch, U17 admin).
  - **Navs.** Trainer, Branch Manager, Super Admin and Founder navs are grouped (`NavItem.group`) with `badgeKey`; "Branch views" / "Super Admin view" left the sidebars and the dashboards. Labels are unchanged on purpose: the screen phases rename them (U13–U17). The trainer phone bar is Today, Sessions, Reviews, Students. The student nav stays flat (its final form comes with the merges in U9 / U10), with counts on Tasks and Support. The Notifications items stay until U5.
  - **Counts** are a visual badge plus a screen-reader description outside the link (`aria-describedby`), so a link's name stays the page name.
  - **"Acting as"** shows for people with more than one workspace, or more than one branch in the Branch Manager workspace; single-role, single-branch users keep the static chip. The branch pick is stored per user in the browser (`lib/acting-branch.ts`) and narrows the counts and the card; the dashboards still read all branches until U14 adds the picker to "My work".
  - **Getting started** shows on the Student (translated), Trainer, Branch Manager and Super Admin homes, disappears once every step is done, and its dismissal is stored in the browser. The Founder has no card. The student's step labels are translated by key in `lib/i18n.ts`.
  - **Tests:** `tests/test_nav.py` (8). e2e: `shell.spec.ts` (grouped navs, switcher with branch picker, badge, Ctrl+K), `dashboards-staff.spec.ts` (cross-workspace links gone). Still failing in the e2e from earlier phases and not caused by U4: `dashboards-staff.spec.ts` "overview: tiles, sync status" (counts failed CRM events, which other specs add).

## U5. Notifications inbox, all roles (no migration unless needed)
- **One effective status per item:** New / Needs action / Done. Done means read, acknowledged or the action is complete, whichever the type needs. One primary button per item, labelled by type.
- **Tabs:** Needs action (default when any) · All · Done. Remove "System Issues" and the Delivery column for non-admins.
- **Links.** Every notification `link` deep-links to its item. Backfill missing links in `notify()` callers.
- **Bell.** A preview dropdown (latest 5 plus "Open inbox"). Remove the Notifications sidebar item from every nav.
- **Preferences.** Move to My Account (student) or Account (staff). Channels that aren't live are hidden.

- **As built (10 Oct 2026).**
  - **One status per item** (`Notification.status`: New / Needs action / Done; Failed for a channel problem) and the new views `needs_action`, `new`, `done` on `GET /notifications` (the older views stay for the API). `GET /notifications/overview` adds `needs_action` and `new`; the bell counts both.
  - **Inbox** (`features/shared/notification-centre.tsx`): tabs Needs action (opens first when there is anything, with a count) · All · Done; one button per item named by kind ("View schedule", "Open task", "View request"), "Mark as done" on open actions, "Mark as read" when there is no link. The Delivery, Read and Acknowledged columns are gone; the Super Admin alone keeps a "System issues" tab, and delivery failures are listed for nobody else.
  - **Bell** (`components/lms/notification-bell.tsx`): a preview of the latest five and "Open inbox". The Notifications sidebar item is gone from every nav; the per-workspace inbox routes stay.
  - **Links.** Every `notify()` call in the services already carried a link (a test now fails if one stops), and the one seed notice without a link got one. Links go to the screen that holds the item; item-level deep links come with the record pages in later phases.
  - **Preferences** moved to the Profile / account screen (`notification-preferences.tsx`), offering only channels with `live: true`.
  - Tests: `test_notification_centre.py` (status, views, failures hidden, every notify has a link); e2e `services.spec.ts` and `staff-account.spec.ts` rewritten for the inbox.

## U6. WhatsApp through the CRM: CRM round 6 (`db/107`)
- **Reply to the CRM.** Write `~/nipuna-crm/nipuna lms-docs/LMS_WHATSAPP_REPLY.md`:
  - W1: the 9 templates in [whatsapp-templates/](whatsapp-templates/README.md).
  - W2 (D1): the LMS sends activation links.
  - W3: yes, through W4.
  - W4: yes, please build `POST /lms/whatsapp`.
  - Also mention U1 and U2.
- **Payload.** Template name, `to` (or `lms_user_id`), values, dedupe key and occurred-at. The CRM applies its switch, test numbers, consent and backoff.
- **LMS outbox.** A `whatsapp_outbox` table written in the same transaction as the change, and a job `whatsapp-send` that posts after commit to the CRM endpoint with the service key.
  - Statuses: Queued / Sent / Failed / Skipped.
  - Never resent on a timeout.
  - Messages about things more than 2 days old are skipped.
- **Templates.** A registry `services/whatsapp_templates.py` in the CRM's format (name, language, category, body, params).
- **Triggers.**
  - Wire the sends for templates 4–9.
  - Templates 1–3 are wired in U7.
  - Class reminders become a job in `services/jobs.JOBS`.
- **Inbox.** WhatsApp shows as a live channel in notification preferences only when the switch is on and the template is approved.
- **Blocked until:**
  - the CRM ships `POST /lms/whatsapp`, and
  - the owner submits the templates.
  - **Until then,** build the outbox and the job with a "CRM endpoint not available" state; the code ships switched off.

- **As built (10 Oct 2026).**
  - **Reply written** to `~/nipuna-crm/nipuna lms-docs/LMS_WHATSAPP_REPLY.md` (W1 nine templates, W2 the LMS sends activation links, W3 yes to status, W4 yes, plus the proposed `POST /lms/whatsapp` contract and the U1 / U2 notes). The CRM's brief stays in `nipuna crm-docs/` until the round closes (a row for round 6 is open in `CRM_INTEGRATION.md` §5).
  - **Built and tested, switched off** (db 107, applied in place to `nipunalms-dev`): `whatsapp_outbox`, `services/whatsapp.py` (queue, rules, job), `services/whatsapp_templates.py` (registry and value checks), `services/whatsapp_messages.py` (builders), jobs `whatsapp-send` and `class-reminders`, `flask whatsapp status | list`. Triggers wired for templates 4-9; 1-3 are U7. Details and dedupe keys in [API.md §4.13](API.md).
  - **Choices not in the plan:** a message that cannot go out is kept as **Skipped** with the reason (so nothing floods out when the switch is turned on); `whatsapp_enabled`, `whatsapp_approved_templates` and `whatsapp_max_age_hours` are `app_settings`; class reminders are a "Learning reminders" message that starts **off** per person (the other templates are "Service", on); WhatsApp is offered in preferences only when live (switch on, `CRM_BASE_URL` set, a template approved); the batch-change message uses a reply-by of 7 days until U8 stores one; the "reminder 2 days before the reply-by date" of template 9 is not built.
  - **Blocked until** the CRM ships `POST /lms/whatsapp` and the owner submits the templates and sets `CRM_BASE_URL`. Tests: `test_whatsapp.py` (17) plus trigger checks in `test_certificates.py`, `test_results.py` and `test_batches_delivery.py`; the CRM is always faked.

## U7. Sign-in and accounts (`db/108`)
- **Login page.** One form, "Student ID or email", plus a "First time here? Activate your account" link. The activation panel leaves the page.
- **Self-service reset.**
  - `POST /auth/reset-code` always answers "If the account exists, we've sent a code".
  - `POST /auth/reset` checks the code and sets the new password.
  - Codes are hashed, single use, expire after 10 minutes, at most 5 per hour per person.
  - Sent by WhatsApp (template 1), falling back to email when the person has one and email is live. The coordinator-reissue path stays as a fallback.
- **Activation.**
  - On success the user is signed in automatically and lands on Home with the Getting started card.
  - A live password checklist; texts translated.
  - The Student ID is shown on the success step.
- **Activation links.** "Send new link" on Student Accounts posts template 2. Staff invites use activation tokens for staff (template 3); the temporary password stays as a fallback.
- **Unlock.** `POST /admin/users/{id}/unlock`, with a reason and an audit entry.
- **Change password.** Translated, with a success toast.
- **Certificate verify page.** A big Valid / Revoked result with no jargon; an unknown number gets a "Certificate not found" message.

- **As built (10 Oct 2026).**
  - **Reset** (`services/password_reset.py`): `POST /auth/reset-code` and `POST /auth/reset` as specified. Codes go by WhatsApp only: **the email fallback is not built**, because the LMS has no email sender. The coordinator-reissue path stays (Super Admin "Reset password", Student Accounts "Send new link").
  - **Activation and invites:** one `/auth/activate` for student and staff tokens; it signs the person in (not counted as learning activity, so the CRM's last-activity value does not change) and the success step shows the Student ID. Template 2 is queued whenever a student link is issued (CRM admission and "Send new link"); template 3 when staff are created or "Invite" is pressed. Temporary password is returned only when no WhatsApp message will carry the link. All three templates are `essential`: they ignore message preferences, and a finished or skipped row keeps no code or link.
  - **Screens:** login is one form with "Forgot password?" and "Activate your account"; `/forgot-password`; activation with a live password checklist; change-password translated with a toast; the certificate verify page shows a large Valid / Revoked / Replaced answer or "Certificate not found"; Users & Access has Invite and Unlock.
  - **Tests:** `test_sign_in.py` (24), e2e `sign-in.spec.ts`. Existing tests were adjusted where activating now creates a session and a WhatsApp row.

## U8. Student: Home and My Learning (`db/109` for topic progress)
- **Home.**
  - `GET /me/home` adds `up_next`, a choice among live class, work due today and continue topic.
  - Layout: hero plus 4 cards; remove the other cards.
  - A batch-change banner with Agree / Decline and the reply-by date.
  - Preferred slot only when the student has no batch.
- **Topic progress.** A `topic_progress` view or table: done = attended or recording watched, plus required work submitted. Module and course % from it.
- **My Learning.**
  - Course cards: Continue, progress, plain status.
  - Course page: modules first; "Course info" collapsed.
  - Track and module pages use the shared breadcrumbs.
- **Topic hub.** `GET /me/topics/{id}` returns sessions, recording, materials, assignments, tests and the next topic.
- **Telugu.** Every string on these screens goes through `t()`.

- **As built (10 Oct 2026).**
  - **Topic progress** (`topic_progress` view, `services/topic_progress.py`): Done = attended or recovered, or recording watched, plus every required assignment and test of the topic handed in. Module and course percentages count topics Done; the four progress measures are unchanged.
  - **Home:** `up_next` hero (live class, then work due today or overdue, then next topic, then next class), four cards (Due work, Continue learning, Latest recording, Attendance), a batch-change banner with Agree / Decline behind a confirm and the reply-by date (`material_changes.reply_by`, 7 days, setting `batch_change_reply_days`), and the preferred slot only while a course waits for a batch. The API still sends the Career, Support, Ask Nipuna and certificate cards; the screen no longer shows them.
  - **My Learning:** cards lead with "Continue: <topic>" and topics-done progress; the course page shows tracks and modules first with "Course info" folded; the topic page is the hub (`GET /me/topics/{id}`); module and track pages use the shared breadcrumbs. Student routes are unchanged (the nav label is "My Learning").
  - **Telugu:** these screens, the slot request and the status badges of enrolment, topic, class, task, attendance, recording and test go through `t()`; tooltips with the longer status help stay English. `title_te` is used for modules and topics.
  - **Tests:** `test_student_learning.py` (18), e2e `dashboards-learning.spec.ts` and `delivery.spec.ts` rewritten. Still failing and not caused by this: the trainer "Today" flow and the learner schedule spec (fixed seed dates).

## U9. Student: Schedule, Tasks & Tests
- **Schedule.**
  - Grouped by day, with plain states from the dictionary.
  - A Past tab: `GET /me/schedule?past=1` with attendance and recording links.
  - Join countdown; the button appears 15 min before start.
- **Tasks & Tests.**
  - `GET /me/work` merges assignments and tests into To do / Waiting / Done with counts.
  - The route `/tasks` (old `/assignments` and `/tests` redirect).
  - Assignment page: brief first, Submit near the top.
- **Tests.**
  - Start confirm (duration, no pause, attempts left).
  - Submit confirm with the unanswered count.
  - Question navigator with answered and flagged states.
  - After submitting: links to Back to tasks and to where the result will appear.

- **As built (10 Oct 2026).**
  - **Schedule:** `GET /me/schedule` now returns everything still to come (cancelled and moved classes included, so a student sees why a class is not on) and `?past=1` the classes that ended, newest first, with the student's attendance and recording (`services/my_courses.py`, new filter `window` in `repositories/class_sessions.py`). The screen groups Today / Tomorrow / This week (the next five days) / Later and has Coming up and Past tabs. Each class carries one plain state (Live now, Starts in 2 h within a day, otherwise Starts 10:00, Cancelled, Moved) and a "Link not ready" chip when the Meet link is missing. The Join button (`features/student/class-time.tsx`) appears 15 minutes before and is highlighted while live; the pages refetch every 30 s so the link shows without a reload. A past class that was never recorded as held says so instead of "Planned".
  - **Tasks & Tests:** `GET /me/work` (`services/student_work.py`, route and controller beside it) merges the rows the assignment and test lists already compute, so all three agree. Rules beyond the plan: a window that closed with nothing handed in is **Missed** and goes to Done (otherwise it would sit in To do for ever); a formal test that is marked but not published waits under Waiting for review; unreleased tests are not tasks; a practice quiz that can be retaken shows "Try again" in Done. The nav badge `tasks` now counts To do (it used to count open items without the Missed rule). `/tasks` is the route; `/assignments` and `/tests` redirect; the nav item is "Tasks & Tests" (the phone bar too); getting-started and the seed notice link to `/tasks`. `PillTabs` takes `labels` so tab names can be translated.
  - **Assignment page:** the brief first, a Submit button beside the title that jumps to the form, then earlier versions and details. **Test page:** start and submit use `ConfirmDialog` (minutes, "can't be paused", attempts left; unanswered count and flagged count); a question navigator (sticky on desktop) shows answered and flagged, flags are kept only in the page; the receipt links to Back to tasks and to Results for formal tests (Results stays until U10 merges it into My Progress).
  - **Telugu:** every string on these screens goes through `t()`, including question types, test kinds and the statuses added to the dictionary (`Missed`, test `In progress` / `Marked`, slot and Meet states). Text that comes from the API (a window's reason, the AI-use and late policies, trainer-written feedback) stays as sent.
  - **Tests:** `test_student_work.py` (15: states, sections, Missed, resubmission, formal wait, mock interview, nav badge, coming / past schedule, attendance isolation); e2e `assessments.spec.ts`, `delivery.spec.ts` and `shell.spec.ts` rewritten for the new screens. Still failing and not caused by this: the trainer "Today" flow (`In Progress` wording from U3) and the specs that depend on the seed's fixed dates.

## U10. Student: Class Materials, My Progress, Certificates
- **Class Materials.**
  - Route `/materials` with Recordings / Files tabs, grouped by course → week or topic.
  - Video cards.
  - A one-line access status per course; the policy goes into `HowThisWorks`; the extension dialog lives here.
- **My Progress.**
  - Route `/progress` with Overview · Attendance · Results.
  - "What to do next" from `GET /me/progress/next-steps`.
  - Result rows link to the test or assignment.
  - Attendance rows: Request recovery (Absent only) and Report a mistake (menu), with request status and decider on the row.
- **Certificates.**
  - Cards with the 3-step tracker and the blocker, including a fee banner linked to Fees.
  - **Certificate PDF.** New: render `GET /me/certificates/{id}/pdf` server-side from the issued version. No PDF generation exists today.
  - Copy verification link.

## U11. Student: Career, Ask Nipuna, Support, My Account
- **Career.** 4-step checklist on top. Apply is disabled with "Needs: …" and a link. The disclaimer becomes a note near Jobs.
- **Ask Nipuna.**
  - Chat thread: store the conversation order and pin the input at the bottom.
  - Quick actions pre-fill the box (and fix the bug where typed text silently wins).
  - Sources become links; quota shown only near the limit.
  - "Raise a support request with this question".
  - A trainer variant gets trainer example prompts (shared component).
- **Support.**
  - Requests waiting on the student float to the top with a badge; a new request opens after submitting.
  - Subject field, help per category, attachments (support attachment storage; migration if needed).
  - Fix the "Student" vs "You" author label.
- **My Account.**
  - Avatar menu → Profile · Fees & Receipts tabs.
  - Next-payment card (date, amount, overdue in red, how to pay, from branch settings).
  - **Receipt PDFs.** Rendered by the LMS from the CRM finance summary. Confirm with the CRM in the U6 document whether it already issues receipt PDFs.
  - Add or change email with a confirmation code.
  - Notification preferences.

## U12. Trainer: Today, class delivery, Attendance, My requests
- **Today.**
  - "Next up" expanded; the other classes compact; finished ones collapsed.
  - The to-do list from nav counts.
  - Tomorrow on empty days.
- **The class flow captures the full class log.** `deliverSession` takes outcome, actual times, break and not-delivered notes. Flow progress is stored server-side, not in `useState`, so a refresh resumes at the right step.
- **Sessions.** Schedule plus reschedule requests only. "Run class" opens the Today flow. Remove "Mark delivered" and "Start" there.
- **No Meet link.** "Ask Branch Manager" raises a flag on the class; the flow continues.
- **My requests.** `GET /me/requests` covers reschedules and corrections, with status, decider and reason; notify on each decision.
- **Attendance.** The "Unmarked & corrections" list (classes still to mark, corrections pending, recoveries to verify, in plain words). It opens the same register with a sticky Save.

## U13. Trainer: To grade, Assessments, Batches/Students, Content, Reports, Support
- **To grade.**
  - `GET /trainer/to-grade` merges submissions and attempts, oldest or overdue first, filter by batch.
  - Focused grading screen with Save & next and an explicit "Start review".
  - Marks validated against the maximum.
- **Assessments.**
  - Tabs: Question bank → Tests → Interviews, with counts and hints.
  - Edit drafts.
  - "New mock interview".
  - Confirm on Release and Close.
  - The "Attempts in progress" table goes.
- **Batch and student pages.** `/trainer/batches/$id` and `/trainer/students/$id`, with "Flag this student". Students get search and a batch filter.
- **Content.** Save & submit as the primary button; reviewer comment on the row; filters.
- **Reports.** `GET /trainer/at-risk` gives per-batch students at risk, with links to act.
- **Support.** The simple trainer view.

## U14. Branch: My work, Batches, Waiting for a batch, Schedule, Class day
- **My work.** `GET /branch/my-work` returns prioritised actionable rows; branch picker.
- **Batch page.**
  - `/branch/batches/$id` with `StepBar` and the next action as the main button.
  - Readiness shown before Confirm.
  - Creation wizard.
  - **"Create classes":** `POST /batches/{id}/generate-sessions` with preview, skipping holidays and closures.
- **Waiting for a batch.** `/branch/waiting` lists each student with matching batches and one-click Allocate; "Add students from waiting list" on the batch page.
- **Schedule.** Week calendar plus list toggle, the "Needs decision" strip, one primary row action plus a menu, Advanced fields hidden, "New class" pre-filled from the batch.
- **Class day.** Today's classes; tiles filter the list; set the Meet link inline; integration checks move to Setup & health.

## U15. Branch: the rest
- **Curriculum.**
  - The submit checklist, with incomplete topics marked.
  - Auto version names; drafts copy the Active version by default.
  - Drag to reorder.
  - Searchable prerequisites.
  - Remove the raw-ID inputs: pick versions and topics by name.
  - Confirm on Remove and Discard.
- **Content & questions.** One Review with preview, Approve & release primary, auto-claim on open, counts, question approval.
- **Marks & results.** Rename; each gap names its owner; publish confirm with counts; publish from inside the review.
- **Attendance & progress.** Tabs Students (at-risk first) · Recovery requests · Corrections, with counts; confirms.
- **Completion & certificates.**
  - The pipeline page; evidence against thresholds.
  - No default decision; confirm.
  - Rare actions under "More".
  - `/branch/completion` replaces both old pages.
- **Issues.**
  - One inbox: `GET /issues` across sources, filters, "Go fix it" deep links, "Add note".
  - Super Admin gets the same list read-and-assign (U17).
- **Recordings.** Release with confirm, or Report a problem with a reason. Collapse Hold / Partial / Unavailable into problem reasons (backend state mapping). Class picker by date and batch.
- **Student support.** Opens on Needs action sorted by deadline; new-reply marker; badge.
- **Access extensions.** Beyond-limit requests: the Branch Manager adds a recommendation and it goes to the Founder inbox (backend: a recommendation field plus routing). Within the limit: approve shows the new end date and "the student will be told".
- **Reports.** Drill-down links, period filter (default this month), CSV/Excel export (`services/exports.py`), monthly trends.

## U16. Founder
- **Inbox.** `GET /founder/inbox` covers curriculum approvals, certificate decisions, fee exceptions, access extensions with recommendations, the AI budget, and Branch Managers' own requests. Each item opens a side panel in the Founder workspace.
- **Curriculum.** `POST /curriculum-versions/{id}/approve` takes `activate_on` (optional; today means activate now), giving "Approve & activate" in one step. Side panel with a what-changes / who's-affected summary and a sticky Approve / Return bar.
- **Certificate decisions.** Approve / Reject buttons, no default, a reason required to reject, a consequence line per kind.
- **Access extensions page** in the Founder workspace, so the Founder no longer lands on `/branch/requests`.
- **CRM tiles** hidden until the CRM is connected.

## U17. Super Admin
- **Home.** "Needs action" list plus quick actions; the Setup checklist card.
- **Setup & health.** Merge both readiness registers into plain states with a staff-picker owner. The always-on "Integration Unavailable" banner goes.
- **AI controls page.** ON/OFF per audience; both the Super Admin and the Founder can switch off and restore company-wide (backend permission change in `services/ai_controls`); typed confirmation for company-wide.
- **CRM Sync.** Opens on Needs attention, with a plain cause per failure and Retry. Event view: summary first, JSON under "Technical details".
- **Users.** Role descriptions; Unlock; Send / Resend invite.
- **Student accounts.**
  - `/admin/students/$id` page with "Suggested next step" and the main button.
  - "Send new link" by WhatsApp; copy fallback.
  - A "Needs attention" filter.
- **Calendar.**
  - Month grid plus list, upcoming first.
  - Fields that change with the kind; date validation.
  - Edit and cancel with impact: `PATCH` and `POST /calendar/{id}/cancel`, returning affected classes.
- **Audit.**
  - Plain sentences from an action→sentence map.
  - Entity links; preset filters; "Last 7 days"; CSV export.
  - Raw diff under Details.
  - Fix the actor list being limited to page 1.
- **Issues.** Read-and-assign view of the U15 inbox. Fix the 100-row truncation everywhere: real paging.

## U18. Final sweep
- **Run every role through its main jobs** on temporary servers, at desktop and phone width, in light and dark mode. Use the screen list in DEVELOPMENT.md Part B.
  - Student: join a class, submit a task, take a test, watch a recording, get a certificate.
  - Trainer: run a class, grade, flag a student.
  - Branch Manager: create a batch, allocate, create classes, publish results, complete a student, issue a certificate.
  - Founder: approve a curriculum.
  - Admin: add staff, fix a CRM event.
- **Jargon check clean.** Every status comes from the dictionary.
- **Docs.**
  - Rewrite `DEVELOPMENT.md` Part B for the new routes.
  - Update `GAP_FIX_PLAN.md` phases 7–12 for the merged role and the new screens. Several of their screens now exist in their new form: assessments, completion, content, notifications, reports. They then only add the missing rules.
- **Then resume gap-fix phase 7.**

---

## Effects on the gap-fix plan (phases 7–12)

- **Numbering and role.** Phases 7–12 start after the last UX migration. Every "Academic Coordinator" in them reads "Branch Manager".
- **Exception queue.** Phase 7–12 items about it use the U15 Issues inbox.
- **Phase 10 (notifications and integrations).** The per-channel model and WhatsApp intake are mostly delivered by U5 and U6. What remains there is the CRM restrictions intake (G057).
- **Phase 11 (reports and dashboards).** Builds on U4 counts, the "My work" lists and the U15 report exports.

## Risks and notes

- **U2 is the biggest change.** Roles, approvals and seed are touched in 26 backend files and most tests. Keep it to role and permission changes plus the moved routes; leave redesign to U14 and U15.
- **Messaging depends on outside work.** U6 and U7 need the CRM's `POST /lms/whatsapp` (round 6) and the owner's Pinbot approvals. The code ships switched off, and the coordinator-reissue fallback stays until both are done.
- **PDFs are new.** Certificate and receipt PDFs need a server-side renderer (no PDF generation exists today). Choose the library in U10.
- **Mapping removal changes what the CRM sees.** No admission waits for curriculum any more. Tell the CRM in the round 6 document so its "Waiting for batch" expectations match.
- **Dev database.** Apply migrations in place. Rebuilding `nipunalms-dev` collides student codes with the CRM's stale `lms_user_id` values; if a rebuild is unavoidable, tell the CRM first so it can run `flask lms backfill`.
- **Known failing e2e before these phases:**
  - two `assessments.spec.ts` tests (fixed seed dates)
  - `admin.spec.ts` "student accounts"
  - `dashboards-staff.spec.ts` "logs a recovery step" (fixed in U1)
  - The rest are rewritten as their screens change.
- **The owner's servers.** :5060 has no reloader; restart it after each phase. All checks use :5061 / :5175.

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
| U9. Student: Schedule, Tasks & Tests | **Done** | `f96337a` | M |
| U10. Student: Class Materials, My Progress, Certificates | **Done** | `a8807f6` | L |
| U11. Student: Career, Ask Nipuna, Support, My Account | **Done** (db 111) | `cb3ca68` | M |
| U12. Trainer: Today, class delivery, Attendance, My requests | **Done** (db 112) | `f5f07c3` | M |
| U13. Trainer: To grade, Assessments, Batches/Students, Content, Reports, Support | **Done** | `7d0318f` | L |
| U14. Branch: My work, Batches, Waiting for a batch, Schedule, Class day | **Done** | `94d6e78` | L |
| U15. Branch: Curriculum, Content & questions, Marks, Attendance, Completion & certificates, Issues, Recordings, Support, Extensions, Reports | **Done** (db 113) | `02022c2` | L |
| U16. Founder | **Done** (db 114) | `2eec410` | S |
| U17. Super Admin | **Done** (db 115) | `ed48777` | M |
| U18. Final sweep and docs, then resume gap-fix phase 7 | **Done** | `d6e64aa` | S |

**Order matters:**
- **Backend first.** U0–U2 change roles and rules that every later screen depends on.
- **Shared parts next.** U3–U5 build the shared components the screen phases reuse.
- **Messaging before sign-in.** U6 has to come before U7, because the reset code and the links need the sending path.
- **Migrations.** `db/105` is U1, `db/106` is U2, `db/107` is U6, `db/108` is U7, `db/109` is U8, `db/110` is the WhatsApp status events (CRM round 6 reply) and `db/111` is U11, `db/112` is U12, `db/113` is U15 and `db/114` is U16 and `db/115` is U17 (U4, U5, U9, U10, U13 and U14 need none). Later phases take the next free number and record it here. Gap-fix phase 7 starts at `db/116`, the first number after the last UX migration (see [GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)).

## Gaps files (index)

What each phase left unbuilt, with the owner actions and test debt that went with it, is in `docs/ux-gaps/`:

| File | Phases | What it holds |
|---|---|---|
| [ux-gaps/U9-U12.md](ux-gaps/U9-U12.md) | U9, U10, U11, U12 | Telugu names in certificate PDFs, receipt PDFs, the email-change code by WhatsApp, question flags not saved; older fixed-date e2e debt |
| [ux-gaps/U13-U14.md](ux-gaps/U13-U14.md) | U13, U14 | Trainer at-risk thresholds, the Batches "Next" tag, week calendar paging, My work and batch confirmation; `delivery.spec.ts` seed dependencies |
| [ux-gaps/U15.md](ux-gaps/U15.md) | U15 | CSV-only exports, Recordings has no nav item, toast View links to tabs, recoveries and corrections not branch-filtered, the Branch Manager has no student page |
| [ux-gaps/U16-U17.md](ux-gaps/U16-U17.md) | U16, U17 | Founder inbox gaps (other Branch Manager requests, no bell, AI budget not enforced), Super Admin gaps (manual "Working", audit sentences, retry for old events), their test debt |

## Owner actions in one place

Everything below needs a person outside this repository (the rows in the gaps files repeat these per phase).

1. **Restart the :5060 API.** It has run without a reloader since 4 Oct, so it serves code from before migrations 102–104 and none of the new endpoints (`/me/schedule`, `/me/recordings` and `/me/progress` return 500 there; they return 200 on current code). The red "could not be loaded" cards on :5060 come from this. Restart :5174 only if its proxy or build is stale.
2. **Apply db 111–115 to any other database** (anything besides `nipunalms-dev`, where they were applied in place): `psql -d <db> -v ON_ERROR_STOP=1 -1 -f db/111_*.sql`, then 112, 113, 114, 115 in order. A database that was not kept up to date also needs 105–110. Never rebuild `nipunalms-dev` without telling the CRM (student codes collide).
3. **WhatsApp (round 6).** Submit the nine templates in Pinbot ([whatsapp-templates/](whatsapp-templates/README.md); replace `LMS_HOST` first). Then set `CRM_BASE_URL`, `app_settings.whatsapp_enabled` and `whatsapp_approved_templates` (`flask whatsapp status` shows why it is off). Until then nothing is sent and password reset by WhatsApp, activation links and class reminders do not reach anyone.
4. **CRM questions for the next round document.**
   - The CRM answered round 6 (`nipuna crm-docs/CRM_WHATSAPP_ROUND6_REPLY.md`, not committed): check its §2 differences against the LMS client (the `to` format, `Queued` as the normal answer, status back by `WhatsappStatusUpdated` events, switched off on its side until the LMS says so) before turning WhatsApp on.
   - Does the CRM already issue receipt PDFs? (U11: the LMS prints only the figures in the finance summary.)
   - A student's new email is not pushed to the CRM because no event carries it (U11).
   - Round 4 request (date of birth and guardians, `PersonRestrictionsUpdated`, placement endpoints): still waiting for the CRM; it blocks gap-fix phases 10 (G057) and 12.
5. **Give each Setup & health row an owner** and record how it was checked (U17); approve the monthly AI budget from the Founder's inbox (it is stored, not enforced yet).
6. **On a server:** `deploy/crontab` already runs `flask jobs run`; the `curriculum-activate` job (U16) is what activates a version on the day the Founder chose. Set `PUBLIC_BASE_URL` so certificate PDFs print the verify link and QR code.

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

- **As built (10 Oct 2026).**
  - **Class Materials** (`/materials`, `?tab=files`): Recordings and Files tabs with counts, grouped by course and then by topic (a recording with no topic falls under "Week of <Monday>"; a file with no topic under its module, else "General"). Recordings are video cards; files are rows with Open / Download and filters by course, type and title. Each course has one access line ("Available until 12 Jan 2027 · Request extension"); the extension dialog lives in `access-window.tsx` and the rules in "How access works". `/recordings` and `/resources` redirect (`/resources` to the Files tab). The Drive-not-connected note left the page; the Watch dialog still states it when it applies.
  - **My Progress** (`/progress`, `?tab=attendance|results`): Overview, Attendance, Results. `GET /me/progress/next-steps` (`services/student_progress.py`) returns up to six steps as `{kind, course, params}` and no sentences, so the screen words them in English and Telugu; the order and kinds are in API.md. Attendance rows carry the student's recovery and "report a mistake" requests with status, decision note and who decides (the Branch Manager); `Request recovery` shows only on an Absent row with no live recovery, `Report a mistake` is in a row menu (off while one is waiting). Result rows link to the assignment or test, where the feedback is. `/attendance` and `/results` redirect. Notification links, the dashboard, schedule, topic and test pages now point at the new routes.
  - **Certificates**: one card per course (and per live register entry) with the three-step tracker and one blocker (`GET /me/certificates` gains `cards`, built in `services/student_certificates.py`; blocker codes in API.md). An unpaid fee shows a banner above the cards with a link to Fees. Issued cards offer **Download PDF** and **Copy verification link** (`<origin>/verify/<number>`).
  - **Certificate PDF** (`GET /me/certificates/{id}/pdf`): rendered with **reportlab** (pure Python wheels, no system libraries; added to `requirements.txt` with its `pillow` and `charset-normalizer` dependencies, installed in the repo venv). `services/pdf.py` holds the renderer and small helpers (`safe_text`, `wrap`); **U11 reuses it for receipt PDFs**. One landscape A4 page from the issued version's own data (a reissue is drawn with its own name and "version 2"), with a QR code when the new setting `PUBLIC_BASE_URL` is set (otherwise it prints the number and the `/verify/` path). Only the owner may download, only an Issued certificate (not Revoked, Superseded or in progress; those answer 422 with the reason; another student's certificate is 404); each download is audited. The standard PDF fonts hold Latin-1 only, so a holder name in Telugu script prints "?" for those letters (a script font would need bundling; the register keeps the true name).
  - **Student nav** is now Home · My Learning · Schedule · Tasks & Tests · Class Materials · My Progress · Certificates · Career · Ask Nipuna · Support, followed by Fees & Receipts and Profile until U11 moves them into My Account. The phone bar is unchanged (the new items sit under More).
  - **Telugu**: every string on the three screens goes through `t()`, including the statuses added to the dictionary translations (attendance not-marked, requests, certificate, result). Data that comes from the API (course, class and trainer names, decision notes) stays as sent.
  - **Also changed**: `FormDialog` can be opened from a menu and translates option labels; `download()` shows the API's own message when a download is refused; amounts show as "₹ 15,000". No migration.
  - **Tests**: `test_student_certificates.py` (12: tracker states, fee blocker, revoked, PDF owner-only, not-issued / revoked / superseded refused, reissue, QR address, Latin-1 fallback), `test_student_progress.py` (12: each next-step kind, order and cap, request status on attendance rows); full backend suite passes. e2e `student-u10.spec.ts` (Materials, Progress with recovery and mistake flows, Results link, Certificates from review to a downloaded PDF and copied link, phone layout) and the student parts of `attendance`, `content`, `assessments`, `dashboards-learning` and `shell` updated. Still failing and not caused by this: the trainer "Today" flow, the trainer review step of `assessments.spec.ts` ("trainer reviews it..."), `attendance.spec.ts` "trainer marks a class" and `delivery.spec.ts` "coordinator creates a batch" (fixed seed dates and state left by earlier specs); because the specs in a file are serial, the student steps that follow them did not run in a full pass, so the changed selectors in `assessments.spec.ts` were checked through `student-u10.spec.ts` instead.

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

- **As built (11 Oct 2026).**
  - **Career** (`GET /me/career` gains `steps` and `apply_needs`): a four-step checklist on top (Opt in, Profile, CV reviewed, Share with employers) with the state of each and the button that does it. Apply is disabled while a step that `apply` requires is open and the page says "Needs: opt in, a reviewed CV, permission to share with employers" with each item scrolling to its step; the profile step is on the checklist but never blocks (the API does not require it). The no-guarantee line is a small note under Jobs for you.
  - **Ask Nipuna** (one `shared/assistant` for the student and trainer wrappers): a chat thread oldest first (`GET /ask-nipuna/queries?order=asc`, latest 30) with the box pinned under it. A quick action fills the box with the start of a question and is shown as "Using: <action>"; it never replaces typed text (the old bug) and the action name is still sent to the API. Sources are links to the class, course, assignment or test they came from. Quota appears only from 80% used. An answer with `answered: false` (no data, no enrolment, or refused) is tagged "Can't answer this" and offers "Raise a support request with this question", which opens `/support?new=1` with the category, subject and details filled in. The trainer variant has trainer example prompts and quick actions.
  - **Support** (db 111 `support_attachments`): the student's list shows requests waiting on the student first with a "Needs your reply" tag and a banner; a guided form (kind with help text, subject, what happened, up to 3 files of 5 MB: png, jpg, pdf, txt, doc, docx, checked by extension and first bytes) opens the new request, which is now its own page `/support/$requestId` with breadcrumbs. Attachments are stored under `UPLOAD_DIR/support/<request>/`, downloaded through `GET /support-requests/attachments/{id}/download` (same scope as the request; a student never gets a file from an internal remark; each download is audited). Student lines say "You" (the API's `from_student`), staff screens say "<name> (you)" or the author. The staff desk (`support-desk`) lost its student mode and can attach files to replies. Notification links now point at the request.
  - **My Account** (`/my-account`, tabs Profile · Fees & Receipts, `?tab=fees`): the avatar menu opens it (Change password and Sign out stay there), the phone More sheet and the Ctrl+K palette list it, and Fees & Receipts and Profile left the student nav, which is now exactly Home · My Learning · Schedule · Tasks & Tests · Class Materials · My Progress · Certificates · Career · Ask Nipuna · Support. `/profile` and `/finance` redirect. Staff keep `/account/profile` (`shared/staff-profile`). Notification preferences moved into the Profile tab, translated for students.
  - **Fees**: a "Next payment" card (amount, due date, "Overdue by N days" and a red card when the CRM says overdue or the date passed, courses, how to pay). *How to pay* is the new setting `branches.payment_instructions` of the branch that collects the fee, edited through `PUT /branches/{id}/payment-instructions` (Branch Manager for their branches, Super Admin); there is no screen for it yet, the seed fills both branches, and with no text set the card says to pay at the branch office. Per course fee / paid / still to pay, the amount still being checked, and the instalment schedule once per invoice remain.
  - **Receipt PDFs** are rendered by the LMS (`services/pdf.render_receipt`, reportlab) from the CRM finance summary: it holds each verified receipt's number, date and amount plus the fee position, so the PDF shows those and says it is a copy of a receipt the finance team verified. It carries no payment mode or official layout. **Still open: confirm with the CRM whether it already issues receipt PDFs** (add to the next CRM round document). Only the owner may download; each download is audited; a payment still being checked has no receipt.
  - **Email** (db 111 `email_change_codes`): "Add email / Change email" asks for the address, sends a 6-digit code and confirms it. The code is **delivered by WhatsApp** to the mobile number the CRM holds, using template 1 (the generic verification-code message, same outbox and switch as the password reset), because the LMS has no email sender. With WhatsApp off the screen says no code was sent and the email stays as it is. Rules are those of `password_reset`: hash only (it also covers the address, so a code cannot confirm another one), single use, 10 minutes, burned after 5 wrong tries, at most 5 codes an hour, an address used by someone else is refused. On success `students.email` and `users.email` change together and the change is audited. The new address is **not** pushed to the CRM (no event carries it yet). Other identity fields say "Contact your branch".
  - **Telugu**: every string on Career, Ask Nipuna, Support (list, form, request page, attachments), My Account and Fees goes through `t()` (about 330 new keys); data from the API (course, branch, trainer names, answers from Ask Nipuna, the branch's payment instructions, a decision note) stays as sent. Staff screens stay English.
  - **Tests**: `test_student_account.py` (email code and its rules, next payment, receipt PDF, branch setting), additions to `test_career.py` (checklist and `apply_needs` match `apply`), `test_support.py` (attachments, ordering, author labels) and `test_ask_nipuna.py` (order, `answered`); full suite passes. e2e `student-u11.spec.ts` (Career needs, the chat and the hand-off to Support, the guided form with attachments, a request waiting on the student, My Account, the email dialog with WhatsApp off, receipt PDF, Telugu, phone layout); `services.spec.ts`, `shell.spec.ts` and `student-u10.spec.ts` updated for the removed items.

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

- **As built (11 Oct 2026).**
  - **Today** (`/trainer`, `?session=<id>`): the next class (the one on now, else the first still to come, else the first without a log) is expanded with its flow, the other classes of the day are one line each with "Open class", finished ones sit under "Finished today (n)". Below is a **To do** list built from the same counts as the nav badges (`services/trainer_todo.py`): up to five classes without a class log ("Add class log"), assignments to review, test attempts to mark (the Assessments grading queue, `?tab=grading`), classes with attendance left, corrections waiting, recoveries to check. Tomorrow's classes show when nothing is left today (an empty day, or every class logged), not only on an empty day. The stat tiles left the screen (the API still sends them); the policy line moved into "How this works". Nav badges: Today = classes without a log (`class_logs`), Attendance = `attendance`.
  - **The class flow** (`services/class_flow.py`, db 112 `class_flow_progress`, `class_session_topics`): Start class → Join → Attendance → Class log. Attendance comes before the log (it can be marked once the class is Live), and **Finish class** saves everything through `deliver` after a confirm. Where the trainer is and the half-typed log (outcome, times, break, what was not covered, topics, notes) are saved on the server a moment after each change, so a refresh or another device resumes there; the saved step is only held to what the class state allows. A class that ended more than 6 hours ago and was never started has just the Class log; attendance is marked right after, from the finished class. `deliver` (API) takes outcome, actual start and end, break, not-delivered note, `topic_ids`, notes and optionally `attendance` entries (and a default status); the UI saves attendance on its own step (Save attendance) and sends the rest at the end. The planned topic is ticked by default and any topic of the curriculum version can be added; the class keeps its single planned topic for student progress and the covered topics are only recorded. Only the teaching trainer runs the flow; a Branch Manager covering a class still starts and logs it from the schedule.
  - **Sessions** is the schedule (Coming up / Past, Past includes a class never logged) plus the reschedule requests waiting. **Run class / Continue class / Add class log** open the Today flow; Start and Mark delivered are gone for the trainer (they stay for the Branch Manager's schedule until U14). `GET /class-sessions` gained `window=coming|past`.
  - **No Meet link**: "Ask Branch Manager" in the Join step records a `Link requested` Meet event (migration widens the check) and sends the branch's Branch Managers an action-required notice; asking again sends nothing more, and the flow carries on. The notice links to the existing Meet Operations screen until U14 builds Class day.
  - **My requests**: its own screen in the TEACH group after Attendance (`/trainer/requests`, nav item "My requests"; the other option, a tab on Sessions, was not chosen so the notification link has a page of its own). `GET /me/requests` lists reschedule requests and attendance corrections with one status vocabulary (Waiting for a decision / Approved / Not approved), who decides, who decided and their note. Every decision already notified; the reschedule notices now carry the note and link to `/trainer/requests`, and a trainer's correction decision no longer links to the student's `/progress` page. Recovery requests are not listed.
  - **Attendance** is "Unmarked & corrections" (nav label stays "Attendance"): Classes to mark · Corrections waiting · Recoveries to check · Recent classes, with counts, opening on the first list with work. A class opens `/trainer/attendance?session=<id>` with the same register as Today and a sticky Save bar (above the phone bottom bar). No new endpoint: it uses the existing register, corrections and recoveries lists.
  - **Not done / left to later phases**: Reviews / "To grade", Assignments, Assessments, Content, Batches, Students, Reports and Support keep their names and screens (U13); the phone bar is unchanged (Today, Sessions, Reviews, Students), U13 renames Reviews; the Branch side of reschedule and correction decisions is untouched (U14, U15).
  - **Tests**: `test_class_flow.py` (15: steps clamped to the class state, progress and draft survive a refresh, topic options, teaching-trainer-only, the full log with topics and attendance, a late class with only the log, missing logs counted, next up and tomorrow, to-do counts match the badges, Meet link request once and its rules, My requests with decisions, notifications with links, a Branch Manager's own request naming the Founder / Super Admin); `test_nav.py` and `test_home_reports.py` adjusted; full backend suite passes. e2e `trainer-u12.spec.ts` (Today flow with refresh, no Meet link, Sessions and Run class, My requests with a decision, Attendance list and register, phone layout) is new; the Today, delivery, attendance and shell specs were rewritten for the new screens, and the `Partial Data` / `Rescheduled` wording that U3 renamed was corrected in `attendance.spec.ts` and `delivery.spec.ts`. Still failing and not caused by this: the `Partial Data:` line of the trainer reports spec (U13).

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

- **As built (11 Oct 2026).**
  - **To grade** (`/trainer/to-grade`, GRADE group, badge `to_grade`; `/trainer/reviews` redirects): `GET /trainer/to-grade` (`services/trainer_grading.py`) merges hand-ins awaiting review and test attempts with written or coding answers left, overdue first then oldest, `?batch_id=` filter, counts and the batches to filter by. The screen has tabs All / Assignments / Tests, a batch filter kept in the address (`?batch=`) and "Start with the first". An item opens `/trainer/to-grade/$kind/$id` (`submission` or `attempt`): the work, an explicit **Start review** button (the form appears after it; typing no longer starts a review), feedback and marks checked in the browser against the maximum (the API already refused more than the maximum and less than zero for a hand-in), **Save & next** and Save. The next item is fixed at the moment the button is pressed (the one after this in the list, else the first left, else back to the list with "All caught up"). "Ask to resubmit" sits under More behind a confirm. A test attempt needs every written answer marked before it saves. The old grading queue and the "Attempts in progress" table are gone. Submission notices and the getting-started step now link to To grade; the Today to-do links there too.
  - **Assessments**: tabs Question bank · Tests · Interviews with counts and one-line hints, in `?tab=questions|tests|interviews` (`?tab=grading` redirects to To grade). Drafts are editable: questions (own drafts), tests (not released) and assignments (drafts, on Assignments) reuse the create dialog. **New mock interview** is its own button on the Interviews tab; interviews also got Edit, Release and Close there (they had no release before, because they were released from the Tests tab, which no longer lists them). Release and Close of tests and interviews, and Release of an assignment, ask first with the consequence.
  - **Batches and Students**: `/trainer/batches` (list with seats, next class, attendance, students needing attention), `/trainer/batches/$id` (progress figures, classes coming up and recent, roster with Flag, assignments, content), `/trainer/students` (search, batch filter, "only students who need attention", Flag per row) and `/trainer/students/$id` (what needs attention with a button each, attendance, work with Grade, results, support requests, **Flag this student**). Backed by `GET /trainer/batches`, `/trainer/batches/{id}`, `/trainer/students?q=&batch_id=` and `/trainer/students/{id}` (`services/trainer_people.py`); anything outside the trainer's batches is a 404. The search palette opens these pages for a found student or batch. The flag dialog is one shared component used by Support, rows and pages.
  - **Content**: filters by batch and status (plain groups such as "Waiting for review"); upload and new-version dialogs have **Save & submit for review** as the primary button and Save draft second; a "Changes requested" or "Rejected" row shows the reviewer's name and comment (`last_decision` on the content list, `services/content.review_comments`) and its primary button is "Fix and resubmit". Uploading without a topic now sends the batch's course (the API rejected it before although the screen said the topic was optional).
  - **Reports**: `GET /trainer/at-risk` (`services/trainer_risk.py`) lists per batch the students at risk with reasons, each with a link: low attendance and work missing or late go to the student page, classes not marked to Attendance, an overdue review to its grading screen. The averages became a four-figure Summary under it. The `Partial Data:` line that the old reports e2e looked for is gone with the old layout; the spec was rewritten.
  - **Support**: the trainer view is `SupportDesk simple` (no ID or category column; "With" shows the owner); in a request, Escalate and internal remarks sit under **More**; the "students with an open flag" table is removed; "Raise a request" and Flag on a student row or page share one dialog.
  - **My requests** also lists the recovery requests a trainer raised for a student (status words Pending / Approved / Not approved, decider and note), and a recovery decision now notifies that trainer with a link to `/trainer/requests`.
  - **Nav and phone bar**: the trainer nav already matched the Decisions list apart from Reviews, now "To grade"; the phone bar is Today, Sessions, To grade, Students.
  - **Choices not in the plan**: a student is "at risk" when any of four reasons holds, and a late hand-in counts only for 30 days so one old slip does not keep a student on the list (the dev seed shows every student at risk because its required work is long past due and unmarked classes exist). Marks for a hand-in must be a number from 0 to the maximum. No migration.
  - **Not done / left**: the Branch Manager side of content review, results and support stays as it was (U15); the at-risk reasons have no per-batch thresholds beyond the existing attendance setting.
  - **Tests**: `test_trainer_u13.py` (11: inbox merge and order, overdue first and the batch filter with scope, saved review leaves the inbox and marks checked, start review shown, at-risk reasons and links, overdue review reason, students search and filter, batch page, student page scope, waiting work on the student page, flag from a student) plus a content-comment test and a recovery-in-My-requests test; the full backend suite passes (831). e2e `trainer-u13.spec.ts` (inbox, grading flow, old links, Assessments, Batches and Students, Content, Reports, Support, phone) is new; `shell`, `services`, `dashboards-learning` and `assessments` were updated for the new names. Still failing and not caused by this (stale or fixed-seed data, run on a database that earlier runs changed): `content.spec.ts` upload (leftover "E2E interview cheatsheet"), `assessments.spec.ts` trainer review step (its hand-in was reviewed in an earlier run), `services.spec.ts` BM resolves the recording-access request, `trainer-u12.spec.ts` reschedule request (several "PCA lab" requests), `dashboards-staff.spec.ts` overview (failed CRM events count).

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

- **As built (11 Oct 2026).**
  - **My work** (`GET /branch/my-work`, `services/branch_work.py`): the Branch home now opens with "My work today", the rows in the Decisions order (students waiting for a batch, reschedule and extra-class requests, results to publish, content to review, recovery and correction requests, support near its deadline, classes at risk today), each with its count, how long the oldest has waited and one button. A row exists only while something waits. The branch pick is the header's "Acting as" pick, repeated as a select on the page; it now also narrows the home's tiles (the dashboards took no branch before). The old tiles follow under "How the branch is doing". New nav badges: `my_work`, `schedule`, `class_day`.
  - **Batches** (`/branch/batches`, `/branch/batches/$id`): a list with a "Next" tag per batch (worked out from the list's own fields, so it is approximate; the page is exact) and a three-step New batch wizard (Course, Mode / dates / timetable, Trainer). The batch page has the `StepBar` and the one next action from `GET /batches/{id}/progress` (`services/batch_steps.py`): assign a lead trainer, finish the setup (a short form asking only for what the checklist still lacks: dates and timetable, verified seats and room, the recording statement), **Confirm batch**, add students from the waiting list, create classes. What blocks a confirmation is listed with a fix button before it; advisory warnings are shown and need a written reason, kept in the audit log (`override_reason`). `POST /batches/{id}/confirm` proposes and confirms in one step (no notice to the other Branch Managers) and refreshes the stored readiness first: a batch created before its trainer kept "Blocked" and the database refused to start it. The old Propose button is gone from the Overview.
  - **Create classes** (`POST /batches/{id}/generate-sessions`, `services/session_plan.py`, with `preview`): one class per teaching day of the timetable, skipping approved company holidays and branch closures (with the reason), days the batch already has a class, and past times; the next unused curriculum topic goes to each class; at most 60 per call. All or nothing; a trainer clash blocks, a room or student clash needs the Branch Manager's reason. `class_sessions.create_series` was split out of `create_sessions` for it.
  - **Waiting for a batch** (`/branch/waiting`, `GET /branch/waiting`, `services/waiting.py`): the count, and per student the matching batches (same course and branch, a seat left, review not blocked) with a one-click **Allocate**; a match whose review has warnings is "Allocate…" and asks first, listing them. A student the review blocks (for example one that already holds a seat) is told why. Combo enrolments are offered the whole-programme batch once and each unseated track its own batches. "Add students from the waiting list" on the batch page uses `GET /batches/{id}/waiting`. The old allocation queue and its review dialog are gone; "Academic mapping" moved onto the student card.
  - **Schedule & calendar** (`/branch/schedule`): a **Needs decision** strip with the count (trainers' reschedule requests with Approve and a menu, proposed extra, remedial and replacement classes), a week calendar by batch or trainer (a day-by-day list on phones) or a list (Coming up, Past, All), one primary action per class (Approve, Add Meet link, Confirm, Plan a replacement) and a More menu (move, cancel, Meet link, log as held, details). Class details show the technical IDs under Advanced; New class is filled in from the batch (its next teaching day and time, room, lead trainer and next unused topic) with the Meet and calendar IDs under Advanced. The holidays and closures calendar sits below.
  - **Class day** (`/branch/class-day`, from Meet Operations; the old route redirects): today's classes; tiles (all, Meet link missing, delayed or disrupted, attendance to mark, class log overdue) filter the list; **Add Meet link** is set in the row. The Meet integration status and the last background checks moved to the Super Admin's integration screen (`admin/meet-health`) until U17 folds it into Setup & health.
  - **Nav**: TODAY My work, Class day; BATCHES & STUDENTS Batches, Waiting for a batch, Schedule & calendar, Attendance & progress. "Batches, Schedule & People" is gone (`/branch/operations` redirects to Batches; `/academic/meet-operations` and `/academic/operations` too). The phone bar is My work, Class day, Batches, Schedule. The search palette opens a found batch's page. Notification links to Meet Operations (including the trainer's "No Meet link" flag, left for here by U12) now go to Class day; a pending branch closure links to Schedule, an unallocated student to Waiting.
  - **How students pay** (left open by U11): a collapsed "How students pay fees" form on the Branch home reads and sets `branches.payment_instructions` (`GET` added beside the existing `PUT`). There is no Setup area for a Branch Manager yet.
  - **Choices not in the plan**: the Branch Manager's own requests are not on these screens, so `approvals.can_decide` is not used here; the Decisions list has no row for batches waiting to be confirmed, so none was added to My work; the first week shown on Schedule is the current one.
  - **Not done / left**: the rest of the Branch screens keep their names and screens (U15); a Branch Manager's own reschedule or correction requests are still decided on the old screens; no per-student "Allocate to another batch" on the waiting card beyond the matches shown. See [ux-gaps/U13-U14.md](ux-gaps/U13-U14.md).
  - **Tests**: `test_branch_u14.py` (14: My work order, scope and badges, waiting matches and blocked reasons, one-click allocate, combo tracks, the steps, one-step confirmation with the stale readiness and the warnings, Create classes preview with holidays and closures, narrowing and the 60-class cut, clashes and the override reason, the notice, payment instructions); `test_nav.py` still passes; the full backend suite passes. e2e `branch-u14.spec.ts` (My work and nav, old routes, branch picker, wizard, step bar and finish-setup form, confirm, add students, Waiting allocate, Create classes with a holiday, Schedule week / trainer / details / New class, Needs decision, Class day tiles and inline link, Meet checks on the admin screen, payment instructions, phone layout) is new; `batch-operations`, `calendar`, `dashboards-staff`, `shell`, `staff-account` and `delivery` were updated for the new names. Test debt: `delivery.spec.ts` "coordinator creates a batch with the wizard and allocates a waiting student in one click" and the schedule steps after it need a freshly seeded database (Sample Learner K. waiting, no class for the trainer today, the seeded PCA lab request); `dashboards-staff.spec.ts` "overview" (failed CRM event count) and `batch-operations.spec.ts` "preferred-slot card" fail for earlier reasons.

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

- **As built (11 Oct 2026).** Details in [API.md §4.19](API.md), [DATABASE.md](DATABASE.md) (113) and [DEVELOPMENT.md](DEVELOPMENT.md) Part B.
  - **Navigation.** The Branch nav is the Decisions list: TODAY My work, Class day; BATCHES & STUDENTS Batches, Waiting for a batch, Schedule & calendar, Attendance & progress; TEACHING Curriculum, Content & questions, Marks & results; COMPLETION Completion & certificates; HELP Student support, Issues; Reports. Every item has its count badge (`content_review` adds questions waiting for approval, `completion` adds certificates to approve or issue, `support` adds new student replies and access extensions, `issues` includes recordings). New routes `/branch/content`, `/results`, `/completion`, `/issues`, `/recordings`; the old ones (`/branch/content-review`, `/assessments`, `/certificates`, `/exceptions`, `/recording-exceptions`, `/requests`, `/academic-reports`) redirect and keep their search. Notification links now point at the new routes. **Recordings is not in the sidebar** (the Decisions list has no row for it): it opens from Class day and from Issues.
  - **Curriculum.** `GET /curriculum-versions/{id}` returns a structured `checklist` (Modules, Topic details, Hours, Completion rules, Required assessments; a combo parent also Tracks and booster) with the incomplete required topics named. Drafts are named by the server (the newest number raised: CV 1.3 becomes CV 1.4) and copy the Active version unless `blank`. Drag to reorder uses the browser's own drag and drop, with Move up / Move down buttons as the keyboard and phone way (no new package). Prerequisites are a searchable list by topic name. A confirm on Remove module / topic / assessment, Discard draft, Retire and Activate. The decision selects no longer default to Approved. Choice not in the plan: the Required assessments step is shown but does not block submitting (the server never required it); the retire reason box went with its confirm.
  - **Content & questions.** One page with tabs and counts (`GET /content-items/review-summary`). Opening a review claims it (`POST /content-items/{id}/claim`, idempotent, never an own upload); the list shows who has it. Approve & release is the primary button and asks first; Approve and release later, Request changes (comment required) and, under More, Reject. Questions to approve is the old question bank approval, moved here.
  - **Marks & results.** Each unready test lists its gaps with who must fix them (`gap_details`); publishing asks first with the counts from `GET /results/publish-preview` ("Publish 12 results? 3 still unreviewed") and works from inside the review. `POST /results/publish` now takes `batch_id` (publishing one batch's review no longer publishes the same assessment in other batches).
  - **Attendance & progress.** Tabs Students (`?sort=risk`, at-risk only unless "Show all students", real paging, a row opens the four measures), Recovery requests, Corrections, with counts from `GET /branch/attendance-summary`. Corrections and reschedule requests carry `can_decide` (this closes the U2 and U14 gap: a Branch Manager's own request, or an entry they marked, hides the buttons; approving or rejecting your own reschedule request is now 422). Approving or rejecting confirms with the consequence.
  - **Completion & certificates.** `GET /branch/completion` builds the pipeline (Ready to decide, Completed, Waiting for fee, Ready to issue, Issued) with counts; evidence shows attendance against the curriculum's minimum, required topics covered, open recoveries and the trainer's recommendation as ticks and crosses. A running student whose evidence is complete and who has no review appears under Ready to decide with Start review. The decision has no default and confirms; approve and issue confirm; correction, revocation, reinstatement and a fee release sit under More. The old Completion Review and Certificate Eligibility pages and the Certificate Register on Reports are gone (the change requests and fee releases waiting for a decision sit in a collapsed section of the new page).
  - **Issues.** `GET /issues` reads the `exception_queue` view (so recording exceptions are in it already) with exact paging, filters type / age / owner and a `go_fix` deep link per source; Add note is the existing recovery step. It is role-aware (Branch Manager their branches, Super Admin everything, Founder reads); U17 reuses `IssuesList` read-and-assign. The 100-row cap is gone from this screen (the page size stays at most 100 per request, with page links).
  - **Recordings.** `POST /recordings/{id}/problem {reason, note}` collapses Hold, Partial and Unavailable into the reasons processing, partial, unavailable and on_hold (each recording carries `problem`); `GET /recordings/classes` feeds the class picker by date and batch. Release asks first, the Drive file id has a hint, and an open problem jumps to its class. Choice not in the plan: "processing" returns a recording to Processing and tells students it is being prepared again, without raising an exception.
  - **Student support.** `GET /support-requests?view=needs_action|waiting|done|all` (Needs action sorted by the nearest `sla_due_at`), `/support-requests/counts`, and `reply_mark` (`new_reply` / `new_request`) on staff rows. Choice not in the plan: "new reply" means the student wrote last after staff had answered; there is no per-person seen state. The nav badge counts what is near or past its deadline plus new replies plus access extensions; My work's support row is unchanged.
  - **Access extensions** (db 113). `access_extension_requests` gains a recommendation (decision, note, suggested end date, who, when). Beyond the limit (after the second anniversary) the Branch Manager adds it (`POST /access-extension-requests/{id}/recommendation`, revisable until decided) and the request goes to the Founder: `with_founder` is true and the Founder is told; the Founder's nav `access` count counts those. A new request beyond the limit now asks the Branch Manager (no longer the Super Admin) for a recommendation. The Super Admin and Founder can still decide any of them. U16's `GET /founder/inbox` reads `services.access_extensions.awaiting_founder()`. Within the limit the screen shows the new end date (`new_end_date`) and says the student will be told; it lives as a tab of Student support (`?tab=extensions`).
  - **Reports.** `GET /branch/reports` (period default this month, last month, last 90 days, custom; figures with a `drill` link each, progress by batch, six-month trends) and `GET /branch/reports/export?section=figures|batches|trends|certificates` as **CSV only** (`services/exports.py`; `openpyxl` is not installed and no spreadsheet package is in `requirements.txt`, so Excel is not offered and the screen says the CSV opens in Excel; cells starting with `=`, `+`, `-` or `@` are guarded). A figure that cannot be worked out is "No data", never 0.
  - **Tests.** `test_branch_u15.py` (13: Issues paging, scope, filters and notes; the curriculum name, copy and checklist; the recommendation and its routing; the within-limit end date; recording problem reasons and the class picker; content claim and counts; support views, order, reply marks and the badge; attendance counts; reports and the CSV guard; a Branch Manager's own reschedule request) plus additions to `test_results.py` (publish preview), `test_tests_attempts.py` (gap owners) and `test_certificates.py` (the pipeline); the full backend suite passes (862). `npx tsc --noEmit -p .` is clean. e2e `branch-u15.spec.ts` (navigation and old routes, Issues, Recordings, Content & questions, Marks & results, Attendance, Support and the recommendation, Completion, Curriculum, Reports and the CSV, phone width at 360px for nine screens) passes with `branch-u14.spec.ts`; `shell`, `dashboards-staff`, `dashboards-learning`, `delivery`, `governance`, `attendance` and `content` were updated for the new names and screens. Still failing in the full desktop run and not caused by U15 (leftover or fixed-seed data, serial chains): `assessments.spec.ts` trainer review step, `attendance.spec.ts` "trainer marks a class" (a class from an earlier run clashes), `batch-operations.spec.ts` preferred-slot card, `content.spec.ts` student step (leftover "E2E interview cheatsheet" rows), `dashboards-staff.spec.ts` overview (failed CRM event count), `delivery.spec.ts` wizard (Sample Learner K. no longer waiting), `services.spec.ts` BM resolves the recording-access request (SR-1042 already resolved), `student-u10.spec.ts` My Progress and `student-u11.spec.ts` Career (state left by earlier runs), `trainer-u12.spec.ts` and `trainer-u13.spec.ts` Content (stale rows), and the public verification `@mobile` wording check in `governance.spec.ts`. The named U15 debt: the `attendance.spec.ts` certificate step now uses the pipeline (its approve and issue steps ran green once; they consume Sample Learner C, so a re-run needs a fresh seed), and the `delivery.spec.ts` curriculum step has the new selectors but cannot pass on this database (CV 3.0 is already active). Open gaps are in [ux-gaps/U15.md](ux-gaps/U15.md).

## U16. Founder
- **Inbox.** `GET /founder/inbox` covers curriculum approvals, certificate decisions, fee exceptions, access extensions with recommendations, the AI budget, and Branch Managers' own requests. Each item opens a side panel in the Founder workspace.
- **Curriculum.** `POST /curriculum-versions/{id}/approve` takes `activate_on` (optional; today means activate now), giving "Approve & activate" in one step. Side panel with a what-changes / who's-affected summary and a sticky Approve / Return bar.
- **Certificate decisions.** Approve / Reject buttons, no default, a reason required to reject, a consequence line per kind.
- **Access extensions page** in the Founder workspace, so the Founder no longer lands on `/branch/requests`.
- **CRM tiles** hidden until the CRM is connected.

- **As built (11 Oct 2026).** Details in [API.md §4.20](API.md), [DATABASE.md](DATABASE.md) (114) and [DEVELOPMENT.md](DEVELOPMENT.md) Part B.
  - **Inbox** (`GET /founder/inbox`, `services/founder_inbox.py`): one list, oldest first, of curriculum versions to approve or activate, certificate change requests, fee exceptions, access extensions that carry the Branch Manager's recommendation (`awaiting_founder()`), the AI budget while it is unset, and Branch Managers' own reschedule requests and attendance corrections. Only what the signed-in person can decide appears (a Super Admin's own submissions and requests are left out). Each item carries the record as its own screen shows it, so a panel needs no second read. The same builders give the nav counts: `inbox` (the Home badge), `curriculum`, `certificates` (change requests plus fee exceptions the person can decide, no longer "Awaiting Approval" certificates, which the Branch Manager approves), `access`.
  - **Screens.** `/founder` leads with "Needs you" (the shared `NeedsYouList`; each Review button opens the item in a side panel on the same page, `?item=<kind>-<id>`), then "How the company is doing": the CRM tiles only once the CRM has sent finance figures (`crm_connected`, which is "any branch has a finance snapshot"; until then one quiet line says they appear later), then the delivery tiles. The nav is Home (with the count) and, under APPROVALS, Curriculum approvals, Certificate decisions and Access extensions, each with its count. The three pages list the same items by kind and open the same panels. The Founder dashboard and notification links no longer use `/branch/requests`: `/founder/access` is new, and the recommendation notice links to the item.
  - **Panels** (`features/founder/panel-*.tsx`, built on the existing `ui/sheet`; a header, a scrolling body and a bar pinned to the bottom). Curriculum: "What changes" and "Who is affected" in plain sentences (`GET /curriculum-versions/{id}/impact`: topics and modules added or removed against the Active version by title, learning hours, batches that would pick it up, batches that stay) and the full outline under a fold; **Return** (reason of at least five characters) and **Approve**, which opens a short choice: Activate it now (preselected, button "Approve & activate"), on a day I choose ("Approve and schedule"), or only approve ("Approve only"). Certificates: **Approve** and **Reject** side by side with the same weight, neither preselected; Approve confirms with a consequence line per kind (correction, revocation, reinstatement, fee release), Reject asks for a reason; a fee release also asks for the basis. Access extension: the recommendation block, then Approve (new end date, filled with the Branch Manager's suggestion) or Reject (reason). AI budget: a rupee amount and a confirm. A Branch Manager's own request says why it came to the Founder.
  - **Backend.** `POST /curriculum-versions/{id}/approve` takes `activate_on`: omitted = approve only (as before), today = approve and activate in one step (the response carries `released`), a later day = approved now and activated that day by the new `curriculum-activate` job (db 114 `curriculum_versions.activate_on`, cleared by any status change), a past day is 400. `PUT /founder/ai-budget` stores the monthly amount (`services/ai_budget.py`, audited). `approvals.founder_may_decide`: the Founder may now approve or reject a reschedule request or an attendance correction **raised by a Branch Manager** (and only those; other requests are still refused with 403), which is what makes the inbox rows decidable.
  - **Choices not in the plan.** "Approve & activate" is a choice inside the Approve dialog (now / a day / not yet) rather than a second button, so the default flow stays one click plus a confirm and nothing is activated by accident. The impact summary compares titles only. The AI budget is a single amount with no reject. The Founder home keeps the delivery tiles but drops the old "Decisions needing you" list. Recent decisions were not built (not chosen).
  - **Not done / left.** The Branch Managers' own requests of other kinds, the Founder notification bell, enforcing the AI budget and changing an approved amount, an override reason for a clash when approving a reschedule: see [ux-gaps/U16-U17.md](ux-gaps/U16-U17.md).
  - **Tests.** `test_founder_u16.py` (14: approve alone, approve and activate today, a chosen day and the job, a past or invalid day and a retired version, no approving your own submission, the impact summary, inbox access, each kind oldest first with nav counts, own requests left out, access extensions only with a recommendation, the AI budget and its audit, a Branch Manager's own correction and reschedule decided by the Founder and a trainer's refused, the CRM flag); `test_nav.py` updated for the new `inbox` badge. The full backend suite passes (876); `npx tsc --noEmit -p .` is clean. e2e `founder-u16.spec.ts` (home and nav, curriculum panel and Return, Approve & activate choices and scheduling, a certificate request with consequence lines and a rejected reason, the access panel, the AI budget confirm, phone width at the panel, dark mode) is new; `shell`, `dashboards-staff` and `governance` were updated for the new Founder names and tiles. The named debt `delivery.spec.ts` "super admin approves and activates the curriculum" is unchanged: it uses the Branch Curriculum page's own Approve and Activate buttons (still there), and fails on this database because CV 3.0 is already active. Still failing in the e2e run of the touched specs and not caused by U16: `dashboards-staff.spec.ts` "overview: tiles, sync status" (failed CRM event count) and "the coordinator logs a recovery step" (every waiting student on the Branch Issues screen already has an owner from earlier runs), and the public verification `@mobile` wording check in `governance.spec.ts` (both failed before).

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

- **As built (11 Oct 2026).** Details in [API.md §4.21](API.md), [DATABASE.md](DATABASE.md) (115) and [DEVELOPMENT.md](DEVELOPMENT.md) Part B.
  - **Navigation.** PEOPLE: Users & access, Student accounts; OPERATIONS: Issues, Academic calendar, CRM sync; SYSTEM: Setup & health, AI controls, Audit log; Home first. Every item has a count (`home` is the sum, `users` = locked accounts, `student_accounts`, `issues` = nobody owns, `calendar` = closures waiting, `crm_sync` = needs attention, `setup` = broken). New routes `/admin/setup`, `/admin/ai-controls`, `/admin/issues`, `/admin/students/$id`; `/admin/integrations`, `/admin/security` and `/admin/exceptions` redirect. The Founder's nav gets **AI controls** (`/founder/ai-controls`, the same page) under "Safety".
  - **Home.** `GET /admin/needs-action`: the newest three failed CRM updates each with an inline **Retry** (the rest as one row), issues nobody owns, locked accounts, closures waiting, student accounts needing attention, broken setup items; Quick actions (Add staff user opens the dialog); the **Setup checklist** card lists what is not Working yet and is gone once every item is Working. The tiles, the CRM sync table and the always-on "not verified" banner are gone from the home.
  - **Setup & health.** One checklist of the 12 connections and 18 security settings with plain states (Not set up / Set up / Working / Broken, worked out from the two registers' statuses in `services/readiness.setup_state`), an owner picked from staff (`owner_user_id`, db 115) and the evidence; the Update dialog sends a plain `state` (Working still needs evidence). The Meet and class checks section moved here from the old integrations screen.
  - **AI controls.** `services/ai_controls._may_control` no longer reserves "All" for the Founder: the Super Admin and the Founder can each switch off and restore any audience company-wide. `GET /ai-controls/status` drives a card per audience (ON / OFF, why, who, when; "off because all AI is off"), one-branch switches and a paged history. Switching off company-wide asks for the typed words `SWITCH OFF`.
  - **CRM sync.** Opens on **Needs attention** (`?attention=true`: failed first, then received-but-unfinished); every update has a `summary` and, when failed, a one-sentence `plain_cause` from `services/crm_causes.py` and `can_retry`; the update opens a plain summary with the raw JSON under "Technical details". Tabs: Needs attention, All updates (filters), Sent to the CRM.
  - **Users & access.** Each role in the picker carries a line on what it does; **Unlock** (with a reason) is the first button on a locked row and Locked is a status filter (`?locked=true`); the invite button reads Send invite or Resend invite. Choice: the role description constants live in the frontend.
  - **Student accounts.** `services/student_next_step.py` gives every student a **Suggested next step** (suspended, no link, link expired, link not carried by WhatsApp, sign-in switched off, enrolment held back, waiting, nothing to do) and a `needs_attention` flag, with the same rules in SQL for the **Needs attention** filter and the nav count (a test keeps them in step). The main button sends the link by WhatsApp (copy fallback in the dialog), reactivates, or opens the account / Issues. The student is a page (`/admin/students/$id`) with breadcrumbs, the next step, account facts, courses, history as sentences and the less common actions.
  - **Calendar.** Month grid and list (`sort=upcoming`: what is ahead first, then what is over); primary **Add holiday / closure** whose fields change with the kind; To follows From and cannot be earlier; at most 63 days. `PATCH /calendar/closures/{id}` and `POST /calendar/closures/{id}/cancel` return `affected_sessions` / `affected_count` and take `dry_run`, so the screen shows "This affects N classes" before anything is saved; an edit that newly covers classes asks the Branch Managers to replace them, a cancel tells them the classes run as scheduled. Cancelling keeps the entry (status reads Cancelled, `cancelled_at` in db 115) and working days stop counting it. Paths follow the existing `/calendar/closures/{id}` shape, not `/calendar/{id}`.
  - **Audit log.** `services/audit_sentences.py`: an action-to-sentence map (about 130 actions), the record's name and a link to its screen, the three presets (`preset=accounts|roles|integrations`), a Last 7 days range, CSV export (`/audit-log/export`, at most 5,000 rows), the raw before / after under Details, and the actor list from `facets.actors` (everyone with an entry, not page 1 of staff). Entries on a student's page read as sentences too.
  - **Issues.** `/admin/issues` reuses the U15 list (`IssuesList canAssign`, no branch pick) with **Assign**: `POST /exceptions/{source}/{id}/assign` records a recovery step with `assigned_to` (db 115 changes the `exception_queue` view to follow it) and tells the person. Not for items whose own screen names the owner. The 100-row cap is gone from the Super Admin's screens: the old exception queues page (which loaded 100) is replaced by the paged list, the calendar list and the AI history page, and the audit actor list is no longer one page.
  - **Choices not in the plan.** "Cancelled" is a column (`cancelled_at`) and not a new value of the shared `approval_status` enum. The Setup checklist is done when every item is Working. The Founder reaches AI controls from their own nav. The AI budget is not shown or enforced here (see the gaps file). Home keeps no tiles.
  - **Tests.** `test_admin_u17.py` (27: setup states, plain-state updates and owners, the checklist and its badge, AI status for both roles, CRM attention and causes, the locked filter, student next steps and the filter agreeing with the flag, calendar edit / cancel / impact / validation / paging, audit sentences / presets / actors / CSV, issue assignment and its refusals, paging past 100); `test_ask_nipuna.py` (the Super Admin may switch all AI off) and `test_nav.py` updated. The full backend suite passes (903); `npx tsc --noEmit -p .` is clean. e2e `admin-u17.spec.ts` (grouped nav and counts, Needs action and Quick actions, AI controls with the typed confirmation, the Founder's AI controls, unlock, CRM sync, the calendar add / edit / cancel with impact, assign, the Needs attention filter and the student page, phone width at 360px for eight screens, dark mode) passes on desktop and mobile; `admin`, `shell`, `calendar`, `governance` and `dashboards-staff` were updated for the new names and screens. Named debt `admin.spec.ts` "student accounts" is rewritten for the new page and passes. Still failing and failing before: `dashboards-staff.spec.ts` "the coordinator logs a recovery step" and the public verification `@mobile` check in `governance.spec.ts`. Gaps in [ux-gaps/U16-U17.md](ux-gaps/U16-U17.md).

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

- **As built (15 Oct 2026).** U18 changed no migration and no endpoint; `API.md` and `DATABASE.md` are unchanged.
  - **Clean baseline.** Everything ran on **scratch databases** (`nipunalms_sweeptpl-dev`, seeded once, copied to `nipunalms_sweep-dev` before every spec file; both dropped afterwards), a temporary API on :5061 and Vite on :5175 with the `WHATSAPP_*` variables blanked, so nothing could be sent and `nipunalms-dev`, :5060 and :5174 were never touched. Per-file reseeding is documented in [DEVELOPMENT.md](DEVELOPMENT.md) Part A.
  - **What the sweep covered.** New `e2e/sweep-u18.spec.ts` (17 tests, desktop and phone):
    - For each of the five roles: every link of the role's navigation opens without a server error, with a heading, no error card and none of the leftover spec words (the jargon list plus `undefined` / `NaN` / `[object Object]`); at 390px nothing scrolls sideways; in dark mode the page background is dark, every status and tone badge keeps at least 4.5:1 contrast (computed from the real colours), and exactly one nav item is current.
    - Student: a class starting in 9 minutes shows a disabled Join with the reason until the Meet link is saved, then a Join link; Class Materials lists a recording and Watch opens it.
    - Branch Manager: a trainer recommends, the Branch Manager decides Complete (Decide has no choice selected, the confirm states the consequence) and the student moves on in the pipeline.
    - The jobs the existing specs already walk were re-run and pass: student submits a task and takes a test (`assessments`), certificate tracker, PDF and verification link (`student-u10`, `attendance`), trainer runs a class, grades and flags a student (`trainer-u12`, `trainer-u13`), Branch Manager creates a batch, allocates, creates classes, publishes results and issues a certificate (`branch-u14`, `branch-u15`, `delivery`, `assessments`, `attendance`), Founder approves a curriculum (`founder-u16`, `delivery`), Super Admin adds staff and retries a CRM update (`admin`, `admin-u17`).
  - **Bugs fixed.**
    - The Trainer's **Today** was marked as the current page on every trainer screen for screen readers (`aria-current` on two links); the router matched the workspace index link loosely. `isWorkspaceRoot` / `activeOptions={{ exact }}` in `auth/access.ts` and `app-shell.tsx`.
    - The Founder's home printed "Meet organizer Pending Verification" and the Super Admin's Issues printed "Organizer account licence Pending Verification": the batch readiness reason (`services/batches.py`) and the seed text now read in plain words ("The Meet organizer is not verified yet").
    - The Branch attendance screens coloured the LMS engagement level with a hand-made tone map; it is now `statusInfo("engagement", …)` in the dictionary.
  - **Stale e2e fixed (wording, selectors, seed assumptions).** `assessments` (the trainer grades the seed's hand-ins for Sample Learners G. and H., and publishing is on Marks & results with its confirm), `attendance` and `governance` (the public verification page's new wording), `batch-operations` (the batch change and the preferred-slot card are on Home), `content` (the old exception queue is the Open problems list on Recordings), `delivery` (the New class dialog fills itself in from the batch, so the test waits for it; the Approve toast and one wording line), `services` (`/branch/requests` opens Student support), `student-u11` (the test now signs the student in on a second device itself instead of relying on leftovers from other specs).
  - **Jargon and statuses.** The Conventions grep shows only comments and code identifiers (`outbox_id`, `OUTBOX_STATUSES`, `Pending Verification` as a data code that is labelled through `statusInfo`). No `toneFor`-style helpers, no hand-made status colour maps for statuses and no "Empty:" / "Saved:" prefixes remain. Tags that are labels, not statuses (Required / Optional, a branch, a role), keep their explicit tone.
  - **Results on the clean database** (each spec file on its own fresh database): backend 903 passed in the first full run, and 902 passed in the final one: `test_branch_u14.py::test_my_work_lists_what_waits_in_the_decided_order` builds a class two hours ahead and fails after about 22:00 IST (it fails the same way on the code before U18), so it is a clock-dependent test, not a regression; `npx tsc --noEmit -p .` clean; Playwright desktop and mobile projects, 189 passed and 0 failed across the 23 spec files.
  - **Still not clean, and why.**
    - Clock-dependent tests: the backend test named above, and `trainer-u12` (and the steps of `dashboards-learning`, `delivery` and `attendance` that schedule a class for today) skip or fail after about 22:20 IST (the specs): they book a class an hour or two ahead and refuse to cross midnight. They passed at 22:07 IST. This is how the specs are written, not a defect; run them earlier in the day.
    - The Setup & health notes for the two Meet organizers still read "Pending Verification": the text is written by migrations 001 and 060, which are history. The sweep exempts that one screen. Rewording needs a new migration (the next one is `db/116`, taken by gap-fix phase 7) or an edit on the Setup screen.
    - Two earlier specs (`branch-u14.spec.ts`, `branch-u15.spec.ts`) fail the Prettier check; they were already like that.
  - **Not checked.** There is no real WhatsApp (nothing is sent; the queue is covered by `test_whatsapp.py`), no real Google Meet or Drive (links are typed in; "Watch" opens the integration-not-connected message), no real CRM (a fake in the tests), no email, no payment. Telugu was checked only where existing specs cover it (`shell`, `student-u11`). Dark mode was checked by computed contrast and page colour, not by eye on every screen. A phone is a 390px viewport (Pixel 7 profile and a resized desktop), not a device. Empty states are covered only where a seed screen is empty; a role with no data at all was not walked. Loading skeletons and toasts were not asserted by the sweep.
  - **Open gaps and owner actions.** The gaps files and the single owner list are above ([Gaps files](#gaps-files-index), [Owner actions](#owner-actions-in-one-place)). Gap-fix phase 7 (assessments, `db/116`) is next.

---

## Effects on the gap-fix plan (phases 7–12)

- **Done in U18** (the phase sections in [GAP_FIX_PLAN.md](GAP_FIX_PLAN.md) are rewritten; the notes below are what was applied).
- **Numbering and role.** Phases 7–12 start at `db/116`. Every "Academic Coordinator" in them reads "Branch Manager".
- **Exception queue.** Phase 7–12 items about it use the U15 Issues inbox.
- **Phase 10 (notifications and integrations).** The per-channel model and WhatsApp intake are mostly delivered by U5 and U6. What remains there is the CRM restrictions intake (G057).
- **Phase 11 (reports and dashboards).** Builds on U4 counts, the "My work" lists and the U15 report exports.

## Risks and notes

- **U2 is the biggest change.** Roles, approvals and seed are touched in 26 backend files and most tests. Keep it to role and permission changes plus the moved routes; leave redesign to U14 and U15.
- **Messaging depends on outside work.** U6 and U7 need the CRM's `POST /lms/whatsapp` (round 6) and the owner's Pinbot approvals. The code ships switched off, and the coordinator-reissue fallback stays until both are done.
- **PDFs are new.** Certificate and receipt PDFs need a server-side renderer (no PDF generation exists today). Choose the library in U10.
- **Mapping removal changes what the CRM sees.** No admission waits for curriculum any more. Tell the CRM in the round 6 document so its "Waiting for batch" expectations match.
- **Dev database.** Apply migrations in place. Rebuilding `nipunalms-dev` collides student codes with the CRM's stale `lms_user_id` values; if a rebuild is unavoidable, tell the CRM first so it can run `flask lms backfill`.
- **E2E on a clean database.** Run each spec file on its own freshly seeded scratch database (DEVELOPMENT.md Part A). After U18 every spec passes that way, except that the specs that book a class for today cannot run after about 22:20 IST (see the U18 "As built" block).
- **The owner's servers.** :5060 has no reloader; restart it after each phase. All checks use :5061 / :5175.

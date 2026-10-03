# Gap fix plan — LMS against approved modules 14–27

## Context

A gap review compared the approved module PDFs (`~/Downloads/CRM  & LMS/LMS MODULE/`, modules 14–27) with the code. It found **109 gaps** that are not in the existing backlog (`docs/DEVELOPMENT.md` Part E) or the CRM open items. Of these, 36 are high, 62 medium and 11 low. Each gap, with the spec text, the code and file evidence, is in [GAPS.md](GAPS.md) (IDs G001–G109).

Several gaps are bugs or privacy leaks in features that are already built. The rest are missing rules, approvals and data the specs require. A production-readiness check also found no deployment, cron or backup setup. The goal is to bring the LMS in line with the approved specs in ordered phases, fixing correctness first.

**Decisions taken with the user (2026-10-03)**
- **Placement:** the LMS keeps the learning side only: internship records, career profile, CV review, and the support period tied to completion. Placement cases, opportunities, interviews and outcomes go to the CRM (D5) in the round 4 request.
- **Under-18 learners:** the CRM sends date of birth and guardian details in `AdmissionQualified` (round 4). The LMS stores them and applies the rules.
- **Email:** deferred along with WhatsApp. The per-channel notification model is built now, with in-app as the only live channel.
- **Delivery:** one commit per phase, directly on `main`.
  - Each commit carries its own migration, tests and doc updates.
  - No co-author trailer (memory rule).

## Conventions every phase follows

- **Migrations:**
  - One numbered file per phase, starting at `db/099_*.sql`.
  - Header lines are `-- NNN: purpose` and `-- Depends on:`.
  - Every file must replay cleanly from an empty database, because `flask create-test-db` and `create-dev-db` rebuild from scratch.
  - Enum CHECKs are dropped and re-added with the full list.
  - A changed view is handled by dropping its dependants in order and recreating them. The views in `db/040_attendance_certificates.sql` have no `OR REPLACE`.
  - New settings go in `app_settings` with `ON CONFLICT DO NOTHING`.
- **Backend:**
  - Code is layered routes → controllers → services → repositories.
  - Reuse these helpers:
    - `services/scope.py` (`require_branch`, `trainer_batch_ids`, `visible_branch_ids`)
    - `services/context.py` role tuples (the founder role code is `FOUNDER_CEO`)
    - `notify()` (`services/notifications.py`) with a unique `event_key`
    - `audit.record()`
    - `settings_repo.get_int`
    - error classes in `services/errors.py`
  - Background work becomes a job registered in `services/jobs.JOBS`.
- **New shared helper (phase 3):** `services/approvals.py`, with `require_independent(requester_id, approver_id, message)`. It replaces the inline checks in `attendance.decide_correction`, `certificates.approve` and `curriculum.approve`.
- **New shared helper (phase 4):** `config/working_days.py`, with `is_working_day` and `add_working_days(date, n, branch_id)`, backed by the academic calendar.
- **Tests:**
  - Add one `backend/tests/test_<area>.py` per slice, using the existing fixtures: `make_user`, `login`, `make_student`, `make_batch`, `make_session`, `allocate`, `crm_event`, and the `world` / `attendance_world` / `assessment_world` builders.
  - Role tests use the existing matrix style: 403 for a role without permission, 404 for another branch, 422 for a business rule.
- **Each commit:**
  - The full `pytest` run passes, and `npx tsc --noEmit` passes.
  - Playwright runs for the touched screens.
  - Update `docs/API.md` and `docs/DATABASE.md`, and remove closed items from `DEVELOPMENT.md` Part E.
  - Reseed the dev database with `flask create-dev-db` and the seed.

---

## Phase 1: correctness and privacy fixes (migration 099)

1. **Question bank scope** (`services/questions.py`, `repositories/questions.py`)
   - Trainers see only questions for courses of their current batches, using `batch_trainers` via `batches_repo.batch_ids_for_trainer`. Moderators (Academic Coordinator, Super Admin) keep branch scope.
   - The filter is per branch, because a user can be a trainer at one branch and a coordinator at another.
   - Apply it in `_load` and `list_stmt`. That covers get, update, approve, retire and new_version.
2. **Timed-out attempts:**
   - Add a new job `attempts-expire`. It uses the unused `tests_repo.expired_in_progress()` and calls `attempts.expire_if_due` on each attempt.
   - Staff attempt lists (`repositories/tests.py attempts_stmt`) also show In Progress and Timed-out attempts.
3. **Notification scope:**
   - Add `notifications.role_code`. `notify()` stores the role it fanned out on.
   - `repositories/notifications.py` (`get_for_recipient`, `list_stmt`, `categories`, `counts`, `mark_all_read`) adds a check that the user still holds that role at `branch_id` or company-wide, reusing `_active_scope_condition()` from `repositories/users.py`.
   - Backfill `role_code` from the existing `event_key` and category where it can be derived.
4. **Certificates:**
   - `open_eligibility` opens only the Course Completion Certificate. The Internship Certificate waits for internship evidence (phase 8).
   - `crm._transfer` moves certificate entries that aren't issued to the new service branch, and records an audit entry.
5. **Attendance views:**
   - Recreate `attendance_grid` → `enrolment_attendance`, `enrolment_covered_topics` → `enrolment_required_learning` → `enrolment_progress`.
   - Expectations start at the first `batch_allocations.effective_from`, not at `joining_date`. `joining_date` stays as "first attended".
   - A recovery counts only when `Completed`.
   - Update `test_attendance.py` expectations.
6. **CRM replay:**
   - `_admission_qualified` and the other notifying handlers skip `notify()` when the event is a historical import. That is an envelope flag `historical: true` (added to `PAYLOAD_RULES`), or `occurred_at` older than a new setting, `crm_notify_max_age_hours` (default 72).
   - Original dates are kept.
7. **Staff-only content:**
   - Add `content_items.staff_only BOOLEAN NOT NULL DEFAULT FALSE`.
   - Exclude these items in `item_matches_enrolment` and `released_candidates`.
   - Add the field to the create and edit forms in `features/academic/content-review.tsx` and the trainer content screen.
8. **Gap register:** mark items closed in [GAPS.md](GAPS.md) as each phase lands.

**Tests:** for each item, a failing test first, then the fix.

## Phase 2: deployment and operations (no migration)

Mirror the CRM's EC2 setup (`~/nipuna-crm/docs/DEVELOPMENT.md` Part C):
- Add a `deploy/` folder with:
  - `gunicorn.conf.py`
  - `nipunalms.service` (systemd, `127.0.0.1:5060`)
  - an nginx site that serves `frontend/dist` and proxies `/api`
  - a `crontab` that runs `flask --app app jobs run` every 10 minutes
  - `backup.sh`, a nightly `pg_dump` with 14-day retention
- Add `DEVELOPMENT.md` Part F: server layout, redeploy, migrations, backups.
- Set the security controls `BACKUPS` and `HTTPS` to Verified only after a real run.
- **No deploy happens without explicit approval.** This phase only adds the files and documentation.

## Phase 3: governance and approvals, plus the CRM round 4 request (migration 100)

- **`services/approvals.py`:** add the independent-approver helper and move the three existing inline checks onto it.
- **Curriculum (Module 14 §5):**
  - Academic Coordinators draft, review, submit and return.
  - Approve, activate and retire need `FOUNDER_CEO` or `SUPER_ADMIN`, through a new `CURRICULUM_APPROVER_ROLES` in `delivery_access.py`. `_approvers()` notifies those roles.
  - Update `features/academic/curriculum.tsx` actions, and give the founder workspace a curriculum approvals list.
- **Certificates (Module 22):**
  - **Fee gate:** eligibility requires `finance_summaries.payment_completion = 'Paid'` (or `balance <= 0`) for paid admissions. Complimentary admissions follow their paid parent.
  - **Financial-release exception:** a new `certificate_financial_exceptions` table (admission, outstanding amount, reason, certificate types, approver). Founder/CEO or Super Admin approve, independent of the requester. The exception does not waive the debt.
  - **Trainer confirmation:** `completion.decide(Complete)` requires the trainer's recommendation (`completion_reviews.trainer_recommendation`) before eligibility opens.
  - **Revocation:** Founder/CEO or Super Admin, with reason, evidence and an independent decision.
  - **Reinstatement:** a new action that keeps the revoked interval (`certificate_status_history`).
  - **Reissue and correction requests:** a new `certificate_change_requests` table. The Academic Coordinator requests, the Branch Manager approves independently, changed fields are recorded, and the old certificate stays valid until the replacement is issued.
  - **Public verification:** returns `Valid — Current Version`, `Superseded` (with the current number) or `Revoked`, plus branch and original issue date. Add a public SPA route `/verify/:number`, with `/verify` added to the public paths.
- **AI kill switch (Module 24 §11):**
  - A new `ai_feature_controls` table (scope, reason, actor, time, restoration).
  - Super Admin can disable per feature or branch; Founder/CEO can disable company-wide.
  - `ask_nipuna` checks it before answering.
- **CRM round 4 request:**
  - Write `nipuna crm-docs/LMS_ROUND4_REQUEST.md` asking for:
    - date of birth and guardian (name, relation, verified contact, scope) in `AdmissionQualified`
    - consent, stop-contact and offboarding events
    - the `historical` flag
    - cancellation and refund fields
    - the new batch states (phase 6)
    - placement service endpoints (D5)
  - Add it to `CRM_INTEGRATION.md` §4.

## Phase 4: academic calendar and working days (migration 101)

- **New tables:**
  - `academic_calendar` for central holidays.
  - `branch_closures`: the Branch Manager approves. Each closure lists the affected sessions and proposes replacements for Branch Manager approval.
- **`config/working_days.py`:** the shared working-day helper, used from here on.
- **Allocation escalation (Module 15):**
  - Deadline: one working day after admission when a seat exists, otherwise 48 hours before the first class.
  - At 24 hours before the committed start, escalate to Founder/CEO or Super Admin. Rework the `allocation-escalation` job.
- **Attendance confirmation (Module 21):**
  - Track whether the trainer confirmed attendance by the end of the same working day.
  - New job `attendance-unconfirmed`: alerts the Academic Coordinator on the next working day. The confirmation date is kept separately from the class date.
- **Review clocks:** closes the backlog item "Review clocks". Assignment and test review targets of 3, 5 and 7 working days now run on the calendar.
- **UI:** a calendar admin screen under `/admin` and `/branch/operations`.

## Phase 5: curriculum model (Module 14) (migration 102)

- **Topics:**
  - Add `outcome`, `topic_class` (Required, Recommended, Optional; `is_required` is kept as a generated column so the views stay stable), `estimated_minutes` and `weight`.
  - Add a `curriculum_topic_dependencies` table.
- **Versions:**
  - Add totals: `instructional_minutes`, `independent_minutes` and `total_minutes`, with an `hours_verified` flag. Unverified hours show as **Pending**.
  - Expand the submit blockers in `_blockers` to require outcomes, hours and weights.
- **Assessment requirements:**
  - Add a `curriculum_assessment_requirements` table: required assignment or test per module/topic, outcome, weight, pass rule and completion contribution.
  - Phase 7 links to it.
- **Combos:**
  - Add `curriculum_version_components`: a parent version pins the exact track and booster versions. Booster hours are shown separately.
  - Borrowing an equivalent standalone version needs a recorded equivalence review by the Academic Coordinator. This replaces the silent fallback in `crm._map_curriculum`.
- **Student mapping:**
  - Add `academic_mappings`: the side-by-side comparison, migration plan, approving receiving Academic Coordinator and student acceptance.
  - Add `learning_credits`: original evidence, reviewer, rule and version, credited outcome.
  - New equivalence rules need Founder/CEO or Super Admin, independently approved.
  - The allocation version-mismatch "warn" in `batch_allocations.review` becomes a **fail** unless an approved mapping exists.
- **Mapping Pending:** enrolments get a named owner and recovery task, shown in the exception queue.
- **Branch variations:** add `curriculum_variations` (branches, batches, versions, kind, approver). Removing a required topic needs a constraint and a remedial plan.
- **Reusable versioned modules and topics (G059):**
  - Add `curriculum_items` and `curriculum_item_versions`. Published versions reference exact item versions, and editing a shared item creates a proposed version.
  - **This is the largest single change.** Build it last in the phase, behind the other items.
- **UI:** rework `features/academic/curriculum.tsx`: a topic editor with the new fields, a dependency picker, a totals panel, a combo pinning view, and a mapping/credit dialog from the allocation queue.

## Phase 6: batches and delivery operations (Modules 15 and 16) (migration 103)

- **Batch lifecycle:**
  - Add the states `Proposed`, `On Hold` and `Archived`. The existing values are kept for CRM compatibility: Forming = Draft, Starting is shown as Confirmed, Running is shown as In Progress.
  - The Branch Manager confirms Proposed → Starting against the 7-point readiness checklist (extend `batches.readiness_checks`).
  - Completed requires its obligations to be closed. Archived is allowed only after Completed or Cancelled.
- **Batch fields:**
  - Add `batch_type` (Group, Individual, Corporate), `schedule_pattern` (Regular, Weekend, Fast-track) and an editable `display_name`.
  - Split capacity into `classroom_capacity`, `lab_capacity` and `online_capacity`. An increase needs a review.
- **Track batches:** allow `batches.component_id`. `batch_allocations.enrolment_track_id` already exists; allocate per track and move one component without moving the admission.
- **Transfers:**
  - Add a `batch_transfer_requests` table. A within-branch move needs Branch Manager approval, independent of the requester.
  - An interbranch move arrives from the CRM `_transfer`, and the receiving Academic Coordinator records the academic mapping (phase 5).
- **Material changes:** add `material_changes` and `material_change_acceptances` (old and new plan, reason, approver, per-student agreement) before the change applies to that student.
- **Sessions:**
  - Add the states `Confirmed` and `Partially Held`.
  - Add `actual_start`, `actual_end`, `break_minutes`, `delivered_minutes`, an unfulfilled note, and `purpose` (Regular, Replacement, Remedial, Extra) with a `replaces_session_id` / recovery link.
  - Same-day log check: missing logs create Academic Coordinator review tasks.
- **Delayed starts (Module 16):**
  - Add the `session_disruptions` table.
  - At 5 minutes students are told; at 15 minutes a disruption is recorded and the Academic Coordinator / Branch Manager is alerted.
  - A new `session-delay-check` job runs every few minutes. Undelivered minutes feed the minute-based attendance backlog item.
- **Meet:**
  - Store `meet_space_id`, `calendar_event_id`, `series_id`, `conference_record_id` and `hosting_branch_id`.
  - Add a `session_hosts` table (host, backup, guests with approval).
  - Add a `meet_incidents` table for compromised links.
  - Add a Meet operations view in `/academic/schedule`.
- **Conflict checks:** add the student's other compulsory classes, assistant availability and online capacity. Overriding an advisory warning needs a recorded reason.
- **Merge and split:** add a `batch_successions` table.
- **Cover:** add substitute/assistant cover approval (the Branch Manager approves, the Academic Coordinator verifies). A substitute no longer has to be pre-assigned.
- **Student preferred slots:** add `slot_preferences` (Requested, Waitlisted, Confirmed). A request reserves no seat.
- **Shared classes across batches (G067):**
  - Add `session_rosters`, linking one session to several batches. Hours are counted once.
  - **Large: do this last in the phase.**

## Phase 7: assessments (Modules 19 and 20) (migration 104)

- **Required work must come from the curriculum:**
  - `assignments` and `tests` reference a `curriculum_assessment_requirement_id`. `is_required` is derived from it, so trainers can't invent required work.
  - Add `rubrics` and `rubric_criteria`, plus weight and pass rule. A required item can't be released without them.
- **Assignment targeting:** add `assignment_targets` (whole batch, selected enrolments, or individual recovery), each with a reason.
- **Brief versions:** add `assignment_versions`. Each student keeps the version they were given. A material change after release needs Academic Coordinator review and notice.
- **Submissions:**
  - Pre-deadline replacement is blocked once `review_started_at` is set.
  - Repository and link submissions store the commit, release or version and the access scope. The link is checked at review time.
- **Completion dimension:** Pending, Completed or Excused. Excused needs Academic Coordinator approval.
- **Final projects:** add `project_milestones` and `project_vivas`, plus contribution evidence.
- **AI-use rule:** enforce the rule. A disclosure (tool, assistance, what the student checked) is required when the rule needs one.
- **Tests:**
  - Add `latest_start_at`. Starting checks the curriculum version and prerequisites.
  - Practice quizzes show explanations and correct answers after submission, plus latest and best scores.
  - Coding tests get language, limits, an I/O contract, and sample/hidden cases. The Academic Coordinator approves the cases; hidden cases are hidden from unauthorised staff.
  - Question metadata: curriculum version compatibility, outcome, language, rights and history.
- **Attempt incidents:** add `attempt_incidents`. The Academic Coordinator authorises restored time, continuation or a replacement attempt. An institute-side failure does not use up an attempt.
- **Jobs:**
  - `assignment-overdue-review`: a trainer support-review task at 3 days overdue.
  - `assessment-unattempted`: a support or reassessment task after a window closes, never an automatic zero.

## Phase 8: attendance, completion and certificates (Modules 21, 22 and the learning side of 23) (migration 105)

- **Attendance:**
  - Add a **Disputed** flag on attendance records. Pending and Disputed rows are excluded from both sides of the calculation.
  - Progress shows the cutoff, coverage and a `Provisional` / `Not Yet Calculable` label.
  - An approved pause (`enrolment_pauses` if it's missing) changes expectations and suppresses inactivity alerts.
  - A correction after completion keeps the original approval, flags an academic review, and records a recalculation trace.
  - Add `participation_mode` (in-person or online) on hybrid entries.
- **Certificates:**
  - Approval is bound to an evidence snapshot hash and the rule and template versions. Eligibility is rechecked immediately before issue.
  - Add bulk and paired review.
  - Add separate processing, document and delivery dimensions. Delivery is in-app only for now.
  - Add an issue-register CSV export and dashboard filters.
- **Internships:** add `internship_programmes` and `internship_records` (organisation, supervisor, dates, verified duration and work, Academic Coordinator verification). These open Internship Certificate eligibility.

## Phase 9: content and recordings (Modules 17 and 18) (migration 106)

- **Recordings:**
  - Add a recording notice and acknowledgement (student and trainer). Guardian authorisation comes in phase 12.
  - Add milestone timestamps: Configured, Started, File Generated, Playback Ready, Released. Add the exception states Review Required and Failed.
  - The release gate expands to the 7 checks.
  - Add `recording_versions`. An edit to a published recording needs independent review.
  - Downloads need an approved exception record.
  - Staff can record an extension request on a student's behalf.
  - Expiry shows a date and time (end of day IST). A new job `recording-expiry-notice` warns students before expiry.
- **Content:**
  - Add asset metadata: owner, version, source and rights, reviewer, size, duration or study time. Add the types slides, handouts, images and notebooks.
  - External links get an owner, rights and checked-at fields. A new job `content-link-check` raises a broken-link exception and withdraws the link.
  - The student library gets Recently Added/Updated and the states Scheduled, Temporarily Unavailable and Withdrawn, with explanations. Add scheduled release (closes a backlog item).
  - Batch materials stay available after a transfer, following historical access rules.
  - Add download and playback events. Unsupported tracking shows "Not Recorded".

## Phase 10: notifications and integrations register (Modules 26 and 27) (migration 107)

- **Notification model:**
  - Add `notification_messages` (one logical notice) and `notification_attempts` (per channel; in-app is live, email and WhatsApp stay Queued/Suppressed until enabled).
  - States: Queued, Suppressed/Obsolete, Sending, Accepted, Delivered, Failed, Uncertain, Staff Recovery Required.
  - Add revised and cancelled notices that link to the notice they replace.
  - A required action links to its source record. A recipient can no longer close a task just by acknowledging the notice.
- **Message centre:** filters for course/enrolment and date; My, Team and Branch views for staff.
- **Preferences:** a history table, plus language and timing preferences. Add `notification_templates` with versions; each message records its template version and language.
- **CRM notices:** cancellation, payment and refund events notify the student and staff. A provisioning failure creates a recovery task.
- **On-duty cover:** add an `on_duty_roster` per role and branch. Notices go to whoever is on duty. A missing roster raises a configuration exception.
- **Integrations register:**
  - Statuses: Pending Verification, Manual, Planned, Live Verified.
  - Add the mandatory per-connection fields and manual-fallback records.
- **Freshness:** add a `freshness_threshold_minutes` setting per CRM source. Stale or unavailable data is shown as such, never as zero.
- **CRM restrictions intake:** consent, stop-contact and offboarding (depends on round 4).

## Phase 11: reports, dashboards and AI (Modules 25 and 24) (migration 108)

- **Period selector:** Today, Yesterday, This/Last Week (Monday to Sunday, IST), This/Last Month, Custom. Every report service takes `period_from` and `period_to`.
- **Report envelope:** each report carries Period, Scope, Filters, Cutoff, Last Refresh, Completeness, Requested by and Generated at.
- **Exports:**
  - Add `services/exports.py`: CSV with the standard library, Excel with **openpyxl**, PDF with **reportlab**, plus a print stylesheet.
  - Add a `report_exports` audit table. Exports are limited to the user's scope.
  - Add `scheduled_reports` (schema and job; email delivery deferred).
- **Dashboards:**
  - Role home dashboards show the approved first three figures for Trainer, Academic Coordinator and Super Admin.
  - The academic dashboard adds students below the attendance minimum, missing or awaiting-review required work, open support, committed-start risk, planned vs delivered hours, and separate certificate queues.
- **Learning-side career report:** opted-in students, CV reviews, internships, readiness. Placement figures wait for the CRM.
- **AI:**
  - Reported answers are routed by type: academic to the Academic Coordinator with trainer input, financial to Super Admin, branch operations to the Branch Manager, privacy issues to Super Admin, policy to the Founder.
  - Ask Nipuna gets read-only sources for certificates and fee summaries, with dates, plus a "Data unavailable" answer.

## Phase 12: career (learning side) and guardians (migration 109, after CRM round 4)

- **Career support period:**
  - It is tied to the qualifying enrolment's approved completion (six months, late opt-in keeps the remaining time) and is enforced.
  - The career profile gets verification states (Verified, Student Reported, Pending).
  - CV review has a reviewer, a backup and a 3-working-day clock.
  - Self-sourced applications are recorded separately.
- **Guardians:**
  - Add `students.date_of_birth` and a `guardians` table from the CRM.
  - Under-18 rules apply to recording acknowledgement, notification copies, guardian access to attendance updates, and placement sharing. Access is reviewed at 18.
- **Placement handover:** the case, opportunity register, interviews and outcomes move to the CRM (D5). The LMS Career screen reads and submits through the CRM endpoints once the CRM builds them.

---

## Critical files (representative)

- **Backend services:** `questions.py`, `attempts.py`, `notifications.py`, `certificates.py`, `crm.py`, `content.py`, `curriculum.py`, `batches.py`, `batch_allocations.py`, `class_sessions.py`, `assignments.py`, `submissions.py`, `tests.py`, `completion.py`, `recordings.py`, `academic_reports.py`, `dashboards.py`, `jobs.py`, `ask_nipuna.py`
- **New backend modules:** `approvals.py`, `exports.py`, `config/working_days.py`
- **Repositories:** `questions.py`, `notifications.py`, `tests.py`, `content.py`
- **Database:** `db/040_attendance_certificates.sql` (views, recreated in 099), new `db/099`–`db/109`
- **Frontend:**
  - `features/academic/` (curriculum, batches, batch-panel, schedule, assessments, certificates, completion, content-review, reports)
  - `features/shared/` (certificate-register, notification-centre)
  - `features/founder/dashboard.tsx`
  - `features/student/` (resources, recordings, tests)
  - `auth/access.ts` (public `/verify`)
- **Docs:** `API.md`, `DATABASE.md`, `DEVELOPMENT.md` (Part E, new Part F), `CRM_INTEGRATION.md`, `GAPS.md`

## Verification

- **Each phase:**
  - `cd backend && ../venv/bin/python -m pytest -q`. It passes 611 today and must pass with the new tests.
  - `cd frontend && npx tsc --noEmit` and the Playwright specs for the touched screens.
  - `flask create-dev-db` plus the seed, then a manual run of each affected role through the app on :5174 / :5060.
- **Phase 1 tests:**
  - A trainer cannot read another course's question (404).
  - An expired attempt is submitted by `flask jobs run attempts-expire`.
  - A transferred coordinator no longer sees the old branch's notices.
  - Course completion leaves the Internship Certificate untouched.
  - A transfer moves pending certificates.
  - Absences before the first Present count.
  - An Approved (not Completed) recovery doesn't count.
  - A replayed historical `AdmissionQualified` sends no notice.
  - A staff-only item is invisible to students and their file download returns 404.
- **CRM-facing phases (3, 6, 10, 12):** re-run the smoke test in `DEVELOPMENT.md` Part C with the local CRM and check `GET /integrations/crm/status`.
- **Phase 2:** checked on a local gunicorn + nginx run. A server deploy waits for explicit approval.

## Risks and notes

- **Attendance numbers drop.** Phase 1 changes attendance percentages for current students. That is intended by the spec; note it in the commit and in Part E.
- **Batch states and the CRM.** New batch states change what the CRM pulls in `batch_crm_state`. Existing values are kept, and new ones go in the round 4 request before phase 6 ships.
- **CRM round 4 dependencies.** Phases 10 (restrictions intake) and 12 (guardians) depend on the CRM. If round 4 slips, those items stay open in `GAPS.md`.
- **Largest items.** G059 (reusable versioned curriculum items) and G067 (shared classes) are the two largest. Each sits last in its phase so it can be split out without blocking the rest.

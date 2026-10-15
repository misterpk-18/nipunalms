# Nipuna LMS — Database

The `nipunalms` PostgreSQL schema: what each migration creates and the rules the database enforces. Derived from the
prototype at https://nipuna-lms-prototype.lovable.app/ (sample data only) and the approved LMS modules 14–27. The API on
top of it is in [API.md](API.md); the CRM contract in [CRM_INTEGRATION.md](CRM_INTEGRATION.md).

**Core flow:** CRM qualifying payment → `AdmissionQualified` event → Student (one per CRM Person) + LMS login + Admission
projection + Enrolment (paid standalone / combo with tracks / complimentary) → curriculum mapping → batch allocation →
Class Sessions → content, recordings, assignments, tests, attendance → progress → completion review → Certificate
Register.

Every academic record is branch-scoped through its batch or the enrolment's service branch (NIT-GNT Guntur, NIT-VIJ
Vijayawada).

---

## How migrations work

- The SQL files in `db/` are the source of truth. Models map existing tables; nothing calls `db.create_all()`.
- Files are applied in numeric order, each in its own transaction:

  ```bash
  psql -d nipunalms -v ON_ERROR_STOP=1 -1 -f db/<file>.sql
  ```

- The dev replica (`nipunalms-dev`) and the pytest database (`nipunalms_test`) are rebuilt from the same files. See
  [DEVELOPMENT.md](DEVELOPMENT.md#3-databases).
- A new migration takes the next free number, says what it depends on in its header, and gets a section below.

| Migration | Area | Status |
|---|---|---|
| `001_foundation.sql` | Foundation | ✅ |
| `002_catalog_curriculum.sql` | Catalogue & curriculum | ✅ |
| `003_students_enrolments.sql` | Students, enrolments, CRM projection | ✅ |
| `004_batches_sessions.sql` | Batches & class sessions | ✅ |
| `005_crm_alignment.sql` | CRM vocabulary and shapes; academic state and batches back to the CRM | ✅ |
| `010_delivery.sql` | Delivery | ✅ |
| `020_content_recordings.sql` | Content & recordings | ✅ |
| `030_assessments.sql` | Assessments | ✅ |
| `040_attendance_certificates.sql` | Attendance, progress & certificates | ✅ |
| `050_student_services.sql` | Student services | ✅ |
| `060_admin_security.sql` | Admin & security | ✅ |
| `070_crm_certificates.sql` | Certificates and completion authoriser to the CRM | ✅ |
| `080_exception_queue.sql` | Exception queue | ✅ |
| `090_crm_round1.sql` | Fixes from the CRM's round-1 integration run | ✅ |
| `095_crm_round2.sql` | The status pull the CRM applies in round 2 | ✅ |
| `096_crm_branches_finance.sql` | Branch and finance-snapshot events from the CRM | ✅ |
| `097_crm_round3.sql` | Curriculum catalogue for the CRM, CRM curriculum mapping | ✅ |
| `098_batch_timetable.sql` | Batch timetable for CRM sales; readiness and seats left in the pull | ✅ |
| `099_gap_fixes.sql` | Gap fix plan phase 1: notice role, staff-only content, historical CRM events, attendance from the seat | ✅ |
| `100_governance.sql` | Gap fix plan phase 3: certificate requests and fee exceptions, status history and reinstatement, AI controls | ✅ |
| `101_academic_calendar.sql` | Gap fix plan phase 4: company holidays and branch closures, working weekdays | ✅ |
| `102_curriculum_model.sql` | Gap fix plan phase 5: the Module 14 curriculum model | ✅ |
| `103_batches_delivery.sql` | Gap fix plan phase 6: batch lifecycle and requests, class logs, live-class operations (Modules 15, 16) | ✅ |
| `104_crm_curriculum_removal.sql` | Round 5: the CRM holds no curriculum (mapping event, catalogue mirror and curriculum fields removed) | ✅ |
| `105_curriculum_mapping_removed.sql` | UX phase U1: the *Curriculum Mapping Pending* enrolment state, its owner column and its exception source are removed | ✅ |
| `106_coordinator_merged_into_branch_manager.sql` | UX phase U2: the Academic Coordinator role is retired and merged into the Branch Manager | ✅ |
| `107_whatsapp_outbox.sql` | UX phase U6: WhatsApp through the CRM (outbox, templates, switch off by default) | ✅ |
| `108_sign_in_and_accounts.sql` | UX phase U7: self-service password reset codes, staff activation, unlock | ✅ |
| `109_topic_progress.sql` | UX phase U8: topic progress for the student Home and My Learning | ✅ |
| `110_whatsapp_status_events.sql` | CRM round 6: WhatsApp delivery status events | ✅ |
| `111_student_account_and_support_files.sql` | UX phase U11: support attachments, email change codes, payment instructions | ✅ |
| `112_class_flow.sql` | UX phase U12: the trainer's class flow progress and covered topics | ✅ |
| `113_access_extension_recommendation.sql` | UX phase U15: Branch Manager recommendation on access extensions beyond the limit | ✅ |
| `114_curriculum_activation_date.sql` | UX phase U16: Approve & activate a curriculum version on a chosen day | ✅ |
| `115_super_admin_setup_calendar_assign.sql` | UX phase U17: Setup owners, cancelled closures, assigned issues | ✅ |

---

## 001 — Foundation

| Table | Purpose |
|---|---|
| `code_counters` | Per-prefix, per-year counters behind the human codes (`NIT-STU-2026-004182`, `NIT-GNT-BAT-2026-000001`, …) |
| `branches` | NIT-GNT (mailbox trainer@nipunatechnologies.com), NIT-VIJ (contactus@nipunatechnologies.com) |
| `roles` | STUDENT, TRAINER, BRANCH_MANAGER (per branch); ACADEMIC_COORDINATOR is retired (`is_active = FALSE`, db 106); SUPER_ADMIN, FOUNDER_CEO (company-wide) |
| `users` | Staff and student logins; case-insensitive unique email; `student_id` (unique) links a login to its student |
| `user_role_scopes` | Role per branch with validity window; one live scope per user / role / branch |
| `user_sessions`, `active_sessions` (view) | Opaque session tokens (hash only), idle + max lifetime, fresh auth |
| `app_settings` | Key / value settings: session timeouts, activation token hours, AI daily limit, password minimum length, … |
| `audit_log` | Append-only change history |
| `integrations` | Register: requirement, configuration status, verification status, owner, last check (Google Workspace, Meet, Drive, CRM, WhatsApp, email, telephony, AI provider) |
| `notifications` | In-app notifications; one per (`event_key`, recipient); separate delivery / read / acknowledged / action states |
| `activity_events` | Learning activity (logins, views, completions) for engagement and "last activity" |

**Rules enforced:** company-wide roles take no branch and branch roles need one; `audit_log` rejects UPDATE / DELETE.

## 002 — Catalogue & curriculum

| Table | Purpose |
|---|---|
| `courses` | Mirror of the CRM Course Master (`CourseUpserted`): code, title, `is_combo`, status |
| `course_components` | Combo tracks: `<combo>/T1`… (Main track) and the included booster, which keeps its own course code (e.g. NIT-CRS-019) |
| `curriculum_versions` | Per course or per track: label, status Draft → Under Review → Approved → Active → Retired |
| `curriculum_modules`, `curriculum_topics` | Ordered modules and topics; topics have `is_required` |

**Rules enforced:** only a combo has components (090 adds a trigger for the reverse direction); a track version must
belong to its course; one Active version per course / track; labels unique per course / track.

## 003 — Students, enrolments, CRM projection

| Table | Purpose |
|---|---|
| `students` | Student Master, one per CRM Person (`crm_person_id` unique); `student_code` = `lms_user_id`; optional email; mobile never unique; original / service branch; language; activation status; `provisioned_at` |
| `student_activations` | Single-use activation tokens (hash, expiry, used, channel); one outstanding token per student |
| `admissions` | CRM projection: `crm_admission_id` unique, `admission_code`, **one course**, original / service / collecting branch, `source_version` |
| `enrolments` | Paid standalone, separately purchased, combo, complimentary; status from *Provisioning Pending* to *Completed*; joining date; access window; certificate status |
| `enrolment_tracks` | Combo enrolment → component track and its curriculum version |
| `finance_summaries` | Read-only per-admission money snapshot from the CRM (fee, verified paid, balance, instalments, receipts) |
| `crm_events` | Inbox: every CRM event once (`event_id`), payload, `source_version`, status Received / Applied / Ignored — stale / Failed |
| `crm_outbox` | Values the CRM stores about the LMS, queued in the same transaction as the change |
| `admission_lms_status` (view), `admission_lms_state` | Per-admission `lms_status` in the CRM's vocabulary and the last value sent |

**Rules enforced:** students are never deleted; `student_code`, `lms_user_id` and `crm_person_id` are immutable;
enrolment student = admission student; one enrolment per admission and course; only combo courses have Combo
enrolments.

The CRM columns these tables feed, and the outbox events that carry them, are listed in
[CRM_INTEGRATION.md §2.2](CRM_INTEGRATION.md#22-lms--crm-what-the-crm-stores-about-the-lms).

## 004 — Batches & class sessions

| Table | Purpose |
|---|---|
| `batches` | `batch_code` (what the CRM stores as `lms_course_id`), `crm_batch_id`, course, branch, curriculum version, capacity, mode, state Forming → Starting → Running → Full → Completed / Cancelled, readiness Ready / Blocked / Pending Verification + reason + recovery owner |
| `batch_trainers` | Trainer ↔ batch (Lead / Co-trainer) with dates; one live row per trainer and one lead per batch |
| `batch_allocations` | Enrolment (or combo track) ↔ batch with effective dates; one active allocation per enrolment / track; history kept |
| `class_sessions` | Actual Class Sessions: batch, topic, trainer, scheduled start / end, mode, room, Meet link + status, state Scheduled / Live / Delivered / Cancelled / Rescheduled |

**Rules enforced:** `batch_code` is immutable; capacity can't drop below allocated students; a trainer must hold the
Trainer role at the batch's branch; allocation course and branch must match the enrolment; no allocation into a closed
or full batch; the track must belong to the enrolment; the session trainer must be assigned to the batch; session end
after start.

## 005 — CRM alignment

Checked against the CRM's schema and docs.

| Change | Why |
|---|---|
| `course_status` + `Archived` | The CRM's course status has it |
| `students.crm_person_code` | The CRM's `PER-GNT-00148`, for display |
| `admissions.complimentary_of_admission_id`, `seat_type`, `planned_start_date` | The CRM grants a complimentary course as **its own admission** linked to the paid one; seat type and planned start come from its delivery plan |
| `check_enrolment_links()` (replaced) | A complimentary enrolment may hang off the paid admission it is complimentary to |
| `enrolments.completed_at` (trigger-stamped) | Feeds the CRM's `admissions.academic_completed_at` |
| `finance_summaries` + pending verification, waived, refunded, payment completion, invoice numbers, instalments | The rest of the CRM's `admission_balances` / `installment_dues` |
| `crm_enrolment_status()`, `crm_delivery_mode()`, `crm_batch_status()` | LMS → CRM vocabulary |
| `admission_academic_state()`, `admission_lms_state.academic` + triggers → `AdmissionAcademicsChanged` | Enrolment status, curriculum status, allocations with joining date, completion: the CRM columns the LMS owns. Reads the enrolment whose course is `admissions.course_id` |
| `batch_crm_state()`, `batch_crm_state` table + triggers → `BatchUpserted` | The CRM's `batches` become a mirror keyed by `lms_course_id` |
| `queue_crm_state()` | An undelivered outbox row for the same admission / batch is superseded by the latest state (the CRM needs the state, not every step) |

## 010 — Delivery

| Object | Purpose |
|---|---|
| `curriculum_events` | Review trail per curriculum version (Created, Submitted, Returned, Approved, Activated, Retired) with from / to status, note and actor |
| `batch_events` | Batch history: created, state changed, readiness, trainer and curriculum changes |
| `session_changes` | Every reschedule, cancellation and substitute trainer: reason, original and new slot, notice hours, `short_notice` |
| `session_change_requests` (+ type `reschedule_request_status`) | Trainer reschedule requests (Open / Approved / Rejected); one Open request per session (partial unique index) |
| `meet_events` | Meet association log: requested, link associated, failed, reset; organizer email; the LMS never calls Google |

No earlier table is altered. Triggers added on the backbone tables: modules and topics of a non-Draft version cannot be
updated or deleted; batch lifecycle transitions; class-session transitions (a Live / Delivered / Cancelled session
cannot change time or trainer); a session topic must belong to the batch's course; one trainer cannot have two
overlapping open sessions. These apply to every later test and seed (a Delivered session's times are fixed).

## 020 — Content & recordings

| Table | Purpose |
|---|---|
| `content_items` | Library entry: `CNT-` code, type (PDF, Notes, Dataset, Code, Lab, Practice material, Link, Video link), placement (course, curriculum version, module, topic), branch, optional batch, download policy, status of the latest version, author, retirement |
| `content_versions` | One row per upload or link (v1, v2 …): file path / URL, size, change summary, review status, released at / by |
| `content_reviews` | Submission, review, release and retirement history with comments |
| `recordings` | `RCD-` code, one or more parts per class session, status Processing / Released / Partial / Held / Unavailable / Expired, Drive reference, duration, download policy, hold reason / partial note |
| `recording_exceptions` | `RX-0012` codes: Partial, Held, Unavailable, Integration Unavailable; owner role and person, Open / In Progress / Resolved, resolution note |
| `access_extension_requests` | `EXT-031` codes: enrolment, scope (Recording / Material / Both), reason, status, `needs_exception`, original and approved expiry, decision |

Settings added: `access_default_years`, `access_max_years`, `recording_check_hours`, `content_max_upload_mb`,
`content_dataset_max_upload_mb`.

**Rules enforced:** placement consistency (version of the course, module of the version, topic of the module, batch of
the course and branch); a version is a file xor a link; released versions need a release time; hold / partial /
resolution / rejection need a reason; a recording maps to a non-cancelled class session and is unique per session and
part; one open exception per session and issue; one pending extension per enrolment and scope; an exception's branch is
its session's branch; codes are immutable.

## 030 — Assessments

| Table | Purpose |
|---|---|
| `assignments` | Per batch, linked to a topic: kind, brief, attachments, required flag, max marks, release / due / closes (due + 7 days) times, resubmission limit, AI-use rule, named reviewer, status Draft / Released / Withdrawn (`ASG-0008`) |
| `assignment_submissions` | Versioned (v1, v2 …) text / file / link with attempt number, received time, late flag, review-started marker, receipt code `SUB-000012` |
| `submission_reviews` | One per version: Reviewed (marks) or Resubmission Requested (own deadline), feedback |
| `questions` | Question bank per course / branch / topic: 8 types, options, answer key, difficulty, tags, Draft / Approved / Retired, versions (`QB-0001`) |
| `tests`, `test_questions` | Practice quiz, module test, coding exercise, mock test, mock interview, final test: window, duration, attempts, pass marks, release status, AC approval; questions frozen with key and marks (`TST-0001`) |
| `test_attempts`, `attempt_answers` | Server clock (`started_at`, `deadline_at`), receipt `RCPT-T-00931`, auto / manual scores, grading status |
| `interview_slots` | Mock interview slots: Open, Slot Confirmation Pending, Confirmed, Completed; rating and feedback |
| `results` | Provisional, Moderated, Published marks per assignment or test and enrolment |

**Rules enforced:** the topic must belong to the batch's course; a submitted version cannot be edited; marks cannot
exceed the maximum; an approved question cannot be edited (new version instead); answers are refused after the deadline
and once an attempt is submitted; the receipt is issued once by a trigger; one attempt in progress per student and test;
one live interview booking per student and test; one result per student and item; a published result cannot change; a
moderated result needs a reason. No backbone table changes.

## 040 — Attendance, progress & certificates

| Object | Purpose |
|---|---|
| `attendance_records` | One row per Class Session × enrolment (Present / Absent / Late / Excused, remarks, marked_by / marked_at, correction fields). Only Live / Delivered sessions and seated enrolments |
| `attendance_recoveries` | `REC-0041` codes; Requested → Approved / Rejected → Completed with evidence; one live recovery per absence |
| `attendance_corrections` | Post-lock changes and student disputes; the decider cannot be the requester |
| Views `enrolment_batch_links`, `attendance_grid`, `enrolment_delivery`, `enrolment_attendance`, `enrolment_required_topics`, `enrolment_covered_topics`, `enrolment_required_learning`, `enrolment_engagement`, `enrolment_progress` | The four progress measures per enrolment |
| `completion_reviews` | Trainer recommendation, Branch Manager decision, evidence snapshot; one Open review per enrolment; Complete blocked by open recoveries |
| `certificates` | LMS Certificate Register (types Course Completion / Internship; statuses Not Yet Eligible → Eligibility Review → Awaiting Approval → Approved for Issue → Issued → Superseded / Revoked); number allocated at first issue, kept across versions |

Settings added: `attendance_lock_days`, `attendance_alert_threshold`, `engagement_window_days`,
`engagement_high_events`, `engagement_medium_events`, `complimentary_completion_rule_configured`.

**Rules enforced:** transition table and eligibility (Completed enrolment; complimentary rule configured), immutable
certificate number, reissue must follow the Superseded version, revocation needs a reason, Excused needs a reason,
rejected recoveries / corrections need a note. No backbone table is altered; a trigger keeps
`enrolments.certificate_status` in step with the live register entry.

## 050 — Student services

| Table | Purpose |
|---|---|
| `support_requests` | `SR-1042` codes; category, priority, status machine (trigger), named owner + role, escalation level, SLA due, resolution, reopen count |
| `support_messages` | Append-only thread and history (Message / Status / Escalation / Assignment / Reopened); internal remarks flagged |
| `notification_preferences` | Per user, group (Service / Learning reminders / Placement / Promotions & alumni) and channel; in-app cannot be off |
| `career_profiles` | Opt-in, support period, preferences, skills with confidence, sharing consent (separate), readiness |
| `cv_documents` | CV versions (`version_no` by trigger), review status, file path |
| `opportunities` | `OPP-0001`; Draft to Closed; Active needs a verifier who is not the creator |
| `applications`, `application_events` | One per student + opportunity + hiring cycle; every status change logged by trigger; closed statuses are final |
| `placement_outcomes`, `verified_placement_outcomes` (view) | Offer Received / Accepted / Joined; counted only when Verified with evidence by someone other than the recorder |
| `ai_queries` | Ask Nipuna question, answer, sources, tokens, fallback flag, status, feedback |

**Backbone changes:** `notifications` gains `channel` (In-app / WhatsApp / Email) and `delivery_note` (a Failed delivery
must say why). Settings: `ai_daily_limit` raised to 50 (Module 24 pilot limit), new `ai_daily_limit_staff` (100),
`ai_enabled`, `support_sla_hours` (48). New helper function `acting_user_id()`.

## 060 — Admin & security

| Table / change | Purpose |
|---|---|
| `integrations` (ALTER) | + `verified_by`, `verified_at`, `evidence`; CHECK `integrations_verified_needs_evidence` (Verified needs a person, a time, an evidence note and a Configured setup) |
| `integration_configuration_status` (ALTER TYPE) | + `Misconfigured` |
| `integrations` (rows) | + `MEET_ORGANIZER_GNT`, `MEET_ORGANIZER_VIJ` (per-branch organizer, Pending Verification), `HDFC_PAYMENTS` (CRM-owned feed), `PRODUCTION_AUTH` |
| `security_controls` | Security readiness register, seeded with 18 controls (scope enforcement, session idle / max, fresh auth, lockout, password policy, unique LMS login, activation token, audit immutability and decisions, temporary / emergency access, student MFA, file access, export scoping, AI data scope, HTTPS, backups); same Verified CHECK |

Nothing is seeded as Verified.

## 070 — CRM certificates

| Change | Why |
|---|---|
| `admission_academic_state()` wraps `admission_academic_core()` and adds `completion_authorised_by_email` | The CRM's `admissions.completion_authorised_by` is required on completion |
| `trg_completion_reviews_academics` | A completion decision refreshes the academic state |
| `certificate_crm_state()`, `trg_certificates_crm` → `CertificateChanged` | Each numbered version when Issued, Superseded or Revoked; the CRM mirrors the LMS register |

## 080 — Exception queue

| Object | Purpose |
|---|---|
| `exception_recovery_steps` | Append-only log (trigger blocks UPDATE / DELETE): `source`, `source_id`, `branch_id`, `reason`, `logged_by`, `logged_at` |
| `exception_queue` (view) | One row per open exception: `source`, `source_id`, `reference`, `queue`, `branch_id` (NULL = company-wide), `title`, `detail`, `owner_user_id` / `owner_name` (NULL = awaiting a named owner), `owner_label` (role that should own it), `opened_at`, `state`, `link` (SPA route), `step_count`, `last_step_at` |

The view unions, without copying: enrolments in `Allocation Pending` / `Provisioning
Pending` (003), unresolved `recording_exceptions` (020), pending `access_extension_requests` with `needs_exception`
(020), results not yet `Published` per batch (030), open `support_requests` that are escalated or past their SLA (050),
`crm_events` with status Failed (003) and integrations that Failed verification or are Misconfigured (001 / 060). The
owner is the source record's own owner, else the last person who logged a step. No backbone tables change.

## 090 — CRM round-1 fixes

The fixes from the CRM's first live run (round 1, [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `courses.title`, `course_components.track_name` → `varchar(255)` | Match the CRM's `course_title` (a booster track takes its course's title) |
| `trg_courses_single_has_no_components` | A course cannot be marked single (`is_combo = false`) while it still has components. `CourseUpserted` removes them first, or refuses the event while they are used |
| `finance_summaries.installments_scope` (`admission` / `invoice`, default `admission`), `invoice_course_count` (default 1) | The CRM keeps instalments per invoice. When one invoice covers several courses (one admission each), every admission carries the same schedule; the LMS shows and sums it once per invoice |
| `seed_data` on `students`, `admissions`, `batches` | Rows written by `flask seed-dev` carry made-up CRM IDs; the status pull leaves them out |

## 095 — CRM round 2: the status pull

What the CRM needed before applying the pull (round 2, [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `crm_pull_as_of()` | The pull's `as_of`: the clock, held just below the start of the oldest open transaction. Changes are stamped with their transaction's start time and appear at commit, so a transaction open during a pull would otherwise commit rows older than the stored `since`. Rows can repeat; none are skipped |
| `admission_lms_state.changed_at` (+ `refresh_admission_lms_state` sets it) | One stamp for "lms_status or last activity changed". Activity recorded late with an earlier `occurred_at` is still pulled |
| `admission_academic_core`: `allocations[].track_code` | A combo is allocated track by track; two tracks can share a `course_code` |
| `trg_batches_never_deleted`, `trg_batch_allocations_never_deleted`, `trg_certificates_never_deleted` (`refuse_crm_mirrored_delete`) | The CRM mirrors them; a removal is a status (Cancelled, Ended / Transferred, Superseded / Revoked). An unnumbered certificate draft can still be deleted |
| Indexes on `students.provisioned_at`, `admission_lms_state.changed_at` / `academic_changed_at`, `batch_crm_state.changed_at`, numbered `certificates.updated_at` | The CRM polls every few minutes |

## 096 — CRM branches and finance snapshots

Round-2 owner decisions D3 and D4 ([CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `crm_events.event_type` accepts `BranchUpserted`, `BranchFinanceSnapshot` | The two new CRM events |
| `branches.source_version` (0 = made in the LMS) | `BranchUpserted` is versioned per branch like the other CRM records |
| `branch_finance_snapshots` (one row per branch: target period, verified collections / target, paid Admissions / target, overdue amount / count / by age band, pending and overdue payment verifications, overdue follow-ups, broken promises, `as_of`, `source_version`) | The CRM-authoritative dashboard figures. Each snapshot replaces the previous one; a target needs its period. A branch without a row shows Not Configured, never 0 |

## 097 — CRM round 3: curriculum catalogue and mapping (removed again in 104)

The CRM mapped admissions to curricula; the LMS reported its catalogue (round 3, [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `curriculum_version_crm_state` (+ `curriculum_version_crm_payload`, `refresh_curriculum_version_crm_state`, triggers on `curriculum_versions` and `curriculum_events`) | `curriculum_versions[]` in the status pull, with its own change stamp. No foreign key: a deleted Draft stays as a tombstone (`status` Retired, `lms_status` Deleted), so nothing the CRM mirrors disappears. `published_at` = the activation event, or the approval of a version made Active directly; a retired version keeps it |
| `crm_events.event_type` accepts `AdmissionCurriculumMapped` | The new CRM event |
| `admissions.curriculum_source_version` | `AdmissionCurriculumMapped` is versioned per admission, separately from `AdmissionQualified` / `AdmissionUpdated` |

## 098 — Batch timetable

The CRM's sales playbook needs real timings before promising a batch (round 3, [CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `batches.schedule_days` (`SMALLINT[]`, ISO weekdays 1–7), `start_time`, `end_time` (`TIME`, IST), `location` | The timetable the Branch Manager promises, set before any class is scheduled. Checks: 1–7 known days; both times or neither, the end after the start |
| `weekday_labels()` | `{1,3,5}` → `'Mon, Wed, Fri'` |
| `batch_crm_state()` adds `readiness`, `readiness_reason`, `seats_left`, `schedule_days`, `start_time`, `end_time`, `location`; `trg_batch_allocations_crm_state` | Sales offers only non-Blocked Planned / Open batches with seats left. Every allocation change refreshes the batch's pulled state |

## 099 — Gap fixes, phase 1

Correctness and privacy fixes from the gap review ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md), [GAPS.md](GAPS.md)).

| Change | Why |
|---|---|
| `notifications.role_code` | The role a notice was fanned out on (`notify(role_code=…)`); NULL = sent to named people. Staff see a branch notice only while they hold that role (or any role, when NULL) at the branch or company-wide, so a transfer or removed role hides it (G010). Rows from before 099 have NULL |
| `content_items.staff_only` | Answer keys, marking guides and trainer notes: never in a student's audience (G022) |
| `crm_events.historical`, setting `crm_notify_max_age_hours` (72) | A backfill or re-import (flagged, or older than the setting) is applied with its original dates but sends no current notices (G056) |
| `enrolment_batch_links.first_effective_from`; `attendance_grid`, `enrolment_attendance`, `enrolment_covered_topics`, `enrolment_required_learning`, `enrolment_progress` recreated | Attendance is expected from the seat (allocation `effective_from`), not the first Present, so earlier absences count (G028); `attendance_state` is Not started only while nothing has been delivered. A recovery counts as recovered / covered only when Completed (G029) |

## 100 — Governance and approvals

Independent decisions from the gap review, phase 3 ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)).

| Change | Why |
|---|---|
| `approval_status` enum; `certificate_financial_exceptions` (one Pending per admission, decider ≠ requester) | A Founder / CEO or Super Admin releases certificates while a fee is outstanding; the debt is not waived (G032) |
| `certificate_request_kind` enum; `certificate_change_requests` (one Pending per certificate, decider ≠ requester, evidence for revocation / reinstatement) | Corrections, revocations and reinstatements are requested and decided by someone else (G036, G095) |
| `certificate_status_history` + `trg_certificates_status_history` (backfilled with each entry's current status) | Every status change, so a revoked interval survives a reinstatement |
| `certificates_before_write()` allows Revoked → Issued, allocating a number only from Approved for Issue | Reinstatement keeps the number and the original issue date |
| `ai_feature_controls` (audience All / Student / Staff, company-wide or one branch; All only company-wide; restoring needs a note) | Switching AI off with scope, reason and a restoration record (G042) |

## 101 — Academic Calendar

The Nipuna Academic Calendar for working-day targets, phase 4 ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)).

| Change | Why |
|---|---|
| `calendar_closure_kind` enum; `calendar_closures` (company holiday = no branch; dates at most 63 days; Pending / Approved / Rejected) | Company holidays set centrally and branch closures approved by the Branch Manager (G064) |
| Settings `working_weekdays` (all seven by default) and `attendance_unconfirmed_lookback_days` (14) | Working days count only configured weekdays outside approved closures; nothing is assumed closed (Module 15 §9) |

## 102 — Curriculum model (Module 14)

Phase 5 of the gap fix plan ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)).

| Change | Why |
|---|---|
| `curriculum_topics`: `topic_class`, `outcome`, `instructional_minutes`, `independent_minutes`, `weight`, `evidence`, `activities`; `trg_curriculum_topics_sync_class` keeps `is_required = (topic_class = 'Required')` | Topic outcome, class, effort, weight and evidence (G013); the progress views keep reading `is_required` |
| `curriculum_topic_dependencies` (same version, Draft only) | Dependencies only where academically necessary |
| `curriculum_versions.hours_verified_by / _at`, `completion_profile` | Verified standard hours and the completion profile before publication |
| `curriculum_assessment_requirements` (Draft only) | The assessments a version requires; assignments and tests will link to them (phase 7) |
| `course_components.equivalence_*`; `curriculum_version_components` | A combo parent pins its track and booster versions; reusing a standalone curriculum needs a recorded review (G058) |
| `equivalence_rules`, `academic_mappings` (`proposed_credits`), `learning_credits`; `enrolment_covered_topics` also counts credits | Individual version moves with comparison, plan, acceptance and independent approval; credit never becomes attendance (G014) |
| `enrolments.mapping_owner_user_id` (dropped again in 105) | The named owner of the removed Curriculum Mapping Pending recovery (G061) |
| `curriculum_variations` | Branch and batch variations; a required-topic constraint needs a remedial plan (G060) |
| `library_modules`, `library_module_versions`, `curriculum_modules.library_version_id` | Reusable modules with explicit, independently approved versions (G059) |

## 103 — Batches and delivery operations (Modules 15 and 16)

Phase 6 of the gap fix plan ([GAP_FIX_PLAN.md](GAP_FIX_PLAN.md)). Stored state names are kept, for the CRM and the views;
the API adds Module 15's labels (`state_label`).

| Change | Why |
|---|---|
| `batch_state` + `Proposed`, `On Hold`, `Archived`; `check_batch_transition` rewritten (Forming → Proposed → Starting needs `confirmed_at`; On Hold returns to `held_from_state`; Archived only after Completed / Cancelled) | Module 15 §5 lifecycle and the Branch Manager's confirmation (G015) |
| `batches`: `proposed_by / _at`, `proposal_note`, `confirmed_by / _at` (≠ proposer), `confirmation_checklist` | The 7-point readiness record as confirmed |
| `batches`: `display_name`, `batch_type`, `schedule_pattern`, `creating_branch_id` (permanent; `branch_id` is the service branch) | Type, pattern, display name (G062) |
| `batches`: `classroom_capacity`, `lab_capacity`, `online_capacity`; `batch_capacity_requests` | Verified capacity per side; an increase is reviewed and approved independently (G103) |
| `batches.recording_provision` / `recording_terms`; `meet_series_link`, `meet_space_id`, `calendar_series_id` | The recording commitment; the recurring batch-series Meet link (G070) |
| `batches.component_id`; `check_batch_allocation` rewritten (track seats, interbranch track placement, no seats while On Hold / Archived) | Track batches and track-level allocation (G016) |
| `batch_transfer_requests` | Transfers approved by the Branch Manager, never the requester; a track placed at another branch after the destination confirms (G017) |
| `material_changes`, `material_change_responses` | The old and new plan, independent approval and each student's agreement before a material change applies (G018) |
| `batch_successions`, `batch_handovers` | Merge / split with successor links; completion needs a named owner, plan and destination for students still owed teaching (G069) |
| `class_sessions`: `original_starts_at / _ends_at`, `confirmed_at / _by`, `live_at`, `delivery_outcome` (Held / Partially Held; defaulted to Held by `trg_class_sessions_default_outcome`), `actual_start / _end`, `break_minutes`, `delivered_minutes`, `unfulfilled_note`, `log_overdue_at` | Planned / Confirmed / Held / Partially Held, the class log and the same-day log check (G065) |
| `class_sessions`: `purpose`, `replaces_session_id`, `purpose_reference`, `approval_status`, `proposed_by`, `approved_by / _at`, `owner_user_id`, `due_on`, `replacement_waiver` | Replacement, remedial and extra classes with their links, approval, owner and deadline (G066) |
| `class_sessions`: `room_override_reason`, `hosting_branch_id`, `meet_space_id`, `calendar_event_id`, `calendar_series_id`, `conference_record_id`; `session_changes.emergency_reason`, `next_action` | Documented overrides (G068); Meet identifiers (G070); emergency notices (G018) |
| `session_cover_requests`; `class_sessions_before_write` accepts an applied substitute | Cover approved by the Branch Manager and verified by the Branch Manager (G101) |
| `session_people`, `meet_incidents`, `meet_participation` | Hosts, backups, approved guests, compromised-link history (G071); join / leave evidence and unmatched identities, never attendance (G104) |
| `session_disruptions`, `class_sessions.delay_notice_at` | Delayed starts (5 / 15 minutes) and undelivered minutes (G019) |
| `session_rosters`, view `session_batches`; `attendance_grid`, `enrolment_delivery` and their dependants recreated over it; `check_attendance_record` accepts any batch of the class | Shared classes: one class, one attendance row per person, counted once (G067) |
| `slot_preferences` | Student preferred slots, Requested / Waitlisted / Confirmed (G102) |
| `job_runs` | Last run and last success of each background job (Meet operations view, G072) |
| `exception_queue` + `DISRUPTION`, `CLASS_LOG`, `REPLACEMENT` | Disruptions, missing class logs and replacements owed reach the queue |
| `crm_batch_status`: Proposed, On Hold and Archived pass through | Round 4 request A5 |
| Settings `session_delay_notice_minutes` (5), `session_disruption_minutes` (15), `material_end_extension_days` (7), `class_log_lookback_days` (14) | |

## 104 — CRM round 5: the CRM holds no curriculum

The CRM no longer holds curriculum, so the LMS stops reporting it and receiving mapping events ([CRM_INTEGRATION.md §5](CRM_INTEGRATION.md#5-integration-rounds)).

| Change | Why |
|---|---|
| `crm_events.event_type` no longer accepts `AdmissionCurriculumMapped` (the check is `NOT VALID`: events already received stay in the inbox) | The CRM never sends it again |
| `admissions.curriculum_source_version` dropped | It versioned that event |
| `curriculum_version_crm_state` and its functions and triggers dropped | `curriculum_versions[]` left the pull |
| `admission_academic_core` and `batch_crm_state` no longer emit `curriculum_status` / `curriculum_version_label`; stored states and Pending outbox rows lose the keys without a new change stamp | The CRM ignores them |

## 105 — UX phase U1: Curriculum Mapping Pending is removed

A new enrolment is always allocatable. With no Active curriculum version it has none, follows the version of the batch it joins, and receives the version when one is activated ([UX_PLAN.md](UX_PLAN.md)).

| Change | Why |
|---|---|
| Enrolments in *Curriculum Mapping Pending* move to *Allocation Pending*; each gets a closing recovery step (`CURRICULUM_MAPPING` stays a valid source of `exception_recovery_steps` for that history) | Existing rows convert in place |
| `enrolment_status` is replaced by a type without the value (PostgreSQL cannot drop a value); the two constraints, three triggers on `status` and `crm_enrolment_status()` that use it are recreated | |
| `enrolments.mapping_owner_user_id` dropped; `exception_queue` loses the `CURRICULUM_MAPPING` branch | The state no longer exists |
| Batches blocked only by *Curriculum Mapping Pending* become Ready | A batch without a curriculum warns instead of blocking |

## 106 — UX phase U2: the Academic Coordinator is merged into the Branch Manager

Like the CRM, the LMS has no Academic Coordinator any more ([UX_PLAN.md](UX_PLAN.md)). The Branch Manager does everything the coordinator did.

| Change | Why |
|---|---|
| `roles.ACADEMIC_COORDINATOR` set inactive (the row stays so history and audit read); every live scope of it is revoked | The role is retired, not deleted |
| Users whose only live role was the coordinator are deactivated and their sessions ended | As the CRM did |
| Open `support_requests`, unresolved `recording_exceptions`, open `session_disruptions`, started-but-unfinished reviews and the reviewer on assignments and tests move to the branch's lowest-id Branch Manager (a Super Admin when the branch has none) | Open items keep an owner |
| `batches_confirmer_independent`, `batch_capacity_requests_independent`, `batch_transfer_requests_independent` dropped | The proposer may confirm a batch, the requester may decide a capacity increase or a transfer (one Branch Manager step). Every other `*_independent` constraint stays; the services add the rule that a Branch Manager's own request is decided by the Founder / CEO or a Super Admin |
| `exception_queue` owner labels read *Branch Manager* and links point at `/branch/*` | The Branch Manager owns what the coordinator did |

## 107 — UX phase U6: WhatsApp through the CRM

| Change | Why |
|---|---|
| Enum `whatsapp_status` (Queued, Sent, Failed, Skipped) and table `whatsapp_outbox` (template, language, `recipient_user_id`, `lms_user_id`, `to_number`, `params`, `button_params`, unique `dedupe_key`, `occurred_at`, `expires_at`, status and note, `provider_message_id`, `attempts`, `next_attempt_at`, `attempt_started_at`, `sent_at`) | The LMS writes the message in the same transaction as the change; a job posts it to the CRM after the commit. A row in flight (`attempt_started_at`) is never auto-resent |
| `app_settings`: `whatsapp_enabled` (false), `whatsapp_approved_templates` (`[]`), `whatsapp_max_age_hours` (48) | The code ships switched off; only approved templates are sent; older messages are skipped |



## 108 — UX phase U7: sign-in and accounts

| Change | Why |
|---|---|
| Table `password_reset_codes` (`user_id`, `code_hash`, `expires_at`, `wrong_attempts`, `used_at`) | The 6-digit code behind "Forgot password". Only a hash of `"<user id>:<code>"` is stored; single use, 10 minutes, burned after 5 wrong tries; at most 5 per person per hour (service rule) |
| Table `staff_invites` (`user_id`, unique `token_hash`, `issued_by`, `expires_at`, `used_at`, `revoked_at`; one outstanding invite per person) | The one-time link that replaces a spoken temporary password for new staff. Student links stay in `student_activations` |

## 109 — UX phase U8: student Home and My Learning

| Change | Why |
|---|---|
| View `topic_progress` (per enrolment and topic of every followed curriculum version: `attended`, `recording_watched`, required assignments handed in, required tests taken, `is_done`, `status` = Done / Work to hand in / Not started) | A topic is Done when the student attended (or recovered) its class or watched its recording, and handed in every required assignment and test of the topic. Module and course percentages count topics Done. The four progress measures keep their own views |
| `material_changes.reply_by` | The date a student is asked to answer a batch change by; set to now + `batch_change_reply_days` when the change goes to students |
| `app_settings.batch_change_reply_days` (7) | Length of that answer window |

## 110 — CRM round 6: WhatsApp status events

| Change | Why |
|---|---|
| `crm_events` accepts `WhatsappStatusUpdated` | The CRM reports what happened to a message after answering Queued |
| `whatsapp_outbox.crm_outbox_id`, `delivery_status` (Sent / Delivered / Read / Failed / Skipped), `delivery_version`, `delivery_at` | The latest reported state, applied only when its version is newer |

## 111 — UX phase U11: student Career, Ask Nipuna, Support and My Account

| Change | Why |
|---|---|
| Table `support_attachments` (`support_request_id`, `support_message_id`, `uploaded_by_user_id`, `file_path`, `original_filename`, `mime_type`, `file_size_bytes`) | A file attached to a support message. The bytes are on disk under `UPLOAD_DIR/support`; type, size and who may download are checked by the service |
| Table `email_change_codes` (`user_id`, `new_email`, `code_hash`, `expires_at`, `wrong_attempts`, `used_at`) | The 6-digit code that confirms a student's new email. Only a hash of `"<user id>:<email>:<code>"` is stored; single use, 10 minutes, burned after 5 wrong tries; at most 5 per person per hour (service rule) |
| `branches.payment_instructions` (text) | How and where a student pays at that branch, shown on the Next payment card. Set through `PUT /branches/{id}/payment-instructions` |

## 112 — UX phase U12: the trainer's class flow

| Change | Why |
|---|---|
| Table `class_flow_progress` (`session_id` PK, `step` open / join / attendance / log, `draft` jsonb, `updated_by`, `updated_at`) | Where a trainer stands in Today's flow for a class and the half-written class log, so a refresh resumes at the same step. The row is deleted when the class is logged; the class's own state stays the truth |
| Table `class_session_topics` (`session_id`, `topic_id`) | The topics the trainer logged as covered in a delivered class. The class keeps its one planned topic (`class_sessions.topic_id`), which still drives student topic progress |
| `meet_events.event_type` accepts `Link requested` | The trainer's one-click "no Meet link" request to the Branch Managers |

## 113 — UX phase U15: access extensions beyond the Branch Manager's limit

| Change | Why |
|---|---|
| `access_extension_requests.recommended_decision` (approve / reject), `recommendation`, `recommended_expiry`, `recommended_by`, `recommended_at` | A request made after the second anniversary is a Founder / Super Admin decision. The Branch Manager of the service branch adds a recommendation instead of deciding it. Checks: the five fields are all set or all empty, only an exception request may carry one, the note is not blank, a suggested end date goes with an approval and is after the current end date |
| Index `access_extension_founder_idx` (pending exception requests with a recommendation) | `recommended_at IS NOT NULL` on a Pending `needs_exception` request is the routing mark: it is in the Founder's inbox (what U16's `GET /founder/inbox` reads) |

## 114 — UX phase U16: Approve & activate a curriculum version on a chosen day

| Change | Why |
|---|---|
| `curriculum_versions.activate_on` (date) with the check `activate_on IS NULL OR status = 'Approved'` | The Founder can approve a version and pick the day it becomes the Active one. The date is kept on the Approved version; the `curriculum-activate` job (`services/curriculum.activate_due`) activates it that day and clears it. A version approved with today's date is activated in the same step and never holds a date; activating, returning or retiring a version clears it (the check refuses a date on any other status) |
| Index `curriculum_versions_due_idx` (versions with an `activate_on`) | The job reads the versions whose day has come |

## 115 — UX phase U17: Super Admin (Setup owners, cancelled closures, assigned issues)

| Change | Why |
|---|---|
| `integrations.owner_user_id`, `security_controls.owner_user_id` (FK to `users`) | Setup & health picks the owner from staff. The text `owner` stays and holds the person's name (or the old role label until someone is picked; "Unassigned" when cleared) |
| `calendar_closures.cancelled_by`, `cancelled_at`, `cancel_reason` with the check `(cancelled_at IS NULL) = (cancelled_by IS NULL)` | A calendar entry can be cancelled and stays in the list. `status` is not changed (the `approval_status` enum is shared by many tables); every reader of "approved closures" also checks `cancelled_at IS NULL` (`CalendarClosure.in_force()`, used by `services/working_days` and `services/batches`), and the API reports the status as `Cancelled` |
| `exception_recovery_steps.assigned_to` (FK to `users`) | "Assign" on the Super Admin's Issues is a recovery step that names its new owner. The table stays append-only |
| `exception_queue` view recreated (same columns as db/106) | The owner is `COALESCE(the record's own owner, assigned_to or author of the latest step)`, so the owner filter and the counts follow an assignment. The integration link now points at `/admin/setup` |

Applied in place to `nipunalms-dev` (`psql -d nipunalms-dev -v ON_ERROR_STOP=1 -1 -f db/115_super_admin_setup_calendar_assign.sql`). Gap-fix phase 7 starts at `db/116`.


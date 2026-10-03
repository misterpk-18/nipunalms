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

---

## 001 — Foundation

| Table | Purpose |
|---|---|
| `code_counters` | Per-prefix, per-year counters behind the human codes (`NIT-STU-2026-004182`, `NIT-GNT-BAT-2026-000001`, …) |
| `branches` | NIT-GNT (mailbox trainer@nipunatechnologies.com), NIT-VIJ (contactus@nipunatechnologies.com) |
| `roles` | STUDENT, TRAINER, ACADEMIC_COORDINATOR, BRANCH_MANAGER (per branch); SUPER_ADMIN, FOUNDER_CEO (company-wide) |
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
| `completion_reviews` | Trainer recommendation, Academic Coordinator decision, evidence snapshot; one Open review per enrolment; Complete blocked by open recoveries |
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

The view unions, without copying: enrolments in `Curriculum Mapping Pending` / `Allocation Pending` / `Provisioning
Pending` (003), unresolved `recording_exceptions` (020), pending `access_extension_requests` with `needs_exception`
(020), results not yet `Published` per batch (030), open `support_requests` that are escalated or past their SLA (050),
`crm_events` with status Failed (003) and integrations that Failed verification or are Misconfigured (001 / 060). The
owner is the source record's own owner, else the last person who logged a step. No backbone tables change.

## 090 — CRM round-1 fixes

The fixes from the CRM's first live run (`nipuna crm-docs/CRM_TO_LMS_FIXES_ROUND1.md`).

| Change | Why |
|---|---|
| `courses.title`, `course_components.track_name` → `varchar(255)` | Match the CRM's `course_title` (a booster track takes its course's title) |
| `trg_courses_single_has_no_components` | A course cannot be marked single (`is_combo = false`) while it still has components. `CourseUpserted` removes them first, or refuses the event while they are used |
| `finance_summaries.installments_scope` (`admission` / `invoice`, default `admission`), `invoice_course_count` (default 1) | The CRM keeps instalments per invoice. When one invoice covers several courses (one admission each), every admission carries the same schedule; the LMS shows and sums it once per invoice |
| `seed_data` on `students`, `admissions`, `batches` | Rows written by `flask seed-dev` carry made-up CRM IDs; the status pull leaves them out |

## 095 — CRM round 2: the status pull

The CRM's round-2 questions (`nipuna crm-docs/CRM_ROUND2_BRIEF.md`, answered in `CRM_ROUND2_LMS_REPLY.md`).

| Change | Why |
|---|---|
| `crm_pull_as_of()` | The pull's `as_of`: the clock, held just below the start of the oldest open transaction. Changes are stamped with their transaction's start time and appear at commit, so a transaction open during a pull would otherwise commit rows older than the stored `since`. Rows can repeat; none are skipped |
| `admission_lms_state.changed_at` (+ `refresh_admission_lms_state` sets it) | One stamp for "lms_status or last activity changed". Activity recorded late with an earlier `occurred_at` is still pulled |
| `admission_academic_core`: `allocations[].track_code` | A combo is allocated track by track; two tracks can share a `course_code` |
| `trg_batches_never_deleted`, `trg_batch_allocations_never_deleted`, `trg_certificates_never_deleted` (`refuse_crm_mirrored_delete`) | The CRM mirrors them; a removal is a status (Cancelled, Ended / Transferred, Superseded / Revoked). An unnumbered certificate draft can still be deleted |
| Indexes on `students.provisioned_at`, `admission_lms_state.changed_at` / `academic_changed_at`, `batch_crm_state.changed_at`, numbered `certificates.updated_at` | The CRM polls every few minutes |

## 096 — CRM branches and finance snapshots

Round-2 owner decisions D3 and D4 (`nipuna crm-docs/CRM_ROUND2_LMS_REPLY.md` §3).

| Change | Why |
|---|---|
| `crm_events.event_type` accepts `BranchUpserted`, `BranchFinanceSnapshot` | The two new CRM events |
| `branches.source_version` (0 = made in the LMS) | `BranchUpserted` is versioned per branch like the other CRM records |
| `branch_finance_snapshots` (one row per branch: target period, verified collections / target, paid Admissions / target, overdue amount / count / by age band, pending and overdue payment verifications, overdue follow-ups, broken promises, `as_of`, `source_version`) | The CRM-authoritative dashboard figures. Each snapshot replaces the previous one; a target needs its period. A branch without a row shows Not Configured, never 0 |

## 097 — CRM round 3: curriculum mapping

The CRM maps admissions to curricula; the LMS reports its catalogue (`nipuna crm-docs/CRM_ROUND3_LMS_CHANGES.md`).

| Change | Why |
|---|---|
| `curriculum_version_crm_state` (+ `curriculum_version_crm_payload`, `refresh_curriculum_version_crm_state`, triggers on `curriculum_versions` and `curriculum_events`) | `curriculum_versions[]` in the status pull, with its own change stamp. No foreign key: a deleted Draft stays as a tombstone (`status` Retired, `lms_status` Deleted), so nothing the CRM mirrors disappears. `published_at` = the activation event, or the approval of a version made Active directly; a retired version keeps it |
| `crm_events.event_type` accepts `AdmissionCurriculumMapped` | The new CRM event |
| `admissions.curriculum_source_version` | `AdmissionCurriculumMapped` is versioned per admission, separately from `AdmissionQualified` / `AdmissionUpdated` |

## 098 — Batch timetable

The CRM's sales playbook needs real timings before promising a batch (`nipuna crm-docs/CRM_PLAYBOOK_LMS_ASKS.md`).

| Change | Why |
|---|---|
| `batches.schedule_days` (`SMALLINT[]`, ISO weekdays 1–7), `start_time`, `end_time` (`TIME`, IST), `location` | The timetable the coordinator promises, set before any class is scheduled. Checks: 1–7 known days; both times or neither, the end after the start |
| `weekday_labels()` | `{1,3,5}` → `'Mon, Wed, Fri'` |
| `batch_crm_state()` adds `readiness`, `readiness_reason`, `seats_left`, `schedule_days`, `start_time`, `end_time`, `location`; `trg_batch_allocations_crm_state` | Sales offers only non-Blocked Planned / Open batches with seats left. Every allocation change refreshes the batch's pulled state |


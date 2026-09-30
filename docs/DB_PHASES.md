# Nipuna LMS — Database Build Phases

Tables are created in dependency order: a table is only built once everything it references exists.
Derived from the prototype at https://nipuna-lms-prototype.lovable.app/ (sample data only) and the approved LMS modules 14–27.

**Core flow:** CRM qualifying payment → `AdmissionQualified` event → Student (one per CRM Person) + LMS login + Admission projection + Enrolments (paid standalone / combo with tracks / complimentary) → curriculum mapping → batch allocation → Class Sessions → content, recordings, assignments, tests, attendance → progress → completion review → Certificate Register.

Every academic record is branch-scoped through its batch or the enrolment's service branch (NIT-GNT Guntur, NIT-VIJ Vijayawada).

Migration files live in `db/` and are applied in numeric order, each in its own transaction:

```bash
psql -d nipunalms -v ON_ERROR_STOP=1 -1 -f db/<file>.sql
```

The dev replica (`nipunalms-dev`) and the pytest database (`nipunalms_test`) are rebuilt from the same files — see [DEVELOPMENT.md](DEVELOPMENT.md#3-databases).

| Phase | Status | Migration |
|---|---|---|
| 1a — Foundation | ✅ Done | `001_foundation.sql` |
| 1a — Catalogue & curriculum | ✅ Done | `002_catalog_curriculum.sql` |
| 1a — Students, enrolments, CRM projection | ✅ Done | `003_students_enrolments.sql` |
| 1a — Batches & class sessions | ✅ Done | `004_batches_sessions.sql` |
| CRM alignment | ✅ Done | `005_crm_alignment.sql` — real CRM vocabulary and shapes; academic state and batches back to the CRM |
| 2 / S1 — Delivery | ✅ Done | `010_delivery.sql` |
| 2 — S6 Admin & security | ✅ Done | `060_admin_security.sql` |
| CRM certificates | ✅ Done | `070_crm_certificates.sql` — certificates and completion authoriser to the CRM |
| 2 — S4 Attendance, progress & certificates | ✅ Done | `040_attendance_certificates.sql` |
| 2 / S2 — Content & recordings | ✅ Done | `020_content_recordings.sql` |
| 2 / S3 — Assessments | ✅ Done | `030_assessments.sql` |
| 2 — S5 Student services | ✅ Done | `050_student_services.sql` |
| 3 — Exception queue | ✅ Done | `080_exception_queue.sql` — `exception_queue` view and `exception_recovery_steps` |

---

## 001 — Foundation ✅

| Table | Purpose |
|---|---|
| `code_counters` | Per-prefix, per-year counters behind the human codes (`NIT-STU-2026-004182`, `NIT-GNT-BAT-2026-000001`, …) |
| `branches` | NIT-GNT (mailbox trainer@nipunatechnologies.com), NIT-VIJ (contactus@nipunatechnologies.com) |
| `roles` | STUDENT, TRAINER, ACADEMIC_COORDINATOR, BRANCH_MANAGER (per branch); SUPER_ADMIN, FOUNDER_CEO (company-wide) |
| `users` | Staff and student logins; case-insensitive unique email; `student_id` (unique) links a login to its student |
| `user_role_scopes` | Role per branch with validity window; one live scope per user/role/branch |
| `user_sessions`, `active_sessions` (view) | Opaque session tokens (hash only), idle + max lifetime, fresh auth |
| `app_settings` | Session timeouts, activation token hours, recording access days, AI daily limit, password minimum length |
| `audit_log` | Append-only change history |
| `integrations` | Register: requirement, configuration status, verification status, owner, last check (Google Workspace, Meet, Drive, CRM, WhatsApp, email, telephony, AI provider) |
| `notifications` | In-app notifications; one per (`event_key`, recipient); separate delivery / read / acknowledged / action states |
| `activity_events` | Learning activity (logins, views, completions) for engagement and "last activity" |

**Rules enforced:** company-wide roles take no branch and branch roles need one; `audit_log` rejects UPDATE/DELETE.

## 002 — Catalogue & curriculum ✅

| Table | Purpose |
|---|---|
| `courses` | Mirror of the CRM Course Master (`CourseUpserted`): code, title, `is_combo`, status |
| `course_components` | Combo tracks: `NIT-CRS-018/T1`… (Main track) and the included booster (NIT-CRS-019) |
| `curriculum_versions` | Per course or per track: label, status Draft → Under Review → Approved → Active → Retired |
| `curriculum_modules`, `curriculum_topics` | Ordered modules and topics; topics have `is_required` |

**Rules enforced:** only a combo has components; a track version must belong to its course; one Active version per course/track; labels unique per course/track.

## 003 — Students, enrolments, CRM projection ✅

| Table | Purpose |
|---|---|
| `students` | Student Master, one per CRM Person (`crm_person_id` unique); `student_code` = `lms_user_id`; optional email; mobile never unique; original / service branch; language; activation status; `provisioned_at` |
| `student_activations` | Single-use activation tokens (hash, expiry, used); one outstanding token per student |
| `admissions` | CRM projection: `crm_admission_id` unique, `admission_code`, course, original / service / collecting branch, `source_version` |
| `enrolments` | Paid standalone, separately purchased, combo, complimentary (linked to its qualifying paid enrolment); status from *Provisioning Pending* to *Completed*; joining date; access window; certificate status |
| `enrolment_tracks` | Combo enrolment → component track and its curriculum version |
| `finance_summaries` | Read-only per-admission money snapshot from the CRM (fee, verified paid, balance, next due, receipts) |
| `crm_events` | Inbox: every CRM event once (`event_id`), payload, `source_version`, status Received / Applied / Ignored — stale / Failed |
| `crm_outbox` | Values the CRM stores about the LMS, queued in the same transaction as the change |
| `admission_lms_status` (view), `admission_lms_state` | Per-admission `lms_status` in the CRM's vocabulary and the last value sent |

**Rules enforced:** students are never deleted; `student_code`, `lms_user_id`, `crm_person_id` are immutable; enrolment student = admission student; only combo courses have Combo enrolments; a complimentary enrolment links to a paid enrolment of the same admission.

### CRM columns fed by the LMS

The CRM already has these columns (`nipuna-crm` db 005/006); the LMS is their source. They reach the CRM through `crm_outbox` (push, worker not built yet) or `GET /api/v1/integrations/crm/status?since=` (pull).

| CRM column | LMS source | Outbox event |
|---|---|---|
| `persons.lms_user_id` | `students.lms_user_id` (= `student_code`, e.g. `NIT-STU-2026-004182`; stable, never reused) | `LmsAccountProvisioned` |
| `persons.lms_provisioned_at` | `students.provisioned_at` (login first created by `AdmissionQualified`) | `LmsAccountProvisioned` |
| `admissions.lms_status` | `admission_lms_status.lms_status` — Not Created / Invited / Active / Inactive / Completed | `AdmissionLmsStatusChanged` |
| `admissions.lms_last_activity_at` | latest `activity_events.occurred_at` for that admission's enrolments | `AdmissionLmsStatusChanged` |
| `admissions.lms_last_synced_at` | time of the pull / delivery | — |
| `batches.lms_course_id` | LMS `batches.batch_code` (linked by `batches.crm_batch_id`) | `BatchLinked` |

`lms_status`: **Not Created** — no LMS login yet; **Invited** — login created, not activated; **Active** — activated and a course of the admission is running; **Inactive** — student suspended, or all its courses Paused / Withdrawn; **Completed** — every non-withdrawn course Completed.

## 004 — Batches & class sessions ✅

| Table | Purpose |
|---|---|
| `batches` | `batch_code` (what the CRM stores as `lms_course_id`), `crm_batch_id`, course, branch, curriculum version, capacity, mode, state Forming → Starting → Running → Full → Completed / Cancelled, readiness Ready / Blocked / Pending Verification + reason + recovery owner |
| `batch_trainers` | Trainer ↔ batch (Lead / Co-trainer) with dates; one live row per trainer and one lead per batch |
| `batch_allocations` | Enrolment (or combo track) ↔ batch with effective dates; one active allocation per enrolment / track; history kept |
| `class_sessions` | Actual Class Sessions: batch, topic, trainer, scheduled start/end, mode, room, Meet link + status, state Scheduled / Live / Delivered / Cancelled / Rescheduled |

**Rules enforced:** `batch_code` is immutable; capacity can't drop below allocated students; a trainer must hold the Trainer role at the batch's branch; allocation course and branch must match the enrolment; no allocation into a closed or full batch; the track must belong to the enrolment; the session trainer must be assigned to the batch; session end after start.

## 005 — CRM alignment ✅

Checked against the CRM's schema (db 001–025) and docs; contract in [CRM_INTEGRATION.md](CRM_INTEGRATION.md).

| Change | Why |
|---|---|
| `course_status` + `Archived` | The CRM's course status has it |
| `students.crm_person_code` | The CRM's `PER-GNT-00148`, for display |
| `admissions.complimentary_of_admission_id`, `seat_type`, `planned_start_date` | The CRM grants a complimentary course as its own admission linked to the paid one; seat type / planned start come from its delivery plan |
| `check_enrolment_links()` (replaced) | A complimentary enrolment may hang off the paid admission it is complimentary to |
| `enrolments.completed_at` (trigger-stamped) | Feeds the CRM's `admissions.academic_completed_at` |
| `finance_summaries` + pending verification, waived, refunded, payment completion, invoice numbers, instalments | The rest of the CRM's `admission_balances` / `installment_dues` |
| `crm_enrolment_status()`, `crm_delivery_mode()`, `crm_batch_status()` | LMS → CRM vocabulary |
| `admission_academic_state()`, `admission_lms_state.academic` + triggers → `AdmissionAcademicsChanged` | Enrolment status, curriculum status, allocations with joining date, completion — the CRM columns the LMS now owns |
| `batch_crm_state()`, `batch_crm_state` table + triggers → `BatchUpserted` | The CRM's `batches` become a mirror keyed by `lms_course_id` |
| `queue_crm_state()` | An undelivered outbox row for the same admission / batch is superseded by the latest state (the CRM needs the state, not every step) |
## 060 — Admin & security ✅

| Table / change | Purpose |
|---|---|
| `integrations` (ALTER) | + `verified_by`, `verified_at`, `evidence`; CHECK `integrations_verified_needs_evidence` (Verified needs a person, a time, an evidence note and a Configured setup) |
| `integration_configuration_status` (ALTER TYPE) | + `Misconfigured` |
| `integrations` (rows) | + `MEET_ORGANIZER_GNT`, `MEET_ORGANIZER_VIJ` (per-branch organizer, Pending Verification), `HDFC_PAYMENTS` (CRM-owned feed), `PRODUCTION_AUTH` |
| `security_controls` | Security readiness register (seeded with 18 controls: scope enforcement, session idle / max, fresh auth, lockout, password policy, unique LMS login, activation token, audit immutability and decisions, temporary / emergency access, student MFA, file access, export scoping, AI data scope, HTTPS, backups); same Verified CHECK |

Nothing is seeded as Verified. The status table above gains the row: `060_admin_security.sql` — S6 Admin & security ✅.

## 010 — Delivery (S1) ✅

| Object | Purpose |
|---|---|
| `curriculum_events` | Review trail per curriculum version (Created, Submitted, Returned, Approved, Activated, Retired) with from / to status, note and actor |
| `batch_events` | Batch history: created, state changed, readiness, trainer and curriculum changes |
| `session_changes` | Every reschedule, cancellation and substitute trainer: reason, original and new slot, notice hours, `short_notice` |
| `session_change_requests` (+ type `reschedule_request_status`) | Trainer reschedule requests (Open / Approved / Rejected); one Open request per session (partial unique index) |
| `meet_events` | Meet association log: requested, link associated, failed, reset; organizer email; the LMS never calls Google |

No table from 001–005 is altered. Rules added as triggers on the Phase 1 tables: modules and topics of a non-Draft version cannot be updated or deleted; batch lifecycle transitions; class-session transitions (a Live / Delivered / Cancelled session cannot change time or trainer); a session topic must belong to the batch's course; one trainer cannot have two overlapping open sessions. These triggers apply to every later slice's tests and seeds (a Delivered session's times are fixed).

## 040 — Attendance, progress & certificates (S4) ✅

| Object | Purpose |
|---|---|
| `attendance_records` | One row per Class Session x enrolment (Present / Absent / Late / Excused, remarks, marked_by / marked_at, correction fields). Only Live / Delivered sessions and seated enrolments |
| `attendance_recoveries` | `REC-0041` codes; Requested → Approved / Rejected → Completed with evidence; one live recovery per absence |
| `attendance_corrections` | Post-lock changes and student disputes; the decider cannot be the requester |
| Views `enrolment_batch_links`, `attendance_grid`, `enrolment_delivery`, `enrolment_attendance`, `enrolment_required_topics`, `enrolment_covered_topics`, `enrolment_required_learning`, `enrolment_engagement`, `enrolment_progress` | The four progress measures per enrolment |
| `completion_reviews` | Trainer recommendation, Academic Coordinator decision, evidence snapshot; one Open review per enrolment; Complete blocked by open recoveries |
| `certificates` | LMS Certificate Register (types Course Completion / Internship; statuses Not Yet Eligible → Eligibility Review → Awaiting Approval → Approved for Issue → Issued → Superseded / Revoked); number allocated at first issue, kept across versions |
| `app_settings` (added) | `attendance_lock_days`, `attendance_alert_threshold`, `engagement_window_days`, `engagement_high_events`, `engagement_medium_events`, `complimentary_completion_rule_configured` |

**Rules enforced:** transition table and eligibility (Completed enrolment; complimentary rule configured), immutable certificate number, reissue must follow the Superseded version, revocation needs a reason, Excused needs a reason, rejected recoveries / corrections need a note. No backbone table is altered; a trigger keeps `enrolments.certificate_status` in step with the live register entry.
## 020 — Content & recordings (S2) ✅

| Table | Purpose |
|---|---|
| `content_items` | Library entry: `CNT-` code, type (PDF, Notes, Dataset, Code, Lab, Practice material, Link, Video link), placement (course, curriculum version, module, topic), branch, optional batch, download policy, status of the latest version, author, retirement |
| `content_versions` | One row per upload or link (v1, v2 …): file path / URL, size, change summary, review status, released at / by |
| `content_reviews` | Submission, review, release and retirement history with comments |
| `recordings` | `RCD-` code, one or more parts per class session, status Processing / Released / Partial / Held / Unavailable / Expired, Drive reference, duration, download policy, hold reason / partial note |
| `recording_exceptions` | `RX-0012` codes: Partial, Held, Unavailable, Integration Unavailable; owner role and person, Open / In Progress / Resolved, resolution note |
| `access_extension_requests` | `EXT-031` codes: enrolment, scope (Recording / Material / Both), reason, status, `needs_exception`, original and approved expiry, decision |

Also inserts `app_settings`: `access_default_years`, `access_max_years`, `recording_check_hours`, `content_max_upload_mb`, `content_dataset_max_upload_mb`.

**Rules enforced:** placement consistency (version of the course, module of the version, topic of the module, batch of the course and branch); a version is a file xor a link; released versions need a release time; hold / partial / resolution / rejection need a reason; a recording maps to a non-cancelled class session and is unique per session and part; one open exception per session and issue; one pending extension per enrolment and scope; an exception's branch is its session's branch; codes are immutable.

## 070 — CRM certificates ✅

| Change | Why |
|---|---|
| `admission_academic_state()` wraps `admission_academic_core()` and adds `completion_authorised_by_email` | The CRM's `admissions.completion_authorised_by` is required on completion |
| `trg_completion_reviews_academics` | A completion decision refreshes the academic state |
| `certificate_crm_state()`, `trg_certificates_crm` → `CertificateChanged` | Each numbered version when Issued, Superseded or Revoked; the CRM mirrors the LMS register |
## 030 — Assessments (slice S3) ✅

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

**Rules enforced:** the topic must belong to the batch's course; a submitted version cannot be edited; marks cannot exceed the maximum; an approved question cannot be edited (new version instead); answers are refused after the deadline and once an attempt is submitted; the receipt is issued once by a trigger; one attempt in progress per student and test; one live interview booking per student and test; one result per student and item; a published result cannot change; a moderated result needs a reason. No changes to backbone tables.
## 050 — Student services ✅

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

**Changes to backbone tables:** `notifications` gains `channel` (In-app / WhatsApp / Email) and `delivery_note` (a Failed delivery must say why). `app_settings`: `ai_daily_limit` raised to 50 (Module 24 pilot limit), new `ai_daily_limit_staff` (100), `ai_enabled`, `support_sla_hours` (48). New helper function `acting_user_id()`. `finance_summaries` is untouched.

## 080 — Exception queue (P3) ✅

| Object | Purpose |
|---|---|
| `exception_recovery_steps` | Append-only log (trigger blocks UPDATE / DELETE): `source`, `source_id`, `branch_id`, `reason`, `logged_by`, `logged_at` |
| `exception_queue` (view) | One row per open exception: `source`, `source_id`, `reference`, `queue`, `branch_id` (NULL = company-wide), `title`, `detail`, `owner_user_id` / `owner_name` (NULL = awaiting a named owner), `owner_label` (role that should own it), `opened_at`, `state`, `link` (SPA route), `step_count`, `last_step_at` |

Unions, without copying: enrolments in `Curriculum Mapping Pending` / `Allocation Pending` / `Provisioning Pending` (003), unresolved `recording_exceptions` (020), pending `access_extension_requests` with `needs_exception` (020), results not yet `Published` per batch (030), open `support_requests` that are escalated or past their SLA (050), `crm_events` with status Failed (003) and integrations that Failed verification or are Misconfigured (001 / 060). The owner is the source record's own owner, else the last person who logged a step. No backbone tables change.

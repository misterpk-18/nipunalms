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
| 2 — S6 Admin & security | ✅ Done | `060_admin_security.sql` |

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

## 060 — Admin & security ✅

| Table / change | Purpose |
|---|---|
| `integrations` (ALTER) | + `verified_by`, `verified_at`, `evidence`; CHECK `integrations_verified_needs_evidence` (Verified needs a person, a time, an evidence note and a Configured setup) |
| `integration_configuration_status` (ALTER TYPE) | + `Misconfigured` |
| `integrations` (rows) | + `MEET_ORGANIZER_GNT`, `MEET_ORGANIZER_VIJ` (per-branch organizer, Pending Verification), `HDFC_PAYMENTS` (CRM-owned feed), `PRODUCTION_AUTH` |
| `security_controls` | Security readiness register (seeded with 18 controls: scope enforcement, session idle / max, fresh auth, lockout, password policy, unique LMS login, activation token, audit immutability and decisions, temporary / emergency access, student MFA, file access, export scoping, AI data scope, HTTPS, backups); same Verified CHECK |

Nothing is seeded as Verified. The status table above gains the row: `060_admin_security.sql` — S6 Admin & security ✅.

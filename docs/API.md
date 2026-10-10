# Nipuna LMS — API

Flask backend over the `nipunalms` PostgreSQL database (schema in `db/`, see [DATABASE.md](DATABASE.md)). The product
is defined by the interactive prototype at https://nipuna-lms-prototype.lovable.app/ (readable copy in
`prototype/reference/`) and the approved LMS modules 14–27. This document covers the code structure, the conventions
every endpoint follows, the domain model and every endpoint with the rules it enforces.

The repository mirrors **nipuna-crm** (`~/nipuna-crm`) layer for layer. When in doubt about a convention, copy what the
CRM does: its `backend/` and `frontend/` are the reference implementation.

Every module described here is built and on `main`. `backend/api.http` lists every endpoint as a runnable request
(regenerate it with `flask --app app api-http` after adding one). Open gaps are in the
[backlog](DEVELOPMENT.md#part-e--backlog).

---

## 1. Architecture

### Layers

A request flows top to bottom. Each layer only talks to the one directly below it.

| Layer | Folder | Responsibility | Must not |
|---|---|---|---|
| Routes | `backend/routes/` | Blueprints: URL + HTTP method, auth / role decorators (`routes/decorators.py`), call the controller | Contain logic or queries |
| Controllers | `backend/controllers/` | Read and validate the request (`Validator` in `controllers/common.py`), call the service, return JSON via `model.to_dict()` | Touch the database |
| Services | `backend/services/` | Business rules, permission and branch / record-scope checks, audit log, notifications. Shared: `errors.py`, `security.py`, `context.py` | Build HTTP responses |
| Repositories | `backend/repositories/` | Database queries: filters, joins, pagination, reading views. Shared: `common.py` (`paginate`, `set_db_user`) | Contain business rules |
| Models | `backend/models/` | SQLAlchemy classes mapped to the existing tables and views, each with `to_dict()` | Create or alter tables |
| Config | `backend/config/` | Settings per environment, the shared `db` object, logging, JSON encoding | Import from any other layer |

Every module uses the same file name across layers: `routes/assignments.py → controllers/assignments.py →
services/assignments.py → repositories/assignments.py → models/assignments.py`.

`app.py` is the only place that builds the application; nothing imports from it. One transaction per request (commit on
success, roll back on error); every exception becomes `{"error": {...}}`.

### Key decisions

| Decision | Choice | Why |
|---|---|---|
| Separate system | Own repo, own database (`nipunalms`), own API (`:5060`) and SPA (`:5174`) | CRM stays authoritative for Admission and finance; LMS owns learning (Module 27 authority split) |
| Schema ownership | SQL files in `db/` are the source of truth; models map existing tables; never `db.create_all()` | Triggers, views, enums and constraints |
| CRM → LMS | CRM posts versioned, idempotent events to `POST /api/v1/integrations/crm/events` (service key). The LMS stores every event in `crm_events` and upserts Student, Admission projection, Enrolments and the finance summary. Contract: [CRM_INTEGRATION.md](CRM_INTEGRATION.md) | Durable handoff, retry of the same event, late events cannot undo newer decisions |
| Finance in LMS | Read-only projection (`finance_summaries`) of what the CRM sends; the LMS never edits money | "CRM is authoritative for Admission and finance" |
| Identity | One `students` row per CRM Person (`crm_person_id` unique) = one LMS account. Student logs in with Student ID (`NIT-STU-2026-004182`) or email; mobile is never a login key | Shared family mobile is not identity proof (M29) |
| Activation | Single-use, expiring activation token (hash stored); the student sets their own password. Staff can issue / reissue (supervised activation) | M29 assisted activation |
| Auth tokens | Same as CRM: opaque bearer session token, SHA-256 hash in `user_sessions`, idle timeout + max session, fresh auth for sensitive actions | Revocation and fresh auth need server-side sessions |
| Integrations | Google Meet / Drive / Workspace, WhatsApp, email, AI provider: an `integrations` register with requirement / configuration / verification status. No live calls; actions that would call them record "Integration Unavailable" / "Pending Verification" states | Prototype + M27: capability must be verified separately |
| AI (Ask Nipuna) | Anthropic API when `ANTHROPIC_API_KEY` is set, otherwise rule-based fallback over the student's own permitted content; scope + sources + daily usage limit | Same pattern as the CRM AI Copilot |
| Language | Student screens bilingual (English / తెలుగు); stored preference on the student | Prototype language toggle |
| Tests | pytest against `nipunalms_test` built from `db/*.sql`, each test in a rolled-back transaction | Same as CRM |

---

## 2. Conventions (all endpoints)

Identical to the CRM:

- Prefix `/api/v1`, plural nouns, actions as sub-resources (`POST /submissions/{id}/review`, `POST /certificates/{id}/issue`).
- Success `{"data": ...}` (+ `"meta": {page, per_page, total, pages}` for lists); error `{"error": {"code", "message", "details"}}`.
- Status codes: 400 `VALIDATION_ERROR`, 401 `UNAUTHENTICATED` / `FRESH_AUTH_REQUIRED`, 403 `FORBIDDEN` / `PASSWORD_CHANGE_REQUIRED`,
  404 `NOT_FOUND` (also for records outside the user's scope), 409 `CONFLICT`, 422 `BUSINESS_RULE` / `INVALID_REFERENCE`, 429 `TOO_MANY_ATTEMPTS`.
- Lists: `?page=&per_page=` (max 100), filters as query params (`?branch_id=1&batch_id=3&status=Due`).
- Timestamps ISO 8601 with offset; business dates in IST (`Asia/Kolkata`). Money as strings with 2 decimals.
- Enum values exactly as stored (`"Allocation Pending"`). Every response carries numeric `*_id` plus the human
  code (`student_code`, `batch_code`, `certificate_number`, …).
- Audit: services write `audit_log` for sensitive changes (publishing results, certificate issue / revoke, role changes,
  access extensions, recording release, account activation / recovery) with old and new values.

### Scope rules (server-enforced on every list, detail, total, export and AI answer)

| Role (`role_code`) | Sees |
|---|---|
| `STUDENT` | Only their own student record, enrolments, sessions of batches they are allocated to, released content / recordings of those enrolments, own submissions / attempts / results / certificates / support / notifications |
| `TRAINER` | Batches they are assigned to (`batch_trainers`), the students allocated to those batches, sessions they teach |
| `BRANCH_MANAGER` | Everything at their branch (academic + operational + read-only finance summary). Since UX phase U2 (db 106) this is also everything the retired `ACADEMIC_COORDINATOR` role did |
| `SUPER_ADMIN` | All branches; admin / integrations / security; can open the branch workspace |
| `FOUNDER_CEO` | All branches, management overview; can open admin and branch workspaces (read-mostly) |

**Who decides** (UX phase U2: the Branch Manager does what the Academic Coordinator did). The Branch Manager decides alone for
the steps that used to take a coordinator and then a Branch Manager: confirming a batch (a warning needs `override_reason`,
audited), replacement and extra classes, approving a certificate (the recommendation is recorded in the same step), cover,
capacity increases and transfers. Requests that need an independent reviewer (`services/approvals.require_independent`:
corrections and requests of trainers or other staff, attendance corrections, academic mappings, variations, library
versions, material changes, merges and splits, guests, certificate change requests) are reviewed by a Branch Manager who
is not the requester; **when the requester is a Branch Manager, only the Founder / CEO or a Super Admin may decide it**
(422 *A Branch Manager's own request is decided by the Founder / CEO or a Super Admin*).

Branch comes from `batches.branch_id` / `enrolments.service_branch_id`, never from a submitted value. A record outside
scope is a 404, not a 403. Scope helpers every module uses live in `services/scope.py` (branch visibility, trainer
batches, student enrolments).

---

## 3. Domain model

Codes follow the prototype: `NIT-STU-2026-004182`, `ADM-GNT-2026-000214`, `NIT-GNT-BAT-2026-000001`, `NIT-CRS-018`,
`NIT-CERT-2026-000001`. Table-by-table detail and the rules the database enforces are in [DATABASE.md](DATABASE.md).

### Backbone (`001`…`005`)

| Table | Purpose |
|---|---|
| `branches` | 1 = NIT-GNT Guntur, 2 = NIT-VIJ Vijayawada; code, name, city, mailbox (`trainer@…` / `contactus@nipunatechnologies.com`) |
| `roles`, `users`, `user_role_scopes`, `user_sessions` (+ `active_sessions` view) | Same shape as CRM. Students are users too: `users.student_id` links a login to a student |
| `audit_log` | Append-only (UPDATE / DELETE blocked by trigger) |
| `app_settings` | Key / value settings (session timeouts, AI daily limit, access years, …) |
| `integrations` | Register: code, name, requirement, configuration status, verification status, owner, last check |
| `notifications` | In-app notifications: recipient user, category, title, body, link, `delivery_status` / `read_at` / `acknowledged_at` / `action_status`, `event_key` (dedupe) — plus `services/notifications.notify()` used by every module |
| `activity_events` | Generic learning activity log (student, enrolment, kind: `login`, `resource_view`, `recording_view`, `topic_complete`, …) — feeds the engagement measure |
| `courses` | LMS course catalogue mirrored from CRM Course Master: `course_code`, title, `is_combo`, status |
| `course_components` | Combo structure: parent course → component course, `track_code` (`NIT-CRS-900/T1`), role (`Main track` / `Included booster`), order |
| `curriculum_versions` | Per course (or per component track): label (`Parent Programme v2026.1`, `Track CV 3.2`), status `Draft` / `Under Review` / `Approved` / `Active` / `Retired`, approved_by / at |
| `curriculum_modules` | Version → ordered modules (`Supervised Learning`) |
| `curriculum_topics` | Module → ordered topics, `is_required` |
| `students` | Student Master: `student_code`, `crm_person_id` (unique), full_name, name_te, email (optional), mobile (not unique), original / service branch, preferred_language, `activation_status` (`Account Created` / `Activation Pending` / `Activated` / `Suspended`), mfa_status |
| `student_activations` | Activation tokens (hash, expires_at, used_at, issued_by, channel) |
| `admissions` | CRM projection: `crm_admission_id` unique, `admission_code`, student, **one course**, original / service / collecting branch, crm status, mode, seat type, planned start, `complimentary_of_admission_id`, `source_version` |
| `enrolments` | `enrolment_code`, admission, student, course, `kind` (`Combo`, `Standalone`, `Separately purchased`, `Complimentary`), `parent_enrolment_id` (complimentary → qualifying enrolment), curriculum_version, service branch, mode, `status` (`Provisioning Pending`, `Allocation Pending`, `Allocated — awaiting first regular class`, `Active`, `Paused`, `Completed`, `Withdrawn`), joining_date (first regular class attended), access_start / end, certificate_status, benefit gate note |
| `enrolment_tracks` | Combo enrolment → component track + its curriculum version |
| `finance_summaries` | Read-only per-admission finance snapshot from CRM: fee, verified paid, pending verification, waived, refunded, balance, payment completion, invoice numbers, instalments (+ `installments_scope`, `invoice_course_count`), next due, receipts, `as_of`, `source_version` |
| `crm_events` | Inbox: `event_id` unique, `event_type`, payload jsonb, `source_version`, original event time, received / processed time, status (`Received` / `Applied` / `Ignored — stale` / `Failed`), error, retries |
| `crm_outbox` | Values the CRM keeps about the LMS, queued in the same transaction as the change |
| `batches` | `batch_code`, course, branch, curriculum_version, capacity, mode, planned start / end, `state` (`Forming`, `Starting`, `Running`, `Full`, `Completed`, `Cancelled`), readiness (`Ready` / `Blocked` / `Pending Verification`) + reason + recovery owner |
| `batch_trainers` | Batch ↔ trainer user (`Lead` / `Co-trainer`), from / to |
| `batch_allocations` | Enrolment (or enrolment track) ↔ batch with effective dates, status, reason; history retained |
| `class_sessions` | Actual Class Session: `session_code`, batch, topic, title, scheduled start / end (timestamptz), mode (`Classroom` / `Live Online` / `Hybrid`), trainer, room, `meet_link` + `meet_status`, `state` (`Scheduled`, `Live`, `Delivered`, `Cancelled`, `Rescheduled`), delivered_at, notes |

### Module tables

| Module | Migration | Owns |
|---|---|---|
| Delivery | `010` | `curriculum_events`, `batch_events`, `session_changes`, `session_change_requests`, `meet_events` — plus all delivery APIs over the backbone |
| Content & recordings | `020` | `content_items`, `content_versions`, `content_reviews`, `recordings`, `recording_exceptions`, `access_extension_requests` |
| Assessments | `030` | `assignments`, `assignment_submissions`, `submission_reviews`, `questions`, `tests`, `test_questions`, `test_attempts`, `attempt_answers`, `interview_slots`, `results` |
| Attendance, progress & certificates | `040` | `attendance_records`, `attendance_recoveries`, `attendance_corrections`, progress views, `completion_reviews`, `certificates` |
| Student services | `050` | `support_requests`, `support_messages`, `notification_preferences`, `career_profiles`, `cv_documents`, `opportunities`, `applications`, `application_events`, `placement_outcomes`, `ai_queries` |
| Admin & security | `060` | `security_controls` (+ integration verification columns) |
| Exception queue | `080` | `exception_queue` view, `exception_recovery_steps` |
| Dashboards & reports | — | Aggregates only |

---

## 4. Endpoints

### 4.1 Health & auth

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/health` | Public | DB check |
| POST | `/auth/login` | Public | `{login, password}` — `login` is a staff email, a Student ID or a student email |
| POST | `/auth/logout` | Signed in | Revokes the session |
| GET | `/auth/me` | Signed in | User, scopes, student (if any), `home_route`, `workspaces` |
| POST | `/auth/reauthenticate` | Signed in | Fresh auth |
| POST | `/auth/change-password` | Signed in | Minimum length from `app_settings.password_min_length` (10) |
| GET / DELETE | `/auth/sessions`, `/auth/sessions/{id}` | Signed in | Own sessions; sign out another device |
| POST | `/auth/activate` | Public | `{token, password}` — single-use student activation |
| GET | `/auth/activation/{token}` | Public | Token status (valid / expired / used) and masked Student ID |
| POST | `/students/{id}/activation` | Super Admin / BM (branch) | Issue or reissue an activation token (fresh auth); shown once |

### 4.2 CRM integration

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/integrations/crm/events` | CRM service key (`X-Service-Key`) | `CourseUpserted`, `AdmissionQualified`, `AdmissionUpdated`, `AdmissionCancelled`, `FinanceSummaryUpdated`, `BranchUpserted`, `BranchFinanceSnapshot`. A record that hasn't arrived yet is 422 `NOT_YET_APPLIED`. Idempotent on `event_id`; stale `source_version` → `Ignored — stale` |
| GET | `/integrations/crm/events` | Super Admin | Inbox with status filters |
| POST | `/integrations/crm/events/{id}/retry` | Super Admin | Re-apply a failed event |
| GET | `/integrations/crm/status?since=&crm_admission_id=&crm_person_id=` | CRM service key | What the CRM stores about the LMS, changed since `since`: `persons`, `admissions`, `academics`, `batches`, `certificates`, `as_of`. The optional filters narrow every key to one admission or person and are echoed as `filter`. `as_of` is safe to store as the next `since` (rows can repeat, none are skipped); no paging. Seed rows (`seed_data`) are left out |

Payloads, validation rules and response handling are in [CRM_INTEGRATION.md §2](CRM_INTEGRATION.md#2-the-contract).

**Rules:**
- Every event is stored once in `crm_events`. Replaying an `event_id` returns the first result; the same `event_id`
  with a different payload is a 409; a `source_version` lower than the stored one is recorded as `Ignored — stale` and
  changes nothing. A failure is kept as `Failed` with the error, retryable.
- `CourseUpserted` is the whole catalog row: components it leaves out are removed, and the event is refused with 422
  while a removed component is still used by enrolment tracks or curriculum versions.
- `AdmissionQualified` upserts the Student by `crm_person_id` (one Student / one LMS login per Person, reused for later
  admissions), the Admission projection and its Enrolment. A new enrolment is *Allocation Pending* (or *Provisioning
  Pending* while a complimentary gate is unmet); it follows the Active curriculum version when its course has one, else it has none yet. A new login gets an activation token; the branch
  Branch Manager is notified. The response includes `lms_user_id` and `lms_status`. A repeat with a higher
  version is a full refresh: it never creates a second login or resets an enrolment being served.
- `AdmissionCancelled` withdraws only that admission's enrolments. `FinanceSummaryUpdated` replaces the read-only
  finance snapshot.
- Values the CRM keeps (`persons.lms_user_id`, `admissions.lms_status`, `batches.lms_course_id`, …) are queued in
  `crm_outbox` in the same transaction as the change and are also served by `/integrations/crm/status`. Mapping:
  [CRM_INTEGRATION.md §2.2](CRM_INTEGRATION.md#22-lms--crm-what-the-crm-stores-about-the-lms).

### 4.3 Reference & backbone reads

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/reference/branches`, `/reference/roles`, `/reference/courses` | Staff | Courses include combo components |
| GET | `/reference/staff?role=&branch_id=` | Staff | Staff in the caller's branches |
| GET | `/students/{id}` | Scoped | Student record (student: own only) |
| GET | `/batches`, `/batches/{id}` | Scoped | Filters `branch_id`, `course_id`, `state`; trainers see assigned batches only |
| GET | `/class-sessions?batch_id=&from=&to=` | Scoped | |

### 4.4 Delivery: curriculum, enrolments, batch allocation, class sessions, student course pages (`010`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/curriculum/overview` | Staff | One row per course: Active version, versions in review, `waiting_batches` (open batches with no approved curriculum yet) |
| GET / POST | `/curriculum-versions` | Staff / BM, Super Admin | List (filters `course_id`, `status`); create a Draft (optionally copied from an earlier version) |
| GET / PATCH / DELETE | `/curriculum-versions/{id}` | Staff / BM, Super Admin | Detail with modules, topics, review trail and publish blockers; rename; delete only a never-published Draft |
| POST | `/curriculum-versions/{id}/submit`, `/return` | BM, Super Admin (`return` also Founder / CEO) | Draft → Under Review; `return` (back to Draft) needs a reason. Submitting notifies the Founder / CEO (link `/founder/curriculum`) and Super Admin |
| POST | `/curriculum-versions/{id}/approve`, `/activate`, `/retire` | Founder / CEO, Super Admin (fresh auth; never the submitter, Module 14 §5) | Under Review → Approved → Active → Retired. Activating gives the version to the course's batches and enrolments that had none and returns the counts (`enrolments_released`, `batches_mapped`) |
| POST | `/curriculum-versions/{id}/modules`, `/curriculum-modules/{id}/topics` | BM, Super Admin | Add to a Draft (optional `position`) |
| PATCH / DELETE | `/curriculum-modules/{id}`, `/curriculum-topics/{id}` | BM, Super Admin | Draft only; sort order re-sequenced. A topic has `topic_class` (Required / Recommended / Optional; `is_required` follows it), `outcome`, `instructional_minutes`, `independent_minutes`, `weight`, `evidence`, `activities` and `depends_on` (topic ids of the same version, no loops) |
| POST / PUT | `/curriculum-versions/{id}/hours-verification`, `/completion-profile` | BM, Super Admin | Draft only. Verifying needs every topic estimated; changing minutes clears it. Profile: `attendance_minimum_pct`, `pass_mark_pct`, `recovery_rule`, `reassessment_rule` |
| POST / DELETE | `/curriculum-versions/{id}/assessment-requirements`, `/assessment-requirements/{id}` | BM, Super Admin | The assessments the version requires: kind, title, outcome, weight, pass rule; Draft only |
| PUT | `/curriculum-versions/{id}/components` | BM, Super Admin | A combo parent version pins `{component_id, component_version_id}`; a booster may pin its own course's version only after `POST /course-components/{id}/equivalence` `{note}` (Module 14 §3) |
| GET / POST | `/academic-mappings`, `/enrolments/{id}/academic-mappings` | Staff / trainer, BM, SA (a trainer of a batch on the target version may prepare it) | `{to_version_id, enrolment_track_id?, comparison, migration_plan, trainer_evidence?, rule_id?, credits?: [{topic_id, original_evidence}]}`; credits need an approved equivalence rule between the two versions |
| POST | `/academic-mappings/{id}/decision` | BM (receiving branch), SA; fresh auth; never the preparer | `{decision, note?, student_acceptance}` (acceptance required to approve). Approving moves the enrolment or track and records `learning_credits`, which count as covered required learning, never attendance |
| GET / POST | `/equivalence-rules`, `/{id}/decision` | Staff / BM, SA propose; Founder, SA decide (fresh auth; never the proposer) | `{from_version_id, to_version_id, description}` |
| GET / POST | `/curriculum-variations`, `/{id}/decision` | Staff / BM, SA; decisions by BM (local) or Founder, SA (required topic constraint) | Kinds Local example, Equivalent exercise, Teaching language, Sequencing (a Branch Manager's own entry is approved), Required topic constraint (needs `topic_id` and `remedial_plan`) |
| GET / POST | `/curriculum-library`, `/curriculum-modules/{id}/library`, `/curriculum-library/{id}/versions`, `/curriculum-library-versions/{id}/decision`, `/curriculum-versions/{id}/library-modules` | Staff / BM, SA | Reusable modules with explicit versions; another reviewer approves each version; inserting copies an approved version into a Draft and keeps `library_version_id` |
| GET | `/enrolments`, `/allocation-queue` | Staff / BM, Super Admin | Branch-scoped enrolment list; the queue of payment-cleared enrolments waiting for a seat, each with `allocation_due_on` (Module 15 §6: one working day after Admission for a confirmed seat, 48 hours before the first class for a future plan, never after the first class) |
| GET / POST | `/calendar/closures`, `/calendar/closures/{id}` | Staff / Founder, SA (company holiday); BM, SA (branch closure) | The Academic Calendar. A company holiday and a Branch Manager's own closure are Approved at once (the Branch Manager decides alone). The detail lists `affected_sessions` (Scheduled / Live classes inside it) |
| POST | `/calendar/closures/{id}/decision` | BM, SA | `{decision, note}` (note to reject). Approving asks the affected branches' Branch Managers to prepare replacements; no class is moved automatically |
| GET / POST | `/batches/{id}/allocations` | Staff / BM, Super Admin | Roster (filter `status`); allocate an enrolment, or one combo track with `enrolment_track_id` (a track batch takes only its track) |
| GET | `/batches/{id}/allocation-review?enrolment_id=&enrolment_track_id=&transfer=` | BM, Super Admin | The checks (branch, course / track, curriculum, capacity, mode, student timetable, batch state, enrolment state) as pass / warn / fail |
| POST | `/enrolments/{id}/deallocate` | BM, Super Admin | `{reason, enrolment_track_id?}`. Moving a seat is a transfer request (§4.4.1) |
| POST / PATCH | `/batches`, `/batches/{id}`, `/trainers`, `/readiness` | BM, Super Admin | Batch with `batch_events` history. The timetable: `schedule_days` (`["Mon", "Wed", "Fri"]`), `start_time` / `end_time` (`"HH:MM"` IST, both or neither), `location` (dropped for Live Online); each nullable. Module 15 fields: `display_name`, `batch_type` (Group / Individual / Corporate), `schedule_pattern` (Regular / Weekend / Fast-track), `component_id` (a track batch, Draft only), `classroom_capacity` / `lab_capacity` / `online_capacity`, `recording_provision` (Included / Not Included / Limited + `recording_terms`), `meet_series_link`, `meet_space_id`, `calendar_series_id`. Responses add `state_label`, `creating_branch`, `component`, `proposed_by` / `confirmed_by`; the detail adds `successions` and `handovers`. `GET /readiness` adds the 7-point `checklist` |
| POST | `/batches/{id}/proposal`, `/batches/{id}/confirmation`, `/batches/{id}/state` | proposal: BM, SA; confirmation: BM, SA; state: see rules | `proposal {note?}`: Draft → Proposed once points 1–6 pass. `confirmation {decision: Confirmed / Returned, note?, override_reason?}`: never the proposer; warnings need `override_reason`. `state {state: Running / On Hold / Resume / Completed / Cancelled / Archived, reason?}`: On Hold, Resume and Archived by BM / SA; reason for On Hold and Cancelled |
| POST | `/batches/{id}/handovers` | BM, SA | `{enrolment_id, owner_user_id, plan, destination, destination_batch_id?}`: a student the batch still owes teaching (paused, not started), needed before Completed |
| GET / POST / PATCH | `/class-sessions`, `/class-sessions/{id}` | Staff; create / edit BM, Super Admin | Filters include `batch_id`, `trainer_id`, `state`, `purpose`, `approval_status`, `from`, `to`; create accepts a weekly `recurrence` (weekdays, `until` / `count`), `purpose` (Regular / Replacement / Remedial / Extra) with `replaces_session_id`, `purpose_reference`, `owner_user_id`, `due_on`, the Meet ids, and `override_reason` for an advisory clash. Changing the trainer by PATCH is the Branch Manager's (others request cover). Responses add `state_label`, `original_starts_at` / `original_ends_at`, `confirmed_at`, `approval_status`, the delivery log and the Meet ids (staff) |
| POST | `/class-sessions/{id}/start`, `/deliver`, `/cancel`, `/reschedule` | Trainer of the class (start, deliver); BM, Super Admin (cancel, reschedule) | Reason required for cancel / reschedule; `session_changes` row with notice hours and `short_notice`; inside 24 hours also `emergency_reason` and `next_action`. Deliver is the class log: `{outcome: Held / Partially Held, actual_start?, actual_end?, break_minutes?, unfulfilled_note?, notes?}` (missing times default to the start and scheduled end) |
| POST | `/class-sessions/{id}/confirm`, `/approval`, `/replacement-waiver` | confirm, waiver: BM, SA; approval: BM, SA (never the proposer) | `confirm`: Planned → Confirmed (room; online also a Meet link and a named backup host). `approval {decision, note?}`: a replacement, remedial or extra class; until approved students don't see it and it cannot start. `replacement-waiver {reason}`: a cancelled class that owes no replacement |
| PUT | `/class-sessions/{id}/notes` | Teaching trainer, BM, Super Admin | `{notes}`; only while the class is Live or Delivered; audited (`SESSION_NOTES_SAVED`). The Trainer Today close-out |
| POST | `/class-sessions/{id}/reschedule-requests`; GET `/reschedule-requests`; POST `/reschedule-requests/{id}/approve`, `/reject` | Trainer (ask); BM (decide) | One open request per session; approve applies the proposed time |
| PUT / POST | `/class-sessions/{id}/meet`, `/meet/fail`, `/meet/reset` | BM, Super Admin | Records the Meet association in `meet_events`; the LMS never calls Google. `meet` also takes `meet_space_id`, `calendar_event_id`, `calendar_series_id`, `conference_record_id`; a link used by another batch's open class is refused |
| GET | `/me/enrolments`, `/me/enrolments/{id}`, `/me/enrolments/{id}/tracks/{track_id}`, `/me/schedule` | Student | Own courses with delivery progress, combo tracks and upcoming / past classes |
| GET | `/modules/{id}`, `/topics/{id}` | Student (own enrolments) / staff | Module and topic pages with their classes, resources and recordings |

Job: `flask --app app jobs run allocation-escalation`: an enrolment still waiting for a seat 24 hours before its
admission's `planned_start_date` (IST), or first noticed inside that window, is raised once to the Founder / CEO, Super Admin
and the service branch's Branch Managers (Module 15 §6).

Working days (`services/working_days.py`): a day counts when its ISO weekday is in `working_weekdays` (all seven by
default; Module 15 §9 assumes no weekend is closed) and no approved company holiday or closure at the branch covers it.

**Rules:**
- Submitting a version needs (Module 14 §5): every Required topic with an outcome, an instructional estimate, a weight and
  evidence; verified hours; a completion profile; and, for a combo parent, a pinned version for every track and the booster.
  A borrowed booster curriculum needs the component's equivalence review; without it the track has no version yet. A
  batch never refuses a student over the version: the student follows the version of the batch they are allocated to,
  and an academic mapping (with credit) is how a student on one version is credited when moving to another.
- Curriculum versions are snapshots: modules and topics change only while the version is a Draft (database trigger);
  an Active version is retired only when another takes over or with a reason. Approval by the submitter is refused.
- Allocation is the only path to a seat: the review returns per-check results, a blocked check cannot be overridden, a
  warning needs the acknowledgement; transfers and deallocations keep the allocation row (history) and free the seat. A
  student is told of every seat change.
- Batch lifecycle is enforced by trigger (Module 15 §5): Forming (Draft) → Proposed → Starting (Confirmed, needs
  `confirmed_at`) → Running (In Progress) ↔ Full → Completed; On Hold from Proposed / Starting / Running / Full and back to
  the held state; Cancelled while no seat is held; Archived only after Completed or Cancelled. The CRM sees Planned,
  Proposed, Open, In Progress, On Hold, Completed, Cancelled, Archived. Completed also needs (service): no open class, no
  replacement owed, no open disruption, no pending request, and a handover for every student still owed teaching.
  Archived needs every seated student Completed or Withdrawn and no open recording issue.
- Sessions: Scheduled / Rescheduled → Live → Delivered; Cancelled; a Live, Delivered or Cancelled session can no longer
  change time or trainer. Labels follow Module 15 §15: Planned / Confirmed / Rescheduled / In Progress / Held / Partially
  Held / Cancelled. Blocked (never overridden): a trainer, backup or assistant already busy. Advisory (Branch Manager
  with `override_reason`, stored on the class): a booked room, or the class's students attending another class then.
- Rescheduling or cancelling with less than 24 hours' notice is flagged `short_notice`, needs `emergency_reason` and
  `next_action`, and students of every batch the class serves are notified; every change is in `session_changes`. A
  reschedule clears the confirmation and keeps `original_starts_at`.
- Capacity: seats never exceed the verified side of the mode (classroom and lab for Classroom, online for Live Online,
  classroom + online for Hybrid). An increase after Draft is a capacity request (§4.4.1).
- A material change (start, mode, teaching days / times, an end extension over `material_end_extension_days`) on a
  confirmed batch with students is refused by PATCH: it goes through `/material-changes` (§4.4.1).
- The student "Join" state comes from `services/meet.join_state`: enabled only when the Meet link is associated and the
  class is Live or within 15 minutes of starting. Meet links are entered manually until the Google integration is
  verified.
- Notifications go through `services/delivery_notices.py` so a repeated event never sends twice.
- Attendance reuses `repositories/class_sessions.get_session`; there is one session lookup.

### 4.4.1 Batch and live-class operations, Modules 15 and 16 (`103`)

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/batches/{id}/capacity-requests` | BM, SA | `{to_capacity, classroom_capacity?, lab_capacity?, online_capacity?, resource_validation, academic_review}`; one open per batch |
| GET / POST | `/batch-capacity-requests`, `/{id}/decision` | BM, SA, Founder (list) / BM, SA (decide, never the requester) | `{decision, note?}` (note to reject); approving sets the capacity |
| POST | `/enrolments/{id}/transfer-requests` | BM, SA (student's service branch) | `{to_batch_id, enrolment_track_id?, reason, acknowledge_warnings?}`, after the allocation review. A batch at another branch is allowed only for one track (`interbranch`) |
| GET | `/batch-transfer-requests?status=&batch_id=` | BM, SA, Founder | Requests touching the user's branches (the student's or the destination's) |
| POST | `/batch-transfer-requests/{id}/destination` | BM, SA of the destination branch | `{decision: Confirmed / Rejected, note?}`: the destination can deliver the placed track |
| POST | `/batch-transfer-requests/{id}/decision` | BM, SA of the student's branch, never the requester | `{decision, note?}`; approving re-runs the review and moves the seat (interbranch only after the destination confirmed) |
| POST | `/batches/{id}/material-changes` | BM, SA | `{kind, proposed_plan, reason, changes?, alternative?}`. Kinds and what they set: Start date (`planned_start`), Delivery mode (`mode`), Teaching days / times (`schedule_days`, `start_time`, `end_time`), End date extension (`planned_end`), Instructional hours (nothing), Batch move (`target_batch_id`, for a merge / split onto another timetable). Every seated student gets a Pending response |
| GET | `/material-changes`, `/material-changes/{id}` | Staff | Filters `status` (Pending Approval / Awaiting Agreement / Applied / Rejected / Withdrawn), `batch_id`; detail has the responses |
| POST | `/material-changes/{id}/decision` | BM, SA, never the requester | Approving asks each student to agree (action-required notice) |
| POST | `/material-changes/{id}/responses` | BM, SA | `{enrolment_id, response: Agreed / Declined, note, alternative_arranged?}`: an answer given outside the LMS, with its evidence; a decline needs the agreed alternative |
| POST | `/material-changes/{id}/apply`, `/withdraw` | BM, SA | Apply once every student agreed or declined with an alternative; `withdraw {note}` |
| GET / POST | `/me/material-changes`, `/me/material-changes/{id}/response` | Student | Own requests for agreement; `{response, note?}` |
| GET / POST | `/batch-successions`, `/batch-successions/{id}/decision` | BM, SA (request) / BM, SA (decide, never the requester) | `{kind: Merge / Split, from_batch_id, to_batch_id, enrolment_ids (split), effective_from, reason, academic_review}`; same branch, course / track and curriculum version; a different mode or timetable needs an applied Batch move material change |
| GET / POST | `/me/slot-options?enrolment_id=`, `/me/slot-preferences`, `/me/slot-preferences/{id}/withdraw` | Student | Open batches of the course at the service branch (labelled honestly); `{enrolment_id, batch_id?, preferred_days?, preferred_start?, preferred_end?, preferred_mode?, note?}`; one open request; `reserves_seat` is always false |
| GET / PATCH | `/slot-preferences`, `/slot-preferences/{id}` | BM, SA (Founder reads) | `{status: Waitlisted / Confirmed / Not Possible, status_note?, batch_id?}`; Confirmed only once the student holds a seat there (an allocation to the requested batch confirms it) |
| GET | `/meet-operations?date=&branch_id=&batch_id=&trainer_user_id=` | Staff (trainers: their batches) | One IST day: per class link and host readiness, delay / disruption, attendance awaiting the trainer, recording state; open disruptions, replacements owed, classes awaiting approval, missing logs, open recording issues, unmatched participants, Meet integration status and `last_runs` of the background checks |
| GET | `/class-sessions/{id}/operations` | Staff | People, incidents, disruptions, cover requests, joined batches, participation and replacements of one class |
| POST / DELETE | `/class-sessions/{id}/people`, `/session-people/{id}`; POST `/session-people/{id}/decision` | BM, SA (guest decision: never the proposer) | `{role: Host / Backup / Guest, user_id? , guest_name?, guest_email?, purpose?, student_agreement?}`. Host and backup are staff not busy then; a guest starts Pending and gets no LMS rights |
| POST | `/class-sessions/{id}/meet-incidents` | Trainer of the class, BM, SA | `{kind, description, actions_taken, replace_link?}`: alerts the Branch Managers; replacing the link clears it (Link removed) and tells the participants |
| POST | `/class-sessions/{id}/participation`; GET `/meet-participation/unmatched`; POST `/meet-participation/{id}/review` | BM, SA | `{source, entries: [{participant_name?, participant_email?, joined_at, left_at?}]}`; matched by email to staff or a seated student, else Unmatched; review `{match_status: Matched / Dismissed, user_id?, note?}`. Never attendance |
| GET / POST | `/session-disruptions`, `/class-sessions/{id}/disruptions`, `/session-disruptions/{id}/resolve` | Staff / trainer of the class, BM, SA / BM, SA | `{kind, cause?, delay_minutes?, detail?}`; resolve `{recovery_plan, undelivered_minutes, cause?, replacement_session_id?, owner_user_id?}` tells the students the plan |
| POST / GET | `/class-sessions/{id}/cover-requests`, `/session-cover-requests` | BM, SA / staff (a cover sees their own) | `{cover_role: Substitute / Assistant, cover_user_id, reason, scope, handover}`; the cover holds the Trainer role (any branch) and is free then |
| POST | `/session-cover-requests/{id}/decision`, `/verification` | BM, SA (never the requester) / BM, SA | Approved and verified (either order) applies it: a substitute becomes the class trainer (a `Trainer changed` change; access to that class only), an assistant joins the class; students are told |
| POST / DELETE | `/class-sessions/{id}/rosters`, `/class-sessions/{id}/rosters/{batch_id}` | BM, SA | `{batch_id, topic_id?, coverage_note}`: a shared class. Distinct people may not exceed the class's verified seats; removing is refused once attendance is marked |

Jobs: `session-delay-check` (online and hybrid classes; students told at `session_delay_notice_minutes`, a disruption recorded and the
Branch Managers alerted at `session_disruption_minutes`, once per class) and `class-log-check` (a class not
Delivered or Cancelled after its working day raises a Branch Manager task once, looking back `class_log_lookback_days`). Every
job run is recorded in `job_runs`.

**Rules:**
- Shared classes: one class row, one attendance entry per person (`attendance_grid` reads `session_batches`), hours and
  trainer time counted once; students of every joined batch see the class and are told of changes; the register lists the
  seats of every batch it serves.
- A replacement names a cancelled or partially held class of the same batch; remedial and extra classes name their
  reference; all three need an owner and `due_on`. A cancelled regular or remedial class owes a replacement (exception
  source `REPLACEMENT`) until a non-cancelled replacement exists or a waiver is recorded; a cancelled replacement leaves its
  original owing; an extra class or a rejected proposal owes nothing. A late classroom class is recorded by hand.
- Exception queue sources added: `DISRUPTION` (open disruptions), `CLASS_LOG` (missing logs), `REPLACEMENT`.

### 4.5 Content library, recordings, recording exceptions, access extensions (`020`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/content-items` | Staff | Filters `course_id`, `batch_id`, `branch_id`, `module_id`, `topic_id`, `content_type`, `q`, `status` (comma list). Trainer: own items + items of batches they teach; BM: their branches; Super Admin / Founder: all |
| POST | `/content-items` | Trainer, BM, Super Admin | JSON (links) or multipart with `file`. Placement from `topic_id` / `module_id` / `curriculum_version_id` / `course_id`; branch from the batch or the author's batches (`branch_id` needed for Super Admin). Creates v1 Draft |
| GET | `/content-items/options` | Staff | Batches the caller may author for, with curriculum versions, modules and topics |
| GET / PATCH | `/content-items/{id}` | Staff / author, BM, Super Admin | Detail with versions and review history; edit metadata, placement, download policy (author only while Draft / Changes Requested; reviewer audited) |
| POST | `/content-items/{id}/versions` | Author, BM, Super Admin | New file (multipart) or `url`; v2, v3 … earlier versions kept |
| POST | `/content-items/{id}/submit` | Author, BM, Super Admin | Draft / Changes Requested → Submitted; Branch Managers notified |
| POST | `/content-items/{id}/review` | BM (branch), Super Admin | `decision` start / approve / request_changes / reject (+ `comment`, `release`); never the uploader |
| POST | `/content-items/{id}/release`, `/retire` | BM (branch), Super Admin | Approved → Released (previous released version retired, students notified); retire needs a reason |
| POST | `/content-items/{id}/open` | Student, staff | Students: entitlement + expiry checked, `resource_view` activity recorded; returns link URL / file info |
| GET | `/content-items/{id}/file?download=` | Student, staff | Serves the file; entitlement, expiry and `download_allowed` enforced here; only safe types shown inline. A `staff_only` item (answer key, marking guide, trainer notes; set on create / edit) is never part of a student's audience: not listed, opened, served or notified |
| GET | `/me/resources`, `/me/recordings`, `/me/access` | Student | Released items / recordings of the student's own enrolments with access state; Joining Date, expiries and what can still be requested. `?topic_id=` / `?session_id=` narrow them for topic and session pages |
| GET / POST | `/recordings` | Staff / BM, Super Admin | List scoped by branch or taught batches; register a part against an actual class session |
| GET / PATCH | `/recordings/{id}` | Staff / BM, Super Admin | Detail (+ open exceptions); media reference, duration, source, download policy |
| POST | `/recordings/{id}/release`, `/hold`, `/partial`, `/unavailable` | BM (branch), Super Admin | Release needs the media reference and a Delivered class and closes open hold / partial exceptions; hold / partial / unavailable raise an exception |
| POST | `/recordings/{id}/watch` | Student | Entitlement and expiry checked, `recording_view` recorded; playback state read from the integrations register |
| GET / POST | `/recording-exceptions` | Staff / Trainer, BM, Super Admin | RX codes; filters `status`, `issue_type`, `branch_id`, `batch_id`, `session_id` |
| POST | `/recording-exceptions/{id}/start`, `/resolve` | BM, Super Admin | Integration exceptions are Super Admin only; resolve needs a note |
| POST / GET | `/access-extension-requests` | Student (create) / student, BM, Super Admin, Founder | EXT codes; own requests or the branch's |
| POST | `/access-extension-requests/{id}/decision` | BM of the service branch, Super Admin; exceptions: Super Admin, Founder | `approve` / `reject` (+ `note`, `new_expiry` for an exception) |

Job: `flask --app app jobs run recording-check`.

**Rules:**
- Content versions carry the review lifecycle (Draft → Submitted → Under Review → Approved → Released, or Changes
  Requested / Rejected; a superseded version is Retired); the item's `status` follows its latest version, so students
  keep the last Released version until a newer one is released. A retired item is withdrawn from students; files and
  versions are never deleted.
- Audience = same branch and course, the item's batch (if any) is the enrolment's active batch, and the item's
  curriculum version is the enrolment's version or one of its combo tracks' versions
  (`services/content.item_matches_enrolment`). Withdrawn and gate-blocked enrolments grant nothing.
- Access window (`services/access.py`): one calendar year from the enrolment's Joining Date through the end of the
  anniversary day in IST (29 Feb → 1 Mar), one extra year to the second anniversary on request (Recording, Material or
  Both), pending before joining. Settings `access_default_years` / `access_max_years`; the older
  `recording_access_days` is superseded by Module 17 §8 and unused.
- Uploads: allow-list, 50 MB / 250 MB (datasets, archives) from `app_settings`, magic-number check, notebook JSON check,
  safe ZIP inspection (paths, nested archives, executables, expansion ratio). Local disk under `UPLOAD_DIR`; no malware
  scan yet (backlog).
- Recordings are references only; Google is never called. Escalation clock from class end: 4 h Branch Manager,
  24 h Super Admin, 48 h Founder (`escalation` on each exception; the job sends the notices once).

### 4.6 Assessments (`030`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/assignments?batch_id=&state=&status=&is_required=` | Scoped | Student: released tasks of their batches with `my.state` (Upcoming, Due, Overdue, Submitted, Under Review, Reviewed, Resubmission Requested), versions, submission window. Staff: assignments with counts |
| GET | `/assignments/{id}` | Scoped | Student sees released work of their batch only (else 404) |
| POST | `/assignments` | Trainer of the batch, BM, Super Admin | Draft; `release_now` releases at once. Reviewer defaults to the creating / lead trainer |
| PATCH | `/assignments/{id}` | Same | Draft: any field. Released: brief, attachments, due time (later only), late policy, reviewer; `closes_at` (reopen window) is BM-only with a reason. Audited; students notified |
| POST | `/assignments/{id}/release`, `/withdraw` | Same | Withdraw needs a reason; versions and results are kept |
| POST | `/assignments/{id}/submissions` | Student | JSON or multipart (`file`, up to 10 MB). New version; replacement before the deadline, late first submission inside the 7-day window, instructed resubmission (up to 2) |
| GET | `/submissions?assignment_id=&status=Awaiting Review&reviewer_me=true` | Staff | Newest version per student |
| GET | `/submissions/{id}`, `/submissions/{id}/file` | Owner, batch staff | Other students and other batches: 404 |
| POST | `/submissions/{id}/start-review`, `/review` | Staff of the batch | `outcome` Reviewed (marks up to the maximum) or Resubmission Requested (own deadline). Marks create a Provisional result |
| GET | `/assessments/curriculum?batch_id=` | Staff | Modules and topics of the course's Active curriculum versions (for linking) |
| GET / POST / PATCH | `/questions`, `/questions/{id}` | Trainer, BM, Super Admin | BM sees their branch bank; a trainer sees only the courses of the batches they teach there, plus questions they wrote. Type-specific answer key validation; keys never reach students |
| POST | `/questions/{id}/approve`, `/retire`, `/new-version` | BM / Super Admin (the author cannot approve) | Approved questions are frozen; a change is a new version |
| GET / POST / PATCH | `/tests`, `/tests/{id}` | Scoped | The student list shows every status of their batches' tests with their own state |
| PUT | `/tests/{id}/questions` | Batch staff | Approved questions of the batch's course and branch, frozen into the test |
| POST | `/tests/{id}/approve` | BM / Super Admin | Formal tests need it before release |
| POST | `/tests/{id}/release`, `/close` | Batch staff | Not Released to Released (Scheduled / Available / Closed by window) |
| POST | `/tests/{id}/attempts` | Student | 201 starts (deadline = min(start + duration, window end)); 200 resumes the open attempt |
| GET | `/attempts/{id}` | Owner, batch staff | Reading past the deadline submits the saved answers once |
| PUT | `/attempts/{id}/answers` | Student | Autosave; after the deadline `accepted: false` and the attempt is submitted |
| POST | `/attempts/{id}/submit` | Student | Idempotent; receipt `RCPT-T-00931` |
| GET | `/attempts?grading_status=Awaiting Grading&reviewer_me=true` | Staff | Grading queue; each row has `review_due` (3 / 5 / 7 working days by test kind, Module 20 §8). `status=In Progress` lists attempts not yet submitted (with `deadline_at`); overdue ones are submitted first |
| POST | `/attempts/{id}/grade` | Batch staff | Marks for Descriptive / Coding answers; complete means Graded, and for a formal test a Provisional result |
| GET / POST | `/tests/{id}/slots`, `/interview-slots/{id}/book`, `/confirm`, `/cancel`, `/complete` | Trainer offers, confirms, completes; student books | Open, Slot Confirmation Pending, Confirmed, Completed |
| GET | `/me/results` | Student | Only Published results carry a score |
| GET | `/results?batch_id=&assignment_id=&test_id=&status=` | Staff | Provisional, moderated and final marks |
| GET | `/assessment-reviews` | Staff | Moderation queue per assessment and batch, plus tests not ready |
| POST | `/results/{id}/moderate`, `/results/publish` | BM / Super Admin | Moderate needs a reason (audited); publish by ids or `assignment_id` / `test_id`; students notified |

Job: `flask --app app jobs run attempts-expire`: submits attempts still open past their deadline, as of the deadline.
Review queues: `/submissions` rows waiting for review carry `review_due` (3 working days for routine assignments and labs, 5
for mini projects, 7 for final projects; Module 19 §8), from `services/review_clock.py`.

**Rules:**
- Student-visible marks and feedback exist only after publication; the one exception is the feedback attached to a
  resubmission request. Practice quizzes and mock tests are non-credit: scored at once, no result row. Formal kinds
  (Module test, Coding exercise, Final test, or `is_required`) need pass marks, a closing time and Branch Manager approval.
- The attempt clock is the server's: `started_at`, `deadline_at`, `submitted_at` (the deadline on timeout) and the
  receipt are set by the API and the database (a trigger rejects answers after the deadline or once submitted). Expiry
  is applied lazily on the next read or save.
- Scoring: exact-set multiple choice, numeric tolerance, accepted short-answer variants, no negative marking; written
  and coding answers wait for the trainer. Code is never executed (`Integration Unavailable`).
- Role groups in `services/context.py`: `ASSESSMENT_AUTHOR_ROLES`, `MODERATOR_ROLES`. Notification categories:
  Assignments, Reviews, Assessments, Results.

### 4.7 Attendance, progress, completion & certificates (`040`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/attendance/sessions` | Trainer, BM, SA, Founder (scoped) | Live / Delivered sessions with `seats`, `marked`, `attendance_state`, `locked`, `can_mark`; filters `batch_id`, `from`, `to`, `attendance=pending\|marked\|locked` |
| GET | `/attendance/sessions/{id}` | same | The register: one row per allocated enrolment, `label` ("Absent — recovery approved (REC-0041)"), summary, `locked`, `can_mark` |
| PUT | `/attendance/sessions/{id}` | Trainer of the batch, BM, SA | `{default_status?, entries: [{enrolment_id, status, remarks?}]}`; `default_status` fills only seats without an entry ("all Present, then exceptions"). Sets the joining date (first Present / Late) |
| GET | `/me/attendance` | Student | Per own enrolment: attendance measure + a row per Live / Delivered class since joining |
| GET | `/attendance/enrolments/{id}` | Scoped | Same block for one enrolment |
| GET / POST | `/attendance/recoveries` | Scoped / Student, Trainer, BM, SA | Raise `{attendance_id, method, reason}` for an Absent entry; one live recovery per absence |
| POST | `/attendance/recoveries/{id}/decision` | BM, SA | `{decision: Approved\|Rejected, decision_note?, target_date?}` |
| POST | `/attendance/recoveries/{id}/completion` | Trainer of the batch, BM, SA | `{evidence_note}` verifies an approved recovery (Completed) |
| GET / POST | `/attendance/corrections` | Scoped / Student, Trainer, BM, SA | `{session_id, enrolment_id, requested_status, reason}`: a dispute, or a change after the lock |
| POST | `/attendance/corrections/{id}/decision` | BM, SA (fresh auth) | Approve applies the change; the decider must not be the requester or the marker |
| GET | `/me/progress`, `/progress/enrolments/{id}` | Student / Scoped | The four measures (`delivery`, `attendance`, `required_learning`, `engagement`), never combined |
| GET | `/progress/students` | Staff (scoped) | Table with filters `branch_id`, `course_id`, `batch_id`, `status`, `alert`, `q` |
| GET | `/progress/summary` | BM, SA, Founder | Per-batch averages of each measure, enrolments and certificates by status |
| GET | `/completion-reviews` | Staff (scoped) | Running / completed enrolments with evidence, latest review, certificate status |
| POST | `/completion-reviews` | Trainer, BM, SA | `{enrolment_id}` opens a review (201, or 200 with the open one) |
| POST | `/completion-reviews/{id}/recommendation` | Trainer of the batch, BM, SA | `{recommendation, comment?}` |
| POST | `/completion-reviews/{id}/decision` | BM, SA (fresh auth) | `{decision: Complete\|Not Yet\|Needs Recovery, reason?}`; Complete needs a Complete recommendation by a trainer of a batch the enrolment was allocated to (Module 22 §2) and → enrolment Completed + Course Completion Certificate eligibility. An Internship Certificate entry stays Not Yet Eligible: it needs internship evidence |
| GET | `/certificates`, `/certificates/{id}`, `/me/certificates` | BM, SA, Founder (branch scope) / Student (own) | Register entries (every version) with `actions` the caller may take; detail has `history` |
| POST | `/certificates` | BM, SA | `{enrolment_id, certificate_type}` adds an entry (e.g. Internship Certificate) |
| POST | `/certificates/{id}/recommendation`, `/return`, `/approval`, `/issue` | BM, SA | Approval and issue need fresh auth. The Branch Manager decides alone: approval may be given straight from Eligibility Review (the recommendation is recorded with it). Recommendation and issue need the fee cleared (`fee_clearance` on every register row: Cleared, Outstanding, Not Received, Released by exception) |
| POST | `/certificates/{id}/change-requests` | Correction: BM, SA. Revocation / Reinstatement: BM, SA, Founder | `{kind: Correction\|Revocation\|Reinstatement, reason, evidence?, holder_name?}`; evidence required for revocation and reinstatement. One pending request per certificate (409). The certificate is unchanged until approved |
| GET | `/certificate-requests?status=&kind=` | BM, SA, Founder (branch scope) | Each row has `actions: ["decide"]` when the caller may decide it |
| POST | `/certificate-requests/{id}/decision` | Correction: BM, SA. Revocation / Reinstatement: Founder, SA (fresh auth; never the requester) | `{decision: Approved\|Rejected, note}` (note required to reject). Approving applies it: a correction issues v+1 under the same number (`resulting_certificate_id`); a revocation revokes; a reinstatement returns Revoked → Issued with the same number and issue date, the revoked interval kept in `status_history` |
| POST | `/certificates/{id}/financial-exception` | BM, SA | `{reason}`: asks for the paying admission to be released for certificates while its fee is Outstanding |
| GET / POST | `/certificate-financial-exceptions`, `/{id}/decision` | BM, SA, Founder / Founder, SA (fresh auth; never the requester) | `{decision, note}` (note required). Approved exceptions satisfy the fee gate for that certificate type; the debt is not waived |
| GET | `/certificates/verify/{number}?version=` | Public | The presented version (latest by default): `state` Valid — Current Version, Superseded (with `current_version`) or Revoked; holder, course, type, branch, issue date, original issue date |

**Rules:**
- Attendance confirmation: job `attendance-unconfirmed` alerts the branch's Branch Managers, once per class, when a
  delivered class still has unmarked seats on the next working day (Module 21 §3); `marked_at` stays separate from the
  class date.
- Attendance: no row = "Not yet marked" (never a guessed absence). A session locks `attendance_lock_days` (7) after it
  ends; later changes go through a correction with an independent reviewer. Absent students get an in-app notification.
- Joining date: `services/attendance.set_joining_date(enrolment, date)` — the first Present / Late moves "Allocated —
  awaiting first regular class" to Active and opens the enrolment's Certificate Register entry (Not Yet Eligible).
- Progress is computed by SQL views (`enrolment_progress` and the views under it). Attendance % = (Present + Late) /
  marked classes delivered while the enrolment held a seat in the batch (from the allocation's `effective_from`, so
  absences before the first Present count; `delivered_since_joining` keeps its name); "Partial Data" while any delivered
  class is unmarked; the alert needs three marked classes and `attendance_alert_threshold`. Excused counts against the
  percentage; a recovery is reported separately and counts towards required learning only once Completed.
- Certificates: the database validates transitions and allocates `NIT-CERT-YYYY-NNNNNN` at first issue; a reissue is a
  new version under the same number and supersedes the earlier one. Complimentary enrolments stay "Configuration
  Pending" until `complimentary_completion_rule_configured` is true. Each Issued / Superseded / Revoked version is sent
  to the CRM (`CertificateChanged`).

### 4.8 Student services: support, notifications, career, profile, finance, Ask Nipuna (`050`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/support-requests` | Scoped | Filters `status`, `category`, `open`, `mine`, `escalated=true` (escalated to the Branch Manager), `branch_id`, `student_id`, `q`. Student: own; trainer: requests they own or raised; BM: their branch; admin: all |
| POST | `/support-requests` | Student; staff for a student (`student_id`) | `{category, details, subject?, priority?, enrolment_id?}`. Routed to a named owner; staff raising for a student = "Staff flag" |
| GET | `/support-requests/{id}` | Scoped | With the thread; internal remarks are left out for a student |
| POST | `/support-requests/{id}/messages` | Scoped | `{body, internal?}`; a staff reply moves Open to In Progress, a student reply moves Waiting on Student to In Progress |
| POST | `/support-requests/{id}/status` | Owner / branch BM / admin | `In Progress`, `Waiting on Student`, `Resolved` (note required), `Closed` |
| POST | `/support-requests/{id}/close`, `/reopen` | Student closes a Resolved request; student or manager reopens with a reason | Reopen gives a fresh SLA clock |
| POST | `/support-requests/{id}/escalate` | Staff | A trainer-owned request goes to the Branch Manager (the owner changes); any other request is marked escalated to the Branch Manager |
| POST | `/support-requests/{id}/assign` | BM / admin | `{owner_user_id}`, must work at the request's branch |
| GET | `/trainer/students` | Trainer | Students with active seats in their batches + open-request flag |
| GET | `/notifications` | Signed in | Own only. `view` = my, action, unread, completed or system; `category`, `q`; each item has `delivery_label`. Staff see a branch notice only while they still hold its role (any role, for notices to named people) at that branch or company-wide; the same rule applies to counts, read and actions. Students keep their own |
| GET | `/notifications/overview` | Signed in | `{unread, action_required, categories}` for the header bell |
| POST | `/notifications/{id}/read`, `/acknowledge`, `/action-done`, `/notifications/read-all` | Recipient | Separate states; acknowledging also reads, does not complete the action |
| GET / PUT | `/notifications/preferences` | Signed in | Group × channel matrix; In-app always on; WhatsApp / Email carry their integration status |
| GET | `/me/career` | Student | Profile + completeness, CVs, eligible opportunities, applications, outcomes, next action |
| PUT | `/me/career/profile`, `/me/career/consent` | Student | Opt in / out; employer-sharing consent is separate |
| POST | `/me/career/cvs` (multipart `file`, `label`) | Student | New version, older ones marked Superseded |
| POST | `/me/career/opportunities/{id}/apply`, `/me/career/applications/{id}/withdraw` | Student | Needs opt-in, consent, a Reviewed CV; one application per opportunity and cycle |
| GET | `/cv-documents/{id}/download` | Student / branch staff | |
| GET / POST / PATCH | `/opportunities`, `/opportunities/{id}` | BM, Super Admin | Branch-scoped; editing a verified one sends it back to Verification Pending |
| POST | `/opportunities/{id}/status` | BM, Super Admin | Draft, Verification Pending, Active (verifier is not the creator, needs `verification_source`), On Hold, Closed |
| GET | `/career-profiles`, `/career-profiles/{student_id}` | BM, Super Admin | |
| POST | `/career-profiles/{student_id}/review`, `/cv-documents/{id}/review` | BM, Super Admin | Readiness + skill verification; CV Reviewed / Changes Requested |
| POST | `/career-profiles/{student_id}/extend-support` | Super Admin, Founder (fresh auth) | `{support_end, reason}`, audited |
| GET | `/applications`, `/applications/{id}` | BM, Super Admin | With status history |
| POST | `/applications/{id}/status` | BM, Super Admin | Any stage may be recorded (stages can be skipped); closed applications are final |
| GET / POST | `/placement-outcomes` | BM, Super Admin | Recorded as Pending Verification |
| POST | `/placement-outcomes/{id}/verify` | BM, Super Admin | `{decision: Verified or Rejected, evidence_note}`; not by the recorder |
| GET | `/placement-outcomes/summary` | BM, Super Admin | Verified outcomes and distinct students per type (reports read this) |
| GET / PATCH | `/me/profile` | Signed in (PATCH: student) | Identity with masked mobile, devices, language. Staff get role, branch, devices, last sign-in |
| POST | `/me/devices/sign-out-others` | Signed in | Revokes every other session |
| GET | `/me/finance` | Student | Read-only CRM data: `admissions[]` (one per course: its own fee, verified paid, balance, receipts) and `schedules[]` (each instalment schedule **once**: per invoice when `installments_scope = invoice`, listing the courses it covers, with `next_due_*` and `overdue_amount`) |
| GET | `/finance-summaries` | BM (service or collecting branch), Super Admin, Founder | Filters `branch_id`, `student_id`, `has_balance`. `meta.totals`: `balance` summed per admission; `overdue_amount` and `next_due_amount` summed once per schedule |
| GET | `/finance-summaries/{admission_id}` | Same | One admission plus its `schedule` |
| GET | `/ask-nipuna/status` | Signed in | `AI Available` / `Configuration Pending` / `Quota Limited` / `Disabled`, usage today, actions, scope. Disabled while `ai_enabled` is false or an AI control covers the caller's audience and branch |
| GET / POST | `/ai-controls`, `/ai-controls/{id}/restore` | Super Admin, Founder (fresh auth to change) | Switch AI off: `{audience: Student\|Staff\|All, branch_id?, reason, remediation?}` (`All` is Founder only and company-wide). Restore with `{restoration_note}` (the checks that passed) |
| POST / GET | `/ask-nipuna/queries` | Signed in | Ask (refusals are answered with `status: Refused` and do not use the allowance); own history |
| POST | `/ask-nipuna/queries/{id}/feedback` | Asker | `Helpful` / `Not helpful` (+ comment); a report notifies the branch's Branch Managers |

Job: `flask --app app jobs run support-escalate-overdue`.

**Rules:**
- Every support request has a named owner (routing table in `services/support.py`); the owner label reads like the
  prototype ("Branch Manager — Guntur", "LMS Support — Vijayawada"). Status moves follow a database trigger
  (`Open → In Progress / Waiting on Student / Resolved`, `Resolved → Closed / Open`, `Closed → Open`). The
  `support-escalate-overdue` job escalates requests past `app_settings.support_sla_hours` (48) to the Branch Manager;
  run it from a scheduler.
- Notifications reuse the backbone table; `050` adds `channel` and `delivery_note` (a WhatsApp / email notice that was
  not sent is `Failed` with the reason and shows under System Issues). Preferences are stored, but nothing is sent on
  WhatsApp / email until those integrations are verified.
- Ask Nipuna calls `client.messages.create(model=AI_MODEL, ...)` only when `ANTHROPIC_API_KEY` is set; otherwise, or
  when the provider fails, `services/ai_rules.py` answers from the same permitted facts. Facts come from
  `services/ai_facts.py`; modules add facts with `register_fact_provider(name, fn)` (`services/ask_nipuna.py` registers
  `due_work` from `services/due_work.py`: the student's open assignments and tests). Questions about other students,
  fee changes, marks / attendance / certificate changes, secrets and prompt injection are refused before anything is
  retrieved. Daily allowance: `ai_daily_limit` 50 (student) and `ai_daily_limit_staff` 100 per IST day; `ai_enabled`
  switches it off.
- Career: verified outcomes are exposed through the `verified_placement_outcomes` view and
  `GET /placement-outcomes/summary`; "Verified" needs evidence and a verifier other than the recorder (database CHECKs).
- Finance shows only what `finance_summaries` holds; pending payments are never receipts. A multi-course invoice's
  instalments are shown and summed once, never per admission.
- `services/context.client_user_agent()` returns the User-Agent string (werkzeug's `UserAgent` object is falsy); the
  profile screen labels devices from it.

### 4.9 Admin & security (`060`)

Super Admin manages; the Founder / CEO can read every list (mutations are Super Admin only, all with fresh auth).
Nothing here calls an external system.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/integrations` | Super Admin, Founder | Register: requirement, configuration, verification, owner, evidence, verified by / at, last check |
| GET | `/integrations/status` | Any signed-in user | `[{integration_code, configuration_status, verification_status, state}]`, `state` = Verified / Pending Verification / Integration Unavailable |
| GET, PATCH | `/integrations/{id}` | Super Admin (PATCH, fresh auth) | PATCH any of `configuration_status`, `verification_status`, `owner`, `evidence`, `notes` |
| GET | `/security-controls`, `/security-controls/{id}` | Super Admin, Founder | Same shape as the integrations register (`control_code`, `category`, `title`) |
| PATCH | `/security-controls/{id}` | Super Admin (fresh auth) | Same rules as integrations |
| GET | `/admin/users?q=&role_code=&branch_id=&is_active=` | Super Admin, Founder | Staff logins (never students) with live role scopes |
| POST | `/admin/users` | Super Admin | `{full_name, email, phone?, scopes: [{role_code, branch_id?, expires_at?}]}` → 201 with `temporary_password` (once); `must_change_password` set |
| GET, PATCH | `/admin/users/{id}` | Super Admin (PATCH) | PATCH `full_name`, `email`, `phone` |
| POST | `/admin/users/{id}/scopes` | Super Admin | Grant a role scope; company-wide roles take no branch, branch roles need one; `expires_at` (temporary access) at most 7 days ahead |
| POST | `/admin/users/{id}/scopes/{scope_id}/revoke` | Super Admin | `{reason}`; not your own access; not the last active Super Admin |
| POST | `/admin/users/{id}/deactivate`, `/reactivate` | Super Admin | Deactivate `{reason}` ends all sessions; not yourself, not the last Super Admin |
| POST | `/admin/users/{id}/reset-password` | Super Admin | New `temporary_password` (once), sessions ended, lockout cleared, must change at next sign-in |
| GET | `/admin/students?q=&activation_status=&activation_channel=&branch_id=` | Super Admin, Founder | Search by Student ID, name, email; activation status, LMS account (`lms_user_id`, login state, active sessions), enrolment counts. `activation_channel=CRM provisioning` finds students whose link the CRM never delivered |
| GET | `/admin/students/{id}` | Super Admin, Founder | Adds enrolments, outstanding activation link state (never the token), suspension reason, recent audit |
| POST | `/admin/students/{id}/suspend`, `/reactivate`, `/revoke-sessions` | Super Admin | Suspend `{reason}`: blocks sign-in, ends sessions, cancels the activation link. Reactivate returns to Activated (password set) or Account Created |
| GET | `/admin/crm-sync/summary` | Super Admin, Founder | Counts by status for the inbox and outbox, last received / delivered, oldest pending |
| GET | `/admin/crm-sync/events?status=&event_type=&q=&from=&to=`, `/events/{id}` | Super Admin, Founder | List without payload; detail with payload and result |
| POST | `/admin/crm-sync/events/{id}/retry` | Super Admin (fresh auth) | Re-applies a Failed event; audited `CRM_EVENT_RETRIED` on success |
| GET | `/admin/crm-sync/outbox?status=&event_type=`, `/outbox/{id}` | Super Admin, Founder | Values queued for the CRM |
| GET | `/audit-log?actor_user_id=&entity_type=&entity_id=&action=&branch_id=&from=&to=`, `/audit-log/facets` | Super Admin, Founder | Newest first with the actor's name; `from` / `to` are inclusive IST dates; facets list the distinct actions and entity types |

**Rules:**
- `services/integrations.py` exposes `integration_status(code)` (`.state`, `.is_verified`) and `is_verified(code)` for
  other modules; an unknown code counts as Not Configured / Not Verified. `GOOGLE_MEET` gates
  `class_sessions.meet_status`, `GOOGLE_DRIVE_RECORDINGS` gates recording import.
- Readiness rules (integrations and security controls share `services/readiness.py`): *Verified* needs a Configured
  setup and an evidence note and records `verified_by` / `verified_at`; taking a Verified record out of Configured drops
  it to Not Verified; any status or evidence change sets `last_checked_at`. The database CHECK `*_verified_needs_evidence`
  enforces the same. Audit actions: `INTEGRATION_UPDATED`, `SECURITY_CONTROL_UPDATED` (entity id = code, old / new of
  the changed fields only).
- Staff account actions are audited on the `user` entity (`USER_CREATED`, `USER_UPDATED`, `SCOPE_GRANTED`,
  `SCOPE_REVOKED`, `USER_DEACTIVATED`, `USER_REACTIVATED`, `PASSWORD_RESET`) and student actions on the `student` entity
  (`STUDENT_SUSPENDED`, `STUDENT_REACTIVATED`, `STUDENT_SESSIONS_REVOKED`, plus the activation actions). Passwords and
  tokens are never written to the audit log.
- The platform always keeps an active Super Admin: the last one cannot be deactivated or lose the scope, and nobody can
  revoke or deactivate themselves.
- `GET /integrations/crm/events` and `POST /integrations/crm/events/{id}/retry` (§4.2) remain; the admin screen uses
  the `/admin/crm-sync/*` equivalents (payload only on detail, audited retry).

### 4.10 Student Home, Trainer Today & reports

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/me/home` | Student | One response for Student Home: `student`, `primary_enrolment` and the cards `next_class` (with Join state), `due_work`, `course_progress`, `continue_learning`, `latest_recording`, `upcoming_work`, `attendance_alert`, `certificate`, `career`, `support`, `ask_nipuna`, `engagement`. Own data only |
| GET | `/trainer/today` | Trainer | `tiles` (`sessions` next 7 days, `reviews` awaiting with the oldest's age, `support_flags`) and `today` (the trainer's sessions for today's IST date with Meet, attendance and recording-mapping state); assigned batches only |
| GET | `/trainer/reports` | Trainer | `batches` (delivery and attendance averages per assigned batch), `review_turnaround`, `engagement` |
| GET | `/academic/reports` | BM, Super Admin, Founder | One block per visible branch (`?branch_id=` narrows; another branch is 404): `curriculum_delivered`, `attendance` (with approved-recovery counts), `completion_reviews`, `certificate_lead_time` |

**Rules:**
- Every card is `{state: "Ready" | "Empty" | "Unavailable", message?, ...}`. `services/cards.safe_card` runs each
  card's source inside a savepoint, so one failing source marks only its own card Unavailable (logged) and the screen
  still renders. A measure with nothing behind it is `Empty` / `null` ("Not Yet Calculable"), never 0.
- Student Home reads existing services only: next class and Join state from `class_sessions.list_sessions(upcoming)`
  and `meet.join_state` (the Meet link is never returned while joining is closed), due work and the next test from
  `due_work.open_items` (the same rules as Ask Nipuna's `due_work` provider), curriculum-delivered % and certificate
  status from `progress.my_progress`, continue-learning from the batch's sessions (last Delivered class's topic, else
  the next scheduled one; track from `content_repo.track_labels`), the latest Released recording and its access-until
  date from `recordings.student_recordings`, the latest absence and its recovery reference from
  `attendance.enrolment_attendance`, career opt-in and profile % from `career.home_summary`, open support requests and
  owner from `support.list_requests`, usage from `ask_nipuna.status`. The primary enrolment is the first Active one,
  else the first being studied.
- Engagement freshness: there is no separate engagement refresh job, so `refreshed_at` is the latest recorded learning
  activity for the primary enrolment. With none inside `engagement_window_days` (14) the card is `Stale` (level
  withheld), never zero.
- Trainer Today counts sessions with `trainer_user_id = me` that start in the next 7 IST days and are still Scheduled /
  Rescheduled / Live; "submissions awaiting my review" is the newest version per student with no review, for
  assignments where the trainer is reviewer; support flags reuse `support.assigned_students`. The "Today's flow" stepper
  drives existing endpoints: `POST /class-sessions/{id}/start`, the session's Meet link, `POST .../deliver`,
  `PUT /attendance/sessions/{id}`, `PUT .../notes`. Recording mapping shows Pending Verification until a recording is
  registered for the session.
- Reports: batch averages come from `progress_repo.batch_summaries` (each measure averaged separately, weighted by
  students for the branch figure). Review turnaround is `reviewed_at - submitted_at` over the trainer's reviews; a pair
  with a missing or impossible timestamp is left out and makes the figure `Partial Data`. Academic: curriculum delivered
  covers Running batches only (`Partial Data` when a running batch has no figure yet), recovery counts come from
  `attendance_recoveries` by batch branch, completion reviews closed is `Partial Data` when Completed enrolments have no
  review record, and certificate lead time (completion decision to issue date) is `Not Configured` until an issued
  certificate traces back to a decided review.
- Code: aggregates in `repositories/reports.py`; services `student_home.py`, `trainer_workspace.py`,
  `academic_reports.py`; routes `home.py` and `reports.py`.

### 4.11 Exception queue & staff dashboards (`080`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/exceptions` | BM (own branch), Super Admin / Founder (all, incl. company-wide rows) | Open exceptions from every module, oldest first. Filters `source`, `state`, `queue`, `branch_id`, `awaiting_owner`; `?page=&per_page=`. A `branch_id` outside the user's scope returns an empty list |
| GET | `/exceptions/{source}/{source_id}/steps` | Same as above | Recovery steps, newest first; 404 outside scope |
| POST | `/exceptions/{source}/{source_id}/steps` | BM (of the item's branch), Super Admin | `{reason}` (3–1000 chars). Audited (`EXCEPTION_STEP_LOGGED`, with the item, reason and branch); returns `{step, exception}`. The logger becomes the named owner of an item that had none. The Founder gets 403; an item outside scope is 404 |
| GET | `/academic/summary` | BM, Super Admin, Founder | `?branch_id=` narrows (404 outside scope). Allocation queue, results awaiting publication, recording exceptions, batches ready, reviews awaiting (content / completion / certificates), open exceptions, batches not ready |
| GET | `/branch/summary` | BM, Super Admin, Founder | `?branch_id=`. CRM figures (from `BranchFinanceSnapshot`, else Not Configured), running batches, schedule and recording exceptions, escalations and extension requests |
| GET | `/admin/summary` | Super Admin, Founder | Integration failures, work awaiting a named owner, integrations verified, provisioning, open exceptions per source, CRM / LMS sync flows, AI status |
| GET | `/founder/summary` | Founder, Super Admin | CRM figures (from `BranchFinanceSnapshot`, else Not Configured), active enrolments per branch, batches at risk, certificates awaiting approval, decisions (AI ceiling, post-2nd-anniversary access requests) |

**Rules:**
- `exception_queue` is a **view** over each module's own records, so an exception leaves the queue when its module
  resolves it; nothing is copied or closed by the queue. Sources (`source`; the id is the record's id in its own table):
  `ALLOCATION` (enrolments in `Allocation Pending`; `CURRICULUM_MAPPING` rows ended with db 105 and stay only as recovery-step history),
  `PROVISIONING` (enrolments in `Provisioning Pending`: a complimentary offer whose qualifying payment gate is unmet),
  `RECORDING` (unresolved `recording_exceptions`), `CRM_EVENT` (events with status Failed; company-wide), `SUPPORT`
  (open requests escalated or past `sla_due_at`), `RESULTS` (provisional or moderated results, one row per batch),
  `ACCESS_EXCEPTION` (pending access requests that `needs_exception`), `INTEGRATION` (verification Failed or
  configuration Misconfigured; company-wide). Rows with no branch are visible to Super Admin and Founder only.
- Owner: the record's own named owner, else the last person who logged a recovery step; `owner = null` /
  `awaiting_owner = true` means "awaiting named owner", and `owner_label` names the role that should take it ("Branch
  Manager — Guntur"). State is the record's own state, shown as `Recovery In Progress` once a step is logged on an
  otherwise `Open` item.
- `exception_recovery_steps` is append-only (trigger). Logging a step does not change the source record; resolving
  happens on the screen in `link`.
- Dashboard summaries only aggregate: counts come from `repositories/dashboards.py` (branch filter over each module's
  own statuses), `exception_queue`, the integrations register, `services/crm_sync.summary()` and
  `ask_nipuna.status()`. They carry `as_of` and a `scope` block (branches, label); Branch Manager is locked to their branches by `services/scope`.
- **CRM-authoritative figures** (verified collections vs target, new paid Admissions, overdue amount, overdue payment
  verifications, overdue follow-ups) are summed over the branches in view from each branch's latest
  `BranchFinanceSnapshot`: `{state: "Configured" | "Partial Data", unit ("INR" money as a string, or "count"), value,
  target, period, as_of, stale, missing_branches, detail}`. With no snapshot for any branch in view they stay
  `{"state": "Not Configured", "reason", "refreshed_at"}`, never 0
  ([CRM_INTEGRATION.md §2.1](CRM_INTEGRATION.md#21-crm--lms-events), finance snapshot figures).
- The AI rupee ceiling is `app_settings.ai_monthly_ceiling_inr`; absent = `Configuration Pending` (Founder decision).
  "Critical integration failures" counts the readiness register (Failed / Misconfigured), not live monitoring.

### 4.12 Shell: navigation counts, Getting started and search (UX phase 4; no migration)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/me/nav-counts` | Signed in | `?workspace=student\|trainer\|branch\|admin\|founder` (required, must be a workspace the user holds, else 403); `?branch_id=` narrows the branch workspace (404 outside scope). Returns `{badgeKey: n}`, cheap counts only, polled every minute with the bell |
| GET | `/me/getting-started` | Signed in | Same query. `{workspace, steps: [{key, label, done, to}], complete}`; the Founder has no steps. Whether the card was dismissed is kept in the browser, not here |
| GET | `/search` | Signed in | `?q=` (two characters or more). `[{kind: student\|batch\|certificate, id, title, subtitle}]`, at most 5 per kind, within the caller's scope: Branch Manager their branches, trainer the batches they teach and the students in them, Super Admin / Founder everything, a student nothing. Pages are not searched here (the client lists the pages of the user's workspaces). A record outside scope is simply absent |

**Badge keys** (the `badgeKey` of a navigation item in `frontend/src/auth/access.ts`):
- `student`: `tasks` (open assignments and tests), `support` (requests waiting on the student).
- `trainer`: `to_grade` (submissions awaiting review plus test attempts awaiting grading, for the trainer's own reviews), `support` (open requests they own).
- `branch`: `waiting` (enrolments in Allocation Pending), `requests` (open reschedule requests, escalations, extension requests), `content_review`, `marks` (results awaiting publication), `completion` (open completion reviews), `certificates` (Eligibility Review or Awaiting Approval), `issues` (open exceptions), `recording_issues`, `support` (open requests past, or within 4 hours of, `sla_due_at`), `attendance` (recoveries requested plus corrections pending).
- `admin`: `crm_sync` (failed events), `issues` (exceptions with no named owner), `users` (locked accounts).
- `founder`: `curriculum` (versions Under Review), `certificates` (Awaiting Approval), `access` (access requests that need an exception).

**Getting started steps** (done is read from the records, so the card ticks itself): student: activate (always), batch (an active seat), class (attended one), task (submitted one). Trainer: open a class (one of theirs is Live or Delivered), mark attendance, grade a submission. Branch Manager: create a batch, allocate students, create classes (anything at the branches in view). Admin: add a staff user (a `USER_CREATED` audit entry by the caller), review setup (an integration is no longer Not Configured).


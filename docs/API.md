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
| `SUPER_ADMIN` | All branches, read-only through the shared reads (batches, students, attendance, support, reports, issues, finance summaries; `?branch_id=` narrows them), plus admin / integrations / security and the decisions listed in §4.22. No branch day-to-day actions |
| `FOUNDER_CEO` | Everything the Super Admin can do on the backend, plus the Founder's inbox and approvals. Reads across all branches; no branch day-to-day actions either |

A login holds **one** role (db 119) and the session carries it (§4.22): every row above is the whole of what that login sees, never a union.
A Branch Manager sees only the branch picked at sign-in, even if the account holds several.

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
| `course_modules` | Course (or one combo track, `component_id`) → ordered modules (`Supervised Learning`); archived ones are hidden (db/121) |
| `course_topics` | Module → ordered topics, `is_required` |
| `students` | Student Master: `student_code`, `crm_person_id` (unique), full_name, name_te, email (optional), mobile (not unique), original / service branch, preferred_language, `activation_status` (`Account Created` / `Activation Pending` / `Activated` / `Suspended`), mfa_status |
| `student_activations` | Activation tokens (hash, expires_at, used_at, issued_by, channel) |
| `admissions` | CRM projection: `crm_admission_id` unique, `admission_code`, student, **one course**, original / service / collecting branch, crm status, mode, seat type, planned start, `complimentary_of_admission_id`, `source_version` |
| `enrolments` | `enrolment_code`, admission, student, course, `kind` (`Combo`, `Standalone`, `Separately purchased`, `Complimentary`), `parent_enrolment_id` (complimentary → qualifying enrolment), service branch, mode, `status` (`Provisioning Pending`, `Allocation Pending`, `Allocated — awaiting first regular class`, `Active`, `Paused`, `Completed`, `Withdrawn`), joining_date (first regular class attended), access_start / end, certificate_status, benefit gate note |
| `enrolment_tracks` | Combo enrolment → component track |
| `finance_summaries` | Read-only per-admission finance snapshot from CRM: fee, verified paid, pending verification, waived, refunded, balance, payment completion, invoice numbers, instalments (+ `installments_scope`, `invoice_course_count`), next due, receipts, `as_of`, `source_version` |
| `crm_events` | Inbox: `event_id` unique, `event_type`, payload jsonb, `source_version`, original event time, received / processed time, status (`Received` / `Applied` / `Ignored — stale` / `Failed`), error, retries |
| `crm_outbox` | Values the CRM keeps about the LMS, queued in the same transaction as the change |
| `batches` | `batch_code`, course, branch, capacity, mode, planned start / end, `state` (`Forming`, `Starting`, `Running`, `Full`, `Completed`, `Cancelled`), readiness (`Ready` / `Blocked` / `Pending Verification`) + reason + recovery owner |
| `batch_trainers` | Batch ↔ trainer user (`Lead` / `Co-trainer`), from / to |
| `batch_allocations` | Enrolment (or enrolment track) ↔ batch with effective dates, status, reason; history retained |
| `class_sessions` | Actual Class Session: `session_code`, batch, topic, title, scheduled start / end (timestamptz), mode (`Classroom` / `Live Online` / `Hybrid`), trainer, room, `meet_link` + `meet_status`, `state` (`Scheduled`, `Live`, `Delivered`, `Cancelled`, `Rescheduled`), delivered_at, notes |

### Module tables

| Module | Migration | Owns |
|---|---|---|
| Delivery | `010` | `batch_events`, `session_changes`, `session_change_requests`, `meet_events` — plus all delivery APIs over the backbone |
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
| POST | `/auth/login` | Public | `{login, password, branch_id?}` — `login` is a staff email, a Student ID or a student email. `branch_id` is for a Branch Manager with several branches (§4.22); the answer is the profile below plus `token` and `expires_at` |
| POST | `/auth/logout` | Signed in | Revokes the session |
| GET | `/auth/me` | Signed in | The session's profile (§4.22): `user`, `role`, `workspace`, `branch`, `needs_branch`, `branches`, `scopes`, `allowed_branches`, `workspaces` (one element), `home_route`, `student` |
| POST | `/auth/branch` | Signed in (Branch Manager) | `{branch_id}` — picks the branch for a session that has `needs_branch`. Answer: the profile. 403 for a branch not on the account; 422 when a branch is already chosen |
| POST | `/auth/change-branch` | Signed in (Branch Manager) | `204`. Ends the session; the person signs in again and picks a branch |
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
  while a removed component is still used by enrolment tracks or outline modules.
- `AdmissionQualified` upserts the Student by `crm_person_id` (one Student / one LMS login per Person, reused for later
  admissions), the Admission projection and its Enrolment. A new enrolment is *Allocation Pending* (or *Provisioning
  Pending* while a complimentary gate is unmet); it follows the outline of its course (no version to map). A new login gets an activation token; the branch
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

### 4.4 Delivery: courses and outlines, enrolments, batch allocation, class sessions, student course pages (`010`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/courses` | BM, Super Admin, Founder / CEO | The Courses page list (R6, db/121): per course `course_id`, `course_code`, `title`, `category`, `is_combo`, `status`, `components` (all CRM-owned, read-only), `counts: {modules, topics, required_topics}`, `hours_verified`, and `usage: {running_batches, students_waiting, active_enrolments, by_branch}`. `running_batches` and the others count the caller's branch (a Branch Manager: the session branch); Super Admin / Founder count company-wide and `by_branch` lists `{branch, running_batches, active_enrolments}` |
| GET | `/courses/{id}/outline` | Everyone who can see the course: BM, Super Admin, Founder; a trainer with a batch of the course; a student enrolled in it (others 404) | `{course, can_edit, counts, modules: [{module_id, component_id, title, title_te, sort_order, library_version_id, topics: [...]}], tracks: [{component, modules, borrowed_from}]}`. `modules` is the course's own outline; each combo track has its own `modules` (or the pinned course's, `borrowed_from`). BM, Super Admin and Founder also get `totals` (instructional / independent / total minutes, `unestimated_topics`, `hours_verified`, `booster`), `completion_profile`, `assessment_requirements` and `usage`. There are no curriculum versions, drafts or approvals |
| POST | `/courses/{id}/modules` | Super Admin, Founder (fresh auth) | `{title, title_te?, position?, component_id?}` (`component_id` = a combo track's own outline) |
| PATCH / DELETE | `/course-modules/{id}` | Super Admin, Founder (fresh auth) | Rename / reorder (`position`); delete. A module whose topics classes, content or tests use is archived (hidden from the outline, nothing lost) instead of deleted |
| POST | `/course-modules/{id}/topics` | Super Admin, Founder (fresh auth) | Optional `position` |
| PATCH / DELETE | `/course-topics/{id}` | Super Admin, Founder (fresh auth) | Sort order re-sequenced. A topic has `topic_class` (Required / Recommended / Optional; `is_required` follows it), `outcome`, `instructional_minutes`, `independent_minutes`, `weight`, `evidence`, `activities` and `depends_on` (topic ids of the same outline, no loops). A topic that classes, content, assignments, questions or tests use cannot be deleted (422) |
| POST / PUT | `/courses/{id}/hours-verification`, `/completion-profile` | Super Admin, Founder (fresh auth) | Verifying needs every topic estimated; changing minutes clears it. Profile: `attendance_minimum_pct`, `pass_mark_pct`, `recovery_rule`, `reassessment_rule`. Both answer with the outline |
| POST / DELETE | `/courses/{id}/assessment-requirements`, `/assessment-requirements/{id}` | Super Admin, Founder (fresh auth) | The assessments the course requires: kind, title, outcome, weight, pass rule |
| PUT | `/courses/{id}/track-pins` | Super Admin, Founder (fresh auth) | `{component_id, pinned_course_id}` makes a combo track follow its own standalone course's outline (after `POST /course-components/{id}/equivalence` `{note}`, Module 14 §3); `pinned_course_id: null` unpins. Answers with the outline |
| GET / POST | `/course-library`, `/course-modules/{id}/library`, `/course-library/{id}/versions`, `/courses/{id}/library-modules` | BM, SA, Founder read; Super Admin, Founder write | Reusable modules with explicit versions, usable at once (no approval step). `POST /courses/{id}/library-modules` `{library_version_id, component_id?}` copies a version into the outline and keeps `library_version_id` |

Every outline edit applies at once, writes `COURSE_OUTLINE_CHANGED` to the audit log (entity `course`) and tells the Branch Managers of every branch with an open batch of the course (category `Courses`, link `/branch/courses/{course_id}`; the editor is not told). Course code, title, category, status and tracks are the CRM's (`CourseUpserted`): there is no endpoint to change them. Removed in R6: `/curriculum/overview`, `/curriculum-versions` and everything under it, `/curriculum-modules/*`, `/curriculum-topics/*`, `/academic-mappings`, `/equivalence-rules`, `/curriculum-variations`, `/curriculum-library*`, `/curriculum-versions/{id}/impact`, the `curriculum` inbox group and the `curriculum` nav count.

**Response shapes changed by R6** (the `curriculum_version` object is gone everywhere; the course is already in each payload): batches (`GET /batches`, `/batches/{id}`, create and update; `curriculum_version_id` is no longer accepted either), enrolments (`/me/enrolments*`, staff enrolment views, their `tracks[]`), content items (`placement()`), `GET /me/enrolments/{id}/tracks/{track_id}` (`enrolment` is the plain summary), `GET /modules/{id}` and `/topics/{id}` (`module` head: `course_id` and `component_id` replace `curriculum_version`). `GET /content-items/options`: `versions[]` became `outlines[]`. `GET /assessments/curriculum`: `version_label` replaced by `component_id` and `track_name`. Batch readiness check `curriculum` and checklist item `course_version` keep their keys; labels are now "Course outline" and "1. Course and outline". Ask Nipuna sources: `type: "course_outline"` (id = course id, code = course code) replaces `curriculum_version`. Founder inbox: no `curriculum` kind, group or `scheduled`; nav counts have no `curriculum` key. Batch history events "Curriculum changed" and "Curriculum mapped" are no longer written (old rows stay).
| GET | `/enrolments`, `/allocation-queue` | Staff / BM, Super Admin | Branch-scoped enrolment list; the queue of payment-cleared enrolments waiting for a seat, each with `allocation_due_on` (Module 15 §6: one working day after Admission for a confirmed seat, 48 hours before the first class for a future plan, never after the first class) |
| GET / POST | `/calendar/closures`, `/calendar/closures/{id}` | Staff / Founder, SA (company holiday); BM, SA (branch closure) | The Academic Calendar. A company holiday, and a branch closure added by a Super Admin or Founder, are Approved at once. A Branch Manager's closure (own branch only) is created `Pending` and only a Super Admin or Founder decides it (decision 18); the proposer is told the outcome. The detail lists `affected_sessions` (Scheduled / Live classes inside it) |
| POST | `/calendar/closures/{id}/decision` | SA, Founder (not the Branch Manager) | `{decision, note}` (note to reject). Approving asks the affected branches' Branch Managers to prepare replacements; no class is moved automatically |
| GET / POST | `/batches/{id}/allocations` | Staff / BM, Super Admin | Roster (filter `status`); allocate an enrolment, or one combo track with `enrolment_track_id` (a track batch takes only its track) |
| GET | `/batches/{id}/allocation-review?enrolment_id=&enrolment_track_id=&transfer=` | BM, Super Admin | The checks (branch, course / track, curriculum, capacity, mode, student timetable, batch state, enrolment state) as pass / warn / fail |
| POST | `/enrolments/{id}/deallocate` | BM, Super Admin | `{reason, enrolment_track_id?}`. Moving a seat is a transfer request (§4.4.1) |
| POST / PATCH | `/batches`, `/batches/{id}`, `/trainers`, `/readiness` | BM, Super Admin | Batch with `batch_events` history. The timetable: `schedule_days` (`["Mon", "Wed", "Fri"]`), `start_time` / `end_time` (`"HH:MM"` IST, both or neither), `location` (dropped for Live Online); each nullable. Module 15 fields: `display_name`, `batch_type` (Group / Individual / Corporate), `schedule_pattern` (Regular / Weekend / Fast-track), `component_id` (a track batch, Draft only), `classroom_capacity` / `lab_capacity` / `online_capacity`, `recording_provision` (Included / Not Included / Limited + `recording_terms`), `meet_series_link`, `meet_space_id`, `calendar_series_id`. Responses add `state_label`, `creating_branch`, `component`, `proposed_by` / `confirmed_by`; the detail adds `successions` and `handovers`. `GET /readiness` adds the 7-point `checklist` |
| GET | `/batches/{id}/progress` | Staff | UX phase 14, see §4.18: the steps, the next action, what still blocks a confirmation |
| POST | `/batches/{id}/confirm` | BM, SA | UX phase 14, see §4.18: propose and confirm in one step |
| POST | `/batches/{id}/generate-sessions` | BM, SA | UX phase 14, see §4.18: create classes from the batch timetable, with a preview |
| GET | `/batches/{id}/waiting` | BM, SA | UX phase 14, see §4.18: waiting students this batch could take |
| POST | `/batches/{id}/proposal`, `/batches/{id}/confirmation`, `/batches/{id}/state` | proposal: BM, SA; confirmation: BM, SA; state: see rules | `proposal {note?}`: Draft → Proposed once points 1–6 pass. `confirmation {decision: Confirmed / Returned, note?, override_reason?}`: never the proposer; warnings need `override_reason`. `state {state: Running / On Hold / Resume / Completed / Cancelled / Archived, reason?}`: On Hold, Resume and Archived by BM / SA; reason for On Hold and Cancelled |
| POST | `/batches/{id}/handovers` | BM, SA | `{enrolment_id, owner_user_id, plan, destination, destination_batch_id?}`: a student the batch still owes teaching (paused, not started), needed before Completed |
| GET / POST / PATCH | `/class-sessions`, `/class-sessions/{id}` | Staff; create / edit BM, Super Admin | Filters include `batch_id`, `trainer_id`, `state`, `purpose`, `approval_status`, `from`, `to`; create accepts a weekly `recurrence` (weekdays, `until` / `count`), `purpose` (Regular / Replacement / Remedial / Extra) with `replaces_session_id`, `purpose_reference`, `owner_user_id`, `due_on`, the Meet ids, and `override_reason` for an advisory clash. Changing the trainer by PATCH is the Branch Manager's (others request cover). Responses add `state_label`, `original_starts_at` / `original_ends_at`, `confirmed_at`, `approval_status`, the delivery log and the Meet ids (staff) |
| POST | `/class-sessions/{id}/start`, `/deliver`, `/cancel`, `/reschedule` | Trainer of the class (start, deliver); BM, Super Admin (cancel, reschedule) | Reason required for cancel / reschedule; `session_changes` row with notice hours and `short_notice`; inside 24 hours also `emergency_reason` and `next_action`. Deliver is the class log: `{outcome: Held / Partially Held, actual_start?, actual_end?, break_minutes?, unfulfilled_note? (required when Partially Held), notes?, topic_ids?, attendance?: [{enrolment_id, status, remarks?}], attendance_default_status?}` (missing times default to the start and scheduled end). `topic_ids` are topics of the batch's course covered in the class (kept in `class_session_topics`); `attendance` is marked in the same call and with the same rules as `PUT /attendance/sessions/{id}`. It also drops the saved flow progress (below). `GET /class-sessions` accepts `window=coming\|past` (past: ended and not Live, newest first, including a class never logged) |
| GET / PUT | `/class-sessions/{id}/flow` | The teaching trainer only (another trainer 404, a Branch Manager 403) | Today's guided class flow, saved on the server (db 112). GET returns the class as Today shows it (below). PUT `{step?: open\|join\|attendance\|log, draft?: {outcome?, actual_start?, actual_end?, break_minutes?, unfulfilled_note?, notes?, topic_ids?}}` keeps where the trainer is and the half-written class log (draft keys merge; the step is held to what the class's state allows: a class not started stays at `open`, a started one is at least at `join`); 422 once the class is Delivered or Cancelled |
| POST | `/class-sessions/{id}/meet/request-link` | The teaching trainer | "No Meet link": records a `Link requested` Meet event and tells the branch's Branch Managers (action required, link to Meet Operations). Asking again while the link is still missing sends nothing more. 422 for a classroom class, a class that already has a link or one that is finished |
| POST | `/class-sessions/{id}/confirm`, `/approval`, `/replacement-waiver` | confirm, waiver: BM, SA; approval: BM, SA (never the proposer) | `confirm`: Planned → Confirmed (room; online also a Meet link and a named backup host). `approval {decision, note?}`: a replacement, remedial or extra class; until approved students don't see it and it cannot start. `replacement-waiver {reason}`: a cancelled class that owes no replacement |
| PUT | `/class-sessions/{id}/notes` | Teaching trainer, BM, Super Admin | `{notes}`; only while the class is Live or Delivered; audited (`SESSION_NOTES_SAVED`). Today's flow saves notes with the class log instead |
| POST | `/class-sessions/{id}/reschedule-requests`; GET `/reschedule-requests`; POST `/reschedule-requests/{id}/approve`, `/reject` | Trainer (ask); BM (decide); Founder (only when the requester is a Branch Manager, UX phase U16) | One open request per session; approve applies the proposed time. Each decision notifies the trainer (link `/trainer/requests`) with the note |
| GET | `/me/requests` | Staff | What the signed-in person asked for: `{items, counts: {waiting, decided}}`, newest first (at most 100). Each item: `kind` (`reschedule` / `correction` / `recovery`; a recovery the trainer raised for a student, with the Branch Manager's decision and a notification linking to `/trainer/requests`), `id`, `status` (`Pending` / `Approved` / `Rejected`; an open reschedule is `Pending`), `title`, `summary`, `reason`, `requested_at`, `decided_by`, `decided_at`, `decision_note`, `decides` (while it waits: `Branch Manager`, or `Founder or Super Admin` when the person asking is a Branch Manager) and the `session`. Attendance corrections come from `POST /attendance/corrections`; their decision notifies a trainer with link `/trainer/requests` (a student still gets `/progress?tab=attendance`) |
| PUT / POST | `/class-sessions/{id}/meet`, `/meet/fail`, `/meet/reset` | BM, Super Admin | Records the Meet association in `meet_events`; the LMS never calls Google. `meet` also takes `meet_space_id`, `calendar_event_id`, `calendar_series_id`, `conference_record_id`; a link used by another batch's open class is refused |
| GET | `/me/enrolments`, `/me/enrolments/{id}`, `/me/enrolments/{id}/tracks/{track_id}` | Student | Own courses with delivery progress and combo tracks |
| GET | `/me/schedule` | Student | The learner's classes, optional `course_id`, `from`, `to`. Default: everything still to come, soonest first, cancelled and moved classes included (a class running past its end counts as coming). `?past=1`: classes that have ended, newest first, each with `attendance` (the learner's status or null) and `recording` (`{recording_id, status, playable}` or null) |
| GET | `/me/work` | Student | **Tasks & Tests** (UX U9): assignments and tests merged as `{counts: {todo, waiting, done, overdue}, todo: [...], waiting: [...], done: [...]}`. An item has `kind` (assignment / test), `id`, `title`, `type`, `is_required`, `batch`, `module`, `topic`, `state` with its dictionary `state_domain` (work / test / slot), `action` (Submit, Resubmit, Start test, Resume test, Try again, Book a slot, View), `due_at`, `opens_at`, `overdue`, `late`, `marks` / `max_marks` (only once visible), `duration_minutes`, `attempts_remaining`, `in_progress`. **To do**: open work, overdue first, then the nearest date (a resubmission request, a test that can be taken, an interview to book or attend). **Waiting for review**: handed in and not reviewed, or marked but not yet published (a formal result waits for the Branch Manager). **Done**: reviewed or marked work, and work whose window closed untouched (`Missed`). Tests not yet released are left out. The nav badge `tasks` equals `counts.todo` |
| GET | `/modules/{id}`, `/topics/{id}` | Student (own enrolments) / staff | Module and topic pages with their classes, resources and recordings |

Job: `flask --app app jobs run allocation-escalation`: an enrolment still waiting for a seat 24 hours before its
admission's `planned_start_date` (IST), or first noticed inside that window, is raised once to the Founder / CEO, Super Admin
and the service branch's Branch Managers (Module 15 §6).

Working days (`services/working_days.py`): a day counts when its ISO weekday is in `working_weekdays` (all seven by
default; Module 15 §9 assumes no weekend is closed) and no approved company holiday or closure at the branch covers it.

**Rules:**
- There are no curriculum versions, drafts or approvals (dropped in db 121): the course owns its outline. Modules and topics
  are edited by a Super Admin or Founder, apply at once, are audited and notify the affected Branch Managers (see `/courses/{id}/outline` above).
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
| POST | `/content-items` | Trainer, BM, Super Admin, Founder / CEO | JSON (links) or multipart with `file`. Placement from `topic_id` / `module_id` / `course_id`; branch from the batch or the author's batches (`branch_id` needed for Super Admin). Creates v1 Draft |
| GET | `/content-items/options` | Staff | Batches the caller may author for, each with `outlines: [{component_id, track_name, modules: [{module_id, title, topics}]}]` (the course's own outline first, then each combo track's; this replaces `versions`) |
| GET / PATCH | `/content-items/{id}` | Staff / author, BM, Super Admin | Detail with versions and review history; edit metadata, placement, download policy (author only while Draft / Changes Requested; reviewer audited) |
| POST | `/content-items/{id}/versions` | Author, BM, Super Admin, Founder / CEO | New file (multipart) or `url`; v2, v3 … earlier versions kept |
| POST | `/content-items/{id}/submit` | Author, BM, Super Admin, Founder / CEO | Draft / Changes Requested → Submitted; Branch Managers notified |
| POST | `/content-items/{id}/review` | BM (branch), Super Admin, Founder / CEO | `decision` start / approve / request_changes / reject (+ `comment`, `release`); never a Branch Manager's own upload (the Super Admin and Founder may approve their own) |
| POST | `/content-items/{id}/release`, `/retire` | BM (branch), Super Admin, Founder / CEO | Approved → Released (previous released version retired, students notified); retire needs a reason |
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
- Audience = same branch and course, the item's batch (if any) is the enrolment's active batch, and an item placed in a combo track's
  module only reaches enrolments that hold that track
  (`services/content.item_matches_enrolment`). Withdrawn and gate-blocked enrolments grant nothing.
- Access window (`services/access.py`): one calendar year from the enrolment's Joining Date through the end of the
  anniversary day in IST (29 Feb → 1 Mar), one extra year to the second anniversary on request (Recording, Material or
  Both), pending before joining. Settings `access_default_years` / `access_max_years`; the older
  `recording_access_days` is superseded by Module 17 §8 and unused.
- Uploads: allow-list, 50 MB / 250 MB (datasets, archives) from `app_settings`, magic-number check, notebook JSON check,
  safe ZIP inspection (paths, nested archives, executables, expansion ratio). Stored in the S3 bucket of the
  environment (`STORAGE_BACKEND=s3`) or under `UPLOAD_DIR` (`local`); served only through the API; no malware
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
| GET | `/assessments/curriculum?batch_id=` | Staff | Modules and topics of the course's outline (for linking): `[{module_id, title, component_id, track_name, topics: [{topic_id, title}]}]` (`version_label` is gone; `component_id` / `track_name` say which combo track a module belongs to) |
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
| GET | `/me/attendance` | Student | Per own enrolment: attendance measure + a row per Live / Delivered class since joining. A row also carries the student's requests (UX U10): `recovery` (`status`, `method`, `decision_note`, `target_date`, `decided_at`, `decides`) when a recovery was asked, and `correction` (`status` Pending / Approved / Rejected, `requested_status`, `reason`, `decision_note`, `decided_at`, `decides`), the latest "report a mistake" for that class. `decides` names who decides (the Branch Manager). `can_request_recovery` is true only for an Absent entry with no live recovery |
| GET | `/attendance/enrolments/{id}` | Scoped | Same block for one enrolment |
| GET / POST | `/attendance/recoveries` | Scoped / Student, Trainer, BM, SA | Raise `{attendance_id, method, reason}` for an Absent entry; one live recovery per absence |
| POST | `/attendance/recoveries/{id}/decision` | BM, SA | `{decision: Approved\|Rejected, decision_note?, target_date?}` |
| POST | `/attendance/recoveries/{id}/completion` | Trainer of the batch, BM, SA | `{evidence_note}` verifies an approved recovery (Completed) |
| GET / POST | `/attendance/corrections` | Scoped / Student, Trainer, BM, SA | `{session_id, enrolment_id, requested_status, reason}`: a dispute, or a change after the lock |
| POST | `/attendance/corrections/{id}/decision` | BM, SA (fresh auth); Founder only for a correction a Branch Manager requested (U16) | Approve applies the change; the decider must not be the requester or the marker |
| GET | `/me/progress`, `/progress/enrolments/{id}` | Student / Scoped | The four measures (`delivery`, `attendance`, `required_learning`, `engagement`), never combined |
| GET | `/me/progress/next-steps` | Student | **What to do next** (UX U10): up to 6 steps `{kind, course, params}`, most urgent first. Kinds, in order: `work_overdue` (n), `certificate_fee` (balance), `recovery` (n, session), `attendance_low` (percent, threshold), `access_ended` / `access_ending` (what = recordings / materials / both, until, can_request), `work_todo` (n), `certificate_ready`, `topics_left` (n), `inactive` (days). No sentence and no link: the screen words each kind (EN / తెలుగు) and knows where it leads. `[]` means nothing needs the student |
| GET | `/progress/students` | Staff (scoped) | Table with filters `branch_id`, `course_id`, `batch_id`, `status`, `alert`, `q` |
| GET | `/progress/summary` | BM, SA, Founder | Per-batch averages of each measure, enrolments and certificates by status |
| GET | `/completion-reviews` | Staff (scoped) | Running / completed enrolments with evidence, latest review, certificate status |
| POST | `/completion-reviews` | Trainer, BM, SA | `{enrolment_id}` opens a review (201, or 200 with the open one) |
| POST | `/completion-reviews/{id}/recommendation` | Trainer of the batch, BM, SA | `{recommendation, comment?}` |
| POST | `/completion-reviews/{id}/decision` | BM, SA (fresh auth) | `{decision: Complete\|Not Yet\|Needs Recovery, reason?}`; Complete needs a Complete recommendation by a trainer of a batch the enrolment was allocated to (Module 22 §2) and → enrolment Completed + Course Completion Certificate eligibility. An Internship Certificate entry stays Not Yet Eligible: it needs internship evidence |
| GET | `/certificates`, `/certificates/{id}`, `/me/certificates` | BM, SA, Founder (branch scope) / Student (own) | Register entries (every version) with `actions` the caller may take; detail has `history`. `/me/certificates` also returns `cards` (UX U10): one per course (and per live register entry), `{key, enrolment, course, certificate_type, certificate (id, number, version, status, issue_date, holder_name) or null, steps: [{key: completed / review / issued, state: done / current / todo}], blocker: {code, params} or null, fee: {state, cleared, balance} or null, can_download, verify_path}`. Blocker codes: `not_completed`, `in_review`, `ready_to_issue`, `fee_outstanding` (balance), `fee_unknown`, `revoked` (reason), `internship_evidence`, `config_pending` |
| GET | `/me/certificates/{id}/pdf` | Student (owner only) | The certificate as a PDF (`application/pdf`, attachment named `<number>.pdf`, or `<number>-v2.pdf` for a reissue), drawn from that version's own data with a QR code to `PUBLIC_BASE_URL/verify/<number>` (no QR when `PUBLIC_BASE_URL` is unset). 404 for another student's certificate, 422 when it is not issued, was revoked, or was replaced by a corrected version. Audited as `CERTIFICATE_DOWNLOADED` |
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
| POST | `/support-requests` | Student; staff for a student (`student_id`) | `{category, details, subject?, priority?, enrolment_id?}` as JSON, or as a multipart form with the same fields plus up to 3 `files` (UX phase 11). Routed to a named owner; staff raising for a student = "Staff flag" |
| GET | `/support-requests` (student) | | The student's list puts **Waiting on Student** first, then newest. Every thread message carries `from_student` (the screen words it "You" for the student's own lines) and `attachments[]` (`attachment_id`, `filename`, `mime_type`, `size_bytes`) |
| GET | `/support-requests/{id}` | Scoped | With the thread; internal remarks are left out for a student |
| GET | `/support-requests/attachments/{id}/download` | Scoped | A file of a message, for anyone who may see the request (404 outside their scope, and for a student, on an internal remark); audited |
| POST | `/support-requests/{id}/messages` | Scoped | `{body, internal?}` (JSON or multipart with up to 3 `files`); a staff reply moves Open to In Progress, a student reply moves Waiting on Student to In Progress |
| POST | `/support-requests/{id}/status` | Owner / branch BM / admin | `In Progress`, `Waiting on Student`, `Resolved` (note required), `Closed` |
| POST | `/support-requests/{id}/close`, `/reopen` | Student closes a Resolved request; student or manager reopens with a reason | Reopen gives a fresh SLA clock |
| POST | `/support-requests/{id}/escalate` | Staff | A trainer-owned request goes to the Branch Manager (the owner changes); any other request is marked escalated to the Branch Manager |
| POST | `/support-requests/{id}/assign` | BM / admin | `{owner_user_id}`, must work at the request's branch |
| GET | `/trainer/students` | Trainer | Students with active seats in their batches (one row per seat): `student`, `batch`, `enrolment`, the open-request flag (`flag`, `open_requests`), `attendance_pct`, `attendance_state`, `delivery_pct`, `required_pct`, `unmarked`, `last_activity_at` and `reasons[]` (why the student needs attention, see `/trainer/at-risk`). `?q=` matches name or Student ID, `?batch_id=` narrows to one batch (another trainer's batch is 404). (UX phase 13) |
| GET | `/trainer/students/{id}` | Trainer | One student inside the trainer's batches (404 otherwise): per seat the figures and `reasons`, recent `attendance` (null status = not marked), `assignments` (state Not submitted / Submitted / Under Review / Reviewed / Resubmission Requested, marks, `to_grade`, `submission_id`) and `results`; plus `flags` (support requests the trainer owns or raised about the student) |
| GET | `/trainer/batches` | Trainer | The trainer's batches: `batch`, `students`, `at_risk`, `next_class`, `attendance_pct`, `delivery_pct` |
| GET | `/trainer/batches/{id}` | Trainer | One batch (404 when not the trainer's): `sessions` (`coming`, `recent`), `roster` (with figures, `reasons`, open requests), `assignments` (with submission counts), `content`, `progress` |
| GET | `/trainer/to-grade` | Trainer | The one grading inbox: `items` (hand-ins awaiting review of assignments the trainer reviews, and test attempts with written or coding answers left; `kind` submission / attempt, `id`, `student`, `batch`, `submitted_at`, `review_due`, `overdue`, `started`, `max_marks`, `to_mark`), overdue first then oldest; `counts` (`total`, `submissions`, `attempts`, `overdue`) and `batches` to filter by. `?batch_id=`. The count equals the `to_grade` nav badge |
| GET | `/trainer/at-risk` | Trainer | Students at risk per assigned batch: `batches[]` of `{batch, students, at_risk, rows: [{student, enrolment_id, reasons}]}` and `totals`. A reason is `{kind, label, detail, to, action}`: **attendance** (below the alert level), **work** (required tasks past due and not handed in, or handed in late in the last 30 days), **unmarked** (delivered classes with no mark) and **review_overdue** (the student's work is past its review target; `to` is the grading screen). `to` is a frontend path |
| GET | `/notifications` | Signed in | Own only. `view` = my (all), needs_action, new, done (the inbox views), or the older action, unread, completed, system; `category`, `q`. Each item has one `status` (**New** / **Needs action** / **Done**; **Failed** for a channel that could not deliver), a `link` to its screen and a `delivery_label`. Delivery failures are listed only for the Super Admin (the `system` view); everyone else sees only delivered messages. Staff see a branch notice only while they still hold its role (any role, for notices to named people) at that branch or company-wide; the same rule applies to counts, read and actions. Students keep their own |
| GET | `/notifications/overview` | Signed in | `{unread, action_required, needs_action, new, categories}`: the bell shows `new + needs_action` |
| POST | `/notifications/{id}/read`, `/acknowledge`, `/action-done`, `/notifications/read-all` | Recipient | Separate states; acknowledging also reads, does not complete the action |
| GET / PUT | `/notifications/preferences` | Signed in | Group × channel matrix; In-app always on. Each channel has `live`: WhatsApp is live only when `whatsapp_enabled` is on, `CRM_BASE_URL` is set and a template is approved; Email when its integration is Configured and Verified. The screen offers only live channels |
| GET | `/me/career` | Student | Profile + completeness, CVs, eligible opportunities, applications, outcomes, next action, plus (UX phase 11) `steps[]` (the checklist in order: `opt_in`, `profile`, `cv` with `state` none / waiting / changes / reviewed, `share`; each `done`) and `apply_needs[]` (the step keys that block applying: opt-in, a reviewed CV, consent; the profile step never blocks) |
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
| GET / PATCH | `/me/profile` | Signed in (PATCH: student) | Identity with masked mobile, devices, language. Staff get their one scope (`scopes`), `allowed_branches`, devices, last sign-in; the session's `role` and `branch` come from `/auth/me` (§4.22) |
| POST | `/me/email/request-code` | Student | `{email}`. Sends a 6-digit code to the student's WhatsApp number (template 1, the generic verification-code message). Answers `{sent, channel, expires_in_minutes, reason}`; `sent: false` says why nothing went out (WhatsApp switched off, no number on file). 422 for an address already in use or the same as now; 429 after 5 codes in an hour |
| POST | `/me/email/confirm` | Student | `{code}`. The newest unused code of the last 10 minutes; only its hash is stored (it covers the address too), single use, burned after 5 wrong tries. On success `students.email` and `users.email` become the new address (audited) and the profile is returned |
| POST | `/me/devices/sign-out-others` | Signed in | Revokes every other session |
| GET | `/me/finance/receipts/{admission_id}/{receipt_number}/pdf` | Student (owner only) | A receipt PDF drawn by the LMS from the CRM's verified receipt row and fee position (`services/pdf.render_receipt`): receipt number and date, amount, student, course, invoice, fee / verified paid / balance. Another student's admission or an unknown number is 404; audited |
| GET | `/branches/{id}/payment-instructions` | BM (own branches, read-only), Super Admin, Founder | `{branch, payment_instructions}`; 404 outside the user's branches (UX phase 14: the Branch home reads it to edit it) |
| PUT | `/branches/{id}/payment-instructions` | Super Admin, Founder (the Branch Manager gets 403: read-only) | `{payment_instructions: text or null}`: how and where students pay at this branch, shown on the Next payment card. The LMS's own setting (`branches.payment_instructions`), not the CRM's |
| GET | `/me/finance` | Student | Adds `next_payment`: `{state: unknown}` (the CRM has sent nothing), `{state: paid}`, or `{state: due, due_date, amount, overdue_amount, is_overdue, courses[], invoice_number, how_to_pay: {branch, instructions}}`: the earliest next instalment across the schedules, overdue when the CRM says so or the date has passed. Read-only CRM data: `admissions[]` (one per course: its own fee, verified paid, balance, receipts) and `schedules[]` (each instalment schedule **once**: per invoice when `installments_scope = invoice`, listing the courses it covers, with `next_due_*` and `overdue_amount`) |
| GET | `/finance-summaries` | BM (service or collecting branch), Super Admin, Founder | Filters `branch_id`, `student_id`, `has_balance`. `meta.totals`: `balance` summed per admission; `overdue_amount` and `next_due_amount` summed once per schedule |
| GET | `/finance-summaries/{admission_id}` | Same | One admission plus its `schedule` |
| GET | `/ask-nipuna/status` | Signed in | `AI Available` / `Configuration Pending` / `Quota Limited` / `Disabled`, usage today, actions, scope. Disabled while `ai_enabled` is false or an AI control covers the caller's audience and branch |
| GET / POST | `/ai-controls`, `/ai-controls/{id}/restore` | Super Admin, Founder (fresh auth to change) | Switch AI off: `{audience: Student\|Staff\|All, branch_id?, reason, remediation?}` (`All` is company-wide; the Super Admin and the Founder can both switch it off and restore it, U17). Restore with `{restoration_note}` (the checks that passed). `GET /ai-controls/status` is the ON / OFF picture (see §4.21) |
| POST / GET | `/ask-nipuna/queries` | Signed in | Ask (refusals are answered with `status: Refused` and do not use the allowance); own history, newest first, or `order=asc` to list the page oldest first (a chat reads that way). Each item has `answered`: false when the answer says it had nothing to go on or the question was refused, so the screen offers "Raise a support request with this question" |
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
| POST | `/admin/users` | Super Admin | `{full_name, email, phone?, scopes: [{role_code, branch_id?, expires_at?}]}` (one role; several scopes only for a Branch Manager, one per branch) → 201 with `temporary_password` (once); `must_change_password` set |
| GET, PATCH | `/admin/users/{id}` | Super Admin (PATCH) | PATCH `full_name`, `email`, `phone` |
| POST | `/admin/users/{id}/scopes` | Super Admin | Another branch for a Branch Manager only (one role per account; any other role is refused with 422); `expires_at` (temporary access) at most 7 days ahead |
| GET | `/admin/users/handouts` | Super Admin, Founder | Accounts created by the role split: role, branches, link status, handed-out state (never the raw link) |
| POST | `/admin/users/handouts/{id}/link` | Super Admin, Founder, fresh auth | New one-time activation link (first issue or re-issue; replaces the old one); `invite_path` is returned once |
| POST | `/admin/users/handouts/{id}/handed-out` | Super Admin, Founder | Marks the account handed out |
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
| GET | `/trainer/today` | Trainer | `today` (the trainer's classes for today's IST date, each as the **flow item** below, plus `next_up`: the class on now, else the first still to come, else the first without a log), `tomorrow` (`{date, sessions}` of compact classes, only when nothing is left today), `todo` (`assignments`, `attempts`, `class_logs: {count, sessions}` (the oldest five), `attendance: {classes, corrections, recoveries, total}`) and the older `tiles` (`sessions` next 7 days, `reviews`, `support_flags`; the screen no longer shows them); assigned batches only |
| GET | `/trainer/reports` | Trainer | `batches` (delivery and attendance averages per assigned batch), `review_turnaround`, `engagement`. The screen shows these as a short summary under Students at risk (`/trainer/at-risk`) |
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
  assignments where the trainer is reviewer; support flags reuse `support.assigned_students`. Recording mapping shows
  Pending Verification until a recording is registered for the session.
- **The class flow** (`services/class_flow.py`, db 112). A flow item is the class (times, mode, room, batch, planned topic,
  `state`), `meet` (`status`, `label`, `link`, `organizer_email`, `link_requested_at`), `attendance` (counts, `locked`,
  `can_mark`), `recording`, and `flow`: `steps` (`open, join, attendance, log`; just `log` for a class that ended more
  than 6 hours ago and was never started; empty once logged), `step` (where the trainer is, saved on the server), `draft`
  (the class log typed so far), `can_start` / `start_opens_at` (an hour before the class), `awaiting_approval` and
  `topic_options` (the topics of the outline, by module). `log` holds the saved class log of a Delivered class
  (outcome, actual times, break, minutes taught against planned, what was not delivered, topics covered). The steps drive
  `POST .../start`, the Meet link request, `PUT /attendance/sessions/{id}` and finally `POST .../deliver`, which saves
  the whole log. A class "without a log" is one of the trainer's that ended within `class_log_lookback_days` (14) and is
  still Scheduled, Rescheduled or Live, not waiting for approval.
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
| GET | `/founder/summary` | Founder, Super Admin | CRM figures (from `BranchFinanceSnapshot`, else Not Configured) and `crm_connected` (true once the CRM has sent finance figures for a branch; the screen hides the CRM tiles until then), active enrolments per branch, batches at risk, certificates awaiting approval, decisions (AI ceiling, post-2nd-anniversary access requests; the screen now reads these from `/founder/inbox`) |

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
| GET | `/me/nav-counts` | Signed in | The workspace comes from the session's role. The old `?workspace=` and `?branch_id=` are accepted and ignored (the Branch Manager's branch is the session's). Returns `{badgeKey: n}`, cheap counts only, polled every minute with the bell. The Founder gets the Super Admin's keys (`home`, `users`, `issues`, `calendar`, `crm_sync`, `student_accounts`, `setup`) plus the inbox keys (`inbox`, `certificates`, `access`; the `curriculum` key is gone). The Super Admin gets the admin keys plus `approvals` (the same inbox count); a Branch Manager's keys include `content_review`, `questions`, `extensions` and `certificate_requests` |
| GET | `/me/getting-started` | Signed in | Same rule. `{workspace, steps: [{key, label, done, to}], complete}`. The Founder gets the Super Admin's two steps (Add a staff user, Review setup and health) with `/founder/...` links. Whether the card was dismissed is kept in the browser, not here |
| GET | `/search` | Signed in | `?q=` (two characters or more). `[{kind: student\|batch\|certificate, id, title, subtitle}]`, at most 5 per kind, within the caller's scope: Branch Manager their branches, trainer the batches they teach and the students in them, Super Admin / Founder everything, a student nothing. Pages are not searched here (the client lists the pages of the user's workspaces). A record outside scope is simply absent |

**Badge keys** (the `badgeKey` of a navigation item in `frontend/src/auth/access.ts`):
- `student`: `tasks` (open assignments and tests), `support` (requests waiting on the student).
- `trainer`: `to_grade` (submissions awaiting review plus test attempts awaiting grading, for the trainer's own reviews), `support` (open requests they own), `attendance` (classes with students still unmarked plus corrections waiting plus recoveries to verify, in the trainer's batches), `class_logs` (the trainer's classes that ended without a class log).
- `branch`: `waiting` (enrolments in Allocation Pending), `requests` (open reschedule requests, escalations, extension requests), `content_review`, `marks` (results awaiting publication), `completion` (open completion reviews), `certificates` (Eligibility Review or Awaiting Approval), `issues` (open exceptions), `recording_issues`, `support` (open requests past, or within 4 hours of, `sla_due_at`), `attendance` (recoveries requested plus corrections pending), `my_work` (the total of the My work rows), `schedule` (reschedule requests plus extra, remedial or replacement classes awaiting approval), `class_day` (today's classes at risk).
- `admin`: `crm_sync` (failed events), `issues` (exceptions with no named owner), `users` (locked accounts).
- `founder` (U16, the Founder's inbox): `inbox` (the whole inbox), `certificates` (change requests plus fee exceptions the person can decide), `access` (beyond-limit requests that carry the Branch Manager's recommendation).

**Getting started steps** (done is read from the records, so the card ticks itself): student: activate (always), batch (an active seat), class (attended one), task (submitted one). Trainer: open a class (one of theirs is Live or Delivered), mark attendance, grade a submission. Branch Manager: create a batch, allocate students, create classes (anything at the branches in view). Admin: add a staff user (a `USER_CREATED` audit entry by the caller), review setup (an integration is no longer Not Configured).

### 4.13 WhatsApp through the CRM (UX phase 6, `107`)

No LMS endpoint: messages are queued in `whatsapp_outbox` by the service that made the change and handed to the CRM by the `whatsapp-send` job. The CRM endpoint the LMS calls is `POST {CRM_BASE_URL}/lms/whatsapp` (contract in `LMS_WHATSAPP_REPLY.md`, summarised in [CRM_INTEGRATION.md §3.2](CRM_INTEGRATION.md)).

**Triggers** (`services/whatsapp_messages.py`; the template is in `services/whatsapp_templates.py`, drafts in [whatsapp-templates/](whatsapp-templates/README.md)):
| Template | Queued by | Dedupe key |
|---|---|---|
| `nipuna_lms_class_reminder_u_v1` | job `class-reminders` (confirmed, approved classes that start in 15 minutes to 2 hours); preference group *Learning reminders* (off until the person turns it on) | `class-reminder:<session>:<student>:<start>` |
| `nipuna_lms_class_cancelled_u_v1` | `class_sessions.cancel` | `class-cancelled:<session>:<student>` |
| `nipuna_lms_class_rescheduled_u_v1` | `class_sessions` reschedule (only a change of time) | `class-rescheduled:<session>:<student>:<new start>` |
| `nipuna_lms_result_published_u_v1` | `results.publish` (no marks in the message) | `result-published:<result>:<published at>` |
| `nipuna_lms_certificate_issued_u_v1` | `certificates.issue` and a corrected reissue | `certificate-issued:<certificate>:<version>` |
| `nipuna_lms_batch_change_agreement_u_v1` | `batch_changes.decide_change` when approved (reply-by: 7 days until phase U8 stores one) | `batch-change:<change>:<student>` |

Templates 1-3 (reset code, student activation link, staff invite) are queued by sign-in in phase U7.

**Rules:**
- `enqueue` always records the message. It is **Queued** only when `whatsapp_enabled` is on, the template is in `whatsapp_approved_templates`, every value is present, the person has a number and has not switched that kind off, and it is not stale; otherwise it is **Skipped** with the reason (`status_note`). One row per dedupe key.
- `send_pending` (job `whatsapp-send`) posts Queued rows after the commit with `X-Service-Key`, commits around each call, and records Sent / Skipped / Failed from the CRM's answer: 401/403 stops the run (the row stays Queued), 429/5xx back off 60 s doubling to 30 min and fail after 5 tries, a timeout or a 200 without confirmation is **Failed "check before resending"** and never auto-resent, a post with no recorded answer after 15 minutes is Failed. A message older than `whatsapp_max_age_hours` (48), or for a class that has begun, is never sent.
- The code ships **switched off** (`whatsapp_enabled` false, no approved template, `CRM_BASE_URL` unset). `flask whatsapp status` and `flask whatsapp list` show why and what is queued.



### 4.14 Sign-in and accounts (UX phase 7, `108`)

| Endpoint | Notes |
|---|---|
| `POST /auth/reset-code` `{login}` | Public. Always `200 {"message": "If the account exists, we've sent a code."}`. Sends template 1 by WhatsApp to the number on file for an active login with a password. At most 5 codes per person per hour. No email fallback yet: the LMS has no email sender |
| `POST /auth/reset` `{login, code, new_password}` | Public. `204`; `400` "That code is wrong or has expired" (5 wrong tries burn the code). Ends every session of the person and clears a lockout |
| `GET /auth/activation/{token}` | Now `{kind: student or staff, status: valid / expired / used / revoked, student_code (masked), email (masked), full_name, expires_at, password_min_length}` |
| `POST /auth/activate` `{token, password}` | Student or staff token. Signs the person in: the answer is a login response plus `activated` and `student_code` (students). Not counted as learning activity |
| `POST /students/{id}/activation` | Also queues template 2; the answer adds `whatsapp: {state, note}`; `token` and `activation_path` remain as the copy fallback |
| `POST /admin/users` | Also issues an invite and queues template 3. The answer adds `invite_path`, `invite_expires_at`, `whatsapp`; `temporary_password` is returned only when no WhatsApp message will carry the link |
| `POST /admin/users/{id}/invite` | Super Admin, fresh auth. New invite link (replaces the old one) for a person who has not chosen a password |
| `POST /admin/users/{id}/unlock` `{reason}` | Super Admin, fresh auth. Clears a lockout; audited as `USER_UNLOCKED` |

### 4.15 Student Home and My Learning (UX phase 8, `109`)

| Endpoint | Notes |
|---|---|
| `GET /me/home` | Adds `up_next` (`live_class`, `work_due`, `continue_topic`, `next_class` or `nothing`), `batch_changes: {items}` (waiting for Agree / Decline, with `reply_by`), `needs_batch` (the preferred slot is offered only then) and `course_progress.topics`. `continue_learning` points at the first topic not Done (`basis: "Next topic"`) |
| `GET /me/enrolments`, `GET /me/enrolments/{id}` | Add `topics {done, total, percent}` and `continue_topic`; modules add `topics_done` and `percent`; tracks add `topics` |
| `GET /modules/{id}` | Topics carry the learner's `progress` (null for staff) |
| `GET /me/topics/{id}` | Topic hub (students only): topic, module, track, `progress`, `sessions` (with attendance), `recordings`, `materials`, `assignments`, `tests`, `next_topic` |

### 4.16 WhatsApp status events (CRM round 6, `110`)

`WhatsappStatusUpdated` is a CRM event on the existing intake (`POST /integrations/crm/events`), data `{dedupe_key, status (Sent / Delivered / Read / Failed / Skipped), crm_outbox_id, provider_message_id, reason, occurred_at}`. It is applied when its `source_version` is higher than the last one for that dedupe key. `Failed` and `Skipped` also finish the LMS row with the reason; the other states set `delivery_status`. An unknown key or an older version is answered as `Ignored — stale` (not an error). The `Queued` answer to `POST /lms/whatsapp` is the normal first answer and stores `crm_outbox_id`.

### 4.17 Student Career, Ask Nipuna, Support and My Account (UX phase 11, `111`)

New and changed endpoints are in the §4.8 tables above (support attachments, career `steps` and `apply_needs`, `answered` and `order=asc` on Ask Nipuna, the email code pair, `next_payment`, the receipt PDF and the branch payment instructions). Rules:
- **Attachments**: images (png, jpg), PDF, text, Word (doc, docx); 5 MB each, at most 3 per message; the first bytes must match the type. Files are kept under the key `support/<request id>/…` (S3 bucket, or `UPLOAD_DIR` with `STORAGE_BACKEND=local`) and downloaded only through the API.
- **Email change** needs the code, which is **delivered by WhatsApp** (the LMS has no email sender), through the same outbox and switch as every other message. With WhatsApp off nothing is sent, the email is not changed and the answer says so.
- **Receipts**: the CRM's finance summary carries each verified receipt's number, date and amount only, so the PDF is a copy drawn by the LMS from those rows (no official receipt layout, no payment mode). Whether the CRM already issues receipt PDFs is still to be confirmed with the CRM.

### 4.18 Branch Manager: My work, Waiting for a batch, batch steps and Create classes (UX phase 14; no migration)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/branch/my-work` | BM, SA, Founder | `?branch_id=` (404 outside scope). `{as_of, scope, total, rows: [{key, what, where, count, oldest_at, to, search, action}]}`. A row exists only while something waits, in this fixed order: `waiting` (enrolments in Allocation Pending), `decisions` (open reschedule requests plus extra, remedial or replacement classes awaiting approval), `results` (Provisional or Moderated), `content` (Submitted or Under Review), `attendance` (recoveries requested plus corrections pending), `support` (open requests past, or within 4 hours of, `sla_due_at`; `oldest_at` is the earliest deadline), `class_day` (today's classes still to run or running that are online with no working link, have a delay noticed, or an open disruption). `what` and `action` are plain-English text, `to` the screen. The navigation badge `my_work` is `total` |
| GET | `/branch/waiting` | BM, SA, Founder | `?branch_id=&course_id=&q=&page=&per_page=`, longest wait first. Each row: `enrolment`, `student`, `course`, `branch`, `mode`, `waiting_days`, `preferred_batch_code` (the CRM counsellor's preference, may name no batch here), `allocation_due_on`, `overdue`, `matches` and `blocked`. `matches` are the open batches of the student's course at their service branch with a seat left, each with the allocation review's `result` (`Ready to allocate` or `Review needed`), its `warnings`, `preferred` (true for the batch whose code is the CRM's preference; shown as "Preferred by counsellor"), the batch (`state_label`, `seats_left`, timetable, trainers) and, for a combo enrolment, the `track` the seat is for (the whole programme batch is offered once, for the whole enrolment; each track without a seat is offered the batches that teach it). A batch the review blocks is left out of `matches` and listed in `blocked` with the reasons (for example "Already allocated to X; use transfer"). Allocating is the existing `POST /batches/{id}/allocations` |
| GET | `/batches/{id}/waiting` | BM, SA | The same rows limited to waiting students (at most 100) this batch could take, with `batch` and `seats_left`. 404 outside scope |
| GET | `/batches/{id}/progress` | Staff | `{state, steps: [{key, label, done}] (created, trainer, ready, confirmed, students, classes), current, next: {key, label} or null, note, problems, warnings, can_confirm, counts}`. `next.key` is `assign_trainer`, `finish_setup`, `confirm`, `add_students` or `create_classes`. `problems` are the points of the readiness checklist (1 to 6) that still fail or are pending, each with `fix` (`trainer` or `details`); `warnings` are the advisory ones. `ready` is done when there are no problems or the batch is already confirmed; `confirmed` when `confirmed_at` is set or the batch is past Proposed |
| POST | `/batches/{id}/confirm` | BM, SA | `{note?, override_reason?}`. A Draft batch is proposed (no notice) and confirmed in one step; a Proposed batch is just confirmed. The recorded readiness is brought up to date first (it was worked out when the batch was created). Failing or missing checklist points answer 422 with `details.blocking`; advisory warnings answer 422 with `details.warnings` until `override_reason` is given (kept in the audit log). A refusal leaves the batch as it was |
| POST | `/batches/{id}/generate-sessions` | BM, SA | `{preview?, from_date?, until?, override_reason?}`. One class per teaching day of the batch timetable (`schedule_days`, `start_time`, `end_time`), led by the lead trainer in the batch room, from `from_date` (default the planned start, never before today) to `until` (default the planned end; at most 52 weeks), at most 60 per call (`truncated`). Skipped with a reason: days under an approved company holiday or closure of the branch (`Holiday: <title>` / `Closed: <title>`), days the batch already has a class, and times already past. Each class takes the next curriculum topic no class of the batch covers yet (optional topics are not scheduled); without a curriculum it is titled "<course>: class N". `preview: true` returns `{batch, trainer, room, mode, from, until, classes: [{starts_at, ends_at, title, topic_id, blocked, warnings}], skipped, truncated, blocking, warnings, created: []}` and changes nothing. Creating is all or nothing, answers 201 with the created classes in `created`, and tells the students and the trainer once. A trainer who already teaches at one of the times blocks it (422 `details.blocking`); a booked room or a student clash needs `override_reason` (422 `details.warnings`; only the Branch Manager of the branch or a Super Admin may give it). 422 when the batch has no timetable, no lead trainer, or is closed or on hold |

`GET /meet-operations` is the data behind **Class day**. The Meet integration status and `last_runs` it still returns are shown on the Super Admin's integration screen, not on Class day.

### 4.19 Branch Manager: Courses, Content & questions, Marks & results, Attendance, Completion, Issues, Recordings, Support, Extensions, Reports (UX phase 15, `113`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/content-items/review-summary` | BM, SA | `{awaiting, ready, changes, released, questions}`: counts for the tabs of Content & questions (`questions` = drafts waiting for approval) |
| POST | `/content-items/{id}/claim` | BM, SA, Founder | Opening a review takes it: a Submitted version becomes Under Review under this reviewer (never their own upload). Idempotent. `{claimed_by, claimed_by_me, can_decide, reason}`. `GET /content-items` rows now carry `claimed_by` while Under Review |
| GET | `/results/publish-preview` | BM, SA | `?assignment_id=|test_id=&batch_id=`: `{to_publish, unreviewed, moderated, already_published, awaiting_grading}` for the publish confirm (`unreviewed` = results still Provisional) |
| POST | `/results/publish` | BM, SA | Also takes `batch_id`, so a publish from one batch's review does not publish the same assessment in another batch |
| GET | `/assessment-reviews` | Staff | Unready tests also carry `gap_details: [{text, owner: "trainer"|"you", owner_label}]` (each gap with who must fix it) |
| GET | `/branch/attendance-summary` | BM, SA | `?branch_id=` -> `{students_at_risk, recoveries, corrections}` for the tab counts |
| GET | `/progress/students` | Staff | `?sort=risk` puts students below the attendance alert first (lowest attendance first) |
| GET | `/attendance/corrections` | Staff | Each row carries `can_decide` (not the requester, not the person who marked the entry, and an admin when the requester is a Branch Manager). `GET /reschedule-requests` rows carry it too; approving or rejecting your own reschedule request is 422 |
| GET | `/branch/completion` | BM, SA, Founder | The pipeline: `?stage=ready|completed|fee|issue|issued&q=&course_id=&branch_id=&page=&per_page=`. Stages: **ready** (an open completion review, or a running enrolment whose evidence is complete and has no review yet), **completed** (course complete, certificate waiting for the Branch Manager's approval), **fee** (a certificate not cleared by fee), **issue** (approved and fee cleared), **issued** (Issued or Revoked). `meta.counts` has every stage. Each row: `student`, `enrolment`, `batch`, `evidence: {checks: [{key, label, value, threshold, unit, ok, detail}], all_ok}` (attendance against the curriculum's minimum, required topics covered, open recoveries, the trainer's Complete recommendation), `review`, `certificate`, `fee`, `actions` (`decide`, `start_review`, or the certificate's own `approve`, `return`, `issue`, `request_correction`, `request_revocation`, `request_reinstatement`) and `can_request_fee_exception`. Deciding and the certificate steps use the existing endpoints (4.7) |
| GET | `/issues` | BM, SA, Founder | The Issues inbox, a paged read of the `exception_queue` view: `?type=students|classes|recordings|support|results|access|system&age=today|over_2|over_7|over_30&owner=me|none|<user id>&branch_id=&page=&per_page=`. A Branch Manager sees their branches, a Super Admin everything (including CRM sync and integrations), the Founder reads. Each item: the queue fields plus `id`, `type`, `type_label`, `go_fix: {to, search}` (the screen that holds the work, chosen by the session's role: a Branch Manager gets `/branch/*`; a Super Admin or Founder never does, they get `/admin/issues/{source}/{id}` or `/founder/issues/{source}/{id}`, a read-only detail with Assign, or `/{admin|founder}/students|crm-sync|setup` for account, CRM and setup problems) and `can_note`. `GET /issues/{source}/{id}` reads one open issue in the same shape (404 outside the person's branches). `meta` has the exact `total`, `pages` and `counts` per type. "Add note" is the existing `POST /exceptions/{source}/{id}/steps` |
| POST | `/recordings/{id}/problem` | BM, SA | `{reason: processing|partial|unavailable|on_hold, note}`: one action for what were Hold, Mark partial and Mark unavailable. `processing` returns the recording to Processing (students lose it until it is released again; no exception), the others raise the usual recording exception. A note is required except for `processing`. Recordings carry `problem: {reason, label, note}` (null when fine) |
| GET | `/recordings/classes` | BM, SA | `?date=<day, default today>&batch_id=`: the day's Delivered or Live classes at the user's branches with their recordings, for the class picker |
| GET | `/support-requests` | Staff | `?view=needs_action|waiting|done|all`. Needs action (Open, In Progress) is sorted by the nearest `sla_due_at`; staff rows carry `reply_mark`: `new_reply` (the student wrote last after staff had answered), `new_request` (only the student has written) or null |
| GET | `/support-requests/counts` | Staff | `{needs_action, waiting, done, all}` with the same scope and filters as the list |
| POST | `/access-extension-requests/{id}/recommendation` | BM | `{decision: approve|reject, note, expiry?}` on a request made after the second anniversary (422 for a routine request). It does not decide it: the request goes to the Founder (`with_founder`) and the Founder is told. May be revised until decided. A student never sees it |
| GET | `/access-extension-requests` | Student, BM, SA, Founder | Rows add `limit` (`within`|`beyond`), `current_end_date`, `new_end_date` (what approval grants: the second anniversary), `can_decide`, `can_recommend` and, for staff, `recommendation` and `with_founder`. U16's Founder inbox reads the requests with `with_founder = true` (`services.access_extensions.awaiting_founder()`) |
| GET | `/branch/reports` | BM, SA, Founder | `?period=this_month|last_month|last_90|custom&from=&to=&branch_id=`: `{period, figures: [{key, label, value, unit, hint, drill: {to, search} or null}], batches, trends}`. A Super Admin or Founder gets all branches (or one with `branch_id`) and `drill` links under `/admin` or `/founder` (null when that role has no screen for it; never `/branch/*`). A figure that cannot be worked out is `null`, never 0. `trends` is the last six months |
| GET | `/branch/reports/export` | BM, SA, Founder | The same period and branch plus `section=figures|batches|trends|certificates&format=csv`. CSV only (UTF-8 with a byte-order mark so Excel reads it; a cell that starts with `=`, `+`, `-` or `@` gets a leading apostrophe). `format=xlsx` is 400: no spreadsheet library is installed (`services/exports.py`) |

Navigation counts changed with the screens: `content_review` also counts questions waiting for approval, `completion` also counts certificates to approve or issue, `support` counts replies near or past their deadline plus new student replies plus access extensions the Branch Manager decides or recommends on, and `certificates`, `recording_issues` are gone (recordings are inside `issues`). The Founder's `access` counts requests carrying a recommendation. Notification links to the old screens now point at `/branch/content`, `/branch/results`, `/branch/completion`, `/branch/recordings`, `/branch/issues` and `/branch/support?tab=extensions`.

### 4.20 Founder: inbox, AI budget (UX phase 16, `114`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/founder/inbox` | Founder, SA, and a Branch Manager (certificate change requests of their branch only) | Everything waiting for the person, oldest first (the dateless AI budget last): `{as_of, total, counts: {kind: n}, items, crm_connected}` (`scheduled` is gone with the curriculum activations). `?group=certificates\|access\|other` narrows it to one page of the workspace (`other` = AI budget and Branch Managers' own requests). Each item: `key` (`<kind>-<id>`, used as `?item=` in the address), `kind`, `id`, `title` (plain words), `where` (branch), `since`, `action` (button label), `to` (the page that lists it), `from_branch_manager` and `detail`, the record as its own screen shows it. Kinds: `curriculum` (Under Review, or Approved with no activation day; not what the person submitted), `certificate` (a pending correction, revocation or reinstatement the person may decide: `detail` is a certificate request with `actions`), `fee_exception` (a pending release for an unpaid fee), `access_extension` (beyond the limit **with** a Branch Manager recommendation: `detail` is the staff request with `recommendation`), `ai_budget` (while no monthly budget is approved), `bm_reschedule` and `bm_correction` (a Branch Manager's own open reschedule request or pending attendance correction, which nobody at the branch can review). `scheduled` lists Approved versions waiting for their activation day. A certificate request or fee exception the person could decide but raised themselves is listed with `can_decide: false` (nobody decides their own request); every item carries `can_decide`, and `total`, `counts` and the nav badges include only what the person can decide. The Super Admin's own curriculum submissions are left out. The Super Admin's `/me/nav-counts` also has `approvals` (the same total) |
| PUT | `/founder/ai-budget` | Founder, SA (fresh auth) | `{amount_inr}` (whole rupees, 1 to 10,000,000). Stores `app_settings.ai_monthly_ceiling_inr`, audited (`AI_BUDGET_APPROVED`). Returns `{state: "Configured", amount_inr}` |

The decisions in the panel use the existing endpoints: `/certificate-requests/{id}/decision` and `/certificate-financial-exceptions/{id}/decision` (a note is required to reject, and for an exception always); `/access-extension-requests/{id}/decision` (`new_expiry` required to approve); `/reschedule-requests/{id}/approve|reject` and `/attendance/corrections/{id}/decision` for a Branch Manager's own request (the Founder is refused on anyone else's: 403).

### 4.21 Super Admin: Needs action, Setup & health, AI controls, CRM sync, Users, Student accounts, Calendar, Audit log, Issues (UX phase 17, `115`)

Everything here is Super Admin (the Founder reads where a GET is listed for both). Changes need fresh authentication, as before.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/admin/needs-action` | SA, Founder | The home: `{rows, total, setup}`. A row exists only while something waits: the newest three failed CRM updates (each with `retry: {crm_event_id}` when Retry can work) and one row for the rest, issues nobody owns, locked staff accounts, branch closures waiting for a decision, student accounts needing attention, broken setup items. `setup` is the Setup checklist: `{counts, total, open, done, items}` (the items that are not Working; the card disappears when `done`) |
| GET | `/admin/setup` | SA, Founder | Integrations and security requirements as one list: `{items, summary, help}`. Each item: `key`, `kind` (integration / security), `id`, `code`, `name`, `group`, `requirement`, `state` (Not set up / Set up / Working / Broken, from the two statuses: Misconfigured or Failed = Broken, Verified = Working, Configured = Set up, else Not set up), `owner {user_id, full_name, label}`, `evidence`, `notes`, `verified_at`, `last_checked_at` |
| PATCH | `/integrations/{id}`, `/security-controls/{id}` | SA | Now also takes `state` (a plain state instead of the two statuses; both together is a 400; Working still needs evidence) and `owner_user_id` (an active staff user; `null` clears it, the text `owner` follows) |
| GET | `/admin/staff-options` | SA, Founder | Every active staff member, unpaged: `{user_id, full_name, email, roles}` |
| GET | `/ai-controls/status` | SA, Founder | `{audiences: [{audience, label, state On/Off, control, via_all}], all: {state, control}, branches: [...], can_switch}`. An audience is Off company-wide when its own control or the All control is active (`via_all` when only All) |
| GET | `/admin/crm-sync/events?attention=true` | SA, Founder | Needs attention: Failed first (newest first), then Received but not finished. Every event now carries `label`, `summary`, `plain_cause` (one sentence for a Failed one) and `can_retry` (a Failed or Received event of a kind the intake still knows). Detail adds `payload` and `result`. The summary adds `needs_attention` (also the nav badge) |
| GET | `/admin/users?locked=true` | SA, Founder | Only accounts locked now; rows carry `locked_until` |
| GET | `/admin/students?needs_attention=true` | SA, Founder | Rows and the detail carry `suggested_step {code, label, detail, action (send_link / reactivate / open / issues / null), action_label, attention}` and `needs_attention`. The rules (`services/student_next_step.py`): suspended = Reactivate (no attention); not activated with no link, an expired link or one WhatsApp did not carry (`Queued` / `Sent` is carried) = Send a link; activated with sign-in off = open the account; enrolments held back (Provisioning Pending) = Issues; else wait or nothing. The filter is the same rules in SQL. The detail's `activation` adds the WhatsApp state of the link. `activation_channel` is no longer offered by the screen (the API still accepts it) |
| PATCH | `/calendar/closures/{id}` | SA, Founder (a Branch Manager proposes and cannot edit or cancel) | `{title?, reason?, starts_on?, ends_on?, dry_run?}` for an entry that is not over, cancelled or rejected. The answer is the entry plus `affected_count` and `affected_sessions` (Scheduled or Live classes inside the new dates), `newly_affected_count`, `freed_count` and `saved`. `dry_run: true` answers the same and saves nothing (the screen shows the impact first). Saving an approved entry asks the Branch Managers to replace the newly affected classes. A closure lasts at most 63 days; To before From is a 400 |
| POST | `/calendar/closures/{id}/cancel` | as PATCH | `{reason, dry_run?}`. The entry reads `status: "Cancelled"` with `cancel_reason`; working days and batch checks stop counting it; the classes inside its dates (`affected_sessions`) run as scheduled and the Branch Managers are told. `GET /calendar/closures` takes `status=Cancelled` and `sort=upcoming` (what is ahead first, soonest first, then what is over); it pages as before |
| GET | `/audit-log?preset=accounts\|roles\|integrations&actor_user_id=&entity_type=&entity_id=&action=&from=&to=` | SA, Founder | Every entry also has `sentence` (from the action-to-sentence map in `services/audit_sentences.py`; an action with no line reads "User unlocked by Asha"), `target` (the record's name) and `link {to, search?, params?}` for the record's screen (null when there is none). `facets` adds `actors` (everyone with an entry, not one page of staff) and `presets` |
| GET | `/audit-log/export` | SA, Founder | The same filters as a CSV (newest first, at most 5,000 rows; cells that would run as a formula are guarded) |
| POST | `/exceptions/{source}/{id}/assign` | SA | `{assignee_user_id, note?}`: hands an issue to an active staff member. It is a recovery step with `assigned_to`, so the owner, the owner filter and the counts follow; the person is told. Refused (422) for support requests, recordings and class disruptions that already have an owner set on their own screen. `GET /issues` rows add `can_assign`; recovery steps add `assigned_to` |

`GET /me/nav-counts` (as a Super Admin; the `?workspace=` is ignored) returns `home` (the sum of the others), `users` (locked), `student_accounts`, `issues` (nobody owns), `calendar` (closures waiting), `crm_sync` (needs attention) and `setup` (broken items).

### 4.22 Role separation R3: the session role, branch pick and who may do what (`120`)

**Session.** `user_sessions` carries `role_code` (the account's one role) and `branch_id` (a Branch Manager's branch for the session; `NULL` for every other role). `authenticate` builds `CurrentUser` from the session: `role_code`, `active_branch_id`, `needs_branch`, and `scopes` holding only the scope that role and branch map to. There is no union of roles and no implicit extra workspace. A session whose role or branch is no longer on the account is a 401 (the person signs in again).

**Workspace and home route (one each).** Student `student` `/dashboard`; Trainer `trainer` `/trainer`; Branch Manager `branch` `/branch`; Super Admin `admin` `/admin`; Founder / CEO `founder` `/founder`.

**Profile** (login, activation and `GET /auth/me` answer the same shape):

```json
{
  "user": {"user_id": 7, "full_name": "…", "email": "…", "must_change_password": false, "student_id": null},
  "role": {"role_code": "BRANCH_MANAGER", "role_name": "Branch Manager"},
  "workspace": "branch",
  "workspaces": ["branch"],
  "home_route": "/branch",
  "branch": {"branch_id": 1, "branch_code": "NIT-GNT", "branch_name": "Guntur"},
  "needs_branch": false,
  "branches": [],
  "scopes": [ {"scope_id": 1, "role_code": "BRANCH_MANAGER", "branch_id": 1, "...": "..."} ],
  "allowed_branches": [ {"branch_id": 1, "branch_code": "NIT-GNT", "branch_name": "Guntur"} ],
  "can_change_branch": false,
  "student": null
}
```

`can_change_branch` is true for a Branch Manager whose account holds more than one branch (the account menu then offers Change branch). `branch` is the Branch Manager's session branch (`null` for every other role and while a pick is pending). `workspaces` and `allowed_branches` stay for the frontend that still reads them: `workspaces` always has one element; `allowed_branches` is the session's branch (Branch Manager), the account's branch (Student, Trainer) or every active branch (Super Admin, Founder). `scopes` is the one scope of the session.

**Branch pick for a Branch Manager with several branches.**

1. `POST /auth/login {login, password}` (or activation) answers `200` with a real `token` and `needs_branch: true`, `branch: null`, `branches: [{branch_id, branch_code, branch_name}, ...]` (the account's branches).
2. Until a branch is picked every endpoint except `GET /auth/me`, `POST /auth/branch`, `POST /auth/change-branch` and `POST /auth/logout` answers `403 BRANCH_REQUIRED` ("Choose a branch to continue").
3. `POST /auth/branch {"branch_id": 2}` (Bearer token) answers `200` with the profile (`needs_branch: false`, `branch` set). A branch not on the account is `403 FORBIDDEN` and nothing changes. A second pick on the same session is `422`.
4. Shortcut: `POST /auth/login {login, password, branch_id}` picks in the same call. A `branch_id` the account does not hold is `403` and no session starts. `branch_id` is ignored for every role but Branch Manager.
5. A Branch Manager with one branch gets it automatically (`needs_branch: false`).
6. "Change branch": `POST /auth/change-branch` (`204`) ends the session. The frontend returns to the sign-in screen, where the person signs in again and picks. There is no way to switch branch inside a session.

**Who may do what.**

| Area | Branch Manager (session branch) | Super Admin | Founder / CEO |
|---|---|---|---|
| Branch day-to-day actions: batches (create, edit, state, confirm, trainers, generate classes), allocate / deallocate, class sessions (create, reschedule, cancel, start, Meet links, rosters, cover, guests), attendance marking and recovery decisions, results moderation and publishing, content review and approval, recordings release, completion decisions, certificate recommend / approve / issue, fee-release requests | yes | yes, any branch (`?branch_id=` or the record's branch) | yes, any branch |
| Read across branches (`?branch_id=` narrows): `GET /batches`, batch detail and progress, `/admin/students`, `/attendance/*`, `/progress/*`, `/enrolments`, `/support-requests`, `/issues`, `/finance-summaries`, `/branch/completion`, `/academic/reports`, `/academic/summary` | own branch only (404 elsewhere) | all branches | all branches |
| Reports | `GET /branch/reports` (and export), `GET /academic/reports` | `GET /branch/reports` and `GET /academic/reports`, both with `?branch_id=` | same |
| Support: reply, status, reopen, `assign` (reassign) | yes, any request of the branch | reply, status and reopen on requests owned by the Super Admin team (LMS / Account / Device, or assigned to a Super Admin); `assign` on any; others read-only (403). The detail carries `can_respond` | same as the Super Admin |
| A Branch Manager's own requests (reschedule, attendance correction, batch capacity change, transfer, merge or split, material change, cover, guest) | cannot decide their own (422); decide other people's | decide | decide |
| Founder inbox items (certificate changes, fee exceptions, access extensions beyond the limit, AI budget, Branch Managers' own requests) | no | decide (not their own request) | decide (not their own request) |
| Admin: users, scopes, hand-outs, CRM sync (including Retry), setup, integrations, security controls, AI controls, audit log, calendar decisions and company holidays, issue assign and notes, course outline, student suspend / reactivate, student activation links, branch payment instructions | no (payment instructions of their branch, calendar proposals and notes on issues of their branch only) | yes | yes |

`@fresh_auth` stays on the same sensitive actions for Super Admin and Founder alike. The independence rule is unchanged: nobody decides their own request (`services/approvals.py`; a Branch Manager's own request is decided by the Founder or a Super Admin, and only by them). The one exception is content and questions: the Super Admin and Founder may approve and release their own uploads and questions (a Branch Manager still may not). Everything a Branch Manager can do, the Super Admin and Founder can do for any branch (`ACADEMIC_ROLES` in `services/context.py`); a Branch Manager still sees and acts in the session branch only; a record outside the Branch Manager's branch is `404`.

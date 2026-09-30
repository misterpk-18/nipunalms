# Nipuna LMS — API Build Plan

Flask backend over the `nipunalms` PostgreSQL database (schema in `db/`, see [DB_PHASES.md](DB_PHASES.md)).
The product is defined by the interactive prototype at https://nipuna-lms-prototype.lovable.app/ (readable copy in
`prototype/reference/`) and the approved LMS modules 14–27. This plan covers the code structure, the conventions every
endpoint follows, the domain model and the order in which the APIs are built.

The repository mirrors **nipuna-crm** (`~/nipuna-crm`) layer for layer. When in doubt about a convention, copy what the CRM
does — its `backend/` and `frontend/` are the reference implementation.

---

## 1. Architecture

### Layers

A request flows top to bottom. Each layer only talks to the one directly below it.

| Layer | Folder | Responsibility | Must not |
|---|---|---|---|
| Routes | `backend/routes/` | Blueprints: URL + HTTP method, auth / role decorators (`routes/decorators.py`), call the controller | Contain logic or queries |
| Controllers | `backend/controllers/` | Read and validate the request (`Validator` in `controllers/common.py`), call the service, return JSON via `model.to_dict()` | Touch the database |
| Services | `backend/services/` | Business rules, permission and branch/record-scope checks, audit log, notifications. Shared: `errors.py`, `security.py`, `context.py` | Build HTTP responses |
| Repositories | `backend/repositories/` | Database queries: filters, joins, pagination, reading views. Shared: `common.py` (`paginate`, `set_db_user`) | Contain business rules |
| Models | `backend/models/` | SQLAlchemy classes mapped to the existing tables and views, each with `to_dict()` | Create or alter tables |
| Config | `backend/config/` | Settings per environment, the shared `db` object, logging, JSON encoding | Import from any other layer |

Every module uses the same file name across layers: `routes/assignments.py → controllers/assignments.py →
services/assignments.py → repositories/assignments.py → models/assignments.py`.

`app.py` is the only place that builds the application; nothing imports from it. One transaction per request (commit on
success, roll back on error), every exception becomes `{"error": {...}}`.

### Key decisions

| Decision | Choice | Why |
|---|---|---|
| Separate system | Own repo, own database (`nipunalms`), own API (`:5060`) and SPA (`:5174`) | CRM stays authoritative for Admission and finance; LMS owns learning (Module 27 authority split) |
| Schema ownership | SQL files in `db/` are the source of truth; models map existing tables; never `db.create_all()` | Triggers, views, enums and constraints |
| CRM → LMS | CRM posts versioned, idempotent events to `POST /api/v1/integrations/crm/events` (service key). The LMS stores every event in `crm_events` and upserts Student, Admission projection, Enrolments and the finance summary | Guide §17: durable handoff, retry of the same event, late events cannot undo newer decisions |
| Finance in LMS | Read-only projection (`finance_summaries`) of what the CRM sends; the LMS never edits money | "CRM is authoritative for Admission and finance" |
| Identity | One `students` row per CRM Person (`crm_person_id` unique) = one LMS account. Student logs in with Student ID (`NIT-STU-2026-004182`) or email; mobile is never a login key | Shared family mobile is not identity proof (M29) |
| Activation | Single-use, expiring activation token (hash stored); the student sets their own password. Staff can issue/reissue (supervised activation) | M29 assisted activation |
| Auth tokens | Same as CRM: opaque bearer session token, SHA-256 hash in `user_sessions`, idle timeout + max session, fresh auth for sensitive actions | Revocation and fresh auth need server-side sessions |
| Integrations | Google Meet / Drive / Workspace, WhatsApp, email, AI provider: an `integrations` register with requirement / configuration / verification status. No live calls; actions that would call them record "Integration Unavailable" / "Pending Verification" states | Prototype + M27: capability must be verified separately |
| AI (Ask Nipuna) | Anthropic API when `ANTHROPIC_API_KEY` is set, otherwise rule-based fallback over the student's own permitted content; scope + sources + daily usage limit | Same pattern as the CRM AI Copilot |
| Language | Student screens bilingual (English / తెలుగు); stored preference on the student | Prototype language toggle |
| Tests | pytest against `nipunalms_test` built from `db/*.sql`, each test in a rolled-back transaction | Same as CRM |

---

## 2. Conventions (all endpoints)

Identical to the CRM (`~/nipuna-crm/docs/API_PLAN.md` §2):

- Prefix `/api/v1`, plural nouns, actions as sub-resources (`POST /submissions/{id}/review`, `POST /certificates/{id}/issue`).
- Success `{"data": ...}` (+ `"meta": {page, per_page, total, pages}` for lists); error `{"error": {"code", "message", "details"}}`.
- Status codes: 400 `VALIDATION_ERROR`, 401 `UNAUTHENTICATED` / `FRESH_AUTH_REQUIRED`, 403 `FORBIDDEN` / `PASSWORD_CHANGE_REQUIRED`,
  404 `NOT_FOUND` (also for records outside the user's scope), 409 `CONFLICT`, 422 `BUSINESS_RULE` / `INVALID_REFERENCE`, 429 `TOO_MANY_ATTEMPTS`.
- Lists: `?page=&per_page=` (max 100), filters as query params (`?branch_id=1&batch_id=3&status=Due`).
- Timestamps ISO 8601 with offset; business dates in IST (`Asia/Kolkata`). Money as strings with 2 decimals.
- Enum values exactly as stored (`"Curriculum Mapping Pending"`). Every response carries numeric `*_id` plus the human code
  (`student_code`, `batch_code`, `certificate_number`, …).
- Audit: services write `audit_log` for sensitive changes (publishing results, certificate issue/revoke, role changes,
  access extensions, recording release, account activation/recovery) with old and new values.

### Scope rules (server-enforced on every list, detail, total, export and AI answer)

| Role (`role_code`) | Sees |
|---|---|
| `STUDENT` | Only their own student record, enrolments, sessions of batches they are allocated to, released content/recordings of those enrolments, own submissions/attempts/results/certificates/support/notifications |
| `TRAINER` | Batches they are assigned to (`batch_trainers`), the students allocated to those batches, sessions they teach |
| `ACADEMIC_COORDINATOR` | Everything academic at their branch (`branch_id` of the scope) |
| `BRANCH_MANAGER` | Everything at their branch (academic + operational + read-only finance summary) |
| `SUPER_ADMIN` | All branches; admin / integrations / security; can open academic and branch workspaces |
| `FOUNDER_CEO` | All branches, management overview; can open admin and branch workspaces (read-mostly) |

Branch comes from `batches.branch_id` / `enrolments.service_branch_id`, never from a submitted value. A record outside
scope is a 404, not a 403.

---

## 3. Domain model

Names below are the contract between slices. Codes follow the prototype:
`NIT-STU-2026-004182`, `ADM-GNT-2026-000214`, `NIT-GNT-BAT-2026-000001`, `NIT-CRS-018`, `NIT-CERT-2026-000001`.

### Backbone (Phase 1 — `001`…`005`)

| Table | Purpose |
|---|---|
| `branches` | 1 = NIT-GNT Guntur, 2 = NIT-VIJ Vijayawada; code, name, city, mailbox (`trainer@…` / `contactus@nipunatechnologies.com`) |
| `roles`, `users`, `user_role_scopes`, `user_sessions` (+ `active_sessions` view) | Same shape as CRM. Students are users too: `users.student_id` links a login to a student |
| `audit_log` | Append-only (UPDATE/DELETE blocked by trigger) |
| `app_settings` | Key/value settings (session timeouts, AI daily limit, recording access days, …) |
| `integrations` | Register: code, name, requirement, configuration status, verification status, owner, last check |
| `notifications` | In-app notifications: recipient user, category, title, body, link, `delivery_status` / `read_at` / `acknowledged_at` / `action_status`, `event_key` (dedupe) — plus `services/notifications.notify()` used by every slice |
| `activity_events` | Generic learning activity log (student, enrolment, kind: `login`, `resource_view`, `recording_view`, `topic_complete`, …) — feeds the engagement measure |
| `courses` | LMS course catalogue mirrored from CRM Course Master: `course_code`, title, `is_combo`, status |
| `course_components` | Combo structure: parent course → component course, `track_code` (`NIT-CRS-018/T1`), role (`Main track` / `Included booster`), order |
| `curriculum_versions` | Per course (or per component track): label (`Parent Programme v2026.1`, `Track CV 3.2`), status `Draft` / `Under Review` / `Approved` / `Active` / `Retired`, approved_by/at |
| `curriculum_modules` | Version → ordered modules (`Supervised Learning`) |
| `curriculum_topics` | Module → ordered topics, `is_required` |
| `students` | Student Master: `student_code`, `crm_person_id` (unique), full_name, name_te, email (optional), mobile (not unique), original/service branch, preferred_language, `activation_status` (`Account Created` / `Activation Pending` / `Activated` / `Suspended`), mfa_status |
| `student_activations` | Activation tokens (hash, expires_at, used_at, issued_by, channel) |
| `admissions` | CRM projection: `crm_admission_id` unique, `admission_code`, student, course, original / service / collecting branch, crm status, `source_version` |
| `enrolments` | `enrolment_code`, admission, student, course, `kind` (`Combo`, `Standalone`, `Separately purchased`, `Complimentary`), `parent_enrolment_id` (complimentary → qualifying enrolment), curriculum_version, service branch, mode, `status` (`Provisioning Pending`, `Curriculum Mapping Pending`, `Allocation Pending`, `Allocated — awaiting first regular class`, `Active`, `Paused`, `Completed`, `Withdrawn`), joining_date (first regular class attended), access_start/end, certificate_status, benefit gate note |
| `enrolment_tracks` | Combo enrolment → component track + its curriculum version |
| `finance_summaries` | Read-only per-admission finance snapshot from CRM: fee, verified paid, balance, next due date/amount, receipts (jsonb: number, date, amount), `as_of`, `source_version` |
| `crm_events` | Inbox: `event_id` unique, `event_type`, payload jsonb, `source_version`, original event time, received/processed time, status (`Received` / `Applied` / `Ignored — stale` / `Failed`), error, retries |
| `batches` | `batch_code`, course, branch, curriculum_version, capacity, mode, planned start/end, `state` (`Forming`, `Starting`, `Running`, `Full`, `Completed`, `Cancelled`), readiness (`Ready` / `Blocked` / `Pending Verification`) + reason + recovery owner |
| `batch_trainers` | Batch ↔ trainer user (`Lead` / `Co-trainer`), from/to |
| `batch_allocations` | Enrolment (or enrolment track) ↔ batch with effective dates, status, reason; history retained |
| `class_sessions` | Actual Class Session: `session_code`, batch, topic, title, scheduled start/end (timestamptz), mode (`Classroom` / `Live Online` / `Hybrid`), trainer, room, `meet_link` + `meet_status`, `state` (`Scheduled`, `Live`, `Delivered`, `Cancelled`, `Rescheduled`), delivered_at, notes |

### Slice tables (Phase 2 — each slice owns its migration)

| Slice | Owns tables (indicative) |
|---|---|
| S1 Delivery | `session_changes` (reschedule / cancel history with reason), `meet_events` (organizer, association status) — plus all delivery APIs over the backbone |
| S2 Content & recordings | `content_items` (+ versions), `content_reviews`, `recordings`, `recording_exceptions` (`RX-0012`), `access_extension_requests` |
| S3 Assessments | `assignments`, `assignment_submissions` (versioned), `submission_reviews`, `questions` (bank), `tests`, `test_questions`, `test_attempts` (server-authoritative timer), `attempt_answers`, `interview_slots`, `results` (provisional → moderated → published) |
| S4 Attendance & certificates | `attendance_records` (trainer-confirmed, per session × enrolment), `attendance_recoveries` (`REC-0041`), progress views (delivery, attendance, required learning, engagement), `completion_reviews`, `certificates` (register, versions, supersede / revoke) |
| S5 Student services | `support_requests` (+ messages, owners, escalations), `career_profiles`, `cv_documents`, `opportunities`, `applications`, `placement_outcomes`, `ai_queries` (+ usage), `user_devices` |
| S6 Admin & security | `security_controls` (requirement / configuration / verification), `exception_queue` view, staff user management, audit viewer, CRM sync monitor & provisioning retry |
| Phase 3 Dashboards | Aggregates only (student Home, trainer Today, academic / branch / admin / founder dashboards, reports) |

---

## 4. Build order

| Phase | Work | Status |
|---|---|---|
| 1a | Backend foundation + backbone schema + auth (staff and student login, activation) + CRM event intake + seed from prototype sample data | ✅ Done — 117 pytest |
| 1b | Frontend foundation: shell, auth, per-role navigation, EN/తెలుగు, shared components, every route as a placeholder | ✅ Done — `e2e/shell.spec.ts` |
| 2 | Slices S1–S6 in parallel (backend + tests + frontend screens), each in its own worktree | ⏳ |
| 3 | Merge, dashboards & reports, exception queues, session/topic panels across slices | ⏳ |
| 4 | Validation: full cross-role Playwright suite (desktop + mobile) against the merged app, acceptance matrix in `TESTING.md`, `PRODUCT_GUIDE.md`, `ROLE_GUIDE.md` | ⏳ |

Endpoint tables are added per slice below as they are built ("As built" notes, like the CRM).

---

## 5. Endpoints

### Health & auth (Phase 1a)

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
| POST | `/students/{id}/activation` | Super Admin / BM / AC (branch) | Issue or reissue an activation token (fresh auth) |

### CRM integration (Phase 1a)

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/integrations/crm/events` | CRM service key (`X-Service-Key`) | `AdmissionQualified`, `AdmissionUpdated`, `AdmissionCancelled`, `FinanceSummaryUpdated`, `CourseUpserted`. Idempotent on `event_id`; stale `source_version` → `Ignored — stale` |
| GET | `/integrations/crm/events` | Super Admin | Inbox with status filters |
| POST | `/integrations/crm/events/{id}/retry` | Super Admin | Re-apply a failed event |
| GET | `/integrations/crm/status?since=` | CRM service key | What the CRM stores about the LMS, changed since `since`: `persons` [{crm_person_id, lms_user_id, lms_provisioned_at}], `admissions` [{crm_admission_id, lms_status, lms_last_activity_at, lms_last_synced_at}], `batches` [{crm_batch_id, lms_course_id}] |

**As built (1a):**
- Every event is stored once in `crm_events`. Replaying an `event_id` returns the first result; the same `event_id` with a different payload is a 409; a `source_version` lower than the stored one is recorded as `Ignored — stale` and changes nothing. A failure is kept as `Failed` with the error, retryable.
- `AdmissionQualified` upserts the Student by `crm_person_id` (one Student / one LMS login per Person, reused for later admissions), the Admission projection and its Enrolments. An enrolment waits in *Curriculum Mapping Pending* when its course has no Active curriculum version, else *Allocation Pending*. A new login gets an activation token; the branch Academic Coordinator is notified. The response includes `lms_user_id` and `lms_status`.
- `AdmissionCancelled` withdraws only that admission's enrolments. `FinanceSummaryUpdated` replaces the read-only finance snapshot.
- Values the CRM keeps (`persons.lms_user_id`, `admissions.lms_status`, `batches.lms_course_id`, …) are queued in `crm_outbox` in the same transaction as the change and are also served by `/integrations/crm/status`. Mapping table: [DB_PHASES.md](DB_PHASES.md#crm-columns-fed-by-the-lms).

### Reference & backbone reads (Phase 1a)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/reference/branches`, `/reference/roles`, `/reference/courses` | Staff | Courses include combo components |
| GET | `/reference/staff?role=&branch_id=` | Staff | Staff in the caller's branches |
| GET | `/students/{id}` | Scoped | Student record (student: own only) |
| GET | `/batches`, `/batches/{id}` | Scoped | Filters `branch_id`, `course_id`, `state`; trainers see assigned batches only |
| GET | `/class-sessions?batch_id=&from=&to=` | Scoped | |

Scope helpers every slice uses live in `services/scope.py` (branch visibility, trainer batches, student enrolments; out-of-scope → 404).

### Admin & security (S6 — `060_admin_security.sql`)

Super Admin manages; the Founder / CEO can read every list (mutations are Super Admin only, all with fresh auth). Nothing here calls an external system.

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
| GET | `/admin/students?q=&activation_status=&branch_id=` | Super Admin, Founder | Search by Student ID, name, email; activation status, LMS account (`lms_user_id`, login state, active sessions), enrolment counts |
| GET | `/admin/students/{id}` | Super Admin, Founder | Adds enrolments, outstanding activation link state (never the token), suspension reason, recent audit |
| POST | `/admin/students/{id}/suspend`, `/reactivate`, `/revoke-sessions` | Super Admin | Suspend `{reason}`: blocks sign-in, ends sessions, cancels the activation link. Reactivate returns to Activated (password set) or Account Created |
| POST | `/students/{id}/activation` | (Phase 1) | Issue / reissue the activation token (shown once) — used by the Student Accounts screen |
| GET | `/admin/crm-sync/summary` | Super Admin, Founder | Counts by status for the inbox and outbox, last received / delivered, oldest pending |
| GET | `/admin/crm-sync/events?status=&event_type=&q=&from=&to=`, `/events/{id}` | Super Admin, Founder | List without payload; detail with payload and result |
| POST | `/admin/crm-sync/events/{id}/retry` | Super Admin (fresh auth) | Re-applies a Failed event; audited `CRM_EVENT_RETRIED` on success |
| GET | `/admin/crm-sync/outbox?status=&event_type=`, `/outbox/{id}` | Super Admin, Founder | Values queued for the CRM |
| GET | `/audit-log?actor_user_id=&entity_type=&entity_id=&action=&branch_id=&from=&to=`, `/audit-log/facets` | Super Admin, Founder | Newest first with the actor's name; `from` / `to` are inclusive IST dates; facets list the distinct actions and entity types |

**As built (S6):**
- `services/integrations.py` exposes `integration_status(code)` (`.state`, `.is_verified`) and `is_verified(code)` for other slices; an unknown code counts as Not Configured / Not Verified. `GOOGLE_MEET` gates `class_sessions.meet_status`, `GOOGLE_DRIVE_RECORDINGS` gates recording import.
- Readiness rules (integrations and security controls share `services/readiness.py`): *Verified* needs a Configured setup and an evidence note and records `verified_by` / `verified_at`; taking a Verified record out of Configured drops it to Not Verified; any status or evidence change sets `last_checked_at`. The database CHECK `*_verified_needs_evidence` enforces the same. Audit actions: `INTEGRATION_UPDATED`, `SECURITY_CONTROL_UPDATED` (entity id = code, old / new of the changed fields only).
- Staff account actions are audited on the `user` entity (`USER_CREATED`, `USER_UPDATED`, `SCOPE_GRANTED`, `SCOPE_REVOKED`, `USER_DEACTIVATED`, `USER_REACTIVATED`, `PASSWORD_RESET`) and student actions on the `student` entity (`STUDENT_SUSPENDED`, `STUDENT_REACTIVATED`, `STUDENT_SESSIONS_REVOKED`, plus the Phase 1 activation actions). Passwords and tokens are never written to the audit log.
- The platform always keeps an active Super Admin: the last one cannot be deactivated or lose the scope, and nobody can revoke or deactivate themselves.
- The Phase 1 `GET /integrations/crm/events` and `POST /integrations/crm/events/{id}/retry` remain; the admin screen uses the `/admin/crm-sync/*` equivalents (payload only on detail, audited retry).

### Attendance, progress, completion & certificates (S4 — `db/040`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/attendance/sessions` | Trainer, AC, BM, SA, Founder (scoped) | Live / Delivered sessions with `seats`, `marked`, `attendance_state`, `locked`, `can_mark`; filters `batch_id`, `from`, `to`, `attendance=pending\|marked\|locked` |
| GET | `/attendance/sessions/{id}` | same | The register: one row per allocated enrolment, `label` ("Absent — recovery approved (REC-0041)"), summary, `locked`, `can_mark` |
| PUT | `/attendance/sessions/{id}` | Trainer of the batch, AC, SA | `{default_status?, entries: [{enrolment_id, status, remarks?}]}`; `default_status` fills only seats without an entry ("all Present, then exceptions"). Sets the joining date (first Present / Late) |
| GET | `/me/attendance` | Student | Per own enrolment: attendance measure + a row per Live / Delivered class since joining |
| GET | `/attendance/enrolments/{id}` | Scoped | Same block for one enrolment |
| GET / POST | `/attendance/recoveries` | Scoped / Student, Trainer, AC, SA | Raise `{attendance_id, method, reason}` for an Absent entry; one live recovery per absence |
| POST | `/attendance/recoveries/{id}/decision` | AC, SA | `{decision: Approved\|Rejected, decision_note?, target_date?}` |
| POST | `/attendance/recoveries/{id}/completion` | Trainer of the batch, AC, SA | `{evidence_note}` verifies an approved recovery (Completed) |
| GET / POST | `/attendance/corrections` | Scoped / Student, Trainer, AC, SA | `{session_id, enrolment_id, requested_status, reason}`: a dispute, or a change after the lock |
| POST | `/attendance/corrections/{id}/decision` | AC, BM, SA (fresh auth) | Approve applies the change; the decider must not be the requester or the marker |
| GET | `/me/progress`, `/progress/enrolments/{id}` | Student / Scoped | The four measures (`delivery`, `attendance`, `required_learning`, `engagement`), never combined |
| GET | `/progress/students` | Staff (scoped) | Table with filters `branch_id`, `course_id`, `batch_id`, `status`, `alert`, `q` |
| GET | `/progress/summary` | AC, BM, SA, Founder | Per-batch averages of each measure, enrolments and certificates by status |
| GET | `/completion-reviews` | Staff (scoped) | Running / completed enrolments with evidence, latest review, certificate status |
| POST | `/completion-reviews` | Trainer, AC, SA | `{enrolment_id}` opens a review (201, or 200 with the open one) |
| POST | `/completion-reviews/{id}/recommendation` | Trainer of the batch, AC, SA | `{recommendation, comment?}` |
| POST | `/completion-reviews/{id}/decision` | AC, SA (fresh auth) | `{decision: Complete\|Not Yet\|Needs Recovery, reason?}`; Complete → enrolment Completed + certificate eligibility |
| GET | `/certificates`, `/certificates/{id}`, `/me/certificates` | AC, BM, SA, Founder (branch scope) / Student (own) | Register entries (every version) with `actions` the caller may take; detail has `history` |
| POST | `/certificates` | AC, SA | `{enrolment_id, certificate_type}` adds an entry (e.g. Internship Certificate) |
| POST | `/certificates/{id}/recommendation`, `/return`, `/approval`, `/issue`, `/reissue`, `/revocation` | AC / BM / BM, AC, SA / BM, SA / SA | Approval, issue, reissue, revocation need fresh auth; approval needs someone other than the recommender |
| GET | `/certificates/verify/{number}` | Public | Holder, course, issue date, status, version only |

**As built (S4):**
- Attendance: no row = "Not yet marked" (never a guessed absence). A session locks `attendance_lock_days` (7) after it ends; later changes go through a correction with an independent reviewer. Absent students get an in-app notification.
- Joining date: `services/attendance.set_joining_date(enrolment, date)` — the first Present / Late moves "Allocated — awaiting first regular class" to Active and opens the enrolment's Certificate Register entry (Not Yet Eligible).
- Progress is computed by SQL views (`enrolment_progress` and the views under it). Attendance % = (Present + Late) / marked classes delivered since joining; "Partial Data" while any delivered class is unmarked; the alert needs three marked classes and `attendance_alert_threshold`. Excused counts against the percentage; an approved or completed recovery is reported separately and counts towards required learning.
- Certificates: the database validates transitions and allocates `NIT-CERT-YYYY-NNNNNN` at first issue; a reissue is a new version under the same number and supersedes the earlier one. Complimentary enrolments stay "Configuration Pending" until `complimentary_completion_rule_configured` is true.
### S1 — Delivery: curriculum, enrolments, batch allocation, class sessions, student course pages (migration `010`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/curriculum/overview` | Staff | One row per course: Active version, versions in review, mapped / pending enrolments (Curriculum Mapping Pending) |
| GET / POST | `/curriculum-versions` | Staff / AC, Super Admin | List (filters `course_id`, `status`); create a Draft (optionally copied from an earlier version) |
| GET / PATCH / DELETE | `/curriculum-versions/{id}` | Staff / AC, Super Admin | Detail with modules, topics, review trail and publish blockers; rename; delete only a never-published Draft |
| POST | `/curriculum-versions/{id}/submit`, `/return`, `/approve`, `/activate`, `/retire` | AC, Super Admin (approval by someone other than the submitter) | Draft → Under Review → Approved → Active → Retired; `return` needs a reason. Activating maps Curriculum Mapping Pending enrolments and batches and returns the counts |
| POST | `/curriculum-versions/{id}/modules`, `/curriculum-modules/{id}/topics` | AC, Super Admin | Add to a Draft (optional `position`) |
| PATCH / DELETE | `/curriculum-modules/{id}`, `/curriculum-topics/{id}` | AC, Super Admin | Draft only; sort order re-sequenced |
| GET | `/enrolments`, `/allocation-queue` | Staff / AC, BM, Super Admin | Branch-scoped enrolment list; the queue of Payment-cleared enrolments waiting for a seat |
| GET / POST | `/batches/{id}/allocations` | Staff / AC, BM, Super Admin | Roster (filter `status`); allocate an enrolment |
| GET | `/batches/{id}/allocation-review?enrolment_id=&transfer=` | AC, BM, Super Admin | The checks (branch, course, curriculum, capacity, state, gate, finance) as pass / warn / block |
| POST | `/enrolments/{id}/transfer`, `/enrolments/{id}/deallocate` | AC, BM, Super Admin | Reason required; warnings need `acknowledge_warnings` |
| POST / PATCH | `/batches`, `/batches/{id}`, `POST /batches/{id}/state`, `/trainers`, `/readiness` | AC, BM, Super Admin | Batch lifecycle with `batch_events` history (extends the Phase 1 batch endpoints) |
| GET / POST / PATCH | `/class-sessions`, `/class-sessions/{id}` | Staff; create / edit AC, BM, Super Admin | Filters include `batch_id`, `trainer_id`, `state`, `from`, `to`; create accepts a weekly `recurrence` (weekdays, `until` / `count`) |
| POST | `/class-sessions/{id}/start`, `/deliver`, `/cancel`, `/reschedule` | Trainer of the batch (start, deliver); AC, BM, Super Admin (cancel, reschedule) | Reason required for cancel / reschedule; `session_changes` row with notice hours and `short_notice` |
| POST | `/class-sessions/{id}/reschedule-requests`; GET `/reschedule-requests`; POST `/reschedule-requests/{id}/approve`, `/reject` | Trainer (ask); AC, BM (decide) | One open request per session; approve applies the proposed time |
| PUT / POST | `/class-sessions/{id}/meet`, `/meet/fail`, `/meet/reset` | AC, BM, Super Admin | Records the Meet association in `meet_events`; the LMS never calls Google |
| GET | `/me/enrolments`, `/me/enrolments/{id}`, `/me/enrolments/{id}/tracks/{track_id}`, `/me/schedule` | Student | Own courses with delivery progress, combo tracks and upcoming / past classes |
| GET | `/modules/{id}`, `/topics/{id}` | Student (own enrolments) / staff | Module and topic pages with their classes, resources and recordings |

**As built (S1):**
- Curriculum versions are snapshots: modules and topics change only while the version is a Draft (database trigger); an Active version is retired only when another takes over or with a reason. Approval by the submitter is refused.
- Allocation is the only path to a seat: the review returns per-check results, a blocked check cannot be overridden, a warning needs the acknowledgement; transfers and deallocations keep the allocation row (history) and free the seat. A student is told of every seat change.
- Batch lifecycle is enforced by trigger (Forming → Starting → Running <-> Full → Completed; Cancelled from any open state). Sessions: Scheduled / Rescheduled → Live → Delivered; Cancelled; a Live, Delivered or Cancelled session can no longer change time or trainer. A trainer cannot teach two overlapping classes (trigger + service message) and a room cannot be double-booked.
- Rescheduling with less than 24 hours' notice is flagged `short_notice` and students of the batch are notified; every change is in `session_changes`.
- The student "Join" state comes from `services/meet.join_state`: enabled only when the Meet link is associated and the class is Live or within 15 minutes of starting. Meet links are entered manually until the Google integration is verified.
- Notifications go through `services/delivery_notices.py` so a repeated event never sends twice.
- Attendance (S4) reuses `repositories/class_sessions.get_session`; there is one session lookup.

### S2 — Content library, recordings, recording exceptions, access extensions (migration `020`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/content-items` | Staff | Filters `course_id`, `batch_id`, `branch_id`, `module_id`, `topic_id`, `content_type`, `q`, `status` (comma list). Trainer: own items + items of batches they teach; AC / BM: their branches; Super Admin / Founder: all |
| POST | `/content-items` | Trainer, AC, Super Admin | JSON (links) or multipart with `file`. Placement from `topic_id` / `module_id` / `curriculum_version_id` / `course_id`; branch from the batch or the author's batches (`branch_id` needed for Super Admin). Creates v1 Draft |
| GET | `/content-items/options` | Staff | Batches the caller may author for, with curriculum versions, modules and topics |
| GET / PATCH | `/content-items/{id}` | Staff / author, AC, Super Admin | Detail with versions and review history; edit metadata, placement, download policy (author only while Draft / Changes Requested; reviewer audited) |
| POST | `/content-items/{id}/versions` | Author, AC, Super Admin | New file (multipart) or `url`; v2, v3 … earlier versions kept |
| POST | `/content-items/{id}/submit` | Author, AC, Super Admin | Draft / Changes Requested → Submitted; coordinators notified |
| POST | `/content-items/{id}/review` | AC (branch), Super Admin | `decision` start / approve / request_changes / reject (+ `comment`, `release`); never the uploader |
| POST | `/content-items/{id}/release`, `/retire` | AC (branch), Super Admin | Approved → Released (previous released version retired, students notified); retire needs a reason |
| POST | `/content-items/{id}/open` | Student, staff | Students: entitlement + expiry checked, `resource_view` activity recorded; returns link URL / file info |
| GET | `/content-items/{id}/file?download=` | Student, staff | Serves the file; entitlement, expiry and `download_allowed` enforced here; only safe types shown inline |
| GET | `/me/resources`, `/me/recordings`, `/me/access` | Student | Released items / recordings of the student's own enrolments with access state; Joining Date, expiries and what can still be requested |
| GET / POST | `/recordings` | Staff / AC, Super Admin | List scoped by branch or taught batches; register a part against an actual class session |
| GET / PATCH | `/recordings/{id}` | Staff / AC, Super Admin | Detail (+ open exceptions); media reference, duration, source, download policy |
| POST | `/recordings/{id}/release`, `/hold`, `/partial`, `/unavailable` | AC (branch), Super Admin | Release needs the media reference and a Delivered class and closes open hold / partial exceptions; hold / partial / unavailable raise an exception |
| POST | `/recordings/{id}/watch` | Student | Entitlement and expiry checked, `recording_view` recorded; playback state read from the integrations register |
| GET / POST | `/recording-exceptions` | Staff / Trainer, AC, Super Admin | RX codes; filters `status`, `issue_type`, `branch_id`, `batch_id`, `session_id` |
| POST | `/recording-exceptions/{id}/start`, `/resolve` | AC, BM (cover), Super Admin | Integration exceptions are Super Admin only; resolve needs a note |
| POST / GET | `/access-extension-requests` | Student (create) / student, AC, BM, Super Admin, Founder | EXT codes; own requests or the branch's |
| POST | `/access-extension-requests/{id}/decision` | AC / BM of the service branch, Super Admin; exceptions: Super Admin, Founder | `approve` / `reject` (+ `note`, `new_expiry` for an exception) |

Job: `flask --app app jobs run recording-check` (`jobs list` shows all jobs).

**As built (S2):**
- Content versions carry the review lifecycle (Draft → Submitted → Under Review → Approved → Released, or Changes Requested / Rejected; a superseded version is Retired); the item's `status` follows its latest version, so students keep the last Released version until a newer one is released. A retired item is withdrawn from students; files and versions are never deleted.
- Audience = same branch and course, the item's batch (if any) is the enrolment's active batch, and the item's curriculum version is the enrolment's version or one of its combo tracks' versions (`services/content.item_matches_enrolment`). Withdrawn and gate-blocked enrolments grant nothing.
- Access window (`services/access.py`): one calendar year from the enrolment's Joining Date through the end of the anniversary day in IST (29 Feb → 1 Mar), one extra year to the second anniversary on request (Recording, Material or Both), pending before joining. Settings `access_default_years` / `access_max_years`; the older `recording_access_days` is superseded by Module 17 §8 and unused.
- Uploads: allow-list, 50 MB / 250 MB (datasets, archives) from `app_settings`, magic-number check, notebook JSON check, safe ZIP inspection (paths, nested archives, executables, expansion ratio). Local disk under `UPLOAD_DIR`; no malware scan yet (BACKLOG).
- Recordings are references only; Google is never called. Escalation clock from class end: 4 h Academic Coordinator, 24 h Branch Manager + Super Admin, 48 h Founder (`escalation` on each exception; the job sends the notices once).
### Assessments — S3 (`030_assessments.sql`)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/assignments?batch_id=&state=&status=&is_required=` | Scoped | Student: released tasks of their batches with `my.state` (Upcoming, Due, Overdue, Submitted, Under Review, Reviewed, Resubmission Requested), versions, submission window. Staff: assignments with counts |
| GET | `/assignments/{id}` | Scoped | Student sees released work of their batch only (else 404) |
| POST | `/assignments` | Trainer of the batch, AC, Super Admin | Draft; `release_now` releases at once. Reviewer defaults to the creating / lead trainer |
| PATCH | `/assignments/{id}` | Same | Draft: any field. Released: brief, attachments, due time (later only), late policy, reviewer; `closes_at` (reopen window) is AC-only with a reason. Audited; students notified |
| POST | `/assignments/{id}/release`, `/withdraw` | Same | Withdraw needs a reason; versions and results are kept |
| POST | `/assignments/{id}/submissions` | Student | JSON or multipart (`file`, up to 10 MB). New version; replacement before the deadline, late first submission inside the 7-day window, instructed resubmission (up to 2) |
| GET | `/submissions?assignment_id=&status=Awaiting Review&reviewer_me=true` | Staff | Newest version per student |
| GET | `/submissions/{id}`, `/submissions/{id}/file` | Owner, batch staff | Other students and other batches: 404 |
| POST | `/submissions/{id}/start-review`, `/review` | Staff of the batch | `outcome` Reviewed (marks up to the maximum) or Resubmission Requested (own deadline). Marks create a Provisional result |
| GET | `/assessments/curriculum?batch_id=` | Staff | Modules and topics of the course's Active curriculum versions (for linking) |
| GET/POST/PATCH | `/questions`, `/questions/{id}` | Trainer, AC, Super Admin (branch bank) | Type-specific answer key validation; keys never reach students |
| POST | `/questions/{id}/approve`, `/retire`, `/new-version` | AC / Super Admin (the author cannot approve) | Approved questions are frozen; a change is a new version |
| GET/POST/PATCH | `/tests`, `/tests/{id}` | Scoped | The student list shows every status of their batches' tests with their own state |
| PUT | `/tests/{id}/questions` | Batch staff | Approved questions of the batch's course and branch, frozen into the test |
| POST | `/tests/{id}/approve` | AC / Super Admin | Formal tests need it before release |
| POST | `/tests/{id}/release`, `/close` | Batch staff | Not Released to Released (Scheduled / Available / Closed by window) |
| POST | `/tests/{id}/attempts` | Student | 201 starts (deadline = min(start + duration, window end)); 200 resumes the open attempt |
| GET | `/attempts/{id}` | Owner, batch staff | Reading past the deadline submits the saved answers once |
| PUT | `/attempts/{id}/answers` | Student | Autosave; after the deadline `accepted: false` and the attempt is submitted |
| POST | `/attempts/{id}/submit` | Student | Idempotent; receipt `RCPT-T-00931` |
| GET | `/attempts?grading_status=Awaiting Grading&reviewer_me=true` | Staff | Grading queue |
| POST | `/attempts/{id}/grade` | Batch staff | Marks for Descriptive / Coding answers; complete means Graded, and for a formal test a Provisional result |
| GET/POST | `/tests/{id}/slots`, `/interview-slots/{id}/book`, `/confirm`, `/cancel`, `/complete` | Trainer offers, confirms, completes; student books | Open, Slot Confirmation Pending, Confirmed, Completed |
| GET | `/me/results` | Student | Only Published results carry a score |
| GET | `/results?batch_id=&assignment_id=&test_id=&status=` | Staff | Provisional, moderated and final marks |
| GET | `/assessment-reviews` | Staff | Moderation queue per assessment and batch, plus tests not ready |
| POST | `/results/{id}/moderate`, `/results/publish` | AC / Super Admin | Moderate needs a reason (audited); publish by ids or `assignment_id` / `test_id`; students notified |

**As built (S3):**
- Student-visible marks and feedback exist only after publication; the one exception is the feedback attached to a resubmission request. Practice quizzes and mock tests are non-credit: scored at once, no result row. Formal kinds (Module test, Coding exercise, Final test, or `is_required`) need pass marks, a closing time and AC approval.
- The attempt clock is the server's: `started_at`, `deadline_at`, `submitted_at` (the deadline on timeout) and the receipt are set by the API and the database (a trigger rejects answers after the deadline or once submitted). Expiry is applied lazily on the next read or save.
- Scoring: exact-set multiple choice, numeric tolerance, accepted short-answer variants, no negative marking; written and coding answers wait for the trainer. Code is never executed (`Integration Unavailable`).
- New role groups in `services/context.py`: `ASSESSMENT_AUTHOR_ROLES`, `MODERATOR_ROLES`. Notification categories: Assignments, Reviews, Assessments, Results.

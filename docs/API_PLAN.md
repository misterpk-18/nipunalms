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

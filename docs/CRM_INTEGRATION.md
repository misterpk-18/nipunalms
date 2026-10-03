# Nipuna LMS ↔ CRM integration

How the LMS and the CRM (`nipuna-crm`) are connected: who owns what (§1), the wire contract (§2), how each side runs it
(§3), what is still open (§4) and the history of the integration rounds (§5).

How to run both systems together on one laptop is in [DEVELOPMENT.md Part C](DEVELOPMENT.md#part-c--running-with-the-local-crm).
The CRM's side is documented in its own repo (`nipuna-crm/docs`: `API.md` "LMS" steps, `DATABASE.md` from "LMS outbox
(026)" on).

---

## 1. Who owns what

The LMS prototype fixes the boundary: *"CRM is authoritative for Admission and finance; the LMS shows read-only,
permitted summaries only. LMS owns curriculum, batches, actual Class Sessions, content, assignments, tests, attendance,
progress and published results. Certificates come from one LMS Certificate Register."*

| Area | Owner | The other system |
|---|---|---|
| Leads, deals, fees, invoices, payments, receipts, admissions, refunds, collections | **CRM** | LMS keeps a read-only projection (admission, finance summary) |
| Person identity and documents (ID proof, photo…) | **CRM** | LMS keeps one Student per CRM Person |
| LMS login, activation, sessions | **LMS** | CRM shows `lms_user_id`, `lms_status` |
| Curriculum versions, batches, trainers, allocation, joining date, class sessions, attendance, progress, completion | **LMS** (Modules 14, 15, 21) | CRM mirrors the columns it already has (enrolment / curriculum status, batches, allocations, joining date, completion) and the curriculum catalogue |
| Curriculum **mapping** of an admission | **Both** (round 3): the LMS maps automatically (a new admission, an activation), and a CRM coordinator can map an admission to the Active version (`AdmissionCurriculumMapped`) | The pull reports the result |
| Certificates | **LMS** Certificate Register (Module 22) | CRM `certificates` becomes a mirror |
| Placement (employers, openings, applications) | **CRM** (decided in round 2, §4) | LMS Career screen reads and submits through the CRM (later round) |
| Support | CRM `support_cases` for money / admission; LMS support requests for academic / LMS | Cross-link (§4) |

**One admission = one course.** The CRM creates one admission per course. A complimentary course is its own admission,
linked to the paid one (`complimentary_of_crm_admission_id`). Several courses bought together share one invoice, not
one admission. A combo is a single course whose tracks the LMS delivers separately.

## 2. The contract

### 2.1 CRM → LMS: events

`POST {LMS}/api/v1/integrations/crm/events` with header `X-Service-Key: <LMS CRM_SERVICE_KEY>`:

```json
{ "event_id": "uuid (unique, from the CRM outbox)", "event_type": "AdmissionQualified",
  "source_version": 7, "occurred_at": "2026-09-28T10:00:00+05:30", "data": { ... } }
```

- **Idempotent**: the same `event_id` returns the first result (200, `replayed: true`); the same `event_id` with a
  different payload is a 409.
- **Ordered by `source_version`** per record (course / admission / finance summary, each counted separately): a lower
  version than the one applied is stored as *Ignored — stale* and changes nothing, so retries and out-of-order delivery
  are safe.
- A failure (e.g. course not sent yet) is a 422, stored as *Failed*; sending the same event again retries it.
- IDs may be numbers; they are stored as text. The CRM's own names and values are accepted as they are: `phone`→`mobile`,
  `course_title`→`title`, `delivery_mode`→`mode`, `Online`→`Live Online`, `English` / `Telugu`→`en` / `te`. Money is a
  string with 2 decimals, dates are `YYYY-MM-DD`.

Send order on a first load: **branches → courses → admissions → finance** (branch finance snapshots any time after their branch); component courses before their combo; a paid admission
before its complimentary one.

| Event | Send when (CRM code path) | `data` — CRM column → field |
|---|---|---|
| `CourseUpserted` | Course Master create / update; combo components change (`courses`, `combo_courses`) | `course_code`, `course_title` (≤ 255), `category`, `is_combo`, `status` (Active / Inactive / Archived), `components[]` = `{component_course_code, is_bonus, sort_order}` (track codes are derived: `<combo>/T1…`, the bonus keeps its course code). **The event is the whole catalog row**: components it leaves out are removed, and a single course (`is_combo: false`) keeps none (its `components` are ignored). A component still used by enrolment tracks or curriculum versions is never removed: the event is refused with 422 and changes nothing — no title, no `is_combo`, no `source_version`. The message names the tracks and counts |
| `AdmissionQualified` | An admission is created: auto on `POST /payments/{id}/verify` and `/allocate`, manual `POST /admissions`, `POST /admissions/{id}/complimentary`. Not sent for cancelled admissions | `person`: `crm_person_id`, `person_code`, `full_name`, `phone`, `email` (optional), `name_te` (optional), `preferred_language` (English / Telugu). `admission`: `crm_admission_id`, `admission_code`, `course_code`, `original_branch_code`, `service_branch_code`, `collecting_branch_code` (the collecting branch of the admission's invoice; a complimentary admission uses its paid admission's invoice), `delivery_mode` (Classroom / Online / Hybrid), `seat_type`, `planned_start_date`, `admission_date`, `complimentary_of_crm_admission_id`, `access_until`. `enrolments` may be omitted (one course per admission). `person_id`, `admission_id` and `complimentary_of_admission_id` are accepted as aliases; the `crm_` name wins if both are sent |
| `AdmissionQualified` (full refresh) | `planned_start_date` changes, or the person's `full_name`, `phone`, `email` or `preferred_language` is edited. Sent with the next `source_version` | Same shape. The LMS updates the person and admission, never creates a second login or token, and never resets an enrolment that is already being served. A present `null` clears `email` or `name_te`; a key left out keeps its value; `full_name` is never cleared. The student's existing login keeps the email it was created with |
| `AdmissionUpdated` | `admission_transfers` insert (service branch), delivery mode change, pause / resume | `crm_admission_id`, `service_branch_code`, `delivery_mode`, `status` (Active / Paused). `status` is sent by the CRM's `POST /admissions/{id}/pause` and `/resume` (since round 2) |
| `AdmissionCancelled` | `POST /admissions/{id}/cancel` | `crm_admission_id`, `reason` (free text, no length limit). Withdraws only that admission's enrolments |
| `FinanceSummaryUpdated` | Payment recorded (pending verification), verified, failed, allocated; correction approved (reversal); fee change applied; refund decided (waiver); refund payout; invoice cancelled; instalment due date changed. Sent for **every admission on the invoice** | From `admission_balances` + `installment_dues` + verified `payments`: `crm_admission_id`, `fee_total` (final fee), `verified_paid`, `pending_verification`, `waived`, `refunded`, `balance` (outstanding; 0 for a cancelled admission), `payment_completion`, `invoice_numbers[]`, `installments[]` = `{installment_no, due_date, amount, covered, balance, due_position}`, `next_due_date`, `next_due_amount` (the first instalment that still has a balance; it may already be overdue), `receipts[]` = `{receipt_number, date, amount}` (verified, non-reversed payments; `amount` is the part allocated to this course; `date` is the payment date), `as_of`, `installments_scope` (`admission` default / `invoice`), `invoice_course_count` (int ≥ 0, default 1) |

| `BranchUpserted` | A branch's name, city or email edited (`PATCH /branches/{id}`), and `flask lms backfill --branches` (a full backfill sends branches first). Versioned per branch (`branch:<id>`) | `branch_code`, `branch_name`, `city`, `receipt_prefix` (→ LMS `short_code`, used inside batch codes), `email` (→ the branch's shared `mailbox`), `is_active`. A new branch needs `receipt_prefix` and `email`; an existing branch keeps its short code (a different one is a 422), and a `null` email keeps the mailbox. Other CRM columns (`address`, `phone`, …) are ignored |
| `BranchFinanceSnapshot` | A CRM job every 15 minutes, one per branch (`branch-finance:<id>`) | `branch_code`, `as_of`, `period` = `{label, start, end}`: the period the figures cover, always sent. It is the Approved target's period, or the current calendar month when the branch has no target, in which case both targets are `null`. A target without a period is a 422; `period: null` is still accepted, `collections` = `{verified, target}`, `paid_admissions` = `{count, target}`, `overdue` = `{amount, count, by_age_band[] = {band, amount, count}}` (from `installment_dues`), `verifications` = `{pending_count, pending_amount, overdue_count (past the verification SLA), oldest_at}`, `followups` = `{overdue_count, broken_promises}`. Each snapshot replaces the branch's previous one |
| `AdmissionCurriculumMapped` | A CRM Academic Coordinator (or admin) maps an admission to an Active LMS version. Versioned per admission (`curriculum:<crm_admission_id>`), in the admission's delivery queue | `crm_admission_id`, `admission_code` (logs), `course_code` (the admission's course), `track_code` (`null` = the course as a whole; a combo track), `curriculum_version_label`, `mapped_by_email`, `reason`. Applied to the enrolment (or track); *Curriculum Mapping Pending* moves to *Allocation Pending*. 422 `NOT_YET_APPLIED`: admission not arrived. 422 `BUSINESS_RULE`: label unknown or not Active, wrong course or track. 409: admission cancelled, enrolment Withdrawn / Completed, or a **change** while that course or track has an active allocation. Mapping the version already there confirms it (`changed: false`) |

**Instalments are per invoice.** With `installments_scope: "invoice"` every admission on the invoice carries the same
schedule and `next_due_*`. The LMS shows and sums the schedule once per invoice (`invoice_numbers[0]`), never per
admission; the per-course figures (`fee_total` … `balance`, `receipts`) stay per admission.

**Finance snapshot figures** follow the CRM dashboard's own rules: collections are verified payments by collecting
branch, net of reversals; paid Admissions are admissions whose first verified payment falls in the period, by original
branch; overdue is `installment_dues` past due, by collecting branch, in the CRM's seven age bands (`1–3 days` …
`91+ days`); verifications are payments in *Pending Verification*, overdue once past the `PAYMENT_VERIFICATION` task's
due time; follow-ups are leads past their next follow-up time plus *Broken* promises on invoices with a balance. The
LMS dashboards sum the branches in view: a figure is *Configured* when every branch has a snapshot, *Partial Data*
(naming the missing branches) when only some do, *Not Configured* when none do, never 0. A snapshot older than 60
minutes is flagged stale, and a target shows only when every branch in view has one for the same period.

Minimal `AdmissionQualified` `data` that is accepted:

```json
{
  "person": { "person_id": 148, "person_code": "PER-GNT-00148", "full_name": "Anvitha K.",
              "phone": "9876543210", "email": "anvitha@example.test", "preferred_language": "English" },
  "admission": { "admission_id": 1001, "admission_code": "NIT-GNT-2026-000001", "course_code": "NIT-CRS-047",
                 "original_branch_code": "NIT-GNT", "service_branch_code": "NIT-GNT", "collecting_branch_code": "NIT-GNT",
                 "delivery_mode": "Classroom", "admission_date": "2026-09-28" }
}
```

#### Responses

The body is `{"data": {"status": "Applied" | "Ignored — stale" | "Failed", "result": {...}, "replayed": bool,
"activation_token": ...}}`. The `AdmissionQualified` result carries `lms_user_id`, `lms_status` and the enrolment
status, and — once, for a new login only — `activation_token`. The token is a secret: never log it or store it in
plaintext (§4, activation link delivery).

| HTTP | Meaning | What the CRM worker does |
|---|---|---|
| 201 | Applied | Delivered |
| 200 | Same `event_id` already processed | Delivered |
| 400 | Payload failed validation (`error.details` lists the fields) | Failed + Super Admin task; the CRM fixes its mapping and resends the record as a **new** event |
| 401 | Missing or wrong service key | Stops the run; fix the config |
| 409 | `event_id` reused with a different payload | Failed + task (a CRM bug: a changed payload needs a new `event_id`) |
| 422 `NOT_YET_APPLIED` | A record it depends on hasn't arrived yet (course, branch, admission) | Stays Pending, retried with backoff (30 s doubling, capped at 1 h); Failed + task after 12 attempts |
| 422 other codes (`BUSINESS_RULE`) | Valid payload that the LMS refuses (component still in use, curriculum label unknown or not Active, …). `error.message` is written for staff | Retried for most events; `AdmissionCurriculumMapped` is *Refused* with the message |
| 5xx / timeout | LMS problem | Retried with backoff, same `event_id` |

### 2.2 LMS → CRM: what the CRM stores about the LMS

The CRM **pulls** `GET {LMS}/api/v1/integrations/crm/status?since=<ISO time>` (service key;
returns `persons[]`, `admissions[]`, `academics[]`, `batches[]`, `certificates[]`, `curriculum_versions[]` and `as_of`,
the next `since`). The same values are also written to the LMS `crm_outbox` in the transaction of each change
(undelivered rows for the same admission / batch superseded by the latest state), but nothing delivers it: the pull is
the transport. Rows written by the dev seed
(`seed_data`) are left out of the pull, because the CRM knows none of their IDs.

**Pull rules** (db 095):

- Each key filters on its row's own change time, set by the database: `persons` on the provisioning time,
  `admissions` on a stamp that moves with `lms_status` or last activity, `academics`, `batches` and `certificates` on
  their state's change time. The comparison is `> since`.
- Store `as_of` exactly as returned as the next `since`. It is held just below the oldest transaction still open, so a
  change committed during the pull is returned next time. A row can repeat; none is skipped. Apply idempotently.
- Every entry is the record's full current state. `academics[].allocations` is the admission's complete allocation
  history. There is no paging.
- Nothing reported is ever deleted (database triggers): a batch ends Cancelled / Completed, an allocation Moved /
  Withdrawn / Completed, a certificate version Superseded / Revoked, a curriculum version Retired (a deleted Draft comes
  back once as `status: Retired`, `lms_status: Deleted`).
- `curriculum_versions[]` (db 097) is the whole catalogue, seed curricula included (it is not student data).
- **Filter** (round 3): `&crm_admission_id=<id>` or `&crm_person_id=<id>` narrows every key to that admission's (or
  person's) records: its person, admissions, academics and certificates, the batches its allocations name, and its
  courses' curriculum versions. The answer echoes `"filter": {...}`. An unknown or seed admission gives empty lists.
- Not state: `admissions[].lms_last_synced_at` is the time of the pull, so a drift check must ignore it.

| CRM column | LMS source | Pull key / outbox event |
|---|---|---|
| `persons.lms_user_id`, `lms_provisioned_at` | Student ID (`students.student_code`, e.g. `NIT-STU-2026-004182`; stable, never reused), time the login was first created | `persons[]` / `LmsAccountProvisioned` |
| `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at` | `lms_status` (below); latest `activity_events.occurred_at` for the admission's enrolments; pull time | `admissions[]` / `AdmissionLmsStatusChanged` |
| `admissions.enrolment_status` | LMS enrolment status → Awaiting Batch Allocation / Scheduled / In Progress / Paused / Completed / Cancelled | `academics[]` / `AdmissionAcademicsChanged` |
| `admissions.curriculum_status`, `curriculum_version_id` | Mapped / Mapping Pending + `curriculum_version_label` | same |
| `batch_allocations` (batch, status, `joining_date`, `ended_at`, `end_reason`) | `allocations[]` = `{course_code, track_code, lms_course_id, crm_batch_id, status (Active / Moved / Withdrawn / Completed), joining_date, allocated_on, ended_on, end_reason}`. A combo has one per track: `track_code` is the LMS track (`null` for a single course), `course_code` its component course or the combo's own code, and `lms_course_id` a batch of the combo course | same |
| `admissions.academic_completed_at` | Enrolment completed time | same |
| `admissions.completion_authorised_by` | The Academic Coordinator who decided the completion review | `academics[].completion_authorised_by_email` |
| `batches` (+ `lms_course_id`) | `{lms_course_id = LMS batch_code, crm_batch_id, course_code, branch_code, delivery_mode, status (Planned / Open / In Progress / Completed / Cancelled), readiness (Ready / Pending Verification / Blocked), readiness_reason, capacity, seats_left, start_date, end_date, schedule_days ("Mon, Wed, Fri"), start_time / end_time ("HH:MM" IST), location (null for Online), curriculum_version_label, lead_trainer_email, trainer_emails}`. The timetable fields are null until the coordinator sets them ("timing not confirmed"). Sales may offer a Planned / Open batch that is not Blocked (db 098) | `batches[]` / `BatchUpserted` (+ `BatchLinked` when a CRM batch is linked) |
| `curriculum_versions` (CRM mirror) | Every version of every course: `{course_code, track_code (null for the course as a whole; <combo>/T1… or a booster's course code), version_label, status (Draft / Active / Retired), lms_status (Draft / Under Review / Approved / Active / Retired / Deleted), published_at}`. One Active version per course or track at a time | `curriculum_versions[]` |
| `certificates` | LMS Certificate Register: every numbered version when Issued, Superseded (by a reissue) or Revoked — `{certificate_number, certificate_type, version, status, crm_admission_id, crm_person_id, course_code, enrolment_code, holder_name, issue_date, issued_by_email, revoked_at, revoked_by_email, reason, supersedes_version, changed_at}` | `certificates[]` / `CertificateChanged` |

`lms_status`: **Not Created** — no LMS login yet; **Invited** — login created, not activated; **Active** — activated and
a course of the admission is running; **Inactive** — student suspended, or all its courses Paused / Withdrawn;
**Completed** — every non-withdrawn course Completed.

### 2.3 Vocabulary mapping (done in the LMS)

| Field | CRM | LMS |
|---|---|---|
| Delivery mode | Classroom, **Online**, Hybrid | Classroom, **Live Online**, Hybrid |
| Language | English, Telugu | en, te |
| Enrolment status | Awaiting Batch Allocation · Scheduled · In Progress · Deferred · Paused · Completed · Cancelled | Provisioning / Curriculum Mapping / Allocation Pending · Allocated — awaiting first regular class · Active · Paused · Completed · Withdrawn. *Deferred* has no LMS value: a deferral is a pause (`AdmissionUpdated` `status: Paused`) |
| Batch status | Planned · Open · In Progress · Completed · Cancelled | Forming · Starting · Running · Full · Completed · Cancelled |
| Allocation status | Active · Moved · Withdrawn · Completed | Active · Transferred · Ended |
| Codes | Admission `NIT-GNT-2026-000001`, person `PER-GNT-00148`, batch `GNT-B-0001`, receipt `GNT-R-2627-00001` | Student `NIT-STU-2026-004182`, batch `NIT-GNT-BAT-2026-000001` (the CRM's `lms_course_id`) |

---

## 3. How each side runs it

### 3.1 CRM

- **Outbox and worker** (CRM db 026, 029, 030). Every change writes its event in the same transaction; a trigger makes
  a written envelope immutable, so a retry is byte-for-byte the same request. Records are versioned per key (`course:`,
  `admission:`, `finance:`, `branch:`, `branch-finance:`, `curriculum:`). An admission's events share one queue, so its
  finance or mapping never overtakes its `AdmissionQualified`.
- **Delivery.** Pushed in a background thread right after the request commits (3 s timeout); the worker
  (`flask lms worker`, cron every minute on a server) retries every 10 s with backoff (§2.1 responses). Events held back
  because the LMS was unreachable are released as soon as `GET /api/v1/health` answers 200, so health stays
  unauthenticated and to one cheap query (`tests/test_health.py`).
- **Pull** about once a minute (`lms-status-pull`, watermark in `lms_pull_state`), applied in the order batches →
  persons → admissions → academics → certificates → curriculum versions, one transaction per record. A record that
  can't be applied yet (unknown batch, course, branch) is held and retried on every pull. LMS-confirmed facts bypass the
  CRM's own validation triggers (`SET LOCAL app.sync_source = 'LMS'`).
- **Mirrors.** `lms_user_id` / `lms_status`, academics with one allocation row per track, batches (trainer and
  authoriser emails stored as text when no CRM user matches), certificates (with *Superseded*), the curriculum catalogue.
  The CRM's academic screens are read-only (409 `MANAGED_IN_LMS`); `PATCH /admissions` refuses `lms_status`.
- **What the CRM still writes:** admissions, persons, money, branches, finance snapshots, pause / resume, and curriculum
  mapping of an admission (to the Active version, never once allocated).
- **Tools:** `flask lms backfill [--branches] [--admission ID --force]`, `deliver`, `outbox --failed`, `requeue`,
  `pull [--full]`, `refresh <admission>`, `reconcile [--admission ID] [--fix]` (also a daily drift job), `holds`.
- `activation_token` is never logged or stored; the CRM keeps only `activation_token_issued` on the outbox row.

### 3.2 LMS

- Every event is stored in `crm_events` (Super Admin → **CRM sync**, `/admin/crm-sync`, with retry). Rules in §2.1.
- **Auto-mapping stays on** (round 3): a new admission gets its course's Active curriculum version, and activating a
  version moves every enrolment still waiting onto it. Only one version per course or track can be Active, so the
  CRM's mapping and the LMS's never disagree; a CRM mapping confirms it, or moves an unallocated admission off a
  retired version.
- **Jobs** (`flask jobs run`): `allocation-escalation` raises an enrolment still without a batch 24 hours before its
  admission's planned start to the service branch's Branch Managers (it replaced the CRM's `batch-allocation` job).
- **Rules the CRM relies on:** nothing pulled is ever deleted; a Blocked batch is not offered for sale; the LMS sends no
  promotional messages (in-app service notifications only), so the CRM's "stop contact" stays CRM-only.
- **Staff** use the same email in both systems: the pull names trainers and completion authorisers by email.

---

## 4. Open items

| Item | Notes |
|---|---|
| Activation link delivery | Decided (D1): coordinators reissue links in the LMS ("Activation link from: CRM provisioning" filter on Student Accounts) until the CRM can send WhatsApp / email; then the CRM delivers `{LMS}/activate?token=…`, storing the token encrypted until sent. No LMS change needed |
| Placement | Decided (D5): the CRM owns employers, openings and applications. The LMS Career screen will read approved openings and submit applications / CVs through new CRM service endpoints. Later round |
| Support cross-link | CRM `support_cases` (money, admission) and LMS support requests (academic, LMS) stay separate; a request that belongs to the other side should be routed with both references stored. Not designed yet |
| Staff accounts | Same email in both systems today; single sign-on or provisioning from the CRM later |
| Course fee and branches | `CourseUpserted` carries neither the standard fee nor the branches offering a course; ask the CRM if the LMS needs them |
| Real data | Everything runs on dev databases only. Never point it at real student data until the service key, transport and retention are agreed |

---

## 5. Integration rounds

Each round is a brief from the CRM, an LMS reply and a joint test, exchanged as files in `nipuna crm-docs/` (both sides
drop them there; they are deleted once the round is recorded here, and stay in git history). Local only: CRM
`nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

| Round | Date | What changed |
|---|---|---|
| 1 | 1 Oct 2026 | First live CRM → LMS run: backfill of 8 courses, 10 admissions and finance, all 30 events Applied. LMS fixes F1–F10 (db 090): the CRM's catalogue and codes in the seed, `CourseUpserted` reconciles components, instalments per invoice, CRM ID aliases, longer titles, seed rows left out of the pull, the "Activation link from" filter |
| 2 | 1 Oct 2026 | The CRM applies the pull and becomes a read-only mirror of academics, batches and certificates. LMS (db 095): a gap-free `as_of`, one change stamp per admission, nothing pulled ever deleted, `track_code` on allocations, the `allocation-escalation` job. Owner decisions D1–D5 (§4); `BranchUpserted` and `BranchFinanceSnapshot` built on both sides (db 096) |
| 3 | 2–3 Oct 2026 | Curriculum mapping writable from the CRM; the CRM pushes after commit and pulls every minute. LMS (db 097): `curriculum_versions[]`, `AdmissionCurriculumMapped`, `NOT_YET_APPLIED`, the pull filter. For the CRM's sales playbook (db 098): batch timetable, `readiness` and `seats_left` in `batches[]`. Joint tests all passed, including an LMS outage |

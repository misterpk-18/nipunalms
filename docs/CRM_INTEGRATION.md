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
| Course outline (modules, topics, hours, completion rules; no versions), batches, trainers, allocation, joining date, class sessions, attendance, progress, completion | **LMS** (Modules 14, 15, 21) | CRM mirrors the columns it still has (enrolment status, batches, allocations, joining date, completion); it holds no curriculum (round 5) |
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
- **Historical imports**: an optional envelope flag `"historical": true` marks a backfill or re-import. Such an event —
  or any event whose `occurred_at` is older than `crm_notify_max_age_hours` (72) — is applied with its original dates but
  sends no current notices to LMS staff (Module 27 §6). Use it when re-sending old admissions.
- IDs may be numbers; they are stored as text. The CRM's own names and values are accepted as they are: `phone`→`mobile`,
  `course_title`→`title`, `delivery_mode`→`mode`, `Online`→`Live Online`, `English` / `Telugu`→`en` / `te`. Money is a
  string with 2 decimals, dates are `YYYY-MM-DD`.

Send order on a first load: **branches → courses → admissions → finance** (branch finance snapshots any time after their branch); component courses before their combo; a paid admission
before its complimentary one.

| Event | Send when (CRM code path) | `data` — CRM column → field |
|---|---|---|
| `CourseUpserted` | Course Master create / update; combo components change (`courses`, `combo_courses`) | `course_code`, `course_title` (≤ 255), `category`, `is_combo`, `status` (Active / Inactive / Archived), `components[]` = `{component_course_code, is_bonus, sort_order}` (track codes are derived: `<combo>/T1…`, the bonus keeps its course code). **The event is the whole catalog row**: components it leaves out are removed, and a single course (`is_combo: false`) keeps none (its `components` are ignored). A component still used by enrolment tracks or outline modules is never removed (no curriculum version is needed for a course to be upserted or an admission applied): the event is refused with 422 and changes nothing — no title, no `is_combo`, no `source_version`. The message names the tracks and counts |
| `AdmissionQualified` | An admission is created: auto on `POST /payments/{id}/verify` and `/allocate`, manual `POST /admissions`, `POST /admissions/{id}/complimentary`. Not sent for cancelled admissions | `person`: `crm_person_id`, `person_code`, `full_name`, `phone`, `email` (optional), `name_te` (optional), `preferred_language` (English / Telugu). `admission`: `crm_admission_id`, `admission_code`, `course_code`, `original_branch_code`, `service_branch_code`, `collecting_branch_code` (the collecting branch of the admission's invoice; a complimentary admission uses its paid admission's invoice), `delivery_mode` (Classroom / Online / Hybrid), `seat_type`, `planned_start_date`, `admission_date`, `complimentary_of_crm_admission_id`, `access_until`, `preferred_batch_code` (optional, db 116: the counsellor's preferred LMS batch; a preference only, never refused: a code that names no batch of the course at the service branch is returned in `result.warnings`; omitted = no preference). `enrolments` may be omitted (one course per admission). `person_id`, `admission_id` and `complimentary_of_admission_id` are accepted as aliases; the `crm_` name wins if both are sent |
| `AdmissionQualified` (full refresh) | `planned_start_date` changes, or the person's `full_name`, `phone`, `email` or `preferred_language` is edited. Sent with the next `source_version` | Same shape. The LMS updates the person and admission, never creates a second login or token, and never resets an enrolment that is already being served. A present `null` clears `email` or `name_te`; a key left out keeps its value; `full_name` is never cleared. The student's existing login keeps the email it was created with |
| `AdmissionUpdated` | `admission_transfers` insert (service branch), delivery mode change, pause / resume | `crm_admission_id`, `service_branch_code`, `delivery_mode`, `status` (Active / Paused). `status` is sent by the CRM's `POST /admissions/{id}/pause` and `/resume` (since round 2). A service branch change ends the seats and moves certificate entries not yet issued to the new branch |
| `AdmissionCancelled` | `POST /admissions/{id}/cancel` | `crm_admission_id`, `reason` (free text, no length limit). Withdraws only that admission's enrolments |
| `FinanceSummaryUpdated` | Payment recorded (pending verification), verified, failed, allocated; correction approved (reversal); fee change applied; refund decided (waiver); refund payout; invoice cancelled; instalment due date changed. Sent for **every admission on the invoice** | From `admission_balances` + `installment_dues` + verified `payments`: `crm_admission_id`, `fee_total` (final fee), `verified_paid`, `pending_verification`, `waived`, `refunded`, `balance` (outstanding; 0 for a cancelled admission), `payment_completion`, `invoice_numbers[]`, `installments[]` = `{installment_no, due_date, amount, covered, balance, due_position}`, `next_due_date`, `next_due_amount` (the first instalment that still has a balance; it may already be overdue), `receipts[]` = `{receipt_number, date, amount}` (verified, non-reversed payments; `amount` is the part allocated to this course; `date` is the payment date), `as_of`, `installments_scope` (`admission` default / `invoice`), `invoice_course_count` (int ≥ 0, default 1) |

| `BranchUpserted` | A branch's name, city or email edited (`PATCH /branches/{id}`), and `flask lms backfill --branches` (a full backfill sends branches first). Versioned per branch (`branch:<id>`) | `branch_code`, `branch_name`, `city`, `receipt_prefix` (→ LMS `short_code`, used inside batch codes), `email` (→ the branch's shared `mailbox`), `is_active`. A new branch needs `receipt_prefix` and `email`; an existing branch keeps its short code (a different one is a 422), and a `null` email keeps the mailbox. Other CRM columns (`address`, `phone`, …) are ignored |
| `BranchFinanceSnapshot` | A CRM job every 15 minutes, one per branch (`branch-finance:<id>`) | `branch_code`, `as_of`, `period` = `{label, start, end}`: the period the figures cover, always sent. It is the Approved target's period, or the current calendar month when the branch has no target, in which case both targets are `null`. A target without a period is a 422; `period: null` is still accepted, `collections` = `{verified, target}`, `paid_admissions` = `{count, target}`, `overdue` = `{amount, count, by_age_band[] = {band, amount, count}}` (from `installment_dues`), `verifications` = `{pending_count, pending_amount, overdue_count (past the verification SLA), oldest_at}`, `followups` = `{overdue_count, broken_promises}`. Each snapshot replaces the branch's previous one |

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
| 422 other codes (`BUSINESS_RULE`) | Valid payload that the LMS refuses (component still in use, …). `error.message` is written for staff | Retried for most events |
| 5xx / timeout | LMS problem | Retried with backoff, same `event_id` |

### 2.2 LMS → CRM: what the CRM stores about the LMS

The CRM **pulls** `GET {LMS}/api/v1/integrations/crm/status?since=<ISO time>` (service key;
returns `persons[]`, `admissions[]`, `academics[]`, `batches[]`, `certificates[]` and `as_of`,
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
  Withdrawn / Completed, a certificate version Superseded / Revoked.
- **Filter** (round 3): `&crm_admission_id=<id>` or `&crm_person_id=<id>` narrows every key to that admission's (or
  person's) records: its person, admissions, academics and certificates, and the batches its allocations name. The
  answer echoes `"filter": {...}`. An unknown or seed admission gives empty lists.
- Not state: `admissions[].lms_last_synced_at` is the time of the pull, so a drift check must ignore it.

| CRM column | LMS source | Pull key / outbox event |
|---|---|---|
| `persons.lms_user_id`, `lms_provisioned_at` | Student ID (`students.student_code`, e.g. `NIT-STU-2026-004182`; stable, never reused), time the login was first created | `persons[]` / `LmsAccountProvisioned` |
| `persons.lms_activated_at` | When the student first set their own password (activation link used); null until then. The CRM's `nipuna_lms_account_activated_u_v1` waits for this, not for `lms_provisioned_at`, when the LMS sends the activation link (db 122) | `persons[]` |
| `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at` | `lms_status` (below); latest `activity_events.occurred_at` for the admission's enrolments; pull time | `admissions[]` / `AdmissionLmsStatusChanged` |
| `admissions.enrolment_status` | LMS enrolment status → Awaiting Batch Allocation / Scheduled / In Progress / Paused / Completed / Cancelled | `academics[]` / `AdmissionAcademicsChanged` |
| `batch_allocations` (batch, status, `joining_date`, `ended_at`, `end_reason`) | `allocations[]` = `{course_code, track_code, lms_course_id, crm_batch_id, status (Active / Moved / Withdrawn / Completed), joining_date, allocated_on, ended_on, end_reason}`. A combo has one per track: `track_code` is the LMS track (`null` for a single course), `course_code` its component course or the combo's own code, and `lms_course_id` a batch of the combo course. `end_reason` holds the allocation's reason while `status` is `Active`; read it as an ending reason only otherwise | same |
| `admissions.academic_completed_at` | Enrolment completed time | same |
| `admissions.completion_authorised_by` | The Branch Manager who decided the completion review (UX phase U2: the LMS merged the Academic Coordinator role into the Branch Manager, so this email now matches a CRM Branch Manager) | `academics[].completion_authorised_by_email` |
| `batches` (+ `lms_course_id`) | `{lms_course_id = LMS batch_code, crm_batch_id, course_code, branch_code, delivery_mode, status (Planned / Proposed / Open / In Progress / On Hold / Completed / Cancelled / Archived; the new three since db 103, round 4 request A5), readiness (Ready / Pending Verification / Blocked), readiness_reason, capacity, seats_left, start_date, end_date, schedule_days ("Mon, Wed, Fri"), start_time / end_time ("HH:MM" IST), location (null for Online), lead_trainer_email, trainer_emails}`. The timetable fields are null until the Branch Manager sets them ("timing not confirmed"). Sales may offer a Planned / Open batch that is not Blocked (db 098) | `batches[]` / `BatchUpserted` (+ `BatchLinked` when a CRM batch is linked) |
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
| Batch status | Planned · Proposed · Open · In Progress · On Hold · Completed · Cancelled · Archived | Forming · Proposed · Starting · Running · Full · On Hold · Completed · Cancelled · Archived (shown as Draft · Proposed · Confirmed · In Progress …) |
| Allocation status | Active · Moved · Withdrawn · Completed | Active · Transferred · Ended |
| Codes | Admission `NIT-GNT-2026-000001`, person `PER-GNT-00148`, batch `GNT-B-0001`, receipt `GNT-R-2627-00001` | Student `NIT-STU-2026-004182`, batch `NIT-GNT-BAT-2026-000001` (the CRM's `lms_course_id`) |

---

## 3. How each side runs it

### 3.1 CRM

- **Outbox and worker** (CRM db 026, 029, 030). Every change writes its event in the same transaction; a trigger makes
  a written envelope immutable, so a retry is byte-for-byte the same request. Records are versioned per key (`course:`,
  `admission:`, `finance:`, `branch:`, `branch-finance:`). An admission's events share one queue, so its
  finance never overtakes its `AdmissionQualified`.
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
- **The outline is the LMS's alone** (round 5, db 104; course outlines, role separation R6, db 121): there are no curriculum
  versions. Modules and topics hang off the course; a new admission needs nothing from them when `AdmissionQualified` is applied
  (a combo enrolment gets one track per component) and a student follows the outline of their course as the LMS holds it.
  Allocation never waits on the CRM, nor on an outline (UX phase U1, db 105): its rules are the batch allocation review (service
  branch, course or track, a seat left), and an admission leaves *Awaiting Batch Allocation* as soon as a seat is given.
  `CourseUpserted` still owns `course_code`, `title`, `category`, `status` and the tracks and never touches the outline, hours or
  completion rules (only the Super Admin and Founder edit those in the LMS); a course the CRM removes a track from is refused
  while enrolments or outline modules still use that track. The CRM no longer sends `AdmissionCurriculumMapped` (a 400 now)
  and the pull carries no `curriculum_versions[]`, `curriculum_status` or `curriculum_version_label`. **No CRM contract change in R6.**
- **Jobs** (`flask jobs run`): `allocation-escalation` raises an enrolment still without a batch 24 hours before its
  admission's planned start to the service branch's Branch Managers (it replaced the CRM's `batch-allocation` job).
- **WhatsApp (round 6, db 107; verified end to end 18 Oct 2026):** the LMS never calls Pinbot. It queues each message in
  `whatsapp_outbox` along with the change that caused it. After the commit, the `whatsapp-send` job posts it to the CRM's
  `POST /lms/whatsapp` (W4), and the CRM applies its own switch, test numbers, consent and backoff. There are nine LMS templates
  (`services/whatsapp_templates.py`). A timeout is never resent, and a message older than 48 hours is skipped.
  A sign-in code or link is wiped from the row once it is handed over. The normal first answer is `Queued`. What happens next
  arrives as `WhatsappStatusUpdated` events (Sent / Delivered / Read / Failed / Skipped, versioned per dedupe key), which the LMS
  applies from db 110; an unknown key or an older version is answered 200. The CRM sends them with
  `LMS_WHATSAPP_STATUS_EVENTS=1` (on in dev). The code ships switched off. In `nipunalms-dev` it is on, with all nine templates
  approved and `CRM_BASE_URL` set, ahead of Pinbot's approval; until then each message ends `Failed` with Pinbot's
  `#132001`. See [API.md §4.13](API.md).
- **Who sends which message (round 8).** No student gets the same event twice:

  | Sender | Messages | Trigger |
  |---|---|---|
  | CRM | `nipuna_batch_allocated_u_v1` | Each new `Active` allocation in the pull: the first batch and every move to another batch (the LMS sends nothing on a move). Deduped per allocation; a timetable change sends nothing |
  | CRM | `nipuna_lms_account_activated_u_v1` | The first non-null `persons[].lms_activated_at` (db 122), so it comes after the LMS's activation link, never before |
  | CRM | `nipuna_lms_course_access_delayed_u_v1` | An LMS event about the admission failed for good |
  | LMS, through the CRM | The nine `nipuna_lms_*` templates: reset code, activation link, staff invite, class reminder, cancelled, rescheduled, result, certificate, batch-change agreement | The LMS change that causes each one |

- **Batches and allocation are the LMS's alone** (round 8). A Branch Manager creates batches and allocates on **Waiting for a
  batch**; the CRM has no allocate action and learns the result from the pull. A batch made in the LMS has no `crm_batch_id`, so a
  `crm_batch_id` in `AdmissionQualified` or `AdmissionUpdated` allocates nobody. For dev, `flask seed-crm-batches` creates the
  batches for the CRM's students ([DEVELOPMENT.md](DEVELOPMENT.md#batches-for-the-crms-own-students)).
- **Rules the CRM relies on:** nothing pulled is ever deleted; a Blocked batch is not offered for sale; the LMS sends no
  promotional messages (service and learning messages only), so the CRM's "stop contact" stays CRM-only.
- **Staff** use the same email in both systems: the pull names trainers and completion authorisers by email.

---

## 4. Open items

| Item | Notes |
|---|---|
| Activation link delivery | **The LMS sends it** (answer to W2, round 6): template `nipuna_lms_student_activation_link_u_v1` through the CRM's `POST /lms/whatsapp`, wired in UX phase U7 and handed to the CRM since 18 Oct 2026; it reaches the phone once Pinbot approves the template. Until then Branch Managers reissue and copy links in the LMS ("Activation link from: CRM provisioning" filter on Student Accounts) |
| Placement | Decided (D5): the CRM owns employers, openings and applications. The LMS Career screen will read approved openings and submit applications / CVs through new CRM service endpoints. Later round |
| Support cross-link | CRM `support_cases` (money, admission) and LMS support requests (academic, LMS) stay separate; a request that belongs to the other side should be routed with both references stored. Not designed yet |
| Staff accounts | Same email in both systems today; single sign-on or provisioning from the CRM later |
| Course fee and branches | `CourseUpserted` carries neither the standard fee nor the branches offering a course; ask the CRM if the LMS needs them |
| Round 4 request | Written 3 Oct 2026 in `nipuna crm-docs/LMS_ROUND4_REQUEST.md`: date of birth and guardians in `AdmissionQualified`, a `PersonRestrictionsUpdated` event (channel opt-outs, consents), cancellation and refund detail, placement endpoints (D5), and the new batch states coming in gap fix phase 6. Also tells the CRM about the `historical` flag, the certificate fee gate and reinstatement (Revoked → Issued). Waiting for the CRM |
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
| 5 | 10 Oct 2026 | The CRM holds no curriculum. LMS (db 104): `AdmissionCurriculumMapped` and its handler removed (`NOT_YET_APPLIED` stays for branch, course and admission events), `curriculum_versions[]` and the curriculum fields on `academics[]` / `batches[]` dropped from the pull and the outbox, `curriculum_version_crm_state` and `admissions.curriculum_source_version` dropped. Reply: `LMS_CURRICULUM_REMOVAL_REPLY.md`. Joint tests T1–T5 all passed on 10 Oct 2026 (migration 104 applied in place, course `NIT-CRS-047`): CRM-created admission auto-mapped to CV 5.1, allocated with no CRM mapping, pull has no curriculum keys, reconcile drift 0. One finding, not from this change: an earlier LMS dev rebuild re-issued student codes that CRM persons still held, so 3 person records were held on a duplicate `lms_user_id` until the CRM cleared 12 stale ids. See `docs/DEVELOPMENT.md` before rebuilding |
| 6 | 10–18 Oct 2026 | WhatsApp through the CRM (W1–W4 of `CRM_WHATSAPP_CONNECTION.md`). LMS (db 107, built, switched off): `whatsapp_outbox`, the `whatsapp-send` and `class-reminders` jobs, nine templates, triggers for class reminder / cancelled / rescheduled, result published, certificate issued and batch change. Reply: `LMS_WHATSAPP_REPLY.md` in the CRM's `nipuna lms-docs/` (W1 the nine templates, W2 the LMS sends activation links, W3 yes to status, W4 yes: the CRM builds `POST /lms/whatsapp`). The CRM built `POST /lms/whatsapp` and the status events (db 110). Verified end to end on 18 Oct 2026: LMS row 133 handed over `Queued` and came back `Failed` with Pinbot's `#132001` (template not approved yet) through a `WhatsappStatusUpdated` event, Applied. Only the owner's Pinbot approvals are left |
| 7 | 17 Oct 2026 | Preferred batch (D19): `AdmissionQualified.admission.preferred_batch_code` is stored (db 116) as a preference only, never refused; a code that names no batch of the course at the service branch comes back as a warning. Waiting for a batch marks the matching batch "Preferred by counsellor"; the Branch Manager still allocates. The CRM's "Open in LMS" link (`/academic/batches?crm_admission_id=…&student=<student code>`) now opens Waiting for a batch on that student. D17 (readiness) and D13 (instalments) answered in `LMS_ROUND7_REPLY.md`. Reply in `nipuna crm-docs/LMS_ROUND7_REPLY.md` |
| 8 | 18 Oct 2026 | Batches, allocation and WhatsApp (the CRM's `CRM_BATCH_WHATSAPP_ALIGNMENT.md`, Q1–Q10). Agreed: batches and allocation are LMS-only, and the pull shows every non-seed batch whatever its readiness. Fixed an overlap: the CRM's "account activated" message fired on `lms_provisioned_at`, before the student had used the LMS's activation link. LMS (db 122) adds `persons[].lms_activated_at`, and the CRM now triggers on it. The CRM sends `batch_allocated` for every new allocation, moves included. LMS dev tooling: `flask seed-crm-batches` (11 batches for the CRM's students) and `flask jobs run --loop`. Joint test: admission 18 allocated by `bm.gnt` to `NIT-GNT-BAT-2026-000004`, pulled, and `batch_allocated` sent to the test number (Sent). The CRM cleared its 63 held E2E rows. Dev sends only to `+919392329248`. Replies `LMS_BATCH_WHATSAPP_REPLY.md`, `LMS_ADMISSION_18_ALLOCATED.md`, `LMS_ACTIVATION_LINK_SENT.md` and `LMS_LOCAL_RUNNING.md` in the CRM's `nipuna lms-docs/`. Open: the `lms_account_activated` test, once Pinbot approves the templates |

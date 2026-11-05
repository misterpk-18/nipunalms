# Nipuna LMS — Integrations

How the LMS connects to the systems around it.

| Part | What it covers |
|---|---|
| [A — CRM](#part-a--crm) | Who owns what, the event and pull contract, how each side runs it, open items, the integration rounds |
| [B — Google Workspace](#part-b--google-workspace) | Meet links on Calendar events, Drive folders and batch groups, Gmail, the sync job, configuration |
| [C — WhatsApp templates](#part-c--whatsapp-templates) | The Meta template forms: the approved password-reset code, and the two to resubmit |

The other docs: [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) · [API.md](API.md) · [DATABASE.md](DATABASE.md) · [DEVELOPMENT.md](DEVELOPMENT.md).
How to run the LMS and the CRM together on one laptop is in [DEVELOPMENT.md Part C](DEVELOPMENT.md#part-c--running-with-the-local-crm).
The CRM's side is documented in its own repo (`nipuna-crm/docs`: `API.md` "LMS" steps, `DATABASE.md` from "LMS outbox (026)" on).
WhatsApp messages go out through the CRM (Part A §2, round 6); their templates are in Part C.

---

## Part A — CRM

How the LMS and the CRM (`nipuna-crm`) are connected: who owns what (§1), the wire contract (§2), how each side runs it
(§3), what is still open (§4) and the history of the integration rounds (§5).

### 1. Who owns what

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

### 2. The contract

#### 2.1 CRM → LMS: events

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

##### Responses

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

#### 2.2 LMS → CRM: what the CRM stores about the LMS

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

#### 2.3 Vocabulary mapping (done in the LMS)

| Field | CRM | LMS |
|---|---|---|
| Delivery mode | Classroom, **Online**, Hybrid | Classroom, **Live Online**, Hybrid |
| Language | English, Telugu | en, te |
| Enrolment status | Awaiting Batch Allocation · Scheduled · In Progress · Deferred · Paused · Completed · Cancelled | Provisioning / Curriculum Mapping / Allocation Pending · Allocated — awaiting first regular class · Active · Paused · Completed · Withdrawn. *Deferred* has no LMS value: a deferral is a pause (`AdmissionUpdated` `status: Paused`) |
| Batch status | Planned · Proposed · Open · In Progress · On Hold · Completed · Cancelled · Archived | Forming · Proposed · Starting · Running · Full · On Hold · Completed · Cancelled · Archived (shown as Draft · Proposed · Confirmed · In Progress …) |
| Allocation status | Active · Moved · Withdrawn · Completed | Active · Transferred · Ended |
| Codes | Admission `NIT-GNT-2026-000001`, person `PER-GNT-00148`, batch `GNT-B-0001`, receipt `GNT-R-2627-00001` | Student `NIT-STU-2026-004182`, batch `NIT-GNT-BAT-2026-000001` (the CRM's `lms_course_id`) |

---

### 3. How each side runs it

#### 3.1 CRM

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

#### 3.2 LMS

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

### 4. Open items

| Item | Notes |
|---|---|
| Activation link delivery | **The LMS sends it** (answer to W2, round 6): template `nipuna_lms_student_activation_link_u_v1` through the CRM's `POST /lms/whatsapp`, wired in UX phase U7 and handed to the CRM since 18 Oct 2026; it reaches the phone once Pinbot approves the template. Until then Branch Managers reissue and copy links in the LMS ("Activation link from: CRM provisioning" filter on Student Accounts) |
| Placement | Decided (D5): the CRM owns employers, openings and applications. The LMS Career screen will read approved openings and submit applications / CVs through new CRM service endpoints. Later round |
| Support cross-link | CRM `support_cases` (money, admission) and LMS support requests (academic, LMS) stay separate; a request that belongs to the other side should be routed with both references stored. Not designed yet |
| Staff accounts | Same email in both systems today; single sign-on or provisioning from the CRM later |
| Course fee and branches | `CourseUpserted` carries neither the standard fee nor the branches offering a course; ask the CRM if the LMS needs them |
| Round 4 request | Sent 3 Oct 2026 (`LMS_ROUND4_REQUEST.md`): date of birth and guardians in `AdmissionQualified`, a `PersonRestrictionsUpdated` event (channel opt-outs, consents), cancellation and refund detail, placement endpoints (D5), and the new batch states coming in gap fix phase 6. Also tells the CRM about the `historical` flag, the certificate fee gate and reinstatement (Revoked → Issued). Waiting for the CRM |
| Real data | Everything runs on dev databases only. Never point it at real student data until the service key, transport and retention are agreed. **Agreed on 28 Oct 2026:** https (production LMS and CRM), the service key handed over in person, and CRM event payloads kept for 1 year: the job `crm-payload-purge` then empties the payload of applied and stale events (the record, type, version and result stay; failed events keep theirs for a retry). A deletion or erasure request is handled by hand, with no new event type |

---

### 5. Integration rounds

Each round is a brief from the CRM, an LMS reply and a joint test, exchanged as notes in `nipuna crm-docs/` (LMS) and the
CRM's `nipuna lms-docs/`; the notes are deleted once the round is recorded here. Local only: CRM
`nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

| Round | Date | What changed |
|---|---|---|
| 1 | 1 Oct 2026 | First live CRM → LMS run: backfill of 8 courses, 10 admissions and finance, all 30 events Applied. LMS fixes F1–F10 (db 090): the CRM's catalogue and codes in the seed, `CourseUpserted` reconciles components, instalments per invoice, CRM ID aliases, longer titles, seed rows left out of the pull, the "Activation link from" filter |
| 2 | 1 Oct 2026 | The CRM applies the pull and becomes a read-only mirror of academics, batches and certificates. LMS (db 095): a gap-free `as_of`, one change stamp per admission, nothing pulled ever deleted, `track_code` on allocations, the `allocation-escalation` job. Owner decisions D1–D5 (§4); `BranchUpserted` and `BranchFinanceSnapshot` built on both sides (db 096) |
| 3 | 2–3 Oct 2026 | Curriculum mapping writable from the CRM; the CRM pushes after commit and pulls every minute. LMS (db 097): `curriculum_versions[]`, `AdmissionCurriculumMapped`, `NOT_YET_APPLIED`, the pull filter. For the CRM's sales playbook (db 098): batch timetable, `readiness` and `seats_left` in `batches[]`. Joint tests all passed, including an LMS outage |
| 5 | 10 Oct 2026 | The CRM holds no curriculum. LMS (db 104): `AdmissionCurriculumMapped` and its handler removed (`NOT_YET_APPLIED` stays for branch, course and admission events), `curriculum_versions[]` and the curriculum fields on `academics[]` / `batches[]` dropped from the pull and the outbox, `curriculum_version_crm_state` and `admissions.curriculum_source_version` dropped. Reply: `LMS_CURRICULUM_REMOVAL_REPLY.md`. Joint tests T1–T5 all passed on 10 Oct 2026 (migration 104 applied in place, course `NIT-CRS-047`): CRM-created admission auto-mapped to CV 5.1, allocated with no CRM mapping, pull has no curriculum keys, reconcile drift 0. One finding, not from this change: an earlier LMS dev rebuild re-issued student codes that CRM persons still held, so 3 person records were held on a duplicate `lms_user_id` until the CRM cleared 12 stale ids. See `docs/DEVELOPMENT.md` before rebuilding |
| 6 | 10–18 Oct 2026 | WhatsApp through the CRM (W1–W4 of `CRM_WHATSAPP_CONNECTION.md`). LMS (db 107, built, switched off): `whatsapp_outbox`, the `whatsapp-send` and `class-reminders` jobs, nine templates, triggers for class reminder / cancelled / rescheduled, result published, certificate issued and batch change. Reply: `LMS_WHATSAPP_REPLY.md` in the CRM's `nipuna lms-docs/` (W1 the nine templates, W2 the LMS sends activation links, W3 yes to status, W4 yes: the CRM builds `POST /lms/whatsapp`). The CRM built `POST /lms/whatsapp` and the status events (db 110). Verified end to end on 18 Oct 2026: LMS row 133 handed over `Queued` and came back `Failed` with Pinbot's `#132001` (template not approved yet) through a `WhatsappStatusUpdated` event, Applied. Only the owner's Pinbot approvals are left |
| 7 | 17 Oct 2026 | Preferred batch (D19): `AdmissionQualified.admission.preferred_batch_code` is stored (db 116) as a preference only, never refused; a code that names no batch of the course at the service branch comes back as a warning. Waiting for a batch marks the matching batch "Preferred by counsellor"; the Branch Manager still allocates. The CRM's "Open in LMS" link (`/academic/batches?crm_admission_id=…&student=<student code>`) now opens Waiting for a batch on that student. D17 (readiness) and D13 (instalments) answered in `LMS_ROUND7_REPLY.md`. |
| 8 | 18 Oct 2026 | Batches, allocation and WhatsApp (the CRM's `CRM_BATCH_WHATSAPP_ALIGNMENT.md`, Q1–Q10). Agreed: batches and allocation are LMS-only, and the pull shows every non-seed batch whatever its readiness. Fixed an overlap: the CRM's "account activated" message fired on `lms_provisioned_at`, before the student had used the LMS's activation link. LMS (db 122) adds `persons[].lms_activated_at`, and the CRM now triggers on it. The CRM sends `batch_allocated` for every new allocation, moves included. LMS dev tooling: `flask seed-crm-batches` (11 batches for the CRM's students) and `flask jobs run --loop`. Joint test: admission 18 allocated by `bm.gnt` to `NIT-GNT-BAT-2026-000004`, pulled, and `batch_allocated` sent to the test number (Sent). The CRM cleared its 63 held E2E rows. Dev sends only to `+919392329248`. Replies `LMS_BATCH_WHATSAPP_REPLY.md`, `LMS_ADMISSION_18_ALLOCATED.md`, `LMS_ACTIVATION_LINK_SENT.md` and `LMS_LOCAL_RUNNING.md` in the CRM's `nipuna lms-docs/`. Open: the `lms_account_activated` test, once Pinbot approves the templates |
| Production test | 28 Oct – 1 Nov 2026 | The combined CRM + LMS test in production, phases A–M, then both systems restored. Results, findings and the go-live steps: [DEVELOPMENT.md Part F, "Production test"](DEVELOPMENT.md#6-production-test-28-oct--1-nov-2026) |

---

## Part B — Google Workspace

Status: **live in production since 28 Oct 2026**: Google Meet, Google Drive and Email are Verified. Configuration, migrations 123 to 126, the Google client, the `google-sync` job with retries, class Calendar events with Meet links and student invitations (§5.1), Drive folders with a Google Group per batch (§5.2), the Gmail outbox (§5.3) and the Super Admin screen (§7). The four design questions are answered (§9). `services/integrations.py` is the on/off switch for each feature.

### 1. Scope

| # | Phase 1 item | Replaces / extends |
|---|---|---|
| 1 | Service account with domain-wide delegation, in one Google API client module | New `services/google/` package |
| 2 | Secret Manager for the service-account key | `.env` values today |
| 3 | Per-branch Workspace config | New table (§4) |
| 4 | Calendar events with Meet links for Live Online and Hybrid classes | Manual `associate_meet` entry |
| 5 | Drive folders per branch → course → batch, shared with the batch's Google Group (students) and its trainers | None today |
| 6 | Gmail for activation links and reminders | WhatsApp-only delivery today |
| 7 | Sync job with retry queue for every Google call | New job in `services/jobs.JOBS` |
| 8 | ~~CRM events for Workspace actions~~ | Not needed for now: the CRM does not want any (§5.5) |

Out of phase 1: **Google Sign-In** (login stays password-only for now), Directory sync of accounts, Meet attendance reports, Sheets,
Chat, Pub/Sub, Docs/Slides/Forms, Cloud Storage. (Google Groups are used, one per batch, only for Drive sharing: §5.2.)

### 2. Architecture rules

- **One door to Google.** Only `services/google/` imports Google libraries. Other services call its functions.
- **The register gates every call.** Before calling Google, a service checks `integrations.is_verified(code)`. Not verified → behave exactly as today (manual Meet link, WhatsApp-only activation) and record the state; never raise to the user.
- **Never call Google inside a request that changes LMS data.** The request writes its LMS change and enqueues a job in the same transaction; the job calls Google. A Google outage cannot block scheduling a class.
- **Idempotent jobs.** One open job per (kind, entity), and Google objects get our own deterministic ids (a class's event id is `lms` + its session id, zero-padded), so a retry after a lost reply finds the same event, never a duplicate.
- **Secrets never reach the database or logs.** Only identifiers (event ID, folder ID) are stored.

Register entries used (all in `integrations`): `GOOGLE_MEET` switches class Calendar events and Meet links; `GOOGLE_DRIVE` (new in migration 123)
switches Drive material; `EMAIL` (existing) switches Gmail. `GOOGLE_WORKSPACE` stays the record of the organisation setup. A switch is on only when
the entry is Verified **and** a service-account key is configured.

### 3. Components

```
request ─▶ service ─▶ google_jobs row (same transaction)
                          │
          jobs run ─▶ google-sync job ─▶ services/google/{calendar,drive,gmail}.py ─▶ Google APIs
                          │                       ▲
                          ▼                       └── services/google/client.py (service account, delegation, Secret Manager)
                  success: store Google IDs, audit, CRM event
                  failure: attempts+1, next_attempt_at (backoff); after the cap → Dead + visible to Super Admin
```

| Module | Does |
|---|---|
| `services/google/client.py` | Loads the key (§6), builds a service object for a given mailbox via delegation, retries 429/5xx once |
| `services/google/class_events.py` | Queues, creates, patches and deletes a class's Calendar event with a Meet conference, and records the link on the class |
| `services/google/drive.py` | Ensures a folder path, grants and revokes access |
| `services/google/gmail.py` | Sends one plain-text message as a mailbox (`gmail.send`) |
| `services/emails.py`, `email_messages.py`, `email_templates.py` | The email outbox: queue, render, send with retries. Mirrors `whatsapp.py`, `whatsapp_messages.py`, `whatsapp_templates.py` |
| `services/google/jobs.py` | `run_due()`: claims due jobs, calls the right handler, records the result, backs off. Registered as `google-sync` in `services/jobs.JOBS`, so `deploy/crontab` and `jobs run --loop` pick it up |
| `repositories/google.py` | All queries on the new tables |

### 4. Database

Migration `123_google_workspace.sql` (built) holds `branch_google_config` and `google_jobs`; `124_email_outbox.sql` (built) holds `email_outbox`; `125_google_drive.sql` and `126_drive_batch_group.sql` (built) hold the Drive tables. Depends on `001` (integrations, branches). Follows the migration workflow in
[DATABASE.md](DATABASE.md#how-migrations-work); add a section there when it lands.

| Table | Columns (key ones) | Rule |
|---|---|---|
| `branch_google_config` | `branch_id` PK/FK, `calendar_mailbox`, `drive_root_folder_id`, `gmail_sender` | Defaults to `branches.mailbox` when null |
| `google_jobs` | `job_id`, `kind`, `entity_type`, `entity_id`, `payload` jsonb, `state` (Queued/Running/Failed/Succeeded/Dead), `attempts`, `next_attempt_at`, `started_at`, `last_error`, timestamps | The retry queue. One open job per (`kind`, `entity_type`, `entity_id`); the job reads the class as it is when it runs |
| `google_drive_items` (125, built) | `entity_type` (branch/course/batch), `entity_id`, `branch_id`, `parent_item_id`, `folder_id`, `folder_name`, `group_email` (batch rows: the batch's Google Group) | Folder tree; unique per (`entity_type`, `entity_id`, `branch_id`) |
| `google_drive_grants` (125, built) | `item_id` FK, `grantee_email`, `grantee_user_id`, `role` (reader/writer), `permission_id`, `granted_at`, `revoked_at` | One live share per person per folder |
| `email_outbox` (124, built) | `template`, `recipient_user_id`, `branch_id`, `to_email`, `subject`, `body`, `dedupe_key` unique, `status` (Queued/Sent/Failed/Skipped), `status_note`, `attempts`, `next_attempt_at`, `sent_at` | Same idea as `whatsapp_outbox`; drained by the `email-send` job |

No token or key column: the service account needs no stored user tokens.

### 5. Flows

#### 5.1 Class → Calendar event → Meet link

1. Creating (once approved), rescheduling, approving, retrying (`meet/reset`) or switching to online a Live Online / Hybrid session enqueues `CALENDAR_UPSERT`; cancelling it or switching it to Classroom enqueues `CALENDAR_CANCEL`. Both are no-ops unless the switch is on (§2).
2. The job creates or patches the event in the branch calendar mailbox (the same mailbox `services/meet.organizer_email` already returns), with a Meet conference and these attendees: the trainer and every student holding a seat in any batch the class serves. Guests cannot see each other's addresses, and Google emails each invitation and any later change.
3. On success the class is Linked, with `meet_link` and `calendar_event_id`, and `meet_events` gets a "Link associated" row in the same log a hand-entered link uses (the job has no signed-in user, so it writes the class directly instead of calling `associate_meet`).
4. If Google has not made the Meet conference yet, the event id is kept and the job retries. When retries run out, or Google refuses the delegation, the class shows Failed and Branch Managers get the same "Meet association failed" task as a hand failure; staff can retry (`meet/reset`) or paste a link by hand. A link entered by hand before the job runs is kept.
5. Reschedule and cancel patch or delete the same event by its stored ID.

A seat taken or ended also queues an update for the batch's upcoming online classes that already have an event, so the invitations follow the roster. Students see the Meet link beside the class on their Schedule page, and the Join button opens 15 minutes before the class, as before. Addresses that are not valid emails are left out rather than failing the event; an event holds at most 190 guests.

#### 5.2 Drive material

- Folders `Nipuna LMS / <course> / <batch code>`, owned by the branch's mailbox and made on demand by the `google-sync` job (`services/google/batch_folders.py`). A folder is found by a tag we put on it, so a retry after a lost reply never makes a second one. The branch folder can be one the branch's admin chose (`branch_google_config.drive_root_folder_id`).
- **One Google Group per batch** (`<batch code>@<Workspace domain>`, made on demand through the Directory API as `GOOGLE_DELEGATED_ADMIN`). The students holding a seat are its members, and the folder is shared **once** with the group as viewers. Trainers assigned to the batch are shared with individually as editors.
- A student leaves the group when their seat ends (left, transferred) or the batch is Completed, Cancelled or Archived, and so loses the folder. Trainers lose access when their assignment ends or the batch is Cancelled or Archived. Group owners and managers are never removed by the sync.
- One `DRIVE_SYNC` job per batch. A seat taken or ended, a trainer assigned or ended, a batch state change, and a change of a seated student's email (from the CRM, or confirmed by the student in My Account) each queue it; an email change also brings the invitations to the batch's upcoming online classes up to date; the job compares who should be in the group and have the folder with the group's actual members and the shares it recorded, and adds or removes the difference, so any number of changes is one pass and a retry resumes where the last pass stopped.
- An address with no Google account can only be invited, which makes Google email it; the job asks for that only after Google refuses the quiet share.
- When retries run out, the branch's managers get a "Drive sharing failed" task.
- A student's address that Google refuses as a group member (400, or 404 `memberKey`, as for a Gmail address with a `+` in it) does not fail the job. Everyone else is synced, and the branch's managers get one "Google would not add a student" task per batch and address, telling them to correct the email in the CRM. A 403, 412, 429, 5xx or a 404 on the group itself still fails the job as above.
- LMS content upload is unchanged; Drive is for shared working material, not the system of record for graded content.

Groups need two things in the Workspace admin console: the Directory scope in the delegation, and Groups for Business sharing settings that let a group have members outside the organisation (students use personal addresses). Without the second, adding such a student fails with a 4xx and the job is retried, then shows on Setup & health.

#### 5.3 Gmail

- Every WhatsApp message the LMS sends has an email beside it, queued by the same code path in the same transaction (`services/email_messages.py`): activation link, staff invite, class reminder, class cancelled, class rescheduled, result published, certificate issued (with a verify link when `PUBLIC_BASE_URL` is set) and a batch change that needs the student's agreement. A staff login's password reset code is emailed too (staff often have no number on file); a student's reset code and the email-change code stay WhatsApp-only. The screen that issues a link says where it went: `email_delivery {state, note, to}` beside `whatsapp`.
- Same rules as WhatsApp: one message per dedupe key; a message that cannot or should not go out is kept as Skipped with the reason ("Email is switched off", "No email address on file", "The person switched email off for this kind of message", "Too old to send"); sign-in links ignore the person's preferences and are blanked from the row once the message is done; class reminders (Learning reminders) and the other notices are on unless the student switches that group's email off in notification preferences (reminders were opt-in until 1 Nov 2026).
- The switch is the `EMAIL` register entry Verified **and** a service-account key. The link needs `PUBLIC_BASE_URL`; without it the activation email is Skipped.
- The `email-send` job sends Queued rows through Gmail as the branch's own sender if one is set (`branch_google_config.gmail_sender`), else the LMS no-reply address (`GOOGLE_EMAIL_SENDER`), else the branch mailbox (a staff invite with no branch and no no-reply address uses `GOOGLE_DELEGATED_ADMIN`). The no-reply address in `.env` is a **sample** (`no-reply@nipunatechnologies.com`) until the real one is given; it must be a real mailbox in the domain, because the service account acts as it. A timeout, 429 or 5xx is retried after 5 min doubling to 6 h, five tries in all; any other refusal fails at once. It is a separate job from `google-sync` so the two cannot hold each other up.

#### 5.4 Sync job and retry

- `google-sync` runs with the other jobs every 5 minutes (`deploy/crontab`); `jobs run --loop` locally.
- Backoff: 5 min, 15 min, 1 h, 6 h, 24 h, then `Dead`. 4xx other than 429 is not retried.
- Each run is recorded in `job_runs` like the existing jobs. Dead jobs list on a Super Admin screen (read-only in phase 1).

#### 5.5 CRM events

None. The CRM does not want any Workspace events for now. If that changes, see [INTEGRATIONS.md Part A](INTEGRATIONS.md) §2.2 before adding one.

### 6. Configuration

New keys in `config/settings.py` (read from `backend/.env`):

| Key | Meaning |
|---|---|
| `GOOGLE_WORKSPACE_DOMAIN` | The Workspace domain the delegation applies to |
| `GOOGLE_DELEGATED_ADMIN` | Mailbox the service account acts as when no branch mailbox applies, and for batch groups (a Workspace admin who can manage groups) |
| `GOOGLE_EMAIL_SENDER` | Who LMS emails come from unless a branch sets its own (a sample no-reply address for now) |
| `GOOGLE_SA_SECRET_NAME` | Secret Manager resource holding the service-account key JSON (production) |
| `GOOGLE_SA_KEY_FILE` | Local file path for the key (development only; git-ignored) |

Unset keys mean the integration reports "Not Configured" and nothing calls Google. Tests mock `services/google/client.py`;
no test reaches Google.

**Google-side setup (done by a Workspace Super Admin, once):** create a Cloud project and enable the Calendar, Drive and Gmail
APIs; create the service account and its key; authorise its client ID in the admin console (Security → API controls →
Domain-wide delegation) for the scopes `calendar.events`, `drive.file`, `gmail.send` and `admin.directory.group`; make sure groups may have members outside the organisation; store the key in Secret Manager;
check that every branch mailbox is a real Workspace account; set Meet so people outside the domain can join. No OAuth client
is needed while Google Sign-In is out.

#### First real test

Do it with one dev mailbox first, so a mistake cannot email students or share real folders. Nothing calls Google until the last step.

1. **Workspace admin, once** (the steps above): Cloud project with the Calendar, Drive and Gmail APIs enabled; a service account and its JSON key; domain-wide delegation with the four scopes (the fourth is `admin.directory.group`); groups allowed to have outside members; Meet open to people outside the domain.
2. **On the server:** save the key as `backend/secrets/google-service-account.json` (git-ignored), and set `GOOGLE_WORKSPACE_DOMAIN` and `GOOGLE_DELEGATED_ADMIN` (a real mailbox in that domain) in `backend/.env`.
3. **`flask --app app google check`** (from `backend/`, venv active). It prints the service account's **client ID**: that is what goes in the Admin console's delegation list. It then proves delegation for each scope and reads the mailbox's calendar and Drive, then checks the Directory scope as the delegated admin and lists the domain's groups. Nothing is created. Add `--mailbox` or `--branch ID` to try a branch's mailbox. Exit code 1 means a check failed, with the fix beneath it.
4. **`flask --app app google send-test --to you@…`** sends one real test email. Use your own address.
5. **Setup & health:** mark Google Meet, Google Drive material and Email **Working**, each with a note of how you checked it. Until then nothing is queued, so the checks above never touch real classes.
6. **Try one of each** with a test branch or batch: schedule an online class (a Meet link appears after the next `google-sync`, within 5 minutes; locally `jobs run --loop` does it), allocate a test student (they are added to the batch's group, which has the folder), and create a test student (an activation email arrives, if `PUBLIC_BASE_URL` is set).
7. **Setup & health > Google Workspace** shows anything stuck, with the reason and a Try again button.

### 7. API and screen

Built. Everything is for Super Admin and Founder, and sits under Setup & health in the admin and founder workspaces. Full detail in
[API.md](API.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/google/overview` | What is on, counts, and the calls that need a person |
| GET | `/google/jobs` | The queue, filterable by state |
| POST | `/google/jobs/<id>/retry` | Run a failed call now, or requeue a dead one |
| GET | `/google/emails` | The email outbox, with why a message did not go |
| GET / PATCH | `/google/branches[/<id>]` | Per-branch calendar mailbox, email sender and Drive folder (fresh authentication to change) |

The screen is the **Google Workspace** section of Setup & health (`frontend/src/features/admin/google-workspace.tsx`): a note while
the server has no Google key, each feature On or Off beside its checklist state, the stuck calls with a Try again button, failed
emails, and a branch picker for the three settings.

### 8. Build order and tests

1. ✅ Migration 123, models, `repositories/google.py`, register entry.
2. ✅ `client.py` + settings + fakes; `google-sync` job with retry.
3. ✅ Calendar/Meet job wired to the class lifecycle (`tests/test_google_calendar.py`, `tests/test_google_client.py`).
4. ✅ Gmail outbox beside activation and reminders (`tests/test_email_outbox.py`).
5. ✅ Drive folders and grants on allocation, transfer and completion (`tests/test_google_drive.py`).
6. ✅ Super Admin screen for stuck calls, failed emails and branch settings (`tests/test_google_admin.py`, `frontend/e2e/google-workspace.spec.ts`).
7. CRM events: not needed (§5.5).

Tests per step in `backend/tests/test_google_*.py`, run with `./run_tests.sh`. Must cover: register gate off → old behaviour
unchanged; duplicate job key → one Google call; failed call → backoff then Dead; revoke on batch transfer.

### 9. Decisions

| Question | Decision |
|---|---|
| Are students attendees on class events? | Yes: the students holding a seat in the batch. They see the Meet link on their Schedule page |
| Per-student Drive shares or a Google Group per batch? | A Google Group per batch |
| Which mailbox sends Gmail? | A no-reply address, a sample until the real one is given; a branch can still set its own |
| Which Workspace events does the CRM want? | None for now |

### 10. Later: Google Sign-In

Deferred. When wanted: staff-only `POST /auth/google` that verifies a Google ID token (audience, expiry, `email_verified`,
hosted domain), links to an existing active staff user by email, and opens the same session as password login via
`auth.open_session`. It never creates accounts. It needs an Internal OAuth consent screen, an OAuth client for the LMS
origins, a `google_identities` table, and a decision on whether it counts as fresh authentication for `@fresh_auth`.

---

## Part C — WhatsApp templates

The LMS's WhatsApp messages and their template names are in `backend/services/whatsapp_templates.py`; the CRM sends them
through Pinbot (Part A, round 6). Meta must approve each template first.

### 1. Password reset code: `nipuna_lms_password_reset_code_auth_v2` (approved)

#### 1.1 Template Setup
* **Category:** Authentication
* **Name:** `nipuna_lms_password_reset_code_auth_v2`
* **Language:** English (en or en_US)

---

#### 1.2 Configuration & Toggles
* **Code delivery method:** Copy code
* **Add security recommendation:** Yes (checked)
* **Code expiration:** Yes (checked)
* **Expiration time:** 10 minutes

---

#### 1.3 Body & Sample
* **Body:**
  ```text
  *{{1}}* is your verification code. For your security, do not share this code. This code expires in 10 minutes.
  ```
* **Sample for `{{1}}`:** `482913`

---

#### 1.4 Button
* **Type:** Copy code
* **Sample code:** `482913`

---

### 2. To resubmit: activation link and staff invite

Pinbot's template report (28 Oct 2026) shows two LMS templates **Rejected**: `nipuna_lms_student_activation_link_u_v1` and `nipuna_lms_staff_account_invite_u_v1`. Both were submitted on 24 Oct. The rejection reason is not in the report. **Read it in the Pinbot or Meta panel before resubmitting**, and fix that first; the drafts below fix the usual causes but cannot know yours.

#### Most likely causes, in order

1. **The button's website address.** Both templates have a "Set password / Activate account" URL button, and Meta checks the domain. On 24 Oct the LMS had no real address; the sslip.io one is an IP-based free domain Meta may also refuse. **The LMS's own hostname `https://nipunalms.com` is live since 1 Nov 2026**: resubmit with it. The button is a dynamic URL ending in the token: `https://nipunalms.com/activate?token={{1}}`.
2. **A missing or unusable sample** for a variable or for the button.
3. **Wording** that reads as an account or security message when filed as Utility, or has a variable at the very start or end of a sentence with too little text around it.

#### What changes in code on approval

Only the **names** and the **body text**. The variables keep their order and meaning, so no code for building the message changes. When Meta approves a version:
- LMS: rename the template in `backend/services/whatsapp_templates.py` and add the new name to `whatsapp_approved_templates`.
- CRM: rename it in its registry (`services/whatsapp_templates.py`) in the same release, and the CRM team confirms.
Do not rename before approval: a name Pinbot does not know is refused, as the v1 names are now.

---

#### 2.1 `nipuna_lms_student_activation_link_u_v2`

* **Category:** Utility
* **Language:** English (`en`)
* **Body:**
  ```text
  Hello {{1}}, your Nipuna Technologies learning account at {{2}} is ready. Your Student ID is {{3}}. Use the button below to set your password. This link can be used once and expires on {{4}}. If you were not expecting this, please contact your branch.
  ```
* **Samples:** `{{1}}` Anvitha K. · `{{2}}` Guntur · `{{3}}` NIT-STU-2026-000001 · `{{4}}` 30 Oct 2026
* **Button:** Visit website, dynamic URL, text **Activate account**, URL `https://nipunalms.com/activate?token={{1}}`, sample `7f3a9c1e2b`

#### 2.2 `nipuna_lms_staff_account_invite_u_v2`

* **Category:** Utility
* **Language:** English (`en`)
* **Body:**
  ```text
  Hello {{1}}, your Nipuna Technologies LMS account has been created with the role {{2}} at {{3}}. Use the button below to choose your password. This link can be used once and expires on {{4}}. If you were not expecting this, please tell your Super Admin.
  ```
* **Samples:** `{{1}}` Ravi Kumar · `{{2}}` Branch Manager · `{{3}}` Guntur · `{{4}}` 30 Oct 2026
* **Button:** Visit website, dynamic URL, text **Set password**, URL `https://nipunalms.com/activate?token={{1}}`, sample `7f3a9c1e2b`

---

#### Until they are approved

Both messages go **by email only**. A student's activation link can also be copied or reissued by a Branch Manager on Student Accounts. The production test (Oct 2026) recorded their WhatsApp as Skipped.

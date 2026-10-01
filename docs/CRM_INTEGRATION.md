# Nipuna LMS ↔ CRM integration

How the LMS and the CRM (`nipuna-crm`) are connected. Part 1 says who owns what, Part 2 is the wire contract, Part 3
lists the work on the CRM side (done and still open), Part 4 is the status, and Part 5 records the integration rounds.

How to run both systems together on one laptop is in [DEVELOPMENT.md Part C](DEVELOPMENT.md#part-c--running-with-the-local-crm).
The CRM's own docs (copied into `nipuna crm-docs/`) describe its side: `API.md` Step 22 and `DATABASE.md` "LMS outbox
(026)".

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
| Curriculum versions, mapping, batches, trainers, allocation, joining date, class sessions, attendance, progress, completion | **LMS** (Modules 14, 15, 21) | CRM mirrors the columns it already has (enrolment / curriculum status, batches, allocations, joining date, completion) |
| Certificates | **LMS** Certificate Register (Module 22) | CRM `certificates` becomes a mirror |
| Placement (employers, openings, applications) | **Decision needed** (§3.9) | |
| Support | CRM `support_cases` for money / admission; LMS support requests for academic / LMS | Cross-link (§3.10) |

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
| `AdmissionUpdated` | `admission_transfers` insert (service branch), delivery mode change, pause / resume | `crm_admission_id`, `service_branch_code`, `delivery_mode`, `status` (Active / Paused). The CRM has no pause action yet, so `status` is not sent |
| `AdmissionCancelled` | `POST /admissions/{id}/cancel` | `crm_admission_id`, `reason` (free text, no length limit). Withdraws only that admission's enrolments |
| `FinanceSummaryUpdated` | Payment recorded (pending verification), verified, failed, allocated; correction approved (reversal); fee change applied; refund decided (waiver); refund payout; invoice cancelled; instalment due date changed. Sent for **every admission on the invoice** | From `admission_balances` + `installment_dues` + verified `payments`: `crm_admission_id`, `fee_total` (final fee), `verified_paid`, `pending_verification`, `waived`, `refunded`, `balance` (outstanding; 0 for a cancelled admission), `payment_completion`, `invoice_numbers[]`, `installments[]` = `{installment_no, due_date, amount, covered, balance, due_position}`, `next_due_date`, `next_due_amount` (the first instalment that still has a balance; it may already be overdue), `receipts[]` = `{receipt_number, date, amount}` (verified, non-reversed payments; `amount` is the part allocated to this course; `date` is the payment date), `as_of`, `installments_scope` (`admission` default / `invoice`), `invoice_course_count` (int ≥ 0, default 1) |

| `BranchUpserted` | Branch created or edited in the CRM (`branches`). Versioned per branch (`branch:<id>`) | `branch_code`, `branch_name`, `city`, `receipt_prefix` (→ LMS `short_code`, used inside batch codes), `email` (→ the branch's shared `mailbox`), `is_active`. A new branch needs `receipt_prefix` and `email`; an existing branch keeps its short code (a different one is a 422), and a `null` email keeps the mailbox. Other CRM columns (`address`, `phone`, …) are ignored |
| `BranchFinanceSnapshot` | A CRM job every 15 minutes, one per branch (`branch-finance:<id>`) | `branch_code`, `as_of`, `period` = `{label, start, end}` of the Approved target (`null` when there is none; then both targets must be `null`), `collections` = `{verified, target}`, `paid_admissions` = `{count, target}`, `overdue` = `{amount, count, by_age_band[] = {band, amount, count}}` (from `installment_dues`), `verifications` = `{pending_count, pending_amount, overdue_count (past the verification SLA), oldest_at}`, `followups` = `{overdue_count, broken_promises}`. Each snapshot replaces the branch's previous one |

**Instalments are per invoice.** With `installments_scope: "invoice"` every admission on the invoice carries the same
schedule and `next_due_*`. The LMS shows and sums the schedule once per invoice (`invoice_numbers[0]`), never per
admission; the per-course figures (`fee_total` … `balance`, `receipts`) stay per admission.

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
plaintext (§3.7).

| HTTP | Meaning | What the CRM worker does |
|---|---|---|
| 201 | Applied | Delivered |
| 200 | Same `event_id` already processed | Delivered |
| 400 | Payload failed validation (`error.details` lists the fields) | Failed + Super Admin task; the CRM fixes its mapping and resends the record as a **new** event |
| 401 | Missing or wrong service key | Stops the run; fix the config |
| 409 | `event_id` reused with a different payload | Failed + task (a CRM bug: a changed payload needs a new `event_id`) |
| 422 | Valid payload that cannot be applied yet (course not arrived, unknown branch, component still in use) | Stays Pending, retried with backoff (30 s doubling, capped at 1 h); Failed + task after 12 attempts |
| 5xx / timeout | LMS problem | Retried with backoff, same `event_id` |

### 2.2 LMS → CRM: what the CRM stores about the LMS

Two ways, both built in the LMS: **pull** `GET {LMS}/api/v1/integrations/crm/status?since=<ISO time>` (service key;
returns `persons[]`, `admissions[]`, `academics[]`, `batches[]`, `certificates[]` and `as_of`, the next `since`), or
**push** from the LMS `crm_outbox` (rows written in the same transaction as the change; no delivery worker yet — §3.2).
Undelivered rows for the same admission / batch are superseded by the latest state. Rows written by the dev seed
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

| CRM column | LMS source | Pull key / outbox event |
|---|---|---|
| `persons.lms_user_id`, `lms_provisioned_at` | Student ID (`students.student_code`, e.g. `NIT-STU-2026-004182`; stable, never reused), time the login was first created | `persons[]` / `LmsAccountProvisioned` |
| `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at` | `lms_status` (below); latest `activity_events.occurred_at` for the admission's enrolments; pull time | `admissions[]` / `AdmissionLmsStatusChanged` |
| `admissions.enrolment_status` | LMS enrolment status → Awaiting Batch Allocation / Scheduled / In Progress / Paused / Completed / Cancelled | `academics[]` / `AdmissionAcademicsChanged` |
| `admissions.curriculum_status`, `curriculum_version_id` | Mapped / Mapping Pending + `curriculum_version_label` | same |
| `batch_allocations` (batch, status, `joining_date`, `ended_at`, `end_reason`) | `allocations[]` = `{course_code, track_code, lms_course_id, crm_batch_id, status (Active / Moved / Withdrawn / Completed), joining_date, allocated_on, ended_on, end_reason}`. A combo has one per track: `track_code` is the LMS track (`null` for a single course), `course_code` its component course or the combo's own code, and `lms_course_id` a batch of the combo course | same |
| `admissions.academic_completed_at` | Enrolment completed time | same |
| `admissions.completion_authorised_by` | The Academic Coordinator who decided the completion review | `academics[].completion_authorised_by_email` |
| `batches` (+ `lms_course_id`) | `{lms_course_id = LMS batch_code, crm_batch_id, course_code, branch_code, delivery_mode, status (Planned / Open / In Progress / Completed / Cancelled), capacity, start_date, end_date, curriculum_version_label, lead_trainer_email, trainer_emails}` | `batches[]` / `BatchUpserted` (+ `BatchLinked` when a CRM batch is linked) |
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

## 3. Work on the CRM side

Numbered so they can be tracked. 3.1 is done; 3.2–3.4 are next; the rest remove double entry and conflicts.

### 3.1 Send events to the LMS ✅ (round 1)

Built in the CRM (`nipuna-crm` db `026_lms_outbox.sql`, dev database only):

- `lms_outbox` table and `lms_sync_versions` counters (`course:<id>`, `admission:<id>`, `finance:<id>`). A trigger makes
  a written envelope immutable, so every retry is byte-for-byte the same request; a changed record gets a new event with
  a higher version.
- Events are written in the same transaction as the change, for every path in §2.1.
- Worker: job `lms-sync` in `flask jobs run`, or `flask --app app lms deliver --loop`. Each run takes the oldest
  Pending row of each record (an admission together with its finance), so an admission's finance never overtakes its
  `AdmissionQualified` and one waiting admission never blocks another. Rows are claimed with a 5-minute lease; no
  transaction is held open during the HTTP call. A Failed row does not hold back later rows of the same admission.
- Config: `LMS_BASE_URL` (dev `http://127.0.0.1:5060`) and `LMS_SERVICE_KEY` (= the LMS `CRM_SERVICE_KEY`) in the CRM
  `backend/.env` / `.env.example`.
- Backfill: `flask --app app lms backfill` (courses, then every non-cancelled admission with its finance;
  `--include-cancelled` also sends cancelled ones, qualified first; `--admission <id> --force` resends one record as a
  new event). Other commands: `lms outbox --failed`, `lms requeue [id…]`, `lms status-check`.
- `activation_token` is never logged or stored; the CRM keeps only `activation_token_issued = true` on the outbox row.

### 3.2 Receive LMS status (next)

- Chosen in round 2: **pull**. A CRM job `lms-status-pull` calls `GET /integrations/crm/status?since=<last as_of>`
  every few minutes (watermark in `app_settings`; rules in §2.2). The LMS outbox is not delivered.
- Apply: `persons.lms_user_id`, `lms_provisioned_at`; `admissions.lms_status`, `lms_last_activity_at`,
  `lms_last_synced_at`; the academic columns (3.3); batches (3.4); certificates (3.6).
- `PATCH /admissions/{id}` must stop accepting `lms_status` from staff at the same time (it becomes LMS-owned); the
  **LMS access** screen (`/lms-access`) keeps its read-only list, now with real values and a "last synced" time.

### 3.3 Academic columns become an LMS mirror

Apply `AdmissionAcademicsChanged` to `admissions.enrolment_status`, `curriculum_status`, `curriculum_version_id`
(match `curriculum_version_label` + course, creating a Published mirror row if missing), `batch_allocations`
(`joining_date`, status, `ended_at`, `end_reason`), `academic_completed_at`. The CRM's triggers need a system path:

- `admissions_completion` requires `completion_authorised_by` (a CRM user): allow a sync source (e.g.
  `completion_source = 'LMS'` + the LMS authoriser's email) or map the email to the CRM user.
- Allocation triggers (same service branch, curriculum Mapped, capacity, one active per course) must accept
  LMS-confirmed allocations as facts, not re-validate them.
- The "first allocation → Scheduled, joining date → In Progress" triggers must not fight the mirrored status (apply the
  status after the allocation, or disable those triggers for the sync session, e.g. `SET LOCAL app.sync_source = 'LMS'`).

### 3.4 Batches become an LMS mirror

- Upsert CRM `batches` from `BatchUpserted` keyed by `lms_course_id` (= LMS `batch_code`); map `lead_trainer_email` →
  `trainer_user_id`; status / mode vocabularies per §2.3. `batch_code` stays the CRM's own (`GNT-B-0001`).
- A combo's tracks are allocated to batches **of the combo course** (the LMS refuses a batch of another course), so
  the CRM must accept a mirrored batch on a combo course. Store one allocation per track (`track_code`).
- Existing CRM batches: dropped, not linked (dev data only; agreed in round 2). The CRM stops sending `crm_batch_id`.
- `lead_trainer_email` with no matching CRM user: store the email as text and leave the user id empty.

### 3.5 Retire double entry in the CRM (after 3.3 / 3.4)

Make these read-only (or remove the buttons) and link to the LMS: `POST/PATCH /batches`, `POST /admissions/{id}/allocations`,
`POST /batch-allocations/{id}/close`, `POST /batch-allocations/{id}/joining-date`, `POST /curriculum-versions`, `/publish`,
`POST /admissions/{id}/curricula`, `POST /admissions/{id}/complete`, `POST /admissions/{id}/certificates`,
`/certificates/{id}/issue`, `/revoke`. Jobs: `batch-allocation` escalation moves to the LMS (its
`allocation-escalation` job is built: 24 hours before `planned_start_date`, to the service branch's Branch Managers). The Academic Coordinator
and Trainer screens in the CRM (Batches, allocation queue, joining date) become views; their academic work happens in
the LMS. Update the CRM ROLE_GUIDE / PRODUCT_GUIDE accordingly.

### 3.6 Certificates

The LMS register numbers certificates `NIT-CERT-2026-000001` (prototype); the CRM numbers `GNT-C-2627-00001`. Decide
one series (decided in round 2, D2: **the LMS register's**, since it owns issue, reissue and revoke) and mirror LMS certificates into
CRM `certificates` read-only, for Student 360 and alumni (CRM `certificate_status` has no *Superseded*: add it, or keep
only the latest version per number).

### 3.7 Student activation delivery (decided: B now, A later)

A new LMS login comes with a one-time activation token in the `AdmissionQualified` response. Today the CRM discards it,
so these students can only activate after an LMS reissue: a coordinator or Super Admin uses Student Accounts →
"Activation link from: CRM provisioning (not delivered)" (`?activation_channel=CRM provisioning`) and reissues the link;
the old token stops working.

- **Option A:** the CRM delivers `{LMS}/activate?token=…` by WhatsApp or email. Needs a CRM template and task, and a
  decision on whether the token may sit in the CRM outbox until sent.
- **Option B:** activation stays supervised in the LMS, and the LMS stops returning `activation_token`.

Decided in round 2 (D1): **B now, A later.** Coordinators reissue links in the LMS until the CRM's WhatsApp / email
delivery is live; then the CRM switches to A. The LMS keeps returning `activation_token` meanwhile (the CRM discards it),
so the switch needs no LMS change.

### 3.8 Staff accounts

Trainers, Academic Coordinators, Branch Managers and admins need LMS accounts too. Use the **same email** in both
systems (the LMS reports trainers and authorisers by email). Later: single sign-on or user provisioning from the CRM.

### 3.9 Placement (decided: the CRM owns it)

The CRM already runs placement (companies, job openings, placement profiles, applications, alumni) for the Placement
Team; the LMS has a student-facing Career screen (profile, CVs, opportunities, applications). Recommended: the CRM stays
the owner of employers, openings and applications; the LMS Career screen reads approved openings and submits
applications / CVs to the CRM (new CRM service endpoints), so there is one placement record. Decided in round 2 (D5);
built in a later round.

### 3.10 Support

CRM `support_cases` (money, admission, complaints) and LMS support requests (academic, LMS, recordings, devices) stay
separate but should cross-link: an LMS request that is really a fee question is routed to a CRM support case (and vice
versa) with both references stored.

### 3.11 Small points

- Keep `admission_code`, `person_code`, `receipt_number` in payloads for display.
- `curriculum_versions` in the CRM are per course only; LMS combos have per-track versions — the mirror should store the
  parent programme label.
- `CourseUpserted` does not carry the standard fee or the branches offering a course; both are in the CRM Course
  Master. Ask the CRM if the LMS needs them.

### 3.12 Branches (decided: `BranchUpserted`)

Decided in round 2 (D3). The LMS accepts `BranchUpserted` (§2.1, db 096). The CRM writes one in its outbox when a branch
is created or edited, and backfills its existing branches once (`NIT-GNT` / `NIT-VIJ` already match: the LMS short codes
equal the CRM's `receipt_prefix`). A `BranchUpserted` must be delivered before the first admission of a new branch,
or that admission gets a 422 and is retried.

### 3.13 Dashboard finance figures (decided: CRM pushes `BranchFinanceSnapshot`)

Decided in round 2 (D4). The LMS accepts `BranchFinanceSnapshot` (§2.1, db 096) and stores the latest one per branch.
The CRM builds the job: every 15 minutes, one event per active branch, from `target_versions` / `target_lines`
(Approved, current period), verified `payments`, `installment_dues` (overdue, by age band), pending `payments` (SLA
task `PAYMENT_VERIFICATION`) and `payment_promises` / follow-up tasks.

The dashboards sum the branches in view: verified collections and new paid Admissions against target (Branch,
Founder), overdue amount by age band (Founder), overdue follow-ups = overdue follow-ups + broken promises (Branch),
overdue payment verifications (Super Admin). A figure is *Configured* when every branch in view has a snapshot,
*Partial Data* (naming the missing branches) when only some do, and *Not Configured* when none do: never 0. A snapshot
older than 60 minutes is flagged stale. A target shows only when every branch in view has one for the same period.

---

## 4. Status

| Item | Status |
|---|---|
| Event intake, idempotency, versions, retry, inbox screen (`/admin/crm-sync`) | ✅ LMS (db 003) |
| CRM vocabulary and shapes (Online, English / Telugu, `phone`, `course_title`, `combo_courses` components, Archived, one course per admission, complimentary as its own admission, seat type, planned start, access until, full finance balances + instalments) | ✅ LMS (db 005, `tests/test_crm_alignment.py`) |
| LMS → CRM: provisioning, `lms_status`, academics, batches (pull + outbox) | ✅ LMS (db 003, 005) |
| Certificates and completion authoriser to the CRM | ✅ LMS (db 070, `tests/test_crm_certificates.py`) |
| Round-1 fixes F1–F10 (§5) | ✅ LMS (db 090, `tests/test_crm_round1.py`, `tests/test_profile_finance.py`) |
| Round-2 answers Q1–Q9 and pull fixes L1–L7 (§5) | ✅ LMS (db 095, `tests/test_crm_round2.py`) |
| CRM outbox, worker, backfill (§3.1) | ✅ CRM (db 026, dev only) |
| CRM applies the status pull (§3.2) and the mirrors (§3.3, §3.4, §3.6); academic screens read-only (§3.5) | ✅ CRM, round 2 (`nipuna crm-docs/CRM_ROUND2_REPLY.md`) |
| LMS outbox delivery worker | Not needed: the CRM pulls (§3.2) |
| Activation link delivery (§3.7) | Decided: B now (LMS reissue), A later (CRM delivers) |
| Branches (§3.12) | ✅ LMS accepts `BranchUpserted` (db 096); ⏳ CRM sends it |
| Dashboard finance figures (§3.13) | ✅ LMS accepts `BranchFinanceSnapshot` and shows it (db 096); ⏳ CRM job |
| Certificate number series (§3.6), placement owner (§3.9) | Decided: LMS series; the CRM owns placement (later round) |

## 5. Integration rounds

Each round runs locally only: CRM `nipunacrm-dev` on :5050 → LMS `nipunalms-dev` on :5060. Never point this at real
student data until the service key, transport and retention are agreed.

### Round 1 — 1 Oct 2026

**CRM run:** backfill of 8 courses, 10 admissions and 10 finance summaries, plus one live payment verification. All 30
events were Applied; no 400 or 422. The CRM's fix list is `nipuna crm-docs/CRM_TO_LMS_FIXES_ROUND1.md`.

**LMS fixes (all done):**

| ID | Fix |
|---|---|
| F1 | The dev catalog holds the CRM's 8 courses with the CRM's codes, titles, categories, `is_combo = false` and status. The seed-only combo moved to `NIT-CRS-900` (tracks `NIT-CRS-900/T1`–`T3` + the `NIT-CRS-019` booster), a code the CRM doesn't use |
| F2 | `CourseUpserted` reconciles components (422 while in use) and a trigger keeps a single course from holding components |
| F3 | Instalments per invoice: `installments_scope`, `invoice_course_count`; one schedule per invoice on Fees & Receipts and in `GET /finance-summaries` `meta.totals` |
| F4 | `person_id`, `admission_id`, `complimentary_of_admission_id` aliases |
| F5 | Course title 255 characters; cancel reason unlimited |
| F6 | `seed_data` rows left out of the status pull (right after a rebuild the pull returns 0 of each) |
| F7 | "Activation link from" filter on Student Accounts; the reissue path is tested (§3.7 decision still open) |
| F8 | Full refresh confirmed and tested; `null` clears `email` / `name_te` |
| F9 | No change; see §3.12 |
| F10 | This document updated to the wire format |

`nipunalms-dev` was rebuilt and reseeded after the fixes, so the round-1 LMS student and enrolment codes are gone; the
CRM's next `flask lms backfill --force` creates new ones. Expected after it: 11 admissions, 10 students and 11 finance
summaries with numeric CRM IDs; 9 courses (the CRM's 8 + `NIT-CRS-900`). Admissions on `NIT-CRS-025`, `NIT-CRS-026` and
`NIT-CRS-052` wait in *Curriculum Mapping Pending* (no Active curriculum in the LMS). CRM admissions 6 and 7 share
invoice `INV-GNT-2627-0005` (`installments_scope = 'invoice'`, `invoice_course_count = 2`): Meera Joshi's Fees &
Receipts shows one schedule, with balances of ₹20,000 and ₹12,000.

### Round 2 — 1 Oct 2026

**CRM brief:** `nipuna crm-docs/CRM_ROUND2_BRIEF.md`: the CRM starts applying the status pull. **LMS reply:**
`nipuna crm-docs/CRM_ROUND2_LMS_REPLY.md`, which answers Q1–Q9, gives the LMS view on D1–D5 and lists what is pending on
the CRM side.

| ID | LMS change (db 095) |
|---|---|
| L1 | `as_of` comes from `crm_pull_as_of()`, below the oldest open transaction. Before, a change committing during a pull could be skipped forever |
| L2 | `admissions[]` filters on `admission_lms_state.changed_at` (status or last activity), so late-recorded activity is pulled |
| L3 | `lms_provisioned_at` uses the database clock |
| L4 | Batches, allocations and numbered certificates can't be deleted |
| L5 | `allocations[].track_code` |
| L6 | Indexes on the pull's change stamps |
| L7 | Seed curricula for `NIT-CRS-025` (`CV 2.0`) and `NIT-CRS-026` (`CV 1.2`); `NIT-CRS-052` stays unmapped (draft `CV 3.0` under review) |

Owner decisions (D1–D5): activation B now, A later; the LMS certificate series; `BranchUpserted`; the CRM pushes
`BranchFinanceSnapshot`; the CRM owns placement. The LMS side of D3 and D4 is built (db 096,
`tests/test_crm_branches_finance.py`).

Also built: the `allocation-escalation` job (§3.5), and a fix to `notify()`, which returned -1 instead of the number of
new recipients. Agreed with the CRM: pull, not push; drop and mirror the CRM's dev batches; no CRM-only *Deferred*;
trainer and authoriser emails stored as text when no CRM user matches.

`nipunalms-dev` was rebuilt and reseeded for db 095. The CRM then backfilled again (14:11 IST, 30 events, all Applied):
admissions 9 and 10 arrived *Mapped*, and admission 2 stays *Mapping Pending* until `CV 3.0` is activated. db 096 was
applied in place, without a rebuild.

**CRM side (`nipuna crm-docs/CRM_ROUND2_REPLY.md`):** the pull job, all the mirrors, read-only academic screens (409
`MANAGED_IN_LMS`), pause / resume, and *Deferred* removed. The first live pull applied 10 persons, 11 admissions and 11
academics, with nothing held. For its request R1, the LMS activated `NIT-CRS-052` `CV 3.0` and created GNT batches
`NIT-GNT-BAT-2026-000004` (047) and `…000005` (052), with CRM admissions 1 and 2 allocated. Still open on the CRM:
sending `BranchUpserted` and the `BranchFinanceSnapshot` job (D3 / D4), and activation-link delivery (D1, once
WhatsApp / email exists).

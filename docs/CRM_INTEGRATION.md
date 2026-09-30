# Nipuna LMS ↔ CRM integration

How the LMS and the CRM (`nipuna-crm`) are connected, checked against the CRM's own docs (`nipuna crm-docs/`:
DATABASE.md, API.md, PRODUCT_GUIDE.md, DEVELOPMENT.md) and its schema (db 001–025). Part 1 is the contract, Part 2 what
the LMS already does, Part 3 **what must change in the CRM** for the LMS to work.

---

## 1. Who owns what

The LMS prototype fixes the boundary: *"CRM is authoritative for Admission and finance; the LMS shows read-only, permitted
summaries only. LMS owns curriculum, batches, actual Class Sessions, content, assignments, tests, attendance, progress and
published results. Certificates come from one LMS Certificate Register."*

| Area | Owner | The other system |
|---|---|---|
| Leads, deals, fees, invoices, payments, receipts, admissions, refunds, collections | **CRM** | LMS keeps a read-only projection (admission, finance summary) |
| Person identity and documents (ID proof, photo…) | **CRM** | LMS keeps one Student per CRM Person |
| LMS login, activation, sessions | **LMS** | CRM shows `lms_user_id`, `lms_status` |
| Curriculum versions, mapping, batches, trainers, allocation, joining date, class sessions, attendance, progress, completion | **LMS** (Modules 14, 15, 21) | CRM mirrors the columns it already has (enrolment / curriculum status, batches, allocations, joining date, completion) |
| Certificates | **LMS** Certificate Register (Module 22) | CRM `certificates` becomes a mirror |
| Placement (employers, openings, applications) | **Decision needed** (§3.9) | |
| Support | CRM `support_cases` for money / admission; LMS support requests for academic / LMS | Cross-link (§3.10) |

## 2. The contract

### 2.1 CRM → LMS: events

`POST {LMS}/api/v1/integrations/crm/events` with header `X-Service-Key: <LMS CRM_SERVICE_KEY>`:

```json
{ "event_id": "uuid (unique, from the CRM outbox)", "event_type": "AdmissionQualified",
  "source_version": 7, "occurred_at": "2026-09-28T10:00:00+05:30", "data": { ... } }
```

- **Idempotent**: the same `event_id` returns the first result (200); the same `event_id` with a different payload is a 409.
- **Ordered by `source_version`** per record (course / admission / finance summary): a lower version than the one applied is stored as *Ignored — stale* and changes nothing, so retries and out-of-order delivery are safe.
- A failure (e.g. course not sent yet) is a 422, stored as *Failed*; sending the same event again retries it.
- IDs may be numbers; they are stored as text. The CRM's own column names and values are accepted as they are.

| Event | Send when (CRM code path) | `data` — CRM column → field |
|---|---|---|
| `CourseUpserted` | Course Master create / update; combo components change (`courses`, `combo_courses`). Send component courses before the combo | `course_code`, `course_title`, `category`, `is_combo`, `status` (Active / Inactive / Archived), `components[]` = `{component_course_code, is_bonus, sort_order}` (track codes are derived: `<combo>/T1…`, the bonus keeps its course code) |
| `AdmissionQualified` | An admission is created: auto on `POST /payments/{id}/verify` and `/allocate` (`admissions_created`), manual `POST /admissions`, `POST /admissions/{id}/complimentary` | `person`: `person_id`→`crm_person_id`, `person_code`, `full_name`, `phone`, `email` (optional), `preferred_language` (English / Telugu). `admission`: `admission_id`→`crm_admission_id`, `admission_code`, course code, `original_branch_code`, `service_branch_code`, `collecting_branch_code` (the collecting branch of the qualifying payment), `delivery_mode` (Classroom / Online / Hybrid), `seat_type`, `planned_start_date`, `admission_date`, `complimentary_of_admission_id`→`complimentary_of_crm_admission_id`, `access_until`. `enrolments` may be omitted (one course per CRM admission) |
| `AdmissionUpdated` | `admission_transfers` insert (service branch), delivery mode change, pause / resume | `crm_admission_id`, `service_branch_code`, `delivery_mode`, `status` (Active / Paused) |
| `AdmissionCancelled` | `POST /admissions/{id}/cancel` | `crm_admission_id`, `reason` |
| `FinanceSummaryUpdated` | After payment verify / fail, reversal (correction request approved), fee change applied, waiver, refund payout, invoice cancel | From `admission_balances` + `installment_dues` + verified `payments`: `fee_total` (final fee), `verified_paid`, `pending_verification`, `waived`, `refunded`, `balance` (outstanding), `payment_completion`, `invoice_numbers[]`, `installments[]` = `{installment_no, due_date, amount, covered, balance, due_position}`, `next_due_date`, `next_due_amount`, `receipts[]` = `{receipt_number, date, amount}` (verified only), `as_of` |

The `AdmissionQualified` response returns `lms_user_id`, `lms_status` and — once, for a new login only — `activation_token`.

### 2.2 LMS → CRM: what the CRM stores about the LMS

Two ways, both built in the LMS: **pull** `GET {LMS}/api/v1/integrations/crm/status?since=<ISO time>` (service key), or
**push** from the LMS `crm_outbox` (rows written in the same transaction as the change; a delivery worker waits for a CRM
endpoint — §3.2). Undelivered rows for the same admission / batch are superseded by the latest state.

| CRM column | LMS source | Pull key / outbox event |
|---|---|---|
| `persons.lms_user_id`, `lms_provisioned_at` | Student ID (`NIT-STU-2026-004182`), time the login was created | `persons[]` / `LmsAccountProvisioned` |
| `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at` | Not Created / Invited / Active / Inactive / Completed; last learning activity; pull time | `admissions[]` / `AdmissionLmsStatusChanged` |
| `admissions.enrolment_status` | LMS enrolment status → Awaiting Batch Allocation / Scheduled / In Progress / Paused / Completed / Cancelled | `academics[]` / `AdmissionAcademicsChanged` |
| `admissions.curriculum_status`, `curriculum_version_id` | Mapped / Mapping Pending + `curriculum_version_label` | same |
| `batch_allocations` (batch, status, `joining_date`, `ended_at`, `end_reason`) | `allocations[]` = `{course_code, lms_course_id, crm_batch_id, status (Active / Moved / Withdrawn / Completed), joining_date, allocated_on, ended_on, end_reason}` — per component course for a combo | same |
| `admissions.academic_completed_at` | Enrolment completed time | same |
| `batches` (+ `lms_course_id`) | `{lms_course_id = LMS batch_code, crm_batch_id, course_code, branch_code, delivery_mode, status (Planned / Open / In Progress / Completed / Cancelled), capacity, start_date, end_date, curriculum_version_label, lead_trainer_email, trainer_emails}` | `batches[]` / `BatchUpserted` (+ `BatchLinked` when a CRM batch is linked) |
| `certificates` | LMS Certificate Register | *Coming with the certificates slice* (`CertificateChanged`) |

### 2.3 Vocabulary mapping (done in the LMS)

| Field | CRM | LMS |
|---|---|---|
| Delivery mode | Classroom, **Online**, Hybrid | Classroom, **Live Online**, Hybrid |
| Language | English, Telugu | en, te |
| Enrolment status | Awaiting Batch Allocation · Scheduled · In Progress · Deferred · Paused · Completed · Cancelled | Provisioning / Curriculum Mapping / Allocation Pending · Allocated — awaiting first regular class · Active · Paused · Completed · Withdrawn |
| Batch status | Planned · Open · In Progress · Completed · Cancelled | Forming · Starting · Running · Full · Completed · Cancelled |
| Allocation status | Active · Moved · Withdrawn · Completed | Active · Transferred · Ended |
| Codes | Admission `NIT-GNT-2026-000001`, person `PER-GNT-00148`, batch `GNT-B-0001`, receipt `GNT-R-2627-00001` | Student `NIT-STU-2026-004182`, batch `NIT-GNT-BAT-2026-000001` (the CRM's `lms_course_id`) |

---

## 3. Changes required in the CRM

Numbered so they can be tracked. **3.1–3.4 are required for the LMS to work at all**; the rest remove double-entry and
conflicts.

### 3.1 Send events to the LMS (required)

- **Migration**: an `lms_outbox` table (event_id uuid, event_type, payload jsonb, record key, `source_version`, status, attempts, last_error, created_at, delivered_at) and a per-admission / per-course sync version (e.g. `admissions.lms_sync_version`, `courses.lms_sync_version`, incremented in the same transaction as the change).
- **Services**: write the events of §2.1 inside the same transaction as the change — `services/payments.py` (verify / allocate → `AdmissionQualified` for each created admission, then `FinanceSummaryUpdated`), `services/admissions.py` (manual create, complimentary, cancel, transfer, mode, fee change applied), `services/refunds.py` (payout), invoice cancel, payment correction approval, Course Master create / update.
- **Worker**: a job `lms-sync` in `flask jobs run` (Step 20) that posts pending rows to the LMS in order, marks them delivered, retries with backoff, and raises a task for the integration owner after repeated failure. Never hold the DB transaction open during the call (guide §17).
- **Config**: `LMS_BASE_URL` (dev `http://127.0.0.1:5060`), `LMS_SERVICE_KEY` (= the LMS `CRM_SERVICE_KEY`) in `backend/.env` / `.env.example`.
- **Backfill**: a one-off command that sends `CourseUpserted` for every course and `AdmissionQualified` + `FinanceSummaryUpdated` for every non-cancelled admission (original IDs, dates and branches; guide §18 "Historical migration").

### 3.2 Receive LMS status (required)

- A job `lms-status-pull` that calls `GET /integrations/crm/status?since=<last as_of>` every few minutes (store the watermark in `app_settings`), **or** an inbound endpoint `POST /api/v1/integrations/lms/events` (service key) for the LMS outbox to push to — pick one (BACKLOG).
- Apply: `persons.lms_user_id`, `lms_provisioned_at`; `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at`; the academic columns (3.3); batches (3.4).
- `PATCH /admissions/{id}` must stop accepting `lms_status` from staff (it becomes LMS-owned); the **LMS access** screen (`/lms-access`) keeps its read-only list, now with real values and a "last synced" time.

### 3.3 Academic columns become an LMS mirror (required)

Apply `AdmissionAcademicsChanged` to `admissions.enrolment_status`, `curriculum_status`, `curriculum_version_id`
(match `curriculum_version_label` + course, creating a Published mirror row if missing), `batch_allocations`
(`joining_date`, status, `ended_at`, `end_reason`), `academic_completed_at`. The CRM's triggers need a system path:

- `admissions_completion` requires `completion_authorised_by` (a CRM user) — allow a sync source (e.g. `completion_source = 'LMS'` + the LMS authoriser's email) or map the email to the CRM user.
- Allocation triggers (same service branch, curriculum Mapped, capacity, one active per course) must accept LMS-confirmed allocations as facts, not re-validate them.
- The "first allocation → Scheduled, joining date → In Progress" triggers must not fight the mirrored status (apply the status after the allocation, or disable those triggers for the sync session, e.g. `SET LOCAL app.sync_source = 'LMS'`).

### 3.4 Batches become an LMS mirror (required)

- Upsert CRM `batches` from `BatchUpserted` keyed by `lms_course_id` (= LMS `batch_code`); map `lead_trainer_email` → `trainer_user_id`; status / mode vocabularies per §2.3. `batch_code` stays the CRM's own (`GNT-B-0001`).
- Allow a batch for a combo **component** course only (as today) — the LMS allocates combo students per track to component-course batches.
- Existing CRM batches: link each to its LMS batch once (set `crm_batch_id` in the LMS), after which the CRM stops editing them.

### 3.5 Retire double entry in the CRM (after 3.3 / 3.4)

Make these read-only (or remove the buttons) and link to the LMS: `POST/PATCH /batches`, `POST /admissions/{id}/allocations`, `POST /batch-allocations/{id}/close`, `POST /batch-allocations/{id}/joining-date`, `POST /curriculum-versions`, `/publish`, `POST /admissions/{id}/curricula`, `POST /admissions/{id}/complete`, `POST /admissions/{id}/certificates`, `/certificates/{id}/issue`, `/revoke`. Jobs: `batch-allocation` escalation moves to the LMS. The Academic Coordinator and Trainer role screens in the CRM (Batches, allocation queue, joining date) become views; their academic work happens in the LMS. Update the CRM ROLE_GUIDE / PRODUCT_GUIDE accordingly.

### 3.6 Certificates

The LMS register numbers certificates `NIT-CERT-2026-000001` (prototype); the CRM numbers `GNT-C-2627-00001`. Decide one series (recommended: the LMS register's, since it owns issue, reissue and revoke) and mirror LMS certificates into CRM `certificates` read-only, for Student 360 and alumni.

### 3.7 Student activation delivery

A new LMS login comes with a one-time activation token in the `AdmissionQualified` response. Either the CRM delivers the link (`{LMS}/activate?token=…`) to the student through its communications (WhatsApp / email, never stored or logged), or activation stays supervised in the LMS (Academic Coordinator reissues a link). Decide which; if the CRM sends it, add a communication template and task.

### 3.8 Staff accounts

Trainers, Academic Coordinators, Branch Managers and admins need LMS accounts too. Use the **same email** in both systems (the LMS reports trainers and authorisers by email). Later: single sign-on or user provisioning from the CRM.

### 3.9 Placement (decision)

The CRM already runs placement (companies, job openings, placement profiles, applications, alumni) for the Placement Team; the LMS prototype has a student-facing Career screen (profile, CVs, opportunities, applications). Recommended: the CRM stays the owner of employers, openings and applications; the LMS Career screen reads approved openings and submits applications / CVs to the CRM (new CRM service endpoints), so there is one placement record.

### 3.10 Support

CRM `support_cases` (money, admission, complaints) and LMS support requests (academic, LMS, recordings, devices) stay separate but should cross-link: an LMS request that is really a fee question is routed to a CRM support case (and vice versa) with both references stored.

### 3.11 Small fixes found while aligning

- Send IDs consistently (numbers are fine); keep `admission_code`, `person_code`, `receipt_number` in payloads for display.
- Include `collecting_branch_code` on the admission payload (the CRM backlog lists "collecting branch on admissions" as not shown yet).
- `curriculum_versions` in the CRM are per course only; LMS combos have per-track versions — the mirror should store the parent programme label.

---

## 4. Status in the LMS

| Item | Status |
|---|---|
| Event intake, idempotency, versions, retry, inbox screen | ✅ (db 003, `/integrations/crm/events`) |
| CRM vocabulary and shapes (Online, English / Telugu, `phone`, `course_title`, `combo_courses` components, Archived, one course per admission, complimentary as its own admission, seat type, planned start, access until, full finance balances + instalments) | ✅ (db 005, `tests/test_crm_alignment.py`) |
| LMS → CRM: provisioning, `lms_status`, academics, batches (pull + outbox) | ✅ (db 003, 005) |
| Outbox delivery worker | ⏳ waits for 3.2 |
| Certificates to the CRM | ⏳ with the certificates slice |

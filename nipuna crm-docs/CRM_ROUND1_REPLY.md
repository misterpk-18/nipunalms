# CRM → LMS live data: round 1 reply from the CRM

> **Superseded for action by [CRM_TO_LMS_FIXES_ROUND1.md](CRM_TO_LMS_FIXES_ROUND1.md)**, the full fix list with code locations, tests and acceptance checks. This file is the short summary.

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Answers:** [docs/CRM_LOCAL_SETUP.md](../docs/CRM_LOCAL_SETUP.md) §9, against the contract in [docs/CRM_INTEGRATION.md](../docs/CRM_INTEGRATION.md) §2.1.
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 → LMS `nipunalms-dev` on :5060.

**In short:** round 1 is done on the CRM side and live data is flowing. There were 30 events and every one was delivered with `Applied`. No 400 or 422 came back. The only 409 was the one the smoke test causes on purpose. §5 lists 6 changes the LMS should make; the first two are real data problems. §6 has 3 decisions for the LMS owner, and §7 has 2 proposals for the dashboards that are *Not Configured*.

---

## 1. Round 1 checklist (CRM_LOCAL_SETUP §8)

| Item | Status |
|---|---|
| `lms_outbox` migration, sync-version counters, `LMS_BASE_URL` / `LMS_SERVICE_KEY` config | ✅ CRM `db/026_lms_outbox.sql` (dev DB only); config in `backend/.env` and `.env.example` |
| Events written in the same transaction as the change | ✅ All paths in §2.2 below |
| Worker with the §3 response handling; one failing row never blocks other admissions | ✅ Job `lms-sync` in `flask jobs run`, or `flask lms deliver --loop` |
| Backfill run against the local CRM database | ✅ `flask lms backfill`: 8 courses, 10 admissions, 10 finance summaries |
| Smoke test §5 | ✅ 201 Applied → 200 `replayed: true` → 409 on a changed title. A wrong key gives 401 |
| One real payment verification shows up in the LMS | ✅ Sana Begum's ₹5,000 claim on `INV-VIJ-2627-0004` was verified in the CRM. That created CRM admission 11 (`NIT-VIJ-2026-000004`). In the LMS it became student `NIT-STU-2026-004284`, enrolment `ENR-000106` (Allocation Pending), and a finance summary of ₹22,000 fee, ₹5,000 paid, ₹17,000 balance, receipt `VIJ-R-2627-00004` |
| Status pull (§7) returns 200 | ✅ `GET /integrations/crm/status` → 200 (`persons` 103, `admissions` 106, `academics` 106, `batches` 5, `certificates` 4). The CRM does not apply it yet (round 2) |

## 2. What the CRM sends

### 2.1 Envelope

It matches §3 of the brief exactly:

- `event_id` is a uuid4, generated once and stored.
- `occurred_at` is in IST with an offset.
- `source_version` comes from a CRM counter table (`lms_sync_versions`) with one counter per record: `course:<crm course_id>`, `admission:<crm admission_id>`, and `finance:<crm admission_id>`. The finance summary is versioned separately from the admission, the same way the LMS versions them.

A database trigger makes the envelope (`event_id`, type, version, `occurred_at`, payload) impossible to change once written. So every retry of an event is byte-for-byte the same request. A changed record always gets a new event with a higher version.

### 2.2 When each event is written

| Event | CRM code path |
|---|---|
| `CourseUpserted` | Course create, course update, combo components set |
| `AdmissionQualified` | Any new admission: automatic on payment verify / allocate, manual `POST /admissions`, or complimentary. **Also re-sent as a full refresh** (next version) in two cases: `planned_start_date` changes, or the person's name / phone / email / language is edited. Not sent for cancelled admissions |
| `AdmissionUpdated` | Service-branch transfer sends `service_branch_code`. A delivery-mode change sends `delivery_mode` |
| `AdmissionCancelled` | Admission cancelled; `reason` is the CRM's cancellation reason |
| `FinanceSummaryUpdated` | Any of: payment **recorded** (it adds to pending verification), verified, failed, allocated; correction approved (reversal); fee change applied; refund decided (waiver); refund payout; invoice cancelled; instalment due date changed. Sent for **every admission on the invoice** |

Within one CRM transaction, each record produces one event. They are written in this order: courses → qualified → updated → cancelled → finance, with a paid admission before its complimentary one.

### 2.3 Payload details the LMS should know

- **IDs.** The CRM sends `crm_person_id`, `crm_admission_id` and `complimentary_of_crm_admission_id` under those exact names, as integers. See §4.1 for why it doesn't use `person_id` / `admission_id`.
- **Money** is sent as strings (`"17000.00"`). Dates are `YYYY-MM-DD`.
- **`collecting_branch_code`** is the collecting branch of the admission's invoice. A complimentary admission uses its paid admission's invoice.
- **`receipts[]`** lists verified, non-reversed payments on this admission's course line. `amount` is only the part of the payment **allocated to this course**: one payment can cover two courses on a multi-course invoice. `date` is the payment date, not the verification date.
- **`installments[]` are per invoice, not per course.** On a two-course invoice, both admissions carry the same schedule. See §5.2. Two extra fields flag this: `installments_scope: "invoice"` and `invoice_course_count` (your validator ignores them).
- **`next_due_date` / `next_due_amount`** come from the first instalment that still has a balance. That instalment can already be overdue.
- **`balance`** is the CRM's `outstanding`. It is 0 for a cancelled admission.
- **Activation tokens.** `activation_token` is never logged or stored. The CRM keeps only `activation_token_issued = true` on the outbox row (see §6.1).

Real example (CRM admission 11, as delivered):

```json
{"event_type": "AdmissionQualified", "source_version": 1, "data": {
  "person": {"crm_person_id": 22, "person_code": "PER-VIJ-00010", "full_name": "Sana Begum",
             "phone": "+919876500022", "email": "sana.begum@example.test", "preferred_language": "English"},
  "admission": {"crm_admission_id": 11, "admission_code": "NIT-VIJ-2026-000004", "course_code": "NIT-CRS-019",
                "original_branch_code": "NIT-VIJ", "service_branch_code": "NIT-VIJ", "collecting_branch_code": "NIT-VIJ",
                "delivery_mode": "Classroom", "seat_type": "Confirmed Seat", "planned_start_date": null,
                "admission_date": "2026-10-01", "complimentary_of_crm_admission_id": null, "access_until": null}}}

{"event_type": "FinanceSummaryUpdated", "source_version": 1, "data": {
  "crm_admission_id": 11, "fee_total": "22000.00", "verified_paid": "5000.00", "pending_verification": "0.00",
  "waived": "0.00", "refunded": "0.00", "balance": "17000.00", "payment_completion": "Part Paid",
  "invoice_numbers": ["INV-VIJ-2627-0004"],
  "installments": [{"installment_no": 1, "due_date": "2026-09-29", "amount": "11000.00", "covered": "5000.00", "balance": "6000.00", "due_position": "Overdue"},
                   {"installment_no": 2, "due_date": "2026-10-11", "amount": "11000.00", "covered": "0.00", "balance": "11000.00", "due_position": "Upcoming"}],
  "installments_scope": "invoice", "invoice_course_count": 1,
  "next_due_date": "2026-09-29", "next_due_amount": "6000.00",
  "receipts": [{"receipt_number": "VIJ-R-2627-00004", "date": "2026-09-29", "amount": "5000.00"}],
  "as_of": "2026-10-01T00:18:03.477586+05:30"}}
```

### 2.4 Delivery behaviour

- **Order.** Each run takes the **oldest Pending row of each record** (a course, or an admission together with its finance summary). A record's rows go one at a time, so an admission's finance never overtakes its `AdmissionQualified`. A waiting admission never blocks any other admission.
- **No open transaction during HTTP.** Rows are claimed with a 5-minute lease, the claim is committed, the event is posted, and the answer is recorded and committed per row.
- **201 / 200.** The row becomes Delivered. The CRM stores your `status` and `result`.
- **400 / 409.** The row becomes Failed and a Super Admin task is raised in the CRM. The CRM fixes its mapping and resends the record as a **new** event.
- **422 and 5xx.** The row stays Pending and is retried with backoff (30 s doubling, capped at 1 h). After 12 attempts it becomes Failed and raises a task.
- **No answer, or 401 / 403 / 404 / 405.** The run stops. The row stays Pending (for 401 / 403 / 404 / 405 the attempt isn't counted).
- **A Failed row does not hold back later rows of the same admission.** So if an `AdmissionQualified` fails with 400, that admission's finance rows will get your 422 until it is fixed.

## 3. Outbox after the backfill, plus one live verification

| Status | CourseUpserted | AdmissionQualified | FinanceSummaryUpdated |
|---|---|---|---|
| Delivered (all `Applied`) | 8 | 11 | 11 |
| Pending / Failed | 0 | 0 | 0 |

- **Logins.** 10 `activation_token`s were issued, one per new student login. Meera Joshi has two admissions and one login. The CRM kept none of the tokens.
- **Warnings.** Every `AdmissionQualified` result had `warnings: []`.
- **Enrolment status.** Admissions 2, 9 and 10 came back as `Curriculum Mapping Pending` (courses NIT-CRS-052 and NIT-CRS-025 have no active LMS curriculum yet). The other 8 came back as `Allocation Pending`.

The backfill left out cancelled admissions. The dev database has none, and `flask lms backfill --include-cancelled` sends them, qualified first and then cancelled.

## 4. Responses seen, and contract points the CRM couldn't follow as written

**400 / 422 bodies:** none. The only error bodies were the ones the smoke test is designed to produce: 409 `{"code": "CONFLICT", "message": "This event_id was already used with a different payload"}` and 401 for a wrong key.

### 4.1 `person_id` / `admission_id` are not aliased in the LMS

The brief says `person_id→crm_person_id` and `admission_id→crm_admission_id`, and its "minimal `AdmissionQualified`" example sends `person_id` and `admission_id`. But `controllers/crm.py` `FIELD_ALIASES` only maps `phone`, `course_title` and `delivery_mode`. Sent as in the brief's example, that payload would fail with 400: `crm_person_id` / `crm_admission_id` required. The same applies to `complimentary_of_admission_id`.

**The CRM sends the `crm_…` names, so nothing breaks today.** Either add the three aliases or correct the example in CRM_LOCAL_SETUP §4 / CRM_INTEGRATION §2.1.

### 4.2 Pause / resume can't be sent

The CRM has no pause or resume action; the `enrolment_status` Paused value exists, but nothing sets it. So `AdmissionUpdated.status` is never sent. The CRM will add it when a pause action exists.

### 4.3 `AdmissionUpdated` has no field for start date, seat type or person details

`planned_start_date` changes and person edits (name / phone / email / language) are sent as a repeated `AdmissionQualified` with a higher version. From your `_admission_qualified` code, that updates the admission and the student, doesn't reissue a login, and doesn't reset an enrolment that is already being served.

**Please confirm this "full refresh" use is intended.** If not, add `planned_start_date` / `seat_type` to `AdmissionUpdated` and a `PersonUpdated` event.

Note that `_upsert_student` skips `None` values, so the CRM can't clear a student's email this way.

### 4.4 `standard_fee` and course branches are not sent

`CourseUpserted` carries what §2.1 lists. Tell the CRM if the LMS wants the course's standard fee or the branches offering it; both are in the CRM Course Master.

## 5. Changes requested in the LMS

| # | Priority | Change | Why |
|---|---|---|---|
| 5.1 | **High** | `CourseUpserted` should **remove components that are not in the event**, or drop all of them when `is_combo` is false | LMS dev had `NIT-CRS-018` seeded as a combo with 4 components. The CRM's course is not a combo, so the LMS now has `is_combo = false` with 4 orphan components (checked in `nipunalms-dev`: `course_components` for `NIT-CRS-018` = 4). Enrolments on 018 may be mapped per track because of them |
| 5.2 | **High** | Treat `installments[]` as the **invoice's** schedule. Show it once per invoice and don't sum it across a student's admissions | Meera Joshi's admissions 6 and 7 share `INV-GNT-2627-0005`, and both carry the same 2 instalments. Any per-student total of dues would double. `invoice_numbers` + `installments_scope: "invoice"` identify the case. If the LMS wants a per-course split instead, say so; that is a CRM product decision (§6.2) |
| 5.3 | Medium | Add the aliases in §4.1, or fix the brief's example | The brief's example payload returns 400 today |
| 5.4 | Medium | The dev status pull returns seeded students / admissions with fake CRM IDs (`CRM-ADM-214` …, 103 persons) | When the CRM starts applying the pull (round 2), it will ignore IDs it doesn't have. A clean dev seed (or a flag on seeded rows) will make the round-2 test meaningful |
| 5.5 | Low | Branch codes: the LMS refuses an unknown branch with 422, and there is no branch event | `NIT-GNT` and `NIT-VIJ` match today. A new CRM branch must be created in the LMS first. Tell the CRM if you want a `BranchUpserted` event |
| 5.6 | Low | Return `activation_token` only when the CRM will deliver it (§6.1), or accept that the CRM discards it | 10 tokens have been discarded so far. Those students can only activate through an LMS reissue |

## 6. Decisions needed (LMS owner and CRM owner)

1. **Student activation link (CRM_INTEGRATION §3.7).**
   - Today: the CRM discards the token. Only `activation_token_issued` is kept, and the token is never logged.
   - Option A: the CRM delivers `{LMS}/activate?token=…` by WhatsApp or email. That needs a CRM template and task, and a decision on whether the token may sit in the CRM outbox until it is sent.
   - Option B: activation stays supervised in the LMS (a coordinator reissues links).
2. **Instalments on multi-course invoices** (see 5.2): show them per invoice, or have the CRM apportion them per course.
3. **Round 2 direction for the LMS → CRM data.** Pull or push (CRM_INTEGRATION §3.2).
   - The CRM's plan is a pull job, `lms-status-pull`, with a watermark in `app_settings`. It would store `persons.lms_user_id`, `admissions.lms_status` / `lms_last_*`, and then the academic, batch and certificate mirrors (§3.3–3.6).
   - `PATCH /admissions` stops accepting `lms_status` from staff at the same time.
   - Say if you'd rather push to a CRM endpoint.

## 7. Data the CRM can supply for the *Not Configured* dashboards

None of this is in §4 of the brief yet. Pick what you need, then the CRM will add it.

| Dashboard need | CRM source |
|---|---|
| Collections vs target | `target_versions` (Approved, `period_start` / `period_end`) + `target_lines` (`branch_id`, `verified_collections_target`, `paid_admissions_target`). Achieved = verified payments in the period and new paid admissions (the date the ₹1,000 token was reached) |
| Overdue amounts | `installment_dues` view (`balance`, `due_position = 'Overdue'`, `days_overdue`, `age_band`, `contact_hold`) per invoice / branch. Also `payment_gaps` (`gap_days`, `outstanding`, `next_due_*`) |
| Payment verifications | `payments` with `verification_status = 'Pending Verification'`: count, amount and the oldest `created_at` per `collecting_branch_id`. There is also a 30-staffed-minute SLA task (`PAYMENT_VERIFICATION`) |
| Promises to pay | `payment_promises` (per invoice: promised date and amount, status Pending / Kept / Broken) |

**Proposal:** a CRM job every 15 minutes writes one `BranchFinanceSnapshot` event per branch into the same outbox. It would carry targets vs achieved for the current period, overdue totals by age band, the pending verification count / amount / oldest, and the number of broken promises, keyed `branch:<code>` and versioned like the others. The alternative is for the LMS to pull a CRM endpoint. Tell the CRM which one you prefer, and the exact fields and shape the LMS validator should accept.

The CRM also has batches, allocations, curricula and certificates, but under CRM_INTEGRATION §1 those are LMS-owned. The CRM won't send them, and will mirror the LMS's versions instead.

## 8. Checking it on the LMS side

- **Where to look.** The LMS Super Admin screen **CRM sync** (`/admin/crm-sync`) should show 30 CRM events plus the two smoke events (`crm-smoke-…`). All 30 are Applied.
- **Checks already run in `nipunalms-dev`.** For admissions with a numeric `crm_admission_id` 1–11:
  - `admissions` holds 11 rows.
  - `students` holds 10 (Meera Joshi has two admissions).
  - `finance_summaries` holds 11, with fee, paid and balance equal to the CRM's `admission_balances`.
- **How the CRM side runs it**, from `nipuna-crm/backend` with `APP_ENV=development`:
  - `flask --app app lms backfill` writes the events.
  - `flask --app app lms deliver --loop` (or `flask jobs run lms-sync`) delivers them.
  - `flask --app app lms outbox --failed` shows counts and errors.
  - `flask --app app lms requeue [id…]` sends Failed rows again unchanged, after an LMS fix.
  - `flask --app app lms backfill --admission <id> --force` sends a record again as a new event, after a CRM mapping fix.
  - `flask --app app lms status-check` calls the status pull once.
- **Full description on the CRM side:** `nipuna-crm/docs/API.md` Step 22 and `docs/DATABASE.md` "LMS outbox (026)".

Reply with corrections to §4–§7. The CRM side will then do round 2: whatever you change in 5.x, plus the decisions in §6 and the dashboard data in §7.

# LMS → CRM: round 2 reply from the LMS

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Answers:** [CRM_ROUND2_BRIEF.md](CRM_ROUND2_BRIEF.md) §3 (Q1–Q9) and §4 (D1–D5).
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** every question has an answer below, and the LMS made seven changes (db `095_crm_round2.sql`). The
important one is **L1**: until now, `as_of` could skip a change that was being committed while you pulled. That is
fixed, so the watermark you store is now safe. The pull's shape is unchanged except for one new field,
`allocations[].track_code`. The owners also decided D1–D5 (§3), and the LMS has built its side of D3 and D4: it now
accepts `BranchUpserted` and `BranchFinanceSnapshot` (db `096_crm_branches_finance.sql`). Your backfill into the rebuilt
`nipunalms-dev` (14:11 IST, 30 events, all Applied) already shows the expected states. The open work on the CRM side
is in §4.

---

## 1. What the LMS changed

| # | Change | Why |
|---|---|---|
| L1 | `as_of` is now read from the database before the rows and kept just below the start of the oldest transaction still open (`crm_pull_as_of()`) | Before, `as_of` was the API's clock. A transaction still open during your pull could commit rows stamped earlier than `as_of`, and no later pull would return them |
| L2 | `admissions[]` now filters on one change stamp (`admission_lms_state.changed_at`). It moves whenever `lms_status` or `lms_last_activity_at` changes | Before, it filtered on the activity time itself. Activity recorded late, with an earlier `occurred_at`, was never pulled |
| L3 | `persons[].lms_provisioned_at` is stamped by the database clock | Every pull filter now uses one clock |
| L4 | The database refuses to delete batches, allocations and numbered certificates | Q2: so a removal is always a status change you can see |
| L5 | `academics[].allocations[].track_code` (new; `null` for a single course) | Q4 |
| L6 | Indexes on every change stamp the pull filters on | Q9 |
| L7 | Seed: Active curricula for `NIT-CRS-025` (`CV 2.0`) and `NIT-CRS-026` (`CV 1.2`). `NIT-CRS-052` stays unmapped on purpose | Q7 |

The LMS also has a new job, `allocation-escalation` (`flask --app app jobs run allocation-escalation`). It does what
your `batch-allocation` job does today: an enrolment still without a batch 24 hours before its admission's
`planned_start_date` (IST) is raised once to the service branch's Branch Managers (brief §2.3). Retire the CRM's job when
the academic screens become read-only.

Tests: `backend/tests/test_crm_round2.py` and `test_crm_branches_finance.py`; all 588 LMS backend tests pass.

## 2. Answers

### Q1 — Pull semantics

- **What `since` filters on.** Each key filters on its row's own change time: `persons` on `lms_provisioned_at`,
  `admissions` on `changed_at` (L2), `academics` on `academic_changed_at`, `batches` on `changed_at`, and
  `certificates` on the certificate's `updated_at`. The comparison is strict (`> since`). The database sets every
  stamp.
- **Storing `as_of` as the next `since`.** Yes, since L1. Store it **exactly as returned**: it has microseconds and an
  offset. URL-encode `+` as `%2B`; a space in its place is also accepted.
- **Repeats.** Because of L1, `as_of` can be a little earlier than the current time, so a row can come back in two pulls
  in a row. Apply idempotently. No row is ever skipped.
- **Full state, not a diff.** Every entry is the record's whole current state. If the same record appears again, the
  later copy wins.
- **Paging.** There is no page size, limit or continuation. One response holds everything changed since `since`; leave
  `since` out for a full pull (it defaults to 1970). See Q9 for sizes.
- **Failed pull.** If the pull fails (LMS down, 5xx, 401), keep the old watermark. Nothing on the LMS side depends on
  the CRM having pulled.

### Q2 — Deletes and removals

Nothing the pull reports is ever deleted. Since 095 the database refuses it (L4). A removal always reaches you as a
status:

| Record | How it ends |
|---|---|
| Batch | `status: Cancelled` (or `Completed`) |
| Allocation | `status` becomes `Moved`, `Withdrawn` or `Completed`, with `ended_on` and `end_reason` |
| Certificate version | `status` becomes `Superseded` (by a reissue) or `Revoked` |
| Admission | `enrolment_status: Cancelled` after `AdmissionCancelled` |

`academics[].allocations` is always the **complete** allocation history of that admission, never a partial list.
Replace the admission's whole set with it. Unnumbered certificate drafts are never reported, and the LMS may delete
them.

### Q3 — Enrolment status mapping and *Deferred*

The mapping in CRM_INTEGRATION §2.3 is confirmed:

| LMS enrolment status | CRM `enrolment_status` |
|---|---|
| Provisioning Pending, Curriculum Mapping Pending, Allocation Pending | Awaiting Batch Allocation (use `curriculum_status` to tell *Mapping Pending* from *Mapped*) |
| Allocated — awaiting first regular class | Scheduled |
| Active | In Progress |
| Paused | Paused |
| Completed | Completed |
| Withdrawn | Cancelled |

**Please don't keep *Deferred* as a CRM-only value.** The pull sends `enrolment_status` every time an admission's
academics change, so it would overwrite *Deferred* anyway. Keeping it would also give one column two owners. Nothing
in the CRM sets *Deferred* today: it appears only in the enum (CRM db 005) and in the "is also active" view (db 008).

To defer a student, pause them in the LMS. Send `AdmissionUpdated` with `status: Paused`, and `status: Active` to
resume. The LMS already handles both, and the pull then reports *Paused*. The CRM has no pause action yet, so that is
CRM work. If the owners want a "deferred start" that differs from a pause, raise it as a new decision; the LMS would
need a new status.

### Q4 — Combo allocations

Store **one row per track**: relax the one-active rule to one active allocation per admission and track. Key each
allocation by `crm_admission_id` + `track_code` (or `course_code` when `track_code` is null) + `allocated_on`.

Two corrections to CRM_INTEGRATION §3.4, now fixed in that doc:

1. **Batches.** In the LMS, a combo's tracks are allocated to batches **of the combo course itself**. The LMS database
   refuses a batch of any other course. So a combo allocation's `lms_course_id` points to a batch whose `course_code`
   is the combo's code. The CRM must accept a mirrored batch on a combo course; today it allows only component-course
   batches.
2. **`course_code`.** An allocation's `course_code` is the track's component course. For a track with no course of its
   own, it is the combo's code, so two tracks can share one `course_code`. That is why `track_code` was added (L5).

None of the CRM's 8 courses is a combo today, so this only matters once the CRM creates one.

### Q5 — Linking existing CRM batches

**Agreed: drop and mirror.** Delete your dev batches and mirror the LMS batches by `lms_course_id` (the LMS
`batch_code`). The LMS doesn't need `crm_batch_id`: it stays `null` on batches made in the LMS. The LMS still accepts
`crm_batch_id` on `POST/PATCH /batches` and in enrolment items, but there is nothing to link.

After you drop them, **stop sending `crm_batch_id`** in `AdmissionQualified` / `AdmissionUpdated`. The LMS would only
answer with the warning "not linked to an LMS batch yet". Allocations are made in the LMS.

Watch out for **seed batches.** The five seed batches (`NIT-GNT-BAT-2026-00000x`, `NIT-VIJ-BAT-2026-00000x`) are seed
data, so `batches[]` never includes them. If a coordinator allocates a real admission to one, `allocations[]` will name
a batch you never received. For the round-2 tests, create new batches in the LMS (Academic → Batches). On the CRM side,
hold such an allocation for retry instead of failing the whole pull.

### Q6 — Trainer and authoriser identity

**Agreed:** store the email in a text column and leave the user id empty when no CRM user matches. Never reject the
row. The allocation, completion or certificate is a fact in the LMS whether or not the CRM knows the person.

- Every LMS staff account has an email; the database requires one for any login that isn't a student's.
- Emails are unique ignoring case but stored as typed, so match on `lower(email)`.
- `completion_authorised_by_email` is `null` until the course is Completed. `revoked_by_email` is `null` unless the
  certificate is Revoked.
- To get matches, use the same email for staff in both systems (CRM_INTEGRATION §3.8).

### Q7 — Curricula for the three waiting courses

`NIT-CRS-025` (`CV 2.0`) and `NIT-CRS-026` (`CV 1.2`) are now seeded as Active (L7). After your backfill:

- Admission 9 (`NIT-CRS-025`, GNT) and admission 10 (`NIT-CRS-026`, VIJ) arrive as *Mapped*, *Awaiting Batch
  Allocation*.
- Admission 2 (`NIT-CRS-052`, GNT) stays *Mapping Pending* on purpose, so you can test the change to *Mapped*.
  `NIT-CRS-052` has a draft `CV 3.0` under review. Approve and activate it in the LMS (Academic → Curriculum). Admission 2
  then moves to *Mapped*, *Awaiting Batch Allocation*, and shows up in the next pull.
- No LMS batch exists yet for `NIT-CRS-025`, `026` or `018`, nor for `019` / `007` at GNT. Create the batches you need
  in the LMS. That also tests `batches[]` (Q5).

### Q8 — `lms_status` timing

Confirmed, with three details:

- **Not Created → Invited.** This happens when the login is created, which is in the same transaction as the student.
  So no backfilled admission ever shows *Not Created* in the pull: the first state you see is *Invited*.
- **Invited → Active.** This happens on activation, if the admission has an open course: any status except Paused,
  Completed or Withdrawn, including one still waiting for a curriculum or a batch. *Active* means "can sign in and has
  an open course", not "is attending".
- **Other transitions.** *Inactive* means the login is suspended, or every course is Paused / Withdrawn. *Completed*
  means every non-withdrawn course is Completed, and this can happen before activation. Reissuing an activation link
  keeps *Invited*.

`lms_last_activity_at` moves with every learning activity (logins, resource views and so on). An admission therefore
appears in `admissions[]` after activity even when its status didn't change, at most once per pull.

### Q9 — Rate and size

Measured on the dev seed (bytes of JSON per entry):

| Key | Average | Notes |
|---|---|---|
| `persons[]` | ~120 | once per student |
| `admissions[]` | ~150 | |
| `academics[]` | ~520 | grows with allocation history; largest seen 552 |
| `batches[]` | ~370 | |
| `certificates[]` | ~530 | per numbered version |

A full pull for 10,000 admissions, 300 batches and 5,000 certificate versions is about **11 MB**, in one request.
Do it once at the start, not repeatedly. After that, pulls hold only what changed, mostly `admissions[]` rows from
student activity. **Polling every 2–5 minutes is fine**; the filters are indexed (L6). Suggestion: every 5 minutes.

## 3. Decisions D1–D5 (decided by the owners, 1 Oct 2026)

| # | Decision | What it means |
|---|---|---|
| D1 Activation link | **B now, A later** | Coordinators reissue activation links in the LMS. The LMS keeps returning `activation_token`; keep discarding it. When the CRM's WhatsApp / email delivery is live, the CRM switches to delivering `{LMS}/activate?token=…` (option A). The switch needs no LMS change, and the token must never be logged or stored in plaintext |
| D2 Certificate series | **The LMS series** (`NIT-CERT-2026-…`) | Mirror LMS certificates read-only and add *Superseded*. The pull already reports *Superseded* and *Revoked* versions under the same `certificate_number` |
| D3 Branches | **`BranchUpserted` event** | **Built in the LMS** (db 096). Fields are in §3.1 below |
| D4 Dashboard finance | **The CRM pushes `BranchFinanceSnapshot`** | **Built in the LMS** (db 096). Fields are in §3.2 below. The dashboard tiles stay *Not Configured* until your job sends the first snapshot |
| D5 Placement | **The CRM owns it** | The LMS Career screen will read openings and submit applications / CVs through new CRM service endpoints, in a later round |

### 3.1 `BranchUpserted` (send from your outbox; versioned per branch, e.g. `branch:<id>`)

Send your own column names; the LMS maps them:

```json
{ "branch_code": "NIT-TEN", "branch_name": "Tenali", "city": "Tenali",
  "receipt_prefix": "TEN", "email": "tenali@nipunacareers.com", "is_active": true }
```

- **Fields.** `receipt_prefix` becomes the LMS `short_code`, which the LMS puts inside batch codes. `email` becomes the
  branch's shared `mailbox`. Other columns (`address`, `phone`, `legal_name`, …) may be sent and are ignored.
- **A new branch** needs `receipt_prefix` and `email`, and the prefix must be free. Otherwise the event gets a 422.
- **An existing branch** keeps its short code: a different `receipt_prefix` is a 422, because every batch code issued
  there contains it. A `null` email keeps the LMS mailbox.
- **Order.** Send it before the branch's first admission; otherwise that admission's `AdmissionQualified` gets a 422
  until it arrives.
- **Backfill.** Send it once for `NIT-GNT` and `NIT-VIJ`. Their LMS short codes `GNT` / `VIJ` already equal your
  `receipt_prefix`.

### 3.2 `BranchFinanceSnapshot` (a CRM job every 15 minutes, one event per active branch, e.g. `branch-finance:<id>`)

```json
{ "branch_code": "NIT-GNT", "as_of": "2026-10-01T10:00:00+05:30",
  "period": { "label": "Oct 2026", "start": "2026-10-01", "end": "2026-10-31" },
  "collections": { "verified": "120000.00", "target": "500000.00" },
  "paid_admissions": { "count": 12, "target": 40 },
  "overdue": { "amount": "45000.00", "count": 7,
               "by_age_band": [{ "band": "1-30 days", "amount": "30000.00", "count": 5 }] },
  "verifications": { "pending_count": 3, "pending_amount": "15000.00", "overdue_count": 1,
                     "oldest_at": "2026-10-01T09:00:00+05:30" },
  "followups": { "overdue_count": 5, "broken_promises": 2 } }
```

- **Sources.** `period` and the targets come from the Approved `target_versions` / `target_lines`. `collections.verified`
  is verified payments in the period; `paid_admissions.count` is new paid admissions in the period (the ₹1,000 token
  reached). `overdue` comes from `installment_dues` with `due_position = 'Overdue'`, grouped by `age_band`.
  `verifications` covers payments in *Pending Verification*; `overdue_count` is those past the `PAYMENT_VERIFICATION`
  SLA. `followups` counts overdue follow-up tasks plus `payment_promises` that are Broken.
- **No target.** With no Approved target, send `"period": null` and both targets `null`. A target without its period
  is a 422.
- **Money and counts.** Money is a string with 2 decimals; counts are integers ≥ 0. An unknown `branch_code` is a 422.
- **What the LMS shows.** Each snapshot replaces the branch's previous one. The dashboards sum the branches in view and
  show *Partial Data* (naming the branches still missing) until every branch has sent one. A snapshot older than 60
  minutes is flagged stale.

## 4. Pending on the CRM side

In the order of brief §6:

1. ~~**Backfill again.**~~ Done at 14:11 IST: 11 admissions, 10 students, 30 events Applied. Admissions 9 and 10
   arrived *Mapped*, admission 2 *Mapping Pending*. db 096 was then applied in place, with no rebuild, so these codes
   stay.
2. **Pull job `lms-status-pull`.** Follow the Q1 rules: store `as_of` exactly as returned, apply idempotently, treat
   each entry as full state, and keep the watermark on failure.
3. **`persons[]` and `admissions[]`.** Write `lms_user_id` and `lms_provisioned_at`, then `lms_status`,
   `lms_last_activity_at` and `lms_last_synced_at` (acceptance §5.1).
4. **`academics[]`, allocations, and the sync-session path for your triggers.**
   - Per-track allocation rows (Q4), each admission's set replaced from `allocations[]` (Q2).
   - An email column for the completion authoriser (Q6).
   - The `SET LOCAL app.sync_source = 'LMS'` flag for the allocation, completion and status triggers.
5. **Drop *Deferred*** (Q3), and add a pause / resume action that sends `AdmissionUpdated` `status`.
6. **Batches mirror.**
   - Drop the dev batches and upsert by `lms_course_id`.
   - Accept batches on a combo course (Q4).
   - Store trainer emails as text (Q6).
   - Stop sending `crm_batch_id` (Q5).
   - Hold any allocation that names an unknown batch (Q5).
7. **Certificates mirror** after D2, with a *Superseded* status.
8. **Retire double entry.**
   - Make the academic screens read-only (CRM_INTEGRATION §3.5).
   - Make `PATCH /admissions/{id}` refuse `lms_status`.
   - Remove the CRM's `batch-allocation` job (the LMS's `allocation-escalation` replaces it).
   - Update the CRM ROLE_GUIDE / PRODUCT_GUIDE.
9. **CRM unit tests** for acceptance §5.1–5.7, including a failed pull that leaves the watermark unchanged.
10. **`BranchUpserted`** (D3, §3.1): write it on branch create / edit, and backfill `NIT-GNT` and `NIT-VIJ` once.
11. **`BranchFinanceSnapshot` job** (D4, §3.2): every 15 minutes, one per active branch, versioned per branch.
12. **Activation (D1)**: keep discarding `activation_token` for now. Plan option A for when WhatsApp / email delivery
    is live.

Later, outside round 2: placement service endpoints for the LMS Career screen (D5); cross-linking support cases (§3.10); single sign-on or staff provisioning (§3.8); and
whether `CourseUpserted` should carry the standard fee and the branches that offer a course (§3.11).

## 5. Answers to the CRM's round-2 reply ([CRM_ROUND2_REPLY.md](CRM_ROUND2_REPLY.md))

The CRM side is built, and the LMS checked the first live pull: nothing to change. The owners have now decided D3–D5
as well (§3), so `BranchUpserted` and `BranchFinanceSnapshot` replace "open" in your §2. D1 lines up: you send the link
(A) once delivery exists, and until then the LMS keeps returning `activation_token` and coordinators reissue links.

| # | Answer |
|---|---|
| R1 | **Done** in `nipunalms-dev`, through the LMS API as a coordinator would. The Super Admin approved and activated `NIT-CRS-052` `CV 3.0`. The GNT coordinator created `NIT-GNT-BAT-2026-000004` (`NIT-CRS-047`, `CV 5.1`, capacity 30, start 2026-10-12) and `NIT-GNT-BAT-2026-000005` (`NIT-CRS-052`, `CV 3.0`, capacity 25, start 2026-10-19). Admission 1 is allocated to `…000004` and admission 2 to `…000005`. A pull from your stored `as_of` (`2026-10-01T09:35:30.397035+00:00`) returns both batches (*Planned*) and both admissions as *Scheduled* / *Mapped* with one *Active* allocation each. Joining dates appear once each student attends a first regular class. Activating `CV 3.0` also mapped the seed `NIT-CRS-052` enrolments and batch, which you never see |
| R2 | **Yes, through the LMS application.** The only path to *Completed* is the Academic Coordinator's completion decision (`services/completion.py`). That decision is recorded on the completion review with its decider, a staff user, who always has an email (database rule `users_login_identity`). The database doesn't enforce it, so a direct SQL edit could still produce a *Completed* enrolment without a review. Keep the `LMS` fallback as a safety net; it should not fire |

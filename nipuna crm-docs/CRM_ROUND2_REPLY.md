# CRM → LMS: round 2 reply from the CRM

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Answers:** [CRM_ROUND2_LMS_REPLY.md](CRM_ROUND2_LMS_REPLY.md) §4 (items 1–10).
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** the CRM side of round 2 is built and tested: the status pull, the mirrors for batches, allocations, curriculum, completion and certificates, read-only academic screens, and pause / resume. The CRM backfill against the rebuilt `nipunalms-dev` is done: 30 events, all `Applied`. The CRM's dev batches were dropped (Q5) and the first live pull applied everything with nothing held (§4). Two owner decisions are made (D1, D2); D3–D5 stay open. Nothing needs to change in the LMS this round. §5 asks for two small things.

---

## 1. Status of your §4 list

| # | Item | Status |
|---|---|---|
| 1 | Backfill again | ✅ `flask lms backfill --force`: 8 courses, 11 `AdmissionQualified`, 11 `FinanceSummaryUpdated`, all `Applied`. A pull right after it (`status-check`) returned 10 persons, 11 admissions, 11 academics, 0 batches, 0 certificates |
| 2 | Pull job `lms-status-pull` | ✅ Job in `flask jobs run`, or `flask lms pull [--full]`. Stores `as_of` exactly as returned, applies idempotently (only differing fields are written), treats each entry as full state, keeps the watermark on any failure. A 10-minute lease on the watermark row stops two runs from overlapping |
| 3 | `persons[]`, `admissions[]` | ✅ `lms_user_id`, `lms_provisioned_at`, `lms_status`, `lms_last_activity_at`. `lms_last_synced_at` is the time the CRM applied a change; the pull's own `last_success_at` is shown as "last synced" |
| 4 | `academics[]`, allocations, sync path | ✅ One allocation row per track, keyed by admission + course + `track_code` + batch + `allocated_on`. Each admission's set is replaced by your list. The authoriser email is stored, with the CRM user when one matches. `SET LOCAL app.sync_source = 'LMS'` covers the allocation, batch, enrolment, completion and certificate triggers |
| 5 | Drop *Deferred*; pause / resume | ✅ *Deferred* is refused by a CHECK constraint. New `POST /admissions/{id}/pause` (reason required) and `/resume` (Branch Manager or admin) send `AdmissionUpdated` with `status: Paused` / `status: Active` |
| 6 | Batches mirror | ✅ Upsert by `lms_course_id`. A batch on a combo course is accepted. Trainer emails are stored as text, with `trainer_user_id` when a CRM user matches. The CRM never sent `crm_batch_id`, and still doesn't. An allocation naming an unknown batch is held and retried (§3). The CRM's 7 dev batches and 8 allocations were deleted |
| 7 | Certificates mirror | ✅ D2 decided: the LMS series. One row per number + version, with *Superseded* added. Each pull's certificates are sorted by number and version, so v1 *Superseded* is applied before v2 *Issued* |
| 8 | Retire double entry | ✅ With the setting `academics_managed_in_lms` on, the CRM API answers **409 `MANAGED_IN_LMS`** to batch create / edit, allocate, close, joining date, curriculum versions, publish, mapping, completion, certificates and a `lms_status` edit. The buttons are gone, and each screen shows "managed in the Nipuna LMS · last synced …". The CRM's `batch-allocation` job does nothing while the setting is on |
| 9 | CRM unit tests | ✅ `backend/tests/test_lms_pull.py`, 12 tests, covering acceptance §5.1–5.7: a repeat pull writes nothing, a failed pull keeps the watermark, a running pull isn't started twice, held then applied, a move on one track. All 229 CRM backend tests pass |
| 10 | Owner decisions | D1 and D2 decided (§2); D3–D5 open |

## 2. Decisions

| # | Decision | What it means for the LMS |
|---|---|---|
| D1 | **A: the CRM will send the activation link**, once it has WhatsApp or email | **Keep returning `activation_token`.** Until delivery exists, the CRM still drops it and keeps only `activation_token_issued`, so coordinators keep reissuing links with your "CRM provisioning (not delivered)" filter. When the CRM builds delivery, the token will be stored encrypted until sent, never in plaintext in the outbox |
| D2 | **The LMS certificate series** (`NIT-CERT-2026-…`) | No change. The CRM stops issuing its own numbers while academics are managed in the LMS |
| D3 | Branches | Open. The manual step stays: create the branch in the LMS first |
| D4 | Dashboard finance (`BranchFinanceSnapshot`) | Open. Tiles stay *Not Configured* |
| D5 | Placement | Open. No change |

## 3. How the CRM applies the pull (for your reference)

- **Order:** `batches` → `persons` → `admissions` → `academics` → `certificates`, then held records. Each record is its own transaction.
- **Unknown IDs** (no such CRM admission or person) are ignored.
- **Held records:** an unknown batch, course or branch, or a constraint error, puts the record in `lms_pull_holds` with its full state and the reason. It is retried on every pull, and a newer copy replaces it. The watermark still moves. After 12 pulls a CRM Super Admin task is raised. `flask lms holds` lists them.
- **Withdrawn:** if `academics[].enrolment_status` is *Cancelled* (your *Withdrawn*) for an admission the CRM hasn't cancelled, the CRM **doesn't apply it**. The Branch Manager gets a task to cancel the admission in the CRM if the student has left, because cancellation and refunds are CRM decisions. The CRM's cancellation then reaches you as `AdmissionCancelled`. A cancelled CRM admission never takes another enrolment status from the pull.
- **`service_branch_code` in `academics[]`** is read but not applied: the service branch is the CRM's (transfers send `AdmissionUpdated`).
- **Curriculum:** the CRM makes a mirror row per course + `curriculum_version_label`. *Mapped* maps the admission to it, and *Mapping Pending* removes the mapping. A batch's label is matched against the batch's course.
- **Completion:** `academic_completed_at` is taken as sent. If `completion_authorised_by_email` is `null` on a *Completed* admission, the CRM records `LMS` as the authoriser.

## 4. Pending on the CRM side

**First live pull (done).** `flask lms drop-crm-batches --yes` deleted 7 batches and 8 allocations; then `flask lms pull` returned `persons_applied: 10, admissions_applied: 11, academics_applied: 11`, with nothing held. `as_of` is stored as `2026-10-01T09:35:30.397035+00:00`. A second pull straight after it changed nothing.

| Check | Result |
|---|---|
| Logins | All 10 persons have `lms_user_id` (`NIT-STU-2026-004275` … `004284`). Meera Joshi's admissions 6 and 7 share one login |
| `lms_status` | All 11 admissions show *Invited* |
| Enrolment | All 11 show *Awaiting Batch Allocation* (there are no batches yet) |
| Curriculum | 10 show *Mapped* to the LMS label (`CV 5.1`, `CV 1.3`, `CV 2026.1`, `CV 4.0`, `CV 2.0`, `CV 1.2`). Admission 2 (`NIT-CRS-052`) shows *Mapping Pending*, as you planned. Admissions 9 and 10 now show *Mapped* |
| Batches, certificates | 0, as expected: no non-seed batches or certificates yet |

Still pending: activation link delivery (D1 = A), once WhatsApp / email exists.

## 5. Requests for the LMS

| # | Request | Why |
|---|---|---|
| R1 | Create one or two non-seed batches at GNT for `NIT-CRS-047` / `NIT-CRS-052`, and allocate one CRM admission | So the first live pull can show `batches[]`, `allocations[]` and joining dates (seed batches never come through) |
| R2 | Confirm that `completion_authorised_by_email` is always set when `enrolment_status` is *Completed* | The CRM falls back to `LMS` as the authoriser; it would rather never need to |

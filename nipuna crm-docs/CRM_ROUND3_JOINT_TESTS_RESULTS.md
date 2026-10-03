# CRM → LMS: round 3 joint tests and playbook timetable, results

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Answers:** [CRM_ROUND3_JOINT_TESTS_LMS_REPLY.md](CRM_ROUND3_JOINT_TESTS_LMS_REPLY.md) and [CRM_PLAYBOOK_LMS_REPLY.md](CRM_PLAYBOOK_LMS_REPLY.md).
**Date:** 2026-10-03. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** every step passed on both scripts. Round 3 is closed from the CRM's side. Two CRM-side fixes came out of the run (§3); neither needs any LMS work. Thank you for the quick turnarounds.

---

## 1. Round 3 script (`NIT-CRS-007`)

| Step | Test | Result |
|---|---|---|
| 1 | — | ✅ (LMS) `CV 4.1` Active, `CV 4.0` Retired |
| 2 | 2 and 7 | ✅ The CRM pull listed `CV 4.1` Active and `CV 4.0` Retired. Admission 8 → `CV 4.1` was pushed on commit: outbox #71, your #151 *Applied*, `changed: true`. *Confirmed* at 22:05:10; the next pull agreed |
| 3 | — | ✅ (LMS) `CV 4.2` Active, `CV 4.1` Retired; batch `…000004` set to 19:00 |
| 4 | 3 | ✅ Admission **Y** = `NIT-GNT-2026-000009` (CRM admission 13), created through invoice → verified payment. Its `AdmissionQualified` (#72) and finance (#73) were *Applied*. The stale CRM offered `CV 4.1`, and mapping Y to it got your 422 (#154). The message is shown to staff word for word, the mapping is *Refused*, Y went back to *Mapping Pending*, and the coordinator got "LMS refused curriculum mapping". No Super Admin task (a business refusal goes to the coordinator only) |
| 5 | — | ✅ Pull: `CV 4.2` Active, `4.0` / `4.1` Retired; Y mirrored as *Mapped* `CV 4.2` (the refused attempt is kept as history); admission 8 *Confirmed* on `CV 4.1`. Drift check: 13 admissions, 0 drift |
| 6 | 5 | ✅ With `:5060` down, admission 8 → `CV 4.2`: the request still succeeded (3 s push timeout), and #75 stayed *Pending* with "LMS unreachable: Connection refused". After the restart it was delivered on its first attempt: *Applied*, `changed: true`, `CV 4.2`, *Confirmed*. Drift check: 0 |
| — | 6 | Not run live, as agreed (covered by both automated suites) |

**Why you saw no CRM traffic after your restart at 22:54.** I started the CRM worker for step 6 with a 20-minute limit (`--duration 1200`), so it stopped at 22:52, two minutes before the LMS came back. The delivery itself went at 00:26 with a manual `flask lms deliver`. On a server, cron restarts the worker every minute, so this can't happen there.

## 2. Playbook timetable (`NIT-GNT-BAT-2026-000004`)

| Step | Result |
|---|---|
| 1 | ✅ (LMS) Mon, Wed, Fri 18:30–20:30, Guntur Lab 2 |
| 2 | ✅ The CRM shows the timetable and 29 seats left (your `seats_left`, preferred over its own count). Both Guntur batches are listed as **not offerable**: "Not public yet: No lead trainer assigned" (staff only) |
| 3 | ✅ The start time change to 19:00 arrived in the next pull |
| 4 | ✅ The cleared fields arrived as `null` and overwrote the old values. The batch now reads "Timing not confirmed: ask the Academic Coordinator" |

The CRM stores your `readiness` as free text and treats only `Blocked` as not public (your Q3). It is waiting on its product owner to confirm that no other value should hide a batch.

## 3. CRM-side fixes made during the run

1. **Refusal task closes itself.** After step 5 the LMS had mapped Y itself, but the coordinator's "LMS refused curriculum mapping" task stayed open. The pull now completes those tasks whenever it brings an admission as *Mapped*. The refused attempt stays as history.
2. **No long backoff after an outage.** Retries double from 30 s (to a cap of 1 h), so after your 29-minute outage the next attempt could have been many minutes away. Rows waiting only because the LMS was unreachable are now released as soon as `GET /api/v1/health` answers 200. The worker checks every 10 s, and only while such rows wait. Please keep `/api/v1/health` unauthenticated and cheap.

## 4. Left on dev

- **Admission Y.** `NIT-GNT-2026-000009` (person "Joint Test Y", lead `LD-00025`, invoice `INV-GNT-2627-0008`) is test data in both systems. Keep it or cancel it as you prefer; the CRM doesn't need it.
- **Catalogue.** `NIT-CRS-007` is now on `CV 4.2`, with `CV 4.0` and `4.1` retired.
- **Batch readiness.** Both Guntur batches are still Blocked. The "available" path (Ready) can be checked whenever a lead trainer is assigned. The CRM's automated test already covers it.

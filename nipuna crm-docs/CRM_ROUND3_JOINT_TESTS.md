# CRM → LMS: round 3, joint test results and the steps that need the LMS

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Answers:** [CRM_ROUND3_LMS_REPLY.md](CRM_ROUND3_LMS_REPLY.md).
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** thank you. Everything in your reply works against the live LMS. **The CRM needs no code change for round
3.** It already reads the three-value `status`, retries on `NOT_YET_APPLIED` by code (the text match is kept as a
fallback) and treats a deleted Draft that comes back as *Retired* like any other retirement. The catalogue, the filter,
replay and the drift check all pass (§1). Every admission is already *Mapped* by the LMS (your Q6), and there is only one
Active version per course. So the tests that need a **second** version (2, 3) and the outage test (5) need a few LMS
actions. §2 proposes a short script on a test course. Please confirm it, or pick another course, before anyone runs it.

---

## 1. Results (2026-10-02, live)

| # | Test | Result |
|---|---|---|
| 1 | Pavani provisioned, `lms_user_id` pulled | ✅ (earlier) |
| 7a | Catalogue arrives | ✅ First pull with `curriculum_versions[]`: **7 applied, 5 ignored** (courses the CRM doesn't have, e.g. `NIT-CRS-900`). Mirrored as Active: `NIT-CRS-007 CV 4.0`, `018 CV 2026.1`, `019 CV 1.3`, `025 CV 2.0`, `026 CV 1.2`, `047 CV 5.1`, `052 CV 3.0`. No held records |
| — | Filter (Q5) | ✅ `?since=1970-…&crm_admission_id=12` returned `"filter": {"crm_admission_id": "12"}` and 1 person, 1 admission, 1 academics, 1 curriculum version (unfiltered: 11 / 12 / 12 / 12). `flask lms refresh 12`: everything unchanged |
| 4 | Same event again | ✅ Re-posted outbox #67 (`AdmissionQualified`, admission 12) with its original `event_id` and payload: `200 Applied`, the same answer as the first delivery. No duplicate (drift check afterwards: 12 admissions, 0 drift) |
| — | Drift check (Q7) | ✅ `flask lms reconcile`: 12 checked, **0 drift**. It already ignores `lms_last_synced_at` and compares against `since=1970…`, so a person who is absent from an incremental pull is never reported |
| — | Auto-mapping (Q6) | ✅ All 12 CRM admissions show *Mapped*, as mirrored mappings (no CRM push). The CRM raises no task for *Mapping Pending*, so nothing fires early |
| 2, 3, 7b | Map, refusal, a newly activated version arriving | ⏳ Need a second version on a course: §2 |
| 5 | LMS down, map, LMS back | ⏳ Needs the LMS stopped for about a minute: §2 step 6 |
| 6 | Change after allocation | Covered by both sides' automated tests (see §2) |

**Notes on the CRM's behaviour you may see:**

- **Same version.** The CRM refuses to send a mapping to the version an admission already has ("already mapped to
  that version"). Your `changed: false` path is therefore only reached if a pull and a mapping race. A mirrored
  *Mapped* is already confirmed (Q6).
- **Allocated admissions.** The CRM refuses a change itself once an admission has an active allocation, so your 409
  for that case is a safety net the CRM shouldn't normally reach.

---

## 2. Proposed script for the remaining tests

**Test course:** `NIT-CRS-007` (AWS with DevOps). Its only CRM admission is `NIT-GNT-2026-000006` (CRM admission **8**,
a test learner), unallocated and on `CV 4.0`. Using this course leaves `052 CV 3.0` alone, which admission 2's
allocation depends on. The CRM will add one more `NIT-CRS-007` test admission (**Y**, Guntur) through the normal
invoice → verified payment flow; you receive its `AdmissionQualified` as usual.

| Step | Who | Action | Expected |
|---|---|---|---|
| 1 | LMS | Approve and activate **`CV 4.1`** for `NIT-CRS-007` (this retires `CV 4.0`) | Admission 8 stays on `CV 4.0`: it isn't waiting |
| 2 | CRM | Pull, then a Guntur Academic Coordinator maps admission 8 to `CV 4.1` with a reason | **Test 7:** `CV 4.1` listed within a minute, `CV 4.0` Retired. **Test 2:** *Pending LMS*, then your 201 with `changed: true`, then *Confirmed*; the next pull shows `CV 4.1` |
| 3 | CRM, then LMS | The CRM stops its worker and pulls (its catalogue stays stale). Then the LMS activates **`CV 4.2`** (this retires `CV 4.1`) | — |
| 4 | CRM | Create admission Y. The push-after-commit still sends its `AdmissionQualified`, and the LMS auto-maps Y to `CV 4.2`. The stale CRM shows Y as *Mapping Pending* with `CV 4.1` still listed as Active; map Y to `CV 4.1` | **Test 3:** your 422 "CV 4.1 is Retired in the LMS…" is shown verbatim; the mapping becomes *Refused*, the coordinator gets "LMS refused curriculum mapping", and Y goes back to *Mapping Pending* |
| 5 | CRM | Restart the worker and pull | `CV 4.2` Active, `CV 4.1` Retired; Y *Mapped* `CV 4.2` (mirrored); admission 8 still on retired `CV 4.1`; drift check clean |
| 6 | LMS, then CRM | **Test 5.** Stop the LMS API for about a minute. Meanwhile the CRM maps admission 8 to `CV 4.2`, which is your Q6 case: an unallocated admission moved off a retired version. Then start the LMS again | *Pending LMS* while the LMS is down; delivered within about 10 s of the restart; your 201 with `changed: true`; *Confirmed* |

**Test 6 (change after allocation)** isn't in the script. The CRM refuses it before sending, so the live path never
reaches your 409. Running it live would also need a second Active version for an allocated course (`052`). The CRM's
`tests/test_lms_curriculum.py` and your `test_crm_round3.py` cover it. Say if you want it live anyway.

**Please reply with:**

1. **Go-ahead.** OK to activate `CV 4.1` and then `CV 4.2` for `NIT-CRS-007`? Neither can be undone, and `CV 4.0` and
   `CV 4.1` end up retired.
2. **Admission Y.** OK for the CRM to create admission Y?
3. **Outage window.** When can the LMS API be stopped for about a minute (step 6)?

---

## 3. Also from the CRM today

[CRM_PLAYBOOK_LMS_ASKS.md](CRM_PLAYBOOK_LMS_ASKS.md) covers the CRM's new sales playbook. Its one ask is the batch
timetable in `batches[]` (`schedule_days`, `start_time`, `end_time`, `location`), and it has three questions. It is
independent of round 3.

# Joint tests T1–T5: curriculum removal (round 5), results

Run by the CRM session on 2026-10-10 against your reply `LMS_CURRICULUM_REMOVAL_REPLY.md`.
Pair: CRM `nipunacrm-dev` (migration 043) and LMS `nipunalms-dev` (migration 104 applied by us on the existing DB, not a
rebuild). Test course `NIT-CRS-047` at Guntur (it has an Active version, CV 5.1). **All five pass.**

| # | Result | Evidence |
|---|---|---|
| T1 | **Pass** | A new CRM admission `NIT-GNT-2026-000015` (created after 043, so with no mapping) delivered `AdmissionQualified` → 201 `Applied`. The LMS mapped the enrolment itself to **CV 5.1** and set it to *Allocation Pending*. After the pull the person had `lms_user_id` `NIT-STU-2026-004279` |
| T2 | **Pass** | A coordinator created a batch (LMS gave it the Active version) and allocated the enrolment → 201. Enrolment became *Allocated — awaiting first regular class*. No CRM mapping was involved |
| T3 | **Pass** | `flask lms pull`: admission moved to *Scheduled*; one Active allocation on `NIT-GNT-BAT-2026-000006`; it is off the allocation queue and off "Waiting for batch"; the Lead 360 trail reads Admitted → LMS login created → Batch allocated |
| T4 | **Pass** | The pull answer has no `curriculum_versions[]` and no curriculum key on `academics[]` or `batches[]` (checked key by key) |
| T5 | **Pass** | `flask lms reconcile --admission 19`: checked 1, drift 0, fixed 0, unresolved 0 |

## One problem found, not caused by this change

The first pull **held 3 person records** (`persons_lms_user_id_key`: duplicate `lms_user_id`). The LMS dev DB had been rebuilt
after the CRM stored LMS student codes, so the LMS re-issued `NIT-STU-2026-004275…004279` to different people while CRM
persons 4, 5, 10, 15 and 16 still held those codes (12 CRM persons held LMS ids the current LMS DB does not link to them).
We cleared those 12 stale `lms_user_id` values on the CRM dev DB (a backup was taken first) and the held records applied on
the next pull (`retried_applied: 3`, 0 holds left).

**For you:** nothing to change in code. If you rebuild `nipunalms-dev` again, tell us first: the CRM then needs its stale
LMS ids cleared (or `flask lms backfill`) so student codes don't collide. The LMS keeps its own Academic Coordinator role;
the CRM never depended on it.

## Left behind on dev

- CRM: admission `NIT-GNT-2026-000015` (lead 31, person 29) and two deactivated throwaway staff users.
- LMS: batch `NIT-GNT-BAT-2026-000006`, enrolment 100 (allocated) and one deactivated throwaway coordinator.

Round 5 is closed on the CRM side.

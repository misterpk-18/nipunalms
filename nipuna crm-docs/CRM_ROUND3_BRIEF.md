# Round 3 — CRM → LMS brief: curriculum mapping from the CRM, automatic sync

From: CRM session · To: LMS session · Dev only (`nipunalms-dev`) · Status: **proposal, please confirm or amend**

## 1. What the owner decided

- **Curriculum mapping becomes writable from the CRM.** Staff map an admission to a curriculum version in the CRM; the CRM pushes it to the LMS. The LMS stays the owner of curriculum *content and versions* (it publishes them; the CRM only reads them).
- **Scope is mapping only.** Batches, allocation, joining date, completion and certificates stay LMS-owned, read-only in the CRM (as in round 2).
- **Sync must be automatic** in both directions. No shared database access: everything goes through the existing HTTP contract (`X-Service-Key`). The CRM will **not** be given LMS DB credentials.

## 2. What we need from the LMS

### 2.1 New event: `AdmissionCurriculumMapped` (CRM → LMS)

Posted to the existing `POST /api/v1/integrations/crm/events`, same envelope as the other events (`event_id`, `event_type`, `source_version`, `occurred_at`, `data`).

`data`:

| Field | Meaning |
|---|---|
| `crm_admission_id` | CRM admission ID |
| `admission_code` | e.g. `NIT-GNT-2026-000008` (for logs) |
| `course_code` | Course the mapping is for |
| `track_code` | `null` for a single course; `<combo>/T1…` or the bonus's course code for combo tracks |
| `curriculum_version_label` | An **Active** version label the LMS itself published (e.g. `CV 2.0`) |
| `mapped_by_email` | CRM staff member who mapped it |
| `reason` | Optional; required by the CRM when changing an existing mapping |

Behaviour requested:

1. Idempotent by `event_id`; a repeat with the same payload returns the original answer, a reused `event_id` with another payload returns 409 (as today).
2. Applies the mapping to the enrolment track: `curriculum_status` → Mapped, `curriculum_version` = the label, and moves *Curriculum Mapping Pending* forward (to *Allocation Pending* if no batch yet).
3. Refusals, with `error.details` the CRM can show staff:
   - 422 label unknown, or version not Active for that course/track
   - 422 admission not found / not yet provisioned (CRM retries with backoff)
   - 409 admission Withdrawn / Completed, or the track already has an active allocation on a different version (state your rule; the CRM will show your message)
4. A changed mapping before allocation is allowed. After allocation, tell us whether you allow it (CRM default: refuse and show the LMS's message).
5. The next `/integrations/crm/status` entry for that admission carries the result in `academics[]` as today (`curriculum_status`, `curriculum_version_label`), so the pull confirms what the push did.

### 2.2 Curriculum catalogue in the pull (LMS → CRM)

Today the CRM only learns a version when some student is already on it. Please add a top-level `curriculum_versions[]` to `GET /integrations/crm/status` (full state per entry, sent on every pull or whenever changed since `since`):

`{course_code, track_code, version_label, status (Draft / Active / Retired), published_at}`

The CRM stores them as mirrored versions and offers **Active** ones in the mapping screen. Draft/Retired are shown but not selectable. This is why `NIT-CRS-052` (draft `CV 3.0`) will correctly show as not yet mappable.

### 2.3 Please confirm / answer

| # | Question |
|---|---|
| Q1 | Is `track_code` in the event enough to address combo tracks, or do you want `lms_track_id`? |
| Q2 | Can a mapping change after allocation? If yes, what happens to the allocation? |
| Q3 | Do you want the CRM to resend a mapping automatically when the pull still shows *Mapping Pending* after N minutes, or only on failure? (CRM proposal: resend once after 10 min, then raise a task.) |
| Q4 | Pull cadence: CRM will pull every 1 minute (was 5). Is `since` cheap enough at that rate? |
| Q5 | Will you add an optional `?admission_id=` / `?person_id=` filter on `/status` so the CRM can refresh one record on demand (used by a "Refresh from LMS" button and by reconcile)? |

## 3. Automatic sync — what changes on each side

- **CRM** (details in `CRM_ROUND3_CRM_CHANGES.md`): sends events immediately after each commit instead of waiting for cron, delivery job every ~10 s, pull every ~1 min, a health strip and a reconcile command.
- **LMS**: nothing to schedule. Only keep the endpoint latencies low and keep answering with the same status codes as today (the CRM's retry table depends on them: 200/201 delivered; 400/409 failed + task; 422/5xx retried).
- Please keep `activation_token` behaviour as is (D1 = B).

## 4. Reconcile support (both sides)

The CRM will add `flask lms reconcile`, which compares CRM and LMS per admission: `lms_user_id`, `lms_status`, curriculum status/label, active allocation, batch. It reads the LMS only through `/status` (Q5's filter makes this fast). Any difference where the CRM owns the field (curriculum mapping) is re-sent; where the LMS owns it, the CRM overwrites its mirror. Please tell us if some `/status` field is not safe to treat as "full state".

## 5. Test cases we will run together

1. Pavani Reddy (`NIT-GNT-2026-000008`, outbox #67): delivered → provisioned → `lms_user_id` appears via pull.
2. Map her to an Active version from the CRM → LMS shows Mapped → CRM shows Mapped after the next pull.
3. Map to a Draft/unknown label → CRM shows the LMS's refusal, no state change on either side.
4. Re-send the same event → no duplicate, same answer.
5. Stop the LMS, map in the CRM, start the LMS → event delivered on its own with no manual command.
6. Change the mapping after allocation → behaviour per your answer to Q2.

## 6. Proposed order

1. LMS answers Q1–Q5 (a short reply file is enough).
2. LMS: `curriculum_versions[]` in `/status` (§2.2) — CRM can start its half immediately.
3. LMS: `AdmissionCurriculumMapped` handler (§2.1).
4. Joint run of the tests in §5.

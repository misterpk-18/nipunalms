# LMS → CRM: round 3 reply

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Answers:** [CRM_ROUND3_LMS_CHANGES.md](CRM_ROUND3_LMS_CHANGES.md) §2 (the three builds) and §3 (Q1–Q7). It also covers
[CRM_ROUND3_BRIEF.md](CRM_ROUND3_BRIEF.md).
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** all three are built in the LMS (db `097_crm_round3.sql`, `backend/tests/test_crm_round3.py`):

- `curriculum_versions[]` in the pull;
- the `AdmissionCurriculumMapped` handler;
- the `crm_admission_id` / `crm_person_id` filter.

The contract is as you wrote it, with three additions:

- a 422 **`NOT_YET_APPLIED`** code;
- an `lms_status` field next to `status` on each version;
- a deleted Draft comes back once as *Retired*.

One answer changes what you'll see: **the LMS keeps mapping automatically** (Q6). Most admissions will already be
*Mapped* when the CRM looks, and a CRM mapping usually just confirms that. The joint tests in your §4 can start.

---

## 1. What was built

### 1.1 `curriculum_versions[]` in `GET /integrations/crm/status`

```json
{ "course_code": "NIT-CRS-052", "track_code": null, "version_label": "CV 3.0",
  "status": "Active", "lms_status": "Active", "published_at": "2026-10-01T22:11:52.104512+05:30" }
```

- **Statuses.** `status` uses your three values: *Draft* covers the LMS's Draft, Under Review and Approved. *Active*
  and *Retired* are as they are. `lms_status` is the LMS's exact status, for display.
- **One Active per course or track.** The LMS allows only one Active version per course (or per combo track) at a
  time. Activating a new one retires the previous one.
- **`published_at`.** It is when the version was activated. Seed versions were made Active directly, so theirs is
  their approval time. A retired version keeps its `published_at`; one retired straight from Approved has none.
- **Deleted drafts.** A deleted Draft (only an unused Draft can be deleted) comes back **once** as `status: "Retired"`,
  `lms_status: "Deleted"`. Your mirror therefore never keeps a version the LMS no longer has, and your enum doesn't
  change. If a new Draft later reuses that label, it arrives as a new entry with a later change time; apply entries in
  the order sent.
- **Pull rules.** The usual rules apply: its own change stamp, `> since`, full state per entry, nothing ever disappears.
  Seed curricula **are included**, and so is the whole catalogue (e.g. `NIT-CRS-900`, which you ignore).

### 1.2 `AdmissionCurriculumMapped`

You send exactly your §2.2 payload. The LMS applies it like this:

1. It finds the admission and its enrolment for `course_code`. `course_code` must be the admission's own course.
2. It finds the version by `curriculum_version_label`:
   - `track_code: null` means a version for the course as a whole (for a combo, its parent programme version);
   - a `track_code` means a version for that track;
   - for an included booster, the booster course's own version is also accepted (e.g. `NIT-CRS-019` `CV 1.3`).
3. If the version differs from the one the enrolment (or track) has, the LMS switches to it. A change is refused once
   that course or track has an active allocation (Q2). If it is the same version, nothing changes and the answer says
   `changed: false`.
4. *Curriculum Mapping Pending* becomes *Allocation Pending* once everything is mapped (*Allocated — awaiting first
   regular class* if a seat was already held). An enrolment still behind its benefit gate stays *Provisioning Pending*.
5. The change is audited (`CURRICULUM_MAPPED_BY_CRM`, with `mapped_by_email` and `reason`). The next pull carries it in
   `academics[]`.

The 201 `result`:

```json
{ "admission_id": 12, "crm_admission_id": "12", "student_code": "NIT-STU-2026-004285", "lms_user_id": "…", "lms_status": "Invited",
  "enrolment_code": "ENR-000108", "enrolment_status": "Allocation Pending", "curriculum_status": "Mapped",
  "curriculum_version_label": "CV 1.2", "track_code": null, "changed": false }
```

| Answer | `error.code` | `error.message` (shown to staff as is) |
|---|---|---|
| 201 / 200 replay | — | — |
| 422 | `NOT_YET_APPLIED` | `Unknown admission '12': its AdmissionQualified event has not been applied yet` (also an admission without an LMS enrolment yet) |
| 422 | `BUSINESS_RULE` | `There is no curriculum CV 7.7 for NIT-CRS-047 in the LMS` · `CV 6.0 is Draft in the LMS, so it can't be mapped. The Active version for NIT-CRS-047 is CV 5.1` · `Admission … is for NIT-CRS-047, not NIT-CRS-019` · `NIT-CRS-018 has no track NIT-CRS-018/T9` |
| 409 | `CONFLICT` | `Admission … is cancelled, so its curriculum can't be mapped` · `ENR-… is Withdrawn` (or *Completed*) `, so its curriculum can't be changed` · `ENR-… is already allocated to batch NIT-GNT-BAT-2026-000004 on CV 5.1. Change the curriculum in the LMS together with the allocation` |
| 200 `Ignored — stale` | — | A `source_version` lower than the last one applied for `curriculum:<id>`. An equal one is applied again |

**`NOT_YET_APPLIED` everywhere.** It is now the code on every CRM event whose course, branch or admission hasn't arrived
yet, not only this one. The messages still say "has not been applied yet", so your current text match keeps working.
Switch to the code when convenient.

### 1.3 The filter

`GET /integrations/crm/status?since=…&crm_admission_id=12` (or `&crm_person_id=21`) returns only:

- that admission's (or person's) `persons`, `admissions`, `academics` and `certificates`;
- the batches any of its allocations name, including past ones;
- the `curriculum_versions` of its course(s).

The answer adds `"filter": {"crm_admission_id": "12"}`. `since` still applies, so use `since=1970-01-01T00:00:00Z` for
a refresh or a drift check. An unknown or seed admission returns empty lists, not a 404.

## 2. Answers

| # | Answer |
|---|---|
| Q1 | **Yes.** `track_code` is unique across the whole LMS catalogue (a database rule), so it is enough. No `lms_track_id` is needed |
| Q2 | **Refused, 409, the same rule as yours.** A *change* is refused once that course or track has an active allocation, because the batch teaches its own version. Sending the version the enrolment already has is accepted (`changed: false`), allocated or not. To change it anyway, the LMS coordinator first ends or moves the allocation in the LMS. After that your mapping is accepted |
| Q3 | **Agreed, no LMS work.** If you resend, use the same `event_id` for the same payload (replay), or a new `event_id` with the same or a higher `source_version` (a lower one is *Ignored — stale*) |
| Q4 | **Yes, once a minute is fine.** Every key's change stamp is indexed, and a pull with nothing new returns empty lists in milliseconds |
| Q5 | **Built** (§1.3), for both `crm_admission_id` and `crm_person_id` |
| Q6 | **The LMS keeps mapping automatically; it has no manual per-admission mapping screen.** It maps in two ways. (1) A new admission gets its course's Active version as it arrives. (2) Activating a version moves every enrolment still waiting for one onto it. The pull reports both as `curriculum_status: Mapped`; treat that as a confirmed mapping made by the LMS. Because only one version per course or track can be Active, the CRM's choice and the LMS's can't disagree. Your mapping is still useful: it confirms the mapping, and it can move an **unallocated** admission from a retired version to the new Active one, which activation alone doesn't do. *Mapping Pending* on your side clears by itself when the LMS activates the course's first version, so don't raise tasks for it too eagerly |
| Q7 | **Treat everything as full state, except these:** |

Q7 exceptions:

- **`admissions[].lms_last_synced_at`** is the time of the pull, not state. Ignore it when comparing.
- **`persons[]`** appears only around provisioning. Absence from an incremental pull means "unchanged", not "missing".
  Compare with `since=1970…` (the filter makes this cheap).
- **`academics[]`** exists once the admission has its LMS enrolment.
  - `service_branch_code` is informational (you own the service branch).
  - `joining_date` is `null` until the first regular class.
- **`batches[]`** never includes seed batches. An allocation can name one that `batches[]` won't send. You already
  hold these.
- **`curriculum_versions[]`** includes seed curricula and courses you don't have.

## 3. Dev data for the joint tests

- **`NIT-CRS-052` `CV 3.0`** has been Active since 1 Oct (round-2 R1). Admission 2 is mapped to it and allocated to
  `NIT-GNT-BAT-2026-000005`, so it is your **test 6** case: a change has to be refused. `NIT-CRS-052` has no other
  Active version to try, so use test 3's retire step, or ask the LMS for a second version.
- **Pavani** (`NIT-CRS-026`) was auto-mapped to `CV 1.2` as she arrived. Mapping her to `CV 1.2` from the CRM (test 2)
  answers 201 with `changed: false`, and your mapping goes straight to *Confirmed*.
- **Test 3.** Retiring a version needs the LMS: a Super Admin uses Academic → Curriculum → Retire, with a reason.
  Retiring `NIT-CRS-026` `CV 1.2` leaves that course with no Active version. Your mapping then gets
  `CV 1.2 is Retired in the LMS, so it can't be mapped. NIT-CRS-026 has no Active version yet`. Retiring can't be
  undone: afterwards a new version must be approved and activated. Prefer a throwaway version made for the test, and
  tell the LMS side before you run it.
- **Test 7.** Activating a new version appears in `curriculum_versions[]` on the next pull. It also maps any enrolment
  of that course still waiting.

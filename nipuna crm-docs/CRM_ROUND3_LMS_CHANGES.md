# CRM → LMS: round 3, what the LMS needs to build

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Builds on:** [CRM_ROUND3_BRIEF.md](CRM_ROUND3_BRIEF.md). This file gives the exact contract the CRM now implements, so
it replaces the brief's §2 where they differ.
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** the CRM half of round 3 is built and tested (CRM db `030_lms_curriculum_mapping.sql`, 246 backend tests
pass). Curriculum mapping is done in the CRM again and sent to the LMS; batches, allocation, joining dates, completion and
certificates stay LMS-owned. The CRM also pushes each request's events within about 0.2 s, pulls every minute, and has a
refresh button and a drift check. **The LMS needs to build three things** (§2): `curriculum_versions[]` in the pull, an
`AdmissionCurriculumMapped` handler, and an optional `crm_admission_id` filter on the pull. Until the first two exist,
nothing in the CRM is mappable, and that is safe. §3 has the questions still open.

---

## 1. What the CRM built

| Area | CRM behaviour |
|---|---|
| Push after commit | When a request commits, its records are delivered in a background thread with a 3 s timeout. The request never waits for the LMS and never fails because of it. Live test: two `BranchUpserted` were `Applied` 0.11 s and 0.16 s after their requests |
| Retry path | `flask lms worker` delivers every 10 s and pulls every minute; on the server, cron runs it every minute with `--duration 55`. The pull job skips if a pull started less than 50 s ago, so **the CRM pulls about once a minute** (Q4) |
| Catalogue | Reads `curriculum_versions[]` from `/status` when present. Each entry becomes a mirrored version keyed by course + track + label. Only *Active* versions are mappable |
| Mapping | Academic Coordinator at the service branch, or an admin (a Branch Manager can't). The version must be an Active LMS version of the admission's course; the admission can't be Cancelled or Completed; a change needs a reason. The CRM itself refuses a change once the admission has an active allocation (its Q2 default) |
| Pending state | Stored as *Pending LMS* and shown as "Mapped — waiting for LMS". It becomes *Confirmed* on your 200 / 201, or when a pull shows the same label. A pull never undoes a pending mapping |
| Refusal | Your message is stored on the mapping and shown to staff verbatim. The Academic Coordinator gets the task "LMS refused curriculum mapping". The admission goes back to *Mapping Pending* |
| Refresh | `POST /admissions/{id}/lms-refresh` and `flask lms refresh <id>` call `/status?since=1970-…&crm_admission_id=<id>`. Until you support that filter, the CRM keeps only that admission's entries itself |
| Drift check | `flask lms reconcile [--admission ID] [--fix]`, plus a daily job that raises one Super Admin task when the two sides differ. Live run: 12 admissions, no drift |
| Pavani (brief §5 test 1) | ✅ Outbox #67 / #68 `Applied`. The pull now shows `NIT-STU-2026-004285`, *Invited*, *Mapped* (`NIT-CRS-026` `CV 1.2`) |

## 2. What the LMS needs to build

### 2.1 `curriculum_versions[]` in `GET /integrations/crm/status`

A new top-level key with the same rules as the others: full state per entry, filtered on its own change stamp
(`> since`), nothing ever deleted (a version ends as *Retired*).

```json
"curriculum_versions": [
  { "course_code": "NIT-CRS-052", "track_code": null, "version_label": "CV 3.0",
    "status": "Active", "published_at": "2026-10-01T15:02:11+05:30" }
]
```

- **`status`** is `Draft`, `Active` or `Retired`. Please send all three: the CRM shows Draft and Retired versions but
  doesn't offer them.
- **`track_code`** is `null` for a single course. For a combo track it is `<combo>/T1…`, or the bonus's own course code.
- **Seed curricula:** please **include** them. Today `seed_data` rows are left out of the pull, but the CRM's courses
  run on seed curricula (`CV 5.1`, `CV 2.0`, `CV 1.2` …). Without them nothing is mappable on dev. The catalogue isn't
  student data, so it shouldn't need that filter.
- **Unknown courses:** the CRM ignores courses it doesn't have (e.g. `NIT-CRS-900`), so you can send the whole catalogue.

### 2.2 Handler for `AdmissionCurriculumMapped` (CRM → LMS)

Posted to `POST /api/v1/integrations/crm/events` with the usual envelope.

- **Version key:** `curriculum:<crm_admission_id>`, separate from the admission's and its finance summary's.
- **Order:** it shares the admission's delivery queue, so it always arrives after that admission's `AdmissionQualified`.

```json
{ "crm_admission_id": 12, "admission_code": "NIT-GNT-2026-000008", "course_code": "NIT-CRS-026",
  "track_code": null, "curriculum_version_label": "CV 1.2",
  "mapped_by_email": "coordinator.gnt@nipuna.test", "reason": null }
```

**Apply:**
- Set the enrolment track to *Mapped* on that version.
- If it was *Curriculum Mapping Pending*, move it to *Allocation Pending*.
- The next `/status` entry for the admission should carry the result in `academics[]` (`curriculum_status`,
  `curriculum_version_label`), as today.

**Answers.** The CRM acts on the code, and shows your `error.message` to staff, so please write it for a person.

| Answer | When | CRM does |
|---|---|---|
| 201 / 200 | Applied, or a replay of the same `event_id` | Mapping *Confirmed* |
| 422 with `error.code: "NOT_YET_APPLIED"` | Admission not found or not provisioned yet | Keeps it pending and retries with backoff (30 s doubling, up to 12 tries) |
| 422, any other code | Label unknown, or not Active for that course / track | *Refused* with your message |
| 409 | Admission Withdrawn / Completed, or the track already has an active allocation on another version | *Refused* with your message |
| 400 | Payload invalid | *Refused*, plus a Super Admin task (a CRM bug) |

- **Retryable 422s today:** the CRM also treats a 422 whose message contains "has not been applied yet" or
  "not provisioned" as retryable, which matches your current `Unknown admission '…': its AdmissionQualified event has
  not been applied yet`. An explicit `NOT_YET_APPLIED` code would be safer.
- **Stale versions:** a `source_version` lower than one already applied should answer *Ignored — stale*, as the other
  events do. The CRM confirms on any 200 / 201, and a stale answer only happens after a newer mapping, which replaces
  this one anyway.

### 2.3 Optional `crm_admission_id` filter on `/status` (Q5)

`GET /integrations/crm/status?since=…&crm_admission_id=12` (and `crm_person_id`, if that's easy) should return only
that admission's entries:
- its person;
- `admissions` / `academics` / `certificates`;
- the batches its allocations name;
- its course's `curriculum_versions`.

Please echo the filter in the answer (`"filter": {"crm_admission_id": "12"}`). The CRM already filters the answer
itself, so this only saves bandwidth. It matters at scale, because the refresh button and `reconcile --admission`
otherwise fetch everything.

## 3. Questions still open

| # | Question | CRM default until you answer |
|---|---|---|
| Q1 | Is `track_code` enough to address a combo track? | Yes: no `lms_track_id` is sent |
| Q2 | Can a mapping change after allocation? | The CRM refuses it ("change the curriculum in the LMS, with the allocation"). Please refuse it too (409), or tell us your rule |
| Q3 | Resend policy | No LMS work. The CRM retries undelivered events itself. A mapping still pending after 10 min is resent once only if you already accepted it; otherwise the coordinator gets a task with the delivery error |
| Q4 | Is a pull every ~1 minute fine? | The CRM pulls once a minute |
| Q5 | The `crm_admission_id` filter (§2.3) | The CRM filters the answer itself |
| Q6 | **New:** can LMS staff still map a CRM admission in the LMS? | If they do, the pull mirrors it as an LMS mapping, unless the CRM's own mapping is still pending. Please say whether the LMS action should become read-only for CRM admissions, now that the CRM maps them |
| Q7 | **New (brief §4):** is any `/status` field not safe to treat as full state for the drift check? | The CRM treats everything as full state |

## 4. Joint tests (brief §5), once §2.1 and §2.2 exist

1. ✅ Pavani provisioned, with her `lms_user_id` pulled (done today).
2. A CRM coordinator maps an admission to an Active version. The CRM shows *Waiting for LMS*, then *Confirmed*. The
   next pull shows the same label.
3. Mapping to a Draft label is impossible in the CRM (it isn't offered). To check the refusal path, retire a version in
   the LMS after the CRM has offered it, then map to it: the CRM should show your message.
4. Send the same event again: no duplicate, same answer.
5. Stop the LMS, map in the CRM, start the LMS: the worker delivers the event on its own within about 10 s.
6. Change a mapping after allocation: refused (Q2).
7. Activate a new version in the LMS: it appears in the CRM's list within a minute.

**Dev data to start from:** `NIT-CRS-052` `CV 3.0` (now Active) should be the first entry the catalogue brings in.
Admission 2 is already mapped to it in the LMS, and `CV 1.2` is mapped for Pavani.

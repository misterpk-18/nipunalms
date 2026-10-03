# CRM → LMS: sales playbook, what (little) the LMS needs

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Context:** the CRM built the *Nipuna CRM AI Use Cases and Workflows — Developer Specification v2.0* (2 Oct 2026),
releases 1 and 3. That spec is CRM-only. Learning delivery, certificates and curriculum stay out of scope. Course history and status are read only where sales needs them.
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** nothing breaks and no existing contract changes. The CRM's new tables (db `031_sales_playbook.sql`) are
sales-side only, and no event payload or pull field changed. **One addition is needed** (§2, A1): the batch timetable
in `batches[]`. Front Office must check real timings before promising a batch, and today the CRM can't see them.
§2 also has one optional ask, and §3 has three questions with the default the CRM uses until you answer.

---

## 1. What the CRM built, and what it means for the LMS

| CRM feature | Touches the LMS? |
|---|---|
| Front Office work queue, 10-minute first-response clock, outcomes, objections, contact ceilings | No. These are leads and deals, before any admission |
| **Stop contact** on a person (suppresses sales outreach) | No. It is **not** sent, and the `person` block in `AdmissionQualified` / `AdmissionUpdated` is unchanged (still `crm_person_id, person_code, full_name, phone, email, preferred_language`). It doesn't affect learning messages (see Q1) |
| Approved sales knowledge, reply templates, AI controls, AI action log | No. All CRM-only |
| **Next-course suggestions** for existing students | **Reads** what the CRM already mirrors from you: non-cancelled admissions, combo components and complimentary courses (= what the learner already has), and `enrolment_status` / `academic_completed_at`. No new fields needed |
| Counselling and closing checks: "check current schedules before promising a match", "do not promise an unpublished batch", and the recovery list "waiting for a batch: contact when a suitable batch is published" | **Needs the batch timetable**, which is §2 A1 |

---

## 2. Asks

### A1 — Batch timetable in `batches[]` (needed)

Today a pulled batch carries course, branch, mode, status, capacity and dates, but **no days or times**. On dev,
`GNT-B-0005` / `GNT-B-0006` arrive with empty `schedule_days` / `start_time`. A counsellor can't answer "is there an
evening classroom batch?" from the CRM, and the spec forbids guessing.

Please add these fields to every `batches[]` entry in `GET /integrations/crm/status`. They are all nullable, and the
CRM already has columns for them:

| Field | Type | Example | CRM column |
|---|---|---|---|
| `schedule_days` | string, ≤ 50 chars, the days the batch meets | `"Mon, Wed, Fri"` or `"Sat, Sun"` | `batches.schedule_days` (varchar 50) |
| `start_time` | `"HH:MM"`, IST | `"18:30"` | `batches.start_time` (time) |
| `end_time` | `"HH:MM"`, IST | `"20:30"` | `batches.end_time` (time) |
| `location` | string, ≤ 255 chars: classroom / room for Classroom and Hybrid; null for Online | `"Guntur Lab 2"` | `batches.location` (varchar 255) |

```json
{ "lms_course_id": "NIT-GNT-BAT-2026-000004", "course_code": "NIT-CRS-047", "branch_code": "NIT-GNT",
  "delivery_mode": "Classroom", "status": "Planned", "capacity": 30, "start_date": "2026-10-12",
  "end_date": null, "schedule_days": "Mon, Wed, Fri", "start_time": "18:30", "end_time": "20:30",
  "location": "Guntur Lab 2", "...": "existing fields unchanged" }
```

Rules the CRM will follow:
- **Missing field.** A missing or null field means "timing not confirmed". Staff see that, and the counselling
  assistant tells them to ask the Academic Coordinator. Nothing is invented.
- **Changes.** A timetable change must bring the batch back in the next delta pull, like any other batch change. The
  CRM overwrites its mirrored copy.
- **Which batches.** The CRM shows Planned and Open batches with seats left as "available". In Progress, Completed and
  Cancelled are never offered.
- **Unpublished batches.** If a batch must not be shown to learners yet, keep it out of `batches[]` until it is
  published, or tell us which status means "not public" (see Q3).

The CRM side is small and starts as soon as you confirm A1. In `apply_batch()` it will read the four fields; the
workbench, counselling brief and "waiting for a batch" recovery list will then match `preferred_timing` against them.

### A2 — Authoritative seats left (optional)

The CRM counts seats as `capacity` minus its mirrored *active* allocations (`batch_occupancy`). If the LMS ever holds
or reserves seats that are not allocations, that count is too high. If so, please add `seats_left` (integer) to
`batches[]`; the CRM will prefer it. If allocations are the only thing that uses seats, skip this.

---

## 3. Questions (CRM default until you answer)

| # | Question | CRM default |
|---|---|---|
| Q1 | Does the LMS send learners any **promotional** messages (for example, offers for another course)? Stop contact in the CRM covers sales outreach only. Class, activation and support messages are service messages and stay unaffected | The LMS sends only service messages, so stop contact doesn't need to go to the LMS. If you do send promotions, say so and we'll add a `PersonContactPreferenceChanged` event |
| Q2 | Does the LMS curriculum hold **prerequisites or overlap** per course / track that the CRM should read? The CRM's next-course paths (e.g. Power BI → Data Science) carry free-text prerequisites that the CRM's Academic Coordinator approves | No. The prerequisites stay in the CRM, and nothing is read from the LMS for this |
| Q3 | Is any batch status, or a flag, meaning **"exists but not public yet"**? | Planned and Open batches are treated as public and can be named to learners (as available, not as a confirmed seat) |

---

## 4. Joint test once A1 is built

1. **Set a timetable.** In the LMS, set Mon/Wed/Fri 18:30–20:30 at "Guntur Lab 2" on the Planned batch
   `NIT-GNT-BAT-2026-000004` (Java Full Stack, Guntur).
2. **Check it arrives.** Run `flask --app app lms pull` in the CRM. `GNT-B-0005` should show `schedule_days = "Mon, Wed,
   Fri"`, `start_time 18:30`, `end_time 20:30`, `location = "Guntur Lab 2"`.
3. **Check a change arrives.** Change the time to 19:00 in the LMS and pull again. The CRM copy must follow.
4. **Check nulls.** Clear the fields in the LMS and pull again. The CRM must show "timing not confirmed" and must not
   keep the old value.

---

## 5. What does not change

- **Events.** Every outbox event (`CourseUpserted`, `AdmissionQualified`, `AdmissionUpdated`, `AdmissionCancelled`,
  `FinanceSummaryUpdated`, `BranchUpserted`, `BranchFinanceSnapshot`, `AdmissionCurriculumMapped`) keeps the same
  envelope and payload.
- **Pull fields.** Every other field of `GET /integrations/crm/status` is unchanged.
- **Ownership.** Admissions, money, and now leads, deals and sales outreach are owned by the CRM. Academics, batches,
  allocation, completion and certificates are owned by the LMS.
- **Round 3.** It is not affected. The CRM's response to `CRM_ROUND3_LMS_REPLY.md` comes separately.

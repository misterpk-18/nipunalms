# LMS → CRM: sales playbook reply

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Answers:** [CRM_PLAYBOOK_LMS_ASKS.md](CRM_PLAYBOOK_LMS_ASKS.md) §2 (A1, A2) and §3 (Q1–Q3).
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** A1 is built (db `098_batch_timetable.sql`), and so is A2. `batches[]` now carries `schedule_days`,
`start_time`, `end_time`, `location`, `seats_left` and `readiness` (with `readiness_reason`). Q3 is decided: **a
Blocked batch is not public**. Step 1 of your joint test is already done on `NIT-GNT-BAT-2026-000004`. No other
field or event changed.

---

## 1. A1: the timetable in `batches[]`

The timetable is new on the LMS batch. The Academic Coordinator sets it on the batch form (Academic → Batches → New
batch / Edit batch), before any class is scheduled. A Planned batch has no class sessions yet, so the timetable can't
be worked out from sessions.

| Field | Format | Notes |
|---|---|---|
| `schedule_days` | `"Mon, Wed, Fri"`: three-letter days, week order, each once, `", "` between them | Up to 34 characters, so it fits your varchar 50 |
| `start_time`, `end_time` | `"HH:MM"`, 24-hour, IST | Always both or neither, and the end is after the start (database rules) |
| `location` | text ≤ 255 | Always `null` for a Live Online batch |

- **Nulls.** Each field is `null` until the coordinator sets it, and clearing one sends `null`. Read `null` as "timing
  not confirmed".
- **Changes.** Any change to the timetable brings the batch back in the next delta pull, like any other batch change.
- **Tests.** Covered by `backend/tests/test_batch_timetable.py`: set, change, clear, refusals, Live Online.

## 2. A2: `seats_left` (added)

`seats_left` = `capacity` minus the students holding an active allocation, never below 0. It is in every `batches[]`
entry, and any allocation change brings the batch back in the next pull.

Please prefer it over your own count. Allocations are the only thing that uses seats, but a combo student has **one
allocation per track**. Counting allocation rows would count that student several times, while the LMS counts each
student once per batch.

## 3. Questions

| # | Answer |
|---|---|
| Q1 | **No promotions.** The LMS sends no promotional messages, and it has no email, SMS or WhatsApp channel at all. Every LMS notification is in-app and about the learner's own service: classes, attendance, results, certificates, support, and career updates such as CV reviews and application status. No `PersonContactPreferenceChanged` event is needed. If the LMS ever adds outbound marketing, it will ask for one first |
| Q2 | **No.** LMS curricula hold modules and topics only, with no prerequisites or overlap between courses. Keep the next-course prerequisites in the CRM |
| Q3 | **Decided: a Blocked batch is not public.** Offer a batch only when `status` is Planned or Open **and** `readiness` is not `Blocked`. `readiness_reason` says why it is blocked (e.g. "No lead trainer assigned"), for staff only. `Pending Verification` (e.g. the Meet link isn't verified yet) may still be named as available. There is no separate "published" flag |

LMS batch states map as: Forming → *Planned*, Starting → *Open*, Running and Full → *In Progress*.

## 4. Joint test (your §4)

| Step | Status |
|---|---|
| 1 | ✅ **Done** (22:00 IST). `NIT-GNT-BAT-2026-000004` (Java Full Stack, Guntur, Planned) is set to Mon, Wed, Fri 18:30–20:30 at "Guntur Lab 2". A pull already returns `"schedule_days": "Mon, Wed, Fri"`, `"start_time": "18:30"`, `"end_time": "20:30"`, `"location": "Guntur Lab 2"`, `"seats_left": 29` |
| 2 | **Your pull.** Note that the batch is **`readiness: Blocked`** ("No lead trainer assigned"), and so is `…000005`. Under Q3 the CRM should list it as not offerable, with the reason. That is a useful first check. To test the "available" path, ask the LMS side to assign a Guntur lead trainer. The coordinator then sets readiness to Ready (the readiness dialog suggests it once the checks pass), and the batch comes back in the next pull |
| 3, 4 | **Ask the LMS side** to change the time to 19:00 and then clear the fields, after each of your pulls. Both are tested: each change returns in the next delta pull, and a clear sends `null` |

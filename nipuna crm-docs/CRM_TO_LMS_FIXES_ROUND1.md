# CRM → LMS integration: fixes for the LMS (round 1)

**For:** the developer or Claude Code session working in `nipunalms`.
**From:** the `nipuna-crm` side, after building and running round 1 of [docs/CRM_LOCAL_SETUP.md](../docs/CRM_LOCAL_SETUP.md).
**Date:** 2026-10-01. Everything here is local and dev only: CRM `nipunacrm-dev` on :5050 → LMS `nipunalms-dev` on :5060.
**This doc replaces** [CRM_ROUND1_REPLY.md](CRM_ROUND1_REPLY.md) as the thing to act on. That file is the short summary.

## How to use this doc

1. Read §1 for context (about 2 minutes).
2. Work through the fixes in §3 in the order of the table in §2. Every fix gives:
   - what is wrong, and the evidence for it;
   - where it is in the LMS code;
   - the change to make;
   - tests to add;
   - how to tell it is done.
3. Use §4 as the field-by-field reference for what the CRM sends today. Where this doc and `CRM_INTEGRATION.md` disagree, §4 is what is actually on the wire.
4. When you're done, run the joint check in §7 and send back what §8 asks for.

Nothing here asks the LMS to change its ownership rules. The CRM owns courses, admissions and money; the LMS owns academics.

---

## 1. Where things stand

- **Round 1 is built on the CRM side and live data is flowing.** The CRM writes an `lms_outbox` row in the same database transaction as each change. A worker posts the rows to `POST /api/v1/integrations/crm/events`.
- **Delivered so far: 30 events, all `Applied`.** That is 8 `CourseUpserted`, 11 `AdmissionQualified` and 11 `FinanceSummaryUpdated`. No 400 and no 422.
- **One real end-to-end check passed.** A payment verified in the CRM (Sana Begum, CRM admission 11) showed up in the LMS as student `NIT-STU-2026-004284`, enrolment `ENR-000106` and a finance summary.
- **Smoke test (§5 of the brief):** 201 → 200 replay → 409 on a changed payload → 401 on a wrong key. All as specified.
- **The bugs below don't come from rejected events.** They come from things the LMS **accepted** that left its data wrong or inconsistent (F1, F2), and from gaps that will reject or confuse future events (F3–F8).

## 2. Fix list

| ID | Priority | Fix | Type | LMS files |
|---|---|---|---|---|
| **F1** | **Blocker** | NIT-CRS-018 is a combo in the LMS seed but a single course in the CRM. 24 seeded combo enrolments now sit on a course the LMS marks as not a combo | Dev data | seed, `nipunalms-dev` |
| **F2** | **High** | `CourseUpserted` never removes combo components, and can flip a combo to a single course while combo enrolments still use its tracks | Code | `services/crm.py` `_course_upserted` |
| **F3** | **High** | Instalments are per **invoice**, not per admission. Two admissions on one invoice carry the same schedule, so totals and lists can double | Code + UI | finance service / repo / student and staff finance screens |
| F4 | Medium | The documented CRM field names `person_id`, `admission_id` and `complimentary_of_admission_id` are not aliased. The brief's own example payload gets a 400 | Code + docs | `controllers/crm.py` `FIELD_ALIASES`, `CRM_INTEGRATION.md`, `CRM_LOCAL_SETUP.md` |
| F5 | Medium | LMS field limits are shorter than the CRM's: course title 200 vs 255, cancel reason 500 vs unlimited. A longer value fails with 400 and gets stuck | Code + migration | `controllers/crm.py`, `courses.title` |
| F6 | Medium | The status pull returns 93 seeded students and 95 seeded admissions with made-up CRM IDs (`CRM-ADM-…`) | Dev data / code | seed, `repositories/crm.py` |
| F7 | Medium | Activation tokens: the CRM discards the one-time token, so 10 CRM-provisioned students can't activate unless the LMS reissues | Process + UI check | activation reissue path |
| F8 | Low | A repeated `AdmissionQualified` is used as a full refresh (start date, person edits). Confirm this behaviour, cover it with a test, and decide how a cleared email is sent | Code + test | `services/crm.py` `_admission_qualified`, `_upsert_student` |
| F9 | Low | There is no branch event. An unknown branch is a permanent 422 | Decision | — |
| F10 | Low | Update the LMS docs to match the wire format | Docs | `docs/CRM_INTEGRATION.md`, `docs/CRM_LOCAL_SETUP.md` |

---

## 3. Fixes in detail

### F1 · Course catalog conflict on NIT-CRS-018 (blocker, dev data)

**Problem.** The two systems describe a different product under the same course code.

| | CRM (owner) | LMS dev seed |
|---|---|---|
| NIT-CRS-018 | "Data Science with Python, SQL, Machine Learning & Applied AI", **single course** (`is_combo = false`, no `combo_courses` rows) | A **combo** with tracks `NIT-CRS-018/T1`, `/T2`, `/T3` and the included booster `NIT-CRS-019` |

The CRM sent `CourseUpserted` for 018 with `is_combo: false` and no components, and the LMS applied it. The LMS now has:

```
courses: NIT-CRS-018  is_combo = false  source_version = 1
course_components of 018: 4 rows (component_id 1–4), each still used by 24 enrolment_tracks and 1 curriculum_version
enrolments on 018: 24 seeded "Combo" enrolments (CRM-ADM-214, CRM-ADM-301 … 331), each with 4 tracks
                   + 2 CRM "Standalone" enrolments (CRM admissions 4 and 6, ENR-000099 / ENR-000101)
```

So the LMS holds combo enrolments under a course it marks as not a combo. Any screen or rule that branches on `courses.is_combo` (curriculum mapping, allocation per track, completion) now gets this course wrong.

**Check it yourself:**

```sql
-- nipunalms-dev
SELECT cc.component_id, cc.track_code, cc.role,
       (SELECT count(*) FROM enrolment_tracks et WHERE et.component_id = cc.component_id) AS tracks_in_use,
       (SELECT count(*) FROM curriculum_versions cv WHERE cv.component_id = cc.component_id) AS versions
FROM course_components cc JOIN courses c ON c.course_id = cc.parent_course_id
WHERE c.course_code = 'NIT-CRS-018';
```

**Fix.** The CRM owns the catalog, so the LMS dev seed has to agree with it:

1. Seed the LMS dev catalog from the CRM's 8 courses, with the same codes, titles, categories and statuses. All 8 are single courses today:

   | Code | Title |
   |---|---|
   | NIT-CRS-007 | AWS with DevOps |
   | NIT-CRS-018 | Data Science with Python, SQL, Machine Learning & Applied AI |
   | NIT-CRS-019 | Microsoft Power BI Data Analytics & Business Intelligence |
   | NIT-CRS-025 | Professional Graphic Design with AI Tools |
   | NIT-CRS-026 | Professional Video Editing with AI Tools |
   | NIT-CRS-028 | Complete Digital Marketing |
   | NIT-CRS-047 | Java Full Stack Developer |
   | NIT-CRS-052 | Python Full Stack Developer |

   The simplest way: let the catalog come only from `CourseUpserted`, and seed no courses at all.
2. If the LMS needs a combo to exercise combo features, **give it a code the CRM doesn't use** (for example `NIT-CRS-900`, marked as seed data), or ask the CRM side to create a real combo in CRM dev and send it. Say which; the CRM can do it in a few minutes.
3. Rebuild `nipunalms-dev`, then tell the CRM side. The CRM will resend everything with `flask lms backfill --force`. That uses new `event_id`s and higher `source_version`s, which a fresh LMS database accepts.

**Done when:**
- `NIT-CRS-018` in `nipunalms-dev` has 0 `course_components`, and no `Combo` enrolment points at it.
- Every LMS course whose code exists in the CRM has the CRM's title, category, `is_combo` and status.

### F2 · `CourseUpserted` must reconcile components (high, code)

**Problem.** `services/crm.py` → `_course_upserted()` only **adds or updates** the components listed in the event. Components missing from the event are left in place, and nothing stops `is_combo` changing from true to false while enrolments still use the tracks. That is how F1 happened silently; the event was stored as `Applied`.

**Change.** After the existing loop over `data["components"]`:

1. Collect the `component_id`s the event kept (created or matched).
2. Every other component of this course is **removed from the combo**:
   - If a component is still used by `enrolment_tracks` or `curriculum_versions`, **don't delete it.** Raise `BusinessRule` (422) and name the tracks and counts. Example message: `Course NIT-CRS-018: tracks NIT-CRS-018/T1, /T2, /T3, NIT-CRS-019 are still used by 24 enrolments and 4 curriculum versions; move or withdraw them before the CRM removes them`.
   - Otherwise delete it.
3. When `is_combo` is false, treat it as "keep no components" and apply rule 2. A single course must end up with 0 components, or the event must be refused with 422.
4. Make the whole check run **before** any change to `course.title`, `is_combo` and so on. It already runs inside `begin_nested()`, so raising rolls everything back. Keep it that way.

Why 422 and not "apply and warn": the CRM retries a 422 with backoff. After 12 tries (several hours) it marks the row Failed and raises a task for the CRM Super Admin. That is the visibility the CRM needs to fix it on its side, or to tell you to move the enrolments. Applying the event and only warning is what hid F1.

Sketch:

```python
kept = set()
for item in sorted(data["components"], key=lambda i: i["sort_order"]):
    ...                                  # existing create / update
    kept.add(component.component_id)
db.session.flush()

for component in catalog_repo.components_of(course.course_id):      # new repository helper
    if component.component_id in kept:
        continue
    in_use = catalog_repo.component_usage(component.component_id)  # {"enrolment_tracks": n, "curriculum_versions": m}
    if any(in_use.values()):
        blocked.append((component.track_code, in_use))
    else:
        db.session.delete(component)
if blocked:
    raise BusinessRule(f"Course {course.course_code}: ... still used ...")   # list them
```

**Tests** (`tests/test_crm_intake.py` or `test_crm_alignment.py`):

1. A combo with 3 components gets an event with 2 → the third is deleted; result `components: 2`.
2. A combo gets `is_combo: false` and no components, with no enrolments → 0 components, `is_combo = false`.
3. The same, but an enrolment track uses a component → 422. The course is unchanged: still a combo, same title, same `source_version`.
4. Re-sending the same event after the enrolment is withdrawn and its tracks removed → `Applied`.

**Done when:** all 4 tests pass and the existing CRM alignment tests still pass.

### F3 · Instalments belong to the invoice (high, code + UI)

**Problem.** In the CRM, one invoice can cover several courses, and each course becomes its own admission. Instalments are kept **per invoice**: there is no per-course schedule. `FinanceSummaryUpdated` therefore carries the invoice's schedule on every admission of that invoice.

Live example: Meera Joshi has CRM admissions 6 and 7, both on `INV-GNT-2627-0005`. Both finance summaries carry the same 2 instalments, and both say `next_due_amount` = the invoice's next balance. Shown per admission, the student and staff would see the same instalments twice. Summed per student or branch, overdue and due amounts double.

What the CRM sends to identify this:

```json
"invoice_numbers": ["INV-GNT-2627-0005"],
"installments_scope": "invoice",
"invoice_course_count": 2,
"installments": [ ...the invoice's schedule... ],
"next_due_date": "…", "next_due_amount": "…"
```

The per-admission figures **are** per course and safe to sum: `fee_total`, `verified_paid`, `pending_verification`, `waived`, `refunded`, `balance`, `payment_completion` and `receipts[]`. Each receipt amount is only the part of the payment allocated to that course.

**Change.**

1. **Store the scope.** Add `installments_scope` (text, default `'admission'`) and `invoice_course_count` (int, default 1) to `finance_summaries`. Read them in `_finance_summary_updated()`, and add both to the validator in `controllers/crm.py` `_finance_summary_updated`. Accept `"invoice"` / `"admission"`; `invoice_course_count` is an integer ≥ 0.
2. **Never sum or list instalments per admission when the scope is `invoice`.** Group by `invoice_numbers[0]` and show the schedule once per invoice, labelled with the invoice number and its courses: "INV-GNT-2627-0005 · Data Science + Power BI".
   - This applies to the student's finance screen (`services/finance.py` `my_summaries`) and the staff finance list (`repositories/finance.py` `branch_summaries_stmt`).
   - It also applies to any future overdue or due total.
3. **`next_due_*` follows the same rule.** It is the invoice's next due, so show it once per invoice.
4. **Per-course balances stay per admission.** Use `balance` for "what this course still owes".

**Tests:** two `FinanceSummaryUpdated` events for two admissions with the same invoice number and `installments_scope: "invoice"` → the student finance endpoint returns the schedule once, and a branch overdue total counts the invoice once.

**Done when:** the student finance view for Meera Joshi (CRM person 21) shows one schedule for `INV-GNT-2627-0005`, and both course balances (₹20,000 and ₹12,000).

If the LMS really needs instalments per course, say so in §8. Splitting them would be a CRM product decision, not something the CRM can do today.

### F4 · Accept the CRM's documented field names (medium, code + docs)

**Problem.** `CRM_LOCAL_SETUP.md` §4 and `CRM_INTEGRATION.md` §2.1 say the LMS maps `person_id → crm_person_id` and `admission_id → crm_admission_id`. Its "minimal AdmissionQualified" example sends `person_id` / `admission_id`. But `controllers/crm.py` has:

```python
FIELD_ALIASES = {"phone": "mobile", "course_title": "title", "delivery_mode": "mode"}
```

So that example returns **400** with `person.crm_person_id: Required` and `admission.crm_admission_id: Required`. The same applies to `complimentary_of_admission_id`.

The CRM is **not** affected today: it sends `crm_person_id`, `crm_admission_id` and `complimentary_of_crm_admission_id`. Fix it anyway, so the contract and the code agree before anyone else writes against the docs.

**Change.**

```python
FIELD_ALIASES = {"phone": "mobile", "course_title": "title", "delivery_mode": "mode",
                 "person_id": "crm_person_id", "admission_id": "crm_admission_id",
                 "complimentary_of_admission_id": "complimentary_of_crm_admission_id"}
```

`_from_crm` turns integer IDs into text only for names in `ID_FIELDS`. Because the alias is applied before that check, `person_id: 148` becomes `crm_person_id: "148"`. Verify this with a test.

**Tests:**
- The brief's minimal payload, sent as written → 201.
- A payload with both `admission_id` and `crm_admission_id` → the LMS-named field wins, as `_from_crm` already does for the other aliases.

**Done when:** the example in `CRM_LOCAL_SETUP.md` §4 works unchanged, or the docs are corrected (F10).

### F5 · Field limits shorter than the CRM's (medium, code + migration)

**Problem.** A value the CRM legitimately holds can fail LMS validation. That is a permanent 400 for the event, and every later event for the same admission is held behind it until a person steps in.

| Field | CRM limit | LMS limit | Where in the LMS |
|---|---|---|---|
| `course_title` → `title` | varchar(**255**) | **200** (validator and `courses.title`) | `_course_upserted` validator, `courses.title` column |
| `AdmissionCancelled.reason` | **text** (unlimited) | **500** | `_admission_cancelled` validator |
| `person_code` | 20 | 30 | OK |
| `admission_code` | 30 | 50 | OK |
| `full_name` | 150 | 150 | OK, equal |
| `phone` | 20, stored `+91XXXXXXXXXX` | `normalise_phone` | OK, passes |
| `receipt_number` | 30 | 50 | OK |
| `course_code` | 20 | 30 | OK |

**Change.**
- Raise `title` to 255: both the validator and a migration on `courses.title`.
- Raise `reason` to at least 2000, or make it `text` with no limit. Store it as `text`.

**Tests:**
- `CourseUpserted` with a 255-character title → 201.
- `AdmissionCancelled` with a 1,500-character reason → 201.

### F6 · Seeded rows in the status pull (medium, dev data / code)

**Problem.** `GET /integrations/crm/status?since=2026-09-30T00:00:00+05:30` returns:

```json
{"persons": 103, "admissions": 106, "academics": 106, "batches": 5, "certificates": 4}
```

Of those, **93 students and 95 admissions** are LMS seed rows whose CRM IDs don't exist in the CRM (`CRM-ADM-214`, `CRM-ADM-301` …). When the CRM starts applying the pull (round 2), it will skip unknown IDs. But the noise hides real results, and the round-2 test can't tell "applied" from "skipped".

**Change (pick one):**
1. **Preferred:** after F1, rebuild `nipunalms-dev` without seeded students, admissions or enrolments that claim to come from the CRM. Let all of them arrive from the CRM backfill. Keep LMS-only seed data (curricula, batches, trainers, sessions) if it doesn't fake CRM IDs.
2. If the seed must stay, mark the seeded rows (for example `crm_source = 'seed'`) and leave them out of `status_since()`.

**Done when:** after a CRM backfill, the pull's `persons` / `admissions` lists contain only numeric CRM IDs that exist in the CRM (persons 4–23, admissions 1–11 today).

### F7 · Activation tokens the CRM throws away (medium, process)

**Problem.** For each new student login, the `AdmissionQualified` response carries a one-time `activation_token`. The CRM never logs it or stores it; it keeps only a flag, `activation_token_issued = true`. That follows the brief: "treat it as a secret". The CRM has no way to deliver it yet; that is decision §3.7 in `CRM_INTEGRATION.md`.

Result: the 10 students provisioned so far (CRM persons 4, 5, 6, 10, 15, 16, 18, 21, 22, 23; all `activation_status = 'Activation Pending'`) can only activate if the LMS **reissues** a link.

**Change in the LMS (now, whatever the final decision):**
1. Confirm the Academic Coordinator / Super Admin reissue path works for a student created by CRM provisioning: `channel = "CRM provisioning"`, `issued_by = NULL`. Add a test if there isn't one.
2. On the student list, make "Activation Pending + created by the CRM" easy to filter, so staff can reissue in bulk.
3. Only if the owners pick option B below: stop issuing a raw token in the response, so it never crosses the wire unused.

**Decision needed (both owners), to answer in §8:**
- **A.** The CRM sends `{LMS}/activate?token=…` by WhatsApp or email. The CRM would add a template and a task. The token would have to sit in the CRM outbox until it is sent; the CRM would encrypt it or keep it out of the outbox.
- **B.** Activation stays supervised in the LMS (a coordinator reissues). The LMS stops returning the token to the CRM.

### F8 · A repeated `AdmissionQualified` is a full refresh (low, confirm + test)

**What the CRM does.** `AdmissionUpdated` has no fields for `planned_start_date`, `seat_type` or person details. So the CRM sends `AdmissionQualified` **again** with the next `source_version` when:
- an admission's `planned_start_date` changes, or
- a person's `full_name`, `phone`, `email` or `preferred_language` is edited. The CRM then re-sends every non-cancelled admission of that person.

Reading `_admission_qualified()` / `_upsert_student()` / `_ensure_enrolment()`, the LMS handles this safely:
- it updates the admission and student fields;
- it doesn't create a second login or token, because `users_repo.get_by_student_id` already finds one;
- it doesn't reset an enrolment that is already being served.

**Asks.**
1. **Confirm** this is intended, and add a test that pins it: qualify, allocate, then re-qualify with a new name and start date → name and start date updated, allocation and status unchanged, no new activation token.
2. **Clearing a value.** `_upsert_student` skips `None`, so if the CRM removes a person's email, the LMS keeps the old one.
   - Decide whether `None` should mean "clear". The CRM always sends the full person object, so a missing key never happens.
   - Recommended: apply `None` for `email` and `name_te`.
   - Never clear `full_name`; the CRM never sends it empty.
3. **Optional, cleaner:** add `planned_start_date` and `seat_type` to `AdmissionUpdated`, and a `PersonUpdated` event (`crm_person_id` + the person fields). If you add them, say so and the CRM will switch over. Until then it keeps using the full refresh.

### F9 · Branches (low, decision)

The LMS refuses an unknown branch code with 422 (`_branch()`). The CRM never sends branches. `NIT-GNT` and `NIT-VIJ` match today. A new CRM branch would make every event for its admissions wait 422 until someone creates the branch in the LMS.

Decide one:
- a `BranchUpserted` event: `branch_code`, `branch_name`, `city`, `is_active`. The CRM can send it.
- a documented manual step: "create the branch in the LMS before the CRM opens it".

### F10 · Update the LMS docs to match the wire format (low)

- **`CRM_LOCAL_SETUP.md` §4 example:** use `crm_person_id` / `crm_admission_id`. Or keep the CRM names once F4 is in.
- **`CRM_INTEGRATION.md` §2.1, `FinanceSummaryUpdated` row:** add `installments_scope`, `invoice_course_count`, and the "per invoice" rule from F3.
- **`CRM_INTEGRATION.md` §2.1, `AdmissionQualified` row:** note that it is also sent as a full refresh (F8).
- **`CRM_INTEGRATION.md` §4 "Status in the LMS":** add the F1–F9 results.
- Note: the CRM does not send `AdmissionUpdated.status` (Paused / Active), because the CRM has no pause action yet.

---

## 4. What the CRM sends today (field reference)

### 4.1 Envelope (every event)

| Field | Type | Notes |
|---|---|---|
| `event_id` | uuid string | uuid4, generated once when the outbox row is written. **Identical on every retry**; a database trigger stops the CRM from changing it |
| `event_type` | string | One of the five below |
| `source_version` | int ≥ 1 | Separate counters for course (`course:<crm course_id>`), admission (`admission:<id>`) and finance summary (`finance:<id>`). Increases by 1 per event for that record |
| `occurred_at` | ISO 8601, +05:30 | When the change was committed in the CRM. Identical on every retry |
| `data` | object | Below. Money as strings with 2 decimals (`"17000.00"`), dates `YYYY-MM-DD`, IDs as integers |

### 4.2 `CourseUpserted`

| Field | Type | Null? | CRM source |
|---|---|---|---|
| `course_code` | string ≤ 20 | no | `courses.course_code` (never changes in the CRM) |
| `course_title` | string ≤ **255** (F5) | no | `courses.course_title` |
| `category` | string ≤ 100 | no | `courses.category` |
| `is_combo` | bool | no | `courses.is_combo` |
| `status` | `Active` / `Inactive` / `Archived` | no | `courses.status` |
| `components[]` | list | **sent only when `is_combo` is true** | `combo_courses`: `{component_course_code, is_bonus, sort_order}` |

Sent on course create and update, and when combo components are set. On a backfill, single courses go before combos.

### 4.3 `AdmissionQualified`

`person`:

| Field | Type | Null? | CRM source |
|---|---|---|---|
| `crm_person_id` | int | no | `persons.person_id` |
| `person_code` | string ≤ 20 | no | `persons.person_code` (`PER-VIJ-00010`) |
| `full_name` | string ≤ 150 | no | `persons.full_name` |
| `phone` | string `+91XXXXXXXXXX` | no | `persons.phone` (the LMS maps it to `mobile`) |
| `email` | string ≤ 255 | **yes** | `persons.email` |
| `preferred_language` | `English` / `Telugu` | no | `persons.preferred_language` (the LMS maps it to `en` / `te`) |

`admission`:

| Field | Type | Null? | CRM source |
|---|---|---|---|
| `crm_admission_id` | int | no | `admissions.admission_id` |
| `admission_code` | string ≤ 30 | no | `NIT-VIJ-2026-000004` |
| `course_code` | string | no | the admission's course |
| `original_branch_code` | string | no | `admissions.original_branch_id` → code |
| `service_branch_code` | string | no | `admissions.service_branch_id` → code |
| `collecting_branch_code` | string | no | the admission's invoice collecting branch. A complimentary admission uses its paid admission's invoice; with neither, the original branch |
| `delivery_mode` | `Classroom` / `Online` / `Hybrid` | no | the LMS maps `Online` to `Live Online` |
| `seat_type` | `Confirmed Seat` / `Future Plan` | no | |
| `planned_start_date` | date | yes | |
| `admission_date` | date | no | |
| `complimentary_of_crm_admission_id` | int | yes | set only for a complimentary admission |
| `access_until` | date | yes | complimentary access end |

`enrolments` is never sent: one course per CRM admission.

When it's sent:
- a new admission: automatic on payment verify or allocate, manual create, or complimentary;
- a full refresh (F8).

A paid admission is always sent before its complimentary one.

### 4.4 `AdmissionUpdated`

| Field | When present |
|---|---|
| `crm_admission_id` | always |
| `service_branch_code` | after a service-branch transfer |
| `delivery_mode` | after a delivery-mode change |
| `status` | **never yet** (the CRM has no pause or resume) |

Never sent for a cancelled admission.

### 4.5 `AdmissionCancelled`

`{crm_admission_id, reason}`. `reason` is the CRM's free-text cancellation reason, with no length limit (F5). A `FinanceSummaryUpdated` follows in the same batch, with `balance` = `"0.00"`.

### 4.6 `FinanceSummaryUpdated`

| Field | Type | Meaning / CRM source |
|---|---|---|
| `crm_admission_id` | int | |
| `fee_total` | money | `admission_balances.final_fee` |
| `verified_paid` | money | verified payments on this course (reversals netted) |
| `pending_verification` | money | claims not verified yet; never counted as paid |
| `waived` | money | approved waivers |
| `refunded` | money | refund payouts with status Completed |
| `balance` | money | `outstanding` = fee − verified − waived. **0 for a cancelled admission** |
| `payment_completion` | `Unpaid` / `Part Paid` / `Paid` | |
| `invoice_numbers` | list of 1 string | the invoice the admission is on (empty for a complimentary admission) |
| `installments[]` | list | **The invoice's schedule** (F3): `{installment_no, due_date, amount, covered, balance, due_position (Paid / Upcoming / Overdue)}` |
| `installments_scope` | `"invoice"` | extra field (F3) |
| `invoice_course_count` | int | courses on that invoice; > 1 means the schedule is shared |
| `next_due_date` / `next_due_amount` | date / money, nullable | The first instalment with a balance. **It can already be overdue** |
| `receipts[]` | list | `{receipt_number, date (payment date), amount}`: verified, not reversed, only the part **allocated to this course** |
| `as_of` | ISO 8601 +05:30 | when the summary was built |

It's sent for **every admission on the invoice** after any of: payment recorded, verified, failed or allocated; correction approved (reversal); fee change applied; refund decided (waiver) or paid out; invoice cancelled; instalment due date changed. It's also sent right after a new admission and after a cancellation.

## 5. How the CRM delivers (what the LMS can rely on)

- **Order.** For each admission, events go one at a time and oldest first. An admission's finance never overtakes its `AdmissionQualified`. Different admissions and courses are independent, so a course still waiting can make an admission's first event get a 422 until the course arrives. That is the documented behaviour, and the CRM retries.
- **Retries.** 422 / 5xx / timeout: the same request again, with backoff of 30 s doubling up to 1 h, at most 12 attempts. After that the row becomes Failed and the CRM Super Admin gets a task.
- **400 / 409.** The row becomes Failed at once and a task is raised. The CRM fixes its side and sends a **new** event (new `event_id`, higher version). It never sends a changed payload under an old `event_id`.
- **401 / 403 / 404.** The CRM stops the run and keeps the row Pending. It treats these as configuration errors.
- **What the CRM stores from your answer:** `status`, `result` and the HTTP code. It drops `activation_token`.
- **One CRM transaction can produce several events.** Example: verifying a payment that admits two courses gives 2 × `AdmissionQualified` + 2 × `FinanceSummaryUpdated`.
- **Concurrency.** Two CRM workers can't send the same row at once (rows are claimed with a lease). Even if one were sent twice, your `event_id` idempotency answers 200.

## 6. Dashboards that show "Not Configured" (proposal; reply in §8)

`services/dashboards.py` marks these as CRM-owned:
- `verified_collections`
- `new_paid_admissions`
- `overdue_followups`
- `overdue_amount`
- `overdue_payment_verifications`

The CRM has all of them. Proposed new event, keyed per branch and sent by a CRM job every 15 minutes (and on change where cheap):

```json
{"event_type": "BranchFinanceSnapshot", "source_version": 42, "data": {
  "branch_code": "NIT-GNT",
  "period": {"start": "2026-10-01", "end": "2026-10-31", "target_version": "TM-2026-10-v1"},
  "verified_collections": {"target": "500000.00", "achieved": "182000.00"},
  "new_paid_admissions": {"target": 20, "achieved": 7},
  "overdue": {"amount": "64000.00", "invoices": 5,
              "by_age_band": [{"band": "0-30", "amount": "40000.00"}, {"band": "31-60", "amount": "24000.00"}]},
  "overdue_followups": 3,
  "payment_verifications": {"pending": 2, "amount": "29000.00", "oldest_at": "2026-10-01T09:12:00+05:30", "overdue": 1},
  "as_of": "2026-10-01T10:00:00+05:30"}}
```

| Field | CRM source |
|---|---|
| Targets | `target_versions` (Approved, covering today) + `target_lines` (`verified_collections_target`, `paid_admissions_target` per branch) |
| Achieved collections | verified payments in the period |
| Achieved admissions | admissions whose ₹1,000 token was reached in the period |
| `overdue` | the `installment_dues` view (`due_position = 'Overdue'`, `age_band`, `contact_hold`) |
| `overdue_followups` | open COLLECTIONS tasks past due |
| `payment_verifications` | payments in `Pending Verification`, and the `PAYMENT_VERIFICATION` task SLA (30 staffed minutes) |

Reply with: accept / change fields / prefer pulling from a CRM endpoint. Also send the exact validator rules you'll apply. The CRM builds it next round.

## 7. Joint check after the fixes

LMS side:

1. Run the LMS test suite, including the new tests from F2, F3, F4, F5, F7 and F8.
2. Rebuild `nipunalms-dev` per F1 / F6 and start it on :5060 with the same `CRM_SERVICE_KEY`.
3. Tell the CRM side the LMS is ready.

CRM side (it will do this):

```bash
cd nipuna-crm/backend
APP_ENV=development ../venv/bin/flask --app app lms backfill --force   # every course, admission and finance summary, as new events
APP_ENV=development ../venv/bin/flask --app app lms deliver --loop     # until the counts stop changing
APP_ENV=development ../venv/bin/flask --app app lms outbox --failed    # expect: all Delivered, no rows listed
APP_ENV=development ../venv/bin/flask --app app lms status-check --since 2026-10-01T00:00:00+05:30
```

Then both sides check in `nipunalms-dev`:

```sql
-- every LMS course from the CRM matches the CRM (expect 8 rows, 0 components each)
SELECT c.course_code, c.title, c.is_combo, c.status,
       (SELECT count(*) FROM course_components cc WHERE cc.parent_course_id = c.course_id) AS components
FROM courses c ORDER BY 1;

-- admissions / students / finance from the CRM (expect 11 / 10 / 11 today)
SELECT count(*) FROM admissions WHERE crm_admission_id ~ '^[0-9]+$';
SELECT count(*) FROM students   WHERE crm_person_id   ~ '^[0-9]+$';
SELECT count(*) FROM finance_summaries f JOIN admissions a USING (admission_id) WHERE a.crm_admission_id ~ '^[0-9]+$';

-- shared invoice: admissions 6 and 7 carry the same invoice schedule, flagged (F3)
SELECT a.crm_admission_id, f.invoice_numbers, f.installments_scope, f.invoice_course_count, f.balance
FROM finance_summaries f JOIN admissions a USING (admission_id) WHERE a.crm_admission_id IN ('6', '7');
```

The figures to compare against, from CRM `admission_balances` on 2026-10-01:

| CRM admission | Fee | Verified | Balance | Status |
|---|---|---|---|---|
| 1 | 25000 | 25000 | 0 | Paid |
| 2 | 24000 | 12000 | 12000 | Part Paid |
| 3 | 22000 | 22000 | 0 | Paid |
| 4 | 30000 | 30000 | 0 | Paid |
| 5 | 22000 | 1000 | 21000 | Part Paid |
| 6 | 30000 | 10000 | 20000 | Part Paid |
| 7 | 22000 | 10000 | 12000 | Part Paid |
| 8 | 22000 | 22000 | 0 | Paid (₹2,000 refunded) |
| 9 | 18000 | 18000 | 0 | Paid |
| 10 | 22000 | 22000 | 0 | Paid |
| 11 | 22000 | 5000 | 17000 | Part Paid |

Finally, one live change end to end. The CRM side will:
- record and verify a new payment;
- transfer an admission to `NIT-VIJ`;
- change a delivery mode to Online;
- cancel an admission.

Expect in the LMS, within a minute each:
- the new balance and receipt;
- the enrolment ended as Transferred, with a coordinator notification at NIT-VIJ;
- mode `Live Online`;
- enrolments Withdrawn and `crm_status = 'Cancelled'`.

## 8. Send back

1. The status of F1–F10: done / changed differently (how) / declined (why).
2. The decisions: F3 (instalments by invoice, OK?), F7 (A or B), F8 (full refresh OK? clearing `None`? `PersonUpdated`?), F9 (branch event or manual).
3. §6: accept the snapshot event as written, or the fields and validator rules you want instead.
4. Any new field the LMS now requires or validates differently, with the exact rule. Example: "`installments_scope` required, one of …".
5. When the LMS dev database has been rebuilt and is ready for `flask lms backfill --force`.

The CRM side will then:
- resend everything;
- start round 2: the snapshot event, the activation decision, and applying the status pull to the CRM columns (`persons.lms_user_id`, `admissions.lms_status`, academics, batches, certificates).

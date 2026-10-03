# LMS → CRM: round 4 request

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Context:** the LMS checked itself against the approved modules 14–27 and is closing the gaps in phases
(`nipunalms/docs/GAP_FIX_PLAN.md`, register in `docs/GAPS.md`). A few gaps need data only the CRM holds.
**Date:** 2026-10-03. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** §1 lists two changes the LMS has already made that the CRM should know about. Neither needs a CRM
change. §2 has five asks; A1 and A2 matter most. §3 has three questions, each with the default the LMS uses until you
answer.

---

## 1. Already changed on the LMS side (no CRM change needed)

| Change | What the CRM sees |
|---|---|
| **Historical imports** (db 099). The event envelope accepts an optional `"historical": true`. Such an event, or any event whose `occurred_at` is more than 72 hours old (`crm_notify_max_age_hours`), is applied with its original dates but sends **no** notices to LMS staff | Nothing changes for normal pushes. Set the flag on `flask lms backfill` re-sends, so LMS coordinators aren't told about old admissions as if they were new |
| **Certificates wait for the fee** (db 100, Module 22 §5). A certificate can't be recommended or issued until the paying admission's `FinanceSummaryUpdated` shows `payment_completion = "Paid"` (or `balance <= 0`). A complimentary admission follows its paid admission. A Founder / CEO or Super Admin can approve a *financial-release exception* in the LMS; it doesn't waive the debt | Please keep `FinanceSummaryUpdated` current after every verified payment, waiver or refund. Without a summary, the certificate shows "fee status not received" |
| **Certificate changes go through an independent approver.** Corrections, revocations and **reinstatements** are requested in the LMS and approved by someone else. A reinstatement moves a certificate from Revoked back to Issued, with the same number and version and the original issue date | `CertificateChanged` can now go **Revoked → Issued** for the same `certificate_number` / `version`, with `revoked_at` and `revoked_by_email` null again. The CRM mirror should accept this |

---

## 2. Asks

### A1 — Date of birth and guardian in `AdmissionQualified` (needed; Modules 17, 21, 23, 26)

The approved modules have under-18 rules. A guardian authorises recording and placement sharing, gets academic
updates, and a payer gets financial notices. Adult payers get no academic information by default. The LMS has
neither a date of birth nor a guardian. Please add to the `person` block (all optional):

```json
"person": { "...": "existing fields",
  "date_of_birth": "2009-04-17",
  "guardians": [ { "crm_guardian_id": "G-77", "full_name": "K. Ramesh", "relation": "Father", "phone": "9876500000",
                   "email": null, "verified_by": "Document", "verified_at": "2026-09-20T10:00:00+05:30",
                   "may_receive": ["academic", "financial"] } ] }
```

`may_receive` is the permitted scope. Leave out `financial` for a guardian who isn't the payer. A full refresh
(`AdmissionQualified` with the next `source_version`) replaces the list.

### A2 — Contact restrictions and consent (needed; Modules 26 §6, 27 §5)

The integrations register lists access and offboarding changes, stop-contact restrictions and entitlement changes as
**sync priority 1**. The sales playbook's *stop contact* rule is sales-only today (your Q1, round 3). For learning
messages the LMS needs to know when a person has opted out of a channel, or withdrawn consent for recordings,
testimonials or AI use. It rechecks consent before every delayed send. Proposed new event:

```json
{ "event_type": "PersonRestrictionsUpdated", "source_version": 3,
  "data": { "crm_person_id": "P-100", "effective_at": "2026-10-03T12:00:00+05:30",
            "channels": { "WhatsApp": "opted_out", "Email": "allowed", "SMS": "allowed" },
            "consents": { "recording_viewing": true, "promotional_use": false, "ai_training": false } } }
```

Versioned per person, like courses and admissions.

### A3 — Cancellation and refund detail (Module 26 §4)

The LMS should tell the student when a cancellation takes effect and how a refund is progressing. Please add
`access_effective_date` and `refund_status` (`None` / `Requested` / `Approved` / `Paid`) to `AdmissionCancelled`. Please
keep `refunded` current in `FinanceSummaryUpdated`.

### A4 — Placement service endpoints (D5, Module 23)

Under D5 the CRM owns employers, openings and applications. The LMS keeps the learning side: career profile, CV review,
internships, and the support period from approved completion. The LMS Career screen needs:

| Endpoint (CRM, service key) | Purpose |
|---|---|
| `GET /lms/openings?crm_person_id=` | Approved, open opportunities the student may see (title, employer, location, mode, closing date or "Open Until Filled", compensation with currency and period) |
| `POST /lms/applications` | `{crm_person_id, opening_id, cv_reference, consent_reference}`: a Nipuna-referred application with the student's consent for that named opportunity |
| `GET /lms/applications?crm_person_id=` | Application stages, interviews and outcomes for the student's own screen |

Shapes are open for discussion. A later round is fine.

### A5 — New batch states, heads-up (gap fix phase 6)

Module 15 adds batch states. `batches[].status` will be able to carry `Proposed` (waiting for Branch Manager
confirmation), `On Hold` and `Archived`, on top of today's values. Please map them in the CRM mirror (Front Office
offers neither On Hold nor Archived batches).

**Confirmed (LMS phase 6, db 103):** `batches[].status` and `BatchUpserted.status` are exactly one of `Planned`,
`Proposed`, `Open`, `In Progress`, `On Hold`, `Completed`, `Cancelled`, `Archived`. `Planned` is a draft; `Proposed`
waits for the Branch Manager and is not confirmed (do not offer it as a confirmed batch); `Open` is confirmed;
`On Hold` returns to its earlier status when resumed; `Archived` follows `Completed` or `Cancelled` and has no live
activity. No other field changes shape.

---

## 3. Questions (with the LMS default until answered)

| # | Question | LMS default |
|---|---|---|
| Q1 | Does Nipuna admit under-18 learners at all? | Treat every learner as an adult until A1 arrives; under-18 handling stays open in `GAPS.md` |
| Q2 | Is `payment_completion = "Paid"` the right signal for a cleared final fee, or should the LMS read `balance` (after waivers) only? | Either `Paid` or `balance <= 0` clears it |
| Q3 | Should a reinstated certificate come with its own CRM-side event or flag, beyond the status going back to Issued? | Status change only |

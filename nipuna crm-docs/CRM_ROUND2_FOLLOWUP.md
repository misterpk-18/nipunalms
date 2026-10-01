# CRM → LMS: round 2 follow-up (D3, D4, R1)

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Answers:** [CRM_ROUND2_LMS_REPLY.md](CRM_ROUND2_LMS_REPLY.md) §3.1, §3.2, §4 items 10–12 and §5 (R1, R2).
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** the CRM now sends `BranchUpserted` and `BranchFinanceSnapshot` (CRM db `029_lms_branch_events.sql`).
Both were delivered live and `Applied`. The R1 batches and allocations came through the pull with nothing held.
**Nothing has to change in the LMS.** §4 has one doc fix and one question about the snapshot period.

---

## 1. Status of your §4 list (items 10–12)

| # | Item | Status |
|---|---|---|
| 10 | `BranchUpserted` | ✅ Written when a branch's name, city or email is edited (`PATCH /branches/{id}`); address, phone and invoice details send nothing. The CRM has no create-branch screen, and `receipt_prefix` / `is_active` can't be edited through the API, so the short-code 422 can't happen from the CRM. Backfill: `flask lms backfill --branches`; a full backfill now sends branches first. A branch added later in SQL is sent by running the backfill again (records already sent are skipped) |
| 11 | `BranchFinanceSnapshot` job | ✅ Job `lms-finance-snapshot`: one event per active branch every 15 minutes, record and version key `branch-finance:<id>`. A snapshot still unsent when the next one is written is marked *Superseded* and never sent, so an LMS outage doesn't leave a backlog of old snapshots. With no `LMS_BASE_URL` / key the job does nothing |
| 12 | Activation (D1) | No change: `activation_token` is still dropped. Only `activation_token_issued` is kept |

**Live run (22:29 IST).** `NIT-GNT` and `NIT-VIJ`: `BranchUpserted` v1 → `Applied`, `created: false`. Snapshots v1 →
`Applied` for both branches. Neither branch has an Approved target this month, so both sent `period: null` with null
targets.

## 2. Where the snapshot figures come from

These are the CRM dashboard's own rules, so both systems show the same numbers.

| Field | CRM source |
|---|---|
| `period`, targets | The Approved `target_versions` row covering today, and this branch's `target_lines` row. If there is no version, or no line for the branch, the CRM sends `period: null` and null targets |
| `collections.verified` | Verified payments by collecting branch, net of reversals, over the target period (or the current calendar month when there is none). Never below 0.00 |
| `paid_admissions.count` | Admissions whose first verified payment (the ₹1,000 token) falls in that period, counted by original branch |
| `overdue` | `installment_dues` with `due_position = 'Overdue'`, by collecting branch. `by_age_band` uses the CRM's seven bands in order: `1–3 days`, `4–7 days`, `8–15 days`, `16–30 days`, `31–60 days`, `61–90 days`, `91+ days` (en dash). Bands with nothing overdue are left out |
| `verifications` | Payments in *Pending Verification*. `overdue_count` counts those whose open `PAYMENT_VERIFICATION` task is past its due time. `oldest_at` is when the oldest one was recorded |
| `followups.overdue_count` | Open leads past their next follow-up time: the CRM Branch dashboard's "overdue follow-ups" |
| `followups.broken_promises` | *Broken* payment promises on invoices that still have a balance. Once an invoice is settled, its broken promises stop counting |

## 3. Your §5

| # | Result |
|---|---|
| R1 | ✅ Verified. The pull applied `batches_applied: 2, academics_applied: 2`, with no holds. CRM batches `GNT-B-0005` = `NIT-GNT-BAT-2026-000004` (`NIT-CRS-047`, *Planned*, 30, starts 2026-10-12) and `GNT-B-0006` = `…000005` (`NIT-CRS-052`, *Planned*, 25, starts 2026-10-19). Admissions 1 and 2 are *Scheduled* / *Mapped*, each with one *Active* allocation and no joining date yet |
| R2 | Noted. The CRM keeps the `LMS` fallback for the authoriser and expects it never to fire |

## 4. For the LMS

| # | Kind | What |
|---|---|---|
| A1 | Doc fix | `docs/CRM_INTEGRATION.md` §2.1, the `AdmissionUpdated` row still says "The CRM has no pause action yet, so `status` is not sent". Since round 2 the CRM sends `status: Paused` / `Active` from `POST /admissions/{id}/pause` and `/resume`. §3.2 also says the watermark is in `app_settings`; it is in the CRM table `lms_pull_state` |
| A2 | Question (optional) | When a branch has no target, its `collections.verified` and `paid_admissions.count` cover the current calendar month, but `period` is `null`, so the LMS can't show which period they cover. Your validator already accepts a `period` with null targets. Should the CRM always send the period of the actuals (e.g. `Oct 2026`) and keep the targets null when there is none? The CRM follows §3.2 as written until you say yes |

---

CRM changes, for reference: db `029_lms_branch_events.sql` (two event types and a *Superseded* outbox status),
`services/lms_sync.py` (`BranchUpserted`), `services/lms_finance.py` (the snapshot), tests in
`backend/tests/test_lms_sync.py`. All 235 CRM backend tests pass.

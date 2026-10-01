# LMS → CRM: reply to the round 2 follow-up

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Answers:** [CRM_ROUND2_FOLLOWUP.md](CRM_ROUND2_FOLLOWUP.md) §4 (A1, A2).
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** confirmed on the LMS side. Both branches' `BranchUpserted` and `BranchFinanceSnapshot` v1 (22:29 IST)
are Applied, and the dashboard finance tiles now show your figures instead of *Not Configured*. A1 is fixed. For A2:
**yes, always send the period.** No LMS code change was needed. Round 2 is closed on both sides; the only open item is
activation-link delivery (D1), once WhatsApp / email exists.

---

## A1 — Doc fixes (done)

`docs/CRM_INTEGRATION.md` is updated:

- **§2.1 `AdmissionUpdated`.** `status` (Paused / Active) is sent by `POST /admissions/{id}/pause` and `/resume`.
- **§2.1 `BranchUpserted`.** It is sent when a branch's name, city or email is edited, and by
  `flask lms backfill --branches`.
- **§3.2.** The watermark lives in the CRM table `lms_pull_state`.
- **§3.13.** It now describes how each snapshot figure is computed, citing your follow-up §2.

## A2 — Snapshot period (yes)

Always send `period` as the period the figures cover:

- **With an Approved target:** the target's period, as today.
- **With no target:** the current calendar month (e.g. `{"label": "Oct 2026", "start": "2026-10-01", "end":
  "2026-10-31"}`), with both targets `null`.

The LMS already accepts this and shows the period's label on the tile. It doesn't show a target until one exists.
`period: null` is still accepted, so nothing breaks before you switch. The contract (CRM_INTEGRATION §2.1) now says
`period` is always sent. A target without a period is still a 422.

Covered by `backend/tests/test_crm_branches_finance.py::test_the_period_of_the_actuals_is_shown_without_a_target`.

## Noted

- **Age bands.** The seven age bands (`1–3 days` … `91+ days`, en dash) are shown as sent. The LMS adds them up per
  band name across branches, so keep the names identical in every branch.
- **Staleness.** A snapshot older than 60 minutes is flagged *stale* on the tiles. If the job stops, the dashboards say
  so within the hour.

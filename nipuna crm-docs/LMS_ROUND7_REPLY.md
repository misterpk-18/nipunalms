# LMS reply, round 7 (17 Oct 2026): answers to the CRM docs of 15–16 Oct

## D19, preferred batch: done (LMS db 116)
- `AdmissionQualified.admission.preferred_batch_code` is now read and stored on the admission. It is a preference only; it is never refused.
- A code that names no LMS batch, or a batch of another course or branch, still comes back in `result.warnings`. A resend without the key clears the preference.
- The Branch Manager's **Waiting for a batch** screen shows "Preferred by counsellor" on the matching batch. The Branch Manager still allocates.
- Migration: apply `db/116_preferred_batch.sql` (done on the LMS `nipunalms-dev`).

## "Open in LMS" link: done
`{LMS_WEB_URL}/academic/batches?crm_admission_id=…&student=<student code>` now opens **Waiting for a batch** filtered to that student (the `student` value is the LMS student code, which the CRM already sends as `lms_user_id`). Without `student` it opens the Branch Manager's batch list. No CRM change needed.

## D17, batch readiness values
The LMS sends exactly three: `Ready`, `Pending Verification` (the Meet organizer is not verified yet) and `Blocked` (a required check fails). Only `Blocked` should hide a batch from sales; `Pending Verification` is a to-do for the LMS side, not a reason to withhold the batch. The CRM's current rule is right.

## D13, instalments on multi-course invoices
Already handled: with `installments_scope: "invoice"` the LMS shows and sums the schedule once per invoice (`invoice_numbers[0]`) and keeps the per-course figures per admission. No per-course split needed.

## Still on the CRM side
- Four old failed events in the LMS (two `AdmissionCurriculumMapped`, one `AdmissionQualified` for the unknown course `NIT-CRS-999`): see `LMS_FAILED_EVENTS_NOTE.md`. Stop sending `AdmissionCurriculumMapped`.
- The LMS's outbox is read by the CRM's `flask lms pull`; rows stay Pending until it runs.

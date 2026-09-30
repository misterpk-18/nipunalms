# Nipuna LMS — Backlog

Open product decisions and gaps found while building. Newest at the bottom of each section.

## CRM connection

| Item | Notes |
|---|---|
| CRM must emit events | The CRM does not yet post `CourseUpserted`, `AdmissionQualified`, `AdmissionUpdated`, `AdmissionCancelled`, `FinanceSummaryUpdated` to `/api/v1/integrations/crm/events`. Needs an outbox + worker in `nipuna-crm` (guide §17) |
| Outbox delivery | `crm_outbox` rows are queued but not delivered; either build a worker that pushes to a CRM endpoint, or the CRM polls `GET /integrations/crm/status?since=` — decide with the CRM team |
| `lms_last_synced_at` | Set by the CRM when it applies a pull/push; the LMS reports `now` at pull time |
| Batch ownership | The CRM also has batches and allocations (`nipuna-crm` db 006). Decide which system owns batch creation; today the LMS owns batches and links a CRM batch by `crm_batch_id` |

## Integrations (not connected)

| Item | Notes |
|---|---|
| Google Workspace / Meet / Drive | Meet association and recording import are recorded as states against the `integrations` register; no Google API calls |
| WhatsApp / email / telephony | In-app notifications only |

## Assessments (S3)

| Item | Notes |
|---|---|
| Individual extensions | Module 19 section 5 (trainer up to 3 days, AC beyond) is not built; the AC can reopen a submission window with a reason, and the trainer can extend the batch due time |
| Validation pending / failed | Submissions are accepted on receipt; there is no scanning or link verification, so `Received — Validation Pending` and `Validation Failed` states do not exist yet. The upload limit is the API's 10 MB, not the 50 MB of Module 19 |
| Extra attempts, group projects, completion-only / pass-fail work | Only numeric marks with one initial attempt and 2 resubmissions; additional attempts by AC approval are not built |
| Reminders | The 24 h / due date / +1 day assignment reminders and the 24 h / 1 h test reminders need a scheduler (the jobs CLI S2 introduces) |
| Reassessment and answer release | A formal test has one attempt; authorised reassessments, a later better attempt after publication, and the separate answer-release step are not built. Correcting a published result (independent review) is not built |
| Review clocks | The 3 / 5 / 7 working-day review targets need the academic working calendar; none is configured |
| Tab-switch / similarity flags, question randomisation | Not built |
| Coding runner | Coding answers are marked by a trainer; the isolated runner stays Pending Verification |
| Question bank scope | One bank per branch; company-wide reuse by a global publisher is not built |
| asg-11 due date | Seeded due 02 Oct 2026 (prototype: 29 Sep) so it reads Due, not Overdue, on the prototype's "today" (30 Sep) |

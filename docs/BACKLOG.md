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


## Attendance, progress & certificates (S4)

| Item | Notes |
|---|---|
| Minute-based attendance | Module 21 measures attended teaching minutes; S4 counts sessions (Present + Late / marked). Needs delivered-minute capture and Late / Left Early flags |
| Completion profile per course | Minimum attendance, required learning weights and recovery rules are not configured per course / curriculum version; Completion Review shows evidence and the coordinator decides |
| Complimentary completion rule | Configuration Pending until `complimentary_completion_rule_configured` is set; needs a business decision |
| Attendance at-risk support cases | Module 21 triggers (two consecutive absences, late pattern, no activity for 7 days) and the support queue belong with S5 support requests |
| Combo per-track attendance | Progress is per enrolment; the module also wants each combo track and the booster separately |
| Certificate document | No PDF / template and no email delivery (Email integration not verified); the register and public verification exist |
| Public verification page | `/certificates/verify/{number}` is API only; a public SPA route needs `/verify` in the public paths |
| Joining date on correction | An approved correction to Present sets the joining date; changing the first Present to Absent does not reset it |

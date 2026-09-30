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


## Student services (S5)

| Item | Notes |
|---|---|
| Fees & Receipts fields | `finance_summaries` will gain pending-verification, waived, refunded, installments and invoice numbers (db/005); the screen shows fee, verified paid, dues, next due and receipts only |
| Notifications for other workspaces | Only student and trainer have a notification route and header bell; academic / branch / admin need routes and a nav entry |
| Staff profile screen | `GET /me/profile` works for staff; no staff route (student `/profile` is student-workspace only) |
| Placement Team | Module 23 names a Placement Team role; there is none, so Academic Coordinator, Branch Manager and Super Admin run career staff work. Employer-sharing per opportunity (individual consent references) and interview reminders are not built |
| Support SLA | One `support_sla_hours` for all categories and priorities; a scheduler for `support-escalate-overdue` is not set up |
| External channels | WhatsApp / email delivery, quiet hours and retry (Module 26) need the integrations verified first; preferences are stored only |
| Ask Nipuna | No spend ceiling / cost tracking (Module 24 section 11: ceiling stays unset); Telugu answer quality untested against a live model; due-work facts wait for S3 to register a provider |
| Career file storage | CV files on local disk under `UPLOAD_DIR/cv` |

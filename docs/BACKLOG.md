# Nipuna LMS — Backlog

Open product decisions and gaps found while building. Newest at the bottom of each section.

## CRM connection

| Item | Notes |
|---|---|
| CRM must emit events | The CRM does not yet post `CourseUpserted`, `AdmissionQualified`, `AdmissionUpdated`, `AdmissionCancelled`, `FinanceSummaryUpdated` to `/api/v1/integrations/crm/events`. Needs an outbox + worker in `nipuna-crm` (guide §17) |
| Outbox delivery | `crm_outbox` rows are queued but not delivered; either build a worker that pushes to a CRM endpoint, or the CRM polls `GET /integrations/crm/status?since=` — decide with the CRM team |
| `lms_last_synced_at` | Set by the CRM when it applies a pull/push; the LMS reports `now` at pull time |
| Batch ownership | Resolved in [CRM_INTEGRATION.md](CRM_INTEGRATION.md) §1: the LMS owns batches, allocation, joining date, completion and certificates; the CRM mirrors them (§3.3–3.5) |
| Push or pull | The CRM pulls `/integrations/crm/status`, or exposes an endpoint for the LMS outbox to push to (CRM_INTEGRATION §3.2) |
| Certificate numbering | LMS `NIT-CERT-2026-000001` vs CRM `GNT-C-2627-00001` — pick one series (§3.6) |
| Activation link delivery | CRM sends the one-time link, or supervised activation in the LMS (§3.7) |
| Placement owner | CRM keeps employers / openings / applications; LMS Career screen reads and submits through the CRM (§3.9) |

## Integrations (not connected)

| Item | Notes |
|---|---|
| Google Workspace / Meet / Drive | Meet association and recording import are recorded as states against the `integrations` register; no Google API calls |
| WhatsApp / email / telephony | In-app notifications only |

## Admin & security

| Item | Notes |
|---|---|
| Emergency / elevated access | Security control `EMERGENCY_ACCESS` (max 4 hours, reviewed afterwards) has no mechanism yet; only routine temporary access (7 days) is enforced |
| Student MFA | `students.mfa_status` exists but no second factor is implemented |
| Exception queue | `/admin/exceptions` and the `exception_queue` view belong to the dashboards phase |
| Integration alerts | A Failed integration verification does not yet notify anyone |
| Audit actor filter | The Actor filter lists staff only; student sign-ins are found by entity |

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

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
## Content & recordings (S2)

| Item | Notes |
|---|---|
| Malware scanning of uploads | Module 18 §7 asks for scanning; not available. Files are validated (type, magic number, safe archive) and never executed; scanning is pending technical validation |
| Scheduled release and urgent hide | Module 18 §4 / §9 describe scheduled and topic-linked release and urgent hiding of a placement. Built: immediate release and retire (withdraw); scheduled release and per-placement hide are open |
| Separate placements per asset | The library keeps one placement per item (course / version / topic / batch). Reusing one asset in several placements without duplicating bytes needs a placement table |
| Selected-student and company-wide audiences | Audience is branch + course (+ batch). Selected students and cross-branch publishing need the explicit company-wide permission Module 18 §3–4 describes |
| "Report a problem" on a resource | Module 18 §10; would create a support request (S5) tied to the item and enrolment |
| Recording access after a delayed release | Module 17 §8: at least 30 days of access after a substantially delayed release is not applied; access is Joining Date based only |
| Batch recording commitment | Included / Not Included / Limited terms per batch (Module 17 §2) are not modelled; the check job flags every Delivered session without a recording |
| Student notices on 24 h delay | Module 17 §6 asks to update affected students at 24 h; only staff escalation notices are sent |
| Recording playback | Needs the verified Drive integration and a proxy with per-request entitlement (Module 17 §7); today `watch` records the view and returns the integration state |
| Jobs runner | `flask jobs run` (S2) holds `recording-check`; other slices add their jobs to `services/jobs.JOBS` |
| S2 seed adjusts two joining dates | Learners A and F (completed) get Joining Dates 2025-06-10 and 2024-08-19 so EXT-032 / EXT-033 show a request after the first / second anniversary |

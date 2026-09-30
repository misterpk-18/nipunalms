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
| Jobs runner | `flask jobs run` (S2) holds `recording-check` and `support-escalate-overdue` (S5); other slices add their jobs to `services/jobs.JOBS` |
| S2 seed adjusts two joining dates | Learners A and F (completed) get Joining Dates 2025-06-10 and 2024-08-19 so EXT-032 / EXT-033 show a request after the first / second anniversary |

## Delivery (S1)

| Item | Notes |
|---|---|
| Google Meet creation | Links are entered by hand; no Calendar / Meet API call until the organizer accounts are verified (Integrations) |
| Substitute trainer on a single class | `session_changes` can record it, but the prototype's substitute picker with availability is not built |
| Trainer availability and leave | Conflicts are only overlapping classes and rooms; leave calendars and working hours are not modelled |
| Bulk timetable import | Sessions are created one batch at a time with a repeat rule; no CSV / calendar import as in the prototype's schedule screen |
| Calendar month grid | Schedules are list / week tables; the prototype's month calendar view and iCal export are not built |
| Curriculum diff between versions | The prototype shows what changed between versions; only the review trail is stored |
| Re-mapping running batches to a new version | Activating a version maps pending enrolments and batches; moving Running batches to a newer version is manual |
| Batch capacity waitlist | Full batches have no waiting list; the allocation queue just lists unseated enrolments |
| Session reminders | Students are notified of changes but not reminded before a class (needs a job in `services/jobs.JOBS`) |
| Topic-level self study progress | Topic pages show classes and resources; students cannot mark a topic as studied |
| Duplicate date helpers | `shared/delivery-ui.tsx` and `shared/format.ts` format IST dates in slightly different forms; the datetime-local helpers (`toIstInput`, `fromIstInput`) now live once in `lib/format.ts` (delivery-ui re-exports them); unify the display formatters when the design settles |

## Assessments (S3)

| Item | Notes |
|---|---|
| Individual extensions | Module 19 section 5 (trainer up to 3 days, AC beyond) is not built; the AC can reopen a submission window with a reason, and the trainer can extend the batch due time |
| Validation pending / failed | Submissions are accepted on receipt; there is no scanning or link verification, so `Received — Validation Pending` and `Validation Failed` states do not exist yet. The upload limit is the API's 10 MB, not the 50 MB of Module 19 |
| Extra attempts, group projects, completion-only / pass-fail work | Only numeric marks with one initial attempt and 2 resubmissions; additional attempts by AC approval are not built |
| Reminders | The 24 h / due date / +1 day assignment reminders and the 24 h / 1 h test reminders need a job in `services/jobs.JOBS` (`flask jobs run`, introduced by S2); none is registered yet |
| Reassessment and answer release | A formal test has one attempt; authorised reassessments, a later better attempt after publication, and the separate answer-release step are not built. Correcting a published result (independent review) is not built |
| Review clocks | The 3 / 5 / 7 working-day review targets need the academic working calendar; none is configured |
| Tab-switch / similarity flags, question randomisation | Not built |
| Coding runner | Coding answers are marked by a trainer; the isolated runner stays Pending Verification |
| Question bank scope | One bank per branch; company-wide reuse by a global publisher is not built |
| Assessment evidence in Completion Review | Required learning (S4) is topic coverage from attendance, not assessment work. Required assignments submitted / graded and published test results are not yet shown in the completion evidence or counted in any progress measure; decide the rule with the Completion profile per course |
| asg-11 due date | Seeded due 02 Oct 2026 (prototype: 29 Sep) so it reads Due, not Overdue, on the prototype's "today" (30 Sep) |

## Student services (S5)

| Item | Notes |
|---|---|
| Fees & Receipts fields | `finance_summaries` will gain pending-verification, waived, refunded, installments and invoice numbers (db/005); the screen shows fee, verified paid, dues, next due and receipts only |
| Staff profile details | `/account/profile` is read-only: no phone number (the API does not return one for staff), MFA is shown as Not Configured, and staff cannot edit their name or email |
| Founder notifications | No event is addressed to the Founder role, so the founder workspace has no notification route or bell; add one when an event targets it |
| Placement Team | Module 23 names a Placement Team role; there is none, so Academic Coordinator, Branch Manager and Super Admin run career staff work. Employer-sharing per opportunity (individual consent references) and interview reminders are not built |
| Support SLA | One `support_sla_hours` for all categories and priorities. The `support-escalate-overdue` job is in `services/jobs.JOBS`; cron for `flask jobs run` is not set up |
| External channels | WhatsApp / email delivery, quiet hours and retry (Module 26) need the integrations verified first; preferences are stored only |
| Ask Nipuna | No spend ceiling / cost tracking (Module 24 section 11: ceiling stays unset); Telugu answer quality untested against a live model; the due-work facts (open assignments and tests) cover the student's own batch seats only, with no per-question detail |
| Career file storage | CV files on local disk under `UPLOAD_DIR/cv` |

## Home, Today & reports (P3)

| Item | Notes |
|---|---|
| Multiple delivered topics per class | A class session carries one topic, so "Save delivered topics" confirms that topic and marks the class Delivered. Recording extra topics taught in the same class needs a `session_topics` table |
| Engagement refresh | No scheduled engagement refresh exists; `refreshed_at` is the latest recorded learning activity. A real refresh timestamp (and Stale against it) waits for the engagement pipeline |
| Review turnaround timestamps | Submission and review times are always present today, so Partial Data only appears for impossible pairs (review before submission). `review_started_at` is not used yet; academic reports do not include turnaround |
| Certificate issue lead time | Measured from the completion decision to `issue_date` (a date, not a timestamp); Not Configured until issued certificates trace back to a decided review. No target or SLA is configured |
| Trainer Today: substitute and co-trainers | Today lists sessions where the trainer is the session's trainer; a co-trainer who is not the session trainer sees the batch but not the session in Today |
| Student Home language | Card titles follow the EN / తెలుగు setting (prototype keys); card bodies are English, as in the prototype. The Telugu greeting uses `name_te` when the CRM sent it |
| Join Class on the home tile | Shows the next class only; a second class the same day is reachable from Schedule |

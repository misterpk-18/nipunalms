# Gap register — LMS against approved modules 14–27

Found on 2026-10-03 by comparing the approved module PDFs (`~/Downloads/CRM  & LMS/LMS MODULE/`, 14–27) with the code. Items already in [DEVELOPMENT.md Part E](DEVELOPMENT.md#part-e--backlog), [CRM_INTEGRATION.md §4](CRM_INTEGRATION.md#4-open-items) and WhatsApp / email delivery are left out. The fix order is in [GAP_FIX_PLAN.md](GAP_FIX_PLAN.md); **Phase** is the plan phase, `CRM (D5)` means the CRM owns it (placement). Set **Status** to `Done (<commit>)` when a phase lands.

109 gaps: 36 high, 62 medium, 11 low.

## Register

| ID | Severity | Module | Gap | Phase | Status |
|---|---|---|---|---|---|
| [G001](#g001) | High | 23 Placement & Career Support | No staff-facing placement UI at all | CRM (D5) | Open |
| [G002](#g002) | High | 23 Placement & Career Support | Internship programme and student internship record not modelled; Internship Certificate eligibility inferred from course completion | 8 | Open |
| [G003](#g003) | High | 23 Placement & Career Support | Support period starts at opt-in, not at approved academic completion; not tied to an enrolment; not enforced | 12 | Open |
| [G004](#g004) | High | 23 Placement & Career Support | Readiness is a single student-level flag and is not checked before an application is created | CRM (D5) | Open |
| [G005](#g005) | High | 23 Placement & Career Support | No employer interview record: single interview_at/round on the application, no reminders | CRM (D5) | Open |
| [G006](#g006) | High | 23 Placement & Career Support | No placement case: owner, backup, handover, response/escalation targets, closure and reopening | CRM (D5) | Open |
| [G007](#g007) | High | 23 Placement & Career Support | No guardian authorisation or manual suitability review for students under 18 | 12 | Open |
| [G008](#g008) | High | 23 Placement & Career Support | Outcome evidence is thin: no structured pay, no uniqueness of a joining, and branch attribution follows the student's current branch | CRM (D5) | Open |
| [G009](#g009) | High | 25 Reports & Dashboards | No placement, internship or alumni report | 11 | Open |
| [G010](#g010) | High | 26 Notifications | Notification access is not re-scoped after a role or branch change | 1 | Done (phase 1) |
| [G011](#g011) | High | 26 Notifications | No guardian or payer model for under-18 students | 12 | Open |
| [G012](#g012) | High | Module 14 | Academic Coordinators can approve and activate global curriculum; Founder cannot | 3 | Open |
| [G013](#g013) | High | Module 14 | Curriculum versions have no outcomes, hours, effort, weights, evidence, activities or dependencies | 5 | Open |
| [G014](#g014) | High | Module 14 | No individual academic mapping, credit or equivalence records; no migration plan | 5 | Open |
| [G015](#g015) | High | Module 15 | Batch lifecycle differs from spec: no Proposed/Confirmed, In Progress, On Hold or Archive, and no Branch Manager confirmation | 6 | Open |
| [G016](#g016) | High | Module 15 | Component (track) batches and track-level allocation cannot be created | 6 | Open |
| [G017](#g017) | High | Module 15 | No LMS interbranch or component-only transfer; within-branch transfer needs no Branch Manager approval | 6 | Open |
| [G018](#g018) | High | Module 15 | No material-change record or student affirmative agreement | 6 | Open |
| [G019](#g019) | High | Module 16 | No 5-minute / 15-minute delayed-start thresholds, disruption record or undelivered-minutes capture | 6 | Open |
| [G020](#g020) | High | Module 17 | No recording notice, student/trainer acknowledgement or guardian authorisation | 9 | Open |
| [G021](#g021) | High | Module 17 | Release gate is two checks, and the milestone/status model is missing the spec's states | 9 | Open |
| [G022](#g022) | High | Module 18 | No staff-only audience, so answer keys, marking guides and trainer notes cannot be kept from students | 1 | Done (phase 1) |
| [G023](#g023) | High | Module 19 | Assignments carry no rubric/checklist, pass rule, weight, outcomes or curriculum-version link, and trainers can mark any task Required | 7 | Open |
| [G024](#g024) | High | Module 20 Tests | Expired in-progress attempts are never auto-submitted unless the student reads them again | 1 | Done (phase 1) |
| [G025](#g025) | High | Module 20 Tests | Question bank is readable, with answer keys, by every trainer in the branch for any course | 1 | Done (phase 1) |
| [G026](#g026) | High | Module 20 Tests | A trainer can make a test Required with no curriculum basis, and tests have no weight or mandatory-section rules | 7 | Open |
| [G027](#g027) | High | Module 20 Tests | No incident or interruption recovery workflow for attempts | 7 | Open |
| [G028](#g028) | High | Module 21 Attendance | Absences before the first Present are never counted (expectations start at first attendance) | 1 | Done (phase 1) |
| [G029](#g029) | High | Module 21 Attendance | An approved but not completed recovery already counts as covered learning and recovered | 1 | Done (phase 1) |
| [G030](#g030) | High | Module 21 Attendance | Disputed entries stay in the calculation; no Disputed state, cutoff or coverage display | 8 | Open |
| [G031](#g031) | High | Module 22 Certificates | Course completion opens the Internship Certificate for review | 1 | Done (phase 1) |
| [G032](#g032) | High | Module 22 Certificates | No fee-clearance gate and no financial-release exception | 3 | Open |
| [G033](#g033) | High | Module 22 Certificates | Certificate branch is not updated when the student transfers branches | 1 | Done (phase 1) |
| [G034](#g034) | High | Module 22 Certificates | Completion needs no Trainer confirmation before certificate eligibility | 3 | Open |
| [G035](#g035) | High | Module 22 Certificates | Public verification does not follow the spec's validity model | 3 | Open |
| [G036](#g036) | High | Module 22 Certificates | Revocation excludes the Founder and has no reinstatement | 3 | Open |
| [G037](#g037) | Medium | 23 Placement & Career Support | Self-sourced / other applications cannot be recorded; every application is hard-coded Nipuna-referred | 12 | Open |
| [G038](#g038) | Medium | 23 Placement & Career Support | Opportunity register is missing verification history, Expired transition, Open-Until-Filled review date, employer contact and structured compensation | CRM (D5) | Open |
| [G039](#g039) | Medium | 23 Placement & Career Support | Withdrawal handling, status corrections and role-limited fields are not implemented | CRM (D5) | Open |
| [G040](#g040) | Medium | 23 Placement & Career Support | Career profile and CV review lack required fields and clocks | 12 | Open |
| [G041](#g041) | Medium | 24 AI Requirements | Reported AI answers all go to the Academic Coordinator; no Ask Trainer / Report Answer routing by issue type | 11 | Open |
| [G042](#g042) | Medium | 24 AI Requirements | No way to disable AI with scope, reason, actor and restoration record | 3 | Open |
| [G043](#g043) | Medium | 25 Reports & Dashboards | Role home dashboards do not carry the approved first three figures for Trainer, Academic Coordinator, Super Admin and Placement Team | 11 | Open |
| [G044](#g044) | Medium | 25 Reports & Dashboards | No period selector, export formats, scheduled reports or report metadata/versioning | 11 | Open |
| [G045](#g045) | Medium | 25 Reports & Dashboards | Academic dashboard lacks several required actionable measures and certificate queues/filters | 11 | Open |
| [G046](#g046) | Medium | 26 Notifications | Recipient can mark a notification's action as done; it is never tied to the source record | 10 | Open |
| [G047](#g047) | Medium | 26 Notifications | Message centre lacks course/enrolment and date filters, a linked-record field, and staff Team/Branch views | 10 | Open |
| [G048](#g048) | Medium | 26 Notifications | No revised or cancelled notice state; superseded notices are not linked | 10 | Open |
| [G049](#g049) | Medium | 26 Notifications | No logical-notice / per-channel attempt model or the three separate counts | 10 | Open |
| [G050](#g050) | Medium | 26 Notifications | No preference history, language or timing preferences, and no template versioning | 10 | Open |
| [G051](#g051) | Medium | 26 Notifications | Cancellation, payment and refund changes arriving from the CRM raise no notice | 10 | Open |
| [G052](#g052) | Medium | 26 Notifications | No on-duty / on-call cover roster or missing-cover exception | 10 | Open |
| [G053](#g053) | Medium | 27 Integrations Register | Integration status vocabulary lacks Manual, Planned and Live Verified | 10 | Open |
| [G054](#g054) | Medium | 27 Integrations Register | Register lacks most mandatory per-connection fields and manual-fallback records | 10 | Open |
| [G055](#g055) | Medium | 27 Integrations Register | No configurable freshness threshold or stale status on CRM-sourced data | 10 | Open |
| [G056](#g056) | Medium | 27 Integrations Register | Replayed or backfilled CRM events can fire current notifications; no historical-import guard | 1 | Done (phase 1) |
| [G057](#g057) | Medium | 27 Integrations Register | No intake of consent, stop-contact, WhatsApp opt-out or access-offboarding state from the CRM | 10 | Open |
| [G058](#g058) | Medium | Module 14 | No parent programme version pinning component versions; no variant tracks or equivalence-reference review | 5 | Open |
| [G059](#g059) | Medium | Module 14 | No stable, separately versioned reusable modules, topics or assessment definitions | 5 | Open |
| [G060](#g060) | Medium | Module 14 | Branch/batch academic variations are not recorded | 5 | Open |
| [G061](#g061) | Medium | Module 14 | Mapping-pending enrolments have no named owner or recovery task | 5 | Open |
| [G062](#g062) | Medium | Module 15 | Batch type (Group/Individual/Corporate), schedule pattern (Regular/Weekend/Fast-track) and editable display name are not stored | 6 | Open |
| [G063](#g063) | Medium | Module 15 | 24-hour allocation escalation goes to Branch Managers, not Founder/Super Admin; deadlines are not tracked | 4 | Open |
| [G064](#g064) | Medium | Module 15 | No Nipuna Academic Calendar, company holidays or branch closures | 4 | Open |
| [G065](#g065) | Medium | Module 15 | Class states lack Partially Held and Confirmed; no replacement link, actual start/end/breaks or unfulfilled portion | 6 | Open |
| [G066](#g066) | Medium | Module 15 | No session purpose type (Replacement/Remedial/Extra) or linkage | 6 | Open |
| [G067](#g067) | Medium | Module 15 | A class cannot be shared across courses, tracks or batches | 6 | Open |
| [G068](#g068) | Medium | Module 15 | Conflict checks omit student timetable, assistant and online capacity; room override has no documented reason | 6 | Open |
| [G069](#g069) | Medium | Module 15 | No batch merge/split/successor history, and Completed/Archive rules are minimal | 6 | Open |
| [G070](#g070) | Medium | Module 16 | Meet/Calendar/recording identifiers, recurring-series link and hosting branch are not stored | 6 | Open |
| [G071](#g071) | Medium | Module 16 | No host/cohost, named backup for live online classes, guest approval or compromised-link incident record | 6 | Open |
| [G072](#g072) | Medium | Module 16 | No Meet operations view for link/host readiness, delayed starts, disruptions or unconfirmed attendance | 6 | Open |
| [G073](#g073) | Medium | Module 17 | Published recordings can be edited, re-released or unheld by one manager with no version history or independent review | 9 | Open |
| [G074](#g074) | Medium | Module 17 | Download permission on a recording is a plain boolean flip with no documented exception or approval | 9 | Open |
| [G075](#g075) | Medium | Module 17 / 18 | Staff cannot record a second-year extension request on behalf of a student | 9 | Open |
| [G076](#g076) | Medium | Module 18 | Asset metadata required by the spec is missing | 9 | Open |
| [G077](#g077) | Medium | Module 18 | External links have no owner, rights record or periodic check, and no broken-link exception | 9 | Open |
| [G078](#g078) | Medium | Module 18 | Student library lacks Recently Added/Updated and the Scheduled, Temporarily Unavailable and Withdrawn states | 9 | Open |
| [G079](#g079) | Medium | Module 18 | Batch-specific materials lose access after a batch transfer, unlike recordings | 9 | Open |
| [G080](#g080) | Medium | Module 19 | Assignments can only target a whole batch; no selected-student or individual recovery allocation | 7 | Open |
| [G081](#g081) | Medium | Module 19 | Released assignment edits overwrite the brief with no preserved version per student and no Academic Coordinator review | 7 | Open |
| [G082](#g082) | Medium | Module 19 | Pre-deadline replacement stays open after the trainer has started review | 7 | Open |
| [G083](#g083) | Medium | Module 19 | Repository and external-link submissions do not record the reviewed version or access scope | 7 | Open |
| [G084](#g084) | Medium | Module 19 | No Completion dimension (Pending / Completed / Excused) and no Excused approval | 7 | Open |
| [G085](#g085) | Medium | Module 19 | Final project milestones, demonstration/viva and individual-contribution evidence are not modelled | 7 | Open |
| [G086](#g086) | Medium | Module 20 Tests | Practice quiz feedback, explanations and correct answers are never shown after submission | 7 | Open |
| [G087](#g087) | Medium | Module 20 Tests | Test timing has no separate latest-start; start checks skip enrolment version and prerequisites | 7 | Open |
| [G088](#g088) | Medium | Module 20 Tests | Coding tests have no language, limits, I/O contract or sample/hidden case definition | 7 | Open |
| [G089](#g089) | Medium | Module 20 Tests | Question bank item lacks curriculum-version compatibility, outcome, language, rights and publication history | 7 | Open |
| [G090](#g090) | Medium | Module 20 Tests | Unattempted work after a window closes creates no support or reassessment review task | 7 | Open |
| [G091](#g091) | Medium | Module 21 Attendance | No same-day Trainer confirmation tracking or next-day Academic Coordinator alert | 4 | Open |
| [G092](#g092) | Medium | Module 21 Attendance | Approved pause is not reflected in attendance expectations | 8 | Open |
| [G093](#g093) | Medium | Module 21 Attendance | Correction approval does not flag a completed enrolment for academic review and has no recalculation trace | 8 | Open |
| [G094](#g094) | Medium | Module 21 Attendance | No guardian or under-18 handling | 12 | Open |
| [G095](#g095) | Medium | Module 22 Certificates | Reissue and correction has no request, approval or changed-field record | 3 | Open |
| [G096](#g096) | Medium | Module 22 Certificates | Approval is not bound to identity, evidence and rule/template version, and there is no recheck before issue | 8 | Open |
| [G097](#g097) | Medium | Module 22 Certificates | No bulk or paired review, no issue-register export, no dashboard filters or review-target clock | 8 | Open |
| [G098](#g098) | Medium | Module 22 Certificates | Certificate state model lacks processing, document-version and delivery dimensions | 8 | Open |
| [G099](#g099) | Low | 24 AI Requirements | Ask Nipuna has no placement, certificate or fee sources and answers career questions with a canned text | 11 | Open |
| [G100](#g100) | Low | 26 Notifications | No task is created when an assignment is three days overdue | 7 | Open |
| [G101](#g101) | Low | Module 15 | No assistant/substitute cover role or approval; substitute must already be an assigned batch trainer | 6 | Open |
| [G102](#g102) | Low | Module 15 | Students cannot submit preferred slots (Requested / Waitlisted / Confirmed) | 6 | Open |
| [G103](#g103) | Low | Module 15 | Capacity is one integer; no separate classroom, lab and online capacity, and no review for increases | 6 | Open |
| [G104](#g104) | Low | Module 16 | No Meet participation evidence or unmatched-identity review; recording states lack Configured/Started/File Generated/Playback Ready and Review Required/Failed | 6 | Open |
| [G105](#g105) | Low | Module 17 / 18 | Expiry is shown as a date only, and there is no 'approaching expiry' notice | 9 | Open |
| [G106](#g106) | Low | Module 18 | Only 'opened' is recorded: no download event, playback position or Not Recorded display | 9 | Open |
| [G107](#g107) | Low | Module 19 | The task AI-use rule and the student's AI disclosure are never enforced | 7 | Open |
| [G108](#g108) | Low | Module 19 | No Trainer support-review task at three days overdue | 7 | Open |
| [G109](#g109) | Low | Module 21 Attendance | Hybrid in-person vs online participation is not recorded per entry | 8 | Open |

## Details

### G001

**No staff-facing placement UI at all** — 23 Placement & Career Support (§2, §16, §17 staff views), High, phase CRM (D5)

- **Spec:** Placement staff run the opportunity register, verify employers, review CVs and readiness, record submissions, stages, interviews and offers, verify joinings, and see Student 360 placement data; Placement Team home dashboard (Module 25 §2) shows Active opted-in cases, Upcoming employer interviews, Verified joinings.
- **Code:** Backend routes exist (/opportunities, /career-profiles, /cv-documents/<id>/review, /applications, /placement-outcomes), but the frontend has only the student Career page. There is no staff route, screen or API client for any of them, so staff cannot do any of this work in the product. The staff dashboards (academic, branch, admin, founder) have no placement tile, and nothing reads the /placement-outcomes/summary endpoint.
- **Evidence:** grep of frontend/src for 'placement-outcomes', 'career-profiles', '/opportunities', 'cv-documents' finds only the student download in frontend/src/api/career.ts:113 and withdraw at :110. frontend/src/routes has no career/placement staff route (academic.*, branch.*, admin.* contain none). backend/routes/career.py staff endpoints are unused. Not in Backlog (the Placement Team row only covers the missing role).

### G002

**Internship programme and student internship record not modelled; Internship Certificate eligibility inferred from course completion** — 23 Placement & Career Support (§12 Internship programme; §18 acceptance), High, phase 8

- **Spec:** Maintain an approved internship programme and a separate student internship record (organisation, internal/external, supervisor, planned and actual dates, verified duration and work, supervisor confirmation, Academic Coordinator verification) that feeds Module 22 Internship Certificate eligibility. Internship evidence must not be inferred from a course project or offer. Report internship starts and completions separately.
- **Code:** There is no internship table, model, service or screen. An Internship Certificate register entry is created by the coordinator and moves to Eligibility Review as soon as the course completion decision is Complete (or immediately if the enrolment is already Completed). No internship evidence is required. 'Internship' exists in placement only as an opportunity employment_type value.
- **Evidence:** services/certificates.py:95-114 open_eligibility() moves every live entry, including Internship Certificate, to Eligibility Review on course completion; services/certificates.py:117-135 create_entry() sets Eligibility Review for a Completed enrolment with no internship check. grep -i 'internship' across backend/models, repositories and db finds only db/040 certificate_type enum and opportunities.employment_type.

### G003

**Support period starts at opt-in, not at approved academic completion; not tied to an enrolment; not enforced** — 23 Placement & Career Support (§2 Participation, entitlement and support period), High, phase 12

- **Spec:** Six months of support after approved academic completion of the qualifying enrolment or full combo. Record the qualifying enrolment, completion date, support start/end, accepted terms and extension basis; show per-enrolment basis where several qualify; a late opt-in uses the remaining valid period, not a fresh six months. At expiry review active applications, interviews and promises and record a continuation or handover decision.
- **Code:** support_start is set to the opt-in date and support_end = opt-in + 6 months (the code comment itself says 'after opting in'). A late opt-in therefore gets a fresh six months, the opposite of the rule. There is no link to enrolment or completion date, no accepted-terms field, no per-enrolment entitlement rows. Nothing checks support_end: apply(), CV upload and review all work after expiry, and no job or workflow handles expiry (no continuation/handover decision, no notice). Extension stores only support_extension_reason (single column, no revised-end history beyond audit).
- **Evidence:** services/career.py:28 SUPPORT_MONTHS comment, :143-158 update_profile sets support_start=today_ist(), support_end=_add_months(...); grep of 'support_end' in backend services shows only career.py set/extend and no check in apply() (:216-240); services/jobs.py JOBS has only recording-check, support-escalate-overdue, allocation-escalation. db/050_student_services.sql:179-207 career_profiles has no enrolment_id/completion_date columns.

### G004

**Readiness is a single student-level flag and is not checked before an application is created** — 23 Placement & Career Support (§6, §8 Referral readiness and pre-submission checks), High, phase CRM (D5)

- **Spec:** Readiness is decided per role/opportunity by an authorised Placement reviewer with evidence, reviewer, time and next action. Before a Nipuna submission check current consent for that named opportunity, reviewed CV, opportunity-specific readiness and active verified status.
- **Code:** career_profiles has one readiness column ('Not Assessed'/'In Preparation'/'Ready for referral') for the whole student. apply() never reads it: any opted-in student with consent and a reviewed CV can apply to any eligible opportunity, even if Not Assessed or In Preparation. The student's click immediately creates a Nipuna-referred application; there is no staff submission step recording channel, time, exact information sent, actor and evidence. Consent is one boolean for all employers, not per opportunity.
- **Evidence:** services/career.py:216-240 apply() checks only opted_in, sharing_consent, latest_reviewed_cv and opportunity eligibility; db/050_student_services.sql:196-198 readiness column; applications table (db/050 :302-317) has no submission_channel/submitted_at/submitted_by/payload columns. (Per-opportunity consent references are in Backlog; the readiness check and submission record are not.)

### G005

**No employer interview record: single interview_at/round on the application, no reminders** — 23 Placement & Career Support (§10 Employer interviews), High, phase CRM (D5)

- **Spec:** Each interview records employer/opportunity, round, date/time/timezone, mode, venue or link, interviewer, student confirmation, actual attendance, feedback, outcome, next action; earlier appointments, reschedules and cancellation reasons are preserved; one application holds multiple rounds. 24-hour and 1-hour reminders, replaced on change. No-show is verified, not inferred.
- **Code:** An application has just two scalar columns, interview_round and interview_at, overwritten on each change, so multiple rounds, reschedule/cancel history, mode/venue/link, confirmation, attendance, feedback and outcome cannot be stored. Interview Attended is just a status. Reporting 'interviews scheduled / attended / cancelled / verified no-shows' (Module 23 §15, Module 25 §7) is impossible. services/interviews.py is the Module 20 mock interview only. (Interview reminders are in Backlog; the interview entity is not.)
- **Evidence:** db/050_student_services.sql:311-312 interview_round, interview_at; services/career.py:444-468 change_application_status overwrites them; no interviews table in db/*.sql other than interview_slots (mock, db/030).

### G006

**No placement case: owner, backup, handover, response/escalation targets, closure and reopening** — 23 Placement & Career Support (§13, §16 Case ownership, targets, closure and reopening), High, phase CRM (D5)

- **Spec:** Each student has a placement case (separate from applications and readiness) with one named Placement owner and backup, handovers, first response in one staffed day, weekly review, employer follow-up after 3-5 days, two contacts in seven days for unresponsive students, escalation to Branch Manager after two staffed days, closure reasons, reviewed non-response closure 30 days after the last permitted contact (never automatic), reopening within a valid period, and five-year retention.
- **Code:** There is no case table or status, owner/backup field, coverage calendar, contact-attempt log, closure/reopen workflow or retention date. The only 'next action' is a computed string. Career jobs do not exist, so no overdue-work escalation to the Branch Manager runs for placement.
- **Evidence:** db/050_student_services.sql has only career_profiles, cv_documents, opportunities, applications, application_events, placement_outcomes; models/career.py and services/career.py contain no owner, backup, case_status, contact attempt or closure logic; services/jobs.py has no placement job. Only the Placement Team role absence is in Backlog.

### G007

**No guardian authorisation or manual suitability review for students under 18** — 23 Placement & Career Support (§3 Consent; minors), High, phase 12

- **Spec:** For a student under 18 verify guardian authorisation and the student's agreement and complete a manual suitability review of the employer opportunity before sharing. Promotional use of testimonial/photo/video needs separate permission.
- **Code:** No age, guardian authorisation, suitability review or publicity-consent field exists anywhere. A minor can opt in, give consent and apply like anyone else.
- **Evidence:** grep -i 'guardian|date_of_birth|dob|minor|under 18|testimonial|publicity' across backend/models, services, repositories and db/*.sql finds no matching career or consent fields; career_profiles (db/050 :179-207) holds only the single sharing_consent boolean; apply() (services/career.py:216) has no age check.

### G008

**Outcome evidence is thin: no structured pay, no uniqueness of a joining, and branch attribution follows the student's current branch** — 23 Placement & Career Support (§11 Offers, joining and compensation; §15 attribution), High, phase CRM (D5)

- **Spec:** Store fixed pay, variable pay, total CTC/stipend, currency and period separately; offer received, accepted and joined are separately verified with minimum evidence; one verified joining counts once with one primary placement branch and programme; event-time and original admitting branch attribution preserved so an interbranch transfer does not move earlier results; offer/compensation visibility restricted by role.
- **Code:** placement_outcomes has a free-text compensation_text only and a single evidence_note. Nothing prevents several Joined rows for the same student/application (or via a combo's linked courses), so a joining can be counted more than once. The reporting view takes the student's current service_branch_id, so a transfer silently moves earlier results; there is no qualifying programme/course on the outcome. Recording an outcome does not update the application status, and a Joined outcome does not link to the enrolment or course.
- **Evidence:** db/050_student_services.sql:374-398 placement_outcomes (no unique constraint on student/application/outcome_type, no course_id or branch_id column); :405-410 view verified_placement_outcomes uses s.service_branch_id; services/career.py:472-484 record_outcome.

### G009

**No placement, internship or alumni report** — 25 Reports & Dashboards (§7 Placement, internship and alumni reporting), High, phase 11

- **Spec:** Report opted-in students and valid support periods, opportunity readiness, CV reviews and shares, applications and employer responses, interviews scheduled/attended/cancelled/no-show, selected, verified offers and joinings, internship starts/completions, with unique students separate from applications, Nipuna-referred vs self-sourced attribution, verification coverage, and definition, period and cutoff.
- **Code:** The only placement reporting is GET /placement-outcomes/summary: verified outcome counts per type and distinct students, no UI consuming it. No application, interview, readiness, CV-review, source-attribution, support-period or internship measures; no report appears on any dashboard or in /academic/reports or /branch/reports.
- **Evidence:** services/career.py verified_outcome_summary(); repositories/career.py verified_outcome_counts(); services/academic_reports.py and services/dashboards.py contain no placement figures; frontend/src/features/*/reports.tsx and dashboard.tsx do not reference career or placement.

### G010

**Notification access is not re-scoped after a role or branch change** — 26 Notifications (§1, §10), High, phase 1

- **Spec:** Search results, counts, previews, deep links and exports enforce current permissions. A transfer or role change recalculates access to the linked notice without exposing another branch's unrelated records.
- **Code:** The notification list, counts, read and acknowledge all filter only on recipient_user_id. Nothing re-checks the user's current role or branch scope against the notice's branch_id. After a scope revoke or transfer, a staff member keeps seeing title and body text from the old branch.
- **Evidence:** backend/repositories/notifications.py:12-15 (get_for_recipient), 17-35 (list_stmt), 45-50 (counts): no scope or branch predicate, and notifications.branch_id is never used in a filter. There is no export either.

### G011

**No guardian or payer model for under-18 students** — 26 Notifications (§4), High, phase 12

- **Spec:** For under-18 students, record the guardian's identity, verification method and permitted scope. Copy the guardian on admission confirmation, material class changes, attendance concerns and similar. Financial notices need separately recorded payer authority. Review guardian access when the student turns 18. A shared family mobile is not proof of identity.
- **Code:** The LMS has no guardian, payer, date of birth or age field, no scope and verification record, and no copy-to-guardian logic. Students carry only email and mobile.
- **Evidence:** backend/models/students.py:22-39 (Student columns); grep -rniE 'guardian|payer|under.18|minor|date_of_birth' over backend, db and frontend/src returns no hits.

### G012

**Academic Coordinators can approve and activate global curriculum; Founder cannot** — Module 14 (§5, §11 Publication permissions), High, phase 3

- **Spec:** AC drafts and reviews. Founder/CEO or Super Admin approves global curriculum, required outcomes, hours, completion profiles and 3+1 structure after academic review.
- **Code:** Approve, activate and retire are gated by CURRICULUM_ROLES = (ACADEMIC_COORDINATOR, SUPER_ADMIN). _approvers() notifies both roles. An AC can approve a version another AC submitted and then activate it. The Founder role has no curriculum permission at all. The only control is that the approver differs from the submitter.
- **Evidence:** backend/routes/curriculum.py:67-88 (@require_roles(*CURRICULUM_ROLES) on approve/activate/retire); backend/services/delivery_access.py:10; backend/services/curriculum.py:322-323 (_approvers) and 339-350 (approve). Search for FOUNDER in routes/curriculum.py and services/curriculum.py: no hits.

### G013

**Curriculum versions have no outcomes, hours, effort, weights, evidence, activities or dependencies** — Module 14 (§2, §4, §6, §10 Curriculum content model), High, phase 5

- **Spec:** A version is an immutable snapshot of required outcomes, topics, dependencies, activities, evidence, estimated effort, weights and completion profile. Each topic has an outcome, a Required/Recommended/Optional class, estimated effort and dependencies. Each version records three totals: standard instructional, independent learning and total effort, in minutes. Publication requires verified outcomes, hours, evidence and weights. Unverified hours stay visibly Pending.
- **Code:** curriculum_versions holds only a label, status and approver. curriculum_modules holds a title, a Telugu title and an order. curriculum_topics holds a title, a Telugu title, an order and a boolean is_required. There is no outcome, Recommended/Optional class, minutes, hours, weight, evidence rule, activity or dependency. The only submit blockers are: at least one module, no empty module, at least one required topic. A version can be published with no hours and no weights. Backlog item 'Completion profile per course' covers only attendance minimum, weights and recovery rules, not outcomes, hours, dependencies or topic classes.
- **Evidence:** db/002_catalog_curriculum.sql:62-79 (curriculum_versions) and 104-131 (modules, topics); backend/services/curriculum.py:55-66 (_blockers). Grep over backend, db and frontend for instructional|independent_learning|estimated_minutes|effort|dependenc|outcome|weight returns no curriculum hits (weight appears only in academic_reports.py).

### G014

**No individual academic mapping, credit or equivalence records; no migration plan** — Module 14 (§8 Curriculum version on admission, later migration and equivalence), High, phase 5

- **Spec:** Moving a student to a different version or batch needs a documented side-by-side comparison of outcomes, previous work and remaining obligations, plus an authorised migration plan and acceptance. The receiving AC approves an individual mapping under existing equivalence rules with trainer evidence. New equivalence rules or reduced required learning need Founder/Super Admin approval, with an independent approver for a requester's own sensitive exception. Credit records the original evidence, reviewer, rule/version and credited outcome, and creates no duplicate attendance or submissions.
- **Code:** There are no equivalence rules, no credit records and no mapping or migration table. A version mismatch at allocation is only a 'warn' check the coordinator acknowledges with a boolean (the text says 'Record the academic mapping before allocating', but nothing exists to record it in). update_batch tells staff to 'use an academic mapping for running batches', which does not exist. CRM-driven version changes are only audit-logged. The Backlog covers re-mapping Running batches, but not student-level mapping, credit or equivalence.
- **Evidence:** backend/services/batch_allocations.py:57-62; backend/services/batches.py:~215 (message about 'academic mapping'); grep for equivalen across backend, db and frontend returns nothing; db/*.sql has no mapping or credit table.

### G015

**Batch lifecycle differs from spec: no Proposed/Confirmed, In Progress, On Hold or Archive, and no Branch Manager confirmation** — Module 15 (§5 Batch lifecycle and confirmation), High, phase 6

- **Spec:** Lifecycle is Draft/Proposed → Confirmed → In Progress, with On Hold, Completed and Cancelled as outcomes. Archiving is a separate state. The Branch Manager confirms a proposed batch only when its readiness record covers a 7-point checklist: course and version, BM/AC contact/trainer/assistant cover, start/timetable/hours/end, room and capacity, holiday/room/trainer/travel checks, recording provision, and BM approval after AC review.
- **Code:** States are Forming/Starting/Running/Full/Completed/Cancelled. Full is automatic, and there is no On Hold or Archived. 'Starting' and 'Running' need only a curriculum version and a lead trainer. Any AC, BM or Super Admin can run every transition (MANAGE_ROLES), so BM approval after AC review is not enforced. Readiness checks cover only curriculum, lead trainer, capacity (always 'pass'), 'schedule' (pending without blocking) and Meet. They do not cover assistant cover, room or lab, equipment, holidays, recording commitment or an approval record. Pending Verification does not block starting.
- **Evidence:** db/004_batches_sessions.sql:5; db/010_delivery.sql check_batch_transition; backend/services/batches.py:100-135 (readiness_checks), 264-281 (transition); backend/services/delivery_access.py:7.

### G016

**Component (track) batches and track-level allocation cannot be created** — Module 15 (§3, §4, §13 Combo component batches and allocations), High, phase 6

- **Spec:** A 3+1 combo has separately trackable allocations for its three main tracks and the booster. They may point to one combined batch or to different component batches, in another branch or slot. A component can move without moving the parent Admission.
- **Code:** A batch is for one course_id with no component. _validate_version rejects any curriculum version that has a component_id. allocations.allocate() and batch_allocations.allocate() take no track parameter, and the check requires batch.course_id == enrolment.course_id. batch_allocations.enrolment_track_id exists in the schema but nothing in the services or API ever sets it. Allocation is therefore whole-enrolment only. Only the CRM can change service branch, and it moves the entire admission and every enrolment (_transfer).
- **Evidence:** backend/services/batches.py:188-194; backend/services/allocations.py:14-50; backend/services/batch_allocations.py:138-157; backend/services/crm.py:517-530; grep for enrolment_track_id in backend/services (outside CRM reads) shows no writes.

### G017

**No LMS interbranch or component-only transfer; within-branch transfer needs no Branch Manager approval** — Module 15 (§13 Transfers), High, phase 6

- **Spec:** A within-branch move needs Branch Manager batch-transfer approval. An interbranch move needs the original Branch Manager or Super Admin and confirmation of destination delivery. The receiving AC approves the individual mapping. The original Admission ID, mapping, history and payment attribution are retained. A requester cannot approve their own sensitive exception.
- **Code:** transfer() is an immediate action by any AC, BM or Super Admin at the branch, with a reason. It is restricted to the same branch and course (allocate raises if the branch differs). There is no request, approval or requester/approver separation. There is no interbranch path from the LMS side at all.
- **Evidence:** backend/services/batch_allocations.py:158-185; backend/services/allocations.py:23-26; db/004_batches_sessions.sql check_batch_allocation (branch must equal service branch).

### G018

**No material-change record or student affirmative agreement** — Module 15 (§14 Material changes and student agreement), High, phase 6

- **Spec:** A change to start commitment, service branch, delivery mode, recurring teaching days/times, required hours or a significant end-date extension is material. Record the old and proposed plan, reason, affected learners, approver, and each student's affirmative agreement before implementing it for that student. A delivered or read notice is not agreement. Ordinary reschedules need 24 hours' notice. An emergency needs an immediate notice with the reason, next action and delivery-failure follow-up.
- **Code:** update_batch() changes mode, planned dates, capacity and timetable days/times directly. It sends no notice, and no plan-change or agreement table exists. The allocation review only warns 'needs the student's agreement' and accepts a boolean acknowledgement. Session reschedules only flag short_notice (<24 h) in session_changes with no emergency justification or next-action field. The existing notices are one-way.
- **Evidence:** backend/services/batches.py:213-243 (update_batch); backend/services/batch_allocations.py:75-80; backend/services/class_sessions.py:291-305; grep for agree in backend/services returns no agreement record.

### G019

**No 5-minute / 15-minute delayed-start thresholds, disruption record or undelivered-minutes capture** — Module 16 (§7 Start-failure recovery), High, phase 6

- **Spec:** The trainer checks readiness 5-10 minutes before the start. At 5 elapsed minutes of delay, students are informed. At 15 minutes unresolved, a disruption is recorded and the AC/BM communicates a recovery or replacement plan. Delivered and undelivered minutes and approved make-up are recorded. A provider or institute failure is not a student absence.
- **Code:** Nothing monitors a session that has not gone Live by its start time. There is no delay notice, no disruption record or state and no alert to the AC or BM. Undelivered minutes are not captured. The exception queue has no source for late or failed starts. The Backlog's 'Student notices on 24 h delay' concerns recordings, not live-class starts.
- **Evidence:** backend/services/jobs.py (3 jobs only); db/080_exception_queue.sql sources (CURRICULUM_MAPPING, ALLOCATION, PROVISIONING, RECORDING, CRM_EVENT, SUPPORT, RESULTS, ACCESS_EXCEPTION, INTEGRATION); grep for disruption|late start|delayed start across backend and db returns nothing.

### G020

**No recording notice, student/trainer acknowledgement or guardian authorisation** — Module 17 (§3 Notice, acknowledgement and privacy), High, phase 9

- **Spec:** Before participation, explain what is captured, purpose, who may view and access period; record student and trainer acknowledgement and guardian authorisation where applicable; handle objections; do not assume classroom acknowledgement covers promotional reuse or AI training.
- **Code:** No table, field, endpoint or screen records any acknowledgement, consent, guardian authorisation or objection against a batch, student or trainer. The only 'consent' in the schema is career sharing_consent. A recording can be registered and released for every student of the batch with no acknowledgement check.
- **Evidence:** grep -i 'acknowledg|guardian|consent' db/*.sql only hits db/001_foundation.sql:304 (notification acknowledged_at) and db/050_student_services.sql:195 (career consent). backend/services/recordings.py release() (approx. lines 215-240) checks only session.state == 'Delivered' and media_ref.

### G021

**Release gate is two checks, and the milestone/status model is missing the spec's states** — Module 17 (§4-§5 Capture milestones and pre-release gate), High, phase 9

- **Spec:** Track Recording Configured, Started, File Generated, Playback Ready and Released as distinct milestones. Show Processing, Partial, Review Required, Failed, Missing, Withdrawn and Unavailable as exceptions. Release only after seven mandatory checks (correct session/parts, entitled group, playable, duration consistent, host permissions and trainer closeout, no privacy concern, tested playback/expiry/revocation). A failed check opens a named exception. Uncertain or wrong-Meet files stay Review Required.
- **Code:** recording_status enum is only Processing, Released, Partial, Held, Unavailable, Expired. There are no milestone timestamps and no Review Required, Failed or Withdrawn state. release() checks only that the session is Delivered and media_ref is non-empty. Duration versus session length, trainer closeout confirmation, permission/playback test and privacy review are not checked and no check results are stored. Exceptions cover only Partial, Held, Unavailable and Integration Unavailable, so there is no named exception for a failed check or an uncertain match.
- **Evidence:** db/020_content_recordings.sql:150 (recording_status enum), :208 (recording_issue_type enum). backend/services/recordings.py release() and register(). The Backlog covers only commitment terms, 30-day access and 24h student notices.

### G022

**No staff-only audience, so answer keys, marking guides and trainer notes cannot be kept from students** — Module 18 (§3, §6 Audience and protected files), High, phase 1

- **Spec:** Audience scopes include staff-only. Answer keys, marking guides, internal trainer notes and staff-only files remain protected from students.
- **Code:** content_items has no audience or visibility field. Every Released item is shown to every matching enrolment of the course and branch (optionally one batch). There is no content type or flag for a staff-only or answer-key resource. content_type is limited to PDF, Notes, Dataset, Code, Lab, Practice material, Link and Video link. The Backlog lists selected-student and company-wide audiences but not staff-only.
- **Evidence:** db/020_content_recordings.sql:15-45 (content_items columns). backend/repositories/content.py released_candidates() and backend/services/content.py item_matches_enrolment() apply only branch, course, batch and version.

### G023

**Assignments carry no rubric/checklist, pass rule, weight, outcomes or curriculum-version link, and trainers can mark any task Required** — Module 19 (§2, §8 Required activity definition), High, phase 7

- **Spec:** Every activity links to an approved curriculum version and is Required or Optional. A required activity references its approved outcomes, weight and completion rule and retains a rubric/checklist, pass rule and version before publishing. A routine batch assignment cannot silently introduce a new mandatory outcome, and trainers may add optional practice.
- **Code:** assignments has only batch, an optional topic, kind, brief, attachments, is_required, max_marks, dates, late_policy and ai_use_rule. There is no rubric, checklist, pass mark, weight, outcome mapping or curriculum_version column. Any trainer of the batch can create and release is_required=true work with arbitrary max_marks; no check ties it to an approved required item.
- **Evidence:** db/030_assessments.sql:12-47 (assignments columns); backend/services/assignments.py create_assignment() accepts is_required and max_marks without any approved-curriculum check; grep rubric|checklist|weight|outcome in db/030_assessments.sql, backend/models/assessments.py and backend/services/assignments.py finds none for assignments.

### G024

**Expired in-progress attempts are never auto-submitted unless the student reads them again** — Module 20 Tests (§5), High, phase 1

- **Spec:** At expiry, submit the server-saved answers once and issue a receipt. A delayed job must not extend the answering period. Unsubmitted or interrupted attempts must be visible to the Trainer.
- **Code:** Expiry is lazy: expire_if_due() runs only when the attempt is read or saved. If the student closes the browser and never returns, the attempt stays In Progress. It is never frozen, scored or put in the grading queue, and no receipt is issued. repositories.tests.expired_in_progress() exists but nothing calls it and no job is registered.
- **Evidence:** backend/repositories/tests.py expired_in_progress() (defined, 0 callers by grep). backend/services/jobs.py JOBS has no attempt-expiry job. backend/services/attempts.py expire_if_due() is called only from load_attempt() and start_attempt().

### G025

**Question bank is readable, with answer keys, by every trainer in the branch for any course** — Module 20 Tests (§2), High, phase 1

- **Spec:** Trainers work only within their assigned academic scope. Confidential answer keys and hidden coding cases are denied to unauthorised staff.
- **Code:** list_questions() and get_question() filter by branch only. A trainer can read the stems, answer keys and explanations of questions for courses they do not teach in that branch. Authoring is course-limited but reading is not.
- **Evidence:** backend/services/questions.py question_branch_ids() returns the branches of the user's TRAINER scopes. _load() and repositories/questions.py list_stmt() filter only by branch_id. Question.to_dict() includes answer_key.

### G026

**A trainer can make a test Required with no curriculum basis, and tests have no weight or mandatory-section rules** — Module 20 Tests (§1, §3), High, phase 7

- **Spec:** The approved curriculum version identifies each required assessment, its learning outcome, weight, pass rule and completion contribution. A batch-level test cannot invent such a requirement. A required test cannot publish without maximum marks, weight, pass criteria and mandatory sections.
- **Code:** Any trainer sets is_required freely when creating or updating a test. The tests table has no weight, mandatory-section, learning-outcome or curriculum-version columns and no link to a curriculum item. configuration_gaps() asks only for pass marks, closing time and approval. Any test of kind Module test, Final test or Coding exercise is treated as formal automatically.
- **Evidence:** backend/controllers/tests.py v.boolean('is_required'). backend/services/tests.py create_test() and update_test() copy is_required. backend/services/assessment_rules.py configuration_gaps(). grep for 'weight' in db/*.sql returns nothing.

### G027

**No incident or interruption recovery workflow for attempts** — Module 20 Tests (§5, §11), High, phase 7

- **Spec:** Record save failures, outages and runner faults as interruption evidence. The Academic Coordinator can authorise restored time, continuation or an equivalent replacement attempt with a reason, adjusted deadline and student notice. A verified institute-side failure must not consume an attempt. Route interrupted attempts to named owners.
- **Code:** There is no incident, interruption or recovery-decision table or service. After the deadline the attempt is frozen, and the database trigger blocks reopening. The attempt count is always the number of submitted attempts, so a technical failure consumes an attempt. The only client-side signal is a 'Failed' save label that is not persisted. This is distinct from the backlog items on individual extensions and reassessment.
- **Evidence:** db/030 attempts_before_write() ('A submitted attempt cannot be reopened') and the attempt_answers guard. backend/services/tests.py student_view() computes attempts_remaining from submitted attempts. grep for incident or interrupt in backend/services/models/db finds only the docstring line in attempts.py.

### G028

**Absences before the first Present are never counted (expectations start at first attendance)** — Module 21 Attendance (§5, §10), High, phase 1

- **Spec:** Attendance expectations start at the agreed available start under the delivery plan. Do not shift expectations automatically to the student's first attendance. The Joining Date is the first confirmed regular attendance. A missed first committed class must trigger a joining/access check.
- **Code:** The attendance grid keeps only delivered sessions on or after enrolments.joining_date, and joining_date is set by the first Present or Late mark. Until then the enrolment is 'Not started' and nothing is counted. A student who misses the first classes shows no absences and no denominator. Once they join, earlier missed sessions are not in the denominator. The backlog item on Joining date correction is a different issue.
- **Evidence:** db/040_attendance_certificates.sql attendance_grid: WHERE e.joining_date IS NOT NULL AND (cs.starts_at...)::date >= e.joining_date. enrolment_progress.attendance_state = 'Not started' when joining_date IS NULL. backend/services/attendance.py set_joining_date(). No planned_start or delivery-plan start is used.

### G029

**An approved but not completed recovery already counts as covered learning and recovered** — Module 21 Attendance (§4, §8), High, phase 1

- **Spec:** Recovery counts only on verified completion (Approved Recovery Completed). A recovery approval, a link or a self-declaration is not enough to satisfy a learning obligation.
- **Code:** The required-learning view treats a topic as covered when the recovery status is Approved OR Completed. recovered_count also counts Approved. A student's Required learning percentage rises as soon as the Academic Coordinator approves a recovery plan, before any evidence is verified.
- **Evidence:** db/040_attendance_certificates.sql: enrolment_covered_topics WHERE ... recovery_status IN ('Approved','Completed'); enrolment_attendance recovered_count FILTER (... recovery_status IN ('Approved','Completed')).

### G030

**Disputed entries stay in the calculation; no Disputed state, cutoff or coverage display** — Module 21 Attendance (§2, §5, §7), High, phase 8

- **Spec:** Disputed is a review condition layered on the existing entry. Pending and Disputed records are excluded from both numerator and denominator until resolved and shown separately. Show the calculation cutoff, resolved-record coverage, unresolved minutes and a Provisional label. Show Not Yet Calculable when no denominator can be verified.
- **Code:** A pending correction does not mark the entry Disputed or remove it from attendance_pct. attendance_pct is computed over all marked records, so a disputed Absent still counts against the student during review. The view has no cutoff, no coverage figure and no unresolved or disputed counts. 'Partial Data' is shown but there is no Provisional label or Not Yet Calculable value.
- **Evidence:** db/040 enrolment_progress (attendance_pct = (present+late)/marked_sessions with no join to attendance_corrections). backend/services/attendance.py get_register() only sets a correction_pending flag for display. No disputed status exists in attendance_status.

### G031

**Course completion opens the Internship Certificate for review** — Module 22 Certificates (§1, §2), High, phase 1

- **Spec:** An Internship Certificate needs a real approved internship programme and verified internship evidence (organisation, actual start/end dates, duration, work done, named verifier). Course completion alone does not create internship experience.
- **Code:** open_eligibility() moves every live entry of the enrolment from Not Yet Eligible to Eligibility Review when the course completion is decided, including Internship entries. create_entry() puts an Internship entry straight into Eligibility Review if the enrolment is Completed. The table has no internship programme, dates, duration, evidence or verifier fields, and nothing checks them.
- **Evidence:** backend/services/certificates.py open_eligibility() (loops certificates_repo.live_entries and sets 'Eligibility Review' with no type check) and create_entry(); db/040_attendance_certificates.sql certificates table has no internship columns.

### G032

**No fee-clearance gate and no financial-release exception** — Module 22 Certificates (§3, §4, §12), High, phase 3

- **Spec:** For a paid Admission, require the final fee to be cleared by verified allocated payments before eligibility. Founder/CEO or Super Admin may approve a documented certificate-release financial exception (admission, outstanding amount, reason, certificate types) that does not waive the debt.
- **Code:** Eligibility is just a Complete completion decision. Fee clearance is not checked at completion, approve or issue. There is no exception record or endpoint. There is no Pending Verification or Not Eligible state with a named blocker.
- **Evidence:** grep for fee/balance/outstanding in backend/services/certificates.py and backend/services/completion.py returns nothing. check_certificate_eligibility() in db/040 tests only enrolment status and the complimentary setting. certificate_status has no blocker states (Not Yet Eligible, Eligibility Review, Awaiting Approval, Approved for Issue, Issued, Superseded, Revoked).

### G033

**Certificate branch is not updated when the student transfers branches** — Module 22 Certificates (§6, §4), High, phase 1

- **Spec:** For a transferred course, the certificate shows the completing service branch, and the receiving branch's Academic Coordinator and Branch Manager run review and issue.
- **Code:** certificates.branch_id is copied from enrolment.service_branch_id when the entry is created and never changed. _transfer() in crm.py updates admission and enrolment branch only. After a transfer the new branch cannot see or act on the entry (scope.require_branch and has_role check certificate.branch_id), and the old branch keeps authority over it.
- **Evidence:** backend/services/certificates.py ensure_register_entry sets branch_id once. backend/services/crm.py _transfer() lines ~517-524 sets enrolment.service_branch_id with no certificate update. No code in services/crm.py touches certificates.

### G034

**Completion needs no Trainer confirmation before certificate eligibility** — Module 22 Certificates (§2, §4; Module 21 §8), High, phase 3

- **Spec:** Trainer confirmation of academic completion and Academic Coordinator verification are both required before a certificate becomes Eligible.
- **Code:** completion.decide() lets the Academic Coordinator or Super Admin decide Complete without any trainer recommendation. The trainer recommendation is optional and informational. Complete moves the enrolment to Completed and opens certificate eligibility.
- **Evidence:** backend/services/completion.py decide() has no check on review.trainer_recommendation. The module docstring says the recommendation 'informs the decision, it never makes it'.

### G035

**Public verification does not follow the spec's validity model** — Module 22 Certificates (§7, §10, §11), High, phase 3

- **Spec:** The public page shows the presented certificate version, with Valid — Current Version, Superseded (with a reference to the current version) or Revoked. It shows number, version, holder, title, type, relevant branch and original issue date.
- **Code:** verify() takes only the number and returns the latest version's raw register status ('Issued', 'Revoked'). It never labels 'Valid — Current Version' or 'Superseded', gives no reference to the current version, and cannot address an older version. Branch is not returned. The 'issue_date' returned is the latest version's reissue date, not the original issue date.
- **Evidence:** backend/controllers/certificates.py verify() returns certificate.status and issue_date with no branch. backend/repositories/certificates.py latest_by_number() takes the highest version only. backend/routes/certificates.py has no version parameter.

### G036

**Revocation excludes the Founder and has no reinstatement** — Module 22 Certificates (§11), High, phase 3

- **Spec:** Founder/CEO or Super Admin may approve revocation, with a reason, evidence and an independent decision. Reinstatement after a mistaken revocation needs a separate recorded Founder/Super Admin decision, with the revoked interval preserved.
- **Code:** Only SUPER_ADMIN can revoke, so FOUNDER_CEO is excluded. There is no evidence field and no independence rule. The database transition table has no Revoked to Issued path, so reinstatement is impossible, and no revoked-interval history exists.
- **Evidence:** backend/services/certificates.py revoke() uses _require_role(certificate, 'SUPER_ADMIN'). The trigger in db/040_attendance_certificates.sql certificates_before_write() allows only ('Issued','Superseded') and ('Issued','Revoked') out of Issued and has no transition out of Revoked. There is no reinstate route in routes/certificates.py.

### G037

**Self-sourced / other applications cannot be recorded; every application is hard-coded Nipuna-referred** — 23 Placement & Career Support (§8, §9 Applications and source), Medium, phase 12

- **Spec:** Students record independent applications; distinguish Nipuna-referred, self-sourced and other documented sources; a self-sourced job must not be counted as a Nipuna referral. Interest ('Suggested', 'Student Interested') are pre-application states. Applications link to all relevant enrolments.
- **Code:** The schema has applications.source (Nipuna-referred/Self-sourced/Other) but the only creation path, apply(), forces source='Nipuna-referred' and requires an Active verified opportunity. No student or staff endpoint creates a Self-sourced/Other application, no Suggested/Student Interested states exist, and hiring_cycle is always 'Current' with no way to start a new cycle. Applications have no enrolment link.
- **Evidence:** services/career.py:232 Application(... source='Nipuna-referred'); :226 find_application(..., 'Current'); db/050_student_services.sql:300-317 status CHECK lacks Suggested/Student Interested and there is no application_enrolments link; routes/career.py exposes no create-application route for staff.

### G038

**Opportunity register is missing verification history, Expired transition, Open-Until-Filled review date, employer contact and structured compensation** — 23 Placement & Career Support (§7 Employer and opportunity register), Medium, phase CRM (D5)

- **Spec:** Record verified employer contact, closing date or Open Until Filled with a review date, compensation with currency and period, retain prior versions and verification history, recheck Open Until Filled items on the review date; states include Expired.
- **Code:** No employer contact or review-date/Open-Until-Filled field; compensation is a free-text column; edits overwrite the row (a previous version is not retained, only audit); Expired is a dead state: OPPORTUNITY_TRANSITIONS has no path into Expired and no job expires opportunities past closing_date. Past-closing opportunities are merely filtered out of the student list.
- **Evidence:** db/050_student_services.sql:249-275 opportunities columns; services/career.py:35-42 OPPORTUNITY_TRANSITIONS ('Active' -> only On Hold/Closed; 'Expired': ()), update_opportunity at :~290 overwrites in place; services/jobs.py JOBS lacks an expiry job.

### G039

**Withdrawal handling, status corrections and role-limited fields are not implemented** — 23 Placement & Career Support (§3, §17 Consent withdrawal and queued sends; §9 corrections), Medium, phase CRM (D5)

- **Spec:** Student can withdraw future sharing permission and ask to withdraw from a specific application; relevant queued unsent submissions are cancelled; previously sent data stays traceable. Corrections preserve previous values and disputed material corrections need independent review. Trainers, Sales and Front Office see only basic status.
- **Code:** set_consent(False) only flips a boolean; it does not touch open applications, and withdraw() immediately sets status Withdrawn with no 'request to withdraw from employer' step or record of what was already sent. Application status edits overwrite status_note/interview fields with only an event row, there is no correction or independent review path, and no field-level visibility rules exist (offers/compensation are returned to every ACADEMIC_ROLES caller, Branch Manager included).
- **Evidence:** services/career.py:172-186 set_consent, :244-257 withdraw, :444-468 change_application_status; routes/career.py uses require_roles(*ACADEMIC_ROLES) throughout.

### G040

**Career profile and CV review lack required fields and clocks** — 23 Placement & Career Support (§4, §5 Profile and CV), Medium, phase 12

- **Spec:** Profile holds verified contact, notice period, relocation preference and optional salary expectation/career gap; claims show Verified / Student Reported / Verification Pending with evidence, source and review date. CV review target is three staffed working days with a named reviewer and backup; material CV edits need renewed review.
- **Code:** Missing notice period, relocation preference, salary expectation, career-gap fields. Skills have a bare confidence label without evidence, source or review date. No CV review due date, reviewer/backup assignment or overdue escalation exists; CV review notifications go to the Academic Coordinator role at large. No change summary is stored per CV version.
- **Evidence:** db/050_student_services.sql:179-207 career_profiles, :215-232 cv_documents (no change_summary, due_at, assigned reviewer); services/career.py:196 notify(role_code='ACADEMIC_COORDINATOR').

### G041

**Reported AI answers all go to the Academic Coordinator; no Ask Trainer / Report Answer routing by issue type** — 24 AI Requirements (§10 Feedback and incident routing), Medium, phase 11

- **Spec:** Provide Ask Trainer / Report Answer with source context and a route to staff. Route reported issues by type: academic to Academic Coordinator with Trainer input; financial to Accounts and Super Admin; branch operational to Branch Manager; privacy/permission/retrieval fault to Super Admin; serious incident or policy to Founder. Keep prompt, model, tool, source and configuration versions with each report.
- **Code:** Feedback is only Helpful / Not helpful with a free comment. A 'Not helpful' answer notifies the branch Academic Coordinator only, with no issue category, no owner routing and no Trainer route. There is no 'Ask Trainer' action. Prompt/config version is not stored on ai_queries (only model name).
- **Evidence:** services/ask_nipuna.py:222-233 give_feedback (rating, comment; notify ACADEMIC_COORDINATOR only); controllers/ask_nipuna.py give_feedback Validator choice ('Helpful','Not helpful'); grep for 'Ask Trainer' / 'Report Answer' in frontend/src and backend finds nothing; models/ask_nipuna.py has no prompt_version/config_version column.

### G042

**No way to disable AI with scope, reason, actor and restoration record** — 24 AI Requirements (§12 Availability and incident controls), Medium, phase 3

- **Spec:** Super Admin may immediately disable an affected AI feature; Founder/CEO may disable AI company-wide. Record scope, reason, actor, time, affected users, remediation and restoration decision; restore only after checks pass.
- **Code:** The only switch is the app_settings row ai_enabled (seeded true). No endpoint, screen or service writes it, there is no per-feature switch, and no disable/restore incident record or audit. It can only be changed by editing the database.
- **Evidence:** grep -rn 'ai_enabled' backend frontend/src finds only reads at services/ask_nipuna.py:112 and :173 and the seed in db/050_student_services.sql:21. No route in routes/ask_nipuna.py or routes/security_controls.py sets it. (The Backlog covers the rupee ceiling only, not the kill switch.)

### G043

**Role home dashboards do not carry the approved first three figures for Trainer, Academic Coordinator, Super Admin and Placement Team** — 25 Reports & Dashboards (§2 Role home dashboards), Medium, phase 11

- **Spec:** Each role's first three figures: Trainer: Assigned sessions scheduled, Submissions awaiting my review, Assigned students with open support flags; Academic Coordinator: Enrolments awaiting batch allocation, Academic results awaiting publication review, Unfulfilled recording promises; Super Admin: Critical integration failures, Work awaiting named ownership/cover, Overdue payment verifications; Placement Team: Active opted-in support cases, Upcoming employer interviews, Verified joinings.
- **Code:** Academic, Super Admin and Founder summaries expose many of the underlying counts (allocation_queue, results_awaiting_publication, recording_exceptions, awaiting_owner, integration_failures), but the dashboards are not ordered as the three top figures per role and, for Placement Team, there is no dashboard or role. Super Admin 'Work awaiting named ownership/cover' is only exception ownership, not staff cover.
- **Evidence:** services/dashboards.py academic_summary/admin_summary/founder_summary; no placement keys; no Placement Team entry in services/context.py role groups (ADMIN_ROLES, BRANCH_ROLES, TRAINER_ROLES).

### G044

**No period selector, export formats, scheduled reports or report metadata/versioning** — 25 Reports & Dashboards (§3, §10 Periods, report metadata, exports and scheduled delivery), Medium, phase 11

- **Spec:** Period choices Today/Yesterday/This Week/Last Week/This Month/Last Month/Custom (IST, Monday-Sunday weeks); every report/export carries Period, Scope, Filters, Cutoff, Last Refresh, Data Completeness, Requesting User, Generation Time; Excel, CSV, PDF, Print and scheduled email with bulk export logging; issued reports preserved and corrections issued as labelled revised versions; daily/weekly/monthly management summaries; failed delivery raises an exception.
- **Code:** LMS reports and dashboards are live as-of snapshots only; no endpoint accepts a period or date range, no report/export generator exists, no scheduled report job is registered, and no issued-report store or revised-version mechanism exists. Reports show as_of but not Filters, Data Completeness or Requesting User. The only download helper is a CSV hook in the frontend client, used for no report.
- **Evidence:** routes/reports.py has only /trainer/reports and /academic/reports with branch_id filter; services/jobs.py JOBS has three non-report jobs; grep for csv/xlsx/pdf/openpyxl/reportlab/send_file in backend/*.py (non-test) finds nothing relevant; frontend/src/api/client.ts:154 download() has no report caller. (Dashboard freshness display is in Backlog; periods/exports/schedules are not.)

### G045

**Academic dashboard lacks several required actionable measures and certificate queues/filters** — 25 Reports & Dashboards (§6 Academic, delivery and certificate dashboards), Medium, phase 11

- **Spec:** Show students below the course-specific attendance minimum, required assignments missing or awaiting review, assessments awaiting grading, open academic-support cases, committed-start risks, planned vs delivered instructional hours, and separate Course Completion Certificate and Internship Certificate queues with blockers, generation/issue failures, reissues and revocations; filters by branch, course/combo, track, batch, curriculum version, Trainer, enrolment status, completion date, reviewer, review status and certificate type.
- **Code:** academic_reports.py reports delivery %, attendance average, recovery counts, completion review counts and certificate lead time per branch only. There are no planned-vs-delivered hours (sessions only), no missing-assignment or grading-queue measure, and no split by certificate type; the only report filter is branch. Certificate lead time uses a date column, not timestamps (Backlog covers that part).
- **Evidence:** services/academic_reports.py reports(branch_id) returns curriculum_delivered, attendance, completion_reviews, certificate_lead_time only; routes/reports.py accepts only branch_id; dashboards.certificates_in_status counts Eligibility Review/Awaiting Approval without certificate_type.

### G046

**Recipient can mark a notification's action as done; it is never tied to the source record** — 26 Notifications (§1, §8, §10), Medium, phase 10

- **Spec:** Delivery, read, acknowledgement and actual business completion remain distinct. A staff member viewing or acknowledging a warning does not finish the task. Required actions link to the existing task or case.
- **Code:** notification_centre.mark_action_done lets the recipient flip action_status to Completed with one click, without checking the underlying certificate, correction, recovery, access-extension or escalation record. Nothing in the codebase closes an Open action when the source record is actioned. A notice stays 'Open' after the work is done, or shows 'Completed' while the work is not.
- **Evidence:** backend/services/notification_centre.py:68-75 (mark_action_done); frontend/src/features/shared/notification-centre.tsx 'Mark action done' button. grep -rn action_status backend --include=*.py outside notification code returns nothing, so no source service ever sets it. The action_required count in repositories/notifications.py counts() therefore reflects clicks, not business state.

### G047

**Message centre lacks course/enrolment and date filters, a linked-record field, and staff Team/Branch views** — 26 Notifications (§10), Medium, phase 10

- **Spec:** Students search/filter by course/enrolment, category, date, unread and action required. Staff see permission-controlled My / Team / Branch views. Each notice shows event, time, linked record, required action and channel/delivery status.
- **Code:** Filters are only view (my/action/unread/completed/system), category and a title/body text search. The notifications table has no enrolment_id, student_id or linked-record reference, only a free-text link route. There is no date filter. Staff get only their own notices, with no Team or Branch view. Revised or cancelled notices are not shown as such.
- **Evidence:** backend/repositories/notifications.py:17-35 (list_stmt); backend/controllers/notifications.py VIEWS=('my','action','unread','completed','system'); db/001_foundation.sql:292-307 and db/050_student_services.sql:9-11 (columns); frontend/src/features/shared/notification-centre.tsx (only Category and Search inputs).

### G048

**No revised or cancelled notice state; superseded notices are not linked** — 26 Notifications (§3, §10), Medium, phase 10

- **Spec:** A changed or cancelled event invalidates its old queued notice. A new notice identifies the revised commitment and preserves history. Make a revised or cancelled notice explicit. Suppressed/Obsolete is a distinct state.
- **Code:** Each change posts an independent notification with a new event_key, such as session-change-N or reschedule-decision-N. Nothing marks the earlier notice as superseded, obsolete or revised, and there is no link between them. The delivery status enum is only Delivered or Failed.
- **Evidence:** db/001_foundation.sql:289 (notification_delivery_status = 'Delivered','Failed'); backend/services/notifications.py (dedupe on (event_key, recipient) only, no supersedes_id or revision field); backend/services/class_sessions.py:266,306,443 (new keys per change).

### G049

**No logical-notice / per-channel attempt model or the three separate counts** — 26 Notifications (§9, §11), Medium, phase 10

- **Spec:** One logical notification with per-recipient/per-channel attempts and provider references. States: Queued, Suppressed/Obsolete, Sending, Accepted by Provider, Delivered, Failed, Uncertain Acceptance, Staff Recovery Required. Record scheduled and actual times, retry count, recovery owner and outcome. Report logical notices, technical attempts and actual deliveries separately, with due/queued/failed/obsolete/suppression views and repeated-failure and blocked-template reports.
- **Code:** There is one notifications row per (event, recipient) with a 2-value delivery status and a delivery_note. There is no attempts table, retry_count, scheduled_at, provider reference, recovery owner or task link. No notification report or dashboard exists. Only the in-app list has a 'System Issues' tab. This is the LMS-side state the spec requires, separate from live WhatsApp/email calls.
- **Evidence:** db/001_foundation.sql:289-310 and db/050_student_services.sql:9-14 (the only notification schema); models/system.py:96-125; no notification report in backend/services/dashboards.py, reports or frontend/src/features/admin and branch.

### G050

**No preference history, language or timing preferences, and no template versioning** — 26 Notifications (§6, §7), Medium, phase 10

- **Spec:** Keep separate, dated preferences including language, channel and agreed timing. Preserve preference changes with actor, time and reason. Centrally version templates (variables, owner, permitted recipients). Support English, Telugu and Telugu-English. Record template version and language on each message.
- **Code:** notification_preferences holds only the current enabled flag per (user, group, channel) plus updated_at. There is no history, audit, language or timing field. set_preferences does not call audit. Notices are hard-coded English f-strings in services, with no template table, version or language column. students.preferred_language is never used when composing a notice. notify() never consults preferences.
- **Evidence:** backend/services/notification_centre.py:106-114 (set_preferences, no audit.record); db/050_student_services.sql:158-175; backend/models/notification_preferences.py; backend/services/notifications.py:21-44 (no language or template); grep -rniE 'template' over backend and db returns nothing.

### G051

**Cancellation, payment and refund changes arriving from the CRM raise no notice** — 26 Notifications (§3), Medium, phase 10

- **Spec:** Admission/delivery-plan confirmation goes to the student. Payment, refund and cancellation notices cover registration, decision, cancellation/access effective date and payout progress. Provisioning or sync failure creates a named recovery task.
- **Code:** CRM intake raises a notice only for AdmissionQualified (to the Academic Coordinators only) and for a branch transfer. AdmissionCancelled and FinanceSummaryUpdated (payment verified, refund, instalment changes) notify neither student nor staff. The student is not told about an admission confirmation or cancellation or access end date.
- **Evidence:** backend/services/crm.py has only two notify() call sites, at lines ~298 and ~526; _admission_cancelled (line 534) and _finance_summary_updated (line 557) contain none.

### G052

**No on-duty / on-call cover roster or missing-cover exception** — 26 Notifications (§8), Medium, phase 10

- **Spec:** Notify the designated on-duty person, not every employee. Branch Manager, Academic Coordinator, Super Admin, Accounts and Placement maintain named cover and backups. A missing roster is a configuration exception. Preserve Guntur's Super Admin cover.
- **Code:** notify(role_code=...) sends to every holder of the role at the branch, plus company-wide holders. There is no cover or backup roster, no designated on-duty field, and no missing-cover exception.
- **Evidence:** backend/services/notifications.py:30-34 (users_repo.user_ids_with_role fan-out); grep -rniE 'on.call|roster|backup_owner|cover' over backend and db returns nothing.

### G053

**Integration status vocabulary lacks Manual, Planned and Live Verified** — 27 Integrations Register (§1, §2, Register), Medium, phase 10

- **Spec:** Status must distinguish Pending Verification, Manual, Planned and Live Verified. Channels and branches are tracked individually. Staff-managed WhatsApp must be recorded as Manual.
- **Code:** The register uses configuration (Not Configured, Configuration Pending, Configured) and verification (Not Verified, Pending Verification, Verified, Failed). There is no Manual or Planned state, so a documented manual fallback cannot be recorded or distinguished from not configured. WhatsApp and email are single global rows with no per-branch (Guntur/Vijayawada) account, sender identity, template or last-successful-test.
- **Evidence:** db/001_foundation.sql:245-262 (enum types and integrations table); backend/models/enums.py:11 (INTEGRATION_VERIFICATION_STATUSES); db/001_foundation.sql:268-285 (single WHATSAPP and EMAIL rows); frontend/src/features/admin/integrations.tsx (Note: 'nothing here is Live Verified').

### G054

**Register lacks most mandatory per-connection fields and manual-fallback records** — 27 Integrations Register (§1, §4-6 (I01-I12)), Medium, phase 10

- **Spec:** Each connection retains business owner, technical maintainer, source of truth, data categories and direction, service branch, stable identifiers, authentication method, event trigger, expected timing, fallback, failure owner, reconciliation, audit and acceptance evidence. Manual fallbacks need named owner, backup, written procedure, reconciliation method and review date. Operational health and last successful event are shown separately from readiness.
- **Code:** The integrations table has only owner, requirement, the two statuses, last_checked_at, notes, evidence and verified_by/at. None of the other fields exists. There is no fallback or manual-procedure record and no per-integration last-successful-event or health field. Only the CRM sync monitor computes last-success, in dashboards._sync_flows.
- **Evidence:** db/001_foundation.sql:251-262; db/060_admin_security.sql (extra rows only); backend/models/system.py:63-96 (Integration model); backend/services/readiness.py FIELDS=('configuration_status','verification_status','owner','evidence','notes'); backend/services/dashboards.py:166-175 (last-success for CRM only).

### G055

**No configurable freshness threshold or stale status on CRM-sourced data** — 27 Integrations Register (§7), Medium, phase 10

- **Spec:** Every displayed CRM/LMS source shows last-successful-update time, configured freshness threshold and visible stale/unavailable status. Exports and Student 360 must not present stale or missing data as verified zero.
- **Code:** Finance and fee screens show 'As of <time> · source', but no threshold setting exists and nothing flags stale or unavailable. The founder/admin tile shows only the max finance as_of. status_since for the CRM carries no freshness or stale indicator. There is no freshness key in app_settings.
- **Evidence:** frontend/src/features/student/finance.tsx:48,88; backend/repositories/dashboards.py:101-103; grep -rn 'freshness|stale_after' db/*.sql returns nothing. The only 'freshness' logic is the student engagement window in services/student_home.py:206.

### G056

**Replayed or backfilled CRM events can fire current notifications; no historical-import guard** — 27 Integrations Register (§8, §9), Medium, phase 1

- **Spec:** A historical import or technical replay must not trigger fresh admission-conversion workflows, obsolete notifications or current-period counts, and must preserve original dates.
- **Code:** AdmissionQualified always calls notify() with an action-required notice to Academic Coordinators, regardless of event age, a replay flag or a backfill mode. The replayed flag only affects the inbox record. There is no historical or backfill marker on events or notifications, and no check of occurred_at or admission_date against now.
- **Evidence:** backend/services/crm.py:296-302 (unconditional notify in _admission_qualified); _process(replayed=...) at lines 111-129 does not reach the handler; grep for 'backfill|historical' in backend/services returns nothing.

### G057

**No intake of consent, stop-contact, WhatsApp opt-out or access-offboarding state from the CRM** — 27 Integrations Register (§4 I07 / §9 (stop-contact propagation)), Medium, phase 10

- **Spec:** Sync priority 1 is access/offboarding changes, stop-contact restrictions and entitlement changes. Pre-launch acceptance requires permission and stop-contact propagation. A WhatsApp opt-out blocks service messages on that channel, and a withdrawn consent is rechecked before a delayed send.
- **Code:** The CRM event types accepted are CourseUpserted, AdmissionQualified, AdmissionUpdated, AdmissionCancelled, FinanceSummaryUpdated, BranchUpserted, BranchFinanceSnapshot and AdmissionCurriculumMapped. There is no event or field for contact restriction, channel opt-out or consent, and no sync-priority ordering in event handling.
- **Evidence:** db/097_crm_round3.sql:95-96 (crm_events event_type CHECK list); backend/models/students.py:22-39 (no consent or opt-out columns); grep -rniE 'stop.contact|opt.out|consent' over backend and db returns nothing.

### G058

**No parent programme version pinning component versions; no variant tracks or equivalence-reference review** — Module 14 (§2, §3 Combos), Medium, phase 5

- **Spec:** A combo has a parent programme version recording the exact version and identity of each of its three tracks and the booster. A track may reference an approved equivalent standalone curriculum, after the AC has established matching outcomes, scope, depth and assessment. Otherwise it is a variant built from reusable parts. Shared work counts once in the parent total. Booster hours are shown as a separate part.
- **Code:** A combo version is a plain version of the combo course with its own modules. Track versions are separate rows with component_id. Nothing links a parent version to specific track versions. Pinning happens only per enrolment, at activation or via CRM events. A booster silently borrows the booster course's Active version when it has no track version (_map_curriculum and overview 'borrowed_from'). There is no AC review, equivalence assertion or recorded scope comparison for that borrowing. There is no shared-work reference and no booster hours split.
- **Evidence:** db/002_catalog_curriculum.sql:62-79; backend/services/crm.py:389-409 (_map_curriculum falls back to active_curriculum_version_id(component.component_course_id)); backend/services/curriculum.py:72-90 (borrowed_from). No table links parent versions to component versions.

### G059

**No stable, separately versioned reusable modules, topics or assessment definitions** — Module 14 (§9 Reusable academic material), Medium, phase 5

- **Spec:** Modules, topics, activities and assessment definitions have stable IDs and explicit versions. A published curriculum references exact approved reusable versions. Editing a shared item creates a proposed version, and running versions stay on the prior one.
- **Code:** Modules and topics belong to exactly one curriculum version (module.curriculum_version_id). Reuse is copy-on-create (copy_from_version_id), which duplicates rows with no lineage to the source. There is no shared item, no reference from a published version to a reusable item version, and no proposed-version flow.
- **Evidence:** db/002_catalog_curriculum.sql:104-131; backend/services/curriculum.py:119-130 (create_version copies modules and topics); no module or topic reuse table in db/*.sql.

### G060

**Branch/batch academic variations are not recorded** — Module 14 (§7 Branch-specific variations), Medium, phase 5

- **Spec:** The AC approves and records local examples, equivalent exercises, teaching language and sequencing, with the branches, batches and versions each variation applies to. Removing a required topic because a trainer, tool or facility is unavailable needs a recorded constraint, a feasibility check and an authorised remedial plan.
- **Code:** There is no variation record, no constraint or remedial-plan record, and no teaching-language field on a batch. Sequencing deviations are not recorded (a session simply carries a topic_id).
- **Evidence:** Grep for variation|remedial|teaching_language across backend/models, backend/services, db and frontend/src/features finds no matching entity. batches table (db/004_batches_sessions.sql:8-28) has no language or variation columns.

### G061

**Mapping-pending enrolments have no named owner or recovery task** — Module 14 (§8 Curriculum Mapping Pending recovery), Medium, phase 5

- **Spec:** Mark the enrolment Curriculum Mapping Pending, assign a named Academic Coordinator or other authorised academic owner and a recovery task. Record the failure, reconciliation and recovery.
- **Code:** The 'recovery owner' is a hard-coded display string ('Academic Coordinator — <branch>'). The enrolment has no owner or recovery column, and no task is created or assigned to a person when the status is set. The only notification is sent on release (when the version is activated), not on entering Pending. The exception queue lists the item but has no owner field for it.
- **Evidence:** backend/services/my_courses.py:87-88; db/003_students_enrolments.sql:142-169 (enrolments has no owner column); backend/services/crm.py:389-420 (_map_curriculum sets status only); db/080_exception_queue.sql:46-56.

### G062

**Batch type (Group/Individual/Corporate), schedule pattern (Regular/Weekend/Fast-track) and editable display name are not stored** — Module 15 (§3 Batch type, mode and pattern; §2 display name), Medium, phase 6

- **Spec:** Record branch, course or combo component, curriculum version, type, mode and pattern separately. Keep an editable human-readable display name apart from the permanent ID. Show the original creating branch, the current service branch and transfer history separately.
- **Code:** batches has mode but no type, pattern or display name. It has a single branch_id, with no creating-branch versus service-branch split and no transfer history. Individual and Corporate batches cannot be represented.
- **Evidence:** db/004_batches_sessions.sql:8-28 and db/098_batch_timetable.sql (no such columns); grep for batch_type|schedule_pattern|Fast-track|display_name across db and backend returns nothing.

### G063

**24-hour allocation escalation goes to Branch Managers, not Founder/Super Admin; deadlines are not tracked** — Module 15 (§6 Allocation escalation), Medium, phase 4

- **Spec:** At 24 hours before the committed start, escalate any unresolved allocation to Founder/CEO or Super Admin (immediately if first identified inside the window). The deadline is one working day after Admission when a seat exists. Otherwise it is at least 48 hours before the first class. Use the working-day calendar.
- **Code:** escalate_unallocated() notifies role BRANCH_MANAGER only, with a date-granularity comparison against admission.planned_start_date. No Founder or Super Admin notice is sent. The 1-working-day and 48-hour deadlines are not computed or stored anywhere, and there is no working-day calendar.
- **Evidence:** backend/services/batch_allocations.py:222-237 (role_code="BRANCH_MANAGER"); db/080_exception_queue.sql:59-70 (ALLOCATION source has no deadline logic). Backlog 'Allocation Pending is always an exception' covers only the queue threshold.

### G064

**No Nipuna Academic Calendar, company holidays or branch closures** — Module 15 (§9 Academic calendar and closures), Medium, phase 4

- **Spec:** Publish an academic calendar: central dates, plus Branch Manager-approved branch closures. A closure intersecting a class identifies the affected sessions and outstanding learning and proposes a replacement for BM approval. Individual student agreement is kept for material changes.
- **Code:** No calendar, holiday or closure entity exists. Session scheduling and recurrence ignore dates entirely, and nothing flags classes that fall on a closure. The Backlog mentions only trainer leave and the 'academic working calendar' for review clocks, not the batch scheduling calendar or closure handling.
- **Evidence:** grep for holiday|academic_calendar|closure across db, backend/models and backend/services returns no calendar table. class_sessions._occurrences (backend/services/class_sessions.py:164-178) has no closure check.

### G065

**Class states lack Partially Held and Confirmed; no replacement link, actual start/end/breaks or unfulfilled portion** — Module 15 (§15 Actual class states and logs), Medium, phase 6

- **Spec:** States are Planned, Confirmed, In Progress, Held, Partially Held, Rescheduled, Cancelled. Store the original slot and a link to the replacement. The trainer records actual start/end, breaks, delivered topics and hours, and any unfulfilled portion by the end of the same working day. Missing or disputed logs create AC review tasks.
- **Code:** States are Scheduled/Live/Delivered/Cancelled/Rescheduled. deliver() just stamps delivered_at and notes. There is no Partially Held, no actual start or end, no break or unfulfilled-portion capture, and no same-day deadline. A reschedule overwrites the same row, and the old slot lives only in session_changes with no link to a separate replacement session. No exception source or job raises missing-log tasks. The Backlog covers minutes-based attendance and multiple topics, not these.
- **Evidence:** db/004_batches_sessions.sql:150-175; backend/services/class_sessions.py:411-428 (deliver); db/080_exception_queue.sql sources list (no missing-log source); backend/services/jobs.py (only recording-check, support-escalate-overdue, allocation-escalation).

### G066

**No session purpose type (Replacement/Remedial/Extra) or linkage** — Module 15 (§16 Replacement, remedial and extra sessions), Medium, phase 6

- **Spec:** A Replacement links to the original class and its remaining topics. A Remedial session links to the evidence and individual recovery plan. An Extra session links to the approved addition. The AC proposes, the BM approves, and credit and hours are logged once with owner and deadline.
- **Code:** class_sessions has no purpose, parent or original-session reference, no proposal/approval step and no owner or deadline. A cancelled class leaves no tracked replacement obligation.
- **Evidence:** db/004_batches_sessions.sql:150-175; backend/services/class_sessions.py create_sessions (no such fields); grep for Replacement|Remedial in db and backend/models finds nothing.

### G067

**A class cannot be shared across courses, tracks or batches** — Module 15 (§4, §7 Shared classes), Medium, phase 6

- **Spec:** One class can serve learners from different courses or tracks when an AC verifies compatible coverage. It has one actual class, a scoped roster and one attendance observation per person, linked to each enrolment. Hours and trainer time are counted once. A shared event is not a conflict with itself. A seat is counted per distinct person.
- **Code:** A session belongs to exactly one batch, which belongs to one course. There is no roster-scope, AC verification or hosting-branch concept for shared classes. Two batches of different courses cannot share a session.
- **Evidence:** db/004_batches_sessions.sql:150-166 (session.batch_id single); db/004_batches_sessions.sql check_batch_allocation (batch.course_id must equal enrolment.course_id).

### G068

**Conflict checks omit student timetable, assistant and online capacity; room override has no documented reason** — Module 15 (§10 Conflicts and overrides), Medium, phase 6

- **Spec:** Before confirmation or allocation, check trainer and assistant availability, rooms and labs, equipment and online capacity, and a student's other compulsory classes. A BM may override an advisory warning with a documented reason. Genuine impossibility cannot be overridden. Show impacted records and recheck after a change.
- **Code:** Only the trainer (blocked) and the room (warning) are checked. The room warning is overridden with a boolean acknowledge_room_conflict and no reason stored, and any AC or BM can do it. There is no check of a student's overlapping classes across batches at allocation or scheduling. There is no assistant check and no online-capacity check. Travel buffers and trainer leave are in the Backlog, but not the student and assistant checks.
- **Evidence:** backend/services/class_sessions.py:143-155; backend/services/batch_allocations.py:review() (no timetable clash check); no reason column for the override in db/004 or db/010.

### G069

**No batch merge/split/successor history, and Completed/Archive rules are minimal** — Module 15 (§17, §19 Merge, split, successor, completion and archive), Medium, phase 6

- **Spec:** A BM may approve a within-branch merge or split after AC review, with successor links, effective date, reason and approval. Keep past records on the originals. Completed requires fulfilled batch obligations, accounted-for replacements and a named owner/plan/destination for paused or deferred students. Archive is allowed only when no live activity remains.
- **Code:** No merge, split or successor entity exists. Completed requires only that no sessions are Scheduled/Live/Rescheduled. Allocations are not checked and no paused-student owner is recorded. There is no Archived state.
- **Evidence:** db/010_delivery.sql check_batch_transition; grep for successor|merge|split|archiv in db/004, db/010 and backend/services/batches.py finds no such flow.

### G070

**Meet/Calendar/recording identifiers, recurring-series link and hosting branch are not stored** — Module 16 (§3, §4, §7, §10 Meet identifiers and series), Medium, phase 6

- **Spec:** Persist the Meet Space resource, Calendar series and instance, conference record and recording identifiers, plus the URL/code. Prefer a recurring batch-series link while keeping a dated Class Session per class. Do not use one branch-wide link for unrelated batches. A shared class has one designated hosting branch.
- **Code:** class_sessions stores only meet_link (a regex-checked URL) and meet_status, plus meet_events with organizer_email. There is no space/series/instance/conference ID, no batch-level series link, no hosting branch, and no check that a link is not already used by another batch's sessions.
- **Evidence:** db/004_batches_sessions.sql:150-166; db/010_delivery.sql meet_events; backend/services/class_sessions.py:468-478 (associate_meet validates the pattern only); grep for conference|meet_space|calendar_event|space_id finds nothing.

### G071

**No host/cohost, named backup for live online classes, guest approval or compromised-link incident record** — Module 16 (§5 Host, backup and guests), Medium, phase 6

- **Spec:** Name a backup for each live online class. Record the actual host and backup, and approved class guests (approved by the AC or BM, with student agreement where applicable). Handle a compromised link: secure the meeting, alert the manager, replace the link, notify participants and retain the incident history.
- **Code:** A session has a trainer_user_id only. There is no backup host, host/cohost, guest or incident entity. Link replacement exists only as reset_meet, which logs 'Link removed' and records no incident, notice to participants or manager alert.
- **Evidence:** db/004_batches_sessions.sql:150-166; db/010_delivery.sql meet_events event_type list; grep for backup (only a DB-backup setting in db/060) and guest returns nothing relevant.

### G072

**No Meet operations view for link/host readiness, delayed starts, disruptions or unconfirmed attendance** — Module 16 (§10 Operations dashboard), Medium, phase 6

- **Spec:** Branch/date/batch/trainer views show upcoming sessions, link and host readiness, delayed starts, disruptions and replacement work, attendance awaiting trainer confirmation, recording states, connection/subscription/storage exceptions, and last successful event/reconciliation time.
- **Code:** Schedule screens show a per-session Meet status. There is no consolidated readiness-by-date view, and no delayed-start, disruption or attendance-awaiting-confirmation view. No last-reconciliation time is stored or shown, and recording-check records no run time. Backlog 'Integration failures tile' covers only the readiness register.
- **Evidence:** backend/services/dashboards.py (no meet-readiness section); backend/services/jobs.py:12-14; frontend/src/features/academic/schedule.tsx shows per-session status only.

### G073

**Published recordings can be edited, re-released or unheld by one manager with no version history or independent review** — Module 17 (§3, §9 Corrections, privacy hold and independent review), Medium, phase 9

- **Spec:** A proposed edit, cut or replacement keeps version and audit history and must not silently alter a published record. Sensitive corrections to published recordings need independent authorised review, preserving previous mapping, audience, access and publication history. A privacy hold must preserve the reasons in a restricted workflow.
- **Code:** update() overwrites media_ref, duration and download_allowed in place on a Released recording, with only an audit old/new entry. There is no recording-version table. The same Academic Coordinator can hold and then release with no second approver. release() sets hold_reason = None, which erases the reason from the row; it survives only in the audit log. Remapping a recording to another session is not supported.
- **Evidence:** backend/services/recordings.py update() (setattr loop, no status guard), release() (recording.hold_reason = None; recording.partial_note = None), hold(). db/020_content_recordings.sql:152-173 has no version or replaced_by columns. No 'independent' or second-approver check exists anywhere in recordings.py.

### G074

**Download permission on a recording is a plain boolean flip with no documented exception or approval** — Module 17 (§7 Storage and controlled playback), Medium, phase 9

- **Spec:** Downloads need a documented approved exception or accepted corporate agreement. Controlled viewing is the default.
- **Code:** Any Academic Coordinator or Super Admin can set download_allowed = true through update() or register() with no reason, approver or evidence. The audit entry records old and new values only. Students see mode 'download' immediately.
- **Evidence:** backend/services/recordings.py register() (download_allowed=data.get('download_allowed', False)) and update(). db/020_content_recordings.sql:159 is a bare BOOLEAN with no exception reference.

### G075

**Staff cannot record a second-year extension request on behalf of a student** — Module 17 / 18 (M17 §8; M18 §5 Extension requests), Medium, phase 9

- **Spec:** Sales and Front Office may record and forward an extension request. Staff verify the enrolment, joining date and prior extension history before granting.
- **Code:** create_request is student-only (login's own enrolments). The route is restricted to the STUDENT role, and the service reads student_context(). An Academic Coordinator or Branch Manager has no way to log a request received by phone or in person, and there is no forwarding path. Staff can only approve or reject requests the student created.
- **Evidence:** backend/routes/access_extensions.py lines 12-13 (@require_roles('STUDENT') on create). backend/services/access_extensions.py create_request() uses student_library.student_context().

### G076

**Asset metadata required by the spec is missing** — Module 18 (§8 Metadata), Medium, phase 9

- **Spec:** Record author/owner, version, source and usage rights, reviewer, publication date, file size, duration or estimated study time, and storage or link identity. Content types include slides, handouts, images, notebooks, datasets and reference links.
- **Code:** No columns for source or provenance, usage rights or licence, duration or estimated study time. The reviewer is only in the content_reviews trail, not on the asset. Each placement records only a download flag, with no preview policy or print policy. There are no distinct Slides, Handout, Image or Notebook content types.
- **Evidence:** db/020_content_recordings.sql content_items (lines 15-45) and content_versions (lines 85-105); backend/models/content.py:15 CONTENT_TYPES.

### G077

**External links have no owner, rights record or periodic check, and no broken-link exception** — Module 18 (§7 External references), Medium, phase 9

- **Spec:** An external reference needs a verified destination, known usage rights, a named owner and periodic link/access checks. Broken or unsafe links become visible exceptions, are withdrawn from student use and the student is updated.
- **Code:** A link is accepted if it is http(s) with a host (_clean_url). It is never re-checked. No job, status, exception row or dashboard figure exists for broken or unsafe links, and there is no rights field. Students open the raw URL. The Backlog covers malware scanning only, not link verification.
- **Evidence:** backend/services/content.py _clean_url() and _source_of(); backend/services/jobs.py has no content or link job; no broken-link, inaccessible or outdated tracking anywhere in db/020_content_recordings.sql or backend/services/dashboards.py.

### G078

**Student library lacks Recently Added/Updated and the Scheduled, Temporarily Unavailable and Withdrawn states** — Module 18 (§10 Student navigation), Medium, phase 9

- **Spec:** Show Recently Added and Recently Updated. Distinguish Available, Scheduled, Temporarily Unavailable, Withdrawn and Expired, with an explanation and next availability. Show Session Resources.
- **Code:** Resources is a flat table with course, type and title filters. It has no Recently Added or Updated lists. Only released, non-retired items are returned, so a withdrawn or held item silently disappears with no state or explanation, and Scheduled does not exist. The Report a problem action is in the Backlog, but the state display and recents are not.
- **Evidence:** frontend/src/features/student/resources.tsx (filters and DataTable only); backend/repositories/content.py released_candidates() (retired_at IS NULL and has a Released version).

### G079

**Batch-specific materials lose access after a batch transfer, unlike recordings** — Module 18 (§3 Access after transfer), Medium, phase 9

- **Spec:** Batch material is limited to the permitted batch/enrolments, subject to approved transfer and accepted historical access rights.
- **Code:** Content audience uses only the enrolment's current Active allocation (batch_by_enrolment), so a transferred student loses material of the previous batch. Recordings keep access via 'Transferred' allocations, so the two are inconsistent. Spec §5 says a pause or transfer preserves earlier resources where entitlement continues.
- **Evidence:** backend/services/student_library.py batch_by_enrolment uses batches_repo.active_allocations; backend/services/content.py item_matches_enrolment(batch_id) compares item.batch_id to that batch. Contrast backend/repositories/recordings.py allocations_for_enrolments (Active and Transferred).

### G080

**Assignments can only target a whole batch; no selected-student or individual recovery allocation** — Module 19 (§3 Allocation), Medium, phase 7

- **Spec:** Allow allocation to the whole batch, selected enrolled students or an individual recovery plan, each with explicit reason and scope. One definition may be allocated to authorised enrolments in both branches, each with its own deadline, submission and result.
- **Code:** assignments.batch_id is NOT NULL and the only audience. There is no allocation table, per-enrolment deadline or reason, and no cross-branch allocation. Students see work only through their active batch seat (released_for_batches), so a recovery task for one student is impossible.
- **Evidence:** db/030_assessments.sql:14-15 (batch_id NOT NULL) and trigger forbidding batch change; backend/services/assignments.py _student_rows() via assessment_scope.student_enrolments_by_batch; no assignment_allocations table in db/*.sql.

### G081

**Released assignment edits overwrite the brief with no preserved version per student and no Academic Coordinator review** — Module 19 (§3 Post-publication change), Medium, phase 7

- **Spec:** Preserve the exact brief, rubric and attachment versions given to each student. A material post-publication change needs Academic Coordinator review, notice, and a deadline adjustment where needed, and the earlier version and acceptance history are kept.
- **Code:** update_assignment() setattr's the brief, attachments and due_at in place. The earlier text exists only inside the audit old/new JSON. A trainer can make the change directly, with no review step and no per-student record of which version they saw or accepted. Students are only notified.
- **Evidence:** backend/services/assignments.py update_assignment() (RELEASED_EDITABLE, setattr loop, _notify_students). No assignment_versions table in db/030_assessments.sql.

### G082

**Pre-deadline replacement stays open after the trainer has started review** — Module 19 (§7 Replacement before review), Medium, phase 7

- **Spec:** A student may replace work only before the effective deadline and before review begins. After review begins, replacement needs the Trainer's resubmission instruction.
- **Code:** submission_window() allows mode 'replacement' whenever the latest version has no completed review and now <= due_at. review_started_at (set by start_review) is ignored, so a student can replace work while the trainer is actively reviewing it.
- **Evidence:** backend/services/assignments.py submission_window(): 'if review is None: if now <= assignment.due_at: return allowed replacement'. start_review() in backend/services/submissions.py sets review_started_at but nothing reads it here.

### G083

**Repository and external-link submissions do not record the reviewed version or access scope** — Module 19 (§6 Repository evidence), Medium, phase 7

- **Spec:** For a repository or mutable artifact record the submitted commit/release or identifiable version, URL, access scope and assessment evidence, so a later edit does not replace what was reviewed. Check links at review time.
- **Code:** A submission stores one link_url string. There is no commit or version field, access-scope field, evidence snapshot or review-time link check. Link verification is partly in the Backlog (Validation Pending/Failed), but commit and version evidence is not.
- **Evidence:** db/030_assessments.sql assignment_submissions columns (link_url VARCHAR(500) only); backend/services/submissions.py submit().

### G084

**No Completion dimension (Pending / Completed / Excused) and no Excused approval** — Module 19 (§8 Completion dimension), Medium, phase 7

- **Spec:** Show a separate Completion value (Pending, Completed, Excused); Evaluated does not mean Completed. Excused needs Academic Coordinator approval and cannot invent marks or satisfy a mandatory outcome automatically.
- **Code:** The student task state is one overloaded word: Upcoming, Due, Overdue, Submitted, Under Review, Reviewed or Resubmission Requested. The results table has only marks and a Provisional, Moderated or Published status. There is no completion status, no excused result and no exemption approval flow. Overdue also has no Missing label or separate timing dimension.
- **Evidence:** backend/services/assignments.py STUDENT_STATES and task_state(); db/030_assessments.sql results table and submission_reviews outcome enum (Reviewed / Resubmission Requested).

### G085

**Final project milestones, demonstration/viva and individual-contribution evidence are not modelled** — Module 19 (§9 Final projects), Medium, phase 7

- **Spec:** A final project requires an approved brief, agreed milestones, final deliverable, demonstration or viva, assessment feedback and individual-contribution evidence, linked to the curriculum rubric.
- **Code:** 'Final project' is only a value in the assignment_kind enum, handled exactly like a class assignment with one deadline, one review and one mark. No milestones, viva or demonstration record, contribution evidence or kind-specific review target exists. The Backlog lists group projects but not milestones or viva.
- **Evidence:** db/030_assessments.sql:8 assignment_kind enum; no milestone or viva table in db/*.sql; backend/services/assignments.py has no kind-specific logic.

### G086

**Practice quiz feedback, explanations and correct answers are never shown after submission** — Module 20 Tests (§6, §8), Medium, phase 7

- **Spec:** Practice quizzes may reveal approved scores, explanations and correct answers after submission. Practice displays latest and best scores.
- **Code:** visible_score() returns only a numeric total for practice. There is no student endpoint or payload that returns per-question correctness, the correct answer or the explanation. The student payload has questions without keys and answers only. Latest and best score is not shown.
- **Evidence:** backend/services/assessment_rules.py visible_score(). backend/services/attempts.py student_payload() (no key, no explanation). grep for 'explanation' in frontend/src/features/student/*.tsx finds nothing.

### G087

**Test timing has no separate latest-start; start checks skip enrolment version and prerequisites** — Module 20 Tests (§3, §4), Medium, phase 7

- **Spec:** Configure the opening time, latest permitted start, duration, submission-closing time and attempts separately, with the latest start leaving the full duration before close. Starting checks the student's enrolment and curriculum version, approved prerequisites, entitlement and remaining attempts.
- **Code:** The test has opens_at and closes_at only, with no latest-start field. The deadline is min(start+duration, closes_at), so a student starting just before close gets a shortened test instead of being refused. start_attempt() checks the seat in the batch, window status and attempt count only, with no enrolment-status, curriculum-version or prerequisite check.
- **Evidence:** db/030 tests columns (duration_minutes, opens_at, closes_at, attempts_allowed). backend/services/attempts.py _deadline() and start_attempt().

### G088

**Coding tests have no language, limits, I/O contract or sample/hidden case definition** — Module 20 Tests (§7), Medium, phase 7

- **Spec:** Each coding test records language and version, permitted libraries, input/output contract, resource and execution limits, visible sample cases and protected hidden cases. The Academic Coordinator approves the test cases. Run sample and autosave must not consume an attempt.
- **Code:** A Coding question is only a stem plus a rubric-style answer_key. There is no field for language, version, libraries, I/O contract, limits, or sample vs hidden cases, so hidden-case secrecy cannot be enforced. This is the LMS-side definition that the spec needs even before the runner exists. The backlog lists only the runner as pending.
- **Evidence:** db/030 questions columns (stem, options, answer_key, explanation). backend/services/scoring.py validate_question_key. No coding-case table exists anywhere in db/*.sql.

### G089

**Question bank item lacks curriculum-version compatibility, outcome, language, rights and publication history** — Module 20 Tests (§2), Medium, phase 7

- **Spec:** A bank item keeps course/curriculum-version compatibility, topic, learning outcome, difficulty, language, author, reviewer, source/usage rights, version and publication history. Compatibility is reviewed before reuse.
- **Code:** questions has course, branch, topic, difficulty and tags with version, author and reviewer. It has no curriculum-version link, learning outcome, language, source or usage rights, or publication history table. set_questions() checks only course and branch, so compatibility with the batch's curriculum version is never checked.
- **Evidence:** db/030 questions columns. backend/services/tests.py set_questions() checks question.course_id and question.branch_id only.

### G090

**Unattempted work after a window closes creates no support or reassessment review task** — Module 20 Tests (§5, §11), Medium, phase 7

- **Spec:** Unattempted work after a window closes creates a support or reassessment review task, not an automatic zero. Missed or failed required tests feed the trainer and coordinator views.
- **Code:** Results show 'Not attempted' on the student view only. Nothing creates a task, notification or queue entry when a required test window closes without an attempt.
- **Evidence:** backend/services/results.py _test_row() label 'Not attempted'. No test-close job or hook in backend/services/tests.py close_test() or jobs.py.

### G091

**No same-day Trainer confirmation tracking or next-day Academic Coordinator alert** — Module 21 Attendance (§3, §13), Medium, phase 4

- **Spec:** The Trainer confirms attendance by the end of the same academic working day. On the next academic working day, a missing confirmation alerts the Academic Coordinator. The class date and the later confirmation date are kept separately.
- **Code:** No job or notification covers unconfirmed attendance. The three registered jobs are allocation-escalation, recording-check and support-escalate-overdue. The register list shows 'Not yet marked' only when someone opens it. marked_at is stored, so the dates are kept, but nothing alerts anyone. This is not one of the backlog's at-risk or reminder items.
- **Evidence:** backend/services/jobs.py JOBS dict has 3 entries. grep of services for unmarked or pending-confirmation notify calls finds none.

### G092

**Approved pause is not reflected in attendance expectations** — Module 21 Attendance (§5), Medium, phase 8

- **Spec:** An approved pause revises future expectations through the delivery plan without erasing earlier absences. Inactivity alerts are not applied during an approved pause.
- **Code:** A CRM Pause only sets enrolment.status = 'Paused'. The attendance grid and the progress view ignore pause periods. Sessions delivered while the enrolment is Paused still count as unmarked or absent for that student, and there is no pause start or end date.
- **Evidence:** backend/services/crm.py (pause branch ~line 495) sets status only. db/040 attendance_grid has no pause filter. grep for 'pause' in db and models finds only status enums.

### G093

**Correction approval does not flag a completed enrolment for academic review and has no recalculation trace** — Module 21 Attendance (§7), Medium, phase 8

- **Spec:** A correction must not silently reverse an approved completion. If corrected evidence affects an earlier completion decision, retain the original approval and flag an authorised academic review. Original and recalculated values and the source event are traceable per affected student. The Academic Coordinator resolves a correction within 2 academic working days.
- **Code:** _apply_correction() changes the record and the audit log holds the old status. It does not check whether the enrolment is already Completed or has an issued certificate, and does not open a review. Recalculated percentages are live view values with no stored before/after. The correction request has no due date and no overdue escalation.
- **Evidence:** backend/services/attendance.py _apply_correction() and decide_correction(). The attendance_corrections table in db/040 has no due or target column.

### G094

**No guardian or under-18 handling** — Module 21 Attendance (§11), Medium, phase 12

- **Spec:** For a learner under 18, an authorised guardian may receive academic updates through verified details and recorded permissions. For an adult, a payer does not get academic information by default.
- **Code:** The LMS has no date of birth, minor flag, guardian contact or guardian permission record, and no stop-contact scope for outreach.
- **Evidence:** grep for guardian, dob, date_of_birth and minor across backend/models, backend/services, db/*.sql and frontend/src finds no matches (only unrelated uploads and a test helper).

### G095

**Reissue and correction has no request, approval or changed-field record** — Module 22 Certificates (§10), Medium, phase 3

- **Spec:** The Academic Coordinator requests a correction or reissue. The Branch Manager approves, with independent review where the requester would approve their own change. The record keeps changed fields, evidence, requester, approver, and effective and reissue dates. The existing certificate stays Valid until the replacement is issued.
- **Code:** reissue() is one call by a Branch Manager or Super Admin. It sets the old row to Superseded and inserts the new Issued row at once. There is no requester or approver split, no changed-fields or evidence capture (only free-text reason and optional holder_name), and no Academic Coordinator request step.
- **Evidence:** backend/services/certificates.py reissue() and RE_ISSUERS = ('BRANCH_MANAGER','SUPER_ADMIN'). The reissue row copies recommended_by and approved_by from the previous version, so the earlier approval is reused with no renewed review.

### G096

**Approval is not bound to identity, evidence and rule/template version, and there is no recheck before issue** — Module 22 Certificates (§2, §4, §8), Medium, phase 8

- **Spec:** Bind approval to the reviewed identity, award details, completion evidence and template/rule versions. A material change requires renewed review. Recheck authoritative records and entitlement immediately before issue. Preserve the rule version and the calculation/verification time.
- **Code:** There are no rule-version, template-version, evidence-snapshot or verified-at fields on certificates. issue() checks only that the status is Approved for Issue. A change to the student name or the enrolment after approval does not invalidate the approval. There is no pre-issue recheck.
- **Evidence:** backend/models/certificates.py has no such columns. backend/services/certificates.py issue() has only _expect_status. Also missing are completion_date, duration and the printed-field freeze (only holder_name is stored).

### G097

**No bulk or paired review, no issue-register export, no dashboard filters or review-target clock** — Module 22 Certificates (§4, §9, §12), Medium, phase 8

- **Spec:** The Academic Coordinator can select several student-award pairs for one review. Paired Course and Internship drafts share one review screen. A permission-controlled exportable issue register is required. The dashboard needs filters (course, programme, batch, trainer, rule version, blocker, approver, dates) and paired-state views. Review and issue within 2 academic working days, with owner alerts.
- **Code:** All transitions are single-certificate endpoints. There is no export (no csv/export code anywhere in the backend or frontend). The register filters are only branch, course, status, type and a text search. There is no 2-working-day target or overdue alert, and no paired-state view.
- **Evidence:** backend/routes/certificates.py has only per-id actions. backend/controllers/certificates.py list_register validates branch_id, course_id, status, certificate_type and q only. backend/services/jobs.py JOBS has no certificate job. grep for 'export' and 'csv' in backend and frontend/src finds nothing.

### G098

**Certificate state model lacks processing, document-version and delivery dimensions** — Module 22 Certificates (§8, §9, §12), Medium, phase 8

- **Spec:** Separate dimensions: Processing (Queued, Processing, Generation Failed with retry state and error), Document (Draft Generated, Final Generated, Issued), Approval including Returned for Correction, Delivery per channel. Failures have an owner, a first deadline and retry history. Paired failures are isolated and retried from a checkpoint.
- **Code:** There is one overloaded status enum. No processing or failure state, error, owner or retry history exists. No delivery state exists. The Returned for Correction approval state is not modelled; a return just sets status back to Eligibility Review. This is the LMS-side state the spec needs, separate from the PDF/email gap already listed in the backlog.
- **Evidence:** db/040 certificate_status enum (7 values) and the certificates columns. backend/models/certificates.py.

### G099

**Ask Nipuna has no placement, certificate or fee sources and answers career questions with a canned text** — 24 AI Requirements (§5, §8, §9 Authoritative sources and Placement/Certificate facts), Low, phase 11

- **Spec:** Answers about certificates, placement/career, and payments must come from the authoritative register, permitted career profile/applications/outcomes and the CRM ledger, with version/date/freshness cited and 'Data unavailable / not verified' when unsupported; AI may suggest matches and flag stale evidence and overdue actions for placement staff.
- **Code:** student_facts() supplies enrolments, curriculum, sessions, delivery and due work only. Career questions get a fixed paragraph in ai_rules.student_answer regardless of the student's career data; certificate and fee questions have no source at all. Staff facts are batch counts only, so there are no placement staff AI features (CV drafts, match suggestions with recorded reasons, stale-evidence flags). Freshness of each fact is not cited.
- **Evidence:** services/ai_facts.py:101-144 student_facts/staff_facts; services/ai_rules.py career branch returns a static string; no FACT_PROVIDERS registered for career or certificates (only 'due_work' at services/ask_nipuna.py:30).

### G100

**No task is created when an assignment is three days overdue** — 26 Notifications (§3 (Assignments row; Module 19)), Low, phase 7

- **Spec:** At three days overdue create the Trainer support-review task under Module 19, and suppress missing-work reminders after accepted submission.
- **Code:** The overdue state is computed on read only. No job or service creates a trainer support-review task or notice at +3 days. The backlog covers only the 24 h, due-date and +1 day reminders, not this task.
- **Evidence:** backend/services/assignments.py:27,51 (Overdue computed as a display state); backend/services/jobs.py:26-31 (JOBS has only allocation-escalation, recording-check and support-escalate-overdue).

### G101

**No assistant/substitute cover role or approval; substitute must already be an assigned batch trainer** — Module 15 (§11 Assistant and substitute cover), Low, phase 6

- **Spec:** The BM approves assistant and substitute assignments. The AC verifies competence, scope and handover. Record planned versus actual trainer, role, approval, sessions covered and notice before class. Preapproved cover runs only within its limits.
- **Code:** batch_trainer_role is only Lead or Co-trainer. A session trainer change is applied immediately by an AC or BM with a reason. It requires the substitute to already be an active batch trainer (_assigned_trainer). There is no approval record, scope limits or verification step. The Backlog's 'Substitute trainer on a single class' covers the picker UI, not this approval and role model.
- **Evidence:** db/004_batches_sessions.sql:68; backend/services/class_sessions.py:196-199 and 232-248; db/010_delivery.sql session_changes (no approver column).

### G102

**Students cannot submit preferred slots (Requested / Waitlisted / Confirmed)** — Module 15 (§13 Student slot preferences), Low, phase 6

- **Spec:** A student may submit preferred slots through the LMS. The display shows Requested, Waitlisted or Confirmed accurately. A request reserves no seat. (The waitlist itself is a known Backlog item; this is the student-facing request.)
- **Code:** There is no preference-request entity, API or student screen. Student schedule and my-courses pages only show allocated batches.
- **Evidence:** grep for preferred|slot request in backend and frontend/src/features/student finds no such feature (preferred_language and similar only).

### G103

**Capacity is one integer; no separate classroom, lab and online capacity, and no review for increases** — Module 15 (§7 Capacity), Low, phase 6

- **Spec:** Record classroom seats, usable lab positions and verified online capacity separately. Hybrid respects both sides. A BM sets capacity after AC review. A proposed increase needs resource validation and academic review.
- **Code:** batches.capacity is a single INT > 0. Any managing role edits it directly (update_batch) with only a lower-bound check against current allocations.
- **Evidence:** db/004_batches_sessions.sql:14; backend/services/batches.py:226-243.

### G104

**No Meet participation evidence or unmatched-identity review; recording states lack Configured/Started/File Generated/Playback Ready and Review Required/Failed** — Module 16 (§7, §8 Meet evidence and recording facts), Low, phase 6

- **Spec:** Meet join/leave events (including reconnects) support review but do not establish attendance. Review unmatched identities. Track Configured, Started, File Generated, Playback Ready and Released as separate facts, with Processing, Failed, Unavailable and Review Required exceptions. Uncertain or conflicting recording matches stay unavailable until a human resolves them.
- **Code:** There is no participation-evidence table or unmatched-identity queue. recording_status is Processing/Released/Partial/Held/Unavailable/Expired. There is no Failed, Review Required or unmatched-file state, and recording_issue_type is Partial/Held/Unavailable/Integration Unavailable. Configured/Started/File Generated/Playback Ready cannot be told apart. No recording-capture configuration is stored per session.
- **Evidence:** db/020_content_recordings.sql:150-174 and 208; db/004_batches_sessions.sql:150-166.

### G105

**Expiry is shown as a date only, and there is no 'approaching expiry' notice** — Module 17 / 18 (M17 §8, §11; M18 §5 Access extension), Low, phase 9

- **Spec:** Display the exact expiry date and time (end of the anniversary day in IST). Approaching expiry needs a distinct service notice to the student.
- **Code:** Expiry is a DATE column and a date object. The UI prints 'Until <date>' with no time. No job or notification exists for approaching expiry. The only registered jobs are allocation-escalation, recording-check and support-escalate-overdue.
- **Evidence:** frontend/src/api/content.ts:274-278 accessText(); backend/services/access.py (expiry: dict[str, date]); backend/services/jobs.py JOBS; grep for approaching/expiring/expiry notice in backend returns nothing outside activation tokens.

### G106

**Only 'opened' is recorded: no download event, playback position or Not Recorded display** — Module 18 (§11 Learning signals), Low, phase 9

- **Spec:** Where supported, record distinct events for opened, download initiated, playback position, activity submitted and completed, with version, enrolment, timestamp and source. Unsupported tracking shows as Not Recorded, not zero.
- **Code:** record_activity is called only from open_item ('resource_view') and watch ('recording_view'). file_for(), which serves downloads, records nothing, so download events and policy denials are not logged. There is no playback-position event and no Not Recorded handling.
- **Evidence:** grep record_activity: backend/services/content.py:519 and backend/services/recordings.py:450 only. backend/services/content.py file_for() has no activity or audit call.

### G107

**The task AI-use rule and the student's AI disclosure are never enforced** — Module 19 (§10 AI-use rule), Low, phase 7

- **Spec:** When AI is used the student identifies the tool, describes the assistance and says what they checked themselves. The published rule (Allowed with disclosure, Limited, Not permitted) is shown and applied.
- **Code:** ai_use_rule is stored and returned, and ai_disclosure is an optional text field. submit() never requires a disclosure under 'Allowed with disclosure' or 'Limited to specified uses', and never checks the rule at all. Disclosure is not structured into tool, assistance and independent work.
- **Evidence:** backend/services/submissions.py submit() copies ai_disclosure only if present; grep ai_use_rule|ai_disclosure in backend (excluding tests) shows only models and seed.

### G108

**No Trainer support-review task at three days overdue** — Module 19 (§11 Trainer support task), Low, phase 7

- **Spec:** At three days overdue with required work still missing, create a Trainer support-review task. Also show missing work, students needing support and an owner and next action on the trainer dashboard.
- **Code:** No job or rule creates a support-review task or notice for missing required work. The Backlog mentions only the 24h, due date and +1 day reminders, not this +3 day task.
- **Evidence:** backend/services/jobs.py JOBS has three jobs, none for assignments; no overdue-task creation in backend/services/assignments.py or trainer_workspace.py.

### G109

**Hybrid in-person vs online participation is not recorded per entry** — Module 21 Attendance (§3), Low, phase 8

- **Spec:** For hybrid teaching, record in-person versus online participation against the same actual session and enrolment, plus delivery incident handling for host or platform failure.
- **Code:** attendance_records has status, remarks and the marker only. There is no participation mode and no evidence field apart from remarks. A class that has no host failure state creates no delivery incident record tied to attendance.
- **Evidence:** db/040 attendance_records columns.

# Combined CRM and LMS production test plan

Tests the CRM (`https://nipunacrm.com`) and the LMS (`https://3-111-225-125.sslip.io`) together, from the first setting that links them to the clean-up that makes them ready for real students. It follows how the two systems really behave: the CRM pushes events to the LMS after each commit, the LMS answers a status pull, and WhatsApp for LMS notices goes LMS → CRM → Pinbot.

Sources: `docs/CRM_INTEGRATION.md` (this repo), `~/nipuna-crm/docs/DEVELOPMENT.md` (the LMS link, commands) and `~/nipuna-crm/docs/API.md` steps 22, 23, 28. Updated 26 Oct 2026.

---

## 1. Where both systems stand (checked 26 Oct 2026)

| | CRM (`nipuna-crm-test`, answers as `nipunacrm.com`) | LMS (`nipunalms-prod`) |
|---|---|---|
| Server | `t3.micro`, Ubuntu, 15.252.72.136, **no reserved IP** | `t3.micro`, Ubuntu, 3.111.225.125 (Elastic IP) |
| Address | `https://nipunacrm.com/api/v1` (Let's Encrypt to 14 Jan 2027) | `https://3-111-225-125.sslip.io/api/v1` (to 21 Jan 2027) |
| Data | 2 persons, 2 leads, 0 admissions, 0 payments, 8 courses, 2 branches, 7 staff | 2 staff (Founder, Super Admin), 0 students, 0 courses, 0 CRM events |
| Link settings | No `LMS_BASE_URL`, no `LMS_SERVICE_KEY`, cutoff `LMS_SYNC_FROM_DATE=2099-12-31` | `CRM_BASE_URL` set; `CRM_SERVICE_KEY` generated, not shared |
| Cron | `flask jobs run` every minute. **No `lms worker` line** | `flask jobs run` every 5 minutes |
| WhatsApp | On, sends only to the test numbers (to be one: +91 9392329248) | On, template list holds `nipuna_lms_password_reset_code_auth_v2` only; cannot send until the CRM holds the key. **v2 verified end to end on the local dev pair on 28 Oct 2026** (LMS reset code, CRM, Pinbot, arrived with the Copy code button; the CRM sent language code `en` and Pinbot accepted it); not yet on production |
| Google | none | Meet, Drive and Email Working and on |
| Backups | Dumps from 10 and 15 Oct in `/srv/nipuna/backups` | `BASELINE-clean-after-go-live.dump` and nightly dumps |

**Gaps this plan must close first**
1. The CRM's template registry still says `nipuna_lms_password_reset_code_auth_v1`. The approved name is **v2** (the LMS already uses v2). A CRM code change.
2. No `lms worker` cron on the CRM server, so retries and the status pull would not run.
3. `LMS_WEB_URL` and `LMS_WHATSAPP_STATUS_EVENTS` are not set on the CRM server.
4. The CRM server has no reserved IP: if it is stopped and started, `nipunacrm.com` breaks until DNS is edited, and the LMS's WhatsApp calls and the CRM's pushes stop.
5. Only **three** templates are approved in Pinbot (CRM's panel check of 23 Oct, plus the v2 note): `nipuna_lms_password_reset_code_auth_v2`, `nipuna_batch_allocated_u_v1` and `nipuna_lms_account_activated_u_v1`. The other eight `nipuna_lms_*` templates (activation link, staff invite, class reminder, cancelled, rescheduled, result, certificate, batch change) were **not submitted**, so those WhatsApp messages are recorded as Skipped or Failed. That is expected, not a test failure, and their email twins still go. Submitting them to Pinbot is the owner's job.

---

## 2. Decisions before anything runs

| # | Decision | Why it matters | Recommended |
|---|---|---|---|
| D1 | **Where to run the money flow** (lead, invoice, payment, admission). | An admission needs an accepted payment plan and a **verified first payment**. Run in the production CRM, that writes a real invoice, payment and receipt number. Ledgers cannot be row-deleted in the CRM, so cleaning up means restoring a dump. | Run the full flow once on the **local dev pair** (already linked, no ledger impact). In production run only the non-money steps (phases B, C, K, L). Run the money flow in production only if D2 is yes. |
| D2 | Accept a TEST admission, invoice and payment in the production CRM, then restore the CRM from a dump taken just before? | The restore also discards anything entered in the meantime, so this is safe only while the CRM holds no real admissions and nobody is entering real data. | Yes, but only in a booked window, with a dump taken at its start |
| D3 | Accounts and roles | The production CRM has **no Sales user** and one Accounts user. The CRM team's answer (28 Oct): the **Guntur Branch Manager** plays counsellor and Branch Manager, the **Accounts user** verifies the payment (the two-person rule holds), and the test uses the **standard fee, no extra discount, no payment correction**, because a discount above the limit, a fee below the floor or a correction each need a second approver and there is none | In the LMS: a Branch Manager and a Trainer on plus-addresses of one inbox, passwords shown once |
| D4 | WhatsApp numbers | Production holds two test numbers; the CRM team removes the second before the window, so **one number only (+91 9392329248)** is messaged. Every TEST person's phone is set to it; any other number is Skipped | Use that number for every TEST person |
| D5 | Window and owner | Each step names an owner; the CRM team does the CRM-side steps | Agree one 2-hour window per phase group |

**Rules for every test**
- Name every test thing `TEST` (person, lead, class, batch).
- Use only your own addresses (plus-addresses of one Gmail inbox) and the CRM test numbers.
- Take the backups in section 3 first, and check the cutoff is still `2099-12-31` before any phase that could send an admission.
- Do not give real students access until phase M is signed off.

---

## 3. Pre-flight (both sides)

| # | Action | Owner | Done when |
|---|---|---|---|
| P1 | Dump both databases: CRM `pg_dump -Fc` to `/srv/nipuna/backups/nipunacrm-before-link-test-<date>.dump`; LMS keep `BASELINE-clean-after-go-live.dump` and take a fresh one | CRM team, LMS | Both files exist, sizes sane |
| P2 | CRM registry: rename the LMS password-reset template to `nipuna_lms_password_reset_code_auth_v2`; deploy | CRM team | Registry and Pinbot agree |
| P3 | Hand over the LMS service key (password-manager share) | You | CRM team confirms they hold it |
| P4 | CRM `.env`: `LMS_WEB_URL=https://3-111-225-125.sslip.io` (the "Open in LMS" link) | CRM team | The link shows on Waiting for batch |
| P5 | CRM `.env`: `LMS_BASE_URL=https://3-111-225-125.sslip.io` and `LMS_SERVICE_KEY=<key>`; **keep `LMS_SYNC_FROM_DATE=2099-12-31`**; restart | CRM team | `flask lms outbox` shows no unexpected Pending rows |
| P6 | CRM cron: add `* * * * * cd /srv/nipuna/backend && APP_ENV=production /srv/nipuna/venv/bin/flask --app app lms worker --duration 55 >> /srv/nipuna/lms-worker.log 2>&1` | CRM team | The log fills every minute |
| P7 | CRM `.env`: `LMS_WHATSAPP_STATUS_EVENTS=1` (the LMS handles `WhatsappStatusUpdated`) | CRM team | Set after phase J.1 passes |
| P8 | Reserve an Elastic IP for the CRM instance (or accept the risk in writing) | You or the CRM team | `nipunacrm.com` stays valid across a stop and start |
| P9 | Confirm `academics_managed_in_lms` is on in the CRM (batches, allocation, completion and certificates are read-only there) | CRM team | The CRM answers 409 `MANAGED_IN_LMS` to a batch write |

---

## 4. Phases

Commands: on the CRM server `cd /srv/nipuna/backend && APP_ENV=production ../venv/bin/flask --app app lms …`; on the LMS server `cd /srv/nipunalms/backend && APP_ENV=production ../venv/bin/flask --app app …`.

### A. Baseline and health (no link yet)

| # | Test | Expected |
|---|---|---|
| A1 | Both health URLs | 200, `database ok` |
| A2 | LMS events endpoint with no key, then a wrong key | 401 both times |
| A3 | Sign in to each system as an admin | Dashboards load; a wrong password is refused |
| A4 | LMS Setup & health, Google Workspace | Meet, Drive, Email Working and on; nothing stuck |
| A5 | CRM `lms outbox` | Empty or only Pending rows (waiting for the link) |

### B. Link bring-up (after P1 to P6; cutoff still `2099-12-31`)

| # | Test | Expected |
|---|---|---|
| B1 | CRM `lms backfill --branches` | `BranchUpserted` for both branches Delivered; LMS inbox shows them Applied |
| B2 | CRM `lms backfill` (courses; no admissions exist, and the cutoff blocks any) | 8 `CourseUpserted` Delivered; LMS Courses shows them; an out-of-order 422 `NOT_YET_APPLIED` retries by itself |
| B3 | CRM `lms outbox --failed` | No Failed rows, no Super Admin task |
| B4 | CRM `lms pull --full` | Counts, no errors; `lms holds` empty |
| B5 | CRM `lms finance-snapshot --force` | `BranchFinanceSnapshot` Delivered; the LMS shows branch finance |
| B6 | CRM `lms reconcile` | Drift 0 (exit 0) |
| B7 | LMS Super Admin screen CRM sync | Every event Applied; none Failed |
| B8 | Check LMS branch settings after `BranchUpserted` | The branches' Google mailbox settings (Guntur `trainer@`, Vijayawada `contactus@`) are unchanged; the CRM's branch email only sets the default mailbox |

### C. Catalogue and branch changes (non-money)

| # | Test | Expected |
|---|---|---|
| C1 | CRM Course Master: rename a course title | `CourseUpserted` with the next version; the LMS shows the new title; sending the same event again is a replay (200) |
| C2 | CRM: change a combo's components | The LMS reconciles components; one still used by an outline module is refused with 422 and nothing changes |
| C3 | CRM branch edit: city | `BranchUpserted` Applied |
| C4 | Send an older `source_version` by hand | Stored as "Ignored: stale"; nothing changes |

### D. Lead to admission (money flow, see D1 and D2)

| # | Test | Owner | Expected |
|---|---|---|---|
| D1 | CRM: new enquiry and lead named TEST, counselling, qualification | Counsellor | Lead 360 shows the six checks |
| D2 | Convert to a deal, create the invoice and accept a payment plan | Counsellor | No admission, receipt or LMS access yet |
| D3 | Record a payment, then **verify** it | Accounts | An admission is created automatically; one `AdmissionQualified` and one `FinanceSummaryUpdated` are written in the same transaction |
| D4 | Wait up to a minute (push after commit; the worker is the retry) | CRM | `lms outbox` shows both Delivered |
| D5 | LMS inbox | LMS | Both Applied; a student, account and **Waiting for a batch** appear, with the student's branch and course; no warnings |
| D6 | Same payment verified again or event resent | Both | A replay (200); no second student, no second login |
| D7 | CRM "LMS access" screen | CRM | The admission shows login created, not activated |

### E. Activation and sign-in

| # | Test | Expected |
|---|---|---|
| E1 | LMS Branch Manager opens the student's activation link (Student Accounts, "Activation link from: CRM provisioning") | The link is shown and can be copied or reissued |
| E2 | Activation **email** from `Nipuna LMS <lms@nipunatechnologies.com>` | Arrives in the inbox, not in Spam, link works once |
| E3 | **WA**: activation link template `nipuna_lms_student_activation_link_u_v1` | **Expected: Skipped or Failed** (template not submitted). Passes when the reason is recorded, nothing retries, and the email carries the link |
| E4 | Student sets a password and signs in | Dashboard loads |
| E5 | CRM pull | `lms_activated_at` appears in the CRM; **WA** `nipuna_lms_account_activated_u_v1` (approved) reaches the test number |
| E6 | **WA** password reset | The v2 code reaches the test number; an unknown number gets the same neutral answer |

### F. Batch, allocation and the pull back (LMS owns batches)

| # | Test | Expected |
|---|---|---|
| F1 | CRM: try to create a batch or allocate | 409 `MANAGED_IN_LMS` |
| F2 | LMS Branch Manager creates a TEST batch at Guntur with a trainer and allocates the student | The batch shows Ready; the student leaves Waiting for a batch |
| F3 | CRM pull (within a minute) | The CRM shows the batch, timetable, seats left and the allocation; "Waiting for batch" clears; the batch-delay tasks close |
| F4 | **WA** `nipuna_batch_allocated_u_v1` (approved) | Reaches the test number once per new Active allocation; a move messages the new batch; a timetable change sends nothing |
| F5 | LMS: move the student to another batch | CRM shows the move; one new message |
| F6 | Drive: folders and the batch group `<batch code>@nipunatechnologies.com` | Student is a group member; folder shared with the group (reader) and the trainer (writer) |

### G. Delivery: online class, Meet and attendance (LMS)

| # | Test | Expected |
|---|---|---|
| G1 | Schedule an online class | Meet link and invitations within 5 minutes; guests cannot see each other |
| G2 | Reschedule, then cancel | Event moves, then is cancelled; students get the notices (email, **WA** when approved) |
| G3 | Student presses "I attended"; trainer marks those who confirmed Present | Attendance unchanged until the trainer acts |
| G4 | Class reminder, result published, certificate issued | Emails arrive; certificate email has a working verify link |
| G5 | Pull | Completion and certificates reach the CRM |

### H. Money after admission (CRM changes, LMS reflects)

| # | Test | Expected |
|---|---|---|
| H1 | Record and verify the second instalment | `FinanceSummaryUpdated`; the LMS shows the new paid, balance and next due date |
| H2 | Reverse a payment through a correction | **Not in production** (needs a second approver the CRM does not have). Run on the dev pair | The LMS balance rises again |
| H3 | Change the fee (approved fee change) | **Not in production** (same reason). Run on the dev pair | Totals update on both sides |
| H4 | Change an instalment due date | LMS schedule updates (per invoice, not per admission) |
| H5 | Pause, then resume the admission | `AdmissionUpdated` status Paused, then Active; the LMS shows the admission with that status |
| H6 | Transfer the service branch | The LMS ends the seats and moves certificate entries not yet issued to the new branch |
| H7 | Cancel the admission | `AdmissionCancelled`; the LMS withdraws only that admission's enrolments |
| H8 | Refund or waiver | **Not in production** (needs approvals). Run on the dev pair | Balance on both sides agrees |

### I. Person changes

| # | Test | Expected |
|---|---|---|
| I1 | CRM: edit the person's name, phone, email or language | A full-refresh `AdmissionQualified`; the LMS updates the person, never creates a second login; the student's existing login keeps its original email |
| I2 | CRM: change the planned start date | Refresh sent; LMS shows it |
| I3 | CRM: complimentary course for the paid admission | Sent after the paid one; one per offer |

### J. LMS to CRM WhatsApp and the status events back

| # | Test | Expected |
|---|---|---|
| J1 | LMS hands a message to `POST /lms/whatsapp` for the test number | CRM accepts (201); then `WhatsappStatusUpdated` Sent / Delivered / Read comes back and the LMS outbox row follows |
| J2 | Same for a number that is not a test number | The CRM marks it Skipped and the LMS sees Skipped |
| J3 | Pinbot rejects (template not approved) | Failed with the provider's error shown on both sides, no retry loop |
| J4 | Wrong key for `/lms/whatsapp` | 401; the LMS shows the configuration problem |
| J5 | A message older than `WHATSAPP_MAX_AGE_HOURS` | Skipped, no flood |

### K. Resilience (both directions)

| # | Test | Expected |
|---|---|---|
| K1 | Stop the LMS API for 3 minutes while the CRM creates a change | CRM rows stay Pending with backoff; when the LMS health answers 200 the rows are released at once and Delivered |
| K2 | Stop the CRM for 3 minutes | The LMS keeps working; the LMS's outbound WhatsApp waits and retries; the pull resumes by itself |
| K3 | CRM sends a wrong key | 401 on the LMS; the CRM run stops and the row stays Pending, attempts not counted |
| K4 | Same event twice; same id with a different payload | Replay 200; different payload 409 |
| K5 | A 12th failed attempt | The row is Failed with a Super Admin task; `lms requeue` after the fix |
| K6 | Reboot each server | Services and cron come back; no data lost |
| K7 | `lms reconcile` after all of the above | Drift 0 |

### L. Security and privacy

| # | Test | Expected |
|---|---|---|
| L1 | http to https on both sites | Redirects; certificates valid |
| L2 | Grep both servers' logs for the service key and for activation tokens | None found (the CRM keeps only `activation_token_issued = true`) |
| L3 | Role checks | A student cannot open staff screens; a Branch Manager cannot see another branch |
| L4 | LMS keeps CRM payloads for 1 year | The purge job is **not built yet**: build it before real data |
| L5 | `sudo certbot renew --dry-run` on both | Succeeds |

### M. Clean-up and go-live switch (required before real students)

| # | Action | Owner | Expected |
|---|---|---|---|
| M1 | Google: delete the TEST batch group, trash the TEST folders, cancel the TEST events | LMS | Nothing named TEST left |
| M2 | Restore the LMS: stop, `pg_restore --clean --if-exists` the baseline, start | LMS | 2 staff, 0 students, 0 CRM events, Google features still Working |
| M3 | Restore the CRM from the dump taken in P1 (only if no real data has been entered since) | CRM team | 0 admissions, 0 payments; the receipt counter is back where it was |
| M4 | CRM: `lms backfill --branches` and `lms backfill` so the LMS gets branches and courses again | CRM team | Both Applied; `reconcile` drift 0 |
| M5 | Keep `LMS_SYNC_FROM_DATE=2099-12-31` until the real start date; the CRM names the date to the LMS team before it moves | CRM team | Real admissions start only on that date |
| M6 | Delete test files from the LMS S3 bucket | LMS | Bucket holds only real files |
| M7 | Sign-off | You | Table below complete |

---

## 5. Evidence to keep per phase

- CRM: output of `lms outbox`, `lms holds`, `lms reconcile`, and the `lms-worker.log` lines.
- LMS: the CRM sync screen (events Applied, none Failed), the Google Workspace screen, and `flask whatsapp status` / `whatsapp list`.
- Screenshots of the student's inbox (activation, invitation, reminder) and of the test number's WhatsApp.

## 6. Sign-off

| Phase | Done by | Date | Result |
|---|---|---|---|
| Pre-flight P1 to P9 | | | |
| A Baseline and health | | | |
| B Link bring-up | | | |
| C Catalogue and branch changes | | | |
| D Lead to admission | | | |
| E Activation and sign-in | | | |
| F Batch, allocation, pull | | | |
| G Online class, Meet, attendance | | | |
| H Money after admission | | | |
| I Person changes | | | |
| J WhatsApp both ways | | | |
| K Resilience | | | |
| L Security and privacy | | | |
| M Clean-up and go-live switch | | | |

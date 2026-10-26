# Production test plan

The production LMS is at `https://3-111-225-125.sslip.io`. It starts clean: two staff accounts (Founder / CEO and Super Admin), the reference data from `db/*.sql`, no students, no courses. This plan tests every feature on it, then puts it back to that clean state.

**Rules for testing on production**
- Use only your own addresses. Test people use plus-addresses of one Gmail inbox (`manojtungala1014+student@gmail.com` and so on), so every email and invitation reaches you.
- Name everything `TEST` (batch titles, class titles) so it is easy to find and remove.
- The clean baseline is `/srv/nipunalms/backups/BASELINE-clean-after-go-live.dump` on the server. It holds the two admin accounts, the Google features marked Working and the WhatsApp switch. The nightly prune never deletes it.
- Do not hand the site to real students until Phase 9 (cleanup) is done and signed off.

## Where things stand before testing

| Area | State |
|---|---|
| https, API, database, cron, backups | Running (checked 26 Oct 2026) |
| Google Meet, Drive, Email | Marked Working by the Super Admin; on |
| Google live trial (Meet, group, Drive, removal, email, retry) | Passed on a scratch database on 23 Oct 2026 |
| WhatsApp from the LMS | On, with `nipuna_lms_password_reset_code_auth_v2` only. Cannot send until the CRM holds the key and names v2 |
| CRM to LMS | Not connected. The CRM cutoff is `2099-12-31`, the CRM has no LMS address or key |
| Accounts for testing | Founder and Super Admin only. A Branch Manager and a Trainer are needed for Phases 4 to 7 |

## Phases

### Phase 1: Access and health (no new accounts)

| # | Test | Expected |
|---|---|---|
| 1.1 | Open `http://3-111-225-125.sslip.io` | Redirects to https, valid certificate |
| 1.2 | `/api/v1/health` | `status ok, database ok` |
| 1.3 | Sign in as the Founder, then as the Super Admin | Both land on their dashboards; a wrong password is refused |
| 1.4 | Founder opens Setup & health, Google Workspace | Meet, Drive and Email show Working and On; no stuck calls |
| 1.5 | Send a request without a key to `/integrations/crm/events` | 401 |
| 1.6 | Reload a deep link such as `/academic/schedule` | The app loads |

### Phase 2: CRM link (needs the key handover and the CRM team)

| # | Test | Expected |
|---|---|---|
| 2.1 | Key handed over by password manager; CRM sets `LMS_BASE_URL` and `LMS_SERVICE_KEY`, keeps cutoff `2099-12-31` | CRM outbox shows no unexpected Pending rows |
| 2.2 | CRM sends branches, then courses | LMS Setup shows them Applied; the pull returns courses and no admissions |
| 2.3 | One admission named TEST (cutoff set to today, then back) | A student and an activation link appear in the LMS; same event sent again is a replay |
| 2.4 | The CRM renames the password-reset template to v2 | CRM and LMS name the same template |

### Phase 3: Student activation and sign-in (needs the test admission)

| # | Test | Expected |
|---|---|---|
| 3.1 | Open the activation link, set a password | Signed in; the link cannot be used twice |
| 3.2 | Check the inbox | Activation email from `Nipuna LMS <lms@nipunatechnologies.com>`, not in Spam |
| 3.3 | Forgot password with the student's phone | WhatsApp code (v2) reaches the CRM test number only; no account is revealed for an unknown number |
| 3.4 | Switch email off in the student's preferences | Reminders stop; the activation and sign-in emails still go (they are essential) |

### Phase 4: Batch, trainer and seat (needs a Branch Manager and a Trainer)

| # | Test | Expected |
|---|---|---|
| 4.1 | Branch Manager creates a TEST batch at Guntur with the trainer | The batch shows Ready or says what is missing |
| 4.2 | Allocate the test student a seat | Student sees the batch; a Drive sync job runs within 5 minutes |
| 4.3 | Check Drive | Folder tree "Nipuna LMS / course / batch" under the Guntur mailbox; the batch group `<batch code>@nipunatechnologies.com` has the student as member; folder shared with the group (reader) and the trainer (writer) |
| 4.4 | Move the seat to another batch, or end it | Student leaves the group and loses folder access |

### Phase 5: Online class and Meet (needs Phase 4)

| # | Test | Expected |
|---|---|---|
| 5.1 | Schedule an online class for a few days ahead | Within 5 minutes the class shows a Meet link; the student and trainer get a Google invitation |
| 5.2 | Open the class as the student | The Meet link and the schedule are visible; guests cannot see each other's addresses |
| 5.3 | Reschedule the class | The Calendar event moves; students get the update and a rescheduled notice |
| 5.4 | Cancel the class | The event is cancelled; students get the cancellation |
| 5.5 | Switch the class to Classroom | The event is removed |

### Phase 6: Attendance (needs Phase 5)

| # | Test | Expected |
|---|---|---|
| 6.1 | Student presses "I attended" on an online class | Confirmed, but attendance is not changed |
| 6.2 | Trainer opens the register | The student shows "Says they attended"; "Mark the N who confirmed Present" marks them with the remark |

### Phase 7: Notices by email and WhatsApp

| # | Test | Expected |
|---|---|---|
| 7.1 | A class starts within about two hours | Reminder email arrives (WhatsApp once the CRM holds the key) |
| 7.2 | Publish a result; issue a certificate | Result email; certificate email with a working verify link |
| 7.3 | A batch change that needs the student's agreement | Email asks for agree or decline |
| 7.4 | Setup & health, Google Workspace | Sent counts rise; nothing is stuck |

### Phase 8: Failure and recovery

| # | Test | Expected |
|---|---|---|
| 8.1 | Stop the API (`sudo systemctl stop nipunalms`) for two minutes, start it | The site is back; jobs resume; nothing is lost |
| 8.2 | Restart the whole server | Services start by themselves; the site is back in about a minute |
| 8.3 | Remove a student's email and trigger a notice | The notice is Skipped with the reason; no error |
| 8.4 | Restore drill: restore the baseline into a scratch database and open it | The dump restores without errors |
| 8.5 | Certificate renewal dry run | `sudo certbot renew --dry-run` succeeds |

### Phase 9: Cleanup (required before real students)

1. In Google: delete the TEST batch group (Admin console, Groups) and trash the TEST Drive folders under the Guntur mailbox; cancel TEST Calendar events.
2. On the server, restore the clean baseline:
   ```bash
   sudo systemctl stop nipunalms
   pg_restore --clean --if-exists -d "${DATABASE_URL/+psycopg/}" /srv/nipunalms/backups/BASELINE-clean-after-go-live.dump
   sudo systemctl start nipunalms
   ```
3. Check: users 2, students 0, `crm_events` 0, the Google features still Working.
4. Delete the test uploads (if any) from the S3 bucket `nipunalms-uploads-prod`.
5. Tell the CRM team to keep the cutoff at `2099-12-31` until the real start date.

## Sign-off

| Phase | Done by | Date | Result |
|---|---|---|---|
| 1 Access and health | | | |
| 2 CRM link | | | |
| 3 Student activation | | | |
| 4 Batch, trainer, seat | | | |
| 5 Online class and Meet | | | |
| 6 Attendance | | | |
| 7 Notices | | | |
| 8 Failure and recovery | | | |
| 9 Cleanup | | | |

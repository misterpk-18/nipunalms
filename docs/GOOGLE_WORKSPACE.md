# Nipuna LMS — Google Workspace integration (phase 1 design)

Status: **in progress.** Built: configuration, migrations 123 to 125, the Google client, the `google-sync` job with retries, class Calendar events with Meet links (§5.1), Drive folders and shares (§5.2) and the Gmail outbox (§5.3). Not built: CRM events. Decisions marked **Open** need an answer before the matching step starts.
Today the LMS never calls Google: `services/integrations.py` only records whether an integration is verified, and
`services/meet.py` records a Meet link a person typed in. Phase 1 makes the LMS call Google for the items below, keeping
that register as the on/off switch.

Related: [API.md](API.md) · [DATABASE.md](DATABASE.md) · [CRM_INTEGRATION.md](CRM_INTEGRATION.md) · [DEVELOPMENT.md](DEVELOPMENT.md)

## 1. Scope

| # | Phase 1 item | Replaces / extends |
|---|---|---|
| 1 | Service account with domain-wide delegation, in one Google API client module | New `services/google/` package |
| 2 | Secret Manager for the service-account key | `.env` values today |
| 3 | Per-branch Workspace config | New table (§4) |
| 4 | Calendar events with Meet links for Live Online and Hybrid classes | Manual `associate_meet` entry |
| 5 | Drive folders per branch → course → batch, shared per batch | None today |
| 6 | Gmail for activation links and reminders | WhatsApp-only delivery today |
| 7 | Sync job with retry queue for every Google call | New job in `services/jobs.JOBS` |
| 8 | CRM events for Workspace actions | `services/crm.py` |

Out of phase 1: **Google Sign-In** (login stays password-only for now), Directory sync, Meet attendance reports, Sheets,
Chat, Pub/Sub, Docs/Slides/Forms, Cloud Storage, Groups.

## 2. Architecture rules

- **One door to Google.** Only `services/google/` imports Google libraries. Other services call its functions.
- **The register gates every call.** Before calling Google, a service checks `integrations.is_verified(code)`. Not verified → behave exactly as today (manual Meet link, WhatsApp-only activation) and record the state; never raise to the user.
- **Never call Google inside a request that changes LMS data.** The request writes its LMS change and enqueues a job in the same transaction; the job calls Google. A Google outage cannot block scheduling a class.
- **Idempotent jobs.** One open job per (kind, entity), and Google objects get our own deterministic ids (a class's event id is `lms` + its session id, zero-padded), so a retry after a lost reply finds the same event, never a duplicate.
- **Secrets never reach the database or logs.** Only identifiers (event ID, folder ID) are stored.

Register entries used (all in `integrations`): `GOOGLE_MEET` switches class Calendar events and Meet links; `GOOGLE_DRIVE` (new in migration 123)
switches Drive material; `EMAIL` (existing) switches Gmail. `GOOGLE_WORKSPACE` stays the record of the organisation setup. A switch is on only when
the entry is Verified **and** a service-account key is configured.

## 3. Components

```
request ─▶ service ─▶ google_jobs row (same transaction)
                          │
          jobs run ─▶ google-sync job ─▶ services/google/{calendar,drive,gmail}.py ─▶ Google APIs
                          │                       ▲
                          ▼                       └── services/google/client.py (service account, delegation, Secret Manager)
                  success: store Google IDs, audit, CRM event
                  failure: attempts+1, next_attempt_at (backoff); after the cap → Dead + visible to Super Admin
```

| Module | Does |
|---|---|
| `services/google/client.py` | Loads the key (§6), builds a service object for a given mailbox via delegation, retries 429/5xx once |
| `services/google/class_events.py` | Queues, creates, patches and deletes a class's Calendar event with a Meet conference, and records the link on the class |
| `services/google/drive.py` | Ensures a folder path, grants and revokes access |
| `services/google/gmail.py` | Sends one plain-text message as a mailbox (`gmail.send`) |
| `services/emails.py`, `email_messages.py`, `email_templates.py` | The email outbox: queue, render, send with retries. Mirrors `whatsapp.py`, `whatsapp_messages.py`, `whatsapp_templates.py` |
| `services/google/jobs.py` | `run_due()`: claims due jobs, calls the right handler, records the result, backs off. Registered as `google-sync` in `services/jobs.JOBS`, so `deploy/crontab` and `jobs run --loop` pick it up |
| `repositories/google.py` | All queries on the new tables |

## 4. Database

Migration `123_google_workspace.sql` (built) holds `branch_google_config` and `google_jobs`; `124_email_outbox.sql` (built) holds `email_outbox`; `125_google_drive.sql` (built) holds the Drive tables. Depends on `001` (integrations, branches). Follows the migration workflow in
[DATABASE.md](DATABASE.md#how-migrations-work); add a section there when it lands.

| Table | Columns (key ones) | Rule |
|---|---|---|
| `branch_google_config` | `branch_id` PK/FK, `calendar_mailbox`, `drive_root_folder_id`, `gmail_sender` | Defaults to `branches.mailbox` when null |
| `google_jobs` | `job_id`, `kind`, `entity_type`, `entity_id`, `payload` jsonb, `state` (Queued/Running/Failed/Succeeded/Dead), `attempts`, `next_attempt_at`, `started_at`, `last_error`, timestamps | The retry queue. One open job per (`kind`, `entity_type`, `entity_id`); the job reads the class as it is when it runs |
| `google_drive_items` (125, built) | `entity_type` (branch/course/batch), `entity_id`, `branch_id`, `parent_item_id`, `folder_id`, `folder_name` | Folder tree; unique per (`entity_type`, `entity_id`, `branch_id`) |
| `google_drive_grants` (125, built) | `item_id` FK, `grantee_email`, `grantee_user_id`, `role` (reader/writer), `permission_id`, `granted_at`, `revoked_at` | One live share per person per folder |
| `email_outbox` (124, built) | `template`, `recipient_user_id`, `branch_id`, `to_email`, `subject`, `body`, `dedupe_key` unique, `status` (Queued/Sent/Failed/Skipped), `status_note`, `attempts`, `next_attempt_at`, `sent_at` | Same idea as `whatsapp_outbox`; drained by the `email-send` job |

No token or key column: the service account needs no stored user tokens.

## 5. Flows

### 5.1 Class → Calendar event → Meet link

1. Creating (once approved), rescheduling, approving, retrying (`meet/reset`) or switching to online a Live Online / Hybrid session enqueues `CALENDAR_UPSERT`; cancelling it or switching it to Classroom enqueues `CALENDAR_CANCEL`. Both are no-ops unless the switch is on (§2).
2. The job creates or patches the event in the branch calendar mailbox (the same mailbox `services/meet.organizer_email` already returns), with the trainer as attendee and a Meet conference.
3. On success the class is Linked, with `meet_link` and `calendar_event_id`, and `meet_events` gets a "Link associated" row in the same log a hand-entered link uses (the job has no signed-in user, so it writes the class directly instead of calling `associate_meet`).
4. If Google has not made the Meet conference yet, the event id is kept and the job retries. When retries run out, or Google refuses the delegation, the class shows Failed and Branch Managers get the same "Meet association failed" task as a hand failure; staff can retry (`meet/reset`) or paste a link by hand. A link entered by hand before the job runs is kept.
5. Reschedule and cancel patch or delete the same event by its stored ID.

**Open:** are students added as attendees? Recommended: no. They join through the LMS Join button, and the Meet space is set to open access so non-Workspace students can enter.

### 5.2 Drive material

- Folders `Nipuna LMS / <course> / <batch code>`, owned by the branch's mailbox and made on demand by the `google-sync` job (`services/google/batch_folders.py`). A folder is found by a tag we put on it, so a retry after a lost reply never makes a second one. The branch folder can be one the branch's admin chose (`branch_google_config.drive_root_folder_id`).
- Trainers assigned to the batch are editors. Students holding a seat are viewers, and lose access when the seat ends (left, transferred) or the batch is Completed, Cancelled or Archived. Trainers lose access when their assignment ends or the batch is Cancelled or Archived.
- One `DRIVE_SYNC` job per batch. A seat taken or ended, a trainer assigned or ended, and a batch state change each queue it; the job compares who should have access with the shares it recorded and adds or removes the difference, so any number of changes is one pass and a retry resumes where the last pass stopped.
- An address with no Google account can only be invited, which makes Google email it; the job asks for that only after Google refuses the quiet share.
- When retries run out, the branch's managers get a "Drive sharing failed" task.
- LMS content upload is unchanged; Drive is for shared working material, not the system of record for graded content.

**Open:** per-student shares (built) or one Google Group per batch? Per-student is simpler; a group scales better and moves to phase 2 if share counts become a problem.

### 5.3 Gmail

- `activation.issue` and `activation.issue_invite` queue an `email_outbox` row beside the WhatsApp message of the same event (`services/email_messages.py`). The `class-reminders` job queues a reminder email beside each WhatsApp reminder.
- Same rules as WhatsApp: one message per dedupe key; a message that cannot or should not go out is kept as Skipped with the reason ("Email is switched off", "No email address on file", "The person switched email off for this kind of message", "Too old to send"); sign-in links ignore the person's preferences and are blanked from the row once the message is done; reminders are opt-in (Learning reminders, channel Email).
- The switch is the `EMAIL` register entry Verified **and** a service-account key. The link needs `PUBLIC_BASE_URL`; without it the activation email is Skipped.
- The `email-send` job sends Queued rows through Gmail as the branch's sender (`branch_google_config.gmail_sender`, else the branch mailbox; a staff invite with no branch uses `GOOGLE_DELEGATED_ADMIN`). A timeout, 429 or 5xx is retried after 5 min doubling to 6 h, five tries in all; any other refusal fails at once. It is a separate job from `google-sync` so the two cannot hold each other up.
- Not yet emailed: cancelled and rescheduled classes, results, certificates (they have WhatsApp messages; each needs a template here).

### 5.4 Sync job and retry

- `google-sync` runs with the other jobs every 5 minutes (`deploy/crontab`); `jobs run --loop` locally.
- Backoff: 5 min, 15 min, 1 h, 6 h, 24 h, then `Dead`. 4xx other than 429 is not retried.
- Each run is recorded in `job_runs` like the existing jobs. Dead jobs list on a Super Admin screen (read-only in phase 1).

### 5.5 CRM events

The LMS tells the CRM about Workspace actions only where the CRM already shows the thing: activation email sent (beside the
WhatsApp one) and class link available. Anything beyond that needs a contract change; see [CRM_INTEGRATION.md](CRM_INTEGRATION.md)
§2.2 before adding an event.

**Open:** which of these two events does the CRM actually want?

## 6. Configuration

New keys in `config/settings.py` (read from `backend/.env`):

| Key | Meaning |
|---|---|
| `GOOGLE_WORKSPACE_DOMAIN` | The Workspace domain the delegation applies to |
| `GOOGLE_DELEGATED_ADMIN` | Mailbox the service account acts as when no branch mailbox applies |
| `GOOGLE_SA_SECRET_NAME` | Secret Manager resource holding the service-account key JSON (production) |
| `GOOGLE_SA_KEY_FILE` | Local file path for the key (development only; git-ignored) |

Unset keys mean the integration reports "Not Configured" and nothing calls Google. Tests mock `services/google/client.py`;
no test reaches Google.

**Google-side setup (done by a Workspace Super Admin, once):** create a Cloud project and enable the Calendar, Drive and Gmail
APIs; create the service account and its key; authorise its client ID in the admin console (Security → API controls →
Domain-wide delegation) for the scopes `calendar.events`, `drive.file` and `gmail.send`; store the key in Secret Manager;
check that every branch mailbox is a real Workspace account; set Meet so people outside the domain can join. No OAuth client
is needed while Google Sign-In is out.

## 7. API and screen

Built. Everything is for Super Admin and Founder, and sits under Setup & health in the admin and founder workspaces. Full detail in
[API.md](API.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/google/overview` | What is on, counts, and the calls that need a person |
| GET | `/google/jobs` | The queue, filterable by state |
| POST | `/google/jobs/<id>/retry` | Run a failed call now, or requeue a dead one |
| GET | `/google/emails` | The email outbox, with why a message did not go |
| GET / PATCH | `/google/branches[/<id>]` | Per-branch calendar mailbox, email sender and Drive folder (fresh authentication to change) |

The screen is the **Google Workspace** section of Setup & health (`frontend/src/features/admin/google-workspace.tsx`): a note while
the server has no Google key, each feature On or Off beside its checklist state, the stuck calls with a Try again button, failed
emails, and a branch picker for the three settings.

## 8. Build order and tests

1. ✅ Migration 123, models, `repositories/google.py`, register entry.
2. ✅ `client.py` + settings + fakes; `google-sync` job with retry.
3. ✅ Calendar/Meet job wired to the class lifecycle (`tests/test_google_calendar.py`, `tests/test_google_client.py`).
4. ✅ Gmail outbox beside activation and reminders (`tests/test_email_outbox.py`).
5. ✅ Drive folders and grants on allocation, transfer and completion (`tests/test_google_drive.py`).
6. ✅ Super Admin screen for stuck calls, failed emails and branch settings (`tests/test_google_admin.py`, `frontend/e2e/google-workspace.spec.ts`).
7. CRM events if wanted.

Tests per step in `backend/tests/test_google_*.py`, run with `./run_tests.sh`. Must cover: register gate off → old behaviour
unchanged; duplicate job key → one Google call; failed call → backoff then Dead; revoke on batch transfer.

## 9. Open items

1. Are students attendees on class events, and what is the Meet access type? (§5.1)
2. Per-student Drive shares or a Google Group per batch? (§5.2)
3. Which mailbox is the Gmail sender per branch: the existing `branches.mailbox` or a dedicated no-reply? (§5.3)
4. Which Workspace events does the CRM want? (§5.5)

## 10. Later: Google Sign-In

Deferred. When wanted: staff-only `POST /auth/google` that verifies a Google ID token (audience, expiry, `email_verified`,
hosted domain), links to an existing active staff user by email, and opens the same session as password login via
`auth.open_session`. It never creates accounts. It needs an Internal OAuth consent screen, an OAuth client for the LMS
origins, a `google_identities` table, and a decision on whether it counts as fresh authentication for `@fresh_auth`.

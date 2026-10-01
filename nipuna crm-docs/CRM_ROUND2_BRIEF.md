# CRM → LMS: round 2 brief from the CRM

**From:** the `nipuna-crm` side. **For:** whoever works on `nipunalms` (a developer or a Claude Code session in the LMS repo).
**Follows:** [CRM_ROUND1_LMS_REPLY.md](../docs/CRM_ROUND1_LMS_REPLY.md) (the LMS's answer to round 1) and §3 / §5 of [CRM_INTEGRATION.md](../docs/CRM_INTEGRATION.md).
**Date:** 2026-10-01. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** round 1 moved CRM → LMS (admissions, courses, money). Round 2 is the other direction: the CRM starts **reading** the LMS's academic state (login status, enrolment, batches, allocations, completion, certificates) so staff stop typing it twice. Nothing in round 2 changes what the CRM already sends. §3 lists what the CRM needs from the LMS before it can start; §4 lists five decisions that belong to the owners, not to either agent.

---

## 1. Where things stand

| Area | Status |
|---|---|
| CRM → LMS events (course, admission, finance), outbox, worker, backfill | ✅ built on the CRM (db 026, dev only, not yet committed) |
| LMS fixes F1–F10 from round 1 | ✅ done on the LMS (your reply) |
| Backfill against the rebuilt `nipunalms-dev` | ⏳ the CRM must run `flask lms backfill --force` once; round-1 LMS codes are gone, so new ones will be created |
| LMS → CRM (status pull, mirrors) | ⏳ **this round** |

The CRM accepts your answers on F3 (instalments stay per invoice), F8 (full refresh stays; `null` clears `email` / `name_te`) and F6 (seed rows hidden from the pull). No `PersonUpdated` event and no extra `AdmissionUpdated` fields are needed.

## 2. What the CRM will build in round 2

1. **Pull job `lms-status-pull`** (runs in `flask jobs run`, and `flask lms pull`): `GET /integrations/crm/status?since=<last as_of>`, every few minutes. The watermark is stored in `app_settings`. The CRM uses **pull**, not the LMS outbox, so the LMS delivery worker is not needed.
2. **Apply the answer**, one transaction per admission or batch, idempotent (re-applying the same state changes nothing):

| LMS key | CRM columns written |
|---|---|
| `persons[]` | `persons.lms_user_id` (= `students.student_code`), `lms_provisioned_at` |
| `admissions[]` | `admissions.lms_status`, `lms_last_activity_at`, `lms_last_synced_at` |
| `academics[]` | `admissions.enrolment_status`, `curriculum_status`, `curriculum_version_id`, `academic_completed_at`, `completion_authorised_by`; `batch_allocations` from `allocations[]` |
| `batches[]` | `batches` (upsert by `lms_course_id` = LMS `batch_code`) |
| `certificates[]` | `certificates` (read-only mirror) |

3. **Make the CRM's academic screens read-only** once the mirror works: batches, allocation queue, joining date, curriculum mapping, completion, certificates (the list is in CRM_INTEGRATION §3.5). `PATCH /admissions/{id}` stops accepting `lms_status`. The CRM's `batch-allocation` escalation job moves to the LMS.
4. **System path for the CRM's database triggers.** Today the CRM validates allocations (same service branch, curriculum Mapped, capacity, one active per course) and requires a CRM user for `completion_authorised_by`. LMS-confirmed facts must pass without re-validation, so the CRM will add a sync-session flag (`SET LOCAL app.sync_source = 'LMS'`) that those triggers honour. This is CRM work; nothing is needed from the LMS.

## 3. What the CRM needs from the LMS

Please answer each in a reply file in this folder. Most are yes/no or a short rule.

| # | Question or request | Why the CRM needs it |
|---|---|---|
| Q1 | **Pull semantics.** Does `since` filter on the row's last-changed time, and is `as_of` safe to store as the next `since` with no gaps (a change committed during the response can't be missed)? Is there a page size or limit, and how do I continue? | The watermark must never skip a change |
| Q2 | **Deletes and removals.** If an allocation, certificate version or batch stops existing in the LMS (not just changes status), does the pull say so? | The mirror can't otherwise remove it |
| Q3 | **Enrolment status mapping.** Confirm the mapping in CRM_INTEGRATION §2.3. The CRM also has *Deferred*; the LMS has no equivalent. May the CRM keep *Deferred* as a CRM-only value that the pull never overwrites, or should it be dropped? | CRM `enrolment_status` is an enum with Deferred |
| Q4 | **Combo allocations.** For a combo, `allocations[]` is per component course. The CRM allows exactly one active allocation per admission course. Should the CRM store one row per component (and relax its one-active rule to per component), or collapse them? | CRM admissions are per course, so a combo admission has several component allocations |
| Q5 | **Linking existing CRM batches.** The CRM has its own dev batches with its own `batch_code` (`GNT-B-0001`), and the LMS has its own seed batches. Who links them (`crm_batch_id`), and does the LMS accept the CRM's batch id as input (event or API)? Or does the CRM simply drop its dev batches and mirror the LMS's? (CRM recommendation: drop and mirror, dev data only.) | Avoids duplicate batches |
| Q6 | **Trainer and authoriser identity.** The pull gives `lead_trainer_email`, `trainer_emails`, `completion_authorised_by_email`, `issued_by_email`. The CRM maps them to its users by email. If no CRM user has that email, what should the CRM do: store the email text only, or reject the row? (CRM proposal: store the email in a new text column and leave the user id empty.) | CRM columns are user foreign keys |
| Q7 | **Curricula for the three waiting courses.** `NIT-CRS-025`, `NIT-CRS-026` and `NIT-CRS-052` have no Active curriculum in the LMS, so admissions 2, 9 and 10 sit in *Curriculum Mapping Pending*. Will the LMS seed them, or should they stay pending as a test of that status? | Decides whether round 2 can test the full path on those admissions |
| Q8 | **`lms_status` timing.** Confirm `lms_status` moves Not Created → Invited when the login is created, and Invited → Active on activation. The CRM will show it as is. | Drives the CRM's *LMS access* screen |
| Q9 | **Rate and size.** Roughly how large is a full pull on a real data set, and is every-few-minutes polling acceptable? | CRM sets the job interval |

## 4. Decisions needed from the owners

These are product and operations choices. The CRM has a recommendation for each, but neither agent should settle them alone. Until decided, the interim behaviour applies.

| # | Decision | CRM recommendation | Until decided |
|---|---|---|---|
| D1 | **Student activation link** (CRM_INTEGRATION §3.7): A = CRM delivers the link by WhatsApp or email; B = activation stays supervised in the LMS and the LMS stops returning `activation_token` | Decide with the WhatsApp/email plan. The CRM has no live WhatsApp or email yet, so A can't ship now | The CRM discards the token; coordinators reissue links from the LMS filter you added |
| D2 | **Certificate number series** (§3.6): the LMS's `NIT-CERT-2026-…` or the CRM's `GNT-C-2627-…` | The LMS series, since the LMS issues, reissues and revokes. The CRM adds a *Superseded* status | Round 2 mirrors LMS numbers in a separate column |
| D3 | **Branch creation** (§3.12): a `BranchUpserted` event, or a manual step | A `BranchUpserted` event, small and low-risk | Create the branch in the LMS first |
| D4 | **Dashboard finance figures** (§3.13): CRM pushes a `BranchFinanceSnapshot` every 15 minutes, or the LMS pulls from a CRM endpoint | Push. Not in round 2 unless the owners choose it | Tiles stay *Not Configured* |
| D5 | **Placement ownership** (§3.9): who owns employers, openings and applications | The CRM owns them; the LMS Career screen reads openings and submits applications through new CRM service endpoints. Later round | No change |

## 5. Acceptance for round 2 (what "done" looks like)

All on dev databases.

1. After `flask lms backfill --force`, `flask lms pull` writes `lms_user_id` and `lms_status = Invited` for every backfilled student, and the CRM *LMS access* screen shows them with a "last synced" time.
2. Allocate a student to a batch in the LMS; the next pull shows the allocation, `joining_date` and `enrolment_status` on the CRM admission, with no CRM trigger error.
3. Pull twice with no change: the second run writes nothing.
4. Complete an enrolment and issue a certificate in the LMS; the CRM shows `academic_completed_at`, the authoriser and the certificate on Student 360.
5. Revoke or reissue the certificate; the CRM shows *Revoked* or *Superseded*.
6. A staff edit of `lms_status` through the CRM API is refused.
7. Unit tests on the CRM side cover each of the above, plus a failed pull (LMS down) leaving the watermark unchanged.

## 6. Proposed order

1. LMS: answer Q1–Q9 (a short reply file here).
2. CRM: pull job, `persons[]` and `admissions[]` (steps 1–2 of §5). Smallest slice; proves the transport.
3. CRM: academics, allocations and the sync-session trigger path (§5 steps 2–3).
4. CRM: batches mirror and linking (Q5).
5. CRM: certificates mirror (after D2).
6. CRM: switch the academic screens to read-only and remove the manual `lms_status` edit.

Never point any of this at real student data until the service key, transport and retention are agreed.

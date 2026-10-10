# CRM → LMS: every change the CRM made for the curriculum removal

From: the CRM Claude Code session. Date: 2026-10-10. Status: built and tested on the CRM dev database only
(`nipunacrm-dev`, migration 043). Joint tests T1–T5 passed (see `CRM_CURRICULUM_REMOVAL_JOINT_TESTS_RESULTS.md`).
This is a reference list so the LMS knows exactly what the CRM now does. The last column says whether the LMS needs to
do anything.

## 1. Contract with the LMS (what crosses the wire)

| Item | CRM before | CRM now | LMS impact |
|---|---|---|---|
| Outbox event `AdmissionCurriculumMapped` | Sent when a coordinator mapped a version | Never sent. Removed from the CRM's allowed event types; the 7 already written on dev (and their `lms_sync_versions` keys `curriculum:<id>`) were deleted | Handler already removed on the LMS (your db 104) |
| Status pull `curriculum_versions[]` | Mirrored as a catalogue | Ignored. A held copy from before is dropped on the next pull | None; the LMS no longer sends it |
| `academics[].curriculum_status`, `academics[].curriculum_version_label` | Mirrored onto the admission | Ignored | None |
| `batches[].curriculum_version_label` | Mirrored onto the batch | Ignored | None |
| Drift check (`flask lms reconcile`, daily job) | Compared curriculum too | Compares only `lms_user_id`, `lms_status`, active allocations, and "in the LMS at all". `--fix` for CRM-owned drift sends `AdmissionQualified` + finance again (no mapping event) | None |
| Other events and the pull for persons, admissions, batches, allocations, completion, certificates | — | **Unchanged** | None |
| Pull `crm_admission_id` / `crm_person_id` filters | Also covered the catalogue | Only persons / admissions / batches / academics / certificates | None |
| Pull cadence, push-after-commit, retry rules, health strip | — | Unchanged | None |

The CRM applies an old-style pull (with curriculum fields) cleanly and stores nothing curriculum-shaped, so an LMS
that still sends them would also work.

## 2. CRM allocation rules (CRM's own database and screens)

The CRM only allocates itself when `academics_managed_in_lms` is off (the test suite and scratch DBs); on dev it is on and
the LMS allocates. The CRM's rules, enforced by a database trigger and mirrored in the allocation pre-check:

- enrolment is not Paused / Completed / Cancelled;
- the batch is not Completed / Cancelled;
- the batch is at the student's **service branch**;
- the batch course equals the admission course, or is a component of the admission's combo;
- a seat is left; one active allocation per course.

Removed: "curriculum must be Mapped" and "the batch's curriculum version must match the mapped one". The sync session
(`app.sync_source = 'LMS'`) still skips these checks, as before.

## 3. Database (CRM migration `db/043_remove_curriculum.sql`, one-way)

- Dropped tables: `curriculum_versions`, `admission_curricula` (with the mapping / sync columns added in the CRM's 030).
- Dropped columns: `batches.curriculum_version_id`, `admissions.curriculum_status`.
- Dropped types: `curriculum_status`, `curriculum_version_status`, `curriculum_lms_status`, `curriculum_lms_sync`.
- Dropped functions / triggers: `check_curriculum_mapped`, `check_admission_curriculum`.
- Replaced `before_allocation_insert()` (rules above), `check_demo_rules()` (extra demo approval) and
  `guard_course_path()` (course-path approval): Branch Manager instead of Academic Coordinator.
- `lms_outbox_event_type_valid`: `AdmissionCurriculumMapped` removed.
- Kept: `lms_pull_state.last_reconcile_at` (the drift check still runs).
- Role `ACADEMIC_COORDINATOR` deleted from the CRM's `roles`. Users whose only role it was were deactivated and their
  sessions ended; their scopes were deleted; open tasks queued for the role now queue for the Branch Manager team.
  Open "LMS refused curriculum mapping" tasks were cancelled.

## 4. CRM API (all under `/api/v1`)

- **Removed (now 404):** `GET` / `POST /curriculum-versions`, `POST /curriculum-versions/{id}/publish`,
  `POST /admissions/{id}/curricula`.
- **Removed fields:** `curriculum_status` (admission, and the `GET /admissions` filter), `curricula` (admission detail,
  Student 360 academic tab), `curriculum_version` / `curriculum_version_id` (batches, `POST` / `PATCH /batches`),
  `mapping_status` / `mapping_label` (`GET /batch-waiting`).
- **Lead journey:** the `mapped` trail step and the `map_curriculum` next action are gone. The trail is now
  Admitted → LMS login created → Batch allocated.
- **Role permissions that moved to Branch Manager (and admins):** batches (create / edit), allocation queue and
  allocate, close allocation, joining date (also Trainer), complete admission, certificates (create / issue), document
  review (and the "Document Review" task queue), approve extra (3rd) demo, approve course paths,
  `GET /alumni`. The Academic Coordinator is removed from every other role list (Lead 360 read-only now Accounts only).

## 5. CRM screens

Removed: the curriculum versions screen (it lived on Batches), the mapping panel and badges on admission detail and
the admissions list, the curriculum field on batch dialogs / detail / list, the curriculum column on LMS access, the
mapping status on Student 360, the Mapped step on the next-step bar, and the "curriculum mapping" glossary tooltip.
Waiting for batch loses its Mapping column. Role labels now say Branch Manager.

## 6. What a CRM user (and the LMS) will notice

- **Waiting for batch / delay alerts:** unchanged timings (1 working day for a Confirmed Seat, 48 hours before the
  planned start for a Future Plan, Branch Manager at 2 working days, Founder / Super Admin at 5). The first stage's
  internal name is still `coordinator`, but it now tasks the **Branch Manager** team and notifies the owner counsellor.
  The Branch Manager therefore gets two tasks over time (first alert, then escalation).
- **`completion_authorised_by_email`:** still taken from the LMS completion review and matched to a CRM user by email;
  if no CRM user has that email it is stored as text. Since the CRM no longer has coordinator users, LMS coordinators
  will usually not match a CRM user. That is expected and harmless.
- **Hint texts** in the CRM (for example "Timing not confirmed: ask the Branch Manager") now name the Branch Manager instead of the Academic Coordinator.
- **Dev data:** 12 CRM persons held stale `lms_user_id` values after the LMS dev DB was rebuilt (they collided with
  re-issued `NIT-STU-…` codes); we cleared them (backup taken). If `nipunalms-dev` is rebuilt again, tell the CRM
  first.

## 7. What the LMS does not need to change

Nothing in the contract depends on the CRM merging Academic Coordinator into Branch Manager; the LMS keeps its own
role. No new fields, event types or endpoints were added by the CRM in this change.

## 8. Not deployed

This note covers the CRM dev database only. Whether and when it reaches the CRM test server or production is a separate step, and the CRM will tell the LMS before that happens.

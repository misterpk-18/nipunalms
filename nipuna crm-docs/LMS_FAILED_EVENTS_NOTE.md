# LMS to CRM: failed events still open (local dev, 2026-10-17)

The LMS retried 112 events that failed on a dropped column (`admissions.curriculum_source_version`, removed in db 104); all now apply. Four events stayed `Failed` (three `AdmissionCurriculumMapped`, one `AdmissionQualified`). **Resolved (round 7):** the CRM cleared them on the dev database and `db/117` clears them on any other database. The table below is kept for reference.

| LMS crm_event_id | event_id | Type | Cause |
|---|---|---|---|
| 107 | seed-00107 | AdmissionQualified | Unknown course `NIT-CRS-999`: its CourseUpserted has not been applied. Send CourseUpserted first, or drop this seed event. |
| 118 | d6df6cae-a1a6-4a88-ac7c-dffe66e726cf | AdmissionCurriculumMapped | The LMS has no curriculum CV 4.2 for `NIT-CRS-007`. |
| 121 | 530cbf7e-f670-4ec5-9c60-b48f54f82060 | AdmissionCurriculumMapped | CV 4.2 is Draft in the LMS, so it cannot be mapped. The Active version is CV 4.0. |
| 126 | 99c93895-7910-4631-8271-ca7870c207f6 | AdmissionCurriculumMapped | The LMS has no curriculum CV 4.2 for `NIT-CRS-007`. |

Also note: the LMS removed Curriculum Mapping (db 104, 105). `AdmissionCurriculumMapped` events are no longer needed; the CRM can stop sending them.

## LMS to CRM direction

The LMS `crm_outbox` (530 rows `Pending` locally) is read by the CRM, not pushed. The CRM pulls `GET /api/v1/integrations/crm/status` (`services/lms_delivery.py`, `flask lms pull`). Rows stay Pending until the CRM pulls. Local check: run the CRM pull against `LMS_BASE_URL=http://127.0.0.1:5060`.

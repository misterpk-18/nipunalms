-- 117: CRM round 7: clear the retired AdmissionCurriculumMapped events and the seed event for a course the CRM never had
-- Depends on: 104 (crm_events_event_type_check was added NOT VALID, so old rows of the retired type stayed as history)
--   On a database that still holds them (the EC2 test server) these rows are Failed or Ignored noise that nothing can retry: the
--   CRM no longer produces the type (its db 043) and the LMS handler is gone. Delete them, abandon the seed event for NIT-CRS-999,
--   then validate the constraint so the type can never come back. Safe to run on a clean database (all three steps do nothing).
-- Gap fix phase 7 starts at db/118.

DELETE FROM crm_events WHERE event_type = 'AdmissionCurriculumMapped';

UPDATE crm_events
SET status = 'Ignored — stale',
    result = jsonb_build_object('reason', 'Seed event for NIT-CRS-999, a course the CRM does not have', 'abandoned', TRUE, 'abandoned_on', CURRENT_DATE),
    processed_at = COALESCE(processed_at, now())
WHERE status = 'Failed' AND event_id LIKE 'seed-%' AND error LIKE 'Unknown course ''NIT-CRS-999''%';

ALTER TABLE crm_events VALIDATE CONSTRAINT crm_events_event_type_check;

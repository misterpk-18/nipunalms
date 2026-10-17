-- 116: CRM round 4 (D19): the counsellor's preferred batch on AdmissionQualified (docs/CRM_INTEGRATION.md)
-- Depends on: 003 (admissions)
--   admissions.preferred_batch_code: the LMS batch_code the CRM delivery plan prefers. A preference only: the Branch Manager still
--   allocates. Not a foreign key, because the batch may not exist (yet) or may be retired; the Waiting for a batch screen marks the
--   matching batch and the intake records a warning when the code names no batch of the admission's course and service branch.

ALTER TABLE admissions
    ADD COLUMN preferred_batch_code VARCHAR(50);

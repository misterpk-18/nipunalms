-- 090: fixes from the CRM's round-1 integration run ("nipuna crm-docs/CRM_TO_LMS_FIXES_ROUND1.md")
-- Depends on: 002 (courses, course_components), 003 (students, admissions, finance_summaries), 004 (batches)
--   F3: a finance summary says whether its instalment schedule belongs to the admission or to the whole invoice
--   F5: course titles as long as the CRM's (varchar 255)
--   F6: rows written by the dev seed are marked, so the CRM status pull leaves them out

-- F5: CRM courses.course_title is varchar(255). A combo track is named after its component course, so it matches.
ALTER TABLE courses ALTER COLUMN title TYPE VARCHAR(255);
ALTER TABLE course_components ALTER COLUMN track_name TYPE VARCHAR(255);

-- F2: a single course has no components. CourseUpserted removes them first (or refuses the event when they are in use);
-- this keeps any other writer from leaving combo tracks under a course marked single, as round 1 did with NIT-CRS-018.
CREATE OR REPLACE FUNCTION check_single_course_has_no_components() RETURNS trigger AS $$
BEGIN
    IF NOT NEW.is_combo AND EXISTS (SELECT 1 FROM course_components WHERE parent_course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'Course % still has combo components; remove them before marking it a single course', NEW.course_code;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_courses_single_has_no_components
    BEFORE UPDATE OF is_combo ON courses
    FOR EACH ROW EXECUTE FUNCTION check_single_course_has_no_components();

-- F3: the CRM keeps instalments per invoice. When one invoice covers several courses (one admission each), every
-- admission's summary carries the same invoice schedule: it is shown and summed once per invoice, never per admission.
ALTER TABLE finance_summaries
    ADD COLUMN installments_scope VARCHAR(20) NOT NULL DEFAULT 'admission'
        CHECK (installments_scope IN ('admission', 'invoice')),
    ADD COLUMN invoice_course_count INT NOT NULL DEFAULT 1 CHECK (invoice_course_count >= 0);

-- F6: staging rows whose CRM IDs are made up (CRM-PER-…, CRM-ADM-…, CRM-BAT-…). Never set outside `flask seed-dev`.
ALTER TABLE students ADD COLUMN seed_data BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE admissions ADD COLUMN seed_data BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE batches ADD COLUMN seed_data BOOLEAN NOT NULL DEFAULT false;

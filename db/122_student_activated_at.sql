-- 122: the status pull reports when a student activated their account (nipuna crm-docs/LMS_BATCH_WHATSAPP_REPLY.md, Q6)
-- Depends on: 003 (students), 095 (pull change stamps)
--   persons[].lms_provisioned_at is when the LMS created the login (and sent the activation link); the CRM's
--   "account activated" WhatsApp waits for lms_activated_at, the first time the student set their own password.
--   Stamped by the database clock (CURRENT_TIMESTAMP), like every other change the pull reads, so `as_of` holds.

ALTER TABLE students ADD COLUMN activated_at TIMESTAMPTZ;

-- Students already activated: the student login's password change (activation sets it), else the row's last update
UPDATE students s SET activated_at = COALESCE(
    (SELECT u.password_changed_at FROM users u WHERE u.student_id = s.student_id), s.updated_at)
WHERE s.activation_status = 'Activated';

-- The first change to Activated sets the stamp; it is never moved or cleared afterwards
CREATE OR REPLACE FUNCTION students_stamp_activated_at() RETURNS trigger AS $$
BEGIN
    IF NEW.activation_status = 'Activated' AND NEW.activated_at IS NULL THEN
        NEW.activated_at := CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_students_activated_at
    BEFORE INSERT OR UPDATE OF activation_status ON students
    FOR EACH ROW EXECUTE FUNCTION students_stamp_activated_at();

CREATE INDEX students_activated_at_idx ON students (activated_at);

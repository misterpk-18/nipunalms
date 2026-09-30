-- 070: certificates and completion authorisation for the CRM (docs/CRM_INTEGRATION.md §2.2, §3.3, §3.6)
-- Depends on: 005_crm_alignment.sql, 040_attendance_certificates.sql
--
-- The LMS Certificate Register is the single source of certificates; the CRM mirrors them read-only. The CRM's
-- admissions.completion_authorised_by is a required user, so the academic state now names the LMS authoriser by email.

ALTER TABLE crm_outbox DROP CONSTRAINT crm_outbox_event_type_check;
ALTER TABLE crm_outbox ADD CONSTRAINT crm_outbox_event_type_check CHECK (event_type IN (
    'LmsAccountProvisioned', 'AdmissionLmsStatusChanged', 'BatchLinked', 'AdmissionAcademicsChanged', 'BatchUpserted',
    'CertificateChanged'));

-- ---------------------------------------------------------------------------
-- Completion authoriser in the academic state
-- ---------------------------------------------------------------------------
ALTER FUNCTION admission_academic_state(INT) RENAME TO admission_academic_core;

CREATE OR REPLACE FUNCTION admission_academic_state(p_admission_id INT) RETURNS JSONB AS $$
    SELECT admission_academic_core(p_admission_id) || jsonb_build_object(
        'completion_authorised_by_email', (
            SELECT u.email
            FROM completion_reviews r
            JOIN enrolments e ON e.enrolment_id = r.enrolment_id
            JOIN admissions a ON a.admission_id = e.admission_id AND a.course_id = e.course_id
            JOIN users u ON u.user_id = r.decided_by
            WHERE a.admission_id = p_admission_id AND r.decision = 'Complete' AND e.status = 'Completed'
            ORDER BY r.decided_at DESC
            LIMIT 1));
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION completion_reviews_refresh_academics() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_admission_academics((SELECT admission_id FROM enrolments WHERE enrolment_id = NEW.enrolment_id));
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_completion_reviews_academics
    AFTER INSERT OR UPDATE OF status, decision ON completion_reviews
    FOR EACH ROW EXECUTE FUNCTION completion_reviews_refresh_academics();

-- ---------------------------------------------------------------------------
-- CertificateChanged: every numbered version when it is issued, superseded by a reissue, or revoked
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION certificate_crm_state(p_certificate_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'certificate_number', c.certificate_number,
        'certificate_type', c.certificate_type,
        'version', c.version,
        'status', c.status,                          -- Issued / Superseded / Revoked
        'crm_admission_id', a.crm_admission_id,
        'crm_person_id', s.crm_person_id,
        'course_code', co.course_code,
        'enrolment_code', e.enrolment_code,
        'holder_name', c.holder_name,
        'issue_date', c.issue_date,
        'issued_by_email', (SELECT email FROM users WHERE user_id = c.issued_by),
        'revoked_at', c.revoked_at,
        'revoked_by_email', (SELECT email FROM users WHERE user_id = c.revoked_by),
        'reason', c.reason,                          -- why a reissue exists, or why it was revoked
        'supersedes_version', (SELECT version FROM certificates WHERE certificate_id = c.supersedes_certificate_id),
        'changed_at', c.updated_at)
    FROM certificates c
    JOIN enrolments e ON e.enrolment_id = c.enrolment_id
    JOIN admissions a ON a.admission_id = e.admission_id
    JOIN students s ON s.student_id = c.student_id
    JOIN courses co ON co.course_id = c.course_id
    WHERE c.certificate_id = p_certificate_id;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION certificates_queue_crm() RETURNS trigger AS $$
BEGIN
    IF NEW.status IN ('Issued', 'Superseded', 'Revoked') AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO crm_outbox (event_type, payload) VALUES ('CertificateChanged', certificate_crm_state(NEW.certificate_id));
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_certificates_crm
    AFTER INSERT OR UPDATE OF status ON certificates
    FOR EACH ROW EXECUTE FUNCTION certificates_queue_crm();

-- Existing rows (a database built before 070): the academic state picks up the new field without queueing history
UPDATE admission_lms_state s SET academic = admission_academic_state(s.admission_id)
WHERE admission_academic_state(s.admission_id) IS NOT NULL;

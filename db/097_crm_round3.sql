-- 097: round 3, curriculum mapping from the CRM (docs/CRM_INTEGRATION.md §5)
-- Depends on: 002 (curriculum_versions), 003 (admissions), 010 (curriculum_events), 095
--   curriculum_versions[] in the status pull: every version of every course, with its own change stamp
--   AdmissionCurriculumMapped: the CRM maps an admission; versioned separately from the admission (curriculum:<id>)

-- ---------------------------------------------------------------------------
-- The curriculum catalogue as the CRM mirrors it
-- ---------------------------------------------------------------------------
-- status in the CRM's three values: Draft (LMS Draft / Under Review / Approved), Active, Retired. lms_status is the
-- LMS's own. published_at is when the version became Active (seed versions, made Active directly: their approval).
CREATE OR REPLACE FUNCTION curriculum_version_crm_payload(p_curriculum_version_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'course_code', c.course_code,
        'track_code', comp.track_code,
        'version_label', v.version_label,
        'status', CASE WHEN v.status IN ('Active', 'Retired') THEN v.status::TEXT ELSE 'Draft' END,
        'lms_status', v.status,
        'published_at', COALESCE(
            (SELECT max(e.created_at) FROM curriculum_events e
             WHERE e.curriculum_version_id = v.curriculum_version_id AND e.action = 'Activated'),
            CASE WHEN v.status = 'Active' THEN v.approved_at END))
    FROM curriculum_versions v
    JOIN courses c ON c.course_id = v.course_id
    LEFT JOIN course_components comp ON comp.component_id = v.component_id
    WHERE v.curriculum_version_id = p_curriculum_version_id;
$$ LANGUAGE sql STABLE;

-- One row per version ever reported. No foreign key: a deleted Draft keeps its row as a tombstone (status Retired,
-- lms_status Deleted), so the CRM's mirror never holds a version the LMS no longer has.
CREATE TABLE curriculum_version_crm_state (
    curriculum_version_id INT PRIMARY KEY,
    payload JSONB NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX curriculum_version_crm_state_changed_idx ON curriculum_version_crm_state (changed_at);
CREATE INDEX curriculum_version_crm_state_course_idx ON curriculum_version_crm_state ((payload ->> 'course_code'));

CREATE OR REPLACE FUNCTION refresh_curriculum_version_crm_state(p_curriculum_version_id INT) RETURNS void AS $$
DECLARE
    v_new JSONB := curriculum_version_crm_payload(p_curriculum_version_id);
    v_old JSONB;
BEGIN
    IF v_new IS NULL THEN
        RETURN;
    END IF;
    SELECT payload INTO v_old FROM curriculum_version_crm_state WHERE curriculum_version_id = p_curriculum_version_id;
    IF v_new ->> 'published_at' IS NULL AND v_old ->> 'published_at' IS NOT NULL THEN
        v_new := v_new || jsonb_build_object('published_at', v_old -> 'published_at');  -- a retired version keeps it
    END IF;
    IF v_old IS NOT DISTINCT FROM v_new THEN
        RETURN;
    END IF;
    INSERT INTO curriculum_version_crm_state (curriculum_version_id, payload) VALUES (p_curriculum_version_id, v_new)
    ON CONFLICT (curriculum_version_id) DO UPDATE SET payload = EXCLUDED.payload, changed_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION curriculum_versions_refresh_crm_state() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE curriculum_version_crm_state
        SET payload = payload || jsonb_build_object('status', 'Retired', 'lms_status', 'Deleted'), changed_at = CURRENT_TIMESTAMP
        WHERE curriculum_version_id = OLD.curriculum_version_id;
        RETURN NULL;
    END IF;
    PERFORM refresh_curriculum_version_crm_state(NEW.curriculum_version_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curriculum_versions_crm_state
    AFTER INSERT OR UPDATE OR DELETE ON curriculum_versions
    FOR EACH ROW EXECUTE FUNCTION curriculum_versions_refresh_crm_state();

-- An activation's event can be written after its status change: refresh again for published_at
CREATE OR REPLACE FUNCTION curriculum_events_refresh_crm_state() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_curriculum_version_crm_state(NEW.curriculum_version_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curriculum_events_crm_state
    AFTER INSERT ON curriculum_events
    FOR EACH ROW EXECUTE FUNCTION curriculum_events_refresh_crm_state();

-- Existing versions (a database built before 097)
INSERT INTO curriculum_version_crm_state (curriculum_version_id, payload)
SELECT curriculum_version_id, curriculum_version_crm_payload(curriculum_version_id) FROM curriculum_versions;

-- ---------------------------------------------------------------------------
-- AdmissionCurriculumMapped is versioned on its own (the CRM's curriculum:<crm_admission_id>)
-- ---------------------------------------------------------------------------
ALTER TABLE crm_events DROP CONSTRAINT crm_events_event_type_check;
ALTER TABLE crm_events ADD CONSTRAINT crm_events_event_type_check CHECK (event_type IN (
    'CourseUpserted', 'AdmissionQualified', 'AdmissionUpdated', 'AdmissionCancelled', 'FinanceSummaryUpdated',
    'BranchUpserted', 'BranchFinanceSnapshot', 'AdmissionCurriculumMapped'));

ALTER TABLE admissions ADD COLUMN curriculum_source_version INT NOT NULL DEFAULT 0 CHECK (curriculum_source_version >= 0);

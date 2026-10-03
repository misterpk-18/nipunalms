-- 095: the status pull the CRM applies in round 2 (docs/CRM_INTEGRATION.md §5)
-- Depends on: 003 (admission_lms_state), 005 (academic state, batch_crm_state), 040 + 070 (certificates), 090
--   Q1: `as_of` can be stored as the next `since` without missing a change still being committed during the pull
--   Q1: every CRM-facing admission value (status, last activity) moves one change stamp, set by the database
--   Q2: what the pull reports is never deleted, so a removal is always a status the CRM sees
--   Q4: an allocation names its combo track
--   Q9: indexes on the change stamps the pull filters on

-- ---------------------------------------------------------------------------
-- Q1: the next `since`
-- ---------------------------------------------------------------------------
-- Changes are stamped CURRENT_TIMESTAMP, the start of the writing transaction, and become visible only at commit. A
-- transaction still open when the CRM pulls can therefore commit rows stamped before the pull. `as_of` is held just
-- below the start of the oldest open transaction, so the next pull still returns them. Rows can come back once (the CRM
-- applies them idempotently); none are skipped. Sessions of other database roles show no xact_start unless the reader
-- has pg_read_all_stats: in production the app role does all LMS writes.
CREATE OR REPLACE FUNCTION crm_pull_as_of() RETURNS TIMESTAMPTZ AS $$
BEGIN
    PERFORM pg_stat_clear_snapshot();               -- pg_stat_activity is otherwise frozen at its first read in a transaction
    RETURN LEAST(clock_timestamp(),
                 (SELECT min(xact_start) - interval '1 microsecond'
                  FROM pg_stat_activity
                  WHERE datname = current_database() AND pid <> pg_backend_pid()
                    AND backend_type = 'client backend' AND xact_start IS NOT NULL));
END;
$$ LANGUAGE plpgsql VOLATILE;

-- ---------------------------------------------------------------------------
-- Q1: one change stamp per admission
-- ---------------------------------------------------------------------------
-- The pull used last_activity_at itself as a change time, but activity can be recorded with an earlier occurred_at
-- (offline or late events) and would then fall behind a stored `since`. changed_at moves whenever lms_status or
-- last_activity_at changes, at the time of the change.
ALTER TABLE admission_lms_state ADD COLUMN changed_at TIMESTAMPTZ;
UPDATE admission_lms_state SET changed_at = GREATEST(status_changed_at, COALESCE(last_activity_at, status_changed_at));
ALTER TABLE admission_lms_state ALTER COLUMN changed_at SET NOT NULL, ALTER COLUMN changed_at SET DEFAULT CURRENT_TIMESTAMP;

CREATE OR REPLACE FUNCTION refresh_admission_lms_state(p_admission_id INT) RETURNS void AS $$
DECLARE
    v_new lms_status := compute_admission_lms_status(p_admission_id);
    v_last TIMESTAMPTZ := admission_last_activity(p_admission_id);
    v_old lms_status;
    v_crm_admission_id VARCHAR(100);
BEGIN
    SELECT lms_status INTO v_old FROM admission_lms_state WHERE admission_id = p_admission_id;

    INSERT INTO admission_lms_state (admission_id, lms_status, last_activity_at)
    VALUES (p_admission_id, v_new, v_last)
    ON CONFLICT (admission_id) DO UPDATE SET
        lms_status = EXCLUDED.lms_status,
        last_activity_at = EXCLUDED.last_activity_at,
        status_changed_at = CASE WHEN admission_lms_state.lms_status <> EXCLUDED.lms_status
                                 THEN CURRENT_TIMESTAMP ELSE admission_lms_state.status_changed_at END,
        changed_at = CASE WHEN admission_lms_state.lms_status <> EXCLUDED.lms_status
                            OR admission_lms_state.last_activity_at IS DISTINCT FROM EXCLUDED.last_activity_at
                          THEN CURRENT_TIMESTAMP ELSE admission_lms_state.changed_at END;

    IF v_new IS DISTINCT FROM COALESCE(v_old, 'Not Created') THEN
        SELECT crm_admission_id INTO v_crm_admission_id FROM admissions WHERE admission_id = p_admission_id;
        INSERT INTO crm_outbox (event_type, payload)
        VALUES ('AdmissionLmsStatusChanged', jsonb_build_object(
            'crm_admission_id', v_crm_admission_id, 'lms_status', v_new,
            'lms_last_activity_at', v_last, 'synced_at', CURRENT_TIMESTAMP));
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Q4: allocations name their combo track
-- ---------------------------------------------------------------------------
-- A combo is allocated track by track, each track to a batch of the combo course. course_code is the track's component
-- course (the combo's own code for a track with no course of its own); track_code is the LMS track, NULL for a single
-- course.
CREATE OR REPLACE FUNCTION admission_academic_core(p_admission_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'crm_admission_id', a.crm_admission_id,
        'enrolment_status', crm_enrolment_status(e.status),
        'curriculum_status', CASE WHEN e.curriculum_version_id IS NOT NULL
                                   AND NOT EXISTS (SELECT 1 FROM enrolment_tracks t
                                                   WHERE t.enrolment_id = e.enrolment_id AND t.curriculum_version_id IS NULL)
                                  THEN 'Mapped' ELSE 'Mapping Pending' END,
        'curriculum_version_label', cv.version_label,
        'service_branch_code', b.branch_code,
        'joining_date', e.joining_date,
        'academic_completed_at', e.completed_at,
        'allocations', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                       'course_code', COALESCE(cc.course_code, c.course_code),
                       'track_code', comp.track_code,
                       'lms_course_id', bt.batch_code,
                       'crm_batch_id', bt.crm_batch_id,
                       'status', CASE ba.status
                                     WHEN 'Active' THEN 'Active'
                                     WHEN 'Transferred' THEN 'Moved'
                                     ELSE CASE WHEN e.status = 'Completed' THEN 'Completed' ELSE 'Withdrawn' END
                                 END,
                       'joining_date', e.joining_date,
                       'allocated_on', ba.effective_from,
                       'ended_on', ba.effective_to,
                       'end_reason', ba.reason)
                   ORDER BY ba.allocation_id)
            FROM batch_allocations ba
            JOIN batches bt ON bt.batch_id = ba.batch_id
            LEFT JOIN enrolment_tracks et ON et.enrolment_track_id = ba.enrolment_track_id
            LEFT JOIN course_components comp ON comp.component_id = et.component_id
            LEFT JOIN courses cc ON cc.course_id = comp.component_course_id
            WHERE ba.enrolment_id = e.enrolment_id), '[]'::jsonb))
    FROM admissions a
    JOIN enrolments e ON e.admission_id = a.admission_id AND e.course_id = a.course_id
    JOIN courses c ON c.course_id = e.course_id
    JOIN branches b ON b.branch_id = e.service_branch_id
    LEFT JOIN curriculum_versions cv ON cv.curriculum_version_id = e.curriculum_version_id
    WHERE a.admission_id = p_admission_id;
$$ LANGUAGE sql STABLE;

-- Existing rows (a database built before 095): their academic state gained a field, so they count as changed
UPDATE admission_lms_state s SET academic = admission_academic_state(s.admission_id), academic_changed_at = CURRENT_TIMESTAMP
WHERE admission_academic_state(s.admission_id) IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Q2: nothing the CRM mirrors disappears
-- ---------------------------------------------------------------------------
-- A batch is Cancelled, an allocation Ended or Transferred, a numbered certificate Superseded or Revoked: the pull
-- reports the new status. A delete would leave the CRM's mirror row behind, so it is refused.
CREATE OR REPLACE FUNCTION refuse_crm_mirrored_delete() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME = 'certificates' THEN
        IF OLD.certificate_number IS NULL THEN
            RETURN OLD;                             -- an unnumbered draft was never reported
        END IF;
    END IF;
    RAISE EXCEPTION '% rows are mirrored by the CRM and are never deleted; change their status instead', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batches_never_deleted
    BEFORE DELETE ON batches FOR EACH ROW EXECUTE FUNCTION refuse_crm_mirrored_delete();
CREATE TRIGGER trg_batch_allocations_never_deleted
    BEFORE DELETE ON batch_allocations FOR EACH ROW EXECUTE FUNCTION refuse_crm_mirrored_delete();
CREATE TRIGGER trg_certificates_never_deleted
    BEFORE DELETE ON certificates FOR EACH ROW EXECUTE FUNCTION refuse_crm_mirrored_delete();

-- ---------------------------------------------------------------------------
-- Q9: the pull filters on these every few minutes
-- ---------------------------------------------------------------------------
CREATE INDEX students_provisioned_at_idx ON students (provisioned_at) WHERE provisioned_at IS NOT NULL;
CREATE INDEX admission_lms_state_changed_idx ON admission_lms_state (changed_at);
CREATE INDEX admission_lms_state_academic_changed_idx ON admission_lms_state (academic_changed_at);
CREATE INDEX batch_crm_state_changed_idx ON batch_crm_state (changed_at);
CREATE INDEX certificates_numbered_updated_idx ON certificates (updated_at) WHERE certificate_number IS NOT NULL;

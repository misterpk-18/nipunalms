-- 104: round 5, the CRM no longer holds curriculum (docs/CRM_INTEGRATION.md)
-- Depends on: 070 (admission_academic_state wraps admission_academic_core), 095, 097, 098, 103
--   The LMS owns curriculum alone: it maps an admission to its course's Active version itself and never waits on the CRM.
--   AdmissionCurriculumMapped is no longer a valid event type; curriculum_versions[], curriculum_status and
--   curriculum_version_label leave the status pull and the outbox payloads.
-- Phase 7 of the gap fix plan starts at db/105.

-- ---------------------------------------------------------------------------
-- AdmissionCurriculumMapped is retired
-- ---------------------------------------------------------------------------
-- NOT VALID: events already received stay in the inbox as history; only new rows are checked.
ALTER TABLE crm_events DROP CONSTRAINT crm_events_event_type_check;
ALTER TABLE crm_events ADD CONSTRAINT crm_events_event_type_check CHECK (event_type IN (
    'CourseUpserted', 'AdmissionQualified', 'AdmissionUpdated', 'AdmissionCancelled', 'FinanceSummaryUpdated',
    'BranchUpserted', 'BranchFinanceSnapshot')) NOT VALID;

ALTER TABLE admissions DROP COLUMN curriculum_source_version;

-- ---------------------------------------------------------------------------
-- The curriculum catalogue mirror
-- ---------------------------------------------------------------------------
DROP TRIGGER trg_curriculum_events_crm_state ON curriculum_events;
DROP TRIGGER trg_curriculum_versions_crm_state ON curriculum_versions;
DROP FUNCTION curriculum_events_refresh_crm_state();
DROP FUNCTION curriculum_versions_refresh_crm_state();
DROP FUNCTION refresh_curriculum_version_crm_state(INT);
DROP TABLE curriculum_version_crm_state;
DROP FUNCTION curriculum_version_crm_payload(INT);

-- ---------------------------------------------------------------------------
-- admissions: curriculum_status / curriculum_version_label leave the academic state
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION admission_academic_core(p_admission_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'crm_admission_id', a.crm_admission_id,
        'enrolment_status', crm_enrolment_status(e.status),
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
    WHERE a.admission_id = p_admission_id;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- batches: curriculum_version_label leaves the CRM-facing state
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION batch_crm_state(p_batch_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'lms_course_id', bt.batch_code,
        'crm_batch_id', bt.crm_batch_id,
        'course_code', c.course_code,
        'branch_code', b.branch_code,
        'delivery_mode', crm_delivery_mode(bt.mode),
        'status', crm_batch_status(bt.state),
        'readiness', bt.readiness,                   -- Ready / Pending Verification / Blocked (a Blocked batch isn't offered)
        'readiness_reason', bt.readiness_reason,
        'capacity', bt.capacity,
        'seats_left', GREATEST(bt.capacity - (SELECT count(DISTINCT a.enrolment_id) FROM batch_allocations a
                                              WHERE a.batch_id = bt.batch_id AND a.status = 'Active'), 0),
        'start_date', bt.planned_start,
        'end_date', bt.planned_end,
        'schedule_days', weekday_labels(bt.schedule_days),
        'start_time', to_char(bt.start_time, 'HH24:MI'),
        'end_time', to_char(bt.end_time, 'HH24:MI'),
        'location', bt.location,
        'lead_trainer_email', (SELECT u.email FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                               WHERE t.batch_id = bt.batch_id AND t.role = 'Lead' AND t.to_date IS NULL LIMIT 1),
        'trainer_emails', COALESCE((SELECT jsonb_agg(u.email ORDER BY t.role, u.email)
                                    FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                                    WHERE t.batch_id = bt.batch_id AND t.to_date IS NULL), '[]'::jsonb))
    FROM batches bt
    JOIN courses c ON c.course_id = bt.course_id
    JOIN branches b ON b.branch_id = bt.branch_id
    WHERE bt.batch_id = p_batch_id;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Rows and queued events already written
-- ---------------------------------------------------------------------------
-- The keys are removed in place and no change stamp moves: the CRM ignores them, so nothing needs re-pulling.
UPDATE admission_lms_state SET academic = academic - 'curriculum_status' - 'curriculum_version_label'
WHERE academic IS NOT NULL;
UPDATE batch_crm_state SET payload = payload - 'curriculum_version_label';
UPDATE crm_outbox SET payload = payload - 'curriculum_status' - 'curriculum_version_label'
WHERE status = 'Pending' AND event_type IN ('AdmissionAcademicsChanged', 'BatchUpserted');

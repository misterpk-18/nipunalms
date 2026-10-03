-- 098: the batch timetable for the CRM's sales playbook (docs/CRM_INTEGRATION.md §5, round 3)
-- Depends on: 004 (batches, batch_allocations), 005 (batch_crm_state)
--   The days, times and room a batch meets, set by the coordinator before any class is scheduled (Planned batches
--   have no sessions yet), so the CRM's Front Office can check real timings before promising a batch.
--   batches[] in the status pull also carries the timetable, readiness (a Blocked batch is not offered) and seats_left.

ALTER TABLE batches
    ADD COLUMN schedule_days SMALLINT[],            -- ISO weekdays, 1 = Mon … 7 = Sun; NULL = not confirmed
    ADD COLUMN start_time TIME,                     -- IST
    ADD COLUMN end_time TIME,
    ADD COLUMN location VARCHAR(255),               -- classroom / room (Classroom, Hybrid); NULL for Live Online
    ADD CONSTRAINT batches_schedule_days CHECK (
        schedule_days IS NULL OR (cardinality(schedule_days) BETWEEN 1 AND 7 AND schedule_days <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::SMALLINT[])),
    ADD CONSTRAINT batches_schedule_times CHECK (
        (start_time IS NULL) = (end_time IS NULL) AND (end_time IS NULL OR end_time > start_time));

-- 'Mon, Wed, Fri' (week order, each day once)
CREATE OR REPLACE FUNCTION weekday_labels(p_days SMALLINT[]) RETURNS TEXT AS $$
    SELECT string_agg((ARRAY['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])[d], ', ' ORDER BY d)
    FROM (SELECT DISTINCT unnest(p_days) AS d) days;
$$ LANGUAGE sql IMMUTABLE;

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
        'curriculum_version_label', cv.version_label,
        'lead_trainer_email', (SELECT u.email FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                               WHERE t.batch_id = bt.batch_id AND t.role = 'Lead' AND t.to_date IS NULL LIMIT 1),
        'trainer_emails', COALESCE((SELECT jsonb_agg(u.email ORDER BY t.role, u.email)
                                    FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                                    WHERE t.batch_id = bt.batch_id AND t.to_date IS NULL), '[]'::jsonb))
    FROM batches bt
    JOIN courses c ON c.course_id = bt.course_id
    JOIN branches b ON b.branch_id = bt.branch_id
    LEFT JOIN curriculum_versions cv ON cv.curriculum_version_id = bt.curriculum_version_id
    WHERE bt.batch_id = p_batch_id;
$$ LANGUAGE sql STABLE;

-- A seat taken or freed changes seats_left
CREATE OR REPLACE FUNCTION batch_allocations_refresh_crm_state() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_batch_crm_state(NEW.batch_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_allocations_crm_state
    AFTER INSERT OR UPDATE ON batch_allocations
    FOR EACH ROW EXECUTE FUNCTION batch_allocations_refresh_crm_state();

-- Existing batches gained fields: they count as changed (no outbox history is queued)
UPDATE batch_crm_state s SET payload = batch_crm_state(s.batch_id), changed_at = CURRENT_TIMESTAMP;

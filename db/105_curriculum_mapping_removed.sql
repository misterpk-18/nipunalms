-- 105: UX phase U1, "Curriculum Mapping Pending" is removed (docs/UX_PLAN.md)
-- Depends on: 003, 005, 080, 102, 103, 104
--   A new enrolment is always allocatable: with no Active curriculum version it simply has none, and the batch it joins
--   (and later the version activated for that course) supplies it. The state, its academic owner and its exception
--   queue source go. Existing enrolments in the state move to Allocation Pending in place.
-- Gap fix phase 7 starts at db/107 (U2 takes 106).

-- ---------------------------------------------------------------------------
-- Move the enrolments waiting in the state, and say so on their exception rows
-- ---------------------------------------------------------------------------
INSERT INTO exception_recovery_steps (source, source_id, branch_id, reason, logged_by)
SELECT 'CURRICULUM_MAPPING', e.enrolment_id, e.service_branch_id,
       'Closed: the Curriculum Mapping Pending state no longer exists. The enrolment can be allocated now and follows the curriculum of its batch.',
       COALESCE(e.mapping_owner_user_id, (SELECT min(user_id) FROM users))
FROM enrolments e
WHERE e.status = 'Curriculum Mapping Pending';

UPDATE enrolments SET status = 'Allocation Pending' WHERE status = 'Curriculum Mapping Pending';

-- A batch whose only blocker was the missing curriculum is no longer blocked (it warns instead)
UPDATE batches SET readiness = 'Ready', readiness_reason = NULL, recovery_owner = NULL
WHERE readiness = 'Blocked' AND readiness_reason LIKE 'Curriculum Mapping Pending:%' AND position(';' IN readiness_reason) = 0;

-- ---------------------------------------------------------------------------
-- Replace the enum (PostgreSQL cannot drop one value)
-- ---------------------------------------------------------------------------
DROP VIEW exception_queue;
DROP TRIGGER trg_enrolments_lms_state ON enrolments;
DROP TRIGGER trg_enrolments_completion ON enrolments;
DROP TRIGGER trg_enrolments_academics ON enrolments;
ALTER TABLE enrolments DROP CONSTRAINT enrolments_active_has_joining_date;
ALTER TABLE enrolments DROP CONSTRAINT enrolments_gate_blocks_access;
DROP FUNCTION crm_enrolment_status(enrolment_status);

ALTER TYPE enrolment_status RENAME TO enrolment_status_old;
CREATE TYPE enrolment_status AS ENUM (
    'Provisioning Pending', 'Allocation Pending',
    'Allocated — awaiting first regular class', 'Active', 'Paused', 'Completed', 'Withdrawn'
);
ALTER TABLE enrolments ALTER COLUMN status TYPE enrolment_status USING status::TEXT::enrolment_status;
DROP TYPE enrolment_status_old;

ALTER TABLE enrolments ADD CONSTRAINT enrolments_active_has_joining_date
    CHECK (status <> 'Active' OR joining_date IS NOT NULL);
ALTER TABLE enrolments ADD CONSTRAINT enrolments_gate_blocks_access
    CHECK (benefit_gate_met IS DISTINCT FROM false OR status IN ('Provisioning Pending', 'Withdrawn'));

CREATE OR REPLACE FUNCTION crm_enrolment_status(p_status enrolment_status) RETURNS TEXT AS $$
    SELECT CASE p_status
        WHEN 'Allocated — awaiting first regular class' THEN 'Scheduled'
        WHEN 'Active' THEN 'In Progress'
        WHEN 'Paused' THEN 'Paused'
        WHEN 'Completed' THEN 'Completed'
        WHEN 'Withdrawn' THEN 'Cancelled'
        ELSE 'Awaiting Batch Allocation'              -- Provisioning / Allocation Pending
    END;
$$ LANGUAGE sql IMMUTABLE;

CREATE TRIGGER trg_enrolments_lms_state AFTER INSERT OR UPDATE OF status ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_refresh_lms_state();
CREATE TRIGGER trg_enrolments_completion BEFORE INSERT OR UPDATE OF status ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_stamp_completion();
CREATE TRIGGER trg_enrolments_academics AFTER INSERT OR UPDATE OF status, joining_date, curriculum_version_id, service_branch_id, completed_at ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_refresh_academics();

-- ---------------------------------------------------------------------------
-- The academic owner of the state, and its exception queue source
-- ---------------------------------------------------------------------------
ALTER TABLE enrolments DROP COLUMN mapping_owner_user_id;

-- 'CURRICULUM_MAPPING' stays an allowed source of exception_recovery_steps: the history above and earlier steps keep it.
-- Exception queue: what db/103 had, without the Curriculum Mapping Pending source
CREATE OR REPLACE VIEW exception_queue AS
WITH items AS (
    -- Enrolments with no batch seat yet, whether or not the course has an approved curriculum
    SELECT 'ALLOCATION'::TEXT AS source, e.enrolment_id AS source_id, e.enrolment_code AS reference,
           'Curriculum / allocation'::TEXT AS queue, e.service_branch_id AS branch_id,
           'Awaiting batch allocation'::TEXT AS title,
           c.course_code || ' · ' || s.full_name AS detail,
           NULL::INT AS owner_user_id, 'Academic Coordinator'::TEXT AS owner_label,
           e.updated_at AS opened_at, 'Open'::TEXT AS state, '/academic/batches'::TEXT AS link
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Allocation Pending'

    UNION ALL
    -- Complimentary access held back until the qualifying payment gate is met (provisioning not finished)
    SELECT 'PROVISIONING', e.enrolment_id, e.enrolment_code,
           'Provisioning', e.service_branch_id,
           'Provisioning Pending',
           c.course_code || ' · ' || s.full_name || COALESCE(' · ' || e.benefit_note, ''),
           NULL, 'Super Admin',
           e.updated_at, 'Pending Verification', '/admin/students'
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Provisioning Pending'

    UNION ALL
    -- Recording promises that are not being kept (S2)
    SELECT 'RECORDING', r.exception_id, r.exception_code,
           'Meet / recording', r.branch_id,
           'Recording: ' || r.issue_type::TEXT,
           b.batch_code || ' · ' || r.issue,
           r.owner_user_id,
           CASE r.owner_role WHEN 'ACADEMIC_COORDINATOR' THEN 'Academic Coordinator'
                             WHEN 'BRANCH_MANAGER' THEN 'Branch Manager' ELSE 'Super Admin' END,
           r.opened_at, r.status::TEXT, '/academic/recording-exceptions'
    FROM recording_exceptions r
    JOIN class_sessions cs ON cs.session_id = r.session_id
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE r.status <> 'Resolved'

    UNION ALL
    -- CRM events that failed to apply (Phase 1 / S6). Company-wide: no branch.
    SELECT 'CRM_EVENT', ev.crm_event_id, ev.event_id,
           'CRM/LMS sync', NULL,
           ev.event_type || ' failed',
           COALESCE(ev.error, 'The event could not be applied'),
           NULL, 'Super Admin',
           COALESCE(ev.processed_at, ev.received_at), 'Failed', '/admin/crm-sync'
    FROM crm_events ev
    WHERE ev.status = 'Failed'

    UNION ALL
    -- Support requests past their SLA or escalated (S5); they always have a named owner
    SELECT 'SUPPORT', sr.support_request_id, sr.request_code,
           'Support', sr.branch_id,
           CASE WHEN sr.escalation_level IS NOT NULL THEN 'Escalated to ' || sr.escalation_level ELSE 'Support request overdue' END,
           sr.subject,
           sr.owner_user_id,
           CASE sr.owner_role WHEN 'TRAINER' THEN 'Trainer' WHEN 'ACADEMIC_COORDINATOR' THEN 'Academic Coordinator'
                              WHEN 'BRANCH_MANAGER' THEN 'Branch Manager' ELSE 'Super Admin' END,
           COALESCE(sr.escalated_at, sr.sla_due_at),
           CASE WHEN sr.escalation_level IS NOT NULL THEN 'Escalated' ELSE 'Overdue' END,
           '/academic/support'
    FROM support_requests sr
    WHERE sr.status IN ('Open', 'In Progress', 'Waiting on Student')
      AND (sr.escalation_level IS NOT NULL OR sr.sla_due_at < CURRENT_TIMESTAMP)

    UNION ALL
    -- Results not yet published, one row per batch (S3)
    SELECT 'RESULTS', b.batch_id, b.batch_code,
           'Assessments', b.branch_id,
           'Results awaiting publication review',
           count(*) || ' result(s) · ' || b.batch_code,
           NULL, 'Academic Coordinator',
           min(r.created_at), 'Awaiting Review', '/academic/assessments'
    FROM results r
    JOIN batches b ON b.batch_id = r.batch_id
    WHERE r.status IN ('Provisional', 'Moderated')
    GROUP BY b.batch_id, b.batch_code, b.branch_id

    UNION ALL
    -- Access requests after the second anniversary: only a Founder / CEO or Super Admin may grant them (S2)
    SELECT 'ACCESS_EXCEPTION', x.request_id, x.request_code,
           'Access / recovery', x.branch_id,
           'Recording access after the 2nd anniversary',
           s.full_name || ' · ' || x.scope::TEXT,
           NULL, 'Super Admin',
           x.requested_at, 'Awaiting Approval', '/branch/requests'
    FROM access_extension_requests x
    JOIN students s ON s.student_id = x.student_id
    WHERE x.status = 'Pending' AND x.needs_exception

    UNION ALL
    -- Integrations whose verification failed or whose configuration is wrong (Phase 1 / S6). Company-wide.
    SELECT 'INTEGRATION', i.integration_id, i.integration_code,
           'Integrations', NULL,
           i.integration_name || ' needs attention',
           COALESCE(i.notes, i.requirement),
           NULL, i.owner,
           COALESCE(i.last_checked_at, i.updated_at), 'Failed', '/admin/integrations'
    FROM integrations i
    WHERE i.verification_status = 'Failed' OR i.configuration_status = 'Misconfigured'

    UNION ALL
    -- Delayed starts and other class disruptions waiting for a recovery plan (Module 16 §7)
    SELECT 'DISRUPTION', d.disruption_id, cs.session_code,
           'Live classes', b.branch_id,
           d.kind || COALESCE(' (' || d.delay_minutes || ' min)', ''),
           b.batch_code || ' · ' || cs.title,
           d.owner_user_id, 'Academic Coordinator',
           d.detected_at, 'Open', '/academic/meet-operations'
    FROM session_disruptions d
    JOIN class_sessions cs ON cs.session_id = d.session_id
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE d.status = 'Open'

    UNION ALL
    -- Classes with no delivery log by the end of their working day (Module 15 §15)
    SELECT 'CLASS_LOG', cs.session_id, cs.session_code,
           'Live classes', b.branch_id,
           'Class log missing',
           b.batch_code || ' · ' || cs.title,
           NULL, 'Academic Coordinator',
           cs.log_overdue_at, 'Overdue', '/academic/schedule'
    FROM class_sessions cs
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE cs.log_overdue_at IS NOT NULL AND cs.state IN ('Scheduled', 'Rescheduled', 'Live')

    UNION ALL
    -- Cancelled classes still owing a replacement (Module 15 §16)
    SELECT 'REPLACEMENT', cs.session_id, cs.session_code,
           'Live classes', b.branch_id,
           'Replacement class owed',
           b.batch_code || ' · ' || cs.title,
           NULL, 'Academic Coordinator',
           cs.updated_at, 'Open', '/academic/schedule'
    FROM class_sessions cs
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE cs.state = 'Cancelled' AND cs.replacement_waiver IS NULL AND cs.purpose IN ('Regular', 'Remedial') AND cs.approval_status <> 'Rejected'
      AND NOT EXISTS (SELECT 1 FROM class_sessions r WHERE r.replaces_session_id = cs.session_id AND r.state <> 'Cancelled')
),
steps AS (
    SELECT source, source_id, count(*) AS step_count, max(logged_at) AS last_step_at,
           (array_agg(logged_by ORDER BY step_id DESC))[1] AS last_step_by
    FROM exception_recovery_steps
    GROUP BY source, source_id
)
SELECT i.source, i.source_id, i.reference, i.queue, i.branch_id, i.title, i.detail,
       -- A named owner is either the record's own owner or the last person who logged a recovery step on it
       COALESCE(i.owner_user_id, st.last_step_by) AS owner_user_id,
       u.full_name AS owner_name,
       i.owner_label, i.opened_at,
       CASE WHEN i.state = 'Open' AND st.step_count > 0 THEN 'Recovery In Progress' ELSE i.state END AS state,
       i.link,
       COALESCE(st.step_count, 0)::INT AS step_count, st.last_step_at
FROM items i
LEFT JOIN steps st ON st.source = i.source AND st.source_id = i.source_id
LEFT JOIN users u ON u.user_id = COALESCE(i.owner_user_id, st.last_step_by);

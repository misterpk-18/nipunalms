-- Phase 3 / 080: the cross-slice exception queue
-- Depends on: 001 (users, branches, integrations), 003 (enrolments, students, crm_events), 004 (batches),
--             020 (recording_exceptions, access_extension_requests), 030 (results), 050 (support_requests)
-- Adds: exception_recovery_steps (what was done about an exception, append-only) and the exception_queue view, which
-- unions the open exceptions each slice already stores. Nothing is copied: a row disappears from the view when the
-- slice resolves its own record, so the queue cannot drift from the source.

-- ---------------------------------------------------------------------------
-- Recovery steps: a person logs what they did (or will do) about an exception. Append-only.
-- ---------------------------------------------------------------------------
CREATE TABLE exception_recovery_steps (
    step_id BIGSERIAL PRIMARY KEY,
    source VARCHAR(30) NOT NULL CHECK (source IN
        ('CURRICULUM_MAPPING', 'ALLOCATION', 'PROVISIONING', 'RECORDING', 'CRM_EVENT', 'SUPPORT', 'RESULTS', 'ACCESS_EXCEPTION', 'INTEGRATION')),
    source_id INT NOT NULL,                         -- the id of the record in its own table (see the view)
    branch_id INT REFERENCES branches(branch_id),   -- the exception's branch when the step was logged (NULL = company-wide)
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    logged_by INT NOT NULL REFERENCES users(user_id),
    logged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX exception_recovery_steps_item_idx ON exception_recovery_steps (source, source_id, logged_at DESC);
CREATE INDEX exception_recovery_steps_branch_idx ON exception_recovery_steps (branch_id);

CREATE OR REPLACE FUNCTION prevent_recovery_step_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'exception_recovery_steps is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_exception_recovery_steps_immutable
    BEFORE UPDATE OR DELETE ON exception_recovery_steps
    FOR EACH ROW EXECUTE FUNCTION prevent_recovery_step_change();

-- ---------------------------------------------------------------------------
-- The queue
--   source / source_id   which table the record lives in and its id there
--   queue                the grouping the Super Admin screen uses
--   owner_user_id        the named owner (NULL = awaiting a named owner); owner_label is the role that should own it
--   state                the record's own state; 'Recovery In Progress' once a step was logged on an otherwise Open item
--   link                 SPA route of the screen that resolves it
-- ---------------------------------------------------------------------------
CREATE VIEW exception_queue AS
WITH items AS (
    -- Enrolments waiting for a curriculum version to be mapped (S1). Paid receipts and Admissions are preserved.
    SELECT 'CURRICULUM_MAPPING'::TEXT AS source, e.enrolment_id AS source_id, e.enrolment_code AS reference,
           'Curriculum / allocation'::TEXT AS queue, e.service_branch_id AS branch_id,
           'Curriculum Mapping Pending'::TEXT AS title,
           c.course_code || ' · ' || s.full_name AS detail,
           NULL::INT AS owner_user_id, 'Academic Coordinator'::TEXT AS owner_label,
           e.updated_at AS opened_at, 'Open'::TEXT AS state, '/academic/curriculum'::TEXT AS link
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Curriculum Mapping Pending'

    UNION ALL
    -- Enrolments with a curriculum but no batch seat yet (S1)
    SELECT 'ALLOCATION', e.enrolment_id, e.enrolment_code,
           'Curriculum / allocation', e.service_branch_id,
           'Awaiting batch allocation',
           c.course_code || ' · ' || s.full_name,
           NULL, 'Academic Coordinator',
           e.updated_at, 'Open', '/academic/batches'
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

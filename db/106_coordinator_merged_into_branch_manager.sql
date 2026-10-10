-- 106: UX phase U2, the Academic Coordinator is merged into the Branch Manager (docs/UX_PLAN.md)
-- Depends on: 001, 020, 030, 050, 080, 103, 105
--   Like the CRM, the LMS has no Academic Coordinator any more: the Branch Manager does everything it did. The role row is
--   retired (not deleted) so history and the audit log stay readable; accounts that held nothing else are deactivated and
--   their open items move to the Branch Managers of their branch (a Super Admin when a branch has none). The two-step
--   coordinator -> Branch Manager approvals become one Branch Manager step, so the database no longer insists that the
--   proposer and the confirmer of a batch, or the requester and the decider of a capacity increase or a transfer, differ.
-- Gap fix phase 7 starts at db/107.

-- ---------------------------------------------------------------------------
-- Who held the role, and who takes over
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE coordinator_users ON COMMIT DROP AS
SELECT DISTINCT s.user_id
FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
WHERE r.role_code = 'ACADEMIC_COORDINATOR';

-- Accounts whose only live role was the coordinator's
CREATE TEMP TABLE coordinator_only_users ON COMMIT DROP AS
SELECT cu.user_id FROM coordinator_users cu
WHERE NOT EXISTS (
    SELECT 1 FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
    WHERE s.user_id = cu.user_id AND s.revoked_at IS NULL AND r.role_code <> 'ACADEMIC_COORDINATOR');

-- The Branch Manager who inherits a branch's open items (the lowest id), else a Super Admin
CREATE TEMP TABLE branch_heirs ON COMMIT DROP AS
SELECT b.branch_id,
       (SELECT min(s.user_id) FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id JOIN users u ON u.user_id = s.user_id
        WHERE r.role_code = 'BRANCH_MANAGER' AND s.revoked_at IS NULL AND u.is_active AND (s.branch_id = b.branch_id OR s.branch_id IS NULL)) AS manager_id,
       (SELECT min(s.user_id) FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id JOIN users u ON u.user_id = s.user_id
        WHERE r.role_code = 'SUPER_ADMIN' AND s.revoked_at IS NULL AND u.is_active) AS admin_id
FROM branches b;

-- ---------------------------------------------------------------------------
-- Open items move to the Branch Managers
-- ---------------------------------------------------------------------------
UPDATE support_requests sr
SET owner_user_id = COALESCE(h.manager_id, h.admin_id),
    owner_role = CASE WHEN h.manager_id IS NOT NULL THEN 'BRANCH_MANAGER' ELSE 'SUPER_ADMIN' END,
    escalation_level = CASE WHEN sr.escalation_level = 'Academic Coordinator' THEN 'Branch Manager' ELSE sr.escalation_level END
FROM branch_heirs h
WHERE h.branch_id = sr.branch_id AND sr.owner_role = 'ACADEMIC_COORDINATOR' AND sr.status IN ('Open', 'In Progress', 'Waiting on Student')
  AND COALESCE(h.manager_id, h.admin_id) IS NOT NULL;

UPDATE recording_exceptions rx
SET owner_role = 'BRANCH_MANAGER', owner_user_id = CASE WHEN rx.owner_user_id IN (SELECT user_id FROM coordinator_users) THEN h.manager_id ELSE rx.owner_user_id END
FROM branch_heirs h
WHERE h.branch_id = rx.branch_id AND rx.owner_role = 'ACADEMIC_COORDINATOR' AND rx.status <> 'Resolved';

UPDATE session_disruptions d
SET owner_user_id = h.manager_id
FROM class_sessions cs, batches b, branch_heirs h
WHERE cs.session_id = d.session_id AND b.batch_id = cs.batch_id AND h.branch_id = b.branch_id
  AND d.status = 'Open' AND d.owner_user_id IN (SELECT user_id FROM coordinator_users) AND h.manager_id IS NOT NULL;

-- Reviews a coordinator had started but not finished, and the reviewer named on assignments and tests
UPDATE assignment_submissions s
SET review_started_by = h.manager_id
FROM assignments a, batches b, branch_heirs h
WHERE a.assignment_id = s.assignment_id AND b.batch_id = a.batch_id AND h.branch_id = b.branch_id
  AND s.review_started_by IN (SELECT user_id FROM coordinator_users) AND h.manager_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM submission_reviews r WHERE r.submission_id = s.submission_id);

UPDATE assignments a
SET reviewer_user_id = h.manager_id
FROM batches b, branch_heirs h
WHERE b.batch_id = a.batch_id AND h.branch_id = b.branch_id AND a.reviewer_user_id IN (SELECT user_id FROM coordinator_users)
  AND a.status <> 'Withdrawn' AND h.manager_id IS NOT NULL;

UPDATE tests t
SET reviewer_user_id = h.manager_id
FROM batches b, branch_heirs h
WHERE b.batch_id = t.batch_id AND h.branch_id = b.branch_id AND t.reviewer_user_id IN (SELECT user_id FROM coordinator_users)
  AND t.release_status <> 'Closed' AND h.manager_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Retire the role, deactivate the accounts that held nothing else, end their sessions
-- ---------------------------------------------------------------------------
UPDATE user_role_scopes s SET revoked_at = now()
FROM roles r WHERE r.role_id = s.role_id AND r.role_code = 'ACADEMIC_COORDINATOR' AND s.revoked_at IS NULL;

UPDATE roles SET is_active = FALSE, description = 'Retired: merged into the Branch Manager (UX phase U2)' WHERE role_code = 'ACADEMIC_COORDINATOR';

UPDATE users SET is_active = FALSE WHERE user_id IN (SELECT user_id FROM coordinator_only_users);

UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'Role retired'
WHERE user_id IN (SELECT user_id FROM coordinator_only_users) AND revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- One Branch Manager step: the proposer may confirm a batch, the requester may decide a capacity increase or a transfer
-- ---------------------------------------------------------------------------
ALTER TABLE batches DROP CONSTRAINT batches_confirmer_independent;
ALTER TABLE batch_capacity_requests DROP CONSTRAINT batch_capacity_requests_independent;
ALTER TABLE batch_transfer_requests DROP CONSTRAINT batch_transfer_requests_independent;

-- ---------------------------------------------------------------------------
-- Exception queue: the Branch Manager owns what the coordinator did; links point at the Branch Manager workspace
-- ---------------------------------------------------------------------------
DROP VIEW exception_queue;
CREATE OR REPLACE VIEW exception_queue AS
WITH items AS (
    -- Enrolments with no batch seat yet, whether or not the course has an approved curriculum
    SELECT 'ALLOCATION'::TEXT AS source, e.enrolment_id AS source_id, e.enrolment_code AS reference,
           'Curriculum / allocation'::TEXT AS queue, e.service_branch_id AS branch_id,
           'Awaiting batch allocation'::TEXT AS title,
           c.course_code || ' · ' || s.full_name AS detail,
           NULL::INT AS owner_user_id, 'Branch Manager'::TEXT AS owner_label,
           e.updated_at AS opened_at, 'Open'::TEXT AS state, '/branch/batches'::TEXT AS link
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
           CASE r.owner_role WHEN 'SUPER_ADMIN' THEN 'Super Admin' ELSE 'Branch Manager' END,
           r.opened_at, r.status::TEXT, '/branch/recording-exceptions'
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
           CASE sr.owner_role WHEN 'TRAINER' THEN 'Trainer' WHEN 'SUPER_ADMIN' THEN 'Super Admin' ELSE 'Branch Manager' END,
           COALESCE(sr.escalated_at, sr.sla_due_at),
           CASE WHEN sr.escalation_level IS NOT NULL THEN 'Escalated' ELSE 'Overdue' END,
           '/branch/support'
    FROM support_requests sr
    WHERE sr.status IN ('Open', 'In Progress', 'Waiting on Student')
      AND (sr.escalation_level IS NOT NULL OR sr.sla_due_at < CURRENT_TIMESTAMP)

    UNION ALL
    -- Results not yet published, one row per batch (S3)
    SELECT 'RESULTS', b.batch_id, b.batch_code,
           'Assessments', b.branch_id,
           'Results awaiting publication review',
           count(*) || ' result(s) · ' || b.batch_code,
           NULL, 'Branch Manager',
           min(r.created_at), 'Awaiting Review', '/branch/assessments'
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
           d.owner_user_id, 'Branch Manager',
           d.detected_at, 'Open', '/branch/meet-operations'
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
           NULL, 'Branch Manager',
           cs.log_overdue_at, 'Overdue', '/branch/schedule'
    FROM class_sessions cs
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE cs.log_overdue_at IS NOT NULL AND cs.state IN ('Scheduled', 'Rescheduled', 'Live')

    UNION ALL
    -- Cancelled classes still owing a replacement (Module 15 §16)
    SELECT 'REPLACEMENT', cs.session_id, cs.session_code,
           'Live classes', b.branch_id,
           'Replacement class owed',
           b.batch_code || ' · ' || cs.title,
           NULL, 'Branch Manager',
           cs.updated_at, 'Open', '/branch/schedule'
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


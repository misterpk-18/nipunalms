-- 099: phase 1 of the gap fix plan — correctness and privacy (docs/GAP_FIX_PLAN.md, docs/GAPS.md)
-- Depends on: 001 (notifications, app_settings), 020 (content_items), 040 (attendance views)
--   Notices keep the role they were sent to, so a role or branch change hides them (G010); staff-only library items
--   (G022); a historical CRM import sends no current notices (G056); attendance expectations start at the seat, not the
--   first Present (G028), and a recovery counts only once completed (G029).

-- ---------------------------------------------------------------------------
-- Notifications: the role a notice was fanned out on (NULL = sent to named people)
-- ---------------------------------------------------------------------------
ALTER TABLE notifications ADD COLUMN role_code VARCHAR(50);

-- ---------------------------------------------------------------------------
-- Content library: answer keys, marking guides and trainer notes stay with staff (Module 18 §3)
-- ---------------------------------------------------------------------------
ALTER TABLE content_items ADD COLUMN staff_only BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- CRM intake: a historical import (flagged by the CRM, or older than crm_notify_max_age_hours) is applied with its
-- original dates but sends no current notices (Module 27 §6)
-- ---------------------------------------------------------------------------
ALTER TABLE crm_events ADD COLUMN historical BOOLEAN NOT NULL DEFAULT FALSE;

INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('crm_notify_max_age_hours', '72', 'A CRM event that happened longer ago than this is a historical import: applied, but no notices are sent')
ON CONFLICT (setting_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Attendance (Module 21 §3, §6). Expectations start when the enrolment got its seat in the batch (the agreed start under
-- the delivery plan), so absences before the first Present count; the Joining Date stays "first attended". A recovery
-- covers learning only when Completed. Views are dropped in dependency order and recreated; enrolment_batch_links gains
-- first_effective_from as a trailing column.
-- ---------------------------------------------------------------------------
DROP VIEW enrolment_progress;
DROP VIEW enrolment_required_learning;
DROP VIEW enrolment_covered_topics;
DROP VIEW enrolment_attendance;
DROP VIEW attendance_grid;

CREATE OR REPLACE VIEW enrolment_batch_links AS
SELECT enrolment_id, batch_id,
       bool_or(status = 'Active') AS is_current,
       max(effective_to) AS last_effective_to,
       min(effective_from) AS first_effective_from
FROM batch_allocations
GROUP BY enrolment_id, batch_id;

-- Delivered sessions while the enrolment held a seat in the batch, each with the enrolment's entry and its live recovery
CREATE VIEW attendance_grid AS
SELECT e.enrolment_id, cs.session_id, cs.batch_id, cs.topic_id, cs.starts_at, cs.ends_at,
       ar.attendance_id, ar.status AS attendance_status,
       rec.recovery_id, rec.recovery_code, rec.status AS recovery_status
FROM enrolments e
JOIN enrolment_batch_links l ON l.enrolment_id = e.enrolment_id
JOIN class_sessions cs ON cs.batch_id = l.batch_id AND cs.state = 'Delivered'
LEFT JOIN attendance_records ar ON ar.session_id = cs.session_id AND ar.enrolment_id = e.enrolment_id
LEFT JOIN attendance_recoveries rec ON rec.attendance_id = ar.attendance_id AND rec.status IN ('Requested', 'Approved', 'Completed')
WHERE (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date >= l.first_effective_from
  AND (l.is_current OR (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date <= l.last_effective_to);

-- delivered_since_joining keeps its name for the API; it now counts from the seat, not the first Present
CREATE VIEW enrolment_attendance AS
SELECT e.enrolment_id,
       count(g.session_id) AS delivered_since_joining,
       count(g.attendance_id) AS marked_sessions,
       count(g.session_id) - count(g.attendance_id) AS unmarked_sessions,
       count(*) FILTER (WHERE g.attendance_status = 'Present') AS present_count,
       count(*) FILTER (WHERE g.attendance_status = 'Late') AS late_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent') AS absent_count,
       count(*) FILTER (WHERE g.attendance_status = 'Excused') AS excused_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent' AND g.recovery_status = 'Completed') AS recovered_count
FROM enrolments e
LEFT JOIN attendance_grid g ON g.enrolment_id = e.enrolment_id
GROUP BY e.enrolment_id;

-- Topics taught in a delivered session the student attended (Present / Late) or recovered (completed recovery)
CREATE VIEW enrolment_covered_topics AS
SELECT DISTINCT enrolment_id, topic_id
FROM attendance_grid
WHERE topic_id IS NOT NULL
  AND (attendance_status IN ('Present', 'Late') OR recovery_status = 'Completed');

CREATE VIEW enrolment_required_learning AS
SELECT e.enrolment_id,
       count(rt.topic_id) AS required_topics,
       count(ct.topic_id) AS covered_topics
FROM enrolments e
LEFT JOIN enrolment_required_topics rt ON rt.enrolment_id = e.enrolment_id
LEFT JOIN enrolment_covered_topics ct ON ct.enrolment_id = rt.enrolment_id AND ct.topic_id = rt.topic_id
GROUP BY e.enrolment_id;

CREATE VIEW enrolment_progress AS
SELECT e.enrolment_id, e.student_id, e.course_id, e.service_branch_id,
       d.delivered_sessions, d.planned_sessions,
       CASE WHEN d.planned_sessions > 0 THEN round(100.0 * d.delivered_sessions / d.planned_sessions, 1) END AS delivery_pct,
       a.delivered_since_joining, a.marked_sessions, a.unmarked_sessions,
       a.present_count, a.late_count, a.absent_count, a.excused_count, a.recovered_count,
       CASE WHEN a.delivered_since_joining = 0 THEN 'Not started'
            WHEN a.unmarked_sessions > 0 THEN 'Partial Data'
            ELSE 'Calculated' END AS attendance_state,
       CASE WHEN a.marked_sessions > 0
            THEN round(100.0 * (a.present_count + a.late_count) / a.marked_sessions, 1) END AS attendance_pct,
       COALESCE(a.marked_sessions >= 3
                AND 100.0 * (a.present_count + a.late_count) / NULLIF(a.marked_sessions, 0) < attendance_setting('attendance_alert_threshold', 75),
                FALSE) AS attendance_alert,
       r.required_topics, r.covered_topics,
       CASE WHEN r.required_topics > 0 THEN round(100.0 * r.covered_topics / r.required_topics, 1) END AS required_pct,
       g.events_recent, g.last_activity_at,
       CASE WHEN g.events_total = 0 THEN 'Not started'
            WHEN g.events_recent >= attendance_setting('engagement_high_events', 8) THEN 'High'
            WHEN g.events_recent >= attendance_setting('engagement_medium_events', 3) THEN 'Medium'
            ELSE 'Low' END AS engagement_level
FROM enrolments e
JOIN enrolment_delivery d ON d.enrolment_id = e.enrolment_id
JOIN enrolment_attendance a ON a.enrolment_id = e.enrolment_id
JOIN enrolment_required_learning r ON r.enrolment_id = e.enrolment_id
JOIN enrolment_engagement g ON g.enrolment_id = e.enrolment_id;

-- 109: UX phase U8, student Home and My Learning (docs/UX_PLAN.md)
-- Depends on: 030 (assignments, tests), 099 / 103 (enrolment_covered_topics, enrolment_batch_links), 107 (whatsapp_outbox)
--   topic_progress: one row per enrolment and topic of every curriculum version the enrolment follows. A topic is Done when the
--     student attended its class (or recovered it) or watched its recording, AND every required assignment and required test
--     of the topic in their batch is handed in. It replaces nothing: the four progress measures keep reading their own views.
--   material_changes.reply_by: the date the student is asked to answer a batch change by (set when the change goes to students).
-- Gap fix phase 7 starts at db/110.

CREATE VIEW topic_progress AS
WITH followed AS (
    SELECT enrolment_id, curriculum_version_id FROM enrolments WHERE curriculum_version_id IS NOT NULL
    UNION
    SELECT enrolment_id, curriculum_version_id FROM enrolment_tracks WHERE curriculum_version_id IS NOT NULL
), topics AS (
    SELECT f.enrolment_id, t.topic_id, m.module_id, m.curriculum_version_id, t.is_required
    FROM followed f
    JOIN curriculum_modules m ON m.curriculum_version_id = f.curriculum_version_id
    JOIN curriculum_topics t ON t.module_id = m.module_id
), signals AS (
    SELECT tp.*,
           EXISTS (SELECT 1 FROM enrolment_covered_topics c
                   WHERE c.enrolment_id = tp.enrolment_id AND c.topic_id = tp.topic_id) AS attended,
           EXISTS (SELECT 1 FROM activity_events a
                   JOIN recordings r ON r.recording_id = (a.detail ->> 'recording_id')::INT
                   JOIN class_sessions cs ON cs.session_id = r.session_id
                   WHERE a.enrolment_id = tp.enrolment_id AND a.kind = 'recording_view' AND cs.topic_id = tp.topic_id) AS recording_watched,
           (SELECT count(*) FROM assignments x
            WHERE x.topic_id = tp.topic_id AND x.is_required AND x.status = 'Released'
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)) AS required_assignments,
           (SELECT count(*) FROM assignments x
            WHERE x.topic_id = tp.topic_id AND x.is_required AND x.status = 'Released'
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)
              AND EXISTS (SELECT 1 FROM assignment_submissions s
                          WHERE s.assignment_id = x.assignment_id AND s.enrolment_id = tp.enrolment_id)) AS assignments_handed_in,
           (SELECT count(*) FROM tests x
            WHERE x.topic_id = tp.topic_id AND x.is_required
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)) AS required_tests,
           (SELECT count(*) FROM tests x
            WHERE x.topic_id = tp.topic_id AND x.is_required
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)
              AND EXISTS (SELECT 1 FROM test_attempts a
                          WHERE a.test_id = x.test_id AND a.enrolment_id = tp.enrolment_id AND a.status = 'Submitted')) AS tests_taken
    FROM topics tp
)
SELECT enrolment_id, topic_id, module_id, curriculum_version_id, is_required,
       attended, recording_watched,
       required_assignments, assignments_handed_in, required_tests, tests_taken,
       (attended OR recording_watched)
           AND assignments_handed_in >= required_assignments AND tests_taken >= required_tests AS is_done,
       CASE WHEN (attended OR recording_watched) AND assignments_handed_in >= required_assignments AND tests_taken >= required_tests THEN 'Done'
            WHEN attended OR recording_watched THEN 'Work to hand in'
            ELSE 'Not started' END AS status
FROM signals;

ALTER TABLE material_changes ADD COLUMN reply_by TIMESTAMPTZ;

INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('batch_change_reply_days', '7', 'How many days a student has to agree to or decline a batch change');

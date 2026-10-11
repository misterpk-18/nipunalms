-- 112: UX phase U12, the trainer's class flow (docs/UX_PLAN.md)
-- Depends on: 001 (users), 002 (curriculum_topics), 004 (class_sessions)
--   class_flow_progress: where a trainer stands in Today's guided flow for one class, and the half-finished class log, so a
--     refresh (or another device) resumes at the same step. One row per class while it is being run; the service deletes it when
--     the class is logged as delivered. The class's own state (Scheduled / Live / Delivered) stays the truth for what happened.
--   class_session_topics: the topics the trainer says were covered in a delivered class (the class log). The class keeps its one
--     planned topic (class_sessions.topic_id), which still drives student topic progress.
--   meet_events: a new event type, 'Link requested', for the trainer's one-click "no Meet link" request (the class flow).
-- Gap fix phase 7 starts at db/113.

CREATE TABLE class_flow_progress (
    session_id INT PRIMARY KEY REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    step VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (step IN ('open', 'join', 'attendance', 'log')),
    draft JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by INT REFERENCES users(user_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE class_session_topics (
    session_id INT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    topic_id INT NOT NULL REFERENCES curriculum_topics(topic_id),
    PRIMARY KEY (session_id, topic_id)
);

CREATE INDEX class_session_topics_topic_idx ON class_session_topics (topic_id);

ALTER TABLE meet_events DROP CONSTRAINT meet_events_event_type_check;
ALTER TABLE meet_events ADD CONSTRAINT meet_events_event_type_check
    CHECK (event_type IN ('Requested', 'Link associated', 'Association failed', 'Association retried', 'Link removed', 'Link requested'));

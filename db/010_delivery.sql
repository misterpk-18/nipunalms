-- Phase 2 / S1 Delivery (010): curriculum review trail, batch history, session changes, reschedule requests, Meet association log
-- Depends on: 004_batches_sessions.sql
-- No backbone table is altered; the rules below are added as triggers on the Phase 1 tables.

-- ---------------------------------------------------------------------------
-- Curriculum: review trail, and published versions are immutable snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE curriculum_events (
    event_id SERIAL PRIMARY KEY,
    curriculum_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('Created', 'Submitted', 'Returned', 'Approved', 'Activated', 'Retired')),
    from_status curriculum_status,
    to_status curriculum_status NOT NULL,
    actor_user_id INT REFERENCES users(user_id),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT curriculum_events_return_has_reason CHECK (action <> 'Returned' OR NULLIF(btrim(note), '') IS NOT NULL)
);

CREATE INDEX curriculum_events_version_idx ON curriculum_events (curriculum_version_id, created_at);

-- Modules and topics change only while their version is a Draft (a published version is a snapshot enrolments point at).
-- Inserts are not blocked here: the service adds content to a Draft, and the staging seed builds Active versions.
CREATE OR REPLACE FUNCTION curriculum_content_is_draft() RETURNS trigger AS $$
DECLARE
    v_status curriculum_status;
    v_label TEXT;
BEGIN
    IF TG_TABLE_NAME = 'curriculum_modules' THEN
        SELECT status, version_label INTO v_status, v_label FROM curriculum_versions
        WHERE curriculum_version_id = OLD.curriculum_version_id;
    ELSE
        SELECT v.status, v.version_label INTO v_status, v_label
        FROM curriculum_modules m JOIN curriculum_versions v ON v.curriculum_version_id = m.curriculum_version_id
        WHERE m.module_id = OLD.module_id;
    END IF;
    IF FOUND AND v_status <> 'Draft' THEN
        RAISE EXCEPTION 'Curriculum version % is % and can no longer be edited; create a new draft version', v_label, v_status;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curriculum_modules_draft_only
    BEFORE UPDATE OR DELETE ON curriculum_modules
    FOR EACH ROW EXECUTE FUNCTION curriculum_content_is_draft();

CREATE TRIGGER trg_curriculum_topics_draft_only
    BEFORE UPDATE OR DELETE ON curriculum_topics
    FOR EACH ROW EXECUTE FUNCTION curriculum_content_is_draft();

-- ---------------------------------------------------------------------------
-- Batches: history of state, readiness, trainer and curriculum changes, and a valid lifecycle
-- ---------------------------------------------------------------------------
CREATE TABLE batch_events (
    event_id SERIAL PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
    event_type VARCHAR(40) NOT NULL,                -- 'Created', 'State changed', 'Readiness changed', 'Trainer assigned', ...
    from_value VARCHAR(200),
    to_value VARCHAR(200),
    reason TEXT,
    actor_user_id INT REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX batch_events_batch_idx ON batch_events (batch_id, created_at);

-- Forming -> Starting -> Running <-> Full -> Completed; Cancelled from any open state. Completed and Cancelled are final.
CREATE OR REPLACE FUNCTION check_batch_transition() RETURNS trigger AS $$
DECLARE
    v_students INT;
    v_open_sessions INT;
BEGIN
    IF NEW.state = OLD.state THEN
        RETURN NEW;
    END IF;
    IF OLD.state IN ('Completed', 'Cancelled') THEN
        RAISE EXCEPTION 'Batch % is % and cannot change state', OLD.batch_code, OLD.state;
    END IF;
    IF NOT ((OLD.state = 'Forming' AND NEW.state IN ('Starting', 'Running', 'Full', 'Cancelled'))
         OR (OLD.state = 'Starting' AND NEW.state IN ('Running', 'Full', 'Cancelled'))
         OR (OLD.state IN ('Running', 'Full') AND NEW.state IN ('Running', 'Full', 'Completed', 'Cancelled'))) THEN
        RAISE EXCEPTION 'Batch % cannot move from % to %', OLD.batch_code, OLD.state, NEW.state;
    END IF;
    IF NEW.state IN ('Starting', 'Running', 'Full') AND NEW.readiness = 'Blocked' THEN
        RAISE EXCEPTION 'Batch % is Blocked (%) and cannot start until it is unblocked', NEW.batch_code, NEW.readiness_reason;
    END IF;
    IF NEW.state = 'Cancelled' THEN
        SELECT count(DISTINCT enrolment_id) INTO v_students FROM batch_allocations WHERE batch_id = NEW.batch_id AND status = 'Active';
        IF v_students > 0 THEN
            RAISE EXCEPTION 'Batch % still has % allocated student(s); transfer them before cancelling', NEW.batch_code, v_students;
        END IF;
    END IF;
    IF NEW.state = 'Completed' THEN
        SELECT count(*) INTO v_open_sessions FROM class_sessions
        WHERE batch_id = NEW.batch_id AND state IN ('Scheduled', 'Live', 'Rescheduled');
        IF v_open_sessions > 0 THEN
            RAISE EXCEPTION 'Batch % still has % open class session(s); deliver or cancel them before completing the batch', NEW.batch_code, v_open_sessions;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batches_transition
    BEFORE UPDATE OF state ON batches
    FOR EACH ROW EXECUTE FUNCTION check_batch_transition();

-- ---------------------------------------------------------------------------
-- Class sessions: lifecycle, topic must belong to the batch's course, one trainer cannot teach two classes at once
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION check_session_transition() RETURNS trigger AS $$
BEGIN
    IF NEW.state <> OLD.state AND NOT (
           (OLD.state IN ('Scheduled', 'Rescheduled') AND NEW.state IN ('Live', 'Delivered', 'Cancelled', 'Rescheduled'))
        OR (OLD.state = 'Live' AND NEW.state = 'Delivered')) THEN
        RAISE EXCEPTION 'Session % is % and cannot become %', OLD.session_code, OLD.state, NEW.state;
    END IF;
    IF OLD.state IN ('Live', 'Delivered', 'Cancelled')
       AND (NEW.starts_at <> OLD.starts_at OR NEW.ends_at <> OLD.ends_at OR NEW.trainer_user_id <> OLD.trainer_user_id) THEN
        RAISE EXCEPTION 'Session % is % and its time and trainer can no longer change', OLD.session_code, OLD.state;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_class_sessions_transition
    BEFORE UPDATE ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION check_session_transition();

CREATE OR REPLACE FUNCTION check_session_topic_and_trainer() RETURNS trigger AS $$
DECLARE
    v_topic_course INT;
    v_batch_course INT;
    v_clash class_sessions%ROWTYPE;
BEGIN
    IF NEW.topic_id IS NOT NULL THEN
        SELECT v.course_id INTO v_topic_course
        FROM curriculum_topics t
        JOIN curriculum_modules m ON m.module_id = t.module_id
        JOIN curriculum_versions v ON v.curriculum_version_id = m.curriculum_version_id
        WHERE t.topic_id = NEW.topic_id;
        SELECT course_id INTO v_batch_course FROM batches WHERE batch_id = NEW.batch_id;
        IF v_topic_course IS DISTINCT FROM v_batch_course THEN
            RAISE EXCEPTION 'The topic belongs to a different course than the batch';
        END IF;
    END IF;

    IF NEW.state IN ('Scheduled', 'Live', 'Rescheduled') THEN
        SELECT * INTO v_clash FROM class_sessions
        WHERE trainer_user_id = NEW.trainer_user_id AND session_id IS DISTINCT FROM NEW.session_id
          AND state IN ('Scheduled', 'Live', 'Rescheduled')
          AND starts_at < NEW.ends_at AND ends_at > NEW.starts_at
        LIMIT 1;
        IF FOUND THEN
            RAISE EXCEPTION 'The trainer already teaches % (%) at that time', v_clash.session_code, v_clash.title;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_class_sessions_topic_trainer
    BEFORE INSERT OR UPDATE OF topic_id, batch_id, trainer_user_id, starts_at, ends_at, state ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION check_session_topic_and_trainer();

CREATE INDEX class_sessions_state_idx ON class_sessions (state, starts_at);

-- ---------------------------------------------------------------------------
-- Session changes: every reschedule, cancellation and substitute trainer, with the reason and the original slot
-- ---------------------------------------------------------------------------
CREATE TABLE session_changes (
    change_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('Rescheduled', 'Cancelled', 'Trainer changed')),
    reason TEXT NOT NULL CHECK (NULLIF(btrim(reason), '') IS NOT NULL),
    old_starts_at TIMESTAMPTZ NOT NULL,
    old_ends_at TIMESTAMPTZ NOT NULL,
    new_starts_at TIMESTAMPTZ,
    new_ends_at TIMESTAMPTZ,
    old_trainer_user_id INT REFERENCES users(user_id),
    new_trainer_user_id INT REFERENCES users(user_id),
    notice_hours NUMERIC(8,1) NOT NULL,             -- hours between the change and the original start (negative: after it)
    short_notice BOOLEAN NOT NULL DEFAULT FALSE,    -- less than 24 hours' notice (Module 15 §14)
    changed_by INT REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT session_changes_reschedule_has_new_slot CHECK (
        change_type <> 'Rescheduled' OR (new_starts_at IS NOT NULL AND new_ends_at IS NOT NULL AND new_ends_at > new_starts_at)),
    CONSTRAINT session_changes_trainer_has_new_trainer CHECK (change_type <> 'Trainer changed' OR new_trainer_user_id IS NOT NULL)
);

CREATE INDEX session_changes_session_idx ON session_changes (session_id, created_at);

-- ---------------------------------------------------------------------------
-- Reschedule requests: a trainer asks, an Academic Coordinator / Branch Manager decides
-- ---------------------------------------------------------------------------
CREATE TYPE reschedule_request_status AS ENUM ('Open', 'Approved', 'Rejected');

CREATE TABLE session_change_requests (
    request_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    requested_by INT NOT NULL REFERENCES users(user_id),
    proposed_starts_at TIMESTAMPTZ NOT NULL,
    proposed_ends_at TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL CHECK (NULLIF(btrim(reason), '') IS NOT NULL),
    status reschedule_request_status NOT NULL DEFAULT 'Open',
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT session_change_requests_slot CHECK (proposed_ends_at > proposed_starts_at),
    CONSTRAINT session_change_requests_decision CHECK ((status = 'Open') = (decided_at IS NULL)),
    CONSTRAINT session_change_requests_rejection_has_note CHECK (status <> 'Rejected' OR NULLIF(btrim(decision_note), '') IS NOT NULL)
);

-- A session has at most one open request at a time
CREATE UNIQUE INDEX session_change_requests_one_open ON session_change_requests (session_id) WHERE status = 'Open';
CREATE INDEX session_change_requests_status_idx ON session_change_requests (status, created_at);

-- ---------------------------------------------------------------------------
-- Meet association log: the LMS records the state; it never calls Google
-- ---------------------------------------------------------------------------
CREATE TABLE meet_events (
    event_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('Requested', 'Link associated', 'Association failed', 'Association retried', 'Link removed')),
    meet_status meet_status NOT NULL,               -- the session's status after the event
    organizer_email VARCHAR(255),                   -- the branch organizer mailbox at the time (Module 16 §2)
    meet_link VARCHAR(500),
    detail TEXT,
    actor_user_id INT REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX meet_events_session_idx ON meet_events (session_id, created_at);

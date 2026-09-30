-- Phase 1a / 004: batches, trainers, allocations, class sessions
-- Depends on: 003_students_enrolments.sql

-- ---------------------------------------------------------------------------
-- Batches
-- ---------------------------------------------------------------------------
CREATE TYPE batch_state AS ENUM ('Forming', 'Starting', 'Running', 'Full', 'Completed', 'Cancelled');
CREATE TYPE batch_readiness AS ENUM ('Ready', 'Blocked', 'Pending Verification');

CREATE TABLE batches (
    batch_id SERIAL PRIMARY KEY,
    batch_code VARCHAR(40) UNIQUE NOT NULL,         -- 'NIT-GNT-BAT-2026-000001'; also what the CRM stores as batches.lms_course_id
    crm_batch_id VARCHAR(100) UNIQUE,               -- the CRM batch this LMS batch is linked to
    crm_linked_at TIMESTAMPTZ,                      -- when the link was made (filled by trigger)
    course_id INT NOT NULL REFERENCES courses(course_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),
    curriculum_version_id INT REFERENCES curriculum_versions(curriculum_version_id),  -- NULL = mapping pending
    capacity INT NOT NULL CHECK (capacity > 0),
    mode delivery_mode NOT NULL DEFAULT 'Classroom',
    planned_start DATE,
    planned_end DATE,
    state batch_state NOT NULL DEFAULT 'Forming',
    readiness batch_readiness NOT NULL DEFAULT 'Ready',
    readiness_reason TEXT,                          -- why it is Blocked / Pending Verification
    recovery_owner VARCHAR(100),                    -- who resolves a blocked batch
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT batches_dates CHECK (planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start),
    CONSTRAINT batches_not_ready_has_reason CHECK (readiness = 'Ready' OR readiness_reason IS NOT NULL)
);

CREATE INDEX batches_branch_state_idx ON batches (branch_id, state);
CREATE INDEX batches_course_idx ON batches (course_id);

CREATE TRIGGER trg_batches_updated_at
    BEFORE UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- NIT-<BRANCH>-BAT-YYYY-NNNNNN when not supplied
CREATE OR REPLACE FUNCTION next_batch_code(p_branch_id INT) RETURNS TEXT AS $$
DECLARE
    v_short TEXT;
    v_year INT := business_year();
    v_code TEXT;
BEGIN
    SELECT short_code INTO v_short FROM branches WHERE branch_id = p_branch_id;
    LOOP
        v_code := 'NIT-' || v_short || '-BAT-' || v_year || '-' || lpad(next_counter_value('BAT-' || v_short || '-' || v_year)::TEXT, 6, '0');
        EXIT WHEN NOT EXISTS (SELECT 1 FROM batches WHERE batch_code = v_code);
    END LOOP;
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION batches_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.batch_code = COALESCE(NEW.batch_code, next_batch_code(NEW.branch_id));
    ELSIF NEW.batch_code <> OLD.batch_code THEN
        RAISE EXCEPTION 'batch_code cannot change (the CRM stores it)';
    END IF;

    -- Linking a CRM batch: stamp the time and queue BatchLinked for the CRM
    IF NEW.crm_batch_id IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.crm_batch_id IS DISTINCT FROM OLD.crm_batch_id) THEN
        NEW.crm_linked_at = CURRENT_TIMESTAMP;
        INSERT INTO crm_outbox (event_type, payload)
        VALUES ('BatchLinked', jsonb_build_object('crm_batch_id', NEW.crm_batch_id, 'lms_course_id', NEW.batch_code));
    END IF;

    -- Seats already taken cannot exceed a reduced capacity
    IF TG_OP = 'UPDATE' AND NEW.capacity < OLD.capacity
       AND (SELECT count(DISTINCT enrolment_id) FROM batch_allocations WHERE batch_id = NEW.batch_id AND status = 'Active') > NEW.capacity THEN
        RAISE EXCEPTION 'Capacity cannot be lower than the students already allocated';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- Batch trainers
-- ---------------------------------------------------------------------------
CREATE TYPE batch_trainer_role AS ENUM ('Lead', 'Co-trainer');

CREATE TABLE batch_trainers (
    batch_trainer_id SERIAL PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
    trainer_user_id INT NOT NULL REFERENCES users(user_id),
    role batch_trainer_role NOT NULL DEFAULT 'Co-trainer',
    from_date DATE NOT NULL DEFAULT CURRENT_DATE,
    to_date DATE,                                   -- NULL = still assigned

    CONSTRAINT batch_trainers_dates CHECK (to_date IS NULL OR to_date >= from_date)
);

CREATE UNIQUE INDEX batch_trainers_one_live ON batch_trainers (batch_id, trainer_user_id) WHERE to_date IS NULL;
CREATE UNIQUE INDEX batch_trainers_one_lead ON batch_trainers (batch_id) WHERE role = 'Lead' AND to_date IS NULL;
CREATE INDEX batch_trainers_user_idx ON batch_trainers (trainer_user_id);

-- Only someone holding the Trainer role at the batch's branch can be assigned
CREATE OR REPLACE FUNCTION check_batch_trainer() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM user_role_scopes s
        JOIN roles r ON r.role_id = s.role_id
        JOIN batches b ON b.batch_id = NEW.batch_id
        WHERE s.user_id = NEW.trainer_user_id AND r.role_code = 'TRAINER' AND s.branch_id = b.branch_id
          AND s.revoked_at IS NULL AND (s.expires_at IS NULL OR s.expires_at > CURRENT_TIMESTAMP)
    ) THEN
        RAISE EXCEPTION 'Trainer must hold the Trainer role at the batch''s branch';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_trainers_check
    BEFORE INSERT OR UPDATE OF batch_id, trainer_user_id ON batch_trainers
    FOR EACH ROW EXECUTE FUNCTION check_batch_trainer();

-- ---------------------------------------------------------------------------
-- Allocations: enrolment (or one track of it) <-> batch, history retained
-- ---------------------------------------------------------------------------
CREATE TYPE allocation_status AS ENUM ('Active', 'Ended', 'Transferred');

CREATE TABLE batch_allocations (
    allocation_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    enrolment_track_id INT REFERENCES enrolment_tracks(enrolment_track_id),
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    status allocation_status NOT NULL DEFAULT 'Active',
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    reason TEXT,
    created_by INT REFERENCES users(user_id),       -- NULL when made by a CRM event
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT batch_allocations_end_matches_status CHECK ((status = 'Active') = (effective_to IS NULL)),
    CONSTRAINT batch_allocations_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

-- One active allocation per enrolment (per track, for allocations made track by track)
CREATE UNIQUE INDEX batch_allocations_one_active
    ON batch_allocations (enrolment_id, COALESCE(enrolment_track_id, 0)) WHERE status = 'Active';
CREATE INDEX batch_allocations_batch_idx ON batch_allocations (batch_id, status);

-- An active allocation needs a matching course and branch, an open batch, and a free seat
CREATE OR REPLACE FUNCTION check_batch_allocation() RETURNS trigger AS $$
DECLARE
    v_batch batches%ROWTYPE;
    v_enrolment enrolments%ROWTYPE;
    v_taken INT;
BEGIN
    IF NEW.status <> 'Active' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO v_batch FROM batches WHERE batch_id = NEW.batch_id FOR UPDATE;  -- serialise seat counting
    SELECT * INTO v_enrolment FROM enrolments WHERE enrolment_id = NEW.enrolment_id;

    IF v_batch.course_id <> v_enrolment.course_id THEN
        RAISE EXCEPTION 'Batch % is for a different course than this enrolment', v_batch.batch_code;
    END IF;
    IF v_batch.branch_id <> v_enrolment.service_branch_id THEN
        RAISE EXCEPTION 'Batch % is at a different branch than the enrolment''s service branch', v_batch.batch_code;
    END IF;
    IF v_batch.state IN ('Completed', 'Cancelled') THEN
        RAISE EXCEPTION 'Batch % is % and cannot take new students', v_batch.batch_code, v_batch.state;
    END IF;
    IF NEW.enrolment_track_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM enrolment_tracks WHERE enrolment_track_id = NEW.enrolment_track_id AND enrolment_id = NEW.enrolment_id) THEN
        RAISE EXCEPTION 'Track does not belong to this enrolment';
    END IF;

    SELECT count(DISTINCT enrolment_id) INTO v_taken FROM batch_allocations
    WHERE batch_id = NEW.batch_id AND status = 'Active' AND allocation_id IS DISTINCT FROM NEW.allocation_id
      AND enrolment_id <> NEW.enrolment_id;
    IF v_taken >= v_batch.capacity THEN
        RAISE EXCEPTION 'Batch % is full (% of % seats taken)', v_batch.batch_code, v_taken, v_batch.capacity;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_allocations_check
    BEFORE INSERT OR UPDATE OF batch_id, enrolment_id, enrolment_track_id, status ON batch_allocations
    FOR EACH ROW EXECUTE FUNCTION check_batch_allocation();

CREATE TRIGGER trg_batches_write
    BEFORE INSERT OR UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION batches_before_write();

-- ---------------------------------------------------------------------------
-- Class sessions: the actual sessions delivered (or to be delivered) to a batch
-- ---------------------------------------------------------------------------
CREATE TYPE session_state AS ENUM ('Scheduled', 'Live', 'Delivered', 'Cancelled', 'Rescheduled');
CREATE TYPE meet_status AS ENUM ('Not Required', 'Pending Verification', 'Linked', 'Unavailable');

CREATE TABLE class_sessions (
    session_id SERIAL PRIMARY KEY,
    session_code VARCHAR(30) UNIQUE NOT NULL,       -- 'SES-000101'
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    topic_id INT REFERENCES curriculum_topics(topic_id),
    title VARCHAR(200) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    mode delivery_mode NOT NULL,
    trainer_user_id INT NOT NULL REFERENCES users(user_id),
    room VARCHAR(100),
    meet_link VARCHAR(500),
    meet_status meet_status NOT NULL DEFAULT 'Not Required',
    state session_state NOT NULL DEFAULT 'Scheduled',
    delivered_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT class_sessions_time CHECK (ends_at > starts_at),
    CONSTRAINT class_sessions_delivered_at CHECK ((state = 'Delivered') = (delivered_at IS NOT NULL)),
    CONSTRAINT class_sessions_meet_link CHECK (meet_link IS NULL OR meet_status = 'Linked'),
    CONSTRAINT class_sessions_classroom_no_meet CHECK (mode <> 'Classroom' OR meet_status = 'Not Required')
);

CREATE INDEX class_sessions_batch_idx ON class_sessions (batch_id, starts_at);
CREATE INDEX class_sessions_trainer_idx ON class_sessions (trainer_user_id, starts_at);

CREATE TRIGGER trg_class_sessions_updated_at
    BEFORE UPDATE ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION class_sessions_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.session_code IS NULL THEN
        LOOP
            NEW.session_code = 'SES-' || lpad(next_counter_value('SES')::TEXT, 6, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM class_sessions WHERE session_code = NEW.session_code);
        END LOOP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM batch_trainers WHERE batch_id = NEW.batch_id AND trainer_user_id = NEW.trainer_user_id) THEN
        RAISE EXCEPTION 'The session trainer must be assigned to the batch';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_class_sessions_write
    BEFORE INSERT OR UPDATE OF batch_id, trainer_user_id ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION class_sessions_before_write();

-- Phase 1a / 003: students, activation, CRM admission projection, enrolments, finance summaries, CRM inbox and outbox
-- Depends on: 002_catalog_curriculum.sql

CREATE TYPE delivery_mode AS ENUM ('Classroom', 'Live Online', 'Hybrid');

-- ---------------------------------------------------------------------------
-- Students: one row per CRM Person = one LMS account
-- ---------------------------------------------------------------------------
CREATE TYPE student_activation_status AS ENUM ('Account Created', 'Activation Pending', 'Activated', 'Suspended');

CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    student_code VARCHAR(30) UNIQUE NOT NULL,       -- 'NIT-STU-2026-004182': the Student ID the learner signs in with
    crm_person_id VARCHAR(100) UNIQUE NOT NULL,     -- link key to the CRM Person
    lms_user_id VARCHAR(100) UNIQUE NOT NULL,       -- what the CRM stores as persons.lms_user_id; equals student_code
    provisioned_at TIMESTAMPTZ,                     -- when the LMS login was first created (CRM persons.lms_provisioned_at)
    full_name VARCHAR(150) NOT NULL,
    name_te VARCHAR(200),                           -- name in Telugu script
    email VARCHAR(255),                             -- optional; never blocks provisioning
    mobile VARCHAR(30),                             -- not unique: a family mobile is not identity proof
    original_branch_id INT NOT NULL REFERENCES branches(branch_id),
    service_branch_id INT NOT NULL REFERENCES branches(branch_id),
    preferred_language VARCHAR(2) NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en', 'te')),
    activation_status student_activation_status NOT NULL DEFAULT 'Account Created',
    mfa_status VARCHAR(30) NOT NULL DEFAULT 'Not Configured' CHECK (mfa_status IN ('Not Configured', 'Enabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT students_activated_needs_account CHECK (activation_status NOT IN ('Activated', 'Suspended') OR provisioned_at IS NOT NULL)
);

CREATE INDEX students_service_branch_idx ON students (service_branch_id);

CREATE TRIGGER trg_students_updated_at
    BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE users ADD CONSTRAINT users_student_fk FOREIGN KEY (student_id) REFERENCES students(student_id);
ALTER TABLE activity_events
    ADD CONSTRAINT activity_events_student_fk FOREIGN KEY (student_id) REFERENCES students(student_id);

-- NIT-STU-YYYY-NNNNNN when not supplied; skips codes already taken (e.g., migrated or seeded students)
CREATE OR REPLACE FUNCTION next_student_code() RETURNS TEXT AS $$
DECLARE
    v_year INT := business_year();
    v_code TEXT;
BEGIN
    LOOP
        v_code := 'NIT-STU-' || v_year || '-' || lpad(next_counter_value('STU-' || v_year)::TEXT, 6, '0');
        EXIT WHEN NOT EXISTS (SELECT 1 FROM students WHERE student_code = v_code);
    END LOOP;
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION students_before_insert() RETURNS trigger AS $$
BEGIN
    NEW.student_code = COALESCE(NEW.student_code, next_student_code());
    NEW.lms_user_id = COALESCE(NEW.lms_user_id, NEW.student_code);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_students_codes
    BEFORE INSERT ON students
    FOR EACH ROW EXECUTE FUNCTION students_before_insert();

-- Identifiers are stable and never reused: they cannot change and a student cannot be deleted
CREATE OR REPLACE FUNCTION students_keep_identifiers() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Students are never deleted (their IDs are never reused)';
    END IF;
    IF NEW.student_code <> OLD.student_code OR NEW.lms_user_id <> OLD.lms_user_id OR NEW.crm_person_id <> OLD.crm_person_id THEN
        RAISE EXCEPTION 'student_code, lms_user_id and crm_person_id cannot change';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_students_identifiers
    BEFORE UPDATE OR DELETE ON students
    FOR EACH ROW EXECUTE FUNCTION students_keep_identifiers();

-- ---------------------------------------------------------------------------
-- Activation tokens: only the hash is stored; single use; expiring
-- ---------------------------------------------------------------------------
CREATE TABLE student_activations (
    activation_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    token_hash VARCHAR(64) UNIQUE NOT NULL,         -- SHA-256 of the token
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('CRM provisioning', 'Staff issued')),
    issued_by INT REFERENCES users(user_id),        -- NULL when issued by CRM provisioning
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,                         -- replaced by a reissue
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- At most one outstanding (unused, unrevoked) token per student
CREATE UNIQUE INDEX student_activations_one_outstanding
    ON student_activations (student_id) WHERE used_at IS NULL AND revoked_at IS NULL;

-- ---------------------------------------------------------------------------
-- Admissions: the CRM Admission as projected into the LMS
-- ---------------------------------------------------------------------------
CREATE TYPE crm_admission_status AS ENUM ('Active', 'Paused', 'Cancelled');

CREATE TABLE admissions (
    admission_id SERIAL PRIMARY KEY,
    crm_admission_id VARCHAR(100) UNIQUE NOT NULL,
    admission_code VARCHAR(50) UNIQUE NOT NULL,     -- 'ADM-GNT-2026-000214'
    student_id INT NOT NULL REFERENCES students(student_id),
    course_id INT NOT NULL REFERENCES courses(course_id),
    original_branch_id INT NOT NULL REFERENCES branches(branch_id),
    service_branch_id INT NOT NULL REFERENCES branches(branch_id),     -- where the learner is taught
    collecting_branch_id INT NOT NULL REFERENCES branches(branch_id),  -- where the fee was collected
    crm_status crm_admission_status NOT NULL DEFAULT 'Active',
    mode delivery_mode NOT NULL DEFAULT 'Classroom',
    admission_date DATE,
    source_version INT NOT NULL CHECK (source_version >= 1),           -- older CRM events are ignored
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX admissions_student_idx ON admissions (student_id);
CREATE INDEX admissions_service_branch_idx ON admissions (service_branch_id);

CREATE TRIGGER trg_admissions_updated_at
    BEFORE UPDATE ON admissions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Enrolments: what the learner actually studies, per course
-- ---------------------------------------------------------------------------
CREATE TYPE enrolment_kind AS ENUM ('Combo', 'Standalone', 'Separately purchased', 'Complimentary');
CREATE TYPE enrolment_status AS ENUM (
    'Provisioning Pending', 'Curriculum Mapping Pending', 'Allocation Pending',
    'Allocated — awaiting first regular class', 'Active', 'Paused', 'Completed', 'Withdrawn'
);

CREATE TABLE enrolments (
    enrolment_id SERIAL PRIMARY KEY,
    enrolment_code VARCHAR(30) UNIQUE NOT NULL,     -- 'ENR-000123'
    admission_id INT NOT NULL REFERENCES admissions(admission_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    course_id INT NOT NULL REFERENCES courses(course_id),
    kind enrolment_kind NOT NULL,
    parent_enrolment_id INT REFERENCES enrolments(enrolment_id),  -- complimentary -> the qualifying paid enrolment
    curriculum_version_id INT REFERENCES curriculum_versions(curriculum_version_id),
    service_branch_id INT NOT NULL REFERENCES branches(branch_id),
    mode delivery_mode NOT NULL DEFAULT 'Classroom',
    status enrolment_status NOT NULL,
    joining_date DATE,                              -- first regular class attended (demos excluded)
    access_start DATE,
    access_end DATE,
    certificate_status VARCHAR(100) NOT NULL DEFAULT 'Not Yet Eligible',
    benefit_gate_met BOOLEAN,                       -- complimentary only: has the qualifying payment gate been met
    benefit_note TEXT,                              -- why a benefit is pending / the offer it comes from
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT enrolments_one_per_course UNIQUE (admission_id, course_id),
    CONSTRAINT enrolments_complimentary_has_parent CHECK ((kind = 'Complimentary') = (parent_enrolment_id IS NOT NULL)),
    CONSTRAINT enrolments_gate_only_complimentary CHECK (kind = 'Complimentary' OR benefit_gate_met IS NULL),
    CONSTRAINT enrolments_gate_blocks_access CHECK (benefit_gate_met IS DISTINCT FROM FALSE OR status IN ('Provisioning Pending', 'Withdrawn')),
    CONSTRAINT enrolments_active_has_joining_date CHECK (status <> 'Active' OR joining_date IS NOT NULL),
    CONSTRAINT enrolments_access_dates CHECK (access_end IS NULL OR access_start IS NULL OR access_end >= access_start)
);

CREATE INDEX enrolments_student_idx ON enrolments (student_id);
CREATE INDEX enrolments_admission_idx ON enrolments (admission_id);
CREATE INDEX enrolments_branch_status_idx ON enrolments (service_branch_id, status);

CREATE TRIGGER trg_enrolments_updated_at
    BEFORE UPDATE ON enrolments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE activity_events
    ADD CONSTRAINT activity_events_enrolment_fk FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id);

CREATE OR REPLACE FUNCTION enrolments_before_insert() RETURNS trigger AS $$
BEGIN
    IF NEW.enrolment_code IS NULL THEN
        LOOP
            NEW.enrolment_code = 'ENR-' || lpad(next_counter_value('ENR')::TEXT, 6, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM enrolments WHERE enrolment_code = NEW.enrolment_code);
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolments_code
    BEFORE INSERT ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_before_insert();

-- The enrolment must agree with its admission and course; a complimentary one hangs off a paid one of the same admission
CREATE OR REPLACE FUNCTION check_enrolment_links() RETURNS trigger AS $$
DECLARE
    v_admission_student INT;
    v_is_combo BOOLEAN;
    v_parent enrolments%ROWTYPE;
BEGIN
    SELECT student_id INTO v_admission_student FROM admissions WHERE admission_id = NEW.admission_id;
    IF v_admission_student <> NEW.student_id THEN
        RAISE EXCEPTION 'Enrolment student does not match the admission student';
    END IF;

    SELECT is_combo INTO v_is_combo FROM courses WHERE course_id = NEW.course_id;
    IF (NEW.kind = 'Combo') <> v_is_combo THEN
        RAISE EXCEPTION 'Only a combo course has a Combo enrolment (and every combo course must use one)';
    END IF;

    IF NEW.parent_enrolment_id IS NOT NULL THEN
        SELECT * INTO v_parent FROM enrolments WHERE enrolment_id = NEW.parent_enrolment_id;
        IF v_parent.admission_id <> NEW.admission_id OR v_parent.kind = 'Complimentary' THEN
            RAISE EXCEPTION 'A complimentary enrolment must link to a paid enrolment of the same admission';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolments_links
    BEFORE INSERT OR UPDATE OF admission_id, student_id, course_id, kind, parent_enrolment_id ON enrolments
    FOR EACH ROW EXECUTE FUNCTION check_enrolment_links();

-- Combo enrolment -> the tracks it includes, each with its own curriculum version
CREATE TABLE enrolment_tracks (
    enrolment_track_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id) ON DELETE CASCADE,
    component_id INT NOT NULL REFERENCES course_components(component_id),
    curriculum_version_id INT REFERENCES curriculum_versions(curriculum_version_id),  -- NULL = mapping pending

    CONSTRAINT enrolment_tracks_unique UNIQUE (enrolment_id, component_id)
);

-- ---------------------------------------------------------------------------
-- Finance summaries: read-only projection of what the CRM sends; the LMS never edits money
-- ---------------------------------------------------------------------------
CREATE TABLE finance_summaries (
    admission_id INT PRIMARY KEY REFERENCES admissions(admission_id),
    fee_total NUMERIC(12,2) NOT NULL CHECK (fee_total >= 0),
    verified_paid NUMERIC(12,2) NOT NULL CHECK (verified_paid >= 0),
    balance NUMERIC(12,2) NOT NULL,
    next_due_date DATE,
    next_due_amount NUMERIC(12,2) CHECK (next_due_amount >= 0),
    receipts JSONB NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(receipts) = 'array'),  -- [{receipt_number, date, amount}]
    as_of TIMESTAMPTZ NOT NULL,                     -- when the CRM computed it
    source_version INT NOT NULL CHECK (source_version >= 1),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_finance_summaries_updated_at
    BEFORE UPDATE ON finance_summaries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- CRM inbox: every event received, with its outcome
-- ---------------------------------------------------------------------------
CREATE TYPE crm_event_status AS ENUM ('Received', 'Applied', 'Ignored — stale', 'Failed');

CREATE TABLE crm_events (
    crm_event_id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,          -- the CRM's event ID: idempotency key
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN
        ('CourseUpserted', 'AdmissionQualified', 'AdmissionUpdated', 'AdmissionCancelled', 'FinanceSummaryUpdated')),
    source_version INT NOT NULL CHECK (source_version >= 1),
    occurred_at TIMESTAMPTZ NOT NULL,               -- original event time (kept on retry)
    payload JSONB NOT NULL,
    status crm_event_status NOT NULL DEFAULT 'Received',
    result JSONB,                                   -- what applying it produced (IDs, statuses); returned on replay
    error TEXT,
    retries INT NOT NULL DEFAULT 0 CHECK (retries >= 0),
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,

    CONSTRAINT crm_events_failed_has_error CHECK (status <> 'Failed' OR error IS NOT NULL)
);

CREATE INDEX crm_events_status_idx ON crm_events (status, received_at DESC);

-- ---------------------------------------------------------------------------
-- CRM outbox: values the CRM stores about the LMS (persons.lms_user_id, admissions.lms_status, batches.lms_course_id).
-- Rows are written in the same transaction as the change; a delivery worker is not built yet.
-- ---------------------------------------------------------------------------
CREATE TYPE outbox_status AS ENUM ('Pending', 'Delivered', 'Failed');

CREATE TABLE crm_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('LmsAccountProvisioned', 'AdmissionLmsStatusChanged', 'BatchLinked')),
    payload JSONB NOT NULL,
    status outbox_status NOT NULL DEFAULT 'Pending',
    attempts INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMPTZ,

    CONSTRAINT crm_outbox_delivered CHECK ((status = 'Delivered') = (delivered_at IS NOT NULL))
);

CREATE INDEX crm_outbox_status_idx ON crm_outbox (status, created_at);

-- A student login was created: tell the CRM which LMS ID belongs to the Person
CREATE OR REPLACE FUNCTION students_outbox_provisioned() RETURNS trigger AS $$
BEGIN
    IF NEW.provisioned_at IS NOT NULL AND (TG_OP = 'INSERT' OR OLD.provisioned_at IS NULL) THEN
        INSERT INTO crm_outbox (event_type, payload)
        VALUES ('LmsAccountProvisioned', jsonb_build_object(
            'crm_person_id', NEW.crm_person_id, 'lms_user_id', NEW.lms_user_id, 'provisioned_at', NEW.provisioned_at));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_students_outbox_provisioned
    AFTER INSERT OR UPDATE OF provisioned_at ON students
    FOR EACH ROW EXECUTE FUNCTION students_outbox_provisioned();

-- ---------------------------------------------------------------------------
-- Per-admission LMS status, in the CRM's own vocabulary (admissions.lms_status in the CRM)
--   Not Created  no LMS login exists yet
--   Invited      login created, student has not activated it
--   Active       activated, and a course of this admission is running (not Paused / Completed / Withdrawn)
--   Inactive     student suspended, or every course of this admission is Paused / Withdrawn
--   Completed    every non-withdrawn course of this admission is Completed
-- ---------------------------------------------------------------------------
CREATE TYPE lms_status AS ENUM ('Not Created', 'Invited', 'Active', 'Inactive', 'Completed');

CREATE OR REPLACE FUNCTION compute_admission_lms_status(p_admission_id INT) RETURNS lms_status AS $$
DECLARE
    v_student students%ROWTYPE;
    v_live INT;
    v_completed INT;
    v_running INT;
BEGIN
    SELECT s.* INTO v_student FROM students s JOIN admissions a ON a.student_id = s.student_id WHERE a.admission_id = p_admission_id;
    IF NOT FOUND OR v_student.provisioned_at IS NULL THEN
        RETURN 'Not Created';
    END IF;

    SELECT count(*) FILTER (WHERE status <> 'Withdrawn'),
           count(*) FILTER (WHERE status = 'Completed'),
           count(*) FILTER (WHERE status NOT IN ('Withdrawn', 'Completed', 'Paused'))
    INTO v_live, v_completed, v_running
    FROM enrolments WHERE admission_id = p_admission_id;

    IF v_student.activation_status = 'Suspended' OR v_live = 0 THEN
        RETURN 'Inactive';
    ELSIF v_completed = v_live THEN
        RETURN 'Completed';
    ELSIF v_student.activation_status <> 'Activated' THEN
        RETURN 'Invited';
    ELSIF v_running > 0 THEN
        RETURN 'Active';
    END IF;
    RETURN 'Inactive';
END;
$$ LANGUAGE plpgsql STABLE;

-- Last learning activity of the student on this admission (activity tied to its enrolments, or to the student in general)
CREATE OR REPLACE FUNCTION admission_last_activity(p_admission_id INT) RETURNS TIMESTAMPTZ AS $$
    SELECT max(e.occurred_at)
    FROM activity_events e
    JOIN admissions a ON a.student_id = e.student_id
    WHERE a.admission_id = p_admission_id
      AND (e.enrolment_id IS NULL OR e.enrolment_id IN (SELECT enrolment_id FROM enrolments WHERE admission_id = p_admission_id));
$$ LANGUAGE sql STABLE;

CREATE VIEW admission_lms_status AS
SELECT a.admission_id,
       a.crm_admission_id,
       a.student_id,
       compute_admission_lms_status(a.admission_id) AS lms_status,
       admission_last_activity(a.admission_id) AS lms_last_activity_at,
       CURRENT_TIMESTAMP AS computed_at
FROM admissions a;

-- Last status sent / to send to the CRM per admission, so a change is detected exactly once
CREATE TABLE admission_lms_state (
    admission_id INT PRIMARY KEY REFERENCES admissions(admission_id),
    lms_status lms_status NOT NULL,
    last_activity_at TIMESTAMPTZ,
    status_changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Recompute one admission: keep the state row current and queue AdmissionLmsStatusChanged when the status changed
CREATE OR REPLACE FUNCTION refresh_admission_lms_state(p_admission_id INT) RETURNS void AS $$
DECLARE
    v_new lms_status := compute_admission_lms_status(p_admission_id);
    v_last TIMESTAMPTZ := admission_last_activity(p_admission_id);
    v_old lms_status;
    v_crm_admission_id VARCHAR(100);
BEGIN
    SELECT lms_status INTO v_old FROM admission_lms_state WHERE admission_id = p_admission_id;

    INSERT INTO admission_lms_state (admission_id, lms_status, last_activity_at)
    VALUES (p_admission_id, v_new, v_last)
    ON CONFLICT (admission_id) DO UPDATE SET
        lms_status = EXCLUDED.lms_status,
        last_activity_at = EXCLUDED.last_activity_at,
        status_changed_at = CASE WHEN admission_lms_state.lms_status <> EXCLUDED.lms_status
                                 THEN CURRENT_TIMESTAMP ELSE admission_lms_state.status_changed_at END;

    IF v_new IS DISTINCT FROM COALESCE(v_old, 'Not Created') THEN
        SELECT crm_admission_id INTO v_crm_admission_id FROM admissions WHERE admission_id = p_admission_id;
        INSERT INTO crm_outbox (event_type, payload)
        VALUES ('AdmissionLmsStatusChanged', jsonb_build_object(
            'crm_admission_id', v_crm_admission_id, 'lms_status', v_new,
            'lms_last_activity_at', v_last, 'synced_at', CURRENT_TIMESTAMP));
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION enrolments_refresh_lms_state() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_admission_lms_state(NEW.admission_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolments_lms_state
    AFTER INSERT OR UPDATE OF status ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_refresh_lms_state();

CREATE OR REPLACE FUNCTION students_refresh_lms_state() RETURNS trigger AS $$
DECLARE
    v_admission_id INT;
BEGIN
    FOR v_admission_id IN SELECT admission_id FROM admissions WHERE student_id = NEW.student_id LOOP
        PERFORM refresh_admission_lms_state(v_admission_id);
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_students_lms_state
    AFTER UPDATE OF activation_status, provisioned_at ON students
    FOR EACH ROW EXECUTE FUNCTION students_refresh_lms_state();

-- New learning activity moves "last activity" on the student's admissions (no CRM event: status did not change)
CREATE OR REPLACE FUNCTION activity_refresh_lms_state() RETURNS trigger AS $$
DECLARE
    v_admission_id INT;
BEGIN
    FOR v_admission_id IN
        SELECT admission_id FROM admissions WHERE student_id = NEW.student_id
          AND (NEW.enrolment_id IS NULL OR admission_id = (SELECT admission_id FROM enrolments WHERE enrolment_id = NEW.enrolment_id))
    LOOP
        PERFORM refresh_admission_lms_state(v_admission_id);
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_activity_lms_state
    AFTER INSERT ON activity_events
    FOR EACH ROW EXECUTE FUNCTION activity_refresh_lms_state();

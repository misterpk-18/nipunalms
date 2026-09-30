-- Phase 2 / 050: student services (support requests, notification preferences, placement & career support, Ask Nipuna usage)
-- Depends on: 001 (users, notifications, app_settings), 003 (students, enrolments), 002 (courses), 004 (batches)

-- ---------------------------------------------------------------------------
-- Backbone additions: notification channel, settings used by this slice
-- ---------------------------------------------------------------------------
-- In-app is the only channel that delivers today; WhatsApp / email notices are recorded against their (unverified)
-- integration so the centre can show them as "not sent" instead of pretending they were delivered.
ALTER TABLE notifications
    ADD COLUMN channel VARCHAR(20) NOT NULL DEFAULT 'In-app' CHECK (channel IN ('In-app', 'WhatsApp', 'Email')),
    ADD COLUMN delivery_note TEXT;

ALTER TABLE notifications ADD CONSTRAINT notifications_failed_has_note
    CHECK (delivery_status <> 'Failed' OR delivery_note IS NOT NULL);

-- Module 24 approved pilot limits: 50 successful student responses and 100 staff responses per IST day
UPDATE app_settings SET setting_value = '50', description = 'Ask Nipuna answers per student per IST day (approved pilot limit)'
    WHERE setting_key = 'ai_daily_limit';
INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('ai_daily_limit_staff', '100', 'Ask Nipuna answers per staff member per IST day (approved pilot limit)'),
    ('ai_enabled', 'true', 'Super Admin switch: false disables Ask Nipuna for everyone'),
    ('support_sla_hours', '48', 'Hours a support request may stay unresolved before it escalates to the Branch Manager');

-- Reads the acting user set by the request (repositories.common.set_db_user); NULL for jobs and seeds
CREATE OR REPLACE FUNCTION acting_user_id() RETURNS INT AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::INT;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Support requests: every request has a named owner
-- ---------------------------------------------------------------------------
CREATE TABLE support_requests (
    support_request_id SERIAL PRIMARY KEY,
    request_code VARCHAR(20) UNIQUE NOT NULL,       -- 'SR-1042'
    student_id INT NOT NULL REFERENCES students(student_id),
    enrolment_id INT REFERENCES enrolments(enrolment_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),          -- the branch that services the request
    category VARCHAR(30) NOT NULL CHECK (category IN ('Academic', 'LMS', 'Account', 'Recording access', 'Device access', 'Other')),
    subject VARCHAR(200) NOT NULL,
    priority VARCHAR(10) NOT NULL DEFAULT 'Normal' CHECK (priority IN ('Normal', 'High', 'Urgent')),
    status VARCHAR(30) NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open', 'In Progress', 'Waiting on Student', 'Resolved', 'Closed')),
    raised_by_user_id INT NOT NULL REFERENCES users(user_id),
    raised_via VARCHAR(20) NOT NULL DEFAULT 'Student' CHECK (raised_via IN ('Student', 'Staff flag')),
    owner_user_id INT NOT NULL REFERENCES users(user_id),           -- the named owner
    owner_role VARCHAR(30) NOT NULL CHECK (owner_role IN ('TRAINER', 'ACADEMIC_COORDINATOR', 'BRANCH_MANAGER', 'SUPER_ADMIN')),
    escalation_level VARCHAR(30) CHECK (escalation_level IN ('Academic Coordinator', 'Branch Manager')),
    escalated_at TIMESTAMPTZ,
    escalation_reason TEXT,
    sla_due_at TIMESTAMPTZ NOT NULL,
    resolution_note TEXT,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    reopened_count INT NOT NULL DEFAULT 0 CHECK (reopened_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT support_requests_escalation CHECK ((escalation_level IS NULL) = (escalated_at IS NULL)),
    CONSTRAINT support_requests_escalation_reason CHECK (escalation_level IS NULL OR escalation_reason IS NOT NULL),
    CONSTRAINT support_requests_resolution CHECK (status NOT IN ('Resolved', 'Closed') OR resolution_note IS NOT NULL),
    CONSTRAINT support_requests_timestamps CHECK (
        (status <> 'Resolved' OR resolved_at IS NOT NULL) AND (status <> 'Closed' OR closed_at IS NOT NULL))
);

CREATE INDEX support_requests_student_idx ON support_requests (student_id, created_at DESC);
CREATE INDEX support_requests_owner_idx ON support_requests (owner_user_id, status);
CREATE INDEX support_requests_branch_idx ON support_requests (branch_id, status);

CREATE TRIGGER trg_support_requests_updated_at
    BEFORE UPDATE ON support_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION support_requests_before_write() RETURNS trigger AS $$
DECLARE
    v_hours INT;
    v_enrolment_student INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE user_id = NEW.owner_user_id AND is_active) THEN
        RAISE EXCEPTION 'The owner of a support request must be an active user';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.request_code IS NULL THEN
            LOOP
                NEW.request_code = 'SR-' || lpad(next_counter_value('SR')::TEXT, 4, '0');
                EXIT WHEN NOT EXISTS (SELECT 1 FROM support_requests WHERE request_code = NEW.request_code);
            END LOOP;
        END IF;
        SELECT COALESCE((setting_value #>> '{}')::INT, 48) INTO v_hours FROM app_settings WHERE setting_key = 'support_sla_hours';
        NEW.sla_due_at = COALESCE(NEW.sla_due_at, CURRENT_TIMESTAMP + make_interval(hours => COALESCE(v_hours, 48)));
    ELSE
        IF NEW.request_code <> OLD.request_code OR NEW.student_id <> OLD.student_id THEN
            RAISE EXCEPTION 'request_code and student cannot change';
        END IF;
        IF NEW.status <> OLD.status AND NOT (
               (OLD.status = 'Open' AND NEW.status IN ('In Progress', 'Waiting on Student', 'Resolved'))
            OR (OLD.status = 'In Progress' AND NEW.status IN ('Waiting on Student', 'Resolved'))
            OR (OLD.status = 'Waiting on Student' AND NEW.status IN ('In Progress', 'Resolved'))
            OR (OLD.status = 'Resolved' AND NEW.status IN ('Closed', 'Open'))
            OR (OLD.status = 'Closed' AND NEW.status = 'Open')) THEN
            RAISE EXCEPTION 'A support request cannot move from % to %', OLD.status, NEW.status;
        END IF;
        IF NEW.status <> OLD.status THEN
            IF NEW.status = 'Resolved' THEN NEW.resolved_at = CURRENT_TIMESTAMP; END IF;
            IF NEW.status = 'Closed' THEN NEW.closed_at = CURRENT_TIMESTAMP; END IF;
            IF NEW.status = 'Open' AND OLD.status IN ('Resolved', 'Closed') THEN
                NEW.reopened_count = OLD.reopened_count + 1;
                NEW.resolved_at = NULL;
                NEW.closed_at = NULL;
                -- A reopened request gets a fresh SLA clock
                SELECT COALESCE((setting_value #>> '{}')::INT, 48) INTO v_hours FROM app_settings WHERE setting_key = 'support_sla_hours';
                NEW.sla_due_at = CURRENT_TIMESTAMP + make_interval(hours => COALESCE(v_hours, 48));
            END IF;
        END IF;
    END IF;

    IF NEW.enrolment_id IS NOT NULL THEN
        SELECT student_id INTO v_enrolment_student FROM enrolments WHERE enrolment_id = NEW.enrolment_id;
        IF v_enrolment_student <> NEW.student_id THEN
            RAISE EXCEPTION 'The enrolment does not belong to this student';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_support_requests_write
    BEFORE INSERT OR UPDATE ON support_requests
    FOR EACH ROW EXECUTE FUNCTION support_requests_before_write();

-- The conversation and the request's history. Append-only; internal remarks are never shown to the student.
CREATE TABLE support_messages (
    support_message_id BIGSERIAL PRIMARY KEY,
    support_request_id INT NOT NULL REFERENCES support_requests(support_request_id),
    author_user_id INT REFERENCES users(user_id),   -- NULL = the system (automatic SLA escalation)
    kind VARCHAR(20) NOT NULL DEFAULT 'Message'
        CHECK (kind IN ('Message', 'Status', 'Escalation', 'Assignment', 'Reopened')),
    body TEXT NOT NULL CHECK (length(btrim(body)) > 0),
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT support_messages_system_author CHECK (author_user_id IS NOT NULL OR kind = 'Escalation')
);

CREATE INDEX support_messages_request_idx ON support_messages (support_request_id, created_at);

CREATE OR REPLACE FUNCTION prevent_support_message_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'support_messages is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_support_messages_immutable
    BEFORE UPDATE OR DELETE ON support_messages
    FOR EACH ROW EXECUTE FUNCTION prevent_support_message_change();

-- ---------------------------------------------------------------------------
-- Notification preferences (Module 26 §6): per group and channel; in-app is always on
-- ---------------------------------------------------------------------------
CREATE TABLE notification_preferences (
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    preference_group VARCHAR(30) NOT NULL
        CHECK (preference_group IN ('Service', 'Learning reminders', 'Placement', 'Promotions & alumni')),
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('In-app', 'WhatsApp', 'Email')),
    enabled BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, preference_group, channel),
    CONSTRAINT notification_preferences_in_app_on CHECK (channel <> 'In-app' OR enabled)
);

CREATE TRIGGER trg_notification_preferences_updated_at
    BEFORE UPDATE ON notification_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Placement & career support (Module 23): assistance only, no guaranteed placement
-- ---------------------------------------------------------------------------
CREATE TABLE career_profiles (
    student_id INT PRIMARY KEY REFERENCES students(student_id),
    opted_in BOOLEAN NOT NULL DEFAULT FALSE,
    opted_in_at TIMESTAMPTZ,
    support_start DATE,
    support_end DATE,
    support_extension_reason TEXT,
    preferred_roles TEXT[] NOT NULL DEFAULT '{}',
    preferred_locations TEXT[] NOT NULL DEFAULT '{}',
    work_mode VARCHAR(20) CHECK (work_mode IN ('On-site', 'Remote', 'Hybrid', 'Any')),
    qualification VARCHAR(200),
    graduation_year INT CHECK (graduation_year BETWEEN 1990 AND 2100),
    experience_level VARCHAR(20) CHECK (experience_level IN ('Fresher', 'Experienced')),
    skills JSONB NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(skills) = 'array'),  -- [{name, confidence}]
    portfolio_url VARCHAR(500),
    availability VARCHAR(200),
    sharing_consent BOOLEAN NOT NULL DEFAULT FALSE,     -- employer sharing, separate from opting in
    sharing_consent_at TIMESTAMPTZ,
    readiness VARCHAR(30) NOT NULL DEFAULT 'Not Assessed'
        CHECK (readiness IN ('Not Assessed', 'In Preparation', 'Ready for referral')),
    readiness_note TEXT,
    readiness_reviewed_by INT REFERENCES users(user_id),
    readiness_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT career_profiles_opt_in CHECK (NOT opted_in OR opted_in_at IS NOT NULL),
    CONSTRAINT career_profiles_consent CHECK (NOT sharing_consent OR opted_in),
    CONSTRAINT career_profiles_support_dates CHECK (support_end IS NULL OR support_start IS NULL OR support_end >= support_start)
);

CREATE TRIGGER trg_career_profiles_updated_at
    BEFORE UPDATE ON career_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- CV versions: kept, never overwritten; a newer upload supersedes the older ones in the service
CREATE TABLE cv_documents (
    cv_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    version_no INT NOT NULL,
    label VARCHAR(150) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100),
    file_size_bytes INT NOT NULL CHECK (file_size_bytes > 0),
    review_status VARCHAR(20) NOT NULL DEFAULT 'Pending Review'
        CHECK (review_status IN ('Pending Review', 'Reviewed', 'Changes Requested', 'Superseded')),
    review_feedback TEXT,
    reviewed_by INT REFERENCES users(user_id),
    reviewed_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT cv_documents_version UNIQUE (student_id, version_no),
    CONSTRAINT cv_documents_reviewed CHECK (review_status NOT IN ('Reviewed', 'Changes Requested') OR reviewed_by IS NOT NULL)
);

CREATE OR REPLACE FUNCTION cv_documents_before_insert() RETURNS trigger AS $$
BEGIN
    IF NEW.version_no IS NULL THEN
        SELECT COALESCE(MAX(version_no), 0) + 1 INTO NEW.version_no FROM cv_documents WHERE student_id = NEW.student_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_cv_documents_version
    BEFORE INSERT ON cv_documents
    FOR EACH ROW EXECUTE FUNCTION cv_documents_before_insert();

-- Opportunities: only an Active (verified) one is shown to students; the verifier cannot be its creator
CREATE TABLE opportunities (
    opportunity_id SERIAL PRIMARY KEY,
    opportunity_code VARCHAR(20) UNIQUE NOT NULL,   -- 'OPP-0001'
    title VARCHAR(200) NOT NULL,
    employer_name VARCHAR(200) NOT NULL,
    employer_source VARCHAR(300),                   -- website / where the employer was verified from
    employment_type VARCHAR(20) NOT NULL DEFAULT 'Full-time' CHECK (employment_type IN ('Full-time', 'Internship', 'Contract')),
    work_mode VARCHAR(20) NOT NULL DEFAULT 'On-site' CHECK (work_mode IN ('On-site', 'Remote', 'Hybrid')),
    location VARCHAR(200),
    description TEXT,
    required_skills TEXT[] NOT NULL DEFAULT '{}',
    course_id INT REFERENCES courses(course_id),    -- NULL = open to every course
    branch_id INT REFERENCES branches(branch_id),   -- NULL = open to every branch
    compensation_text VARCHAR(200) NOT NULL DEFAULT 'Not Disclosed',
    openings INT CHECK (openings > 0),
    closing_date DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'Draft'
        CHECK (status IN ('Draft', 'Verification Pending', 'Active', 'On Hold', 'Closed', 'Expired')),
    verification_source VARCHAR(300),
    verified_by INT REFERENCES users(user_id),
    verified_at TIMESTAMPTZ,
    created_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT opportunities_active_verified CHECK (status <> 'Active' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT opportunities_independent_verifier CHECK (verified_by IS NULL OR verified_by <> created_by)
);

CREATE INDEX opportunities_status_idx ON opportunities (status, course_id, branch_id);

CREATE TRIGGER trg_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION opportunities_before_insert() RETURNS trigger AS $$
BEGIN
    IF NEW.opportunity_code IS NULL THEN
        LOOP
            NEW.opportunity_code = 'OPP-' || lpad(next_counter_value('OPP')::TEXT, 4, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM opportunities WHERE opportunity_code = NEW.opportunity_code);
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_opportunities_code
    BEFORE INSERT ON opportunities
    FOR EACH ROW EXECUTE FUNCTION opportunities_before_insert();

-- One application per student + opportunity + hiring cycle; several interview rounds live inside it
CREATE TABLE applications (
    application_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    opportunity_id INT NOT NULL REFERENCES opportunities(opportunity_id),
    hiring_cycle VARCHAR(30) NOT NULL DEFAULT 'Current',
    source VARCHAR(20) NOT NULL DEFAULT 'Nipuna-referred' CHECK (source IN ('Nipuna-referred', 'Self-sourced', 'Other')),
    cv_id INT REFERENCES cv_documents(cv_id),       -- the exact CV version sent
    status VARCHAR(30) NOT NULL DEFAULT 'Applied' CHECK (status IN (
        'Applied', 'Shortlisted', 'Interview Scheduled', 'Interview Attended', 'Selected', 'Offer Received',
        'Offer Accepted', 'Joined', 'Rejected', 'Student Declined', 'Position Closed', 'Withdrawn')),
    interview_round VARCHAR(100),
    interview_at TIMESTAMPTZ,
    status_note TEXT,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT applications_one_per_cycle UNIQUE (student_id, opportunity_id, hiring_cycle)
);

CREATE INDEX applications_student_idx ON applications (student_id, applied_at DESC);

CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE application_events (
    application_event_id BIGSERIAL PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(application_id),
    from_status VARCHAR(30),
    to_status VARCHAR(30) NOT NULL,
    note TEXT,
    actor_user_id INT REFERENCES users(user_id),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX application_events_application_idx ON application_events (application_id, occurred_at);

CREATE OR REPLACE FUNCTION applications_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM opportunities WHERE opportunity_id = NEW.opportunity_id AND status = 'Active') THEN
            RAISE EXCEPTION 'This opportunity is not open for applications';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM career_profiles WHERE student_id = NEW.student_id AND opted_in) THEN
            RAISE EXCEPTION 'Opt in to career support before applying';
        END IF;
    ELSIF NEW.status <> OLD.status AND OLD.status IN ('Joined', 'Rejected', 'Student Declined', 'Position Closed', 'Withdrawn') THEN
        RAISE EXCEPTION 'A closed application (%) cannot change status', OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_applications_guard
    BEFORE INSERT OR UPDATE OF status ON applications
    FOR EACH ROW EXECUTE FUNCTION applications_guard();

-- Every status the application passes through is kept, with who set it
CREATE OR REPLACE FUNCTION applications_log_status() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status <> OLD.status THEN
        INSERT INTO application_events (application_id, from_status, to_status, note, actor_user_id)
        VALUES (NEW.application_id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status, NEW.status_note, acting_user_id());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_applications_log
    AFTER INSERT OR UPDATE OF status ON applications
    FOR EACH ROW EXECUTE FUNCTION applications_log_status();

-- Outcomes count only once Verified with evidence, by someone other than the person who recorded them
CREATE TABLE placement_outcomes (
    outcome_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id),
    application_id INT REFERENCES applications(application_id),
    outcome_type VARCHAR(20) NOT NULL CHECK (outcome_type IN ('Offer Received', 'Offer Accepted', 'Joined')),
    employer_name VARCHAR(200) NOT NULL,
    role_title VARCHAR(200) NOT NULL,
    event_date DATE NOT NULL,
    compensation_text VARCHAR(200),
    source VARCHAR(20) NOT NULL DEFAULT 'Placement records' CHECK (source IN ('Placement records', 'Student reported')),
    verification_status VARCHAR(30) NOT NULL DEFAULT 'Pending Verification'
        CHECK (verification_status IN ('Pending Verification', 'Verified', 'Rejected')),
    evidence_note TEXT,
    recorded_by INT NOT NULL REFERENCES users(user_id),
    verified_by INT REFERENCES users(user_id),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT placement_outcomes_verified CHECK (
        verification_status <> 'Verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND length(btrim(COALESCE(evidence_note, ''))) > 0)),
    CONSTRAINT placement_outcomes_independent CHECK (verified_by IS NULL OR verified_by <> recorded_by)
);

CREATE INDEX placement_outcomes_student_idx ON placement_outcomes (student_id, event_date DESC);

CREATE TRIGGER trg_placement_outcomes_updated_at
    BEFORE UPDATE ON placement_outcomes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- What reports may count (Module 23 §15): verified outcomes only, with the student's service branch
CREATE VIEW verified_placement_outcomes AS
SELECT o.outcome_id, o.student_id, s.student_code, s.service_branch_id AS branch_id, o.outcome_type, o.employer_name,
       o.role_title, o.event_date, o.application_id, o.verified_at
FROM placement_outcomes o
JOIN students s ON s.student_id = o.student_id
WHERE o.verification_status = 'Verified';

-- ---------------------------------------------------------------------------
-- Ask Nipuna (Module 24): every question and answer, with tokens, sources and feedback
-- ---------------------------------------------------------------------------
CREATE TABLE ai_queries (
    ai_query_id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    student_id INT REFERENCES students(student_id),
    audience VARCHAR(10) NOT NULL CHECK (audience IN ('Student', 'Staff')),
    branch_id INT REFERENCES branches(branch_id),
    action VARCHAR(60),
    question TEXT NOT NULL CHECK (length(btrim(question)) > 0),
    answer TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Answered' CHECK (status IN ('Answered', 'Refused', 'Failed')),  -- only Answered counts to the daily limit
    refusal_reason TEXT,
    is_fallback BOOLEAN NOT NULL DEFAULT FALSE,     -- answered by the rule-based writer, not the model
    model VARCHAR(80) NOT NULL,
    input_tokens INT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens INT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    sources JSONB NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(sources) = 'array'),
    scope_note TEXT NOT NULL,
    warnings JSONB NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(warnings) = 'array'),
    feedback VARCHAR(20) CHECK (feedback IN ('Helpful', 'Not helpful')),
    feedback_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ai_queries_refusal_reason CHECK ((status = 'Refused') = (refusal_reason IS NOT NULL))
);

CREATE INDEX ai_queries_user_idx ON ai_queries (user_id, created_at DESC);

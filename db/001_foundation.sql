-- Phase 1a / 001: foundation (branches, roles, users, sessions, audit, settings, integrations, notifications, activity)
-- Depends on: nothing (first migration)

-- ---------------------------------------------------------------------------
-- Shared helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Generated codes (student, batch, enrolment, session): one counter row per code series, e.g. 'STU-2026'
CREATE TABLE code_counters (
    counter_key VARCHAR(50) PRIMARY KEY,
    last_value INT NOT NULL DEFAULT 0
);

CREATE OR REPLACE FUNCTION next_counter_value(p_key TEXT) RETURNS INT AS $$
    INSERT INTO code_counters (counter_key, last_value) VALUES (p_key, 1)
    ON CONFLICT (counter_key) DO UPDATE SET last_value = code_counters.last_value + 1
    RETURNING last_value;
$$ LANGUAGE sql;

-- Calendar year in the business timezone (IST), so a code minted just after midnight IST gets the new year
CREATE OR REPLACE FUNCTION business_year() RETURNS INT AS $$
    SELECT EXTRACT(YEAR FROM (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata'))::INT;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Branches
-- ---------------------------------------------------------------------------
CREATE TABLE branches (
    branch_id SERIAL PRIMARY KEY,
    branch_code VARCHAR(20) UNIQUE NOT NULL,        -- e.g., 'NIT-GNT'
    short_code VARCHAR(10) UNIQUE NOT NULL,         -- e.g., 'GNT' (used inside batch codes)
    branch_name VARCHAR(100) NOT NULL,              -- e.g., 'Guntur'
    city VARCHAR(100) NOT NULL,
    mailbox VARCHAR(255) NOT NULL,                  -- shared branch mailbox (Meet organizer / notices)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_branches_updated_at
    BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO branches (branch_code, short_code, branch_name, city, mailbox) VALUES
    ('NIT-GNT', 'GNT', 'Guntur', 'Guntur', 'trainer@nipunatechnologies.com'),
    ('NIT-VIJ', 'VIJ', 'Vijayawada', 'Vijayawada', 'contactus@nipunatechnologies.com');

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_code VARCHAR(50) UNIQUE NOT NULL,          -- e.g., 'BRANCH_MANAGER'
    role_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_company_wide BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE = sees all branches
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO roles (role_code, role_name, description, is_company_wide) VALUES
    ('STUDENT', 'Student', 'Own learning, submissions, results, certificates and support', FALSE),
    ('TRAINER', 'Trainer', 'Batches they are assigned to and the students allocated to them', FALSE),
    ('ACADEMIC_COORDINATOR', 'Academic Coordinator', 'Everything academic at one branch', FALSE),
    ('BRANCH_MANAGER', 'Branch Manager', 'Everything at one branch, read-only finance summary', FALSE),
    ('SUPER_ADMIN', 'Super Admin', 'All branches; admin, integrations and security', TRUE),
    ('FOUNDER_CEO', 'Founder / CEO', 'All branches; management overview', TRUE);

-- ---------------------------------------------------------------------------
-- Users (staff and students; a student login points at students via student_id, FK added in 003)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255),                             -- optional for students (they sign in with their Student ID)
    phone VARCHAR(20),
    password_hash VARCHAR(255),                     -- NULL until the user sets a password (students: on activation)
    student_id INT UNIQUE,                          -- one LMS login per student
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    password_changed_at TIMESTAMPTZ,
    failed_login_attempts SMALLINT NOT NULL DEFAULT 0 CHECK (failed_login_attempts >= 0),
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT users_login_identity CHECK (email IS NOT NULL OR student_id IS NOT NULL)
);

-- Case-insensitive unique email
CREATE UNIQUE INDEX users_email_lower_key ON users (LOWER(email)) WHERE email IS NOT NULL;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One role at one branch (branch_id NULL = all branches, company-wide roles only)
CREATE TABLE user_role_scopes (
    scope_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(role_id),
    branch_id INT REFERENCES branches(branch_id),
    granted_by INT REFERENCES users(user_id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,                         -- temporary access
    revoked_by INT REFERENCES users(user_id),
    revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX user_role_scopes_one_live
    ON user_role_scopes (user_id, role_id, COALESCE(branch_id, 0)) WHERE revoked_at IS NULL;
CREATE INDEX user_role_scopes_user_idx ON user_role_scopes (user_id);
CREATE INDEX user_role_scopes_branch_idx ON user_role_scopes (branch_id);

-- Company-wide roles (Super Admin, Founder / CEO) cover all branches; the rest are per branch
CREATE OR REPLACE FUNCTION check_role_scope_branch() RETURNS trigger AS $$
DECLARE
    v_company_wide BOOLEAN;
BEGIN
    SELECT is_company_wide INTO v_company_wide FROM roles WHERE role_id = NEW.role_id;
    IF v_company_wide AND NEW.branch_id IS NOT NULL THEN
        RAISE EXCEPTION 'Company-wide roles apply to all branches; leave branch_id empty';
    ELSIF NOT v_company_wide AND NEW.branch_id IS NULL THEN
        RAISE EXCEPTION 'This role is per branch; set branch_id (add one scope per branch)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_role_scopes_branch
    BEFORE INSERT OR UPDATE OF role_id, branch_id ON user_role_scopes
    FOR EACH ROW EXECUTE FUNCTION check_role_scope_branch();

-- ---------------------------------------------------------------------------
-- App settings: admin-editable values read by the app and some triggers
-- ---------------------------------------------------------------------------
CREATE TABLE app_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value JSONB NOT NULL,
    description TEXT,
    updated_by INT REFERENCES users(user_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_app_settings_updated_at
    BEFORE UPDATE ON app_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('business_timezone', '"Asia/Kolkata"', 'Timezone for class times and business dates'),
    ('session_idle_minutes', '30', 'Inactivity timeout'),
    ('session_max_minutes', '720', 'Maximum session length'),
    ('fresh_auth_minutes', '15', 'Sensitive actions need a password entry within this many minutes'),
    ('login_max_attempts', '5', 'Failed logins before the account is locked'),
    ('login_lock_minutes', '15', 'How long a locked account stays locked'),
    ('password_min_length', '10', 'Minimum password length'),
    ('activation_token_hours', '72', 'How long a student activation link stays valid'),
    ('recording_access_days', '90', 'Days a student can watch a released recording after the session'),
    ('ai_daily_limit', '20', 'Ask Nipuna questions per student per day');

-- ---------------------------------------------------------------------------
-- Sessions: idle timeout, maximum length, fresh authentication for sensitive actions
-- ---------------------------------------------------------------------------
CREATE TABLE user_sessions (
    session_id VARCHAR(128) PRIMARY KEY,            -- SHA-256 of the bearer token
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    reauthenticated_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT,
    revoked_at TIMESTAMPTZ,
    revoke_reason VARCHAR(100)
);

CREATE INDEX user_sessions_user_idx ON user_sessions (user_id);

CREATE OR REPLACE FUNCTION set_session_expiry() RETURNS trigger AS $$
BEGIN
    NEW.expires_at = COALESCE(NEW.expires_at, NEW.created_at + make_interval(mins =>
        COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = 'session_max_minutes'), 720)));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_sessions_expiry
    BEFORE INSERT ON user_sessions
    FOR EACH ROW EXECUTE FUNCTION set_session_expiry();

CREATE VIEW active_sessions AS
SELECT s.*,
       s.reauthenticated_at IS NOT NULL AND s.reauthenticated_at > CURRENT_TIMESTAMP - make_interval(mins =>
           COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = 'fresh_auth_minutes'), 15))
           AS has_fresh_auth
FROM user_sessions s
WHERE s.revoked_at IS NULL
  AND s.expires_at > CURRENT_TIMESTAMP
  AND s.last_seen_at > CURRENT_TIMESTAMP - make_interval(mins =>
        COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = 'session_idle_minutes'), 30));

-- ---------------------------------------------------------------------------
-- Audit log: append-only
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_user_id INT REFERENCES users(user_id),    -- NULL for system actions (CRM events, jobs)
    action VARCHAR(50) NOT NULL,                    -- e.g., 'LOGIN', 'ACTIVATION_ISSUED'
    entity_type VARCHAR(50) NOT NULL,               -- e.g., 'student', 'certificate'
    entity_id VARCHAR(50) NOT NULL,                 -- PK or business code of the record
    branch_id INT REFERENCES branches(branch_id),
    old_values JSONB,
    new_values JSONB,
    reason TEXT,
    ip_address INET
);

CREATE INDEX audit_log_entity_idx ON audit_log (entity_type, entity_id);
CREATE INDEX audit_log_actor_idx ON audit_log (actor_user_id);
CREATE INDEX audit_log_occurred_at_idx ON audit_log (occurred_at);

CREATE OR REPLACE FUNCTION prevent_audit_log_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_change();

-- ---------------------------------------------------------------------------
-- Integrations register: capability is verified separately from configuration
-- ---------------------------------------------------------------------------
CREATE TYPE integration_configuration_status AS ENUM ('Not Configured', 'Configuration Pending', 'Configured');
CREATE TYPE integration_verification_status AS ENUM ('Not Verified', 'Pending Verification', 'Verified', 'Failed');

CREATE TABLE integrations (
    integration_id SERIAL PRIMARY KEY,
    integration_code VARCHAR(50) UNIQUE NOT NULL,
    integration_name VARCHAR(100) NOT NULL,
    requirement TEXT NOT NULL,                      -- what the LMS needs from it
    configuration_status integration_configuration_status NOT NULL DEFAULT 'Not Configured',
    verification_status integration_verification_status NOT NULL DEFAULT 'Not Verified',
    owner VARCHAR(100) NOT NULL,                    -- who resolves it (role or team)
    last_checked_at TIMESTAMPTZ,
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_integrations_updated_at
    BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO integrations (integration_code, integration_name, requirement, configuration_status, verification_status, owner, last_checked_at, notes) VALUES
    ('GOOGLE_WORKSPACE', 'Google Workspace', 'Branch mailboxes and organizer accounts for classes',
        'Configuration Pending', 'Pending Verification', 'Super Admin', NULL, 'Organizer accounts and licences not yet confirmed'),
    ('GOOGLE_MEET', 'Google Meet', 'Create and associate a Meet link with each Live Online / Hybrid class session',
        'Not Configured', 'Not Verified', 'Super Admin', NULL, 'Organizer account licence Pending Verification'),
    ('GOOGLE_DRIVE_RECORDINGS', 'Google Drive recordings', 'Map Meet recordings in Drive to actual class sessions',
        'Not Configured', 'Not Verified', 'Super Admin', NULL, 'Recording capability must be verified per organizer'),
    ('CRM', 'Nipuna CRM', 'Receive admissions, courses and finance summaries; report LMS account and access status back',
        'Configured', 'Pending Verification', 'Super Admin', NULL, 'Inbound events supported; outbound delivery worker not built yet'),
    ('WHATSAPP', 'WhatsApp', 'Reminders, activation links and support replies',
        'Not Configured', 'Not Verified', 'Branch Manager', NULL, NULL),
    ('EMAIL', 'Email', 'Activation links, certificates and notices',
        'Configuration Pending', 'Not Verified', 'Super Admin', NULL, 'SMTP sender not yet provided'),
    ('TELEPHONY', 'Telephony', 'Click-to-call for trainer and coordinator follow-ups',
        'Not Configured', 'Not Verified', 'Branch Manager', NULL, 'Optional'),
    ('AI_PROVIDER', 'AI provider', 'Ask Nipuna answers over the student''s permitted content',
        'Not Configured', 'Not Verified', 'Super Admin', NULL, 'Rule-based fallback is used until an API key is set');

-- ---------------------------------------------------------------------------
-- In-app notifications
-- ---------------------------------------------------------------------------
CREATE TYPE notification_delivery_status AS ENUM ('Delivered', 'Failed');
CREATE TYPE notification_action_status AS ENUM ('None', 'Open', 'Completed');

CREATE TABLE notifications (
    notification_id BIGSERIAL PRIMARY KEY,
    recipient_user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    branch_id INT REFERENCES branches(branch_id),
    category VARCHAR(50) NOT NULL,                  -- e.g., 'Enrolment', 'Session', 'Assignment'
    title VARCHAR(200) NOT NULL,
    body TEXT,
    link VARCHAR(255),                              -- app route the notification opens
    event_key VARCHAR(200) NOT NULL,                -- what happened; one notification per (event_key, recipient)
    delivery_status notification_delivery_status NOT NULL DEFAULT 'Delivered',
    action_status notification_action_status NOT NULL DEFAULT 'None',
    read_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT notifications_dedupe UNIQUE (event_key, recipient_user_id)
);

CREATE INDEX notifications_recipient_idx ON notifications (recipient_user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Learning activity log (feeds the engagement measure and the CRM "last activity" value).
-- student_id / enrolment_id foreign keys are added in 003 once those tables exist.
-- ---------------------------------------------------------------------------
CREATE TABLE activity_events (
    activity_id BIGSERIAL PRIMARY KEY,
    student_id INT NOT NULL,
    enrolment_id INT,                               -- NULL = not tied to one course (e.g., login)
    kind VARCHAR(50) NOT NULL,                      -- 'login', 'resource_view', 'recording_view', 'topic_complete', ...
    detail JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX activity_events_student_idx ON activity_events (student_id, occurred_at DESC);
CREATE INDEX activity_events_enrolment_idx ON activity_events (enrolment_id, occurred_at DESC);

-- Phase 2 / S6 (060): admin & security readiness
-- Depends on: 001 (users, integrations)
-- Adds: verification evidence on the integrations register, the security_controls register (seeded with the
-- platform's controls), a 'Misconfigured' configuration state, and the extra integrations the prototype lists.

-- ---------------------------------------------------------------------------
-- Integrations register: who verified it, when, and on what evidence
-- ---------------------------------------------------------------------------
-- A configuration that is set up but wrong is different from one that is not set up at all
ALTER TYPE integration_configuration_status ADD VALUE IF NOT EXISTS 'Misconfigured';

ALTER TABLE integrations
    ADD COLUMN verified_by INT REFERENCES users(user_id),
    ADD COLUMN verified_at TIMESTAMPTZ,
    ADD COLUMN evidence TEXT;

-- "Verified" is a claim about operation, so it needs a person, a time, an evidence note and a working configuration
ALTER TABLE integrations
    ADD CONSTRAINT integrations_verified_needs_evidence CHECK (
        verification_status <> 'Verified'
        OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND NULLIF(BTRIM(evidence), '') IS NOT NULL
            AND configuration_status = 'Configured')
    );

-- What the prototype's readiness table lists beyond the backbone rows: one Meet organizer per branch mailbox,
-- the CRM-owned payment reference feed and production authentication
INSERT INTO integrations (integration_code, integration_name, requirement, configuration_status, verification_status, owner, notes) VALUES
    ('MEET_ORGANIZER_GNT', 'Google Meet organizer — Guntur', 'Organizer account and licence for classes at NIT-GNT (branch mailbox)',
        'Configuration Pending', 'Pending Verification', 'Super Admin', 'Organizer label trainer@nipunatechnologies.com: account and licence Pending Verification'),
    ('MEET_ORGANIZER_VIJ', 'Google Meet organizer — Vijayawada', 'Organizer account and licence for classes at NIT-VIJ (branch mailbox)',
        'Configuration Pending', 'Pending Verification', 'Super Admin', 'Organizer label contactus@nipunatechnologies.com: Pending Verification'),
    ('HDFC_PAYMENTS', 'HDFC payment references (via CRM)', 'Payment references reach the LMS only through CRM finance summaries',
        'Configuration Pending', 'Not Verified', 'Branch Manager', 'CRM-owned; the LMS reads the summary only'),
    ('PRODUCTION_AUTH', 'Production authentication', 'Production identity settings: HTTPS, secure cookies / tokens, MFA policy',
        'Not Configured', 'Not Verified', 'Super Admin', NULL);

-- ---------------------------------------------------------------------------
-- Security controls register
-- ---------------------------------------------------------------------------
CREATE TABLE security_controls (
    control_id SERIAL PRIMARY KEY,
    control_code VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL,                  -- Access, Sessions, Identity, Audit, Data, Operations
    title VARCHAR(200) NOT NULL,
    requirement TEXT NOT NULL,
    configuration_status integration_configuration_status NOT NULL DEFAULT 'Not Configured',
    verification_status integration_verification_status NOT NULL DEFAULT 'Not Verified',
    owner VARCHAR(100) NOT NULL,
    evidence TEXT,
    verified_by INT REFERENCES users(user_id),
    verified_at TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT security_controls_verified_needs_evidence CHECK (
        verification_status <> 'Verified'
        OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND NULLIF(BTRIM(evidence), '') IS NOT NULL
            AND configuration_status = 'Configured')
    )
);

CREATE TRIGGER trg_security_controls_updated_at
    BEFORE UPDATE ON security_controls
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Controls the platform implements start Configured / Pending Verification (a Super Admin verifies them with
-- evidence); the rest wait for their slice or for production set-up. Nothing is Verified without evidence.
INSERT INTO security_controls (control_code, category, title, requirement, configuration_status, verification_status, owner, notes) VALUES
    ('SCOPE_ENFORCEMENT', 'Access', 'Server-side scope enforcement',
        'Every list, detail, total, export, notification and AI answer is filtered on the server by role, branch and record scope; a record outside scope answers 404. The frontend role switcher is a UAT aid, not a security boundary.',
        'Configured', 'Pending Verification', 'Super Admin', 'services/scope.py is applied by every endpoint; covered by the scope tests'),
    ('SESSION_IDLE', 'Sessions', 'Inactivity timeout — 30 minutes',
        'A session idle for longer than app_settings.session_idle_minutes stops working and the user signs in again.',
        'Configured', 'Pending Verification', 'Super Admin', 'active_sessions view checks last_seen_at'),
    ('SESSION_MAX', 'Sessions', 'Maximum session — 12 hours',
        'A session ends after app_settings.session_max_minutes however active it is.',
        'Configured', 'Pending Verification', 'Super Admin', 'user_sessions.expires_at is set by trigger at login'),
    ('FRESH_AUTH', 'Sessions', 'Re-authentication for sensitive actions',
        'Role changes, password resets, account suspension, integration changes and similar actions need a password entry within app_settings.fresh_auth_minutes.',
        'Configured', 'Pending Verification', 'Super Admin', '@fresh_auth on the sensitive endpoints'),
    ('LOGIN_LOCKOUT', 'Sessions', 'Account lockout after failed logins',
        'An account locks for app_settings.login_lock_minutes after app_settings.login_max_attempts failed sign-ins.',
        'Configured', 'Pending Verification', 'Super Admin', NULL),
    ('PASSWORD_POLICY', 'Identity', 'Password policy and temporary passwords',
        'Passwords meet app_settings.password_min_length; a temporary password set by an administrator must be changed at first sign-in.',
        'Configured', 'Pending Verification', 'Super Admin', NULL),
    ('UNIQUE_LMS_LOGIN', 'Identity', 'One unique LMS login per student',
        'A student has one Student ID and one login (one per CRM Person); email is optional; a mobile number is never identity proof.',
        'Configured', 'Pending Verification', 'Super Admin', 'students.crm_person_id and users.student_id are unique'),
    ('ACTIVATION_TOKEN', 'Identity', 'Activation link expiry and single use',
        'An activation token is single-use, expires after app_settings.activation_token_hours, and only its hash is stored; staff reissue links under supervision.',
        'Configured', 'Pending Verification', 'Super Admin', NULL),
    ('AUDIT_IMMUTABLE', 'Audit', 'Audit log immutability',
        'Audit entries can be added but never changed or deleted.',
        'Configured', 'Pending Verification', 'Super Admin', 'A trigger on audit_log rejects UPDATE and DELETE'),
    ('AUDIT_DECISIONS', 'Audit', 'Audit logging of certificate and access decisions',
        'Certificate issue / revoke, role changes, access extensions, recording release and account actions are written to the audit log with old and new values.',
        'Configuration Pending', 'Not Verified', 'Super Admin', 'Account, role and integration changes are audited; the remaining decisions arrive with their slices'),
    ('TEMP_ACCESS', 'Access', 'Routine temporary access — maximum 7 calendar days',
        'A temporary role scope expires automatically and cannot be granted for more than 7 calendar days.',
        'Configured', 'Pending Verification', 'Super Admin', 'user_role_scopes.expires_at; the limit is checked when the scope is granted'),
    ('EMERGENCY_ACCESS', 'Access', 'Elevated / emergency access — maximum 4 elapsed hours',
        'Elevated access lasts at most 4 elapsed hours and is reviewed afterwards.',
        'Not Configured', 'Not Verified', 'Super Admin', 'Procedure to be agreed'),
    ('STUDENT_MFA', 'Identity', 'Student multi-factor authentication',
        'Optional unless configured; when enabled a student confirms sign-in with a second factor.',
        'Not Configured', 'Not Verified', 'Super Admin', 'students.mfa_status tracks the choice; no second factor is implemented yet'),
    ('FILE_ACCESS', 'Data', 'File access checks',
        'Uploaded files (content, CVs, submissions) are served only after the same scope check as the record they belong to.',
        'Configuration Pending', 'Not Verified', 'Super Admin', 'Applies once the content, assessment and career slices store files'),
    ('EXPORT_SCOPING', 'Data', 'Export scoping',
        'Exports contain only the rows the requester may see, and are logged.',
        'Configuration Pending', 'Not Verified', 'Super Admin', NULL),
    ('AI_DATA_SCOPE', 'Data', 'AI data scope',
        'Ask Nipuna answers use only the asking user''s permitted records and refuse other students'' data and finance edits.',
        'Configuration Pending', 'Not Verified', 'Super Admin', 'Applies with the student-services slice'),
    ('TRANSPORT_SECURITY', 'Operations', 'HTTPS in production',
        'The API and the app are served only over HTTPS in production.',
        'Not Configured', 'Not Verified', 'Super Admin', 'Production set-up'),
    ('BACKUPS', 'Operations', 'Database backups and restore test',
        'The production database is backed up daily and a restore is tested at least quarterly.',
        'Not Configured', 'Not Verified', 'Super Admin', 'Production set-up');

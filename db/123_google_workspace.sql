-- 123: Google Workspace integration, first slice (docs/GOOGLE_WORKSPACE.md): per-branch Google settings and the retry queue
-- Depends on: 001 (branches, integrations, set_updated_at)
--   The LMS calls Google only from a background job: a request writes its own change and a `google_jobs` row in one
--   transaction, and the `google-sync` job calls Google after the commit. At most one open job per (kind, entity), so
--   repeated changes to one class collapse into one call that reads the class as it is when the job runs.

CREATE TYPE google_job_state AS ENUM ('Queued', 'Running', 'Failed', 'Succeeded', 'Dead');

CREATE TABLE branch_google_config (
    branch_id INTEGER PRIMARY KEY REFERENCES branches (branch_id),
    calendar_mailbox VARCHAR(255),                  -- whose calendar holds the class events; the branch mailbox when empty
    drive_root_folder_id VARCHAR(200),              -- the branch's Drive folder, once created
    gmail_sender VARCHAR(255),                      -- who the branch's email comes from; the branch mailbox when empty
    updated_by INTEGER REFERENCES users (user_id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_branch_google_config_updated_at
    BEFORE UPDATE ON branch_google_config
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE google_jobs (
    job_id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(40) NOT NULL,                      -- CALENDAR_UPSERT, CALENDAR_CANCEL
    entity_type VARCHAR(40) NOT NULL,               -- class_session
    entity_id INTEGER NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    state google_job_state NOT NULL DEFAULT 'Queued',
    attempts SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,                         -- when the current attempt began; a Running job older than 15 minutes is taken again
    finished_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One open job per (kind, entity): a second request while one waits reuses it
CREATE UNIQUE INDEX google_jobs_open_uq ON google_jobs (kind, entity_type, entity_id)
    WHERE state IN ('Queued', 'Running', 'Failed');
CREATE INDEX google_jobs_due_idx ON google_jobs (next_attempt_at) WHERE state IN ('Queued', 'Failed');
CREATE INDEX google_jobs_state_idx ON google_jobs (state, updated_at DESC);

CREATE TRIGGER trg_google_jobs_updated_at
    BEFORE UPDATE ON google_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Register: Drive material is not the same thing as the Drive recordings entry
INSERT INTO integrations (integration_code, integration_name, requirement, configuration_status, verification_status, owner, notes) VALUES
    ('GOOGLE_DRIVE', 'Google Drive material', 'Folders per branch, course and batch, shared with the batch''s students and trainers',
        'Not Configured', 'Not Verified', 'Super Admin', 'Service account with domain-wide delegation required; see docs/GOOGLE_WORKSPACE.md');

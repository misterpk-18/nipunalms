-- 125: Google Workspace integration, third slice (docs/GOOGLE_WORKSPACE.md §5.2): Drive folders and who they are shared with
-- Depends on: 001 (users, branches), 002 (courses), 004 (batches), 123 (Google Workspace)
--   One folder per branch, per course at a branch and per batch, created on demand by the `google-sync` job, owned by the
--   branch's mailbox. A batch's folder is shared with its trainers (editors) and the students holding a seat (viewers).
--   The job compares who should have access (the seats and trainer assignments) with `google_drive_grants`, so one
--   `DRIVE_SYNC` job per batch covers every change to it.

CREATE TABLE google_drive_items (
    item_id SERIAL PRIMARY KEY,
    entity_type VARCHAR(10) NOT NULL CHECK (entity_type IN ('branch', 'course', 'batch')),
    entity_id INTEGER NOT NULL,                     -- the branch, course or batch
    branch_id INTEGER NOT NULL REFERENCES branches (branch_id),
    parent_item_id INTEGER REFERENCES google_drive_items (item_id),
    folder_id VARCHAR(200) NOT NULL,                -- Google's id of the folder
    folder_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, branch_id)
);

CREATE TABLE google_drive_grants (
    grant_id BIGSERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES google_drive_items (item_id),
    grantee_email VARCHAR(255) NOT NULL,
    grantee_user_id INTEGER REFERENCES users (user_id),
    role VARCHAR(10) NOT NULL CHECK (role IN ('reader', 'writer')),
    permission_id VARCHAR(200) NOT NULL,            -- Google's id of the share, needed to remove it
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ
);

-- One live share per person per folder
CREATE UNIQUE INDEX google_drive_grants_live_uq ON google_drive_grants (item_id, LOWER(grantee_email)) WHERE revoked_at IS NULL;

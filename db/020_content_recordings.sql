-- Phase 2 / S2 / 020: content library, content review, recordings, recording exceptions, access extension requests
-- Depends on: 004_batches_sessions.sql (curriculum, enrolments, batches, class sessions, app_settings)

-- ---------------------------------------------------------------------------
-- Settings read by this slice
-- ---------------------------------------------------------------------------
INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('access_default_years', '1', 'Recordings and materials stay available this many calendar years from the confirmed Joining Date (Modules 17 and 18)'),
    ('access_max_years', '2', 'A student-requested extension reaches this many years from the Joining Date; later requests need a Founder / Super Admin exception'),
    ('recording_check_hours', '4', 'A Delivered class session without a recording after this many hours raises a recording exception'),
    ('content_max_upload_mb', '50', 'Largest ordinary content file (Module 18 §7)'),
    ('content_dataset_max_upload_mb', '250', 'Largest dataset or approved archive');

-- ---------------------------------------------------------------------------
-- Content items: one library entry (title, type, placement), with its versions below
-- ---------------------------------------------------------------------------
CREATE TYPE content_type AS ENUM ('PDF', 'Notes', 'Dataset', 'Code', 'Lab', 'Practice material', 'Link', 'Video link');
CREATE TYPE content_status AS ENUM ('Draft', 'Submitted', 'Under Review', 'Approved', 'Released', 'Changes Requested', 'Rejected', 'Retired');

CREATE TABLE content_items (
    content_item_id SERIAL PRIMARY KEY,
    item_code VARCHAR(30) UNIQUE NOT NULL,          -- 'CNT-000012'
    title VARCHAR(200) NOT NULL,
    description TEXT,
    content_type content_type NOT NULL,
    language VARCHAR(2) NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'te')),
    course_id INT NOT NULL REFERENCES courses(course_id),
    curriculum_version_id INT REFERENCES curriculum_versions(curriculum_version_id),  -- NULL = any version of the course
    module_id INT REFERENCES curriculum_modules(module_id),
    topic_id INT REFERENCES curriculum_topics(topic_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),  -- the audience never crosses branches
    batch_id INT REFERENCES batches(batch_id),      -- NULL = every student of the course at the branch
    download_allowed BOOLEAN NOT NULL DEFAULT TRUE, -- enforced when the file is served, not only in the UI
    status content_status NOT NULL DEFAULT 'Draft', -- of the latest version; Retired when the item is withdrawn
    owner_user_id INT NOT NULL REFERENCES users(user_id),  -- the author
    retired_at TIMESTAMPTZ,
    retired_by INT REFERENCES users(user_id),
    retire_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT content_items_retired CHECK ((status = 'Retired') = (retired_at IS NOT NULL)),
    CONSTRAINT content_items_retire_reason CHECK (retired_at IS NULL OR retire_reason IS NOT NULL),
    CONSTRAINT content_items_topic_needs_module CHECK (topic_id IS NULL OR module_id IS NOT NULL),
    CONSTRAINT content_items_module_needs_version CHECK (module_id IS NULL OR curriculum_version_id IS NOT NULL)
);

CREATE INDEX content_items_branch_idx ON content_items (branch_id, status);
CREATE INDEX content_items_course_idx ON content_items (course_id, curriculum_version_id);
CREATE INDEX content_items_topic_idx ON content_items (topic_id);
CREATE INDEX content_items_owner_idx ON content_items (owner_user_id);

CREATE TRIGGER trg_content_items_updated_at
    BEFORE UPDATE ON content_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- The placement must be consistent: topic in module in version of the course; the batch teaches that course at that branch
CREATE OR REPLACE FUNCTION content_items_before_write() RETURNS trigger AS $$
DECLARE
    v_batch batches%ROWTYPE;
BEGIN
    IF TG_OP = 'INSERT' AND NEW.item_code IS NULL THEN
        NEW.item_code = 'CNT-' || lpad(next_counter_value('CNT')::TEXT, 6, '0');
    ELSIF TG_OP = 'UPDATE' AND NEW.item_code <> OLD.item_code THEN
        RAISE EXCEPTION 'item_code cannot change';
    END IF;

    IF NEW.curriculum_version_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM curriculum_versions WHERE curriculum_version_id = NEW.curriculum_version_id AND course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'The curriculum version does not belong to this course';
    END IF;
    IF NEW.module_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM curriculum_modules WHERE module_id = NEW.module_id AND curriculum_version_id = NEW.curriculum_version_id) THEN
        RAISE EXCEPTION 'The module does not belong to this curriculum version';
    END IF;
    IF NEW.topic_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM curriculum_topics WHERE topic_id = NEW.topic_id AND module_id = NEW.module_id) THEN
        RAISE EXCEPTION 'The topic does not belong to this module';
    END IF;
    IF NEW.batch_id IS NOT NULL THEN
        SELECT * INTO v_batch FROM batches WHERE batch_id = NEW.batch_id;
        IF v_batch.course_id <> NEW.course_id THEN
            RAISE EXCEPTION 'Batch % is for a different course', v_batch.batch_code;
        END IF;
        IF v_batch.branch_id <> NEW.branch_id THEN
            RAISE EXCEPTION 'Batch % is at a different branch than this content', v_batch.batch_code;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_content_items_write
    BEFORE INSERT OR UPDATE ON content_items
    FOR EACH ROW EXECUTE FUNCTION content_items_before_write();

-- ---------------------------------------------------------------------------
-- Content versions: a new upload never overwrites; earlier versions are kept
-- ---------------------------------------------------------------------------
CREATE TYPE content_storage_kind AS ENUM ('File', 'Link');

CREATE TABLE content_versions (
    content_version_id SERIAL PRIMARY KEY,
    content_item_id INT NOT NULL REFERENCES content_items(content_item_id),
    version_no SMALLINT NOT NULL CHECK (version_no > 0),
    storage_kind content_storage_kind NOT NULL,
    file_path VARCHAR(500),                         -- relative to UPLOAD_DIR
    original_filename VARCHAR(255),
    mime_type VARCHAR(100),
    file_size_bytes BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes > 0),
    url VARCHAR(1000),
    change_summary TEXT,
    status content_status NOT NULL DEFAULT 'Draft',
    uploaded_by INT NOT NULL REFERENCES users(user_id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,
    released_by INT REFERENCES users(user_id),

    CONSTRAINT content_versions_unique UNIQUE (content_item_id, version_no),
    CONSTRAINT content_versions_file CHECK ((storage_kind = 'File') = (file_path IS NOT NULL)),
    CONSTRAINT content_versions_link CHECK ((storage_kind = 'Link') = (url IS NOT NULL)),
    CONSTRAINT content_versions_released CHECK (status <> 'Released' OR released_at IS NOT NULL)
);

CREATE INDEX content_versions_item_idx ON content_versions (content_item_id, version_no DESC);

-- ---------------------------------------------------------------------------
-- Review history: who submitted, reviewed, released or retired what, and why
-- ---------------------------------------------------------------------------
CREATE TYPE content_review_action AS ENUM ('Submitted', 'Review Started', 'Approved', 'Changes Requested', 'Rejected', 'Released', 'Retired');

CREATE TABLE content_reviews (
    review_id SERIAL PRIMARY KEY,
    content_item_id INT NOT NULL REFERENCES content_items(content_item_id),
    content_version_id INT NOT NULL REFERENCES content_versions(content_version_id),
    action content_review_action NOT NULL,
    actor_user_id INT NOT NULL REFERENCES users(user_id),
    comment TEXT,
    acted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT content_reviews_comment CHECK (action NOT IN ('Changes Requested', 'Rejected', 'Retired') OR coalesce(length(btrim(comment)), 0) > 0)
);

CREATE INDEX content_reviews_item_idx ON content_reviews (content_item_id, acted_at);

-- ---------------------------------------------------------------------------
-- Recordings: a controlled reference to the one media asset of an actual class session (never a copy of the video)
-- ---------------------------------------------------------------------------
CREATE TYPE recording_status AS ENUM ('Processing', 'Released', 'Partial', 'Held', 'Unavailable', 'Expired');

CREATE TABLE recordings (
    recording_id SERIAL PRIMARY KEY,
    recording_code VARCHAR(30) UNIQUE NOT NULL,     -- 'RCD-000012'
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    part_no SMALLINT NOT NULL DEFAULT 1 CHECK (part_no > 0),  -- one class can have several recording parts
    status recording_status NOT NULL DEFAULT 'Processing',
    source VARCHAR(50) NOT NULL DEFAULT 'Google Drive' CHECK (source IN ('Google Drive', 'Manual upload')),
    media_ref VARCHAR(500),                         -- stable provider id (Drive file id), never a public link
    duration_minutes INT CHECK (duration_minutes IS NULL OR duration_minutes > 0),
    download_allowed BOOLEAN NOT NULL DEFAULT FALSE,  -- controlled viewing by default (Module 17 §7)
    released_at TIMESTAMPTZ,
    released_by INT REFERENCES users(user_id),
    hold_reason TEXT,
    partial_note TEXT,                              -- what was and was not captured
    created_by INT REFERENCES users(user_id),       -- NULL when raised by the recording-check job
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT recordings_one_part UNIQUE (session_id, part_no),
    CONSTRAINT recordings_released CHECK (status <> 'Released' OR (released_at IS NOT NULL AND media_ref IS NOT NULL)),
    CONSTRAINT recordings_held_reason CHECK (status <> 'Held' OR coalesce(length(btrim(hold_reason)), 0) > 0),
    CONSTRAINT recordings_partial_note CHECK (status <> 'Partial' OR coalesce(length(btrim(partial_note)), 0) > 0)
);

CREATE INDEX recordings_status_idx ON recordings (status);

CREATE TRIGGER trg_recordings_updated_at
    BEFORE UPDATE ON recordings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION recordings_before_write() RETURNS trigger AS $$
DECLARE
    v_state session_state;
BEGIN
    IF TG_OP = 'INSERT' AND NEW.recording_code IS NULL THEN
        NEW.recording_code = 'RCD-' || lpad(next_counter_value('RCD')::TEXT, 6, '0');
    ELSIF TG_OP = 'UPDATE' AND NEW.recording_code <> OLD.recording_code THEN
        RAISE EXCEPTION 'recording_code cannot change';
    END IF;
    IF TG_OP = 'INSERT' OR NEW.session_id <> OLD.session_id THEN
        SELECT state INTO v_state FROM class_sessions WHERE session_id = NEW.session_id;
        IF v_state = 'Cancelled' THEN
            RAISE EXCEPTION 'A cancelled class session has no recording';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recordings_write
    BEFORE INSERT OR UPDATE ON recordings
    FOR EACH ROW EXECUTE FUNCTION recordings_before_write();

-- ---------------------------------------------------------------------------
-- Recording exceptions (RX-0012): every recording promise that is not being kept has a named owner
-- ---------------------------------------------------------------------------
CREATE TYPE recording_issue_type AS ENUM ('Partial', 'Held', 'Unavailable', 'Integration Unavailable');
CREATE TYPE recording_exception_status AS ENUM ('Open', 'In Progress', 'Resolved');

CREATE TABLE recording_exceptions (
    exception_id SERIAL PRIMARY KEY,
    exception_code VARCHAR(20) UNIQUE NOT NULL,     -- 'RX-0012'
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    recording_id INT REFERENCES recordings(recording_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),  -- the batch's branch
    issue_type recording_issue_type NOT NULL,
    issue TEXT NOT NULL,
    status recording_exception_status NOT NULL DEFAULT 'Open',
    owner_role VARCHAR(50) NOT NULL CHECK (owner_role IN ('ACADEMIC_COORDINATOR', 'SUPER_ADMIN', 'BRANCH_MANAGER')),
    owner_user_id INT REFERENCES users(user_id),    -- the person who took it on
    auto_raised BOOLEAN NOT NULL DEFAULT FALSE,     -- raised by the recording-check job or by a hold / partial mark
    raised_by INT REFERENCES users(user_id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    resolved_by INT REFERENCES users(user_id),
    resolution_note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT recording_exceptions_resolved CHECK (
        (status = 'Resolved') = (resolved_at IS NOT NULL) AND (status <> 'Resolved' OR coalesce(length(btrim(resolution_note)), 0) > 0))
);

-- One open exception per session and issue: repeated checks do not pile up duplicates
CREATE UNIQUE INDEX recording_exceptions_one_open
    ON recording_exceptions (session_id, issue_type) WHERE status <> 'Resolved';
CREATE INDEX recording_exceptions_branch_idx ON recording_exceptions (branch_id, status);

CREATE TRIGGER trg_recording_exceptions_updated_at
    BEFORE UPDATE ON recording_exceptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION recording_exceptions_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.exception_code IS NULL THEN
        NEW.exception_code = 'RX-' || lpad(next_counter_value('RX')::TEXT, 4, '0');
    ELSIF TG_OP = 'UPDATE' AND NEW.exception_code <> OLD.exception_code THEN
        RAISE EXCEPTION 'exception_code cannot change';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM class_sessions s JOIN batches b ON b.batch_id = s.batch_id
        WHERE s.session_id = NEW.session_id AND b.branch_id = NEW.branch_id) THEN
        RAISE EXCEPTION 'The exception''s branch must be the branch of the session''s batch';
    END IF;
    IF NEW.recording_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM recordings WHERE recording_id = NEW.recording_id AND session_id = NEW.session_id) THEN
        RAISE EXCEPTION 'The recording belongs to a different class session';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recording_exceptions_write
    BEFORE INSERT OR UPDATE ON recording_exceptions
    FOR EACH ROW EXECUTE FUNCTION recording_exceptions_before_write();

-- ---------------------------------------------------------------------------
-- Access extension requests (EXT-031): one requested extra year for recordings and / or materials, per enrolment
-- ---------------------------------------------------------------------------
CREATE TYPE extension_scope AS ENUM ('Recording', 'Material', 'Both');
CREATE TYPE extension_status AS ENUM ('Pending', 'Approved', 'Rejected');

CREATE TABLE access_extension_requests (
    request_id SERIAL PRIMARY KEY,
    request_code VARCHAR(20) UNIQUE NOT NULL,       -- 'EXT-031'
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),  -- the enrolment's service branch: who decides
    scope extension_scope NOT NULL,
    reason TEXT NOT NULL CHECK (coalesce(length(btrim(reason)), 0) > 0),
    status extension_status NOT NULL DEFAULT 'Pending',
    needs_exception BOOLEAN NOT NULL DEFAULT FALSE, -- asked after the second anniversary: Founder / Super Admin only
    original_expiry DATE NOT NULL,                  -- expiry when the request was made (first anniversary)
    approved_expiry DATE,                           -- new expiry, set on approval
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,

    CONSTRAINT access_extension_decided CHECK ((status = 'Pending') = (decided_at IS NULL)),
    CONSTRAINT access_extension_approved CHECK ((status = 'Approved') = (approved_expiry IS NOT NULL)),
    CONSTRAINT access_extension_rejected_note CHECK (status <> 'Rejected' OR coalesce(length(btrim(decision_note)), 0) > 0),
    CONSTRAINT access_extension_expiry CHECK (approved_expiry IS NULL OR approved_expiry > original_expiry)
);

-- One request waiting per enrolment and scope; a repeat cannot be raised until it is decided
CREATE UNIQUE INDEX access_extension_one_pending ON access_extension_requests (enrolment_id, scope) WHERE status = 'Pending';
CREATE INDEX access_extension_branch_idx ON access_extension_requests (branch_id, status);
CREATE INDEX access_extension_student_idx ON access_extension_requests (student_id);

CREATE OR REPLACE FUNCTION access_extension_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.request_code IS NULL THEN
        NEW.request_code = 'EXT-' || lpad(next_counter_value('EXT')::TEXT, 3, '0');
    ELSIF TG_OP = 'UPDATE' AND NEW.request_code <> OLD.request_code THEN
        RAISE EXCEPTION 'request_code cannot change';
    END IF;
    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1 FROM enrolments WHERE enrolment_id = NEW.enrolment_id AND student_id = NEW.student_id AND service_branch_id = NEW.branch_id) THEN
        RAISE EXCEPTION 'The request must match the enrolment''s student and service branch';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_access_extension_write
    BEFORE INSERT OR UPDATE ON access_extension_requests
    FOR EACH ROW EXECUTE FUNCTION access_extension_before_write();

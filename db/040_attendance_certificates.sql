-- Phase 2 / S4 040: attendance, recovery, corrections, the four progress measures, completion review, Certificate Register
-- Depends on: 004_batches_sessions.sql (class sessions, allocations) and the backbone tables before it.
-- Only backbone objects are read; nothing in 001-004 is altered (enrolments.joining_date / status / certificate_status are
-- written by the S4 services and a trigger below).

-- ---------------------------------------------------------------------------
-- Settings owned by this slice (admin-editable, read by the views and services)
-- ---------------------------------------------------------------------------
INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('attendance_lock_days', '7', 'Days after a session ends before its attendance is locked; later changes need Academic Coordinator approval'),
    ('attendance_alert_threshold', '75', 'Attendance % below which a student is flagged (after three marked sessions)'),
    ('engagement_window_days', '14', 'Days of LMS activity the Engagement measure looks at'),
    ('engagement_high_events', '8', 'Activity events in the window for Engagement = High'),
    ('engagement_medium_events', '3', 'Activity events in the window for Engagement = Medium (fewer is Low)'),
    ('complimentary_completion_rule_configured', 'false', 'TRUE once a completion rule exists for complimentary offers; until then their certificates stay Configuration Pending')
ON CONFLICT (setting_key) DO NOTHING;

CREATE OR REPLACE FUNCTION attendance_setting(p_key TEXT, p_default INT) RETURNS INT AS $$
    SELECT COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = p_key), p_default);
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Attendance: one row per actual Class Session x allocated enrolment, written by the trainer (or Academic Coordinator).
-- No row = "Not yet marked"; a missing entry is never a guessed absence.
-- ---------------------------------------------------------------------------
CREATE TYPE attendance_status AS ENUM ('Present', 'Absent', 'Late', 'Excused');

CREATE TABLE attendance_records (
    attendance_id BIGSERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    status attendance_status NOT NULL,
    remarks TEXT,                                   -- an Excused entry names its approved reason
    marked_by INT NOT NULL REFERENCES users(user_id),
    marked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,   -- when the trainer confirmed (the class date is the session's)
    corrected_by INT REFERENCES users(user_id),     -- set when an approved correction changed the entry
    corrected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT attendance_records_one_per_session UNIQUE (session_id, enrolment_id),
    CONSTRAINT attendance_records_excused_has_reason CHECK (status <> 'Excused' OR length(btrim(COALESCE(remarks, ''))) > 0),
    CONSTRAINT attendance_records_correction CHECK ((corrected_by IS NULL) = (corrected_at IS NULL))
);

CREATE INDEX attendance_records_enrolment_idx ON attendance_records (enrolment_id);

CREATE TRIGGER trg_attendance_records_updated_at
    BEFORE UPDATE ON attendance_records
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Only a Live or Delivered session can have attendance, and only for an enrolment that holds (or held) a seat in its batch
CREATE OR REPLACE FUNCTION check_attendance_record() RETURNS trigger AS $$
DECLARE
    v_state session_state;
    v_batch INT;
BEGIN
    SELECT state, batch_id INTO v_state, v_batch FROM class_sessions WHERE session_id = NEW.session_id;
    IF v_state NOT IN ('Live', 'Delivered') THEN
        RAISE EXCEPTION 'Attendance can only be marked for a Live or Delivered session (this one is %)', v_state;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM batch_allocations WHERE enrolment_id = NEW.enrolment_id AND batch_id = v_batch) THEN
        RAISE EXCEPTION 'This enrolment is not allocated to the batch of the session';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_attendance_records_check
    BEFORE INSERT ON attendance_records
    FOR EACH ROW EXECUTE FUNCTION check_attendance_record();

-- When the entry stops being changeable without approval: the session end plus attendance_lock_days
CREATE OR REPLACE FUNCTION attendance_lock_time(p_session_ends_at TIMESTAMPTZ) RETURNS TIMESTAMPTZ AS $$
    SELECT p_session_ends_at + make_interval(days => attendance_setting('attendance_lock_days', 7));
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Recovery for an absence (REC-0041): the student or the trainer raises it, the Academic Coordinator approves,
-- the evidence is verified on completion. The original Absent entry is never rewritten.
-- ---------------------------------------------------------------------------
CREATE TYPE recovery_method AS ENUM ('Recording watched', 'Extra session', 'Assignment');
CREATE TYPE recovery_status AS ENUM ('Requested', 'Approved', 'Rejected', 'Completed');

CREATE TABLE attendance_recoveries (
    recovery_id SERIAL PRIMARY KEY,
    recovery_code VARCHAR(20) UNIQUE NOT NULL,      -- 'REC-0041'
    attendance_id BIGINT NOT NULL REFERENCES attendance_records(attendance_id),
    method recovery_method NOT NULL,
    status recovery_status NOT NULL DEFAULT 'Requested',
    reason TEXT NOT NULL,
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    target_date DATE,                               -- agreed date to complete the recovery
    completed_by INT REFERENCES users(user_id),
    completed_at TIMESTAMPTZ,
    evidence_note TEXT,                             -- what was verified (a recording link alone is not evidence)
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT attendance_recoveries_decision CHECK ((status IN ('Requested')) = (decided_at IS NULL)),
    CONSTRAINT attendance_recoveries_rejection_note CHECK (status <> 'Rejected' OR length(btrim(COALESCE(decision_note, ''))) > 0),
    CONSTRAINT attendance_recoveries_completion CHECK ((status = 'Completed') = (completed_at IS NOT NULL)),
    CONSTRAINT attendance_recoveries_evidence CHECK (status <> 'Completed' OR length(btrim(COALESCE(evidence_note, ''))) > 0)
);

-- One live recovery per absence (a rejected one can be raised again)
CREATE UNIQUE INDEX attendance_recoveries_one_live
    ON attendance_recoveries (attendance_id) WHERE status IN ('Requested', 'Approved', 'Completed');

CREATE TRIGGER trg_attendance_recoveries_updated_at
    BEFORE UPDATE ON attendance_recoveries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION attendance_recoveries_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (SELECT status FROM attendance_records WHERE attendance_id = NEW.attendance_id) <> 'Absent' THEN
            RAISE EXCEPTION 'Recovery can only be raised for an Absent entry';
        END IF;
        IF NEW.recovery_code IS NULL THEN
            LOOP
                NEW.recovery_code = 'REC-' || lpad(next_counter_value('REC')::TEXT, 4, '0');
                EXIT WHEN NOT EXISTS (SELECT 1 FROM attendance_recoveries WHERE recovery_code = NEW.recovery_code);
            END LOOP;
        END IF;
    ELSIF NEW.recovery_code <> OLD.recovery_code OR NEW.attendance_id <> OLD.attendance_id THEN
        RAISE EXCEPTION 'recovery_code and the absence it recovers cannot change';
    ELSIF OLD.status IN ('Rejected', 'Completed') AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION 'A % recovery is final', OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_attendance_recoveries_write
    BEFORE INSERT OR UPDATE ON attendance_recoveries
    FOR EACH ROW EXECUTE FUNCTION attendance_recoveries_before_write();

-- ---------------------------------------------------------------------------
-- Corrections: any change to attendance after it is locked (or a student's dispute) needs Academic Coordinator approval.
-- The original entry stays visible until the correction is decided.
-- ---------------------------------------------------------------------------
CREATE TYPE correction_status AS ENUM ('Pending', 'Approved', 'Rejected');

CREATE TABLE attendance_corrections (
    correction_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    requested_status attendance_status NOT NULL,
    previous_status attendance_status,              -- NULL: the session was never marked for this enrolment
    reason TEXT NOT NULL,
    status correction_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,

    CONSTRAINT attendance_corrections_reason CHECK (length(btrim(reason)) > 0),
    CONSTRAINT attendance_corrections_decision CHECK ((status = 'Pending') = (decided_at IS NULL)),
    CONSTRAINT attendance_corrections_independent CHECK (decided_by IS NULL OR decided_by <> requested_by),
    CONSTRAINT attendance_corrections_rejection_note CHECK (status <> 'Rejected' OR length(btrim(COALESCE(decision_note, ''))) > 0)
);

CREATE UNIQUE INDEX attendance_corrections_one_pending
    ON attendance_corrections (session_id, enrolment_id) WHERE status = 'Pending';
CREATE INDEX attendance_corrections_status_idx ON attendance_corrections (status, requested_at DESC);

-- ---------------------------------------------------------------------------
-- Progress: four separate measures per enrolment, never one blended score.
--   Delivery          delivered sessions / planned sessions of the enrolment's batch
--   Attendance        (Present + Late) / marked sessions delivered since the joining date; Partial Data while any is unmarked
--   Required learning required topics covered by an attended or recovered session / required topics of the curriculum
--   Engagement        LMS activity events in the last engagement_window_days
-- ---------------------------------------------------------------------------

-- Batches an enrolment holds or held a seat in (allocations of a combo track collapse into one row per batch)
CREATE VIEW enrolment_batch_links AS
SELECT enrolment_id, batch_id,
       bool_or(status = 'Active') AS is_current,
       max(effective_to) AS last_effective_to
FROM batch_allocations
GROUP BY enrolment_id, batch_id;

-- Delivered sessions since the enrolment's joining date, each with the enrolment's entry and its live recovery
CREATE VIEW attendance_grid AS
SELECT e.enrolment_id, cs.session_id, cs.batch_id, cs.topic_id, cs.starts_at, cs.ends_at,
       ar.attendance_id, ar.status AS attendance_status,
       rec.recovery_id, rec.recovery_code, rec.status AS recovery_status
FROM enrolments e
JOIN enrolment_batch_links l ON l.enrolment_id = e.enrolment_id
JOIN class_sessions cs ON cs.batch_id = l.batch_id AND cs.state = 'Delivered'
LEFT JOIN attendance_records ar ON ar.session_id = cs.session_id AND ar.enrolment_id = e.enrolment_id
LEFT JOIN attendance_recoveries rec ON rec.attendance_id = ar.attendance_id AND rec.status IN ('Requested', 'Approved', 'Completed')
WHERE e.joining_date IS NOT NULL
  AND (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date >= e.joining_date
  AND (l.is_current OR (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date <= l.last_effective_to);

CREATE VIEW enrolment_delivery AS
SELECT e.enrolment_id,
       count(cs.session_id) FILTER (WHERE cs.state = 'Delivered') AS delivered_sessions,
       count(cs.session_id) FILTER (WHERE cs.state IN ('Scheduled', 'Live', 'Delivered')) AS planned_sessions
FROM enrolments e
LEFT JOIN enrolment_batch_links l ON l.enrolment_id = e.enrolment_id
LEFT JOIN class_sessions cs ON cs.batch_id = l.batch_id
GROUP BY e.enrolment_id;

CREATE VIEW enrolment_attendance AS
SELECT e.enrolment_id,
       count(g.session_id) AS delivered_since_joining,
       count(g.attendance_id) AS marked_sessions,
       count(g.session_id) - count(g.attendance_id) AS unmarked_sessions,
       count(*) FILTER (WHERE g.attendance_status = 'Present') AS present_count,
       count(*) FILTER (WHERE g.attendance_status = 'Late') AS late_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent') AS absent_count,
       count(*) FILTER (WHERE g.attendance_status = 'Excused') AS excused_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent' AND g.recovery_status IN ('Approved', 'Completed')) AS recovered_count
FROM enrolments e
LEFT JOIN attendance_grid g ON g.enrolment_id = e.enrolment_id
GROUP BY e.enrolment_id;

-- Required topics of every curriculum version the enrolment follows (the parent version and each combo track's version)
CREATE VIEW enrolment_required_topics AS
SELECT v.enrolment_id, t.topic_id
FROM (
    SELECT enrolment_id, curriculum_version_id FROM enrolments WHERE curriculum_version_id IS NOT NULL
    UNION
    SELECT enrolment_id, curriculum_version_id FROM enrolment_tracks WHERE curriculum_version_id IS NOT NULL
) v
JOIN curriculum_modules m ON m.curriculum_version_id = v.curriculum_version_id
JOIN curriculum_topics t ON t.module_id = m.module_id AND t.is_required;

-- Topics taught in a delivered session the student attended (Present / Late) or recovered (approved recovery)
CREATE VIEW enrolment_covered_topics AS
SELECT DISTINCT enrolment_id, topic_id
FROM attendance_grid
WHERE topic_id IS NOT NULL
  AND (attendance_status IN ('Present', 'Late') OR recovery_status IN ('Approved', 'Completed'));

CREATE VIEW enrolment_required_learning AS
SELECT e.enrolment_id,
       count(rt.topic_id) AS required_topics,
       count(ct.topic_id) AS covered_topics
FROM enrolments e
LEFT JOIN enrolment_required_topics rt ON rt.enrolment_id = e.enrolment_id
LEFT JOIN enrolment_covered_topics ct ON ct.enrolment_id = rt.enrolment_id AND ct.topic_id = rt.topic_id
GROUP BY e.enrolment_id;

-- Logins (not tied to a course) and this enrolment's own resource / recording events
CREATE VIEW enrolment_engagement AS
SELECT e.enrolment_id,
       count(a.activity_id) AS events_total,
       count(a.activity_id) FILTER (
           WHERE a.occurred_at > CURRENT_TIMESTAMP - make_interval(days => attendance_setting('engagement_window_days', 14))
       ) AS events_recent,
       max(a.occurred_at) AS last_activity_at
FROM enrolments e
LEFT JOIN activity_events a ON a.student_id = e.student_id AND (a.enrolment_id = e.enrolment_id OR a.enrolment_id IS NULL)
GROUP BY e.enrolment_id;

CREATE VIEW enrolment_progress AS
SELECT e.enrolment_id, e.student_id, e.course_id, e.service_branch_id,
       d.delivered_sessions, d.planned_sessions,
       CASE WHEN d.planned_sessions > 0 THEN round(100.0 * d.delivered_sessions / d.planned_sessions, 1) END AS delivery_pct,
       a.delivered_since_joining, a.marked_sessions, a.unmarked_sessions,
       a.present_count, a.late_count, a.absent_count, a.excused_count, a.recovered_count,
       CASE WHEN e.joining_date IS NULL OR a.delivered_since_joining = 0 THEN 'Not started'
            WHEN a.unmarked_sessions > 0 THEN 'Partial Data'
            ELSE 'Calculated' END AS attendance_state,
       CASE WHEN a.marked_sessions > 0
            THEN round(100.0 * (a.present_count + a.late_count) / a.marked_sessions, 1) END AS attendance_pct,
       COALESCE(a.marked_sessions >= 3
                AND 100.0 * (a.present_count + a.late_count) / NULLIF(a.marked_sessions, 0) < attendance_setting('attendance_alert_threshold', 75),
                FALSE) AS attendance_alert,
       r.required_topics, r.covered_topics,
       CASE WHEN r.required_topics > 0 THEN round(100.0 * r.covered_topics / r.required_topics, 1) END AS required_pct,
       g.events_recent, g.last_activity_at,
       CASE WHEN g.events_total = 0 THEN 'Not started'
            WHEN g.events_recent >= attendance_setting('engagement_high_events', 8) THEN 'High'
            WHEN g.events_recent >= attendance_setting('engagement_medium_events', 3) THEN 'Medium'
            ELSE 'Low' END AS engagement_level
FROM enrolments e
JOIN enrolment_delivery d ON d.enrolment_id = e.enrolment_id
JOIN enrolment_attendance a ON a.enrolment_id = e.enrolment_id
JOIN enrolment_required_learning r ON r.enrolment_id = e.enrolment_id
JOIN enrolment_engagement g ON g.enrolment_id = e.enrolment_id;

-- ---------------------------------------------------------------------------
-- Completion review: evidence-based decision per enrolment (a percentage alone never completes a course)
-- ---------------------------------------------------------------------------
CREATE TYPE completion_decision AS ENUM ('Complete', 'Not Yet', 'Needs Recovery');
CREATE TYPE completion_review_status AS ENUM ('Open', 'Decided');

CREATE TABLE completion_reviews (
    review_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    status completion_review_status NOT NULL DEFAULT 'Open',
    opened_by INT NOT NULL REFERENCES users(user_id),
    trainer_recommendation completion_decision,
    trainer_comment TEXT,
    recommended_by INT REFERENCES users(user_id),
    recommended_at TIMESTAMPTZ,
    decision completion_decision,
    decision_reason TEXT,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    evidence JSONB,                                 -- the four measures + open recoveries as they were when decided
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT completion_reviews_decided CHECK ((status = 'Decided') = (decision IS NOT NULL AND decided_at IS NOT NULL AND evidence IS NOT NULL)),
    CONSTRAINT completion_reviews_reason CHECK (decision IS NULL OR decision = 'Complete' OR length(btrim(COALESCE(decision_reason, ''))) > 0),
    CONSTRAINT completion_reviews_recommendation CHECK ((trainer_recommendation IS NULL) = (recommended_at IS NULL))
);

CREATE UNIQUE INDEX completion_reviews_one_open ON completion_reviews (enrolment_id) WHERE status = 'Open';
CREATE INDEX completion_reviews_enrolment_idx ON completion_reviews (enrolment_id, review_id DESC);

CREATE TRIGGER trg_completion_reviews_updated_at
    BEFORE UPDATE ON completion_reviews
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION completion_reviews_before_write() RETURNS trigger AS $$
DECLARE
    v_open_recoveries INT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF (SELECT status FROM enrolments WHERE enrolment_id = NEW.enrolment_id) <> 'Active' THEN
            RAISE EXCEPTION 'Only an Active enrolment can be reviewed for completion';
        END IF;
    ELSIF OLD.status = 'Decided' THEN
        RAISE EXCEPTION 'A decided completion review is final; open a new review to reconsider';
    END IF;

    IF NEW.decision = 'Complete' THEN
        SELECT count(*) INTO v_open_recoveries
        FROM attendance_recoveries r
        JOIN attendance_records ar ON ar.attendance_id = r.attendance_id
        WHERE ar.enrolment_id = NEW.enrolment_id AND r.status IN ('Requested', 'Approved');
        IF v_open_recoveries > 0 THEN
            RAISE EXCEPTION 'Cannot complete: % recovery(ies) still open for this enrolment', v_open_recoveries;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_completion_reviews_write
    BEFORE INSERT OR UPDATE ON completion_reviews
    FOR EACH ROW EXECUTE FUNCTION completion_reviews_before_write();

-- ---------------------------------------------------------------------------
-- LMS Certificate Register: the single source for certificates. A reissue is a new version row (same number) and the
-- earlier version becomes Superseded; the number is allocated only at first issue and never changes.
-- ---------------------------------------------------------------------------
CREATE TYPE certificate_type AS ENUM ('Course Completion Certificate', 'Internship Certificate');
CREATE TYPE certificate_status AS ENUM (
    'Not Yet Eligible', 'Eligibility Review', 'Awaiting Approval', 'Approved for Issue', 'Issued', 'Superseded', 'Revoked'
);

CREATE TABLE certificates (
    certificate_id SERIAL PRIMARY KEY,
    certificate_number VARCHAR(30),                 -- 'NIT-CERT-2026-000001'; NULL until first issue
    certificate_type certificate_type NOT NULL,
    version SMALLINT NOT NULL DEFAULT 1 CHECK (version >= 1),
    status certificate_status NOT NULL DEFAULT 'Not Yet Eligible',
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    course_id INT NOT NULL REFERENCES courses(course_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),      -- service branch of the enrolment: who approves and sees it
    holder_name VARCHAR(150) NOT NULL,              -- the name printed on this version (a correction is a reissue)
    completion_review_id INT REFERENCES completion_reviews(review_id),
    issue_date DATE,                                -- IST business date of issue
    reason TEXT,                                    -- why this version exists (reissue) or was revoked
    recommended_by INT REFERENCES users(user_id),
    recommended_at TIMESTAMPTZ,
    approved_by INT REFERENCES users(user_id),
    approved_at TIMESTAMPTZ,
    issued_by INT REFERENCES users(user_id),
    revoked_by INT REFERENCES users(user_id),
    revoked_at TIMESTAMPTZ,
    supersedes_certificate_id INT REFERENCES certificates(certificate_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT certificates_number_once_issued CHECK ((status IN ('Issued', 'Superseded', 'Revoked')) = (certificate_number IS NOT NULL)),
    CONSTRAINT certificates_issue_date CHECK ((certificate_number IS NOT NULL) = (issue_date IS NOT NULL)),
    CONSTRAINT certificates_reissue_link CHECK ((version > 1) = (supersedes_certificate_id IS NOT NULL)),
    CONSTRAINT certificates_reissue_reason CHECK (version = 1 OR length(btrim(COALESCE(reason, ''))) > 0),
    CONSTRAINT certificates_revoked CHECK (status <> 'Revoked' OR (length(btrim(COALESCE(reason, ''))) > 0 AND revoked_by IS NOT NULL AND revoked_at IS NOT NULL)),
    CONSTRAINT certificates_approved CHECK (status NOT IN ('Approved for Issue', 'Issued') OR approved_by IS NOT NULL),
    CONSTRAINT certificates_issued_by CHECK (status <> 'Issued' OR issued_by IS NOT NULL)
);

CREATE UNIQUE INDEX certificates_number_version ON certificates (certificate_number, version) WHERE certificate_number IS NOT NULL;
-- One live register entry per enrolment and certificate type (earlier versions are Superseded)
CREATE UNIQUE INDEX certificates_one_live ON certificates (enrolment_id, certificate_type) WHERE status <> 'Superseded';
CREATE INDEX certificates_branch_status_idx ON certificates (branch_id, status);
CREATE INDEX certificates_student_idx ON certificates (student_id);

CREATE TRIGGER trg_certificates_updated_at
    BEFORE UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- NIT-CERT-YYYY-NNNNNN, skipping numbers already taken
CREATE OR REPLACE FUNCTION next_certificate_number() RETURNS TEXT AS $$
DECLARE
    v_year INT := business_year();
    v_number TEXT;
BEGIN
    LOOP
        v_number := 'NIT-CERT-' || v_year || '-' || lpad(next_counter_value('CERT-' || v_year)::TEXT, 6, '0');
        EXIT WHEN NOT EXISTS (SELECT 1 FROM certificates WHERE certificate_number = v_number);
    END LOOP;
    RETURN v_number;
END;
$$ LANGUAGE plpgsql;

-- Eligibility only opens for a Completed enrolment; a complimentary offer needs a configured completion rule
CREATE OR REPLACE FUNCTION check_certificate_eligibility(p_enrolment_id INT) RETURNS void AS $$
DECLARE
    v_enrolment enrolments%ROWTYPE;
BEGIN
    SELECT * INTO v_enrolment FROM enrolments WHERE enrolment_id = p_enrolment_id;
    IF v_enrolment.kind = 'Complimentary'
       AND COALESCE((SELECT setting_value = 'true'::jsonb FROM app_settings WHERE setting_key = 'complimentary_completion_rule_configured'), FALSE) IS NOT TRUE THEN
        RAISE EXCEPTION 'Configuration Pending: completion rule not configured for complimentary offer';
    END IF;
    IF v_enrolment.status <> 'Completed' THEN
        RAISE EXCEPTION 'Certificate eligibility opens only after a Complete completion decision (enrolment is %)', v_enrolment.status;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION certificates_before_write() RETURNS trigger AS $$
DECLARE
    v_previous certificates%ROWTYPE;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.version = 1 THEN
            IF NEW.status NOT IN ('Not Yet Eligible', 'Eligibility Review') THEN
                RAISE EXCEPTION 'A new register entry starts as Not Yet Eligible or Eligibility Review';
            END IF;
            IF NEW.status = 'Eligibility Review' THEN
                PERFORM check_certificate_eligibility(NEW.enrolment_id);
            END IF;
        ELSE
            SELECT * INTO v_previous FROM certificates WHERE certificate_id = NEW.supersedes_certificate_id;
            IF v_previous.status <> 'Superseded' OR v_previous.enrolment_id <> NEW.enrolment_id
               OR v_previous.certificate_type <> NEW.certificate_type OR v_previous.version + 1 <> NEW.version THEN
                RAISE EXCEPTION 'A reissue must follow the Superseded version it replaces';
            END IF;
            IF NEW.status <> 'Issued' THEN
                RAISE EXCEPTION 'A reissued version is Issued immediately';
            END IF;
            NEW.certificate_number = v_previous.certificate_number;
            NEW.issue_date = COALESCE(NEW.issue_date, (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date);
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.certificate_number IS DISTINCT FROM OLD.certificate_number AND OLD.certificate_number IS NOT NULL THEN
        RAISE EXCEPTION 'A certificate number never changes once issued';
    END IF;
    IF NEW.enrolment_id <> OLD.enrolment_id OR NEW.certificate_type <> OLD.certificate_type OR NEW.version <> OLD.version THEN
        RAISE EXCEPTION 'Enrolment, type and version of a register entry cannot change';
    END IF;
    IF NEW.status = OLD.status THEN
        IF OLD.status IN ('Superseded', 'Revoked') AND (NEW.holder_name <> OLD.holder_name OR NEW.reason IS DISTINCT FROM OLD.reason) THEN
            RAISE EXCEPTION 'A % certificate cannot be edited', OLD.status;
        END IF;
        RETURN NEW;
    END IF;

    IF NOT ((OLD.status, NEW.status) IN (
        ('Not Yet Eligible', 'Eligibility Review'),
        ('Eligibility Review', 'Awaiting Approval'),
        ('Awaiting Approval', 'Approved for Issue'),
        ('Awaiting Approval', 'Eligibility Review'),
        ('Approved for Issue', 'Issued'),
        ('Issued', 'Superseded'),
        ('Issued', 'Revoked')
    )) THEN
        RAISE EXCEPTION 'A certificate cannot move from % to %', OLD.status, NEW.status;
    END IF;

    IF OLD.status = 'Not Yet Eligible' THEN
        PERFORM check_certificate_eligibility(NEW.enrolment_id);
    END IF;
    IF NEW.status = 'Issued' THEN
        NEW.certificate_number = next_certificate_number();
        NEW.issue_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_certificates_write
    BEFORE INSERT OR UPDATE ON certificates
    FOR EACH ROW EXECUTE FUNCTION certificates_before_write();

-- Keep enrolments.certificate_status (shown on student and CRM-facing views) in step with the live register entry
CREATE OR REPLACE FUNCTION certificates_sync_enrolment() RETURNS trigger AS $$
BEGIN
    UPDATE enrolments SET certificate_status = COALESCE((
        SELECT status::TEXT FROM certificates
        WHERE enrolment_id = NEW.enrolment_id AND status <> 'Superseded'
        ORDER BY (certificate_type = 'Course Completion Certificate') DESC, certificate_id DESC LIMIT 1
    ), 'Not Yet Eligible')
    WHERE enrolment_id = NEW.enrolment_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_certificates_sync_enrolment
    AFTER INSERT OR UPDATE OF status ON certificates
    FOR EACH ROW EXECUTE FUNCTION certificates_sync_enrolment();

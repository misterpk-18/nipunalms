-- 005: alignment with the live CRM schema (nipuna-crm db 001–025), so real CRM events apply and the CRM's academic
-- columns can be fed from the LMS, which owns learning delivery.
-- Depends on: 004_batches_sessions.sql
--
--   CRM → LMS: complimentary courses arrive as their own CRM admission (admissions.complimentary_of_admission_id);
--              the CRM's seat type / planned start; its person code; course status 'Archived'.
--   LMS → CRM: per-admission academic state in the CRM's vocabulary (enrolment_status, curriculum_status,
--              batch allocations with joining date, completion) and every LMS batch, queued in crm_outbox.

-- ---------------------------------------------------------------------------
-- CRM vocabulary the LMS did not have
-- ---------------------------------------------------------------------------
ALTER TYPE course_status ADD VALUE IF NOT EXISTS 'Archived';

ALTER TABLE students
    ADD COLUMN crm_person_code VARCHAR(30);          -- the CRM's readable code, e.g. 'PER-GNT-00148' (display only)

ALTER TABLE admissions
    ADD COLUMN complimentary_of_admission_id INT REFERENCES admissions(admission_id),  -- CRM: complimentary admission → its paid one
    ADD COLUMN seat_type VARCHAR(20) CHECK (seat_type IN ('Confirmed Seat', 'Future Plan')),
    ADD COLUMN planned_start_date DATE,
    ADD CONSTRAINT admissions_complimentary_not_self CHECK (complimentary_of_admission_id <> admission_id);

-- When a course was academically completed (the CRM's admissions.academic_completed_at)
ALTER TABLE enrolments
    ADD COLUMN completed_at TIMESTAMPTZ;

CREATE OR REPLACE FUNCTION enrolments_stamp_completion() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'Completed' AND (TG_OP = 'INSERT' OR OLD.status <> 'Completed') THEN
        NEW.completed_at = COALESCE(NEW.completed_at, CURRENT_TIMESTAMP);
    ELSIF NEW.status <> 'Completed' THEN
        NEW.completed_at = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolments_completion
    BEFORE INSERT OR UPDATE OF status ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_stamp_completion();

-- A complimentary enrolment hangs off a paid enrolment of the same admission, or — as the CRM sends it — of the paid
-- admission its own admission is complimentary to
CREATE OR REPLACE FUNCTION check_enrolment_links() RETURNS trigger AS $$
DECLARE
    v_admission admissions%ROWTYPE;
    v_is_combo BOOLEAN;
    v_parent enrolments%ROWTYPE;
BEGIN
    SELECT * INTO v_admission FROM admissions WHERE admission_id = NEW.admission_id;
    IF v_admission.student_id <> NEW.student_id THEN
        RAISE EXCEPTION 'Enrolment student does not match the admission student';
    END IF;

    SELECT is_combo INTO v_is_combo FROM courses WHERE course_id = NEW.course_id;
    IF (NEW.kind = 'Combo') <> v_is_combo THEN
        RAISE EXCEPTION 'Only a combo course has a Combo enrolment (and every combo course must use one)';
    END IF;

    IF NEW.parent_enrolment_id IS NOT NULL THEN
        SELECT * INTO v_parent FROM enrolments WHERE enrolment_id = NEW.parent_enrolment_id;
        IF v_parent.kind = 'Complimentary' OR v_parent.student_id <> NEW.student_id
           OR v_parent.admission_id NOT IN (NEW.admission_id, COALESCE(v_admission.complimentary_of_admission_id, NEW.admission_id)) THEN
            RAISE EXCEPTION 'A complimentary enrolment must link to a paid enrolment of the same admission or of the paid admission it is complimentary to';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- LMS vocabulary → CRM vocabulary
-- ---------------------------------------------------------------------------
-- CRM admissions.enrolment_status: Awaiting Batch Allocation, Scheduled, In Progress, Deferred, Paused, Completed, Cancelled
CREATE OR REPLACE FUNCTION crm_enrolment_status(p_status enrolment_status) RETURNS TEXT AS $$
    SELECT CASE p_status
        WHEN 'Allocated — awaiting first regular class' THEN 'Scheduled'
        WHEN 'Active' THEN 'In Progress'
        WHEN 'Paused' THEN 'Paused'
        WHEN 'Completed' THEN 'Completed'
        WHEN 'Withdrawn' THEN 'Cancelled'
        ELSE 'Awaiting Batch Allocation'              -- Provisioning / Curriculum Mapping / Allocation Pending
    END;
$$ LANGUAGE sql IMMUTABLE;

-- CRM delivery_mode: Classroom, Online, Hybrid
CREATE OR REPLACE FUNCTION crm_delivery_mode(p_mode delivery_mode) RETURNS TEXT AS $$
    SELECT CASE p_mode WHEN 'Live Online' THEN 'Online' ELSE p_mode::TEXT END;
$$ LANGUAGE sql IMMUTABLE;

-- CRM batch_status: Planned, Open, In Progress, Completed, Cancelled
CREATE OR REPLACE FUNCTION crm_batch_status(p_state batch_state) RETURNS TEXT AS $$
    SELECT CASE p_state
        WHEN 'Forming' THEN 'Planned'
        WHEN 'Starting' THEN 'Open'
        WHEN 'Running' THEN 'In Progress'
        WHEN 'Full' THEN 'In Progress'
        ELSE p_state::TEXT                            -- Completed, Cancelled
    END;
$$ LANGUAGE sql IMMUTABLE;

-- ---------------------------------------------------------------------------
-- Academic state of one admission, as the CRM stores it
-- ---------------------------------------------------------------------------
-- The CRM admission is one course: its (non-complimentary-to-another) enrolment for admissions.course_id.
-- Allocations are per course the CRM knows: the enrolment's course, or each combo component course.
CREATE OR REPLACE FUNCTION admission_academic_state(p_admission_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'crm_admission_id', a.crm_admission_id,
        'enrolment_status', crm_enrolment_status(e.status),
        'curriculum_status', CASE WHEN e.curriculum_version_id IS NOT NULL
                                   AND NOT EXISTS (SELECT 1 FROM enrolment_tracks t
                                                   WHERE t.enrolment_id = e.enrolment_id AND t.curriculum_version_id IS NULL)
                                  THEN 'Mapped' ELSE 'Mapping Pending' END,
        'curriculum_version_label', cv.version_label,
        'service_branch_code', b.branch_code,
        'joining_date', e.joining_date,
        'academic_completed_at', e.completed_at,
        'allocations', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                       'course_code', COALESCE(cc.course_code, c.course_code),
                       'lms_course_id', bt.batch_code,
                       'crm_batch_id', bt.crm_batch_id,
                       'status', CASE ba.status
                                     WHEN 'Active' THEN 'Active'
                                     WHEN 'Transferred' THEN 'Moved'
                                     ELSE CASE WHEN e.status = 'Completed' THEN 'Completed' ELSE 'Withdrawn' END
                                 END,
                       'joining_date', e.joining_date,
                       'allocated_on', ba.effective_from,
                       'ended_on', ba.effective_to,
                       'end_reason', ba.reason)
                   ORDER BY ba.allocation_id)
            FROM batch_allocations ba
            JOIN batches bt ON bt.batch_id = ba.batch_id
            LEFT JOIN enrolment_tracks et ON et.enrolment_track_id = ba.enrolment_track_id
            LEFT JOIN course_components comp ON comp.component_id = et.component_id
            LEFT JOIN courses cc ON cc.course_id = comp.component_course_id
            WHERE ba.enrolment_id = e.enrolment_id), '[]'::jsonb))
    FROM admissions a
    JOIN enrolments e ON e.admission_id = a.admission_id AND e.course_id = a.course_id
    JOIN courses c ON c.course_id = e.course_id
    JOIN branches b ON b.branch_id = e.service_branch_id
    LEFT JOIN curriculum_versions cv ON cv.curriculum_version_id = e.curriculum_version_id
    WHERE a.admission_id = p_admission_id;
$$ LANGUAGE sql STABLE;

ALTER TABLE admission_lms_state
    ADD COLUMN academic JSONB,                       -- last academic state queued for the CRM
    ADD COLUMN academic_changed_at TIMESTAMPTZ;

ALTER TABLE crm_outbox DROP CONSTRAINT crm_outbox_event_type_check;
ALTER TABLE crm_outbox ADD CONSTRAINT crm_outbox_event_type_check CHECK (event_type IN (
    'LmsAccountProvisioned', 'AdmissionLmsStatusChanged', 'BatchLinked', 'AdmissionAcademicsChanged', 'BatchUpserted'));

-- The CRM needs the latest academic state, not every intermediate step: an undelivered row for the same admission
-- (or batch) is superseded in place; delivered rows stay as history.
CREATE OR REPLACE FUNCTION queue_crm_state(p_event_type TEXT, p_key_field TEXT, p_payload JSONB) RETURNS void AS $$
BEGIN
    UPDATE crm_outbox SET payload = p_payload, created_at = CURRENT_TIMESTAMP
    WHERE status = 'Pending' AND event_type = p_event_type AND payload ->> p_key_field = p_payload ->> p_key_field;
    IF NOT FOUND THEN
        INSERT INTO crm_outbox (event_type, payload) VALUES (p_event_type, p_payload);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Recompute the academic state; queue AdmissionAcademicsChanged when it differs from what was last queued
CREATE OR REPLACE FUNCTION refresh_admission_academics(p_admission_id INT) RETURNS void AS $$
DECLARE
    v_new JSONB := admission_academic_state(p_admission_id);
    v_old JSONB;
BEGIN
    IF v_new IS NULL THEN
        RETURN;                                     -- no enrolment for the admission's course yet
    END IF;
    SELECT academic INTO v_old FROM admission_lms_state WHERE admission_id = p_admission_id;
    IF v_old IS NOT DISTINCT FROM v_new THEN
        RETURN;
    END IF;

    -- The state row is created by the LMS-status refresh, so its first status change is still queued
    IF NOT EXISTS (SELECT 1 FROM admission_lms_state WHERE admission_id = p_admission_id) THEN
        PERFORM refresh_admission_lms_state(p_admission_id);
    END IF;
    UPDATE admission_lms_state SET academic = v_new, academic_changed_at = CURRENT_TIMESTAMP
    WHERE admission_id = p_admission_id;

    PERFORM queue_crm_state('AdmissionAcademicsChanged', 'crm_admission_id', v_new);
END;
$$ LANGUAGE plpgsql;

-- Every enrolment change that the CRM shows: status, joining date, curriculum, branch
CREATE OR REPLACE FUNCTION enrolments_refresh_academics() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_admission_academics(NEW.admission_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolments_academics
    AFTER INSERT OR UPDATE OF status, joining_date, curriculum_version_id, service_branch_id, completed_at ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_refresh_academics();

CREATE OR REPLACE FUNCTION enrolment_tracks_refresh_academics() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_admission_academics((SELECT admission_id FROM enrolments WHERE enrolment_id = NEW.enrolment_id));
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enrolment_tracks_academics
    AFTER INSERT OR UPDATE OF curriculum_version_id ON enrolment_tracks
    FOR EACH ROW EXECUTE FUNCTION enrolment_tracks_refresh_academics();

CREATE OR REPLACE FUNCTION batch_allocations_refresh_academics() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_admission_academics((SELECT admission_id FROM enrolments WHERE enrolment_id = NEW.enrolment_id));
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_allocations_academics
    AFTER INSERT OR UPDATE ON batch_allocations
    FOR EACH ROW EXECUTE FUNCTION batch_allocations_refresh_academics();

-- ---------------------------------------------------------------------------
-- Batches, as the CRM stores them (its batches table becomes a mirror; lms_course_id = batch_code)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION batch_crm_state(p_batch_id INT) RETURNS JSONB AS $$
    SELECT jsonb_build_object(
        'lms_course_id', bt.batch_code,
        'crm_batch_id', bt.crm_batch_id,
        'course_code', c.course_code,
        'branch_code', b.branch_code,
        'delivery_mode', crm_delivery_mode(bt.mode),
        'status', crm_batch_status(bt.state),
        'capacity', bt.capacity,
        'start_date', bt.planned_start,
        'end_date', bt.planned_end,
        'curriculum_version_label', cv.version_label,
        'lead_trainer_email', (SELECT u.email FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                               WHERE t.batch_id = bt.batch_id AND t.role = 'Lead' AND t.to_date IS NULL LIMIT 1),
        'trainer_emails', COALESCE((SELECT jsonb_agg(u.email ORDER BY t.role, u.email)
                                    FROM batch_trainers t JOIN users u ON u.user_id = t.trainer_user_id
                                    WHERE t.batch_id = bt.batch_id AND t.to_date IS NULL), '[]'::jsonb))
    FROM batches bt
    JOIN courses c ON c.course_id = bt.course_id
    JOIN branches b ON b.branch_id = bt.branch_id
    LEFT JOIN curriculum_versions cv ON cv.curriculum_version_id = bt.curriculum_version_id
    WHERE bt.batch_id = p_batch_id;
$$ LANGUAGE sql STABLE;

CREATE TABLE batch_crm_state (
    batch_id INT PRIMARY KEY REFERENCES batches(batch_id) ON DELETE CASCADE,
    payload JSONB NOT NULL,                          -- last batch state queued for the CRM
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION refresh_batch_crm_state(p_batch_id INT) RETURNS void AS $$
DECLARE
    v_new JSONB := batch_crm_state(p_batch_id);
BEGIN
    IF v_new IS NULL OR EXISTS (SELECT 1 FROM batch_crm_state WHERE batch_id = p_batch_id AND payload = v_new) THEN
        RETURN;
    END IF;
    INSERT INTO batch_crm_state (batch_id, payload) VALUES (p_batch_id, v_new)
    ON CONFLICT (batch_id) DO UPDATE SET payload = EXCLUDED.payload, changed_at = CURRENT_TIMESTAMP;
    PERFORM queue_crm_state('BatchUpserted', 'lms_course_id', v_new);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION batches_refresh_crm_state() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_batch_crm_state(NEW.batch_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batches_crm_state
    AFTER INSERT OR UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION batches_refresh_crm_state();

CREATE OR REPLACE FUNCTION batch_trainers_refresh_crm_state() RETURNS trigger AS $$
BEGIN
    PERFORM refresh_batch_crm_state(COALESCE(NEW.batch_id, OLD.batch_id));
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_batch_trainers_crm_state
    AFTER INSERT OR UPDATE OR DELETE ON batch_trainers
    FOR EACH ROW EXECUTE FUNCTION batch_trainers_refresh_crm_state();

-- Existing rows (a database built before 005): record their current state without queueing history
INSERT INTO batch_crm_state (batch_id, payload) SELECT batch_id, batch_crm_state(batch_id) FROM batches;
UPDATE admission_lms_state s SET academic = admission_academic_state(s.admission_id), academic_changed_at = CURRENT_TIMESTAMP
WHERE admission_academic_state(s.admission_id) IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Finance summary: the rest of the CRM's admission_balances / installment_dues (read-only in the LMS)
-- ---------------------------------------------------------------------------
ALTER TABLE finance_summaries
    ADD COLUMN pending_verification NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (pending_verification >= 0),  -- never counted as paid
    ADD COLUMN waived NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (waived >= 0),
    ADD COLUMN refunded NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (refunded >= 0),
    ADD COLUMN payment_completion VARCHAR(20) CHECK (payment_completion IN ('Unpaid', 'Part Paid', 'Paid')),
    ADD COLUMN invoice_numbers JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN installments JSONB NOT NULL DEFAULT '[]'::jsonb;  -- [{installment_no, due_date, amount, covered, balance, due_position}]

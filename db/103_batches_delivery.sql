-- 103: phase 6 of the gap fix plan — batches and delivery operations, Modules 15 and 16 (docs/GAP_FIX_PLAN.md, docs/GAPS.md)
-- Depends on: 004 / 010 / 098 (batches, allocations, sessions), 005 (CRM batch state), 020 (recordings), 040 / 099 / 102
--             (attendance views, exception queue), 100 (approval_status), 102 (academic mappings)
--   Batch lifecycle with Proposed, On Hold and Archived and a Branch Manager confirmation against the 7-point readiness
--   record (G015); type, pattern, display name and the creating branch (G062); split capacity and reviewed increases (G103);
--   component (track) batches and track allocations (G016); transfer requests with Branch Manager approval, and a
--   component placed at another branch (G017); material changes with each student's agreement (G018); merge / split
--   successions and completion / archive obligations (G069). Class sessions keep their original slot, record actual
--   delivery (Held / Partially Held), purpose and replacement links (G065, G066); delayed starts and disruptions (G019);
--   Meet identifiers and hosting branch (G070); hosts, backups, guests and link incidents (G071); cover requests (G101);
--   student slot preferences (G102); Meet participation evidence (G104); shared classes across batches (G067).
--   Session states keep their stored values: Scheduled is shown as Planned (Confirmed once confirmed), Live as In Progress
--   and Delivered as Held or Partially Held, so attendance and progress views read sessions as before.

-- ---------------------------------------------------------------------------
-- Batch lifecycle: Forming (Draft) -> Proposed -> Starting (Confirmed) -> Running (In Progress) <-> Full -> Completed;
-- On Hold from Proposed / Starting / Running / Full and back; Cancelled; Archived after Completed or Cancelled.
-- New enum values are only referenced as text inside this file (they cannot be used in the transaction that adds them).
-- ---------------------------------------------------------------------------
ALTER TYPE batch_state ADD VALUE IF NOT EXISTS 'Proposed' AFTER 'Forming';
ALTER TYPE batch_state ADD VALUE IF NOT EXISTS 'On Hold' AFTER 'Full';
ALTER TYPE batch_state ADD VALUE IF NOT EXISTS 'Archived';

ALTER TABLE batches
    ADD COLUMN display_name VARCHAR(200),                                  -- editable, separate from the permanent batch_code
    ADD COLUMN batch_type VARCHAR(20) NOT NULL DEFAULT 'Group'
        CHECK (batch_type IN ('Group', 'Individual', 'Corporate')),
    ADD COLUMN schedule_pattern VARCHAR(20) NOT NULL DEFAULT 'Regular'
        CHECK (schedule_pattern IN ('Regular', 'Weekend', 'Fast-track')),
    ADD COLUMN creating_branch_id INT REFERENCES branches(branch_id),     -- the branch in the batch code; branch_id is the service branch
    ADD COLUMN component_id INT REFERENCES course_components(component_id),  -- set: the batch teaches one track of a combo
    ADD COLUMN classroom_capacity INT CHECK (classroom_capacity IS NULL OR classroom_capacity >= 0),
    ADD COLUMN lab_capacity INT CHECK (lab_capacity IS NULL OR lab_capacity >= 0),
    ADD COLUMN online_capacity INT CHECK (online_capacity IS NULL OR online_capacity >= 0),
    ADD COLUMN recording_provision VARCHAR(20) CHECK (recording_provision IN ('Included', 'Not Included', 'Limited')),
    ADD COLUMN recording_terms TEXT,                                       -- covered sessions, exclusions, conditions (Limited)
    ADD COLUMN held_from_state batch_state,                                -- the state an On Hold batch returns to
    ADD COLUMN proposed_by INT REFERENCES users(user_id),
    ADD COLUMN proposed_at TIMESTAMPTZ,
    ADD COLUMN proposal_note TEXT,                                         -- the Academic Coordinator's review
    ADD COLUMN confirmed_by INT REFERENCES users(user_id),
    ADD COLUMN confirmed_at TIMESTAMPTZ,
    ADD COLUMN confirmation_checklist JSONB,                               -- the 7-point record as the Branch Manager confirmed it
    ADD COLUMN meet_series_link VARCHAR(500),                              -- the recurring batch-series Meet link (Module 16 §3)
    ADD COLUMN meet_space_id VARCHAR(200),
    ADD COLUMN calendar_series_id VARCHAR(200),
    ADD CONSTRAINT batches_recording_terms CHECK (
        recording_provision IS DISTINCT FROM 'Limited' OR length(btrim(COALESCE(recording_terms, ''))) > 0),
    ADD CONSTRAINT batches_confirmed CHECK ((confirmed_at IS NULL) = (confirmed_by IS NULL)),
    ADD CONSTRAINT batches_confirmer_independent CHECK (confirmed_by IS NULL OR proposed_by IS NULL OR confirmed_by <> proposed_by);

UPDATE batches SET creating_branch_id = branch_id;
ALTER TABLE batches ALTER COLUMN creating_branch_id SET NOT NULL;

CREATE INDEX batches_component_idx ON batches (component_id) WHERE component_id IS NOT NULL;

-- Code and creating branch are permanent; a component belongs to the batch's course; capacity floors at the seats taken
CREATE OR REPLACE FUNCTION batches_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.batch_code = COALESCE(NEW.batch_code, next_batch_code(NEW.branch_id));
        NEW.creating_branch_id = COALESCE(NEW.creating_branch_id, NEW.branch_id);
    ELSIF NEW.batch_code <> OLD.batch_code THEN
        RAISE EXCEPTION 'batch_code cannot change (the CRM stores it)';
    ELSIF NEW.creating_branch_id <> OLD.creating_branch_id THEN
        RAISE EXCEPTION 'The creating branch of a batch cannot change';
    END IF;

    IF NEW.component_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM course_components WHERE component_id = NEW.component_id AND parent_course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'The track is not a component of the batch''s course';
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

CREATE OR REPLACE FUNCTION check_batch_transition() RETURNS trigger AS $$
DECLARE
    v_from TEXT := OLD.state::TEXT;
    v_to TEXT := NEW.state::TEXT;
    v_held TEXT := COALESCE(OLD.held_from_state::TEXT, '');
    v_students INT;
    v_open_sessions INT;
BEGIN
    IF v_from = v_to THEN
        RETURN NEW;
    END IF;
    IF v_from = 'Archived' THEN
        RAISE EXCEPTION 'Batch % is Archived and cannot change state', OLD.batch_code;
    END IF;
    IF v_from IN ('Completed', 'Cancelled') AND v_to <> 'Archived' THEN
        RAISE EXCEPTION 'Batch % is % and cannot change state', OLD.batch_code, v_from;
    END IF;
    IF NOT ((v_from = 'Forming' AND v_to IN ('Proposed', 'Cancelled'))
         OR (v_from = 'Proposed' AND v_to IN ('Forming', 'Starting', 'On Hold', 'Cancelled'))
         OR (v_from = 'Starting' AND v_to IN ('Running', 'Full', 'On Hold', 'Cancelled'))
         OR (v_from IN ('Running', 'Full') AND v_to IN ('Running', 'Full', 'On Hold', 'Completed', 'Cancelled'))
         OR (v_from = 'On Hold' AND (v_to = 'Cancelled' OR v_to = v_held
                                     OR (v_held IN ('Running', 'Full') AND v_to IN ('Running', 'Full'))))
         OR (v_from IN ('Completed', 'Cancelled') AND v_to = 'Archived')) THEN
        RAISE EXCEPTION 'Batch % cannot move from % to %', OLD.batch_code, v_from, v_to;
    END IF;
    IF v_to = 'Starting' AND NEW.confirmed_at IS NULL THEN
        RAISE EXCEPTION 'Batch % needs the Branch Manager''s confirmation before it is Confirmed', NEW.batch_code;
    END IF;
    IF v_to IN ('Starting', 'Running', 'Full') AND NEW.readiness = 'Blocked' THEN
        RAISE EXCEPTION 'Batch % is Blocked (%) and cannot start until it is unblocked', NEW.batch_code, NEW.readiness_reason;
    END IF;
    IF v_to = 'Cancelled' THEN
        SELECT count(DISTINCT enrolment_id) INTO v_students FROM batch_allocations WHERE batch_id = NEW.batch_id AND status = 'Active';
        IF v_students > 0 THEN
            RAISE EXCEPTION 'Batch % still has % allocated student(s); transfer them before cancelling', NEW.batch_code, v_students;
        END IF;
    END IF;
    IF v_to IN ('Completed', 'Archived') THEN
        SELECT count(*) INTO v_open_sessions FROM class_sessions
        WHERE batch_id = NEW.batch_id AND state IN ('Scheduled', 'Live', 'Rescheduled');
        IF v_open_sessions > 0 THEN
            RAISE EXCEPTION 'Batch % still has % open class session(s); deliver or cancel them before completing the batch', NEW.batch_code, v_open_sessions;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- CRM batch_status: Planned, Proposed, Open, In Progress, On Hold, Completed, Cancelled, Archived (round 4 request A5)
CREATE OR REPLACE FUNCTION crm_batch_status(p_state batch_state) RETURNS TEXT AS $$
    SELECT CASE p_state::TEXT
        WHEN 'Forming' THEN 'Planned'
        WHEN 'Starting' THEN 'Open'
        WHEN 'Running' THEN 'In Progress'
        WHEN 'Full' THEN 'In Progress'
        ELSE p_state::TEXT                            -- Proposed, On Hold, Completed, Cancelled, Archived
    END;
$$ LANGUAGE sql IMMUTABLE;

-- ---------------------------------------------------------------------------
-- Capacity increases: resource validation and academic review, then the Branch Manager's independent approval (G103)
-- ---------------------------------------------------------------------------
CREATE TABLE batch_capacity_requests (
    request_id SERIAL PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    from_capacity INT NOT NULL,
    to_capacity INT NOT NULL,
    classroom_capacity INT CHECK (classroom_capacity IS NULL OR classroom_capacity >= 0),
    lab_capacity INT CHECK (lab_capacity IS NULL OR lab_capacity >= 0),
    online_capacity INT CHECK (online_capacity IS NULL OR online_capacity >= 0),
    resource_validation TEXT NOT NULL CHECK (length(btrim(resource_validation)) > 0),
    academic_review TEXT NOT NULL CHECK (length(btrim(academic_review)) > 0),
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    CONSTRAINT batch_capacity_requests_increase CHECK (to_capacity > from_capacity),
    CONSTRAINT batch_capacity_requests_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT batch_capacity_requests_independent CHECK (decided_by IS NULL OR decided_by <> requested_by)
);

CREATE UNIQUE INDEX batch_capacity_requests_one_open ON batch_capacity_requests (batch_id) WHERE status = 'Pending';

-- ---------------------------------------------------------------------------
-- Transfers between batches (G017): requested, then approved by the Branch Manager (or Super Admin) independently of the
-- requester. A component placed in another branch's batch also needs the destination's confirmation that it can deliver.
-- ---------------------------------------------------------------------------
CREATE TABLE batch_transfer_requests (
    request_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    enrolment_track_id INT REFERENCES enrolment_tracks(enrolment_track_id),  -- NULL = the whole enrolment
    from_batch_id INT REFERENCES batches(batch_id),                          -- NULL = a track's first placement elsewhere
    to_batch_id INT NOT NULL REFERENCES batches(batch_id),
    interbranch BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    acknowledged_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    destination_confirmed_by INT REFERENCES users(user_id),
    destination_confirmed_at TIMESTAMPTZ,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    applied_allocation_id INT REFERENCES batch_allocations(allocation_id),
    CONSTRAINT batch_transfer_requests_interbranch_track CHECK (NOT interbranch OR enrolment_track_id IS NOT NULL),
    CONSTRAINT batch_transfer_requests_from CHECK (from_batch_id IS NOT NULL OR interbranch),
    CONSTRAINT batch_transfer_requests_batches CHECK (from_batch_id IS DISTINCT FROM to_batch_id),
    CONSTRAINT batch_transfer_requests_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT batch_transfer_requests_independent CHECK (decided_by IS NULL OR decided_by <> requested_by),
    CONSTRAINT batch_transfer_requests_destination CHECK ((destination_confirmed_at IS NULL) = (destination_confirmed_by IS NULL))
);

CREATE UNIQUE INDEX batch_transfer_requests_one_open
    ON batch_transfer_requests (enrolment_id, COALESCE(enrolment_track_id, 0)) WHERE status = 'Pending';
CREATE INDEX batch_transfer_requests_status_idx ON batch_transfer_requests (status, requested_at);

-- An allocation: the batch teaches the enrolment's course (or the allocated track), at its service branch unless an
-- approved interbranch placement names this track and batch, while the batch is open, with a seat free
CREATE OR REPLACE FUNCTION check_batch_allocation() RETURNS trigger AS $$
DECLARE
    v_batch batches%ROWTYPE;
    v_enrolment enrolments%ROWTYPE;
    v_track enrolment_tracks%ROWTYPE;
    v_component course_components%ROWTYPE;
    v_taken INT;
BEGIN
    IF NEW.status <> 'Active' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO v_batch FROM batches WHERE batch_id = NEW.batch_id FOR UPDATE;  -- serialise seat counting
    SELECT * INTO v_enrolment FROM enrolments WHERE enrolment_id = NEW.enrolment_id;

    IF NEW.enrolment_track_id IS NULL THEN
        IF v_batch.component_id IS NOT NULL THEN
            RAISE EXCEPTION 'Batch % teaches one track; allocate the track, not the whole enrolment', v_batch.batch_code;
        END IF;
        IF v_batch.course_id <> v_enrolment.course_id THEN
            RAISE EXCEPTION 'Batch % is for a different course than this enrolment', v_batch.batch_code;
        END IF;
    ELSE
        SELECT * INTO v_track FROM enrolment_tracks WHERE enrolment_track_id = NEW.enrolment_track_id AND enrolment_id = NEW.enrolment_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Track does not belong to this enrolment';
        END IF;
        SELECT * INTO v_component FROM course_components WHERE component_id = v_track.component_id;
        IF NOT ((v_batch.course_id = v_enrolment.course_id AND (v_batch.component_id IS NULL OR v_batch.component_id = v_track.component_id))
             OR (v_batch.component_id IS NULL AND v_batch.course_id = v_component.component_course_id)) THEN
            RAISE EXCEPTION 'Batch % does not teach track %', v_batch.batch_code, v_component.track_code;
        END IF;
    END IF;

    IF v_batch.branch_id <> v_enrolment.service_branch_id AND NOT (NEW.enrolment_track_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM batch_transfer_requests r
            WHERE r.enrolment_id = NEW.enrolment_id AND r.enrolment_track_id = NEW.enrolment_track_id AND r.to_batch_id = NEW.batch_id
              AND r.interbranch AND r.status = 'Approved' AND r.destination_confirmed_at IS NOT NULL)) THEN
        RAISE EXCEPTION 'Batch % is at a different branch than the enrolment''s service branch', v_batch.batch_code;
    END IF;
    IF v_batch.state::TEXT IN ('Completed', 'Cancelled', 'Archived', 'On Hold') THEN
        RAISE EXCEPTION 'Batch % is % and cannot take new students', v_batch.batch_code, v_batch.state;
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

-- ---------------------------------------------------------------------------
-- Material changes (G018): the old and proposed plan, approved independently, then applied only once every affected
-- student agreed or declined with an agreed alternative. A notice being read is not agreement.
-- ---------------------------------------------------------------------------
CREATE TABLE material_changes (
    change_id SERIAL PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    kind VARCHAR(30) NOT NULL CHECK (kind IN ('Start date', 'Delivery mode', 'Teaching days / times', 'Instructional hours',
                                              'End date extension', 'Batch move')),
    current_plan TEXT NOT NULL CHECK (length(btrim(current_plan)) > 0),
    proposed_plan TEXT NOT NULL CHECK (length(btrim(proposed_plan)) > 0),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    changes JSONB NOT NULL DEFAULT '{}'::jsonb,       -- batch fields applied when it takes effect, or {target_batch_id} for a move
    alternative TEXT,                                 -- the replacement offered to a student who cannot accept
    status VARCHAR(20) NOT NULL DEFAULT 'Pending Approval'
        CHECK (status IN ('Pending Approval', 'Awaiting Agreement', 'Applied', 'Rejected', 'Withdrawn')),
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    applied_by INT REFERENCES users(user_id),
    applied_at TIMESTAMPTZ,
    CONSTRAINT material_changes_decided CHECK (
        (status = 'Pending Approval' AND decided_at IS NULL) OR status = 'Withdrawn'
        OR (status NOT IN ('Pending Approval', 'Withdrawn') AND decided_at IS NOT NULL AND decided_by IS NOT NULL)),
    CONSTRAINT material_changes_independent CHECK (decided_by IS NULL OR decided_by <> requested_by),
    CONSTRAINT material_changes_applied CHECK ((status = 'Applied') = (applied_at IS NOT NULL))
);

CREATE INDEX material_changes_batch_idx ON material_changes (batch_id, status);

CREATE TABLE material_change_responses (
    response_id SERIAL PRIMARY KEY,
    change_id INT NOT NULL REFERENCES material_changes(change_id) ON DELETE CASCADE,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    response VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (response IN ('Pending', 'Agreed', 'Declined')),
    note TEXT,
    alternative_arranged TEXT,                        -- what was agreed instead with a student who declined
    recorded_via VARCHAR(20) CHECK (recorded_via IN ('Student', 'Staff')),
    recorded_by INT REFERENCES users(user_id),
    responded_at TIMESTAMPTZ,
    UNIQUE (change_id, enrolment_id),
    CONSTRAINT material_change_responses_answered CHECK ((response = 'Pending') = (responded_at IS NULL)),
    CONSTRAINT material_change_responses_staff_evidence CHECK (
        recorded_via IS DISTINCT FROM 'Staff' OR length(btrim(COALESCE(note, ''))) > 0)
);

-- ---------------------------------------------------------------------------
-- Merge and split (G069): a successor link with effective date, reason, the coordinator's review and the Branch
-- Manager's independent approval. Past classes, attendance and payments stay on the original batch.
-- ---------------------------------------------------------------------------
CREATE TABLE batch_successions (
    succession_id SERIAL PRIMARY KEY,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('Merge', 'Split')),
    from_batch_id INT NOT NULL REFERENCES batches(batch_id),
    to_batch_id INT NOT NULL REFERENCES batches(batch_id),
    enrolment_ids INT[] NOT NULL DEFAULT '{}',        -- a split: who moves (a merge moves everyone)
    effective_from DATE NOT NULL,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    academic_review TEXT NOT NULL CHECK (length(btrim(academic_review)) > 0),
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    moved_count INT,
    CONSTRAINT batch_successions_batches CHECK (from_batch_id <> to_batch_id),
    CONSTRAINT batch_successions_split_names_students CHECK (kind <> 'Split' OR cardinality(enrolment_ids) > 0),
    CONSTRAINT batch_successions_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT batch_successions_independent CHECK (decided_by IS NULL OR decided_by <> requested_by)
);

CREATE INDEX batch_successions_batches_idx ON batch_successions (from_batch_id, to_batch_id);

-- Remaining obligations at batch completion (G069): a paused, deferred or not-yet-started student has a named owner,
-- a plan and a destination
CREATE TABLE batch_handovers (
    handover_id SERIAL PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    owner_user_id INT NOT NULL REFERENCES users(user_id),
    plan TEXT NOT NULL CHECK (length(btrim(plan)) > 0),
    destination TEXT NOT NULL CHECK (length(btrim(destination)) > 0),
    destination_batch_id INT REFERENCES batches(batch_id),
    recorded_by INT NOT NULL REFERENCES users(user_id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (batch_id, enrolment_id)
);

-- ---------------------------------------------------------------------------
-- Class sessions: original slot, confirmation, actual delivery, purpose and replacement links, Meet identifiers
-- ---------------------------------------------------------------------------
ALTER TABLE class_sessions
    ADD COLUMN original_starts_at TIMESTAMPTZ,
    ADD COLUMN original_ends_at TIMESTAMPTZ,
    ADD COLUMN confirmed_at TIMESTAMPTZ,                                   -- shown as Confirmed; a reschedule clears it
    ADD COLUMN confirmed_by INT REFERENCES users(user_id),
    ADD COLUMN live_at TIMESTAMPTZ,                                        -- when the trainer started the class
    ADD COLUMN delivery_outcome VARCHAR(20) CHECK (delivery_outcome IN ('Held', 'Partially Held')),
    ADD COLUMN actual_start TIMESTAMPTZ,
    ADD COLUMN actual_end TIMESTAMPTZ,
    ADD COLUMN break_minutes INT NOT NULL DEFAULT 0 CHECK (break_minutes >= 0),
    ADD COLUMN delivered_minutes INT CHECK (delivered_minutes IS NULL OR delivered_minutes >= 0),
    ADD COLUMN unfulfilled_note TEXT,                                      -- what was not delivered (Partially Held)
    ADD COLUMN log_overdue_at TIMESTAMPTZ,                                 -- set by class-log-check when no log by the deadline
    ADD COLUMN delay_notice_at TIMESTAMPTZ,                                -- students told the class is running late
    ADD COLUMN purpose VARCHAR(20) NOT NULL DEFAULT 'Regular' CHECK (purpose IN ('Regular', 'Replacement', 'Remedial', 'Extra')),
    ADD COLUMN replaces_session_id INT REFERENCES class_sessions(session_id),
    ADD COLUMN purpose_reference TEXT,                                     -- evidence and recovery plan / the approved addition
    ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'Not Required'
        CHECK (approval_status IN ('Not Required', 'Pending', 'Approved', 'Rejected')),
    ADD COLUMN proposed_by INT REFERENCES users(user_id),
    ADD COLUMN approved_by INT REFERENCES users(user_id),
    ADD COLUMN approved_at TIMESTAMPTZ,
    ADD COLUMN owner_user_id INT REFERENCES users(user_id),                -- who sees the replacement / remedial work through
    ADD COLUMN due_on DATE,
    ADD COLUMN replacement_waiver TEXT,                                    -- a cancelled class that needs no replacement, and why
    ADD COLUMN room_override_reason TEXT,                                  -- the Branch Manager's reason for using a booked room
    ADD COLUMN hosting_branch_id INT REFERENCES branches(branch_id),
    ADD COLUMN meet_space_id VARCHAR(200),
    ADD COLUMN calendar_event_id VARCHAR(200),
    ADD COLUMN calendar_series_id VARCHAR(200),
    ADD COLUMN conference_record_id VARCHAR(200);

UPDATE class_sessions SET delivery_outcome = 'Held' WHERE state = 'Delivered';
UPDATE class_sessions cs SET
    original_starts_at = COALESCE((SELECT sc.old_starts_at FROM session_changes sc WHERE sc.session_id = cs.session_id
                                   AND sc.change_type = 'Rescheduled' ORDER BY sc.change_id LIMIT 1), cs.starts_at),
    original_ends_at = COALESCE((SELECT sc.old_ends_at FROM session_changes sc WHERE sc.session_id = cs.session_id
                                 AND sc.change_type = 'Rescheduled' ORDER BY sc.change_id LIMIT 1), cs.ends_at),
    hosting_branch_id = (SELECT b.branch_id FROM batches b WHERE b.batch_id = cs.batch_id);

ALTER TABLE class_sessions
    ALTER COLUMN original_starts_at SET NOT NULL,
    ALTER COLUMN original_ends_at SET NOT NULL,
    ALTER COLUMN hosting_branch_id SET NOT NULL,
    ADD CONSTRAINT class_sessions_outcome CHECK ((state = 'Delivered') = (delivery_outcome IS NOT NULL)),
    ADD CONSTRAINT class_sessions_partial_note CHECK (
        delivery_outcome IS DISTINCT FROM 'Partially Held' OR length(btrim(COALESCE(unfulfilled_note, ''))) > 0),
    ADD CONSTRAINT class_sessions_actual_times CHECK (actual_end IS NULL OR actual_start IS NULL OR actual_end > actual_start),
    ADD CONSTRAINT class_sessions_replacement_link CHECK (purpose <> 'Replacement' OR replaces_session_id IS NOT NULL),
    ADD CONSTRAINT class_sessions_purpose_reference CHECK (
        purpose IN ('Regular', 'Replacement') OR length(btrim(COALESCE(purpose_reference, ''))) > 0),
    ADD CONSTRAINT class_sessions_not_self_replacement CHECK (replaces_session_id IS DISTINCT FROM session_id),
    ADD CONSTRAINT class_sessions_confirmed CHECK ((confirmed_at IS NULL) = (confirmed_by IS NULL));

CREATE INDEX class_sessions_replaces_idx ON class_sessions (replaces_session_id) WHERE replaces_session_id IS NOT NULL;

-- A class marked Delivered without an outcome (imports, older callers) was Held
CREATE OR REPLACE FUNCTION class_sessions_default_outcome() RETURNS trigger AS $$
BEGIN
    IF NEW.state = 'Delivered' AND NEW.delivery_outcome IS NULL THEN
        NEW.delivery_outcome = 'Held';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_class_sessions_default_outcome
    BEFORE INSERT OR UPDATE OF state, delivery_outcome ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION class_sessions_default_outcome();

-- A reschedule or cancellation inside 24 hours is an emergency: why advance notice was impossible and the next action
-- (Module 15 §14). Older rows have neither, so the rule is enforced by the service.
ALTER TABLE session_changes
    ADD COLUMN emergency_reason TEXT,
    ADD COLUMN next_action TEXT;

-- ---------------------------------------------------------------------------
-- Cover (G101): the Branch Manager approves a substitute or assistant, the Academic Coordinator verifies competence,
-- scope and handover. A substitute no longer has to be assigned to the batch: an applied cover request is enough.
-- ---------------------------------------------------------------------------
CREATE TABLE session_cover_requests (
    request_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    cover_role VARCHAR(20) NOT NULL CHECK (cover_role IN ('Substitute', 'Assistant')),
    planned_trainer_user_id INT NOT NULL REFERENCES users(user_id),
    cover_user_id INT NOT NULL REFERENCES users(user_id),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    scope TEXT NOT NULL CHECK (length(btrim(scope)) > 0),                 -- what the cover may teach / do
    handover TEXT NOT NULL CHECK (length(btrim(handover)) > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Applied', 'Rejected')),
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_by INT REFERENCES users(user_id),                             -- Branch Manager / Super Admin
    approved_at TIMESTAMPTZ,
    verified_by INT REFERENCES users(user_id),                             -- Academic Coordinator / Super Admin
    verified_at TIMESTAMPTZ,
    verification_note TEXT,
    decision_note TEXT,
    applied_at TIMESTAMPTZ,
    CONSTRAINT session_cover_requests_independent CHECK (approved_by IS NULL OR approved_by <> requested_by),
    CONSTRAINT session_cover_requests_not_planned CHECK (cover_user_id <> planned_trainer_user_id),
    CONSTRAINT session_cover_requests_applied CHECK (status <> 'Applied' OR (approved_at IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT session_cover_requests_rejected_note CHECK (status <> 'Rejected' OR length(btrim(COALESCE(decision_note, ''))) > 0)
);

CREATE UNIQUE INDEX session_cover_requests_one_open ON session_cover_requests (session_id, cover_role) WHERE status IN ('Pending', 'Approved');

-- The session trainer is a batch trainer, or the substitute of an applied cover request
CREATE OR REPLACE FUNCTION class_sessions_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.session_code IS NULL THEN
            LOOP
                NEW.session_code = 'SES-' || lpad(next_counter_value('SES')::TEXT, 6, '0');
                EXIT WHEN NOT EXISTS (SELECT 1 FROM class_sessions WHERE session_code = NEW.session_code);
            END LOOP;
        END IF;
        NEW.original_starts_at = COALESCE(NEW.original_starts_at, NEW.starts_at);
        NEW.original_ends_at = COALESCE(NEW.original_ends_at, NEW.ends_at);
        NEW.hosting_branch_id = COALESCE(NEW.hosting_branch_id, (SELECT branch_id FROM batches WHERE batch_id = NEW.batch_id));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM batch_trainers WHERE batch_id = NEW.batch_id AND trainer_user_id = NEW.trainer_user_id)
       AND NOT (TG_OP = 'UPDATE' AND EXISTS (
            SELECT 1 FROM session_cover_requests r
            WHERE r.session_id = NEW.session_id AND r.cover_user_id = NEW.trainer_user_id AND r.cover_role = 'Substitute'
              AND r.status = 'Applied')) THEN
        RAISE EXCEPTION 'The session trainer must be assigned to the batch or be its approved substitute';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER trg_class_sessions_write ON class_sessions;
CREATE TRIGGER trg_class_sessions_write
    BEFORE INSERT OR UPDATE OF batch_id, trainer_user_id ON class_sessions
    FOR EACH ROW EXECUTE FUNCTION class_sessions_before_write();

-- ---------------------------------------------------------------------------
-- Hosts, backups, assistants and guests of a class (G071)
-- ---------------------------------------------------------------------------
CREATE TABLE session_people (
    session_person_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('Host', 'Backup', 'Assistant', 'Guest')),
    user_id INT REFERENCES users(user_id),
    guest_name VARCHAR(150),
    guest_email VARCHAR(255),
    purpose TEXT,
    student_agreement TEXT,                         -- how the students agreed to a guest, where applicable
    status approval_status NOT NULL DEFAULT 'Approved',
    added_by INT NOT NULL REFERENCES users(user_id),
    added_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    removed_at TIMESTAMPTZ,
    CONSTRAINT session_people_identity CHECK ((role = 'Guest') = (user_id IS NULL)),
    CONSTRAINT session_people_guest_name CHECK (role <> 'Guest' OR length(btrim(COALESCE(guest_name, ''))) > 0),
    CONSTRAINT session_people_guest_purpose CHECK (role <> 'Guest' OR length(btrim(COALESCE(purpose, ''))) > 0)
);

CREATE UNIQUE INDEX session_people_one_host ON session_people (session_id) WHERE role = 'Host' AND removed_at IS NULL;
CREATE UNIQUE INDEX session_people_one_backup ON session_people (session_id) WHERE role = 'Backup' AND removed_at IS NULL;
CREATE UNIQUE INDEX session_people_once ON session_people (session_id, user_id) WHERE user_id IS NOT NULL AND removed_at IS NULL;

-- Link incidents (compromised link, unexpected joiners): kept with the session's history
CREATE TABLE meet_incidents (
    incident_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    kind VARCHAR(30) NOT NULL CHECK (kind IN ('Compromised link', 'Unexpected joiner', 'Host access failure', 'Other')),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0),
    actions_taken TEXT NOT NULL CHECK (length(btrim(actions_taken)) > 0),
    old_meet_link VARCHAR(500),
    link_replaced BOOLEAN NOT NULL DEFAULT FALSE,
    reported_by INT NOT NULL REFERENCES users(user_id),
    reported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    participants_notified_at TIMESTAMPTZ,
    manager_alerted_at TIMESTAMPTZ
);

CREATE INDEX meet_incidents_session_idx ON meet_incidents (session_id, reported_at);

-- Meet join / leave evidence (G104): supports review, never sets attendance. Unmatched identities wait for a person.
CREATE TABLE meet_participation (
    participation_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    participant_name VARCHAR(200),
    participant_email VARCHAR(255),
    joined_at TIMESTAMPTZ NOT NULL,
    left_at TIMESTAMPTZ,
    source VARCHAR(20) NOT NULL DEFAULT 'Manual' CHECK (source IN ('Meet API', 'Manual')),
    match_status VARCHAR(20) NOT NULL DEFAULT 'Unmatched' CHECK (match_status IN ('Matched', 'Unmatched', 'Dismissed')),
    matched_user_id INT REFERENCES users(user_id),
    matched_enrolment_id INT REFERENCES enrolments(enrolment_id),
    reviewed_by INT REFERENCES users(user_id),
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    recorded_by INT REFERENCES users(user_id),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT meet_participation_identity CHECK (participant_name IS NOT NULL OR participant_email IS NOT NULL),
    CONSTRAINT meet_participation_times CHECK (left_at IS NULL OR left_at >= joined_at),
    CONSTRAINT meet_participation_matched CHECK (match_status <> 'Matched' OR matched_user_id IS NOT NULL)
);

CREATE INDEX meet_participation_session_idx ON meet_participation (session_id, joined_at);

-- ---------------------------------------------------------------------------
-- Delayed starts and disruptions (G019). The session-delay-check job tells students at 5 minutes and records a
-- disruption at 15; the coordinator or Branch Manager records the recovery plan and the undelivered minutes.
-- ---------------------------------------------------------------------------
CREATE TABLE session_disruptions (
    disruption_id SERIAL PRIMARY KEY,
    session_id INT NOT NULL REFERENCES class_sessions(session_id),
    kind VARCHAR(30) NOT NULL CHECK (kind IN ('Delayed start', 'Failed start', 'Connection failure', 'Compromised link', 'Other')),
    cause VARCHAR(20) NOT NULL DEFAULT 'Unknown' CHECK (cause IN ('Institute', 'Provider', 'Trainer', 'Unknown')),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delay_minutes INT CHECK (delay_minutes IS NULL OR delay_minutes >= 0),
    detail TEXT,
    undelivered_minutes INT CHECK (undelivered_minutes IS NULL OR undelivered_minutes >= 0),
    recovery_plan TEXT,
    replacement_session_id INT REFERENCES class_sessions(session_id),
    owner_user_id INT REFERENCES users(user_id),
    status VARCHAR(20) NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Resolved')),
    raised_by INT REFERENCES users(user_id),                               -- NULL = the session-delay-check job
    resolved_by INT REFERENCES users(user_id),
    resolved_at TIMESTAMPTZ,
    CONSTRAINT session_disruptions_resolved CHECK ((status = 'Resolved') = (resolved_at IS NOT NULL)),
    CONSTRAINT session_disruptions_resolution_plan CHECK (
        status <> 'Resolved' OR (length(btrim(COALESCE(recovery_plan, ''))) > 0 AND undelivered_minutes IS NOT NULL))
);

CREATE UNIQUE INDEX session_disruptions_one_delay ON session_disruptions (session_id) WHERE kind = 'Delayed start';
CREATE INDEX session_disruptions_status_idx ON session_disruptions (status, detected_at);

-- ---------------------------------------------------------------------------
-- Shared classes (G067): one class taught to several batches. The coordinator verifies the coverage for each joined
-- batch (and may name that batch's equivalent topic). One actual class, one attendance row per person.
-- ---------------------------------------------------------------------------
CREATE TABLE session_rosters (
    session_id INT NOT NULL REFERENCES class_sessions(session_id) ON DELETE CASCADE,
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    topic_id INT REFERENCES curriculum_topics(topic_id),     -- the joined batch's own topic this class covers
    coverage_note TEXT NOT NULL CHECK (length(btrim(coverage_note)) > 0),
    verified_by INT NOT NULL REFERENCES users(user_id),
    verified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, batch_id)
);

CREATE INDEX session_rosters_batch_idx ON session_rosters (batch_id);

-- Attendance for a shared class: any batch the class serves
CREATE OR REPLACE FUNCTION check_attendance_record() RETURNS trigger AS $$
DECLARE
    v_state session_state;
BEGIN
    SELECT state INTO v_state FROM class_sessions WHERE session_id = NEW.session_id;
    IF v_state NOT IN ('Live', 'Delivered') THEN
        RAISE EXCEPTION 'Attendance can only be marked for a Live or Delivered session (this one is %)', v_state;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM batch_allocations a
                   WHERE a.enrolment_id = NEW.enrolment_id
                     AND a.batch_id IN (SELECT batch_id FROM class_sessions WHERE session_id = NEW.session_id
                                        UNION SELECT batch_id FROM session_rosters WHERE session_id = NEW.session_id)) THEN
        RAISE EXCEPTION 'This enrolment is not allocated to a batch of the session';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Every batch a class serves: its own batch (host) and the batches joined to it, each with the topic it counts as
CREATE VIEW session_batches AS
SELECT session_id, batch_id, topic_id, TRUE AS is_host FROM class_sessions
UNION ALL
SELECT r.session_id, r.batch_id, r.topic_id, FALSE FROM session_rosters r;

-- Attendance and delivery read classes through session_batches. The views are dropped in dependency order and
-- recreated with the same columns; one row per enrolment and class even when two of its batches share the class.
DROP VIEW enrolment_progress;
DROP VIEW enrolment_required_learning;
DROP VIEW enrolment_covered_topics;
DROP VIEW enrolment_attendance;
DROP VIEW enrolment_delivery;
DROP VIEW attendance_grid;

CREATE VIEW attendance_grid AS
SELECT DISTINCT ON (e.enrolment_id, cs.session_id)
       e.enrolment_id, cs.session_id, sb.batch_id, sb.topic_id, cs.starts_at, cs.ends_at,
       ar.attendance_id, ar.status AS attendance_status,
       rec.recovery_id, rec.recovery_code, rec.status AS recovery_status
FROM enrolments e
JOIN enrolment_batch_links l ON l.enrolment_id = e.enrolment_id
JOIN session_batches sb ON sb.batch_id = l.batch_id
JOIN class_sessions cs ON cs.session_id = sb.session_id AND cs.state = 'Delivered'
LEFT JOIN attendance_records ar ON ar.session_id = cs.session_id AND ar.enrolment_id = e.enrolment_id
LEFT JOIN attendance_recoveries rec ON rec.attendance_id = ar.attendance_id AND rec.status IN ('Requested', 'Approved', 'Completed')
WHERE (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date >= l.first_effective_from
  AND (l.is_current OR (cs.starts_at AT TIME ZONE 'Asia/Kolkata')::date <= l.last_effective_to)
ORDER BY e.enrolment_id, cs.session_id, sb.is_host DESC, rec.recovery_id DESC NULLS LAST;

CREATE VIEW enrolment_delivery AS
SELECT e.enrolment_id,
       count(DISTINCT cs.session_id) FILTER (WHERE cs.state = 'Delivered') AS delivered_sessions,
       count(DISTINCT cs.session_id) FILTER (WHERE cs.state IN ('Scheduled', 'Live', 'Delivered')) AS planned_sessions
FROM enrolments e
LEFT JOIN enrolment_batch_links l ON l.enrolment_id = e.enrolment_id
LEFT JOIN session_batches sb ON sb.batch_id = l.batch_id
LEFT JOIN class_sessions cs ON cs.session_id = sb.session_id
GROUP BY e.enrolment_id;

-- delivered_since_joining keeps its name for the API; it counts from the seat, not the first Present
CREATE VIEW enrolment_attendance AS
SELECT e.enrolment_id,
       count(g.session_id) AS delivered_since_joining,
       count(g.attendance_id) AS marked_sessions,
       count(g.session_id) - count(g.attendance_id) AS unmarked_sessions,
       count(*) FILTER (WHERE g.attendance_status = 'Present') AS present_count,
       count(*) FILTER (WHERE g.attendance_status = 'Late') AS late_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent') AS absent_count,
       count(*) FILTER (WHERE g.attendance_status = 'Excused') AS excused_count,
       count(*) FILTER (WHERE g.attendance_status = 'Absent' AND g.recovery_status = 'Completed') AS recovered_count
FROM enrolments e
LEFT JOIN attendance_grid g ON g.enrolment_id = e.enrolment_id
GROUP BY e.enrolment_id;

-- Credited topics count as covered required learning (never as attendance)
CREATE VIEW enrolment_covered_topics AS
SELECT DISTINCT enrolment_id, topic_id
FROM attendance_grid
WHERE topic_id IS NOT NULL
  AND (attendance_status IN ('Present', 'Late') OR recovery_status = 'Completed')
UNION
SELECT enrolment_id, topic_id FROM learning_credits;

CREATE VIEW enrolment_required_learning AS
SELECT e.enrolment_id,
       count(rt.topic_id) AS required_topics,
       count(ct.topic_id) AS covered_topics
FROM enrolments e
LEFT JOIN enrolment_required_topics rt ON rt.enrolment_id = e.enrolment_id
LEFT JOIN enrolment_covered_topics ct ON ct.enrolment_id = rt.enrolment_id AND ct.topic_id = rt.topic_id
GROUP BY e.enrolment_id;

CREATE VIEW enrolment_progress AS
SELECT e.enrolment_id, e.student_id, e.course_id, e.service_branch_id,
       d.delivered_sessions, d.planned_sessions,
       CASE WHEN d.planned_sessions > 0 THEN round(100.0 * d.delivered_sessions / d.planned_sessions, 1) END AS delivery_pct,
       a.delivered_since_joining, a.marked_sessions, a.unmarked_sessions,
       a.present_count, a.late_count, a.absent_count, a.excused_count, a.recovered_count,
       CASE WHEN a.delivered_since_joining = 0 THEN 'Not started'
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
-- Student slot preferences (G102): a request reserves no seat; Confirmed only once the student holds a seat there
-- ---------------------------------------------------------------------------
CREATE TABLE slot_preferences (
    preference_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    batch_id INT REFERENCES batches(batch_id),        -- a particular batch the student asked for
    preferred_days SMALLINT[],
    preferred_start TIME,
    preferred_end TIME,
    preferred_mode delivery_mode,
    note TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'Requested'
        CHECK (status IN ('Requested', 'Waitlisted', 'Confirmed', 'Not Possible', 'Withdrawn')),
    status_note TEXT,
    status_by INT REFERENCES users(user_id),
    status_at TIMESTAMPTZ,
    created_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT slot_preferences_days CHECK (
        preferred_days IS NULL OR (cardinality(preferred_days) BETWEEN 1 AND 7 AND preferred_days <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::SMALLINT[])),
    CONSTRAINT slot_preferences_times CHECK (
        (preferred_start IS NULL) = (preferred_end IS NULL) AND (preferred_end IS NULL OR preferred_end > preferred_start)),
    CONSTRAINT slot_preferences_something CHECK (batch_id IS NOT NULL OR preferred_days IS NOT NULL OR preferred_start IS NOT NULL),
    CONSTRAINT slot_preferences_confirmed_batch CHECK (status <> 'Confirmed' OR batch_id IS NOT NULL)
);

CREATE UNIQUE INDEX slot_preferences_one_open ON slot_preferences (enrolment_id) WHERE status IN ('Requested', 'Waitlisted');

-- ---------------------------------------------------------------------------
-- Job runs: when each background job last ran and last succeeded (the Meet operations view shows reconciliation time)
-- ---------------------------------------------------------------------------
CREATE TABLE job_runs (
    job_name VARCHAR(60) PRIMARY KEY,
    last_started_at TIMESTAMPTZ NOT NULL,
    last_finished_at TIMESTAMPTZ,
    last_ok_at TIMESTAMPTZ,
    last_result TEXT,
    last_error TEXT
);

-- ---------------------------------------------------------------------------
-- Exception queue: delivery disruptions, missing class logs and cancelled classes still owing a replacement
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW exception_queue AS
WITH items AS (
    -- Enrolments waiting for a curriculum version to be mapped (S1). Paid receipts and Admissions are preserved.
    SELECT 'CURRICULUM_MAPPING'::TEXT AS source, e.enrolment_id AS source_id, e.enrolment_code AS reference,
           'Curriculum / allocation'::TEXT AS queue, e.service_branch_id AS branch_id,
           'Curriculum Mapping Pending'::TEXT AS title,
           c.course_code || ' · ' || s.full_name AS detail,
           e.mapping_owner_user_id AS owner_user_id, 'Academic Coordinator'::TEXT AS owner_label,
           e.updated_at AS opened_at, 'Open'::TEXT AS state, '/academic/curriculum'::TEXT AS link
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Curriculum Mapping Pending'

    UNION ALL
    -- Enrolments with a curriculum but no batch seat yet (S1)
    SELECT 'ALLOCATION', e.enrolment_id, e.enrolment_code,
           'Curriculum / allocation', e.service_branch_id,
           'Awaiting batch allocation',
           c.course_code || ' · ' || s.full_name,
           NULL, 'Academic Coordinator',
           e.updated_at, 'Open', '/academic/batches'
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Allocation Pending'

    UNION ALL
    -- Complimentary access held back until the qualifying payment gate is met (provisioning not finished)
    SELECT 'PROVISIONING', e.enrolment_id, e.enrolment_code,
           'Provisioning', e.service_branch_id,
           'Provisioning Pending',
           c.course_code || ' · ' || s.full_name || COALESCE(' · ' || e.benefit_note, ''),
           NULL, 'Super Admin',
           e.updated_at, 'Pending Verification', '/admin/students'
    FROM enrolments e
    JOIN students s ON s.student_id = e.student_id
    JOIN courses c ON c.course_id = e.course_id
    WHERE e.status = 'Provisioning Pending'

    UNION ALL
    -- Recording promises that are not being kept (S2)
    SELECT 'RECORDING', r.exception_id, r.exception_code,
           'Meet / recording', r.branch_id,
           'Recording: ' || r.issue_type::TEXT,
           b.batch_code || ' · ' || r.issue,
           r.owner_user_id,
           CASE r.owner_role WHEN 'ACADEMIC_COORDINATOR' THEN 'Academic Coordinator'
                             WHEN 'BRANCH_MANAGER' THEN 'Branch Manager' ELSE 'Super Admin' END,
           r.opened_at, r.status::TEXT, '/academic/recording-exceptions'
    FROM recording_exceptions r
    JOIN class_sessions cs ON cs.session_id = r.session_id
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE r.status <> 'Resolved'

    UNION ALL
    -- CRM events that failed to apply (Phase 1 / S6). Company-wide: no branch.
    SELECT 'CRM_EVENT', ev.crm_event_id, ev.event_id,
           'CRM/LMS sync', NULL,
           ev.event_type || ' failed',
           COALESCE(ev.error, 'The event could not be applied'),
           NULL, 'Super Admin',
           COALESCE(ev.processed_at, ev.received_at), 'Failed', '/admin/crm-sync'
    FROM crm_events ev
    WHERE ev.status = 'Failed'

    UNION ALL
    -- Support requests past their SLA or escalated (S5); they always have a named owner
    SELECT 'SUPPORT', sr.support_request_id, sr.request_code,
           'Support', sr.branch_id,
           CASE WHEN sr.escalation_level IS NOT NULL THEN 'Escalated to ' || sr.escalation_level ELSE 'Support request overdue' END,
           sr.subject,
           sr.owner_user_id,
           CASE sr.owner_role WHEN 'TRAINER' THEN 'Trainer' WHEN 'ACADEMIC_COORDINATOR' THEN 'Academic Coordinator'
                              WHEN 'BRANCH_MANAGER' THEN 'Branch Manager' ELSE 'Super Admin' END,
           COALESCE(sr.escalated_at, sr.sla_due_at),
           CASE WHEN sr.escalation_level IS NOT NULL THEN 'Escalated' ELSE 'Overdue' END,
           '/academic/support'
    FROM support_requests sr
    WHERE sr.status IN ('Open', 'In Progress', 'Waiting on Student')
      AND (sr.escalation_level IS NOT NULL OR sr.sla_due_at < CURRENT_TIMESTAMP)

    UNION ALL
    -- Results not yet published, one row per batch (S3)
    SELECT 'RESULTS', b.batch_id, b.batch_code,
           'Assessments', b.branch_id,
           'Results awaiting publication review',
           count(*) || ' result(s) · ' || b.batch_code,
           NULL, 'Academic Coordinator',
           min(r.created_at), 'Awaiting Review', '/academic/assessments'
    FROM results r
    JOIN batches b ON b.batch_id = r.batch_id
    WHERE r.status IN ('Provisional', 'Moderated')
    GROUP BY b.batch_id, b.batch_code, b.branch_id

    UNION ALL
    -- Access requests after the second anniversary: only a Founder / CEO or Super Admin may grant them (S2)
    SELECT 'ACCESS_EXCEPTION', x.request_id, x.request_code,
           'Access / recovery', x.branch_id,
           'Recording access after the 2nd anniversary',
           s.full_name || ' · ' || x.scope::TEXT,
           NULL, 'Super Admin',
           x.requested_at, 'Awaiting Approval', '/branch/requests'
    FROM access_extension_requests x
    JOIN students s ON s.student_id = x.student_id
    WHERE x.status = 'Pending' AND x.needs_exception

    UNION ALL
    -- Integrations whose verification failed or whose configuration is wrong (Phase 1 / S6). Company-wide.
    SELECT 'INTEGRATION', i.integration_id, i.integration_code,
           'Integrations', NULL,
           i.integration_name || ' needs attention',
           COALESCE(i.notes, i.requirement),
           NULL, i.owner,
           COALESCE(i.last_checked_at, i.updated_at), 'Failed', '/admin/integrations'
    FROM integrations i
    WHERE i.verification_status = 'Failed' OR i.configuration_status = 'Misconfigured'

    UNION ALL
    -- Delayed starts and other class disruptions waiting for a recovery plan (Module 16 §7)
    SELECT 'DISRUPTION', d.disruption_id, cs.session_code,
           'Live classes', b.branch_id,
           d.kind || COALESCE(' (' || d.delay_minutes || ' min)', ''),
           b.batch_code || ' · ' || cs.title,
           d.owner_user_id, 'Academic Coordinator',
           d.detected_at, 'Open', '/academic/meet-operations'
    FROM session_disruptions d
    JOIN class_sessions cs ON cs.session_id = d.session_id
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE d.status = 'Open'

    UNION ALL
    -- Classes with no delivery log by the end of their working day (Module 15 §15)
    SELECT 'CLASS_LOG', cs.session_id, cs.session_code,
           'Live classes', b.branch_id,
           'Class log missing',
           b.batch_code || ' · ' || cs.title,
           NULL, 'Academic Coordinator',
           cs.log_overdue_at, 'Overdue', '/academic/schedule'
    FROM class_sessions cs
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE cs.log_overdue_at IS NOT NULL AND cs.state IN ('Scheduled', 'Rescheduled', 'Live')

    UNION ALL
    -- Cancelled classes still owing a replacement (Module 15 §16)
    SELECT 'REPLACEMENT', cs.session_id, cs.session_code,
           'Live classes', b.branch_id,
           'Replacement class owed',
           b.batch_code || ' · ' || cs.title,
           NULL, 'Academic Coordinator',
           cs.updated_at, 'Open', '/academic/schedule'
    FROM class_sessions cs
    JOIN batches b ON b.batch_id = cs.batch_id
    WHERE cs.state = 'Cancelled' AND cs.replacement_waiver IS NULL AND cs.purpose IN ('Regular', 'Remedial') AND cs.approval_status <> 'Rejected'
      AND NOT EXISTS (SELECT 1 FROM class_sessions r WHERE r.replaces_session_id = cs.session_id AND r.state <> 'Cancelled')
),
steps AS (
    SELECT source, source_id, count(*) AS step_count, max(logged_at) AS last_step_at,
           (array_agg(logged_by ORDER BY step_id DESC))[1] AS last_step_by
    FROM exception_recovery_steps
    GROUP BY source, source_id
)
SELECT i.source, i.source_id, i.reference, i.queue, i.branch_id, i.title, i.detail,
       -- A named owner is either the record's own owner or the last person who logged a recovery step on it
       COALESCE(i.owner_user_id, st.last_step_by) AS owner_user_id,
       u.full_name AS owner_name,
       i.owner_label, i.opened_at,
       CASE WHEN i.state = 'Open' AND st.step_count > 0 THEN 'Recovery In Progress' ELSE i.state END AS state,
       i.link,
       COALESCE(st.step_count, 0)::INT AS step_count, st.last_step_at
FROM items i
LEFT JOIN steps st ON st.source = i.source AND st.source_id = i.source_id
LEFT JOIN users u ON u.user_id = COALESCE(i.owner_user_id, st.last_step_by);

-- ---------------------------------------------------------------------------
-- Settings
-- ---------------------------------------------------------------------------
INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('session_delay_notice_minutes', '5', 'Minutes after a class should have started before its students are told it is running late (Module 16 §7)'),
    ('session_disruption_minutes', '15', 'Minutes of unresolved delay before a disruption is recorded and the coordinator and Branch Manager are alerted'),
    ('material_end_extension_days', '7', 'An end-date extension longer than this many days is a material change needing each student''s agreement'),
    ('class_log_lookback_days', '14', 'How far back the class-log-check job looks for classes still without a delivery log')
ON CONFLICT (setting_key) DO NOTHING;

-- Existing batches gained fields that the CRM state does not carry; states are unchanged, so nothing is re-queued

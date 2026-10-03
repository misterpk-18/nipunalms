-- 102: phase 5 of the gap fix plan — the curriculum model of Module 14 (docs/GAP_FIX_PLAN.md, docs/GAPS.md)
-- Depends on: 002 (curriculum), 003 (enrolments), 010 (draft-only content), 040 (progress views), 080 (exception queue),
--             099 (attendance views), 100 (approval_status)
--   Topics carry an outcome, a Required / Recommended / Optional class, effort, weight, evidence and dependencies (G013).
--   Versions record verified hours, a completion profile and the assessments they require. A combo's parent version pins its
--   track and booster versions; borrowing a standalone curriculum for a component needs a recorded equivalence review
--   (G058). Students move between versions through an approved academic mapping with credits (G014). Mapping Pending
--   enrolments get a named owner (G061); branch variations are recorded (G060); modules can be reused from a versioned
--   library (G059).

-- ---------------------------------------------------------------------------
-- Topics
-- ---------------------------------------------------------------------------
ALTER TABLE curriculum_topics
    ADD COLUMN topic_class VARCHAR(12),
    ADD COLUMN outcome TEXT,
    ADD COLUMN instructional_minutes INT CHECK (instructional_minutes >= 0),
    ADD COLUMN independent_minutes INT CHECK (independent_minutes >= 0),
    ADD COLUMN weight NUMERIC(6, 2) CHECK (weight >= 0),
    ADD COLUMN evidence TEXT,
    ADD COLUMN activities TEXT;

-- Published topics are frozen (010); the backfill only names the class each topic already had
ALTER TABLE curriculum_topics DISABLE TRIGGER trg_curriculum_topics_draft_only;
UPDATE curriculum_topics SET topic_class = CASE WHEN is_required THEN 'Required' ELSE 'Optional' END;
ALTER TABLE curriculum_topics ENABLE TRIGGER trg_curriculum_topics_draft_only;

ALTER TABLE curriculum_topics
    ADD CONSTRAINT curriculum_topics_class CHECK (topic_class IN ('Required', 'Recommended', 'Optional')),
    ADD CONSTRAINT curriculum_topics_class_required CHECK (is_required = (topic_class = 'Required'));

-- is_required (read by the progress views) follows topic_class; writers may set either
CREATE OR REPLACE FUNCTION curriculum_topics_sync_class() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.topic_class IS NULL THEN
            NEW.topic_class = CASE WHEN NEW.is_required THEN 'Required' ELSE 'Optional' END;
        END IF;
    ELSIF NEW.topic_class IS DISTINCT FROM OLD.topic_class THEN
        NULL;  -- the class decides
    ELSIF NEW.is_required IS DISTINCT FROM OLD.is_required THEN
        NEW.topic_class = CASE WHEN NEW.is_required THEN 'Required' ELSE 'Optional' END;
    END IF;
    NEW.is_required = (NEW.topic_class = 'Required');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curriculum_topics_sync_class
    BEFORE INSERT OR UPDATE ON curriculum_topics
    FOR EACH ROW EXECUTE FUNCTION curriculum_topics_sync_class();

ALTER TABLE curriculum_topics ALTER COLUMN topic_class SET NOT NULL;

-- Dependencies inside one version, only where academically necessary (Module 14 §4)
CREATE TABLE curriculum_topic_dependencies (
    topic_id INT NOT NULL REFERENCES curriculum_topics(topic_id) ON DELETE CASCADE,
    depends_on_topic_id INT NOT NULL REFERENCES curriculum_topics(topic_id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, depends_on_topic_id),
    CONSTRAINT topic_dependencies_not_self CHECK (topic_id <> depends_on_topic_id)
);

CREATE OR REPLACE FUNCTION topic_version(p_topic_id INT) RETURNS INT AS $$
    SELECT m.curriculum_version_id FROM curriculum_topics t JOIN curriculum_modules m ON m.module_id = t.module_id
    WHERE t.topic_id = p_topic_id;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION topic_dependencies_check() RETURNS trigger AS $$
BEGIN
    IF topic_version(NEW.topic_id) <> topic_version(NEW.depends_on_topic_id) THEN
        RAISE EXCEPTION 'A topic can only depend on a topic of the same curriculum version';
    END IF;
    IF (SELECT status FROM curriculum_versions WHERE curriculum_version_id = topic_version(NEW.topic_id)) <> 'Draft' THEN
        RAISE EXCEPTION 'Dependencies change only while the version is a Draft';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_topic_dependencies_check
    BEFORE INSERT OR UPDATE ON curriculum_topic_dependencies
    FOR EACH ROW EXECUTE FUNCTION topic_dependencies_check();

-- ---------------------------------------------------------------------------
-- Versions: verified hours and the completion profile (Module 14 §5, §6, §10)
-- ---------------------------------------------------------------------------
ALTER TABLE curriculum_versions
    ADD COLUMN hours_verified_by INT REFERENCES users(user_id),
    ADD COLUMN hours_verified_at TIMESTAMPTZ,
    ADD COLUMN completion_profile JSONB,          -- {attendance_minimum_pct, pass_mark_pct, recovery_rule, reassessment_rule}
    ADD CONSTRAINT curriculum_versions_hours_verified CHECK ((hours_verified_by IS NULL) = (hours_verified_at IS NULL));

-- The assessments a version requires: Module 19 / 20 work links to these instead of inventing required work
CREATE TABLE curriculum_assessment_requirements (
    requirement_id SERIAL PRIMARY KEY,
    curriculum_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id) ON DELETE CASCADE,
    module_id INT REFERENCES curriculum_modules(module_id) ON DELETE CASCADE,
    topic_id INT REFERENCES curriculum_topics(topic_id) ON DELETE CASCADE,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('Assignment', 'Test')),
    title VARCHAR(200) NOT NULL CHECK (length(btrim(title)) > 0),
    outcome TEXT NOT NULL CHECK (length(btrim(outcome)) > 0),
    weight NUMERIC(6, 2) NOT NULL CHECK (weight >= 0),
    pass_rule TEXT NOT NULL CHECK (length(btrim(pass_rule)) > 0),
    counts_for_completion BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX assessment_requirements_version_idx ON curriculum_assessment_requirements (curriculum_version_id);

CREATE OR REPLACE FUNCTION curriculum_child_is_draft() RETURNS trigger AS $$
DECLARE
    v_status curriculum_status;
BEGIN
    SELECT status INTO v_status FROM curriculum_versions
    WHERE curriculum_version_id = COALESCE(NEW.curriculum_version_id, OLD.curriculum_version_id);
    IF FOUND AND v_status <> 'Draft' THEN
        RAISE EXCEPTION 'The curriculum version is % and can no longer be edited; create a new draft version', v_status;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assessment_requirements_draft_only
    BEFORE UPDATE OR DELETE ON curriculum_assessment_requirements
    FOR EACH ROW EXECUTE FUNCTION curriculum_child_is_draft();

-- ---------------------------------------------------------------------------
-- Combos (Module 14 §2, §3): the parent version pins each track and booster version; a component may reuse a standalone
-- course's curriculum only after the Academic Coordinator records matching outcomes, scope, depth and assessment
-- ---------------------------------------------------------------------------
ALTER TABLE course_components
    ADD COLUMN equivalence_note TEXT,
    ADD COLUMN equivalence_reviewed_by INT REFERENCES users(user_id),
    ADD COLUMN equivalence_reviewed_at TIMESTAMPTZ,
    ADD CONSTRAINT course_components_equivalence CHECK (
        (equivalence_reviewed_at IS NULL) = (equivalence_reviewed_by IS NULL)
        AND (equivalence_reviewed_at IS NULL OR length(btrim(COALESCE(equivalence_note, ''))) > 0));

CREATE TABLE curriculum_version_components (
    curriculum_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id) ON DELETE CASCADE,
    component_id INT NOT NULL REFERENCES course_components(component_id),
    component_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    PRIMARY KEY (curriculum_version_id, component_id)
);

CREATE TRIGGER trg_version_components_draft_only
    BEFORE UPDATE OR DELETE ON curriculum_version_components
    FOR EACH ROW EXECUTE FUNCTION curriculum_child_is_draft();

-- ---------------------------------------------------------------------------
-- Individual academic mapping and credit (Module 14 §8): a student moves to another version only through a reviewed
-- comparison and migration plan approved by the receiving Academic Coordinator; credited outcomes keep their original
-- evidence and never become attendance or submissions. New equivalence rules need the Founder / CEO or Super Admin.
-- ---------------------------------------------------------------------------
CREATE TABLE equivalence_rules (
    rule_id SERIAL PRIMARY KEY,
    from_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    to_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0),
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    CONSTRAINT equivalence_rules_versions CHECK (from_version_id <> to_version_id),
    CONSTRAINT equivalence_rules_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT equivalence_rules_independent CHECK (decided_by IS NULL OR decided_by <> requested_by)
);

CREATE TABLE academic_mappings (
    mapping_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    enrolment_track_id INT REFERENCES enrolment_tracks(enrolment_track_id),
    from_version_id INT REFERENCES curriculum_versions(curriculum_version_id),
    to_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    rule_id INT REFERENCES equivalence_rules(rule_id),
    comparison TEXT NOT NULL CHECK (length(btrim(comparison)) > 0),       -- outcomes met, previous work, remaining obligations
    migration_plan TEXT NOT NULL CHECK (length(btrim(migration_plan)) > 0),
    trainer_evidence TEXT,
    student_acceptance TEXT,                                               -- how the student accepted the material change
    proposed_credits JSONB NOT NULL DEFAULT '[]'::jsonb,                   -- [{topic_id, original_evidence}] until approved
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    CONSTRAINT academic_mappings_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT academic_mappings_accepted CHECK (status <> 'Approved' OR length(btrim(COALESCE(student_acceptance, ''))) > 0)
);

CREATE UNIQUE INDEX academic_mappings_one_pending ON academic_mappings (enrolment_id) WHERE status = 'Pending';

CREATE TABLE learning_credits (
    credit_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    topic_id INT NOT NULL REFERENCES curriculum_topics(topic_id),          -- the credited topic (and its outcome) in the new version
    mapping_id INT NOT NULL REFERENCES academic_mappings(mapping_id),
    original_evidence TEXT NOT NULL CHECK (length(btrim(original_evidence)) > 0),
    rule_id INT REFERENCES equivalence_rules(rule_id),
    reviewed_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (enrolment_id, topic_id)
);

-- Credited topics count as covered required learning (never as attendance)
CREATE OR REPLACE VIEW enrolment_covered_topics AS
SELECT DISTINCT enrolment_id, topic_id
FROM attendance_grid
WHERE topic_id IS NOT NULL
  AND (attendance_status IN ('Present', 'Late') OR recovery_status = 'Completed')
UNION
SELECT enrolment_id, topic_id FROM learning_credits;

-- ---------------------------------------------------------------------------
-- Curriculum Mapping Pending: a named academic owner (Module 14 §8)
-- ---------------------------------------------------------------------------
ALTER TABLE enrolments ADD COLUMN mapping_owner_user_id INT REFERENCES users(user_id);

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
-- Branch and batch variations (Module 14 §7)
-- ---------------------------------------------------------------------------
CREATE TABLE curriculum_variations (
    variation_id SERIAL PRIMARY KEY,
    curriculum_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),
    batch_id INT REFERENCES batches(batch_id),                             -- NULL = every batch of the branch on this version
    topic_id INT REFERENCES curriculum_topics(topic_id),
    kind VARCHAR(30) NOT NULL CHECK (kind IN ('Local example', 'Equivalent exercise', 'Teaching language', 'Sequencing',
                                              'Required topic constraint')),
    description TEXT NOT NULL CHECK (length(btrim(description)) > 0),
    remedial_plan TEXT,                                                    -- required for a constraint on a required topic
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    CONSTRAINT curriculum_variations_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT curriculum_variations_constraint CHECK (kind <> 'Required topic constraint'
        OR (topic_id IS NOT NULL AND length(btrim(COALESCE(remedial_plan, ''))) > 0))
);

-- ---------------------------------------------------------------------------
-- Reusable academic material (Module 14 §9): a library module has stable identity and explicit versions. A draft
-- curriculum copies an approved library version and keeps the reference; editing a library module proposes a new version,
-- and versions already in curricula stay as they were.
-- ---------------------------------------------------------------------------
CREATE TABLE library_modules (
    library_module_id SERIAL PRIMARY KEY,
    module_code VARCHAR(30) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    created_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE library_module_versions (
    library_version_id SERIAL PRIMARY KEY,
    library_module_id INT NOT NULL REFERENCES library_modules(library_module_id),
    version_no INT NOT NULL CHECK (version_no >= 1),
    content JSONB NOT NULL,                       -- {title, topics: [{title, topic_class, outcome, instructional_minutes, ...}]}
    change_note TEXT,
    status approval_status NOT NULL DEFAULT 'Pending',
    proposed_by INT NOT NULL REFERENCES users(user_id),
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    UNIQUE (library_module_id, version_no),
    CONSTRAINT library_versions_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT library_versions_independent CHECK (decided_by IS NULL OR decided_by <> proposed_by)
);

ALTER TABLE curriculum_modules ADD COLUMN library_version_id INT REFERENCES library_module_versions(library_version_id);

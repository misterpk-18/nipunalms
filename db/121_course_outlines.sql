-- 121: Role separation R6 (backend): the curriculum becomes the course outline (docs/ROLE_SEPARATION.md, decisions 5, 10-14, 25)
-- Depends on: 002, 003, 004, 005, 010, 020, 030, 040, 080, 095-098, 102-106, 109, 112, 114, 115
--   There are no curriculum versions, drafts or approvals any more. Modules and topics hang off the course itself
--   (`course_modules.course_id`; `component_id` set = the outline of one combo track).
--
--   Which outline survives: per course (and per combo track) the Active version's modules and topics, or the latest version's
--   when none is Active. Those module and topic ROWS are kept and simply re-parented to the course, so every foreign key from
--   sessions, content, assignments, questions, tests, covered topics and class logs stays valid.
--   Modules of any other version: a topic that something references is mapped by title (module + topic, then topic alone) to
--   the surviving outline and the referencing rows are re-pointed; whatever is still referenced after that is kept as an
--   ARCHIVED module of the course (`is_archived`, hidden from the outline, nothing lost); the rest is deleted.
--   Batches and enrolments pinned to an older version simply follow the course now (their `curriculum_version_id` column goes).
--
--   Moved onto the course: verified hours and the completion profile (`courses.hours_verified_*`, `completion_profile`, from
--   the surviving whole-course version), required assessments (`course_assessment_requirements`), combo track pins
--   (`course_components.pinned_course_id`) and the reusable module library (library tables stay, `course_modules.library_version_id`).
--   Dropped: curriculum_versions, curriculum_events, curriculum_version_components, equivalence_rules, academic_mappings,
--   curriculum_variations, learning_credits (refuses to run if it holds rows), type curriculum_status, and every draft-only trigger.
--   The CRM-owned course fields (code, title, category, status, tracks) are untouched; courses are never dropped.
-- Gap fix phase 7 starts at db/122.

-- ---------------------------------------------------------------------------
-- 0. Safety: refuse to drop student credit data, snapshot the row counts
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM learning_credits) THEN
        RAISE EXCEPTION 'learning_credits holds rows: credited topics are student data, review them before dropping the equivalence model';
    END IF;
END $$;

CREATE TEMP TABLE r6_counts AS
SELECT t.name, t.n FROM (
    SELECT 'courses' AS name, count(*) AS n FROM courses
    UNION ALL SELECT 'course_components', count(*) FROM course_components
    UNION ALL SELECT 'enrolments', count(*) FROM enrolments
    UNION ALL SELECT 'enrolment_tracks', count(*) FROM enrolment_tracks
    UNION ALL SELECT 'batches', count(*) FROM batches
    UNION ALL SELECT 'class_sessions', count(*) FROM class_sessions
    UNION ALL SELECT 'class_session_topics', count(*) FROM class_session_topics
    UNION ALL SELECT 'session_batches', count(*) FROM session_batches
    UNION ALL SELECT 'session_rosters', count(*) FROM session_rosters
    UNION ALL SELECT 'content_items', count(*) FROM content_items
    UNION ALL SELECT 'assignments', count(*) FROM assignments
    UNION ALL SELECT 'questions', count(*) FROM questions
    UNION ALL SELECT 'tests', count(*) FROM tests
    UNION ALL SELECT 'modules', count(*) FROM curriculum_modules
    UNION ALL SELECT 'topics', count(*) FROM curriculum_topics
    UNION ALL SELECT 'referenced_topics', count(DISTINCT x.topic_id) FROM (
        SELECT topic_id FROM class_sessions UNION ALL SELECT topic_id FROM class_session_topics
        UNION ALL SELECT topic_id FROM session_rosters UNION ALL SELECT topic_id FROM content_items
        UNION ALL SELECT topic_id FROM assignments UNION ALL SELECT topic_id FROM questions
        UNION ALL SELECT topic_id FROM tests) x WHERE x.topic_id IS NOT NULL
    UNION ALL SELECT 'topic_progress_rows', count(*) FROM topic_progress
    UNION ALL SELECT 'required_topic_rows', count(*) FROM enrolment_required_topics
) t;

-- ---------------------------------------------------------------------------
-- 1. Rename the outline tables (views and foreign keys follow the rename)
-- ---------------------------------------------------------------------------
ALTER TABLE curriculum_modules RENAME TO course_modules;
ALTER TABLE curriculum_topics RENAME TO course_topics;
ALTER TABLE curriculum_topic_dependencies RENAME TO course_topic_dependencies;
ALTER TABLE curriculum_assessment_requirements RENAME TO course_assessment_requirements;
ALTER TABLE course_modules RENAME CONSTRAINT curriculum_modules_pkey TO course_modules_pkey;
ALTER TABLE course_topics RENAME CONSTRAINT curriculum_topics_pkey TO course_topics_pkey;
ALTER FUNCTION curriculum_topics_sync_class() RENAME TO course_topics_sync_class;
ALTER TRIGGER trg_curriculum_topics_sync_class ON course_topics RENAME TO trg_course_topics_sync_class;
ALTER INDEX assessment_requirements_version_idx RENAME TO assessment_requirements_course_idx;

-- Published content stopped being frozen: nothing is a "Draft only" snapshot any more
DROP TRIGGER trg_curriculum_modules_draft_only ON course_modules;
DROP TRIGGER trg_curriculum_topics_draft_only ON course_topics;
DROP TRIGGER trg_assessment_requirements_draft_only ON course_assessment_requirements;
DROP TRIGGER trg_version_components_draft_only ON curriculum_version_components;
DROP TRIGGER trg_topic_dependencies_check ON course_topic_dependencies;

-- ---------------------------------------------------------------------------
-- 2. Modules and topics on the course
-- ---------------------------------------------------------------------------
ALTER TABLE course_modules
    ADD COLUMN course_id INT REFERENCES courses(course_id),
    ADD COLUMN component_id INT REFERENCES course_components(component_id),
    ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE course_modules m SET course_id = v.course_id, component_id = v.component_id
FROM curriculum_versions v WHERE v.curriculum_version_id = m.curriculum_version_id;

-- The surviving version of each outline slot: Active, else the latest
CREATE TEMP TABLE r6_survivor AS
SELECT DISTINCT ON (course_id, COALESCE(component_id, 0)) curriculum_version_id, course_id, component_id
FROM curriculum_versions
ORDER BY course_id, COALESCE(component_id, 0), (status = 'Active') DESC, curriculum_version_id DESC;

-- Modules and topics of the other versions that live data refers to: map them by title onto the surviving outline
CREATE TEMP TABLE r6_module_map AS
SELECT DISTINCT ON (old.module_id) old.module_id AS old_id, new.module_id AS new_id
FROM course_modules old
JOIN r6_survivor s ON s.course_id = old.course_id AND s.component_id IS NOT DISTINCT FROM old.component_id
JOIN course_modules new ON new.curriculum_version_id = s.curriculum_version_id
WHERE old.curriculum_version_id <> s.curriculum_version_id AND lower(btrim(new.title)) = lower(btrim(old.title))
ORDER BY old.module_id, new.sort_order;

CREATE TEMP TABLE r6_topic_map AS
WITH candidates AS (
    SELECT old.topic_id AS old_id, new.topic_id AS new_id, 1 AS rank, new.sort_order AS so, nm.sort_order AS mo
    FROM course_topics old
    JOIN course_modules om ON om.module_id = old.module_id
    JOIN r6_survivor s ON s.course_id = om.course_id AND s.component_id IS NOT DISTINCT FROM om.component_id
    JOIN course_modules nm ON nm.curriculum_version_id = s.curriculum_version_id AND lower(btrim(nm.title)) = lower(btrim(om.title))
    JOIN course_topics new ON new.module_id = nm.module_id AND lower(btrim(new.title)) = lower(btrim(old.title))
    WHERE om.curriculum_version_id <> s.curriculum_version_id
    UNION ALL
    SELECT old.topic_id, new.topic_id, 2, new.sort_order, nm.sort_order
    FROM course_topics old
    JOIN course_modules om ON om.module_id = old.module_id
    JOIN r6_survivor s ON s.course_id = om.course_id AND s.component_id IS NOT DISTINCT FROM om.component_id
    JOIN course_modules nm ON nm.curriculum_version_id = s.curriculum_version_id
    JOIN course_topics new ON new.module_id = nm.module_id AND lower(btrim(new.title)) = lower(btrim(old.title))
    WHERE om.curriculum_version_id <> s.curriculum_version_id
)
SELECT DISTINCT ON (old_id) old_id, new_id FROM candidates ORDER BY old_id, rank, mo, so;

-- Re-point every foreign key that references a mapped topic or module (generic: columns found in the catalogue)
DO $$
DECLARE
    fk RECORD;
BEGIN
    FOR fk IN
        SELECT c.conrelid::regclass AS tbl, a.attname AS col, c.confrelid::regclass::text AS target
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND array_length(c.conkey, 1) = 1
          AND c.confrelid IN ('course_topics'::regclass, 'course_modules'::regclass)
          AND c.conrelid NOT IN ('course_topics'::regclass, 'course_modules'::regclass,
                                 'course_topic_dependencies'::regclass, 'learning_credits'::regclass)
    LOOP
        IF fk.target = 'course_topics' THEN
            EXECUTE format('UPDATE %s t SET %I = m.new_id FROM r6_topic_map m WHERE t.%I = m.old_id', fk.tbl, fk.col, fk.col);
        ELSE
            EXECUTE format('UPDATE %s t SET %I = m.new_id FROM r6_module_map m WHERE t.%I = m.old_id', fk.tbl, fk.col, fk.col);
        END IF;
    END LOOP;
END $$;

-- Requirements of versions that did not survive go with them (the survivors' keep their rows)
DELETE FROM course_assessment_requirements r
WHERE NOT EXISTS (SELECT 1 FROM r6_survivor s WHERE s.curriculum_version_id = r.curriculum_version_id);

-- Modules of the other versions: delete when nothing refers to them, else keep as archived (still the course's, hidden)
CREATE TEMP TABLE r6_log (kind TEXT, n INT);
DO $$
DECLARE
    m RECORD;
    topics_in INT;
BEGIN
    FOR m IN
        SELECT cm.module_id FROM course_modules cm
        WHERE NOT EXISTS (SELECT 1 FROM r6_survivor s WHERE s.curriculum_version_id = cm.curriculum_version_id)
        ORDER BY cm.module_id
    LOOP
        SELECT count(*) INTO topics_in FROM course_topics WHERE module_id = m.module_id;
        BEGIN
            DELETE FROM course_modules WHERE module_id = m.module_id;
            INSERT INTO r6_log VALUES ('deleted_modules', 1), ('deleted_topics', topics_in);
        EXCEPTION WHEN foreign_key_violation THEN
            UPDATE course_modules SET is_archived = TRUE WHERE module_id = m.module_id;
            INSERT INTO r6_log VALUES ('archived_modules', 1), ('archived_topics', topics_in);
        END;
    END LOOP;
END $$;

ALTER TABLE course_modules DROP CONSTRAINT curriculum_modules_order;
ALTER TABLE course_modules ALTER COLUMN course_id SET NOT NULL;
CREATE UNIQUE INDEX course_modules_order ON course_modules (course_id, COALESCE(component_id, 0), sort_order) WHERE NOT is_archived;
CREATE INDEX course_modules_course_idx ON course_modules (course_id, component_id);

CREATE OR REPLACE FUNCTION check_module_component() RETURNS trigger AS $$
BEGIN
    IF NEW.component_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM course_components WHERE component_id = NEW.component_id AND parent_course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'The track does not belong to this course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_course_modules_component
    BEFORE INSERT OR UPDATE OF course_id, component_id ON course_modules
    FOR EACH ROW EXECUTE FUNCTION check_module_component();

-- ---------------------------------------------------------------------------
-- 3. Hours, completion rules, required assessments, combo track pins on the course
-- ---------------------------------------------------------------------------
ALTER TABLE courses
    ADD COLUMN hours_verified_by INT REFERENCES users(user_id),
    ADD COLUMN hours_verified_at TIMESTAMPTZ,
    ADD COLUMN completion_profile JSONB;          -- {attendance_minimum_pct, pass_mark_pct, recovery_rule, reassessment_rule}

UPDATE courses c SET hours_verified_by = v.hours_verified_by, hours_verified_at = v.hours_verified_at,
                     completion_profile = v.completion_profile
FROM curriculum_versions v JOIN r6_survivor s ON s.curriculum_version_id = v.curriculum_version_id
WHERE v.course_id = c.course_id AND s.component_id IS NULL;

ALTER TABLE courses ADD CONSTRAINT courses_hours_verified CHECK ((hours_verified_by IS NULL) = (hours_verified_at IS NULL));

ALTER TABLE course_assessment_requirements ADD COLUMN course_id INT REFERENCES courses(course_id);
UPDATE course_assessment_requirements r SET course_id = v.course_id
FROM curriculum_versions v WHERE v.curriculum_version_id = r.curriculum_version_id;
ALTER TABLE course_assessment_requirements ALTER COLUMN course_id SET NOT NULL;
ALTER TABLE course_assessment_requirements DROP COLUMN curriculum_version_id;
CREATE INDEX assessment_requirements_course_idx2 ON course_assessment_requirements (course_id);

-- A track may reuse a standalone course's outline once its equivalence review is recorded (Module 14 §3, kept as the pin's gate)
ALTER TABLE course_components ADD COLUMN pinned_course_id INT REFERENCES courses(course_id);
UPDATE course_components cc SET pinned_course_id = p.course_id
FROM (SELECT DISTINCT ON (vc.component_id) vc.component_id, cv.course_id
      FROM curriculum_version_components vc
      JOIN curriculum_versions cv ON cv.curriculum_version_id = vc.component_version_id
      ORDER BY vc.component_id, vc.curriculum_version_id DESC) p
WHERE p.component_id = cc.component_id AND p.course_id <> cc.parent_course_id AND cc.equivalence_reviewed_at IS NOT NULL;
ALTER TABLE course_components
    ADD CONSTRAINT course_components_pin_not_self CHECK (pinned_course_id IS NULL OR pinned_course_id <> parent_course_id),
    ADD CONSTRAINT course_components_pin_reviewed CHECK (pinned_course_id IS NULL OR equivalence_reviewed_at IS NOT NULL);

-- Dependencies stay inside one outline
CREATE OR REPLACE FUNCTION topic_dependencies_check() RETURNS trigger AS $$
DECLARE
    a RECORD;
    b RECORD;
BEGIN
    SELECT m.course_id, m.component_id INTO a FROM course_topics t JOIN course_modules m ON m.module_id = t.module_id WHERE t.topic_id = NEW.topic_id;
    SELECT m.course_id, m.component_id INTO b FROM course_topics t JOIN course_modules m ON m.module_id = t.module_id WHERE t.topic_id = NEW.depends_on_topic_id;
    IF a.course_id IS DISTINCT FROM b.course_id OR a.component_id IS DISTINCT FROM b.component_id THEN
        RAISE EXCEPTION 'A topic can only depend on a topic of the same course outline';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_topic_dependencies_check
    BEFORE INSERT OR UPDATE ON course_topic_dependencies
    FOR EACH ROW EXECUTE FUNCTION topic_dependencies_check();

-- ---------------------------------------------------------------------------
-- 4. Functions that read the outline through the version
-- ---------------------------------------------------------------------------
-- Is the topic part of the course's outline (its own, or the outline a combo track is pinned to)?
CREATE OR REPLACE FUNCTION course_covers_topic(p_course_id INT, p_topic_id INT) RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM course_topics t JOIN course_modules m ON m.module_id = t.module_id
        WHERE t.topic_id = p_topic_id
          AND (m.course_id = p_course_id
               OR EXISTS (SELECT 1 FROM course_components cc WHERE cc.parent_course_id = p_course_id AND cc.pinned_course_id = m.course_id)));
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION check_session_topic_and_trainer() RETURNS trigger AS $$
DECLARE
    v_batch_course INT;
    v_clash class_sessions%ROWTYPE;
BEGIN
    IF NEW.topic_id IS NOT NULL THEN
        SELECT course_id INTO v_batch_course FROM batches WHERE batch_id = NEW.batch_id;
        IF NOT course_covers_topic(v_batch_course, NEW.topic_id) THEN
            RAISE EXCEPTION 'The topic belongs to a different course than the batch';
        END IF;
    END IF;

    IF NEW.state IN ('Scheduled', 'Live', 'Rescheduled') THEN
        SELECT * INTO v_clash FROM class_sessions
        WHERE trainer_user_id = NEW.trainer_user_id AND session_id IS DISTINCT FROM NEW.session_id
          AND state IN ('Scheduled', 'Live', 'Rescheduled')
          AND starts_at < NEW.ends_at AND ends_at > NEW.starts_at
        LIMIT 1;
        IF FOUND THEN
            RAISE EXCEPTION 'The trainer already teaches % (%) at that time', v_clash.session_code, v_clash.title;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION content_items_before_write() RETURNS trigger AS $$
DECLARE
    v_batch batches%ROWTYPE;
BEGIN
    IF TG_OP = 'INSERT' AND NEW.item_code IS NULL THEN
        NEW.item_code = 'CNT-' || lpad(next_counter_value('CNT')::TEXT, 6, '0');
    ELSIF TG_OP = 'UPDATE' AND NEW.item_code <> OLD.item_code THEN
        RAISE EXCEPTION 'item_code cannot change';
    END IF;

    IF NEW.module_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM course_modules m WHERE m.module_id = NEW.module_id
          AND (m.course_id = NEW.course_id
               OR EXISTS (SELECT 1 FROM course_components cc WHERE cc.parent_course_id = NEW.course_id AND cc.pinned_course_id = m.course_id))) THEN
        RAISE EXCEPTION 'The module does not belong to this course';
    END IF;
    IF NEW.topic_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM course_topics WHERE topic_id = NEW.topic_id AND module_id = NEW.module_id) THEN
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

CREATE OR REPLACE FUNCTION assignments_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.assignment_code IS NULL THEN
        LOOP
            NEW.assignment_code = 'ASG-' || lpad(next_counter_value('ASG')::TEXT, 4, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM assignments WHERE assignment_code = NEW.assignment_code);
        END LOOP;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.batch_id <> OLD.batch_id THEN
        RAISE EXCEPTION 'An assignment cannot move to another batch';
    END IF;
    IF NEW.topic_id IS NOT NULL AND NOT course_covers_topic((SELECT course_id FROM batches WHERE batch_id = NEW.batch_id), NEW.topic_id) THEN
        RAISE EXCEPTION 'The topic does not belong to the batch''s course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION questions_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.question_code IS NULL THEN
        LOOP
            NEW.question_code = 'QB-' || lpad(next_counter_value('QB')::TEXT, 4, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM questions WHERE question_code = NEW.question_code);
        END LOOP;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'Approved' AND NEW.status = 'Approved'
       AND (NEW.stem IS DISTINCT FROM OLD.stem OR NEW.options IS DISTINCT FROM OLD.options
            OR NEW.answer_key IS DISTINCT FROM OLD.answer_key OR NEW.marks IS DISTINCT FROM OLD.marks) THEN
        RAISE EXCEPTION 'An approved question cannot be edited; create a new version instead';
    END IF;
    IF NEW.topic_id IS NOT NULL AND NOT course_covers_topic(NEW.course_id, NEW.topic_id) THEN
        RAISE EXCEPTION 'The topic does not belong to the question''s course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 5. Views: an enrolment follows the outline of its course (and of each combo track it holds)
-- ---------------------------------------------------------------------------
CREATE VIEW enrolment_outlines AS
SELECT e.enrolment_id, e.course_id, NULL::INT AS component_id FROM enrolments e
UNION
SELECT t.enrolment_id,
       COALESCE(cc.pinned_course_id, cc.parent_course_id),
       CASE WHEN cc.pinned_course_id IS NULL THEN t.component_id END
FROM enrolment_tracks t JOIN course_components cc ON cc.component_id = t.component_id;

CREATE OR REPLACE VIEW enrolment_required_topics AS
SELECT o.enrolment_id, t.topic_id
FROM enrolment_outlines o
JOIN course_modules m ON m.course_id = o.course_id AND m.component_id IS NOT DISTINCT FROM o.component_id AND NOT m.is_archived
JOIN course_topics t ON t.module_id = m.module_id AND t.is_required;

CREATE OR REPLACE VIEW enrolment_covered_topics AS
SELECT DISTINCT enrolment_id, topic_id
FROM attendance_grid
WHERE topic_id IS NOT NULL
  AND (attendance_status IN ('Present', 'Late') OR recovery_status = 'Completed');

DROP VIEW topic_progress;
CREATE VIEW topic_progress AS
WITH topics AS (
    SELECT o.enrolment_id, t.topic_id, m.module_id, m.course_id, m.component_id, t.is_required
    FROM enrolment_outlines o
    JOIN course_modules m ON m.course_id = o.course_id AND m.component_id IS NOT DISTINCT FROM o.component_id AND NOT m.is_archived
    JOIN course_topics t ON t.module_id = m.module_id
), signals AS (
    SELECT tp.*,
           EXISTS (SELECT 1 FROM enrolment_covered_topics c
                   WHERE c.enrolment_id = tp.enrolment_id AND c.topic_id = tp.topic_id) AS attended,
           EXISTS (SELECT 1 FROM activity_events a
                   JOIN recordings r ON r.recording_id = (a.detail ->> 'recording_id')::INT
                   JOIN class_sessions cs ON cs.session_id = r.session_id
                   WHERE a.enrolment_id = tp.enrolment_id AND a.kind = 'recording_view' AND cs.topic_id = tp.topic_id) AS recording_watched,
           (SELECT count(*) FROM assignments x
            WHERE x.topic_id = tp.topic_id AND x.is_required AND x.status = 'Released'
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)) AS required_assignments,
           (SELECT count(*) FROM assignments x
            WHERE x.topic_id = tp.topic_id AND x.is_required AND x.status = 'Released'
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)
              AND EXISTS (SELECT 1 FROM assignment_submissions s
                          WHERE s.assignment_id = x.assignment_id AND s.enrolment_id = tp.enrolment_id)) AS assignments_handed_in,
           (SELECT count(*) FROM tests x
            WHERE x.topic_id = tp.topic_id AND x.is_required
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)) AS required_tests,
           (SELECT count(*) FROM tests x
            WHERE x.topic_id = tp.topic_id AND x.is_required
              AND x.batch_id IN (SELECT batch_id FROM enrolment_batch_links l WHERE l.enrolment_id = tp.enrolment_id)
              AND EXISTS (SELECT 1 FROM test_attempts a
                          WHERE a.test_id = x.test_id AND a.enrolment_id = tp.enrolment_id AND a.status = 'Submitted')) AS tests_taken
    FROM topics tp
)
SELECT enrolment_id, topic_id, module_id, course_id, component_id, is_required,
       attended, recording_watched,
       required_assignments, assignments_handed_in, required_tests, tests_taken,
       (attended OR recording_watched)
           AND assignments_handed_in >= required_assignments AND tests_taken >= required_tests AS is_done,
       CASE WHEN (attended OR recording_watched) AND assignments_handed_in >= required_assignments AND tests_taken >= required_tests THEN 'Done'
            WHEN attended OR recording_watched THEN 'Work to hand in'
            ELSE 'Not started' END AS status
FROM signals;

-- ---------------------------------------------------------------------------
-- 6. Drop the version columns, then the version, draft, approval and equivalence tables
-- ---------------------------------------------------------------------------
DROP TRIGGER trg_enrolments_academics ON enrolments;
DROP TRIGGER trg_enrolment_tracks_academics ON enrolment_tracks;

ALTER TABLE content_items DROP CONSTRAINT content_items_module_needs_version;
DROP INDEX content_items_course_idx;
ALTER TABLE content_items DROP COLUMN curriculum_version_id;
CREATE INDEX content_items_course_idx ON content_items (course_id);
ALTER TABLE enrolments DROP COLUMN curriculum_version_id;
ALTER TABLE enrolment_tracks DROP COLUMN curriculum_version_id;
ALTER TABLE batches DROP COLUMN curriculum_version_id;
ALTER TABLE course_modules DROP COLUMN curriculum_version_id;

CREATE TRIGGER trg_enrolments_academics
    AFTER INSERT OR UPDATE OF status, joining_date, service_branch_id, completed_at ON enrolments
    FOR EACH ROW EXECUTE FUNCTION enrolments_refresh_academics();
CREATE TRIGGER trg_enrolment_tracks_academics
    AFTER INSERT ON enrolment_tracks
    FOR EACH ROW EXECUTE FUNCTION enrolment_tracks_refresh_academics();

DROP TABLE curriculum_variations;
DROP TABLE learning_credits;
DROP TABLE academic_mappings;
DROP TABLE equivalence_rules;
DROP TABLE curriculum_version_components;
DROP TABLE curriculum_events;
DROP TABLE curriculum_versions;
DROP FUNCTION active_curriculum_version(INT, INT);
DROP FUNCTION check_curriculum_component();
DROP FUNCTION curriculum_child_is_draft();
DROP FUNCTION curriculum_content_is_draft();
DROP FUNCTION topic_version(INT);
DROP TYPE curriculum_status;

-- The library has no approval step any more: a saved or changed library module is usable at once
ALTER TABLE library_module_versions DROP CONSTRAINT library_versions_independent;
UPDATE library_module_versions SET status = 'Approved', decided_by = proposed_by, decided_at = COALESCE(decided_at, CURRENT_TIMESTAMP)
WHERE status <> 'Approved';

-- Notices written while there were approvals keep their text; their links and category move to Courses
UPDATE notifications SET link = '/founder/courses', category = 'Courses' WHERE link = '/founder/curriculum';
UPDATE notifications SET link = '/branch/courses', category = 'Courses' WHERE link IN ('/branch/curriculum', '/academic/curriculum');
UPDATE notifications SET category = 'Courses' WHERE category = 'Curriculum';

-- ---------------------------------------------------------------------------
-- 7. Verify: every row that was there is still there
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
    after_n BIGINT;
    moved BIGINT;
BEGIN
    FOR r IN SELECT name, n FROM r6_counts WHERE name NOT IN ('modules', 'topics', 'referenced_topics', 'topic_progress_rows', 'required_topic_rows') LOOP
        EXECUTE format('SELECT count(*) FROM %I', r.name) INTO after_n;
        IF after_n <> r.n THEN
            RAISE EXCEPTION 'R6 migration: % had % rows, now %', r.name, r.n, after_n;
        END IF;
    END LOOP;

    SELECT count(*) INTO after_n FROM course_modules;
    SELECT COALESCE(sum(n), 0) INTO moved FROM r6_log WHERE kind = 'deleted_modules';
    IF after_n + moved <> (SELECT n FROM r6_counts WHERE name = 'modules') THEN
        RAISE EXCEPTION 'R6 migration: modules before % <> after % + deleted %', (SELECT n FROM r6_counts WHERE name = 'modules'), after_n, moved;
    END IF;

    SELECT count(*) INTO after_n FROM course_topics;
    SELECT COALESCE(sum(n), 0) INTO moved FROM r6_log WHERE kind = 'deleted_topics';
    IF after_n + moved <> (SELECT n FROM r6_counts WHERE name = 'topics') THEN
        RAISE EXCEPTION 'R6 migration: topics before % <> after % + deleted %', (SELECT n FROM r6_counts WHERE name = 'topics'), after_n, moved;
    END IF;

    -- every topic that something referenced still exists
    SELECT count(DISTINCT x.topic_id) INTO after_n FROM (
        SELECT topic_id FROM class_sessions UNION ALL SELECT topic_id FROM class_session_topics
        UNION ALL SELECT topic_id FROM session_rosters UNION ALL SELECT topic_id FROM content_items
        UNION ALL SELECT topic_id FROM assignments UNION ALL SELECT topic_id FROM questions
        UNION ALL SELECT topic_id FROM tests) x WHERE x.topic_id IS NOT NULL;
    IF after_n > (SELECT n FROM r6_counts WHERE name = 'referenced_topics') THEN
        RAISE EXCEPTION 'R6 migration: referenced topics grew from % to %', (SELECT n FROM r6_counts WHERE name = 'referenced_topics'), after_n;
    END IF;

    -- Progress rows may differ only because every enrolment follows its course now (before, only allocated ones had a version)
    SELECT count(*) INTO after_n FROM topic_progress;
    RAISE NOTICE 'R6: topic_progress rows % -> %; required topic rows % -> %; modules archived %, deleted %',
        (SELECT n FROM r6_counts WHERE name = 'topic_progress_rows'), after_n,
        (SELECT n FROM r6_counts WHERE name = 'required_topic_rows'), (SELECT count(*) FROM enrolment_required_topics),
        (SELECT count(*) FROM course_modules WHERE is_archived), (SELECT COALESCE(sum(n), 0) FROM r6_log WHERE kind = 'deleted_modules');
END $$;

DROP TABLE r6_log;
DROP TABLE r6_topic_map;
DROP TABLE r6_module_map;
DROP TABLE r6_survivor;
DROP TABLE r6_counts;

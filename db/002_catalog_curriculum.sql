-- Phase 1a / 002: course catalogue (mirrored from the CRM Course Master) and curriculum
-- Depends on: 001_foundation.sql

-- ---------------------------------------------------------------------------
-- Courses: created and updated by CRM CourseUpserted events
-- ---------------------------------------------------------------------------
CREATE TYPE course_status AS ENUM ('Active', 'Inactive');

CREATE TABLE courses (
    course_id SERIAL PRIMARY KEY,
    course_code VARCHAR(30) UNIQUE NOT NULL,        -- e.g., 'NIT-CRS-018'
    title VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    is_combo BOOLEAN NOT NULL DEFAULT FALSE,
    status course_status NOT NULL DEFAULT 'Active',
    source_version INT NOT NULL DEFAULT 1 CHECK (source_version >= 1),  -- CRM version; older events are ignored
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_courses_updated_at
    BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Combo structure: parent course -> tracks. A track is either a slice of the parent
-- ('NIT-CRS-018/T1', no course of its own) or an included booster that is a course itself.
-- ---------------------------------------------------------------------------
CREATE TYPE component_role AS ENUM ('Main track', 'Included booster');

CREATE TABLE course_components (
    component_id SERIAL PRIMARY KEY,
    parent_course_id INT NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    component_course_id INT REFERENCES courses(course_id),
    track_code VARCHAR(50) UNIQUE NOT NULL,         -- 'NIT-CRS-018/T1', or the booster's own course code
    track_name VARCHAR(200) NOT NULL,
    role component_role NOT NULL DEFAULT 'Main track',
    sort_order SMALLINT NOT NULL DEFAULT 0,

    CONSTRAINT course_components_not_self CHECK (component_course_id IS NULL OR component_course_id <> parent_course_id),
    CONSTRAINT course_components_booster_is_course CHECK (role <> 'Included booster' OR component_course_id IS NOT NULL)
);

CREATE INDEX course_components_parent_idx ON course_components (parent_course_id, sort_order);

CREATE OR REPLACE FUNCTION check_parent_is_combo() RETURNS trigger AS $$
BEGIN
    IF NOT (SELECT is_combo FROM courses WHERE course_id = NEW.parent_course_id) THEN
        RAISE EXCEPTION 'Only a combo course can have components';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_course_components_parent
    BEFORE INSERT OR UPDATE OF parent_course_id ON course_components
    FOR EACH ROW EXECUTE FUNCTION check_parent_is_combo();

-- ---------------------------------------------------------------------------
-- Curriculum versions: per course, or per track of a combo (component_id set)
-- ---------------------------------------------------------------------------
CREATE TYPE curriculum_status AS ENUM ('Draft', 'Under Review', 'Approved', 'Active', 'Retired');

CREATE TABLE curriculum_versions (
    curriculum_version_id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(course_id),
    component_id INT REFERENCES course_components(component_id),  -- NULL = the course as a whole
    version_label VARCHAR(100) NOT NULL,            -- 'Parent Programme v2026.1', 'Track CV 3.2', 'CV 4.0'
    status curriculum_status NOT NULL DEFAULT 'Draft',
    approved_by INT REFERENCES users(user_id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT curriculum_versions_approval CHECK (status NOT IN ('Approved', 'Active') OR approved_at IS NOT NULL)
);

CREATE UNIQUE INDEX curriculum_versions_label_unique
    ON curriculum_versions (course_id, COALESCE(component_id, 0), version_label);

-- One Active version per course (or per track): this is what new enrolments are mapped to
CREATE UNIQUE INDEX curriculum_versions_one_active
    ON curriculum_versions (course_id, COALESCE(component_id, 0)) WHERE status = 'Active';

CREATE TRIGGER trg_curriculum_versions_updated_at
    BEFORE UPDATE ON curriculum_versions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- The track must belong to the course the version is for
CREATE OR REPLACE FUNCTION check_curriculum_component() RETURNS trigger AS $$
BEGIN
    IF NEW.component_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM course_components WHERE component_id = NEW.component_id AND parent_course_id = NEW.course_id) THEN
        RAISE EXCEPTION 'Track does not belong to this course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_curriculum_versions_component
    BEFORE INSERT OR UPDATE OF course_id, component_id ON curriculum_versions
    FOR EACH ROW EXECUTE FUNCTION check_curriculum_component();

-- The Active version for a course (or a track of it); NULL when none is mapped
CREATE OR REPLACE FUNCTION active_curriculum_version(p_course_id INT, p_component_id INT DEFAULT NULL) RETURNS INT AS $$
    SELECT curriculum_version_id FROM curriculum_versions
    WHERE course_id = p_course_id AND component_id IS NOT DISTINCT FROM p_component_id AND status = 'Active';
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------------
-- Modules and topics
-- ---------------------------------------------------------------------------
CREATE TABLE curriculum_modules (
    module_id SERIAL PRIMARY KEY,
    curriculum_version_id INT NOT NULL REFERENCES curriculum_versions(curriculum_version_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    title_te VARCHAR(300),                          -- Telugu title
    sort_order SMALLINT NOT NULL,

    CONSTRAINT curriculum_modules_order UNIQUE (curriculum_version_id, sort_order)
);

CREATE TABLE curriculum_topics (
    topic_id SERIAL PRIMARY KEY,
    module_id INT NOT NULL REFERENCES curriculum_modules(module_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    title_te VARCHAR(300),
    sort_order SMALLINT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,      -- counts towards required-learning progress

    CONSTRAINT curriculum_topics_order UNIQUE (module_id, sort_order)
);

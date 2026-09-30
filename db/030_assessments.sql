-- Phase 2 / 030 (slice S3): assignments & projects, submissions and reviews, question bank, tests and attempts,
-- mock interview slots, results (provisional -> moderated -> published)
-- Depends on: 004_batches_sessions.sql

-- ---------------------------------------------------------------------------
-- Assignments (Module 19): one definition per batch, linked to a curriculum topic
-- ---------------------------------------------------------------------------
CREATE TYPE assignment_kind AS ENUM ('Class assignment', 'Module assignment', 'Practical lab', 'Mini project', 'Final project');
CREATE TYPE assignment_status AS ENUM ('Draft', 'Released', 'Withdrawn');
CREATE TYPE ai_use_rule AS ENUM ('Allowed with disclosure', 'Limited to specified uses', 'Not permitted');

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    assignment_code VARCHAR(30) UNIQUE NOT NULL,    -- 'ASG-0008'
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    topic_id INT REFERENCES curriculum_topics(topic_id),
    title VARCHAR(200) NOT NULL,
    kind assignment_kind NOT NULL DEFAULT 'Class assignment',
    brief TEXT NOT NULL,
    attachments JSONB NOT NULL DEFAULT '[]',        -- [{"name": "housing.csv", "url": "https://..."}]
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    max_marks NUMERIC(6,2) NOT NULL CHECK (max_marks > 0),
    release_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_at TIMESTAMPTZ NOT NULL,                    -- homework default 11:59 PM IST; no automatic grace period
    closes_at TIMESTAMPTZ NOT NULL,                 -- last moment a first (late) submission is accepted: due + 7 calendar days
    max_resubmissions SMALLINT NOT NULL DEFAULT 2 CHECK (max_resubmissions >= 0),  -- one initial attempt + up to two authorised resubmissions
    late_policy TEXT NOT NULL DEFAULT 'No automatic mark deduction. A first submission after the due time is accepted as Late until the window closes.',
    ai_use_rule ai_use_rule NOT NULL DEFAULT 'Allowed with disclosure',
    reviewer_user_id INT NOT NULL REFERENCES users(user_id),   -- the named reviewer
    status assignment_status NOT NULL DEFAULT 'Draft',
    released_by INT REFERENCES users(user_id),
    withdrawn_reason TEXT,
    created_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT assignments_due_after_release CHECK (due_at > release_at),
    CONSTRAINT assignments_window_after_due CHECK (closes_at >= due_at),
    CONSTRAINT assignments_withdrawn_has_reason CHECK (status <> 'Withdrawn' OR withdrawn_reason IS NOT NULL),
    CONSTRAINT assignments_attachments_list CHECK (jsonb_typeof(attachments) = 'array')
);

CREATE INDEX assignments_batch_idx ON assignments (batch_id, status);
CREATE INDEX assignments_reviewer_idx ON assignments (reviewer_user_id);

CREATE TRIGGER trg_assignments_updated_at
    BEFORE UPDATE ON assignments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

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
    IF NEW.topic_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM curriculum_topics t
        JOIN curriculum_modules m ON m.module_id = t.module_id
        JOIN curriculum_versions v ON v.curriculum_version_id = m.curriculum_version_id
        JOIN batches b ON b.batch_id = NEW.batch_id
        WHERE t.topic_id = NEW.topic_id AND v.course_id = b.course_id
    ) THEN
        RAISE EXCEPTION 'The topic does not belong to the batch''s course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assignments_write
    BEFORE INSERT OR UPDATE ON assignments
    FOR EACH ROW EXECUTE FUNCTION assignments_before_write();

-- ---------------------------------------------------------------------------
-- Submissions: versioned (v1, v2, ...); a version is never edited or replaced
-- ---------------------------------------------------------------------------
CREATE TABLE assignment_submissions (
    submission_id SERIAL PRIMARY KEY,
    submission_code VARCHAR(30) UNIQUE NOT NULL,    -- receipt / reference: 'SUB-000012'
    assignment_id INT NOT NULL REFERENCES assignments(assignment_id),
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    version_no INT NOT NULL CHECK (version_no >= 1),
    attempt_no INT NOT NULL DEFAULT 1 CHECK (attempt_no >= 1),   -- pre-review replacements share an attempt; a resubmission starts the next
    body_text TEXT,
    link_url VARCHAR(500),
    file_path VARCHAR(500),
    original_filename VARCHAR(255),
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    ai_disclosure TEXT,                             -- tool, help received and what the student checked themselves
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,   -- time the complete submission was received
    is_late BOOLEAN NOT NULL DEFAULT FALSE,         -- a first submission after the due time
    review_started_at TIMESTAMPTZ,
    review_started_by INT REFERENCES users(user_id),

    CONSTRAINT submissions_unique_version UNIQUE (assignment_id, enrolment_id, version_no),
    CONSTRAINT submissions_has_content CHECK (body_text IS NOT NULL OR link_url IS NOT NULL OR file_path IS NOT NULL)
);

CREATE INDEX submissions_student_idx ON assignment_submissions (student_id);

CREATE OR REPLACE FUNCTION submissions_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.submission_code IS NULL THEN
            LOOP
                NEW.submission_code = 'SUB-' || lpad(next_counter_value('SUB')::TEXT, 6, '0');
                EXIT WHEN NOT EXISTS (SELECT 1 FROM assignment_submissions WHERE submission_code = NEW.submission_code);
            END LOOP;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM enrolments WHERE enrolment_id = NEW.enrolment_id AND student_id = NEW.student_id) THEN
            RAISE EXCEPTION 'The enrolment does not belong to this student';
        END IF;
    ELSIF NEW.body_text IS DISTINCT FROM OLD.body_text OR NEW.link_url IS DISTINCT FROM OLD.link_url
          OR NEW.file_path IS DISTINCT FROM OLD.file_path OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
        RAISE EXCEPTION 'A submitted version cannot be changed; submit a new version instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_submissions_write
    BEFORE INSERT OR UPDATE ON assignment_submissions
    FOR EACH ROW EXECUTE FUNCTION submissions_before_write();

-- ---------------------------------------------------------------------------
-- Trainer reviews: feedback + provisional marks per version, or a request to resubmit
-- ---------------------------------------------------------------------------
CREATE TYPE review_outcome AS ENUM ('Reviewed', 'Resubmission Requested');

CREATE TABLE submission_reviews (
    review_id SERIAL PRIMARY KEY,
    submission_id INT NOT NULL UNIQUE REFERENCES assignment_submissions(submission_id),
    reviewer_user_id INT NOT NULL REFERENCES users(user_id),
    outcome review_outcome NOT NULL,
    feedback TEXT NOT NULL,
    marks NUMERIC(6,2) CHECK (marks >= 0),
    resubmission_due_at TIMESTAMPTZ,                -- its own deadline for the corrected work
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT reviews_marks_match_outcome CHECK ((outcome = 'Reviewed') = (marks IS NOT NULL)),
    CONSTRAINT reviews_resubmission_has_deadline CHECK ((outcome = 'Resubmission Requested') = (resubmission_due_at IS NOT NULL))
);

CREATE OR REPLACE FUNCTION reviews_check_marks() RETURNS trigger AS $$
DECLARE
    v_max NUMERIC;
BEGIN
    SELECT a.max_marks INTO v_max FROM assignments a
    JOIN assignment_submissions s ON s.assignment_id = a.assignment_id
    WHERE s.submission_id = NEW.submission_id;
    IF NEW.marks IS NOT NULL AND NEW.marks > v_max THEN
        RAISE EXCEPTION 'Marks (%) cannot exceed the maximum marks (%)', NEW.marks, v_max;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reviews_marks
    BEFORE INSERT OR UPDATE OF marks, submission_id ON submission_reviews
    FOR EACH ROW EXECUTE FUNCTION reviews_check_marks();

-- ---------------------------------------------------------------------------
-- Question bank (Module 20): questions per course and topic, answer keys never leave staff APIs
-- ---------------------------------------------------------------------------
CREATE TYPE question_type AS ENUM (
    'Single choice', 'Multiple choice', 'True / False', 'Numeric', 'Short answer', 'Descriptive', 'Coding', 'Output prediction'
);
CREATE TYPE question_status AS ENUM ('Draft', 'Approved', 'Retired');
CREATE TYPE question_difficulty AS ENUM ('Easy', 'Medium', 'Hard');

CREATE TABLE questions (
    question_id SERIAL PRIMARY KEY,
    question_code VARCHAR(30) UNIQUE NOT NULL,      -- 'QB-0001'
    course_id INT NOT NULL REFERENCES courses(course_id),
    branch_id INT NOT NULL REFERENCES branches(branch_id),   -- the branch whose staff own and see the item
    topic_id INT REFERENCES curriculum_topics(topic_id),
    question_type question_type NOT NULL,
    stem TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]',            -- choice questions: [{"key": "A", "text": "..."}]
    answer_key JSONB NOT NULL,                      -- by type: {"option": "B"} | {"options": [..]} | {"value": true|number, "tolerance": n} | {"variants": [..]} | {"rubric": ".."}
    explanation TEXT,
    marks NUMERIC(5,2) NOT NULL DEFAULT 1 CHECK (marks > 0),
    difficulty question_difficulty NOT NULL DEFAULT 'Medium',
    tags TEXT[] NOT NULL DEFAULT '{}',
    status question_status NOT NULL DEFAULT 'Draft',
    version INT NOT NULL DEFAULT 1,
    parent_question_id INT REFERENCES questions(question_id),   -- the version this one replaces
    author_user_id INT NOT NULL REFERENCES users(user_id),
    reviewed_by INT REFERENCES users(user_id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT questions_options_list CHECK (jsonb_typeof(options) = 'array'),
    CONSTRAINT questions_choice_has_options CHECK (
        question_type NOT IN ('Single choice', 'Multiple choice') OR jsonb_array_length(options) >= 2),
    CONSTRAINT questions_key_object CHECK (jsonb_typeof(answer_key) = 'object'),
    CONSTRAINT questions_approved_has_reviewer CHECK (status <> 'Approved' OR (approved_at IS NOT NULL AND reviewed_by IS NOT NULL))
);

CREATE INDEX questions_course_idx ON questions (course_id, status);
CREATE INDEX questions_branch_idx ON questions (branch_id);

CREATE TRIGGER trg_questions_updated_at
    BEFORE UPDATE ON questions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

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
    IF NEW.topic_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM curriculum_topics t
        JOIN curriculum_modules m ON m.module_id = t.module_id
        JOIN curriculum_versions v ON v.curriculum_version_id = m.curriculum_version_id
        WHERE t.topic_id = NEW.topic_id AND v.course_id = NEW.course_id
    ) THEN
        RAISE EXCEPTION 'The topic does not belong to the question''s course';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_questions_write
    BEFORE INSERT OR UPDATE ON questions
    FOR EACH ROW EXECUTE FUNCTION questions_before_write();

-- ---------------------------------------------------------------------------
-- Tests: practice quiz, module test, coding exercise, mock test, mock interview, final test
-- ---------------------------------------------------------------------------
CREATE TYPE test_kind AS ENUM ('Practice quiz', 'Module test', 'Coding exercise', 'Mock test', 'Mock interview', 'Final test');
-- What staff control. The student-facing status also has Scheduled / Available, derived from the window while Released.
CREATE TYPE test_release_status AS ENUM ('Configuration Pending', 'Not Released', 'Released', 'Closed');

CREATE TABLE tests (
    test_id SERIAL PRIMARY KEY,
    test_code VARCHAR(30) UNIQUE NOT NULL,          -- 'TST-0001'
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    module_id INT REFERENCES curriculum_modules(module_id),
    topic_id INT REFERENCES curriculum_topics(topic_id),
    title VARCHAR(200) NOT NULL,
    kind test_kind NOT NULL,
    instructions TEXT,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,     -- practice and mocks are optional unless the curriculum says otherwise
    ai_use_rule ai_use_rule NOT NULL DEFAULT 'Not permitted',
    duration_minutes INT CHECK (duration_minutes > 0),
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    attempts_allowed INT CHECK (attempts_allowed >= 1),   -- NULL = repeat within the window (practice)
    pass_marks NUMERIC(7,2) CHECK (pass_marks >= 0),
    release_status test_release_status NOT NULL DEFAULT 'Configuration Pending',
    approved_by INT REFERENCES users(user_id),      -- Academic Coordinator sign-off of questions and settings (formal tests)
    approved_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,
    reviewer_user_id INT NOT NULL REFERENCES users(user_id),   -- the named grader
    created_by INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT tests_window CHECK (opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at),
    CONSTRAINT tests_released_has_window CHECK (release_status NOT IN ('Released') OR released_at IS NOT NULL)
);

CREATE INDEX tests_batch_idx ON tests (batch_id, release_status);

CREATE TRIGGER trg_tests_updated_at
    BEFORE UPDATE ON tests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION tests_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.test_code IS NULL THEN
        LOOP
            NEW.test_code = 'TST-' || lpad(next_counter_value('TST')::TEXT, 4, '0');
            EXIT WHEN NOT EXISTS (SELECT 1 FROM tests WHERE test_code = NEW.test_code);
        END LOOP;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.batch_id <> OLD.batch_id THEN
        RAISE EXCEPTION 'A test cannot move to another batch';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tests_write
    BEFORE INSERT OR UPDATE ON tests
    FOR EACH ROW EXECUTE FUNCTION tests_before_write();

-- The question set of a test, frozen at selection time: the exact wording, key and marks every attempt is scored against
CREATE TABLE test_questions (
    test_id INT NOT NULL REFERENCES tests(test_id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES questions(question_id),
    position SMALLINT NOT NULL CHECK (position >= 1),
    question_version INT NOT NULL,
    question_type question_type NOT NULL,
    stem TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]',
    answer_key JSONB NOT NULL,
    marks NUMERIC(5,2) NOT NULL CHECK (marks > 0),

    PRIMARY KEY (test_id, question_id),
    CONSTRAINT test_questions_position UNIQUE (test_id, position) DEFERRABLE INITIALLY DEFERRED
);

-- ---------------------------------------------------------------------------
-- Attempts: the server owns the clock (started_at, deadline_at) and the receipt
-- ---------------------------------------------------------------------------
CREATE TYPE attempt_status AS ENUM ('In Progress', 'Submitted');
CREATE TYPE attempt_grading_status AS ENUM ('Pending', 'Awaiting Grading', 'Graded');

CREATE TABLE test_attempts (
    attempt_id SERIAL PRIMARY KEY,
    test_id INT NOT NULL REFERENCES tests(test_id),
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    attempt_no INT NOT NULL CHECK (attempt_no >= 1),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deadline_at TIMESTAMPTZ,                        -- min(start + duration, window end); NULL only for an untimed test without a window end
    submitted_at TIMESTAMPTZ,                       -- the effective submission (or expiry) time, not the processing time
    submit_reason VARCHAR(20) CHECK (submit_reason IN ('Student', 'Timeout')),
    status attempt_status NOT NULL DEFAULT 'In Progress',
    grading_status attempt_grading_status NOT NULL DEFAULT 'Pending',
    receipt_code VARCHAR(30) UNIQUE,                -- 'RCPT-T-00931', issued once at submission
    auto_score NUMERIC(7,2),
    total_score NUMERIC(7,2),                       -- auto + trainer-graded marks once every question is graded
    graded_by INT REFERENCES users(user_id),
    graded_at TIMESTAMPTZ,

    CONSTRAINT attempts_unique_no UNIQUE (test_id, enrolment_id, attempt_no),
    CONSTRAINT attempts_submitted_consistent CHECK ((status = 'Submitted') = (submitted_at IS NOT NULL AND submit_reason IS NOT NULL)),
    CONSTRAINT attempts_deadline_after_start CHECK (deadline_at IS NULL OR deadline_at > started_at)
);

-- One attempt in progress per student and test
CREATE UNIQUE INDEX attempts_one_in_progress ON test_attempts (test_id, enrolment_id) WHERE status = 'In Progress';
CREATE INDEX attempts_student_idx ON test_attempts (student_id);

CREATE OR REPLACE FUNCTION attempts_before_write() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NOT EXISTS (SELECT 1 FROM enrolments WHERE enrolment_id = NEW.enrolment_id AND student_id = NEW.student_id) THEN
        RAISE EXCEPTION 'The enrolment does not belong to this student';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'Submitted' AND (NEW.status <> 'Submitted' OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at) THEN
        RAISE EXCEPTION 'A submitted attempt cannot be reopened';
    END IF;
    -- The receipt is issued exactly once, when the attempt is submitted
    IF NEW.status = 'Submitted' AND NEW.receipt_code IS NULL THEN
        NEW.receipt_code = 'RCPT-T-' || lpad(next_counter_value('RCPT-T')::TEXT, 5, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_attempts_write
    BEFORE INSERT OR UPDATE ON test_attempts
    FOR EACH ROW EXECUTE FUNCTION attempts_before_write();

CREATE TABLE attempt_answers (
    answer_id SERIAL PRIMARY KEY,
    attempt_id INT NOT NULL REFERENCES test_attempts(attempt_id) ON DELETE CASCADE,
    question_id INT NOT NULL REFERENCES questions(question_id),
    answer JSONB,                                   -- by type: "B" | ["A","C"] | true | 3.5 | "text"
    saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    awarded_marks NUMERIC(6,2) CHECK (awarded_marks >= 0),
    is_auto_graded BOOLEAN NOT NULL DEFAULT FALSE,
    grader_feedback TEXT,
    graded_by INT REFERENCES users(user_id),
    graded_at TIMESTAMPTZ,

    CONSTRAINT attempt_answers_unique UNIQUE (attempt_id, question_id)
);

-- Answers are only accepted while the attempt is open and before its server deadline; awarded marks may change later.
-- A blank placeholder row (no answer) can be added at any time so an unanswered question can be marked 0 at submission.
CREATE OR REPLACE FUNCTION attempt_answers_guard() RETURNS trigger AS $$
DECLARE
    v_attempt test_attempts%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.answer IS NOT DISTINCT FROM OLD.answer THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' AND NEW.answer IS NULL THEN
        RETURN NEW;  -- a placeholder for an unanswered question, so it can carry marks
    END IF;
    SELECT * INTO v_attempt FROM test_attempts WHERE attempt_id = NEW.attempt_id;
    IF v_attempt.status = 'Submitted' THEN
        RAISE EXCEPTION 'Answers are frozen: this attempt has been submitted';
    END IF;
    IF v_attempt.deadline_at IS NOT NULL AND CURRENT_TIMESTAMP > v_attempt.deadline_at THEN
        RAISE EXCEPTION 'The time for this attempt is over';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM test_questions WHERE test_id = v_attempt.test_id AND question_id = NEW.question_id) THEN
        RAISE EXCEPTION 'The question is not part of this test';
    END IF;
    NEW.saved_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_attempt_answers_guard
    BEFORE INSERT OR UPDATE ON attempt_answers
    FOR EACH ROW EXECUTE FUNCTION attempt_answers_guard();

-- ---------------------------------------------------------------------------
-- Mock interview slots: offered by the trainer, booked by the student, confirmed, completed with feedback
-- ---------------------------------------------------------------------------
CREATE TYPE slot_status AS ENUM ('Open', 'Slot Confirmation Pending', 'Confirmed', 'Completed', 'Cancelled');

CREATE TABLE interview_slots (
    slot_id SERIAL PRIMARY KEY,
    test_id INT NOT NULL REFERENCES tests(test_id),
    trainer_user_id INT NOT NULL REFERENCES users(user_id),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status slot_status NOT NULL DEFAULT 'Open',
    enrolment_id INT REFERENCES enrolments(enrolment_id),
    student_id INT REFERENCES students(student_id),
    booked_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    rating SMALLINT CHECK (rating BETWEEN 1 AND 5),
    strengths TEXT,
    improvements TEXT,
    next_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT slots_time CHECK (ends_at > starts_at),
    CONSTRAINT slots_booked_has_student CHECK ((status IN ('Open', 'Cancelled')) OR student_id IS NOT NULL),
    CONSTRAINT slots_completed_has_feedback CHECK (status <> 'Completed' OR (rating IS NOT NULL AND completed_at IS NOT NULL))
);

CREATE UNIQUE INDEX slots_trainer_time ON interview_slots (trainer_user_id, starts_at) WHERE status <> 'Cancelled';
CREATE UNIQUE INDEX slots_one_booking_per_student ON interview_slots (test_id, enrolment_id)
    WHERE status IN ('Slot Confirmation Pending', 'Confirmed', 'Completed');

CREATE TRIGGER trg_interview_slots_updated_at
    BEFORE UPDATE ON interview_slots
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Results: provisional (trainer) -> moderated (Academic Coordinator adjusts, reason) -> published (visible to students)
-- ---------------------------------------------------------------------------
CREATE TYPE result_status AS ENUM ('Provisional', 'Moderated', 'Published');

CREATE TABLE results (
    result_id SERIAL PRIMARY KEY,
    enrolment_id INT NOT NULL REFERENCES enrolments(enrolment_id),
    student_id INT NOT NULL REFERENCES students(student_id),
    batch_id INT NOT NULL REFERENCES batches(batch_id),
    assignment_id INT REFERENCES assignments(assignment_id),
    test_id INT REFERENCES tests(test_id),
    submission_id INT REFERENCES assignment_submissions(submission_id),   -- the version whose marks count
    attempt_id INT REFERENCES test_attempts(attempt_id),                  -- the attempt whose score counts (best graded attempt)
    max_marks NUMERIC(7,2) NOT NULL CHECK (max_marks > 0),
    provisional_marks NUMERIC(7,2) NOT NULL CHECK (provisional_marks >= 0),
    moderated_marks NUMERIC(7,2) CHECK (moderated_marks >= 0),
    final_marks NUMERIC(7,2) CHECK (final_marks >= 0),
    status result_status NOT NULL DEFAULT 'Provisional',
    moderation_reason TEXT,
    moderated_by INT REFERENCES users(user_id),
    moderated_at TIMESTAMPTZ,
    published_by INT REFERENCES users(user_id),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT results_one_source CHECK ((assignment_id IS NULL) <> (test_id IS NULL)),
    CONSTRAINT results_marks_within_max CHECK (
        provisional_marks <= max_marks AND COALESCE(moderated_marks, 0) <= max_marks AND COALESCE(final_marks, 0) <= max_marks),
    CONSTRAINT results_moderated_has_reason CHECK (status <> 'Moderated' OR (moderated_marks IS NOT NULL AND moderation_reason IS NOT NULL)),
    CONSTRAINT results_published_complete CHECK (status <> 'Published' OR (final_marks IS NOT NULL AND published_at IS NOT NULL AND published_by IS NOT NULL))
);

CREATE UNIQUE INDEX results_one_per_assignment ON results (assignment_id, enrolment_id) WHERE assignment_id IS NOT NULL;
CREATE UNIQUE INDEX results_one_per_test ON results (test_id, enrolment_id) WHERE test_id IS NOT NULL;
CREATE INDEX results_batch_idx ON results (batch_id, status);
CREATE INDEX results_student_idx ON results (student_id, status);

CREATE TRIGGER trg_results_updated_at
    BEFORE UPDATE ON results
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Students, batch and item must agree, and a published result is final
CREATE OR REPLACE FUNCTION results_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM enrolments WHERE enrolment_id = NEW.enrolment_id AND student_id = NEW.student_id) THEN
            RAISE EXCEPTION 'The enrolment does not belong to this student';
        END IF;
        IF NEW.assignment_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments WHERE assignment_id = NEW.assignment_id AND batch_id = NEW.batch_id) THEN
            RAISE EXCEPTION 'The assignment does not belong to this batch';
        END IF;
        IF NEW.test_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM tests WHERE test_id = NEW.test_id AND batch_id = NEW.batch_id) THEN
            RAISE EXCEPTION 'The test does not belong to this batch';
        END IF;
    ELSIF OLD.status = 'Published' AND (NEW.provisional_marks IS DISTINCT FROM OLD.provisional_marks
          OR NEW.moderated_marks IS DISTINCT FROM OLD.moderated_marks OR NEW.final_marks IS DISTINCT FROM OLD.final_marks
          OR NEW.status <> 'Published') THEN
        RAISE EXCEPTION 'A published result cannot be changed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_results_guard
    BEFORE INSERT OR UPDATE ON results
    FOR EACH ROW EXECUTE FUNCTION results_guard();

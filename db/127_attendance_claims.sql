-- 127: students confirm they attended an online class (docs/PRODUCT_GUIDE.md, attendance)
-- Depends on: 004 (class_sessions), 003 (enrolments), 040 (attendance_records)
--   A claim is the student saying "I attended". It is never attendance: the trainer's (or Branch Manager's) register stays the only
--   record, and the register shows who claimed so the trainer can confirm or correct. One claim per student per class.

CREATE TABLE attendance_claims (
    claim_id BIGSERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES class_sessions (session_id) ON DELETE CASCADE,
    enrolment_id INTEGER NOT NULL REFERENCES enrolments (enrolment_id),
    claimed_by INTEGER NOT NULL REFERENCES users (user_id),
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (session_id, enrolment_id)
);

CREATE INDEX attendance_claims_session_idx ON attendance_claims (session_id);

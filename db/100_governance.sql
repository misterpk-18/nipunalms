-- 100: phase 3 of the gap fix plan — governance and approvals (docs/GAP_FIX_PLAN.md, docs/GAPS.md)
-- Depends on: 003 (admissions, finance_summaries), 040 (certificates), 050 (ai_queries)
--   Certificates: a financial-release exception for an unpaid fee (G032), requests for correction / reissue, revocation and
--   reinstatement decided by an independent approver (G036, G095), a status history that keeps a revoked interval, and
--   reinstatement (Revoked -> Issued under the same number). AI: switching a feature off with scope, reason and a
--   restoration record (G042).

-- ---------------------------------------------------------------------------
-- Certificate-release financial exception (Module 22 §5): lets a certificate go ahead while the fee is not cleared.
-- It never waives the debt; the CRM ledger stays authoritative.
-- ---------------------------------------------------------------------------
CREATE TYPE approval_status AS ENUM ('Pending', 'Approved', 'Rejected');

CREATE TABLE certificate_financial_exceptions (
    exception_id SERIAL PRIMARY KEY,
    admission_id INT NOT NULL REFERENCES admissions(admission_id),        -- the paying admission
    outstanding_amount NUMERIC(12, 2) NOT NULL CHECK (outstanding_amount >= 0),
    certificate_types certificate_type[] NOT NULL CHECK (cardinality(certificate_types) > 0),
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,

    CONSTRAINT financial_exceptions_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT financial_exceptions_independent CHECK (decided_by IS NULL OR decided_by <> requested_by)
);

CREATE UNIQUE INDEX financial_exceptions_one_pending ON certificate_financial_exceptions (admission_id) WHERE status = 'Pending';

-- ---------------------------------------------------------------------------
-- Certificate change requests (Module 22 §7, §8): a correction or reissue (Academic Coordinator asks, Branch Manager or
-- Super Admin approves), a revocation or a reinstatement (Founder / CEO or Super Admin approves). The approver is never
-- the requester; the current certificate stays valid until the request is approved and applied.
-- ---------------------------------------------------------------------------
CREATE TYPE certificate_request_kind AS ENUM ('Correction', 'Revocation', 'Reinstatement');

CREATE TABLE certificate_change_requests (
    request_id SERIAL PRIMARY KEY,
    certificate_id INT NOT NULL REFERENCES certificates(certificate_id),
    kind certificate_request_kind NOT NULL,
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    evidence TEXT,
    changes JSONB NOT NULL DEFAULT '{}'::jsonb,       -- corrected fields, e.g. {"holder_name": {"from": "...", "to": "..."}}
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,
    resulting_certificate_id INT REFERENCES certificates(certificate_id),   -- the new version a correction issued

    CONSTRAINT certificate_requests_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL)),
    CONSTRAINT certificate_requests_independent CHECK (decided_by IS NULL OR decided_by <> requested_by),
    CONSTRAINT certificate_requests_evidence CHECK (kind = 'Correction' OR length(btrim(COALESCE(evidence, ''))) > 0)
);

CREATE UNIQUE INDEX certificate_requests_one_pending ON certificate_change_requests (certificate_id) WHERE status = 'Pending';

-- ---------------------------------------------------------------------------
-- Status history: every status change of a register entry, so a revoked interval survives a reinstatement
-- ---------------------------------------------------------------------------
CREATE TABLE certificate_status_history (
    history_id BIGSERIAL PRIMARY KEY,
    certificate_id INT NOT NULL REFERENCES certificates(certificate_id) ON DELETE CASCADE,  -- an unnumbered draft can be deleted
    from_status certificate_status,
    to_status certificate_status NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX certificate_status_history_idx ON certificate_status_history (certificate_id, changed_at);

CREATE OR REPLACE FUNCTION certificates_record_status() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO certificate_status_history (certificate_id, from_status, to_status)
        VALUES (NEW.certificate_id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status);
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_certificates_status_history
    AFTER INSERT OR UPDATE OF status ON certificates
    FOR EACH ROW EXECUTE FUNCTION certificates_record_status();

INSERT INTO certificate_status_history (certificate_id, from_status, to_status, changed_at)
SELECT certificate_id, NULL, status, updated_at FROM certificates;

-- ---------------------------------------------------------------------------
-- Reinstatement: Revoked -> Issued keeps the number and the original issue date (no new number is allocated)
-- ---------------------------------------------------------------------------
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
        ('Issued', 'Revoked'),
        ('Revoked', 'Issued')
    )) THEN
        RAISE EXCEPTION 'A certificate cannot move from % to %', OLD.status, NEW.status;
    END IF;

    IF OLD.status = 'Not Yet Eligible' THEN
        PERFORM check_certificate_eligibility(NEW.enrolment_id);
    END IF;
    IF NEW.status = 'Issued' AND OLD.status = 'Approved for Issue' THEN
        NEW.certificate_number = next_certificate_number();
        NEW.issue_date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- AI controls (Module 24 §11): the Super Admin switches an assistant off for an audience (company-wide or one branch);
-- the Founder / CEO can switch all AI off company-wide. Restoring records who checked what.
-- ---------------------------------------------------------------------------
CREATE TABLE ai_feature_controls (
    control_id SERIAL PRIMARY KEY,
    audience VARCHAR(10) NOT NULL CHECK (audience IN ('All', 'Student', 'Staff')),
    branch_id INT REFERENCES branches(branch_id),                          -- NULL = company-wide
    reason TEXT NOT NULL CHECK (length(btrim(reason)) > 0),
    remediation TEXT,                                                       -- what is being done about it
    disabled_by INT NOT NULL REFERENCES users(user_id),
    disabled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    restored_by INT REFERENCES users(user_id),
    restored_at TIMESTAMPTZ,
    restoration_note TEXT,                                                  -- the checks that passed before restoring

    CONSTRAINT ai_controls_restored CHECK ((restored_at IS NULL) = (restored_by IS NULL)),
    CONSTRAINT ai_controls_restoration_note CHECK (restored_at IS NULL OR length(btrim(COALESCE(restoration_note, ''))) > 0),
    CONSTRAINT ai_controls_company_wide_all CHECK (audience <> 'All' OR branch_id IS NULL)
);

CREATE INDEX ai_controls_active_idx ON ai_feature_controls (audience, branch_id) WHERE restored_at IS NULL;

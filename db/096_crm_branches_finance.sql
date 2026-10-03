-- 096: two CRM events agreed in round 2 (owner decisions D3 and D4; docs/CRM_INTEGRATION.md §5)
-- Depends on: 001 (branches), 003 (crm_events)
--   BranchUpserted: the CRM creates and updates branches; the LMS no longer needs one made by hand first
--   BranchFinanceSnapshot: per-branch finance figures for the dashboards (collections and paid Admissions against
--   target, overdue amounts, payment verifications, follow-ups), pushed by the CRM every 15 minutes

ALTER TABLE crm_events DROP CONSTRAINT crm_events_event_type_check;
ALTER TABLE crm_events ADD CONSTRAINT crm_events_event_type_check CHECK (event_type IN (
    'CourseUpserted', 'AdmissionQualified', 'AdmissionUpdated', 'AdmissionCancelled', 'FinanceSummaryUpdated',
    'BranchUpserted', 'BranchFinanceSnapshot'));

-- BranchUpserted is versioned per branch (`branch:<code>` on the CRM). 0 = made in the LMS, never sent by the CRM.
ALTER TABLE branches ADD COLUMN source_version INT NOT NULL DEFAULT 0 CHECK (source_version >= 0);

-- ---------------------------------------------------------------------------
-- The CRM's latest finance figures per branch. CRM-authoritative and read-only in the LMS: every snapshot replaces the
-- previous one. A branch without a row shows its figures as Not Configured, never 0.
-- ---------------------------------------------------------------------------
CREATE TABLE branch_finance_snapshots (
    branch_id INT PRIMARY KEY REFERENCES branches(branch_id),
    source_version INT NOT NULL CHECK (source_version >= 1),
    as_of TIMESTAMPTZ NOT NULL,                     -- when the CRM computed the figures
    -- The CRM's Approved target period; NULL when the branch has no approved target
    period_label VARCHAR(50),
    period_start DATE,
    period_end DATE,
    collections_verified NUMERIC(14, 2) NOT NULL CHECK (collections_verified >= 0),
    collections_target NUMERIC(14, 2) CHECK (collections_target >= 0),
    paid_admissions INT NOT NULL CHECK (paid_admissions >= 0),
    paid_admissions_target INT CHECK (paid_admissions_target >= 0),
    overdue_amount NUMERIC(14, 2) NOT NULL CHECK (overdue_amount >= 0),
    overdue_count INT NOT NULL CHECK (overdue_count >= 0),
    overdue_by_age_band JSONB NOT NULL DEFAULT '[]',  -- [{band, amount, count}]
    verifications_pending INT NOT NULL CHECK (verifications_pending >= 0),
    verifications_pending_amount NUMERIC(14, 2) NOT NULL CHECK (verifications_pending_amount >= 0),
    verifications_overdue INT NOT NULL CHECK (verifications_overdue >= 0),  -- past the CRM's verification SLA
    verifications_oldest_at TIMESTAMPTZ,
    followups_overdue INT NOT NULL CHECK (followups_overdue >= 0),
    broken_promises INT NOT NULL CHECK (broken_promises >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT branch_finance_period CHECK ((period_start IS NULL) = (period_end IS NULL)
                                           AND (period_end IS NULL OR period_end >= period_start)),
    CONSTRAINT branch_finance_targets_need_period CHECK (period_start IS NOT NULL
                                                        OR (collections_target IS NULL AND paid_admissions_target IS NULL))
);

CREATE TRIGGER trg_branch_finance_snapshots_updated_at
    BEFORE UPDATE ON branch_finance_snapshots
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

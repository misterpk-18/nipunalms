-- 101: phase 4 of the gap fix plan — the Nipuna Academic Calendar and working days (docs/GAP_FIX_PLAN.md, docs/GAPS.md)
-- Depends on: 001 (branches, users, app_settings), 100 (approval_status)
--   Company holidays (set by the Founder / CEO or Super Admin) and branch closures (approved by the Branch Manager) make up
--   the published calendar (G064). Working-day targets (allocation deadline G063, next-day attendance alert G091, review
--   clocks) count only days that are working weekdays and not closed. Module 15 §9: Sunday, weekends and bank holidays are
--   not assumed closed, so every weekday is a working day until `working_weekdays` says otherwise.

CREATE TYPE calendar_closure_kind AS ENUM ('Company Holiday', 'Branch Closure');

CREATE TABLE calendar_closures (
    closure_id SERIAL PRIMARY KEY,
    kind calendar_closure_kind NOT NULL,
    branch_id INT REFERENCES branches(branch_id),                    -- NULL for a company holiday
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    title VARCHAR(200) NOT NULL CHECK (length(btrim(title)) > 0),
    reason TEXT,
    status approval_status NOT NULL DEFAULT 'Pending',
    requested_by INT NOT NULL REFERENCES users(user_id),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_by INT REFERENCES users(user_id),
    decided_at TIMESTAMPTZ,
    decision_note TEXT,

    CONSTRAINT calendar_closures_scope CHECK ((kind = 'Company Holiday') = (branch_id IS NULL)),
    CONSTRAINT calendar_closures_dates CHECK (ends_on >= starts_on AND ends_on - starts_on <= 62),
    CONSTRAINT calendar_closures_decided CHECK ((status = 'Pending') = (decided_by IS NULL AND decided_at IS NULL))
);

CREATE INDEX calendar_closures_dates_idx ON calendar_closures (starts_on, ends_on) WHERE status = 'Approved';

INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('working_weekdays', '[1, 2, 3, 4, 5, 6, 7]', 'ISO weekdays (1 = Mon … 7 = Sun) that count as working days; closures in the Academic Calendar are excluded too'),
    ('attendance_unconfirmed_lookback_days', '14', 'How far back the attendance-unconfirmed job looks for delivered classes still missing attendance')
ON CONFLICT (setting_key) DO NOTHING;

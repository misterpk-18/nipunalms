-- 114: UX phase U16, Founder: "Approve & activate" with an optional activation date (docs/UX_PLAN.md)
-- Depends on: 002 (curriculum_versions)
--   curriculum_versions.activate_on: the day an Approved version becomes the Active one. Set when the approver picks a future date
--   with the approval; the background job `curriculum-activate` (services/curriculum.activate_due) activates it on that day and
--   clears the date. A version approved with today's date (or none) is activated at once and never carries a date. Only an Approved
--   version can hold one.
-- Gap fix phase 7 starts at db/115.

ALTER TABLE curriculum_versions
    ADD COLUMN activate_on DATE,
    ADD CONSTRAINT curriculum_versions_activate_on_approved CHECK (activate_on IS NULL OR status = 'Approved');

CREATE INDEX curriculum_versions_due_idx ON curriculum_versions (activate_on) WHERE activate_on IS NOT NULL;

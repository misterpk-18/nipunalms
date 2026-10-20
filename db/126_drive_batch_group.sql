-- 126: Google Workspace integration: a Google Group per batch (docs/GOOGLE_WORKSPACE.md §5.2)
-- Depends on: 125 (google_drive_items)
--   A batch's students are members of one Google Group, and the batch's Drive folder is shared once with that group, instead of
--   with each student. The group's address is kept on the batch's folder row so a later change of Workspace domain cannot orphan it.

ALTER TABLE google_drive_items ADD COLUMN group_email VARCHAR(255);

COMMENT ON COLUMN google_drive_items.group_email IS 'The batch''s Google Group (batch rows only); the students are its members';

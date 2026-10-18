-- Role separation R2 (2/2): the constraint. Depends on 118 (the split must have run first, or this refuses existing data).
--
-- One live role per user. The one exception is Branch Manager, which may hold several live rows, one per branch. Student and
-- Trainer therefore keep exactly one branch on their single row; Super Admin and Founder take no branch (check_role_scope_branch,
-- db/001). "Live" means not revoked; a temporary scope past its expires_at still counts until it is revoked.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
        WHERE s.revoked_at IS NULL
        GROUP BY s.user_id
        HAVING count(*) > 1 AND (count(DISTINCT s.role_id) > 1 OR bool_or(r.role_code <> 'BRANCH_MANAGER'))
    ) THEN
        RAISE EXCEPTION 'Some users still hold more than one live role; run db/118 first';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION check_one_role_per_user() RETURNS trigger AS $$
DECLARE
    v_code TEXT;
    v_clash INT;
BEGIN
    IF NEW.revoked_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    PERFORM 1 FROM users WHERE user_id = NEW.user_id FOR UPDATE;  -- serialise concurrent grants to one person
    SELECT role_code INTO v_code FROM roles WHERE role_id = NEW.role_id;
    SELECT count(*) INTO v_clash
    FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
    WHERE s.user_id = NEW.user_id AND s.revoked_at IS NULL AND s.scope_id IS DISTINCT FROM NEW.scope_id
      AND NOT (v_code = 'BRANCH_MANAGER' AND r.role_code = 'BRANCH_MANAGER');
    IF v_clash > 0 THEN
        RAISE EXCEPTION 'One role per account: this user already holds a live role (only Branch Manager may hold several branches)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_role_scopes_one_role
    BEFORE INSERT OR UPDATE OF user_id, role_id, branch_id, revoked_at ON user_role_scopes
    FOR EACH ROW EXECUTE FUNCTION check_one_role_per_user();

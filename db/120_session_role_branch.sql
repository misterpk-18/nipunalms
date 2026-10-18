-- Role separation R3: the session carries the one role it signed in as and, for a Branch Manager, the branch picked at sign-in.
--
-- role_code  the account's single role, set when the session starts (db/119 guarantees there is one).
-- branch_id  a Branch Manager's branch for this session. NULL while a Branch Manager with several branches has not picked yet
--            (the session then only reaches /auth/branch, /auth/me and /auth/logout); NULL for every other role (a Student or
--            Trainer's branch is read from their scope, Super Admin and Founder are company-wide).
-- Sessions that started before this migration are given the role and branch of the account's single live scope. A Branch Manager
-- with several branches cannot be resolved, so that session is revoked and the person signs in again and picks a branch.

ALTER TABLE user_sessions
    ADD COLUMN role_code VARCHAR(50) REFERENCES roles(role_code),
    ADD COLUMN branch_id INT REFERENCES branches(branch_id);

UPDATE user_sessions us
SET role_code = x.role_code,
    branch_id = CASE WHEN x.role_code = 'BRANCH_MANAGER' THEN x.branch_id END
FROM (
    SELECT s.user_id, min(r.role_code) AS role_code, min(s.branch_id) AS branch_id
    FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
    WHERE s.revoked_at IS NULL
    GROUP BY s.user_id
    HAVING count(*) = 1
) x
WHERE x.user_id = us.user_id AND us.revoked_at IS NULL;

UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP, revoke_reason = 'role separation: sign in again'
WHERE revoked_at IS NULL AND role_code IS NULL;

DROP VIEW active_sessions;
CREATE VIEW active_sessions AS
SELECT s.*,
       s.reauthenticated_at IS NOT NULL AND s.reauthenticated_at > CURRENT_TIMESTAMP - make_interval(mins =>
           COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = 'fresh_auth_minutes'), 15))
           AS has_fresh_auth
FROM user_sessions s
WHERE s.revoked_at IS NULL
  AND s.expires_at > CURRENT_TIMESTAMP
  AND s.last_seen_at > CURRENT_TIMESTAMP - make_interval(mins =>
        COALESCE((SELECT (setting_value #>> '{}')::INT FROM app_settings WHERE setting_key = 'session_idle_minutes'), 30));

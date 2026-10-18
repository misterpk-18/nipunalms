-- Role separation R2 (1/2): one role per account.
-- Depends on: 001 (users, roles, user_role_scopes, user_sessions), 108 (staff_invites).
--
-- Every user holding more than one live role scope is split. The highest role (Founder > Super Admin > Branch Manager >
-- Trainer > Student) stays on the existing account; each other role gets a new account with its own email
-- (localpart.<role>@domain, numbered if taken), no password and no sign-in until the person is handed an activation link.
-- The non-primary scopes are moved onto the new account (revoked on the old one, same grant re-created on the new one) and the
-- sessions of every split user end. Each new account is recorded in split_account_handouts, which the hand-out page reads.
-- The one-time activation link is NOT created here: only the SHA-256 of a token is ever stored, so a link made in SQL could
-- never be shown. The hand-out page issues the link (staff_invites) when the Super Admin or Founder asks for it.
-- Branch Manager is the only role that may hold several branches, so all of a user's Branch Manager scopes move together;
-- for any other role holding several branches each extra scope gets its own account.
-- The constraint that forbids a second role is db/119, applied after this file.

CREATE TABLE split_account_handouts (
    handout_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE REFERENCES users(user_id),         -- the new account
    split_from_user_id INT NOT NULL REFERENCES users(user_id),     -- the account it was split off
    role_id INT NOT NULL REFERENCES roles(role_id),
    branch_id INT REFERENCES branches(branch_id),                  -- NULL for company-wide roles; first branch for a multi-branch Branch Manager
    invite_id INT REFERENCES staff_invites(invite_id),             -- the latest activation link issued for it (NULL until issued)
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    handed_out_at TIMESTAMPTZ,
    handed_out_by INT REFERENCES users(user_id)
);
CREATE INDEX split_account_handouts_pending_idx ON split_account_handouts (created_at) WHERE handed_out_at IS NULL;

CREATE OR REPLACE FUNCTION role_separation_rank(p_code TEXT) RETURNS INT AS $$
    SELECT CASE p_code WHEN 'FOUNDER_CEO' THEN 5 WHEN 'SUPER_ADMIN' THEN 4 WHEN 'BRANCH_MANAGER' THEN 3
                       WHEN 'TRAINER' THEN 2 WHEN 'STUDENT' THEN 1 ELSE 0 END;
$$ LANGUAGE sql IMMUTABLE;

DO $$
DECLARE
    u RECORD;
    g RECORD;
    v_primary_role INT;
    v_primary_scope INT;
    v_new_user INT;
    v_local TEXT;
    v_domain TEXT;
    v_suffix TEXT;
    v_email TEXT;
    v_n INT;
    v_student INT;
BEGIN
    FOR u IN
        SELECT s.user_id FROM user_role_scopes s WHERE s.revoked_at IS NULL
        GROUP BY s.user_id
        HAVING count(*) > 1
           AND (count(DISTINCT s.role_id) > 1
                OR EXISTS (SELECT 1 FROM user_role_scopes x JOIN roles xr ON xr.role_id = x.role_id
                           WHERE x.user_id = s.user_id AND x.revoked_at IS NULL AND xr.role_code <> 'BRANCH_MANAGER'))
        ORDER BY s.user_id
    LOOP
        -- the scope that stays: highest role, then lowest scope id
        SELECT s.role_id, s.scope_id INTO v_primary_role, v_primary_scope
        FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
        WHERE s.user_id = u.user_id AND s.revoked_at IS NULL
        ORDER BY role_separation_rank(r.role_code) DESC, s.scope_id LIMIT 1;

        -- every other (role) group moves: Branch Manager as one group, other roles one scope per account
        FOR g IN
            SELECT r.role_id, r.role_code, s.scope_id, s.branch_id, s.granted_by, s.granted_at, s.expires_at
            FROM user_role_scopes s JOIN roles r ON r.role_id = s.role_id
            WHERE s.user_id = u.user_id AND s.revoked_at IS NULL
              AND NOT (s.role_id = v_primary_role AND (r.role_code = 'BRANCH_MANAGER' OR s.scope_id = v_primary_scope))
            ORDER BY role_separation_rank(r.role_code) DESC, s.scope_id
        LOOP
            -- a further Branch Manager branch joins the account made for the first one
            IF g.role_code = 'BRANCH_MANAGER' THEN
                SELECT h.user_id INTO v_new_user FROM split_account_handouts h
                WHERE h.split_from_user_id = u.user_id AND h.role_id = g.role_id;
            ELSE
                v_new_user := NULL;
            END IF;

            IF v_new_user IS NULL THEN
                v_suffix := CASE g.role_code WHEN 'FOUNDER_CEO' THEN 'founder' WHEN 'SUPER_ADMIN' THEN 'superadmin'
                                             WHEN 'BRANCH_MANAGER' THEN 'branchmanager' WHEN 'TRAINER' THEN 'trainer'
                                             WHEN 'STUDENT' THEN 'student' ELSE lower(g.role_code) END;
                SELECT split_part(email, '@', 1), split_part(email, '@', 2) INTO v_local, v_domain FROM users WHERE user_id = u.user_id;
                IF v_domain = '' THEN v_domain := 'nipunatechnologies.com'; END IF;
                IF v_local = '' THEN v_local := 'user' || u.user_id; END IF;
                v_email := v_local || '.' || v_suffix || '@' || v_domain;
                v_n := 1;
                WHILE EXISTS (SELECT 1 FROM users WHERE lower(email) = lower(v_email)) LOOP
                    v_n := v_n + 1;
                    v_email := v_local || '.' || v_suffix || v_n || '@' || v_domain;
                END LOOP;

                INSERT INTO users (full_name, email, phone, password_hash, is_active, must_change_password)
                SELECT full_name, v_email, phone, NULL, is_active, TRUE FROM users WHERE user_id = u.user_id
                RETURNING user_id INTO v_new_user;

                IF g.role_code = 'STUDENT' THEN  -- the one LMS login of the student follows the Student role
                    SELECT student_id INTO v_student FROM users WHERE user_id = u.user_id;
                    IF v_student IS NOT NULL THEN
                        UPDATE users SET student_id = NULL WHERE user_id = u.user_id;
                        UPDATE users SET student_id = v_student WHERE user_id = v_new_user;
                    END IF;
                END IF;

                INSERT INTO split_account_handouts (user_id, split_from_user_id, role_id, branch_id)
                VALUES (v_new_user, u.user_id, g.role_id, g.branch_id);
            END IF;

            UPDATE user_role_scopes SET revoked_at = now() WHERE scope_id = g.scope_id;
            INSERT INTO user_role_scopes (user_id, role_id, branch_id, granted_by, granted_at, expires_at)
            VALUES (v_new_user, g.role_id, g.branch_id, g.granted_by, g.granted_at, g.expires_at);
        END LOOP;

        UPDATE user_sessions SET revoked_at = now(), revoke_reason = 'account split by role separation'
        WHERE user_id = u.user_id AND revoked_at IS NULL;
    END LOOP;
END $$;

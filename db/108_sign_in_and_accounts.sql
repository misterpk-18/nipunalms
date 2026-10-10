-- 108: UX phase U7, sign-in and accounts (docs/UX_PLAN.md)
-- Depends on: 001 (users), 107 (whatsapp_outbox)
--   password_reset_codes: the 6-digit code a person asks for on the sign-in page. Only its hash is stored; single use,
--     10 minutes, at most 5 wrong tries per code, at most 5 codes per person per hour (enforced in the service).
--   staff_invites: the one-time link that replaces a spoken temporary password for new staff (student links stay in
--     student_activations). Only the token's hash is stored.
-- Gap fix phase 7 starts at db/110 (UX phase U8 takes 109).

CREATE TABLE password_reset_codes (
    code_id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    code_hash VARCHAR(64) NOT NULL,                 -- SHA-256 of "<user id>:<code>"
    expires_at TIMESTAMPTZ NOT NULL,
    wrong_attempts SMALLINT NOT NULL DEFAULT 0,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX password_reset_codes_user_idx ON password_reset_codes (user_id, created_at DESC);

CREATE TABLE staff_invites (
    invite_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    token_hash VARCHAR(64) UNIQUE NOT NULL,         -- SHA-256 of the token
    issued_by INT REFERENCES users(user_id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,                         -- replaced by a newer invite
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- At most one outstanding (unused, unrevoked) invite per person
CREATE UNIQUE INDEX staff_invites_one_outstanding ON staff_invites (user_id) WHERE used_at IS NULL AND revoked_at IS NULL;

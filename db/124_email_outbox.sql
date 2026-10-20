-- 124: Google Workspace integration, second slice (docs/GOOGLE_WORKSPACE.md §5.3): the email outbox
-- Depends on: 001 (users, branches, set_updated_at), 123 (Google Workspace)
--   Like whatsapp_outbox: a message is written in the same transaction as the change it reports, and the `email-send` job
--   sends it through Gmail after the commit. A message that cannot or should not go out is kept as Skipped with the reason.
--   `has_secret` rows carry a sign-in link; the body is blanked once the message is done.

CREATE TYPE email_status AS ENUM ('Queued', 'Sent', 'Failed', 'Skipped');

CREATE TABLE email_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    template VARCHAR(60) NOT NULL,
    recipient_user_id INTEGER REFERENCES users (user_id),
    branch_id INTEGER REFERENCES branches (branch_id),      -- whose mailbox the message comes from
    to_email VARCHAR(255),
    subject VARCHAR(200) NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    has_secret BOOLEAN NOT NULL DEFAULT FALSE,
    dedupe_key VARCHAR(200) NOT NULL UNIQUE,
    occurred_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    status email_status NOT NULL DEFAULT 'Queued',
    status_note TEXT,
    attempts SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    attempt_started_at TIMESTAMPTZ,                          -- set while a send is in progress; an old one is taken again
    sent_at TIMESTAMPTZ,
    provider_message_id VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX email_outbox_due_idx ON email_outbox (next_attempt_at NULLS FIRST, outbox_id) WHERE status = 'Queued';

CREATE TRIGGER trg_email_outbox_updated_at
    BEFORE UPDATE ON email_outbox
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

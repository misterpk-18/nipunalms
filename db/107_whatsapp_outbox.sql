-- 107: UX phase U6, WhatsApp through the CRM (docs/UX_PLAN.md, CRM_INTEGRATION.md round 6)
-- Depends on: 001 (users, app_settings), 003 (students)
--   The LMS never calls Pinbot. A message is written here in the same transaction as the change it reports, and the
--   `whatsapp-send` job posts it to the CRM's POST /lms/whatsapp after the commit. The CRM applies its own switch, test-number
--   list, consent and backoff, and sends it on the one company number. Nothing is resent on a timeout.
-- Gap fix phase 7 starts at db/108 (UX phase U7 takes 108).

CREATE TYPE whatsapp_status AS ENUM ('Queued', 'Sent', 'Failed', 'Skipped');

CREATE TABLE whatsapp_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    recipient_user_id INT REFERENCES users(user_id),
    lms_user_id VARCHAR(100),                       -- the student's LMS id, for the CRM to find the person
    to_number VARCHAR(20),                          -- digits with country code, no '+'
    params JSONB NOT NULL DEFAULT '[]',             -- the body values {{1}}..{{n}}, in order
    button_params JSONB NOT NULL DEFAULT '[]',      -- the URL-button value, when the template has one
    dedupe_key VARCHAR(200) NOT NULL UNIQUE,        -- one message per event and person, however often it is processed
    occurred_at TIMESTAMPTZ NOT NULL,               -- when the thing happened
    expires_at TIMESTAMPTZ NOT NULL,                -- after this the message is stale and is not sent
    status whatsapp_status NOT NULL DEFAULT 'Queued',
    status_note TEXT,
    provider_message_id VARCHAR(200),
    attempts SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    attempt_started_at TIMESTAMPTZ,                 -- set while a post is in flight; a row stuck here is never auto-resent
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT whatsapp_outbox_sent_has_time CHECK (status <> 'Sent' OR sent_at IS NOT NULL),
    CONSTRAINT whatsapp_outbox_note CHECK (status NOT IN ('Failed', 'Skipped') OR status_note IS NOT NULL)
);

CREATE INDEX whatsapp_outbox_due_idx ON whatsapp_outbox (outbox_id) WHERE status = 'Queued';
CREATE INDEX whatsapp_outbox_recipient_idx ON whatsapp_outbox (recipient_user_id, created_at DESC);

CREATE TRIGGER trg_whatsapp_outbox_updated_at
    BEFORE UPDATE ON whatsapp_outbox
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Both start off: the code ships switched off until the CRM endpoint exists and the owner has the templates approved
INSERT INTO app_settings (setting_key, setting_value, description) VALUES
    ('whatsapp_enabled', 'false', 'Super Admin switch: true lets the LMS hand WhatsApp messages to the CRM'),
    ('whatsapp_approved_templates', '[]', 'Names of the LMS WhatsApp templates Meta has approved in Pinbot; only these are sent'),
    ('whatsapp_max_age_hours', '48', 'A WhatsApp message about something older than this is not sent');

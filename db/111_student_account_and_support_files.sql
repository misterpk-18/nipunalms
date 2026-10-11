-- 111: UX phase U11, student Career, Ask Nipuna, Support and My Account (docs/UX_PLAN.md)
-- Depends on: 001 (users, branches), 050 (support_requests, support_messages)
--   support_attachments: a file a student or a colleague attaches to a message of a support request. The file itself sits on disk
--     under UPLOAD_DIR/support (like CV files); this row says whose it is. The checks (type, size, who may download) are in the service.
--   email_change_codes: the 6-digit code that confirms a student's new email address. Only its hash is stored; single use,
--     10 minutes, burned after 5 wrong tries, at most 5 per person per hour (service rule, like password_reset_codes).
--   branches.payment_instructions: how and where a student pays at that branch (free text shown on Fees & Receipts).
-- Gap fix phase 7 starts at db/112.

CREATE TABLE support_attachments (
    attachment_id SERIAL PRIMARY KEY,
    support_request_id INT NOT NULL REFERENCES support_requests(support_request_id),
    support_message_id BIGINT NOT NULL REFERENCES support_messages(support_message_id),
    uploaded_by_user_id INT NOT NULL REFERENCES users(user_id),
    file_path VARCHAR(500) NOT NULL,                -- relative to UPLOAD_DIR
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    file_size_bytes INT NOT NULL CHECK (file_size_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX support_attachments_request_idx ON support_attachments (support_request_id);
CREATE INDEX support_attachments_message_idx ON support_attachments (support_message_id);

CREATE TABLE email_change_codes (
    code_id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    new_email VARCHAR(255) NOT NULL,
    code_hash VARCHAR(64) NOT NULL,                 -- SHA-256 of "<user id>:<new email>:<code>"
    expires_at TIMESTAMPTZ NOT NULL,
    wrong_attempts SMALLINT NOT NULL DEFAULT 0,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX email_change_codes_user_idx ON email_change_codes (user_id, created_at DESC);

ALTER TABLE branches ADD COLUMN payment_instructions TEXT;

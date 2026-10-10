-- 110: CRM round 6 reply, WhatsappStatusUpdated (nipuna crm-docs/CRM_WHATSAPP_ROUND6_REPLY.md §3)
-- Depends on: 107 (whatsapp_outbox), 104 (crm_events_event_type_check)
--   The CRM tells the LMS what happened to a message after it answered Queued: Sent, Delivered, Read, Failed or Skipped,
--   one event per change, versioned per dedupe key. The LMS keeps the latest delivery state beside its own status.
-- Gap fix phase 7 starts at db/111.

ALTER TABLE crm_events DROP CONSTRAINT crm_events_event_type_check;
ALTER TABLE crm_events ADD CONSTRAINT crm_events_event_type_check CHECK (event_type IN (
    'CourseUpserted', 'AdmissionQualified', 'AdmissionUpdated', 'AdmissionCancelled', 'FinanceSummaryUpdated',
    'BranchUpserted', 'BranchFinanceSnapshot', 'WhatsappStatusUpdated')) NOT VALID;

ALTER TABLE whatsapp_outbox
    ADD COLUMN crm_outbox_id INT,                                   -- the CRM's id for the message
    ADD COLUMN delivery_status VARCHAR(20)
        CHECK (delivery_status IN ('Sent', 'Delivered', 'Read', 'Failed', 'Skipped')),
    ADD COLUMN delivery_version INT NOT NULL DEFAULT 0,             -- last WhatsappStatusUpdated source_version applied
    ADD COLUMN delivery_at TIMESTAMPTZ;                             -- when the provider reported it

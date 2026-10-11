-- 113: UX phase U15, access extensions beyond the Branch Manager's limit (docs/UX_PLAN.md)
-- Depends on: 001 (users), 020 (access_extension_requests)
--   A request made after the second anniversary is a Founder / CEO (or Super Admin) decision. The Branch Manager of the service
--   branch does not decide it, but adds a recommendation (approve or reject, a note and, for approve, the end date they suggest).
--   Saving the recommendation routes the request to the Founder's inbox: `recommended_at IS NOT NULL` on a Pending request with
--   `needs_exception` is the routing mark that U16's GET /founder/inbox reads. Routine requests (within the limit) never use it.
-- Gap fix phase 7 starts at db/114.

ALTER TABLE access_extension_requests
    ADD COLUMN recommended_decision VARCHAR(10) CHECK (recommended_decision IN ('approve', 'reject')),
    ADD COLUMN recommendation TEXT,
    ADD COLUMN recommended_expiry DATE,
    ADD COLUMN recommended_by INT REFERENCES users(user_id),
    ADD COLUMN recommended_at TIMESTAMPTZ,
    ADD CONSTRAINT access_extension_recommendation_complete CHECK (
        (recommended_at IS NULL) = (recommended_by IS NULL) AND (recommended_at IS NULL) = (recommended_decision IS NULL)),
    ADD CONSTRAINT access_extension_recommendation_exception_only CHECK (recommended_at IS NULL OR needs_exception),
    ADD CONSTRAINT access_extension_recommendation_note CHECK (
        recommended_at IS NULL OR coalesce(length(btrim(recommendation)), 0) > 0),
    ADD CONSTRAINT access_extension_recommended_expiry CHECK (
        recommended_expiry IS NULL OR (recommended_decision = 'approve' AND recommended_expiry > original_expiry));

CREATE INDEX access_extension_founder_idx ON access_extension_requests (recommended_at)
    WHERE status = 'Pending' AND needs_exception AND recommended_at IS NOT NULL;

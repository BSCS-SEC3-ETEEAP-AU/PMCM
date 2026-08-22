-- Account assistance requests submitted from the unauthenticated login page.
-- Run once against the Neon PostgreSQL database before deploying the related Flask code.

CREATE TABLE IF NOT EXISTS public.account_assistance_requests (
    id SERIAL PRIMARY KEY,
    request_type VARCHAR(40) NOT NULL,
    requester_name VARCHAR(120) NOT NULL,
    requester_contact VARCHAR(120) NOT NULL,
    message TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'Open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by_user_id INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT account_assistance_requests_status_check CHECK (status IN ('Open', 'Resolved'))
);

CREATE INDEX IF NOT EXISTS ix_account_assistance_requests_status_created
    ON public.account_assistance_requests (status, created_at DESC);

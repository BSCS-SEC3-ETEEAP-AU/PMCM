-- Add requester contact information and completion-notification tracking.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS requester_email VARCHAR(120),
    ADD COLUMN IF NOT EXISTS completion_email_sent_at TIMESTAMP;

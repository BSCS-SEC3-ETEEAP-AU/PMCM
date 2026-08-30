-- Project-level priority used by urgency indicators.
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'Medium';

UPDATE projects
SET priority = 'Medium'
WHERE priority IS NULL OR priority NOT IN ('Low', 'Medium', 'High');

ALTER TABLE projects
ALTER COLUMN priority SET DEFAULT 'Medium';

ALTER TABLE projects
ALTER COLUMN priority SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_projects_priority'
    ) THEN
        ALTER TABLE projects
        ADD CONSTRAINT ck_projects_priority
        CHECK (priority IN ('Low', 'Medium', 'High'));
    END IF;
END $$;

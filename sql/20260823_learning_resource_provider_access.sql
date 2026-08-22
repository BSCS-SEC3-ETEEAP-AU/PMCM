-- Add learning-resource source metadata used by the recommendation module.
-- Existing rows are intentionally left unassigned so actual providers are not fabricated.

ALTER TABLE learning_resources
    ADD COLUMN IF NOT EXISTS provider VARCHAR(120),
    ADD COLUMN IF NOT EXISTS access_type VARCHAR(30);

-- Optional integrity rule for newly maintained data. Existing NULLs remain valid.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_learning_resources_access_type'
    ) THEN
        ALTER TABLE learning_resources
        ADD CONSTRAINT ck_learning_resources_access_type
        CHECK (access_type IS NULL OR access_type IN ('Internal', 'Company Subscription', 'External'));
    END IF;
END $$;

-- Verify:
-- SELECT id, title, provider, access_type, url FROM learning_resources ORDER BY id;

-- Populate existing rows only with VERIFIED sources. Examples:
-- UPDATE learning_resources
-- SET provider = 'LinkedIn Learning', access_type = 'Company Subscription', url = 'https://...'
-- WHERE id = <resource_id>;
--
-- UPDATE learning_resources
-- SET provider = 'Internal Learning Portal', access_type = 'Internal', url = 'https://internal-portal/...';
-- WHERE id = <resource_id>;

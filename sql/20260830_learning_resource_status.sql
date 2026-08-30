ALTER TABLE learning_resources
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE learning_resources
SET is_active = TRUE
WHERE is_active IS NULL;

CREATE INDEX IF NOT EXISTS ix_learning_resources_is_active
    ON learning_resources(is_active);

SELECT id, title, resource_type, provider, is_active
FROM learning_resources
ORDER BY is_active DESC, title;

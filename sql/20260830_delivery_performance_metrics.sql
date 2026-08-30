-- Delivery performance / behavioral metrics support.
-- Adds explicit lifecycle timestamps so completion speed is measured from
-- recorded work history rather than from the generic updated_at timestamp.

ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE projects
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITHOUT TIME ZONE;

-- Historical backfill. For completed tasks created before lifecycle tracking,
-- created_at is the best available estimate of when work began and updated_at
-- is the best available estimate of when the task was completed.
UPDATE tasks
SET started_at = created_at
WHERE started_at IS NULL
  AND status IN ('In Progress', 'In Review', 'Done');

UPDATE tasks
SET completed_at = COALESCE(updated_at, created_at)
WHERE completed_at IS NULL
  AND status = 'Done';

-- If an old completed project has no explicit completion timestamp, use the
-- latest completed-task timestamp first, then its target date as a fallback.
UPDATE projects p
SET completed_at = COALESCE(
    (
        SELECT MAX(t.completed_at)
        FROM tasks t
        WHERE t.project_id = p.id
          AND t.status = 'Done'
          AND t.completed_at IS NOT NULL
    ),
    p.target_date::timestamp,
    p.created_at
)
WHERE p.status = 'Completed'
  AND p.completed_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_tasks_completed_at
    ON tasks(completed_at);

CREATE INDEX IF NOT EXISTS ix_projects_completed_at
    ON projects(completed_at);

-- Verification
SELECT
    COUNT(*) FILTER (WHERE status = 'Done') AS completed_tasks,
    COUNT(*) FILTER (WHERE status = 'Done' AND completed_at IS NOT NULL) AS completed_tasks_with_timestamp,
    COUNT(*) FILTER (WHERE status = 'Done' AND started_at IS NOT NULL) AS completed_tasks_with_start
FROM tasks;

SELECT
    name,
    status,
    start_date,
    target_date,
    completed_at
FROM projects
WHERE status = 'Completed'
ORDER BY completed_at DESC NULLS LAST;

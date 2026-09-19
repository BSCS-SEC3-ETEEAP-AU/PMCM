-- Employee task-status changes require project-manager approval.
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS status_change_requested_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS status_change_requested_by INTEGER REFERENCES employees(id),
    ADD COLUMN IF NOT EXISTS status_change_requested_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_tasks_status_change_requested
    ON tasks(status_change_requested_status)
    WHERE status_change_requested_status IS NOT NULL;

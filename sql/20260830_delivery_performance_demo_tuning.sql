-- Demo-data tuning for the Delivery Performance report.
-- Purpose:
--   1) Replace implausible minute-level historical durations with realistic work durations.
--   2) Keep the original task count/status/assignee relationships intact.
--   3) Introduce two late completed tasks so the on-time rate is believable rather than 100%.
--
-- This script only adjusts lifecycle timestamps and due dates of existing completed demo tasks.
-- It does not create completed tasks or change task ownership/status.

BEGIN;

-- Make sure every completed, assigned demo task has a due date so deadline reliability
-- can be measured. Existing due dates are preserved.
UPDATE tasks
SET due_date = COALESCE(
    due_date,
    COALESCE(completed_at, updated_at, created_at)::date + 1
)
WHERE status = 'Done'
  AND assignee_id IS NOT NULL;

-- Give completed tasks realistic durations by employee. Existing task creation time is
-- preserved; started_at becomes the work-start record used by the report. Completion is
-- placed around the task's existing due date so the historical calendar remains familiar.
-- Exactly two tasks are intentionally late: Maria Santos' first completed task and
-- Anna Reyes' first completed task.
WITH completed_demo AS (
    SELECT
        t.id,
        t.due_date,
        e.full_name,
        ROW_NUMBER() OVER (
            PARTITION BY e.id
            ORDER BY t.due_date NULLS LAST, t.id
        ) AS rn
    FROM tasks t
    JOIN employees e ON e.id = t.assignee_id
    WHERE t.status = 'Done'
      AND t.assignee_id IS NOT NULL
), tuned AS (
    SELECT
        id,
        full_name,
        rn,
        CASE
            WHEN (full_name = 'Maria Santos' AND rn = 1)
              OR (full_name = 'Anna Reyes' AND rn = 1)
                THEN due_date::timestamp + interval '1 day 16 hours'
            ELSE due_date::timestamp - interval '1 day' + interval '16 hours'
        END AS new_completed_at,
        CASE
            WHEN full_name = 'Maria Santos' THEN 48 + ((rn - 1) * 12)::numeric
            WHEN full_name = 'Paolo Diaz' THEN 96 + ((rn - 1) * 14)::numeric
            WHEN full_name = 'Anna Reyes' THEN 120 + ((rn - 1) * 19.2)::numeric
            WHEN full_name = 'Mark Lim' THEN 76.8
            WHEN full_name = 'Kevin Ramos' THEN 88.8
            WHEN full_name = 'Nina Velasco' THEN 98.4
            WHEN full_name = 'Liza Torres' THEN 180
            ELSE 96 + ((rn - 1) * 8)::numeric
        END AS duration_hours
    FROM completed_demo
)
UPDATE tasks t
SET
    completed_at = tuned.new_completed_at,
    started_at = tuned.new_completed_at - (tuned.duration_hours * interval '1 hour'),
    updated_at = tuned.new_completed_at
FROM tuned
WHERE t.id = tuned.id;

COMMIT;

-- Verification: this should now show realistic multi-day averages. Employees with only
-- one completed task remain visible in the report but are labeled Limited Sample.
WITH employee_metrics AS (
    SELECT
        e.full_name,
        COUNT(*) AS completed_tasks,
        ROUND(AVG(EXTRACT(EPOCH FROM (t.completed_at - t.started_at)) / 86400.0), 1) AS avg_days,
        COUNT(*) FILTER (WHERE t.completed_at::date <= t.due_date) AS on_time,
        COUNT(*) FILTER (WHERE t.completed_at::date > t.due_date) AS late
    FROM tasks t
    JOIN employees e ON e.id = t.assignee_id
    WHERE t.status = 'Done'
      AND t.started_at IS NOT NULL
      AND t.completed_at IS NOT NULL
      AND t.due_date IS NOT NULL
    GROUP BY e.id, e.full_name
)
SELECT
    full_name,
    completed_tasks,
    avg_days,
    on_time,
    late,
    ROUND(100.0 * on_time / NULLIF(on_time + late, 0)) AS on_time_rate,
    CASE WHEN completed_tasks >= 2 THEN 'Ranked' ELSE 'Limited Sample' END AS ranking_status
FROM employee_metrics
ORDER BY
    CASE WHEN completed_tasks >= 2 THEN 0 ELSE 1 END,
    avg_days,
    full_name;

SELECT
    COUNT(*) AS completed_tasks_with_due_dates,
    COUNT(*) FILTER (WHERE completed_at::date <= due_date) AS on_time,
    COUNT(*) FILTER (WHERE completed_at::date > due_date) AS late,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE completed_at::date <= due_date)
        / NULLIF(COUNT(*), 0)
    ) AS overall_on_time_rate
FROM tasks
WHERE status = 'Done'
  AND assignee_id IS NOT NULL
  AND completed_at IS NOT NULL
  AND due_date IS NOT NULL;

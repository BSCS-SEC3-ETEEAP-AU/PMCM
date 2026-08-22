-- Give Administrator / Manager accounts their own Employee competency identity.
-- Roles continue to control permissions; Employee rows hold personal competency records.
-- Safe to re-run: existing matching links/assessments are preserved.

BEGIN;

-- Remove legacy demo links where a privileged account was attached to another person's profile.
UPDATE employees e
SET user_id = NULL
FROM users u
WHERE e.user_id = u.id
  AND u.role IN ('admin', 'manager')
  AND LOWER(TRIM(e.full_name)) <> LOWER(TRIM(u.full_name));

-- If a matching employee profile already exists by name, link it to the account.
UPDATE employees e
SET user_id = u.id,
    position = COALESCE(u.position, e.position),
    work_mode = COALESCE(u.work_mode, e.work_mode)
FROM users u
WHERE u.role IN ('admin', 'manager')
  AND LOWER(TRIM(e.full_name)) = LOWER(TRIM(u.full_name))
  AND (e.user_id IS NULL OR e.user_id = u.id);

-- Create a personal Employee profile for any privileged account that still has none.
INSERT INTO employees (user_id, full_name, position, team, work_mode, created_at)
SELECT u.id,
       u.full_name,
       u.position,
       'IT Architecture & Data Engineering',
       COALESCE(u.work_mode, 'hybrid'),
       CURRENT_TIMESTAMP
FROM users u
WHERE u.role IN ('admin', 'manager')
  AND NOT EXISTS (
      SELECT 1 FROM employees e WHERE e.user_id = u.id
  );

-- Keep account/profile identity fields synchronized for the newly linked profiles.
UPDATE employees e
SET full_name = u.full_name,
    position = COALESCE(u.position, e.position),
    work_mode = COALESCE(u.work_mode, e.work_mode)
FROM users u
WHERE e.user_id = u.id
  AND u.role IN ('admin', 'manager');

-- Demo competency records for privileged users. These are inserted only when a
-- profile does not already have the same skill assessment.
WITH desired(role, skill_name, current_level, required_level) AS (
    VALUES
        ('admin',   'Communication', 4, 4),
        ('admin',   'Agile/Scrum',   3, 4),
        ('admin',   'SQL',           3, 3),
        ('manager', 'Communication', 4, 5),
        ('manager', 'Agile/Scrum',   4, 4),
        ('manager', 'SQL',           3, 4)
)
INSERT INTO competency_assessments
    (employee_id, skill_id, current_level, required_level, assessed_on, notes, created_at)
SELECT e.id,
       s.id,
       d.current_level,
       d.required_level,
       CURRENT_DATE - 7,
       'Initial demo competency record for role-holder profile.',
       CURRENT_TIMESTAMP
FROM users u
JOIN employees e ON e.user_id = u.id
JOIN desired d ON d.role = u.role
JOIN skills s ON s.name = d.skill_name
WHERE u.role IN ('admin', 'manager')
  AND NOT EXISTS (
      SELECT 1
      FROM competency_assessments ca
      WHERE ca.employee_id = e.id
        AND ca.skill_id = s.id
  );

COMMIT;

-- Verification: every Administrator / Manager should now have their own Employee row.
SELECT u.id AS user_id, u.username, u.full_name, u.role,
       e.id AS employee_id, e.full_name AS employee_name,
       e.position, e.team, e.work_mode
FROM users u
LEFT JOIN employees e ON e.user_id = u.id
WHERE u.role IN ('admin', 'manager')
ORDER BY u.role, u.full_name;

-- Verification: show the personal competency records created/preserved for those users.
SELECT u.username, u.full_name, s.name AS skill,
       ca.current_level, ca.required_level,
       GREATEST(ca.required_level - ca.current_level, 0) AS gap
FROM users u
JOIN employees e ON e.user_id = u.id
JOIN competency_assessments ca ON ca.employee_id = e.id
JOIN skills s ON s.id = ca.skill_id
WHERE u.role IN ('admin', 'manager')
ORDER BY u.full_name, s.name;

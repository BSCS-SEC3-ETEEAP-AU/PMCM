-- Ensure every employee/team-member profile is backed by a login account.
-- Demo/backfill accounts use password: password123

-- 1) Link any existing user that already has the same full name.
UPDATE employees e
SET user_id = u.id
FROM users u
WHERE e.user_id IS NULL
  AND lower(trim(e.full_name)) = lower(trim(u.full_name))
  AND NOT EXISTS (
      SELECT 1 FROM employees linked WHERE linked.user_id = u.id
  )
  AND (
      SELECT COUNT(*)
      FROM employees candidate
      WHERE candidate.user_id IS NULL
        AND lower(trim(candidate.full_name)) = lower(trim(u.full_name))
  ) = 1;

-- 2) Create employee-role accounts for any remaining unlinked profiles.
INSERT INTO users (
    username, password_hash, full_name, email, role, work_mode, position, is_active, created_at
)
SELECT
    'emp_' || regexp_replace(lower(trim(e.full_name)), '[^a-z0-9]+', '_', 'g') || '_' || e.id,
    'pbkdf2:sha256:600000$a68bf4898756d9c4$cfabfcf533d7f3d5adf42f4ae44c09a9a15d6fbf29fb40ca0d532ee156c6d944',
    e.full_name,
    NULL,
    'employee',
    COALESCE(e.work_mode, 'hybrid'),
    e.position,
    TRUE,
    CURRENT_TIMESTAMP
FROM employees e
WHERE e.user_id IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM users u
      WHERE u.username = 'emp_' || regexp_replace(lower(trim(e.full_name)), '[^a-z0-9]+', '_', 'g') || '_' || e.id
  );

-- 3) Link the newly created accounts back to their employee profiles.
UPDATE employees e
SET user_id = u.id
FROM users u
WHERE e.user_id IS NULL
  AND u.username = 'emp_' || regexp_replace(lower(trim(e.full_name)), '[^a-z0-9]+', '_', 'g') || '_' || e.id;

-- 4) Enforce one employee profile per login account and disallow profile-only staff.
ALTER TABLE employees
    ALTER COLUMN user_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_employees_user_id'
    ) THEN
        ALTER TABLE employees
            ADD CONSTRAINT uq_employees_user_id UNIQUE (user_id);
    END IF;
END $$;

-- Verification: every team member now has exactly one login account.
SELECT
    e.id AS employee_id,
    e.full_name,
    u.username,
    u.role,
    u.is_active AS account_active
FROM employees e
JOIN users u ON u.id = e.user_id
ORDER BY e.full_name;

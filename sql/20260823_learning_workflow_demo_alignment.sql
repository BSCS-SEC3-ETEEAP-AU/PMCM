-- Align the Scrum demo resource with the Level 5 managerial requirement used
-- in the final-defense scenario. This is a data update only; no schema change.
UPDATE learning_resources lr
SET title = 'Professional Scrum Master Advanced Preparation',
    description = 'Advanced Scrum leadership and certification preparation.',
    target_level = 5,
    provider = 'Scrum.org',
    access_type = 'External',
    url = 'https://www.scrum.org/professional-scrum-master-certification'
WHERE lr.skill_id = (SELECT id FROM skills WHERE name = 'Agile/Scrum')
  AND lr.provider = 'Scrum.org';

SELECT lr.id, lr.title, s.name AS skill, lr.target_level, lr.provider, lr.access_type, lr.url
FROM learning_resources lr
JOIN skills s ON s.id = lr.skill_id
WHERE s.name = 'Agile/Scrum'
ORDER BY lr.id;

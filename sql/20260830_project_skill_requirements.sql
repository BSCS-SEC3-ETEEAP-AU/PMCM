-- Project-level competency requirements for team-fit evaluation.
CREATE TABLE IF NOT EXISTS project_skill_requirements (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id),
    required_level INTEGER NOT NULL CHECK (required_level BETWEEN 1 AND 5),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_project_skill_requirement UNIQUE (project_id, skill_id)
);

CREATE INDEX IF NOT EXISTS ix_project_skill_requirements_project_id
    ON project_skill_requirements(project_id);

CREATE INDEX IF NOT EXISTS ix_project_skill_requirements_skill_id
    ON project_skill_requirements(skill_id);

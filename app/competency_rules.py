"""Shared competency requirement rules.

Project-level and task-level requirements are the source of truth for target
proficiency. An employee's assessment stores observed/current proficiency,
while active project membership and assigned work determine the target used
for gap analysis and learning recommendations.
"""
from .models import db, Project, Task, ProjectMember, ProjectSkillRequirement


def active_project_requirements(employee_id):
    """Return active project/task competency requirements keyed by skill id.

    Project-level requirements apply to every member of an active project.
    Active, unfinished task requirements are also included for tasks assigned
    to the employee. When multiple sources require the same skill, the highest
    required level is used as the target. Source projects/tasks are retained
    so the UI can explain where the target came from.
    """
    requirements = {}

    project_rows = (
        db.session.query(ProjectSkillRequirement, Project)
        .join(Project, Project.id == ProjectSkillRequirement.project_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .filter(
            ProjectMember.employee_id == employee_id,
            Project.status == "Active",
        )
        .order_by(Project.name, ProjectSkillRequirement.skill_id)
        .all()
    )

    for requirement, project in project_rows:
        level = max(1, min(5, int(requirement.required_level or 1)))
        entry = requirements.setdefault(requirement.skill_id, {
            "required_level": level,
            "projects": [],
            "tasks": [],
        })
        entry["required_level"] = max(entry["required_level"], level)
        if project.name not in entry["projects"]:
            entry["projects"].append(project.name)

    task_rows = (
        db.session.query(Task, Project)
        .join(Project, Task.project_id == Project.id)
        .filter(
            Task.assignee_id == employee_id,
            Task.required_skill_id.isnot(None),
            Project.status == "Active",
            db.or_(Task.status.is_(None), db.func.lower(Task.status) != "done"),
        )
        .order_by(Project.name, Task.title)
        .all()
    )

    for task, project in task_rows:
        level = max(1, min(5, int(task.required_level or 1)))
        entry = requirements.setdefault(task.required_skill_id, {
            "required_level": level,
            "projects": [],
            "tasks": [],
        })
        entry["required_level"] = max(entry["required_level"], level)
        if project.name not in entry["projects"]:
            entry["projects"].append(project.name)
        entry["tasks"].append({
            "task_id": task.id,
            "task_title": task.title,
            "project_id": project.id,
            "project_name": project.name,
            "required_level": level,
        })

    return requirements

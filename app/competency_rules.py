"""Shared competency requirement rules.

Project/task requirements are the source of truth for target proficiency. An
employee's assessment stores observed/current proficiency, while the active
work assigned to that employee determines the target used for gap analysis and
learning recommendations.
"""
from .models import db, Project, Task


def active_project_requirements(employee_id):
    """Return active, unfinished task requirements keyed by skill id.

    When more than one active task requires the same skill, the highest
    required level is used as the target. Source projects/tasks are retained so
    the UI can explain where the target came from.
    """
    rows = (
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

    requirements = {}
    for task, project in rows:
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

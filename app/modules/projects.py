"""Sprint 1 - Project Management Module.

Supports project creation, task assignment, workflow coordination,
milestone management, and project progress monitoring (thesis Fig. 5).
Manager/Admin create projects & tasks; Employees update their task status.
"""
from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ..models import (
    db, Project, Task, Employee, ProjectMember, ProjectSkillRequirement,
    Milestone, Skill, User, CompetencyAssessment,
)
from ..decorators import manager_required

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")

TASK_STATUSES = ["Backlog", "To Do", "In Progress", "In Review", "Done"]
TASK_PRIORITIES = ["Low", "Medium", "High"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed"]
PROJECT_PRIORITIES = ["Low", "Medium", "High"]


def _can_manage_project(project):
    """Return True when the signed-in user may modify this project."""
    return current_user.role == "admin" or (
        current_user.role == "manager" and project.manager_id == current_user.id
    )


def _require_project_manager(project):
    """Enforce project-level ownership for Manager; Admin may manage any project."""
    if not _can_manage_project(project):
        abort(403)


def _selected_member_ids(project_id):
    return {
        row.employee_id
        for row in ProjectMember.query.filter_by(project_id=project_id).all()
    }


def _active_account_employees():
    """Return workforce profiles backed by an enabled login account."""
    return (
        Employee.query
        .join(User, User.id == Employee.user_id)
        .filter(User.is_active.is_(True))
        .order_by(Employee.full_name)
        .all()
    )


def _employee_capacity_map():
    """Return active project workload and remaining capacity for each employee."""
    active_counts = dict(
        db.session.query(ProjectMember.employee_id, db.func.count(ProjectMember.id))
        .join(Project, Project.id == ProjectMember.project_id)
        .filter(Project.status == "Active")
        .group_by(ProjectMember.employee_id)
        .all()
    )

    capacity_map = {}
    for employee in _active_account_employees():
        active_projects = active_counts.get(employee.id, 0)
        stored_capacity = max(0, employee.project_capacity or 0)
        # Existing demo data may predate capacity controls. Never present a
        # contradictory workload such as 4/3; current assignments establish
        # the minimum effective capacity shown to the manager.
        capacity = max(active_projects, stored_capacity)
        availability_status = employee.availability_status or "Available"
        at_capacity = active_projects >= capacity
        is_available = availability_status == "Available" and not at_capacity
        capacity_map[employee.id] = {
            "active_projects": active_projects,
            "capacity": capacity,
            "remaining": max(0, capacity - active_projects),
            "availability_status": availability_status,
            "at_capacity": at_capacity,
            "is_available": is_available,
        }
    return capacity_map


def _available_employees(capacity_map):
    """Employees eligible to accept a new project assignment."""
    return [
        employee
        for employee in _active_account_employees()
        if capacity_map.get(employee.id, {}).get("is_available")
    ]


def _employee_proficiency_map():
    """Return each employee's latest recorded current proficiency by skill."""
    proficiency_map = {}
    assessments = CompetencyAssessment.query.order_by(
        CompetencyAssessment.employee_id,
        CompetencyAssessment.skill_id,
        CompetencyAssessment.assessed_on,
        CompetencyAssessment.created_at,
        CompetencyAssessment.id,
    ).all()

    # Ordered oldest-to-newest so a later assessment replaces an earlier one.
    for assessment in assessments:
        if assessment.current_level not in range(1, 6):
            continue
        proficiency_map.setdefault(assessment.employee_id, {})[assessment.skill_id] = (
            assessment.current_level
        )
    return proficiency_map


def _parse_project_requirements(valid_skill_ids):
    """Parse project competency requirements submitted by the project form."""
    skill_values = request.form.getlist("requirement_skill_id")
    level_values = request.form.getlist("requirement_level")
    row_count = max(len(skill_values), len(level_values))
    requirements = []
    seen_skill_ids = set()

    for index in range(row_count):
        skill_value = skill_values[index].strip() if index < len(skill_values) else ""
        level_value = level_values[index].strip() if index < len(level_values) else ""
        if not skill_value:
            continue
        if not skill_value.isdigit() or int(skill_value) not in valid_skill_ids:
            return requirements, "Please select a valid skill for each project requirement."
        if not level_value.isdigit() or not 1 <= int(level_value) <= 5:
            return requirements, "Required proficiency must be between Level 1 and Level 5."

        skill_id = int(skill_value)
        if skill_id in seen_skill_ids:
            return requirements, "Each skill can only be added once to a project."
        seen_skill_ids.add(skill_id)
        requirements.append({
            "skill_id": skill_id,
            "required_level": int(level_value),
        })

    return requirements, None


def _saved_project_requirements(project):
    """Return existing project requirements in form-friendly order."""
    return [
        {"skill_id": requirement.skill_id, "required_level": requirement.required_level}
        for requirement in sorted(
            project.skill_requirements,
            key=lambda requirement: requirement.skill.name.lower(),
        )
    ]


def _replace_project_requirements(project_id, requirements):
    """Replace all competency requirements for a project."""
    ProjectSkillRequirement.query.filter_by(project_id=project_id).delete(
        synchronize_session=False
    )
    for requirement in requirements:
        db.session.add(ProjectSkillRequirement(
            project_id=project_id,
            skill_id=requirement["skill_id"],
            required_level=requirement["required_level"],
        ))


@projects_bp.route("/skills/add", methods=["POST"])
@manager_required
def add_project_skill():
    """Allow a Manager/Admin to add a missing competency while planning a project."""
    payload = request.get_json(silent=True) or request.form
    name = " ".join(str(payload.get("name", "")).split())
    category = str(payload.get("category", "Technical")).strip().title()
    description = str(payload.get("description", "")).strip()

    if not name:
        return {"ok": False, "message": "Skill name is required."}, 400
    if len(name) > 120:
        return {"ok": False, "message": "Skill name must be 120 characters or fewer."}, 400
    if category not in ("Technical", "Soft", "Domain"):
        return {"ok": False, "message": "Please select a valid skill category."}, 400

    existing = Skill.query.filter(db.func.lower(Skill.name) == name.lower()).first()
    if existing:
        return {
            "ok": True,
            "existing": True,
            "message": f"'{existing.name}' already exists in the Skills Catalog and was selected.",
            "skill": {
                "id": existing.id,
                "name": existing.name,
                "category": existing.category or category,
            },
        }

    skill = Skill(name=name, category=category, description=description)
    db.session.add(skill)
    db.session.commit()
    return {
        "ok": True,
        "existing": False,
        "message": f"'{skill.name}' was added to the Skills Catalog and selected for this project.",
        "skill": {
            "id": skill.id,
            "name": skill.name,
            "category": skill.category,
        },
    }


@projects_bp.route("/")
@login_required
def list_projects():
    if current_user.role in ("admin", "manager"):
        projects = Project.query.order_by(Project.created_at.desc()).all()
    else:
        # Employee: only projects they are a member of
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        emp_proj = [pm.project_id for pm in ProjectMember.query.filter_by(employee_id=emp.id).all()] if emp else []
        projects = Project.query.filter(Project.id.in_(emp_proj)).order_by(Project.created_at.desc()).all() if emp_proj else []

    project_rows = []
    for project in projects:
        total_tasks = len(project.tasks)
        done_tasks = sum(1 for task in project.tasks if task.status == "Done")
        progress = round(100 * done_tasks / total_tasks) if total_tasks else 0
        project_rows.append({
            "project": project,
            "total_tasks": total_tasks,
            "progress": progress,
            "team_size": ProjectMember.query.filter_by(project_id=project.id).count(),
        })

    deadline_rank = {"overdue": 0, "due-today": 1, "due-soon": 2, "on-track": 3, "no-deadline": 4, "completed": 5}
    priority_rank = {"High": 0, "Medium": 1, "Low": 2}
    project_rows.sort(key=lambda row: (
        deadline_rank.get(row["project"].deadline_state, 4),
        priority_rank.get(row["project"].priority or "Medium", 1),
        row["project"].target_date or date.max,
        row["project"].name.lower(),
    ))

    total = len(project_rows)
    project_summary = {
        "total": total,
        "active": sum(1 for row in project_rows if row["project"].status == "Active"),
        "completed": sum(1 for row in project_rows if row["project"].status == "Completed"),
        "on_hold": sum(1 for row in project_rows if row["project"].status == "On Hold"),
        "avg_progress": round(sum(row["progress"] for row in project_rows) / total) if total else 0,
    }
    return render_template(
        "projects/list.html",
        projects=projects,
        project_rows=project_rows,
        project_summary=project_summary,
    )


@projects_bp.route("/create", methods=["GET", "POST"])
@manager_required
def create_project():
    capacity_map = _employee_capacity_map()
    employee_proficiencies = _employee_proficiency_map()
    skills = Skill.query.order_by(Skill.name).all()
    valid_skill_ids = {skill.id for skill in skills}
    project_requirements = []

    # Show the full workforce for manager visibility, but only eligible employees
    # can be selected for a new project assignment.
    employees = _active_account_employees()
    # Keep assignable employees first. Unavailable employees and employees at
    # capacity remain visible for workforce planning, but are grouped below.
    employees.sort(
        key=lambda employee: (
            not capacity_map.get(employee.id, {}).get("is_available", False),
            employee.full_name.lower(),
        )
    )
    available_employee_ids = {
        employee.id
        for employee in employees
        if capacity_map.get(employee.id, {}).get("is_available")
    }
    selected_member_ids = set()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", "Active")
        priority = request.form.get("priority", "Medium")
        selected_member_ids = {
            int(emp_id) for emp_id in request.form.getlist("members") if emp_id.isdigit()
        }
        project_requirements, requirement_error = _parse_project_requirements(
            valid_skill_ids
        )
        if requirement_error:
            flash(requirement_error, "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=None,
                project_requirements=project_requirements,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )

        invalid_member_ids = selected_member_ids - available_employee_ids
        if invalid_member_ids:
            flash(
                "One or more selected employees are unavailable or already at project capacity. "
                "Please review the team selection.",
                "danger",
            )
            selected_member_ids &= available_employee_ids
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=None,
                project_requirements=project_requirements,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )
        if not name:
            flash("Project name is required.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=None,
                project_requirements=project_requirements,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )
        if status not in PROJECT_STATUSES:
            flash("Invalid project status.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=None,
                project_requirements=project_requirements,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )
        if priority not in PROJECT_PRIORITIES:
            flash("Invalid project priority.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=None,
                project_requirements=project_requirements,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )

        proj = Project(
            name=name,
            description=request.form.get("description", ""),
            manager_id=current_user.id,
            status=status,
            priority=priority,
            start_date=_date(request.form.get("start_date")),
            target_date=_date(request.form.get("target_date")),
            completed_at=datetime.utcnow() if status == "Completed" else None,
        )
        db.session.add(proj)
        db.session.flush()
        for emp_id in selected_member_ids:
            db.session.add(ProjectMember(project_id=proj.id, employee_id=emp_id))
        _replace_project_requirements(proj.id, project_requirements)
        db.session.commit()
        flash(f"Project '{name}' created.", "success")
        return redirect(url_for("projects.detail", project_id=proj.id))

    return render_template(
        "projects/form.html",
        employees=employees, skills=skills, project=None,
        project_requirements=project_requirements,
        selected_member_ids=selected_member_ids,
        project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES, employee_capacity=capacity_map,
        employee_proficiencies=employee_proficiencies,
    )


@projects_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@manager_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    _require_project_manager(project)
    selected_member_ids = _selected_member_ids(project_id)
    capacity_map = _employee_capacity_map()
    employee_proficiencies = _employee_proficiency_map()
    active_employees = _active_account_employees()
    active_account_employee_ids = {employee.id for employee in active_employees}
    historical_members = (
        Employee.query
        .filter(Employee.id.in_(selected_member_ids - active_account_employee_ids))
        .order_by(Employee.full_name)
        .all()
        if selected_member_ids - active_account_employee_ids
        else []
    )
    employees = active_employees + historical_members
    # Keep current project members first, then employees who can accept a new
    # assignment, then unavailable/at-capacity employees for manager visibility.
    employees.sort(key=lambda employee: (
        employee.id not in selected_member_ids,
        not capacity_map.get(employee.id, {}).get("is_available", False),
        employee.full_name.lower(),
    ))
    eligible_new_member_ids = {
        employee.id
        for employee in active_employees
        if capacity_map.get(employee.id, {}).get("is_available", False)
    }
    skills = Skill.query.order_by(Skill.name).all()
    valid_skill_ids = {skill.id for skill in skills}
    project_requirements = _saved_project_requirements(project)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", project.status)
        priority = request.form.get("priority", project.priority or "Medium")
        posted_member_ids = {
            int(emp_id) for emp_id in request.form.getlist("members") if emp_id.isdigit()
        }
        # Current members may remain even if they are now unavailable or at
        # capacity. Capacity/availability rules apply only to newly added members.
        allowed_member_ids = eligible_new_member_ids | selected_member_ids
        invalid_member_ids = posted_member_ids - allowed_member_ids
        if invalid_member_ids:
            flash(
                "One or more newly selected employees are unavailable or already at project capacity.",
                "danger",
            )
            posted_member_ids &= allowed_member_ids

        project_requirements, requirement_error = _parse_project_requirements(
            valid_skill_ids
        )
        if requirement_error:
            flash(requirement_error, "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=project,
                project_requirements=project_requirements,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
                active_account_employee_ids=active_account_employee_ids,
                employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )

        if not name:
            flash("Project name is required.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=project,
                project_requirements=project_requirements,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
                active_account_employee_ids=active_account_employee_ids,
                employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )
        if status not in PROJECT_STATUSES:
            flash("Invalid project status.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=project,
                project_requirements=project_requirements,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
                active_account_employee_ids=active_account_employee_ids,
                employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )
        if priority not in PROJECT_PRIORITIES:
            flash("Invalid project priority.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=project,
                project_requirements=project_requirements,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
                active_account_employee_ids=active_account_employee_ids,
                employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )

        # Do not remove a member who still owns tasks in this project.
        assigned_employee_ids = {
            task.assignee_id
            for task in project.tasks
            if task.assignee_id is not None and task.status != "Done"
        }
        blocked_removals = assigned_employee_ids - posted_member_ids
        if blocked_removals:
            blocked_names = [
                emp.full_name
                for emp in Employee.query.filter(Employee.id.in_(blocked_removals)).all()
            ]
            flash(
                "Reassign tasks before removing these project members: "
                + ", ".join(sorted(blocked_names)),
                "danger",
            )
            return render_template(
                "projects/form.html",
                employees=employees, skills=skills, project=project,
                project_requirements=project_requirements,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
                active_account_employee_ids=active_account_employee_ids,
                employee_capacity=capacity_map,
                employee_proficiencies=employee_proficiencies,
            )

        previous_status = project.status
        project.name = name
        project.description = request.form.get("description", "")
        project.status = status
        project.priority = priority
        project.start_date = _date(request.form.get("start_date"))
        project.target_date = _date(request.form.get("target_date"))
        if status == "Completed" and previous_status != "Completed":
            project.completed_at = datetime.utcnow()
        elif status != "Completed" and previous_status == "Completed":
            project.completed_at = None

        existing_links = ProjectMember.query.filter_by(project_id=project_id).all()
        existing_ids = {link.employee_id for link in existing_links}
        for link in existing_links:
            if link.employee_id not in posted_member_ids:
                db.session.delete(link)
        for emp_id in posted_member_ids - existing_ids:
            db.session.add(ProjectMember(project_id=project_id, employee_id=emp_id))

        _replace_project_requirements(project_id, project_requirements)
        db.session.commit()
        flash(f"Project '{project.name}' updated.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template(
        "projects/form.html",
        employees=employees, skills=skills, project=project,
        project_requirements=project_requirements,
        selected_member_ids=selected_member_ids,
        project_statuses=PROJECT_STATUSES, project_priorities=PROJECT_PRIORITIES,
        active_account_employee_ids=active_account_employee_ids,
        employee_capacity=capacity_map,
        employee_proficiencies=employee_proficiencies,
    )


@projects_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Employees may only open projects where they are an assigned member.
    if current_user.role == "employee":
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        is_member = (
            emp is not None
            and ProjectMember.query.filter_by(
                project_id=project_id, employee_id=emp.id
            ).first() is not None
        )
        if not is_member:
            abort(403)
    elif current_user.role not in ("admin", "manager"):
        abort(403)

    tasks = Task.query.filter_by(project_id=project_id).all()
    members = (
        db.session.query(Employee)
        .join(ProjectMember, ProjectMember.employee_id == Employee.id)
        .filter(ProjectMember.project_id == project_id)
        .order_by(Employee.full_name)
        .all()
    )
    assignable_members = (
        db.session.query(Employee)
        .join(ProjectMember, ProjectMember.employee_id == Employee.id)
        .join(User, User.id == Employee.user_id)
        .filter(ProjectMember.project_id == project_id, User.is_active.is_(True))
        .order_by(Employee.full_name)
        .all()
    )
    milestones = Milestone.query.filter_by(project_id=project_id).order_by(Milestone.due_date).all()
    skills = Skill.query.order_by(Skill.name).all()
    project_requirements = sorted(
        project.skill_requirements, key=lambda requirement: requirement.skill.name.lower()
    )
    project_skill_ids = {requirement.skill_id for requirement in project_requirements}

    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "Done")
    progress = round(100 * done / total) if total else 0
    can_manage_project = _can_manage_project(project)

    return render_template(
        "projects/detail.html",
        project=project, tasks=tasks, members=members,
        milestones=milestones, skills=skills, employees=assignable_members,
        project_requirements=project_requirements, project_skill_ids=project_skill_ids,
        progress=progress, statuses=TASK_STATUSES,
        can_manage_project=can_manage_project,
    )


@projects_bp.route("/<int:project_id>/task/create", methods=["POST"])
@manager_required
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    _require_project_manager(project)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))

    assignee_id = int(request.form.get("assignee_id") or 0) or None
    if assignee_id:
        assignee = (
            Employee.query
            .join(User, User.id == Employee.user_id)
            .filter(Employee.id == assignee_id, User.is_active.is_(True))
            .first()
        )
        is_project_member = ProjectMember.query.filter_by(
            project_id=project_id, employee_id=assignee_id
        ).first()
        if not assignee or not is_project_member:
            flash("Tasks can only be assigned to active-account members of this project.", "danger")
            return redirect(url_for("projects.detail", project_id=project_id))

    status = request.form.get("status", "Backlog")
    if status not in TASK_STATUSES:
        flash("Invalid task status.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))
    priority = request.form.get("priority", "Medium")
    if priority not in TASK_PRIORITIES:
        flash("Invalid task priority.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))

    now = datetime.utcnow()
    started_at = now if status in ("In Progress", "In Review", "Done") else None
    completed_at = now if status == "Done" else None
    task = Task(
        project_id=project_id,
        title=title,
        description=request.form.get("description", ""),
        assignee_id=assignee_id,
        status=status,
        priority=priority,
        required_skill_id=int(request.form.get("required_skill_id") or 0) or None,
        required_level=int(request.form.get("required_level") or 3),
        due_date=_date(request.form.get("due_date")),
        started_at=started_at,
        completed_at=completed_at,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task added.", "success")
    return redirect(url_for("projects.detail", project_id=project_id))


@projects_bp.route("/task/<int:task_id>/update", methods=["POST"])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)

    # Employees may update only tasks assigned to their own employee profile.
    if current_user.role == "employee":
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        if not emp or task.assignee_id != emp.id:
            abort(403)
    elif current_user.role in ("admin", "manager"):
        _require_project_manager(task.project)
    else:
        abort(403)

    new_status = request.form.get("status")
    if new_status not in TASK_STATUSES:
        flash("Invalid task status.", "danger")
        return redirect(url_for("projects.detail", project_id=task.project_id))

    previous_status = task.status
    now = datetime.utcnow()
    if new_status in ("In Progress", "In Review") and task.started_at is None:
        task.started_at = now
    if new_status == "Done":
        if task.started_at is None:
            task.started_at = task.created_at or now
        if previous_status != "Done" or task.completed_at is None:
            task.completed_at = now
    elif previous_status == "Done":
        # A reopened task should no longer count as completed until it reaches Done again.
        task.completed_at = None

    task.status = new_status
    task.updated_at = now
    db.session.commit()
    flash(f"Task '{task.title}' → {new_status}.", "success")
    return redirect(url_for("projects.detail", project_id=task.project_id))


@projects_bp.route("/<int:project_id>/milestone/create", methods=["POST"])
@manager_required
def create_milestone(project_id):
    project = Project.query.get_or_404(project_id)
    _require_project_manager(project)
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(Milestone(
            project_id=project_id, title=title,
            due_date=_date(request.form.get("due_date")),
        ))
        db.session.commit()
        flash("Milestone added.", "success")
    return redirect(url_for("projects.detail", project_id=project_id))


@projects_bp.route("/milestone/<int:milestone_id>/update", methods=["POST"])
@manager_required
def update_milestone(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    project = Project.query.get_or_404(milestone.project_id)
    _require_project_manager(project)

    title = request.form.get("title", "").strip()
    if not title:
        flash("Milestone title is required.", "danger")
        return redirect(url_for("projects.detail", project_id=project.id))

    milestone.title = title
    milestone.due_date = _date(request.form.get("due_date"))
    milestone.achieved = request.form.get("achieved") == "on"
    db.session.commit()
    flash(f"Milestone '{milestone.title}' updated.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


def _date(v):
    from datetime import datetime
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None

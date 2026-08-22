"""Sprint 1 - Project Management Module.

Supports project creation, task assignment, workflow coordination,
milestone management, and project progress monitoring (thesis Fig. 5).
Manager/Admin create projects & tasks; Employees update their task status.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ..models import (
    db, Project, Task, Employee, ProjectMember, Milestone, Skill, User,
)
from ..decorators import manager_required

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")

TASK_STATUSES = ["Backlog", "To Do", "In Progress", "In Review", "Done"]
PROJECT_STATUSES = ["Active", "On Hold", "Completed"]


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
    employees = Employee.query.order_by(Employee.full_name).all()
    selected_member_ids = set()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", "Active")
        selected_member_ids = {
            int(emp_id) for emp_id in request.form.getlist("members") if emp_id.isdigit()
        }
        if not name:
            flash("Project name is required.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees,
                project=None,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES,
            )
        if status not in PROJECT_STATUSES:
            flash("Invalid project status.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees,
                project=None,
                selected_member_ids=selected_member_ids,
                project_statuses=PROJECT_STATUSES,
            )
        proj = Project(
            name=name,
            description=request.form.get("description", ""),
            manager_id=current_user.id,
            status=status,
            start_date=_date(request.form.get("start_date")),
            target_date=_date(request.form.get("target_date")),
        )
        db.session.add(proj)
        db.session.flush()
        for emp_id in selected_member_ids:
            db.session.add(ProjectMember(project_id=proj.id, employee_id=emp_id))
        db.session.commit()
        flash(f"Project '{name}' created.", "success")
        return redirect(url_for("projects.detail", project_id=proj.id))
    return render_template(
        "projects/form.html",
        employees=employees,
        project=None,
        selected_member_ids=selected_member_ids,
        project_statuses=PROJECT_STATUSES,
    )


@projects_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@manager_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    _require_project_manager(project)
    employees = Employee.query.order_by(Employee.full_name).all()
    selected_member_ids = _selected_member_ids(project_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        status = request.form.get("status", project.status)
        posted_member_ids = {
            int(emp_id) for emp_id in request.form.getlist("members") if emp_id.isdigit()
        }

        if not name:
            flash("Project name is required.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees,
                project=project,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES,
            )
        if status not in PROJECT_STATUSES:
            flash("Invalid project status.", "danger")
            return render_template(
                "projects/form.html",
                employees=employees,
                project=project,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES,
            )

        # Do not remove a member who still owns tasks in this project.
        assigned_employee_ids = {
            task.assignee_id for task in project.tasks if task.assignee_id is not None
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
                employees=employees,
                project=project,
                selected_member_ids=posted_member_ids,
                project_statuses=PROJECT_STATUSES,
            )

        project.name = name
        project.description = request.form.get("description", "")
        project.status = status
        project.start_date = _date(request.form.get("start_date"))
        project.target_date = _date(request.form.get("target_date"))

        existing_links = ProjectMember.query.filter_by(project_id=project_id).all()
        existing_ids = {link.employee_id for link in existing_links}
        for link in existing_links:
            if link.employee_id not in posted_member_ids:
                db.session.delete(link)
        for emp_id in posted_member_ids - existing_ids:
            db.session.add(ProjectMember(project_id=project_id, employee_id=emp_id))

        db.session.commit()
        flash(f"Project '{project.name}' updated.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template(
        "projects/form.html",
        employees=employees,
        project=project,
        selected_member_ids=selected_member_ids,
        project_statuses=PROJECT_STATUSES,
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
        .all()
    )
    milestones = Milestone.query.filter_by(project_id=project_id).order_by(Milestone.due_date).all()
    skills = Skill.query.order_by(Skill.name).all()

    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "Done")
    progress = round(100 * done / total) if total else 0
    can_manage_project = _can_manage_project(project)

    return render_template(
        "projects/detail.html",
        project=project, tasks=tasks, members=members,
        milestones=milestones, skills=skills, employees=members,
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
    if assignee_id and not ProjectMember.query.filter_by(
        project_id=project_id, employee_id=assignee_id
    ).first():
        flash("Tasks can only be assigned to members of this project.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))

    status = request.form.get("status", "Backlog")
    if status not in TASK_STATUSES:
        flash("Invalid task status.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))

    task = Task(
        project_id=project_id,
        title=title,
        description=request.form.get("description", ""),
        assignee_id=assignee_id,
        status=status,
        priority=request.form.get("priority", "Medium"),
        required_skill_id=int(request.form.get("required_skill_id") or 0) or None,
        required_level=int(request.form.get("required_level") or 3),
        due_date=_date(request.form.get("due_date")),
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

    task.status = new_status
    task.updated_at = db.func.now()
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

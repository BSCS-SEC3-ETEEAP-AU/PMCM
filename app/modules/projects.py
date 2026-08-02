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


@projects_bp.route("/")
@login_required
def list_projects():
    if current_user.role in ("admin", "manager"):
        projects = Project.query.order_by(Project.created_at.desc()).all()
    else:
        # Employee: only projects they are a member of
        member_project_ids = [pm.project_id for pm in ProjectMember.query.all()]
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        emp_proj = [pm.project_id for pm in ProjectMember.query.filter_by(employee_id=emp.id).all()] if emp else []
        projects = Project.query.filter(Project.id.in_(emp_proj)).all() if emp_proj else []
    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/create", methods=["GET", "POST"])
@manager_required
def create_project():
    employees = Employee.query.order_by(Employee.full_name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Project name is required.", "danger")
            return render_template("projects/form.html", employees=employees)
        proj = Project(
            name=name,
            description=request.form.get("description", ""),
            manager_id=current_user.id,
            status=request.form.get("status", "Active"),
            start_date=_date(request.form.get("start_date")),
            target_date=_date(request.form.get("target_date")),
        )
        db.session.add(proj)
        db.session.commit()
        # assign members
        for emp_id in request.form.getlist("members"):
            db.session.add(ProjectMember(project_id=proj.id, employee_id=int(emp_id)))
        flash(f"Project '{name}' created.", "success")
        return redirect(url_for("projects.detail", project_id=proj.id))
    return render_template("projects/form.html", employees=employees)


@projects_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()
    members = (
        db.session.query(Employee)
        .join(ProjectMember, ProjectMember.employee_id == Employee.id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )
    milestones = Milestone.query.filter_by(project_id=project_id).order_by(Milestone.due_date).all()
    skills = Skill.query.order_by(Skill.name).all()
    employees = Employee.query.order_by(Employee.full_name).all()

    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "Done")
    progress = round(100 * done / total) if total else 0

    return render_template(
        "projects/detail.html",
        project=project, tasks=tasks, members=members,
        milestones=milestones, skills=skills, employees=employees,
        progress=progress, statuses=["Backlog", "To Do", "In Progress", "In Review", "Done"],
    )


@projects_bp.route("/<int:project_id>/task/create", methods=["POST"])
@manager_required
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))
    task = Task(
        project_id=project_id,
        title=title,
        description=request.form.get("description", ""),
        assignee_id=int(request.form.get("assignee_id") or 0) or None,
        status=request.form.get("status", "Backlog"),
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
    new_status = request.form.get("status")
    if new_status:
        task.status = new_status
        task.updated_at = db.func.now()
        db.session.commit()
        flash(f"Task '{task.title}' → {new_status}.", "success")
    return redirect(url_for("projects.detail", project_id=task.project_id))


@projects_bp.route("/<int:project_id>/milestone/create", methods=["POST"])
@manager_required
def create_milestone(project_id):
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(Milestone(
            project_id=project_id, title=title,
            due_date=_date(request.form.get("due_date")),
        ))
        db.session.commit()
        flash("Milestone added.", "success")
    return redirect(url_for("projects.detail", project_id=project_id))


def _date(v):
    from datetime import datetime
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None
